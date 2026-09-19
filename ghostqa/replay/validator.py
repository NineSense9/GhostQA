"""Replay validation: confirm candidate bugs by re-executing a trace
from a clean reset.

The caller MUST pass an episode-local executable sequence (see
RunResult.reproduction_actions). This module never slices by
finding.step_index — that index is global and crosses reset boundaries.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ..oracle.engine import OracleEngine
from ..state.models import Finding
from ..state.signature import state_signature

PASS, FAIL, INVALID = "PASS", "FAIL", "INVALID"


@dataclass
class ValidationResult:
    confirmed: bool
    attempts: int
    reproduced_finding: Finding = None
    detail: str = ""
    status: str = ""
    failed_action_index: int = None
    failed_action: str = ""
    last_url: str = ""
    target_fingerprint: str = ""
    observed_fingerprints: list = field(default_factory=list)


def _replay(executor_factory, actions, oracle: OracleEngine):
    """Execute `actions` on a fresh executor (one reset, then the sequence).

    Returns (status, findings, diag).
    """
    executor = executor_factory()
    oracle = oracle or OracleEngine()
    state = executor.reset()
    hist = [state_signature(state)]
    sig_url = {hist[0]: state.url}
    effective_clicks = set()
    all_findings: list = []
    last_url = getattr(state, "url", "") or ""
    fps = []
    for i, action in enumerate(actions):
        result = executor.execute(action)
        if not result.ok:
            return INVALID, all_findings, {
                "failed_action_index": i,
                "failed_action": action.brief() if hasattr(action, "brief") else str(action),
                "last_url": last_url,
                "observed_fingerprints": fps,
            }
        new_state = result.state if not result.crashed else None
        findings = oracle.inspect(state, action, result, new_state, {
            "step_index": i, "history_sigs": hist,
            "ground_truth": executor.ground_truth() if not result.crashed else {},
            "sig_url_map": sig_url,
            "effective_clicks": effective_clicks,
        })
        all_findings.extend(findings)
        fps.extend(f.fingerprint() for f in findings)
        if result.crashed:
            return "CRASHED", all_findings, {
                "failed_action_index": i,
                "failed_action": action.brief() if hasattr(action, "brief") else str(action),
                "last_url": last_url,
                "observed_fingerprints": fps,
            }
        if action.type == "click":
            new_sig = state_signature(new_state)
            if (result.events or new_sig != hist[-1]
                    or new_state.obs != state.obs):
                effective_clicks.add((hist[-1], action.target_eid))
        state = new_state
        last_url = state.url if state else last_url
        sig = state_signature(state)
        hist.append(sig)
        sig_url[sig] = state.url
    return "OK", all_findings, {
        "failed_action_index": None,
        "failed_action": "",
        "last_url": last_url,
        "observed_fingerprints": fps,
    }


def make_bug_test(executor_factory, target_fingerprint: str, oracle: OracleEngine):
    """Build a tri-state predicate for ddmin.

    test(actions) -> "PASS" | "FAIL" | "INVALID"
    """
    def test(actions) -> str:
        status, findings, _diag = _replay(executor_factory, actions, oracle)
        if status == INVALID:
            return INVALID
        for f in findings:
            if f.fingerprint() == target_fingerprint:
                return PASS
        return FAIL
    return test


def validate_reproduction(executor_factory, actions: list,
                          target_fingerprint: str, oracle: OracleEngine,
                          retries: int = 2) -> ValidationResult:
    """Reset, execute the given sequence in full, match fingerprint."""
    attempts = 0
    last_diag = {}
    last_status = FAIL
    for _ in range(1 + retries):
        attempts += 1
        status, findings, diag = _replay(executor_factory, actions, oracle)
        last_diag, last_status = diag, status
        if status == INVALID:
            return ValidationResult(
                confirmed=False, attempts=attempts,
                detail="replay sequence invalid", status=INVALID,
                failed_action_index=diag.get("failed_action_index"),
                failed_action=diag.get("failed_action", ""),
                last_url=diag.get("last_url", ""),
                target_fingerprint=target_fingerprint,
                observed_fingerprints=diag.get("observed_fingerprints", []),
            )
        for f in findings:
            if f.fingerprint() == target_fingerprint:
                return ValidationResult(
                    confirmed=True, attempts=attempts, reproduced_finding=f,
                    status=PASS, last_url=diag.get("last_url", ""),
                    target_fingerprint=target_fingerprint,
                    observed_fingerprints=diag.get("observed_fingerprints", []),
                )
    return ValidationResult(
        confirmed=False, attempts=attempts,
        detail="not reproduced after retries", status=last_status or FAIL,
        failed_action_index=last_diag.get("failed_action_index"),
        failed_action=last_diag.get("failed_action", ""),
        last_url=last_diag.get("last_url", ""),
        target_fingerprint=target_fingerprint,
        observed_fingerprints=last_diag.get("observed_fingerprints", []),
    )


def validate_candidate(executor_factory, actions: list, finding: Finding,
                       oracle: OracleEngine, retries: int = 2) -> ValidationResult:
    """Confirm `finding` by replaying the given episode-local actions.

    Does **not** slice `actions` with `finding.step_index`. Callers must
    pass RunResult.reproduction_actions(finding) (or an equivalent
    executable prefix from a clean reset).
    """
    return validate_reproduction(
        executor_factory, actions, finding.fingerprint(), oracle, retries)
