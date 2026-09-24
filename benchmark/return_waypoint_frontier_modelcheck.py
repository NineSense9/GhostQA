"""Pure lifecycle model of return-waypoint frontier escape.

Enumerates every token string of length 1..5 over R, T, U, P, F, N, E, C.
Impossible transitions are rejected without changing state. Possible
transitions must keep the lifecycle invariants. This checker does not read
application traces and does not choose actions.
"""
from __future__ import annotations

import itertools
from dataclasses import dataclass

ALPHABET = ("R", "T", "U", "P", "F", "N", "E", "C")
RAW_TRACE_COUNT = sum(len(ALPHABET) ** length for length in range(1, 6))


@dataclass
class ModelState:
    phase: str = "idle"
    resumed: bool = False
    active_return: bool = False
    place: str = ""
    frontier: bool = False
    success: int = 0
    returned: int = 0
    escapes: int = 0
    terminals: int = 0
    suppressed: bool = False
    stack: int = 0
    ranked: int = 0
    started: int = 0
    completed: int = 0


def initial_state() -> ModelState:
    return ModelState()


def _copy(state: ModelState) -> ModelState:
    return ModelState(
        phase=state.phase,
        resumed=state.resumed,
        active_return=state.active_return,
        place=state.place,
        frontier=state.frontier,
        success=state.success,
        returned=state.returned,
        escapes=state.escapes,
        terminals=state.terminals,
        suppressed=state.suppressed,
        stack=state.stack,
        ranked=state.ranked,
        started=state.started,
        completed=state.completed,
    )


def _invariants(state: ModelState) -> list:
    failures = []
    if state.stack < 0:
        failures.append("negative_stack")
    if min(state.success, state.returned, state.escapes, state.terminals, state.completed) < 0:
        failures.append("negative_count")
    if state.success != state.returned or state.completed != state.success:
        failures.append("false_success")
    if state.ranked != 0:
        failures.append("escape_ranked_action")
    if state.escapes > 1 or state.terminals > 1:
        failures.append("duplicate_terminal")
    if state.escapes and (not state.resumed or state.success or state.returned or state.ranked):
        failures.append("escape_accounting")
    if state.phase == "escaped" and (
        state.escapes != 1 or state.terminals != 1 or state.active_return
        or state.success or state.returned or not state.suppressed
        or state.place != "known" or not state.frontier or state.stack != 0
        or not state.resumed or state.ranked
    ):
        failures.append("escape_shape")
    if state.phase == "completed" and (
        state.success != 1 or state.returned != 1 or state.escapes
        or state.active_return or state.terminals != 1 or state.place != "parent"
    ):
        failures.append("parent_completion")
    if state.phase == "abandoned" and (
        state.success or state.returned or state.escapes or state.active_return
        or state.terminals != 1
    ):
        failures.append("cycle_accounting")
    if state.place == "unknown" and state.escapes:
        failures.append("unknown_hub_escape")
    if state.place == "parent" and state.escapes:
        failures.append("parent_escape")
    if state.phase == "idle" and (
        state.resumed or state.active_return or state.escapes or state.terminals
        or state.success or state.frontier or state.place
    ):
        failures.append("idle_dirty")
    return failures


def apply_token(state: ModelState, token: str):
    """Return (state, status, failures). Impossible leaves the prior state."""
    if token not in ALPHABET or state.phase in ("escaped", "completed", "abandoned"):
        return state, "impossible", []
    nxt = _copy(state)
    if token == "R":
        if state.phase != "idle" or state.stack != 0:
            return state, "impossible", []
        nxt.phase = "resumed"
        nxt.resumed = True
        nxt.active_return = True
        nxt.started = 1
        nxt.stack = 0
        nxt.place = ""
        nxt.frontier = False
    elif token == "T":
        if not state.resumed or not state.active_return or state.stack != 0 or state.place == "parent":
            return state, "impossible", []
        nxt.place = "known"
        nxt.phase = "known"
    elif token == "U":
        if not state.resumed or not state.active_return or state.stack != 0:
            return state, "impossible", []
        nxt.place = "unknown"
        nxt.phase = "unknown"
    elif token == "P":
        if not state.resumed or not state.active_return or state.stack != 0 or state.terminals:
            return state, "impossible", []
        nxt.place = "parent"
        nxt.phase = "completed"
        nxt.active_return = False
        nxt.success = 1
        nxt.returned = 1
        nxt.completed = 1
        nxt.terminals = 1
    elif token == "F":
        if not state.active_return:
            return state, "impossible", []
        nxt.frontier = True
    elif token == "N":
        if not state.active_return:
            return state, "impossible", []
        nxt.frontier = False
    elif token == "C":
        if not state.active_return or state.terminals or state.escapes:
            return state, "impossible", []
        nxt.phase = "abandoned"
        nxt.active_return = False
        nxt.terminals = 1
    elif token == "E":
        if not (
            state.resumed and state.active_return and state.place == "known"
            and state.frontier and not state.suppressed and state.stack == 0
            and state.terminals == 0 and state.success == 0 and state.ranked == 0
        ):
            return state, "impossible", []
        nxt.phase = "escaped"
        nxt.active_return = False
        nxt.escapes = 1
        nxt.terminals = 1
        nxt.suppressed = True
        nxt.ranked = 0
    else:
        return state, "impossible", []
    return nxt, "ok", _invariants(nxt)


def enumerate_traces():
    valid = 0
    rejected = 0
    failures = []
    for length in range(1, 6):
        for tokens in itertools.product(ALPHABET, repeat=length):
            state = initial_state()
            impossible = False
            for index, token in enumerate(tokens):
                state, status, step_failures = apply_token(state, token)
                if status == "impossible":
                    impossible = True
                    break
                if step_failures:
                    failures.append({
                        "trace": "".join(tokens),
                        "index": index,
                        "token": token,
                        "failures": list(step_failures),
                    })
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
    return 0 if report["invariant_failures"] == 0 and report["raw_traces"] == RAW_TRACE_COUNT else 1


if __name__ == "__main__":
    raise SystemExit(main())
