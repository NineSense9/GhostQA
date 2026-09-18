"""Replay validation: confirm candidate bugs by re-executing the trace
in a fresh environment.

Predicate is tri-state:
    PASS    -> bug with the SAME BugFingerprint reproduced
    FAIL    -> sequence executed fully but bug did not reproduce
    INVALID -> sequence itself is not executable end-to-end
               (missing element / unsupported action / premature crash)

A candidate is Confirmed only on PASS. Matching uses BugFingerprint
(finding.fingerprint()), never bare `kind`.
"""
from __future__ import annotations

from dataclasses import dataclass

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


def _replay(executor_factory, actions, oracle: OracleEngine):
    """Execute actions on a fresh executor.

    Returns (status, findings):
      status: "OK" fully executed | "CRASHED" mid-way | "INVALID" not executable
    """
    executor = executor_factory()
    oracle = oracle or OracleEngine()
    state = executor.reset()
    hist = [state_signature(state)]
    sig_url = {hist[0]: state.url}
    effective_clicks = set()
    all_findings: list = []
    for i, action in enumerate(actions):
        result = executor.execute(action)
        if not result.ok:
            return INVALID, all_findings
        new_state = result.state if not result.crashed else None
        findings = oracle.inspect(state, action, result, new_state, {
            "step_index": i, "history_sigs": hist,
            "ground_truth": executor.ground_truth() if not result.crashed else {},
            "sig_url_map": sig_url,
            "effective_clicks": effective_clicks,
        })
        all_findings.extend(findings)
        if result.crashed:
            return "CRASHED", all_findings
        if action.type == "click":
            new_sig = state_signature(new_state)
            if (result.events or new_sig != hist[-1]
                    or new_state.obs != state.obs):
                effective_clicks.add((hist[-1], action.target_eid))
        state = new_state
        sig = state_signature(state)
        hist.append(sig)
        sig_url[sig] = state.url
    return "OK", all_findings


def make_bug_test(executor_factory, target_fingerprint: str, oracle: OracleEngine):
    """Build a tri-state predicate for ddmin.

    test(actions) -> "PASS" | "FAIL" | "INVALID"
    """
    def test(actions) -> str:
        status, findings = _replay(executor_factory, actions, oracle)
        if status == INVALID:
            return INVALID
        for f in findings:
            if f.fingerprint() == target_fingerprint:
                return PASS
        return FAIL
    return test


def validate_candidate(executor_factory, actions: list, finding: Finding,
                       oracle: OracleEngine, retries: int = 2) -> ValidationResult:
    """Replay actions[:finding.step_index+1]; confirm only on fingerprint PASS."""
    prefix = actions[: finding.step_index + 1]
    target = finding.fingerprint()
    attempts = 0
    for _ in range(1 + retries):
        attempts += 1
        status, findings = _replay(executor_factory, prefix, oracle)
        if status == INVALID:
            return ValidationResult(confirmed=False, attempts=attempts,
                                    detail="replay sequence invalid")
        for f in findings:
            if f.fingerprint() == target:
                return ValidationResult(confirmed=True, attempts=attempts,
                                        reproduced_finding=f)
    return ValidationResult(confirmed=False, attempts=attempts,
                            detail="not reproduced after retries")
