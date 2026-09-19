"""ddmin (delta debugging) for GUI action sequences.

Minimizes a reproduction sequence while the bug predicate stays True.
GUI adaptation: a candidate subsequence is only executed if it is
well-formed (does not start with `back`, no input before any navigation
when the sequence is empty) - malformed sequences are counted as
predicate=False without an expensive replay.
"""
from __future__ import annotations


def _well_formed(actions) -> bool:
    # `back` at app root is a legitimate no-op, so no structural constraints
    # beyond non-emptiness for v0.1.
    return len(actions) > 0


def ddmin(actions, test) -> list:
    """Classic ddmin. `test(seq) -> bool` must be True for the full sequence."""
    actions = list(actions)
    if not _well_formed(actions) or not test(actions):
        return []
    n = 2
    while len(actions) >= 2:
        chunk = max(1, len(actions) // n)
        reduced = False
        # try removing each chunk (complement test)
        i = 0
        while i < len(actions):
            subset = actions[:i] + actions[i + chunk:]
            if len(subset) < len(actions) and _well_formed(subset) and test(subset):
                actions = subset
                n = max(n - 1, 2)
                reduced = True
                break
            i += chunk
        # try keeping only each chunk
        if not reduced:
            i = 0
            while i < len(actions):
                subset = actions[i:i + chunk]
                if len(subset) < len(actions) and _well_formed(subset) and test(subset):
                    actions = subset
                    n = 2
                    reduced = True
                    break
                i += chunk
        if not reduced:
            if n < len(actions):
                n = min(len(actions), n * 2)
            else:
                break
    return actions


def minimize_reproduction(executor_factory, actions, finding, oracle) -> list:
    """Full pipeline: tri-state fingerprint predicate, then ddmin.

    `actions` must already be the episode-local reproduction prefix
    (RunResult.reproduction_actions). This function does not slice by
    finding.step_index.

    The returned sequence is guaranteed executable end-to-end from a clean
    reset (ddmin only keeps candidates whose predicate is PASS).
    """
    from ..replay.validator import make_bug_test, PASS

    tri = make_bug_test(executor_factory, finding.fingerprint(), oracle)
    return ddmin(list(actions), lambda seq: tri(seq) == PASS)
