"""Pure episode-drain model.

Enumerates every token string of length 1..5 over S, P, R, X, W, Q, D, F, N.
Impossible transitions are rejected without changing state. Possible
transitions must keep the episode invariants. This checker does not read
application traces and does not choose actions.
"""
from __future__ import annotations

import itertools
from dataclasses import dataclass

ALPHABET = ("S", "P", "R", "X", "W", "Q", "D", "F", "N")
RAW_TRACE_COUNT = sum(len(ALPHABET) ** length for length in range(1, 6))


@dataclass
class ModelState:
    episode: int = 0
    advances: int = 0
    current_same: int = 0
    invalidated_same: int = 0
    cross: int = 0
    witness: bool = False
    replaying: bool = False
    restore_steps: int = 0
    return_success: int = 0
    structural: int = 0
    fake_success: int = 0


def initial_state() -> ModelState:
    return ModelState()


def _copy(state: ModelState) -> ModelState:
    return ModelState(
        episode=state.episode,
        advances=state.advances,
        current_same=state.current_same,
        invalidated_same=state.invalidated_same,
        cross=state.cross,
        witness=state.witness,
        replaying=state.replaying,
        restore_steps=state.restore_steps,
        return_success=state.return_success,
        structural=state.structural,
        fake_success=state.fake_success,
    )


def _invariants(state: ModelState, previous: ModelState, token: str) -> list:
    failures = []
    if min(
        state.episode, state.advances, state.current_same, state.invalidated_same,
        state.cross, state.restore_steps, state.return_success, state.structural,
        state.fake_success,
    ) < 0:
        failures.append("negative")
    if state.episode != state.advances:
        failures.append("episode_without_relocation")
    if state.return_success != 0 or state.fake_success != 0 or state.structural != 0:
        failures.append("false_success_or_structural")
    if state.replaying and state.witness:
        failures.append("witness_during_replay")
    if token == "R":
        if state.episode != previous.episode + 1:
            failures.append("episode_increment")
        if state.cross != previous.cross:
            failures.append("cross_invalidated")
        if state.return_success != previous.return_success:
            failures.append("return_success_changed")
        if state.structural != previous.structural:
            failures.append("structural_changed")
        if state.invalidated_same != previous.invalidated_same + previous.current_same:
            failures.append("same_hub_invalidation")
    if token == "X" and (
        state.current_same != previous.current_same
        or state.invalidated_same != previous.invalidated_same
        or state.cross != previous.cross
        or state.episode != previous.episode
    ):
        failures.append("restore_probe")
    if token == "Q" and previous.invalidated_same <= 0:
        failures.append("q_without_invalidation")
    if token == "D" and state.current_same != previous.current_same:
        failures.append("duplicate_not_suppressed")
    if token == "F" and (
        state.return_success != 0 or state.fake_success != 0
        or state.episode != previous.episode
    ):
        failures.append("failure_success")
    if token == "N" and (
        state.episode or state.current_same or state.cross
        or state.invalidated_same or state.advances or state.replaying
    ):
        failures.append("reset_incomplete")
    return failures


def _check(state: ModelState, previous: ModelState, token: str):
    return state, "possible", _invariants(state, previous, token)


def _apply_open(state: ModelState, token: str):
    if token in ("X", "F"):
        return state, "impossible", []
    nxt = _copy(state)
    if token == "S":
        nxt.current_same += 1
    elif token == "P":
        nxt.cross += 1
    elif token == "R":
        nxt.invalidated_same += state.current_same
        nxt.current_same = 0
        nxt.episode += 1
        nxt.advances += 1
        nxt.replaying = True
        nxt.witness = False
        nxt.restore_steps = 0
    elif token == "W":
        nxt.witness = True
    elif token == "Q":
        if (not state.witness) or state.invalidated_same <= 0:
            return state, "impossible", []
        nxt.invalidated_same -= 1
        nxt.current_same += 1
    elif token == "D":
        if state.current_same <= 0:
            return state, "impossible", []
    else:
        return state, "impossible", []
    return _check(nxt, state, token)


def apply_token(state: ModelState, token: str):
    """Return (state, status, failures). Impossible leaves the prior state."""
    if token not in ALPHABET:
        return state, "impossible", []
    if token == "N":
        return _check(initial_state(), state, token)
    if state.replaying:
        if token == "X":
            nxt = _copy(state)
            nxt.restore_steps += 1
            return _check(nxt, state, token)
        if token == "F":
            nxt = _copy(state)
            nxt.replaying = False
            nxt.restore_steps = 0
            return _check(nxt, state, token)
        if state.restore_steps < 1:
            return state, "impossible", []
        ended = _copy(state)
        ended.replaying = False
        ended.restore_steps = 0
        return _apply_open(ended, token)
    return _apply_open(state, token)


def enumerate_traces() -> dict:
    failures = []
    valid = 0
    rejected = 0
    for length in range(1, 6):
        for tokens in itertools.product(ALPHABET, repeat=length):
            state = initial_state()
            impossible = False
            for token in tokens:
                state, status, step_failures = apply_token(state, token)
                if step_failures:
                    failures.append({
                        "trace": "".join(tokens),
                        "token": token,
                        "failures": list(step_failures),
                    })
                if status == "impossible":
                    impossible = True
                    break
            if impossible:
                rejected += 1
            else:
                valid += 1
    raw = valid + rejected
    return {
        "alphabet": list(ALPHABET),
        "raw_traces": raw,
        "valid_traces": valid,
        "rejected_traces": rejected,
        "invariant_failures": len(failures),
        "failures": failures[:20],
    }


def main(argv=None) -> int:
    del argv
    report = enumerate_traces()
    print(
        f"raw {report['raw_traces']} valid {report['valid_traces']} "
        f"rejected {report['rejected_traces']} "
        f"failures {report['invariant_failures']}")
    if report["failures"]:
        print(report["failures"][:5])
    return 0 if report["invariant_failures"] == 0 and report["raw_traces"] == RAW_TRACE_COUNT else 1


if __name__ == "__main__":
    raise SystemExit(main())
