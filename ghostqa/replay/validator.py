"""Replay validator: a candidate bug is only reported if it reproduces."""
from __future__ import annotations

from dataclasses import dataclass

from ..oracle.engine import OracleEngine
from ..state.signature import state_signature


@dataclass
class ValidationResult:
    confirmed: bool
    attempts: int
    reproduced_kind: str = ""
    note: str = ""


def make_bug_test(executor_factory, kind: str, oracle: OracleEngine,
                  match: dict = None):
    """Build a ddmin predicate: replay the action sequence from scratch and
    return True iff a finding of `kind` (optionally matching evidence) occurs."""
    match = match or {}

    def test(actions) -> bool:
        executor = executor_factory()
        state = executor.reset()
        hist = [state_signature(state)]
        for i, action in enumerate(actions):
            result = executor.execute(action)
            new_state = result.state if not result.crashed else None
            findings = oracle.inspect(state, action, result, new_state, {
                "step_index": i,
                "history_sigs": hist,
                "ground_truth": executor.ground_truth() if not result.crashed else {},
            })
            for f in findings:
                if f.kind != kind:
                    continue
                if all(f.evidence.get(k) == v for k, v in match.items()):
                    return True
            if result.crashed:
                return kind == "crash"
            state = new_state
            hist.append(state_signature(state))
        return False

    return test


def validate_candidate(executor_factory, actions, finding,
                       oracle: OracleEngine, retries: int = 3) -> ValidationResult:
    """Replay the trace up to (and including) the finding step; the same kind of
    finding must reproduce."""
    prefix = actions[: finding.step_index + 1]
    match = {}
    if "assert_id" in finding.evidence:
        match["assert_id"] = finding.evidence["assert_id"]
    elif "eid" in finding.evidence:
        match["eid"] = finding.evidence["eid"]
    test = make_bug_test(executor_factory, finding.kind, oracle, match)
    for attempt in range(1, retries + 1):
        if test(prefix):
            return ValidationResult(confirmed=True, attempts=attempt,
                                    reproduced_kind=finding.kind)
    return ValidationResult(confirmed=False, attempts=retries,
                            note="finding did not reproduce on replay (flaky/false positive)")
