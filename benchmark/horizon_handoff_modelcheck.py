"""Pure lifecycle model of Horizon Handoff stack discipline.

Enumerates every token string of length 1..5 over
C, H, P, V, X, F, E. Impossible transitions are rejected without changing
state. Possible transitions must keep the handoff invariants. This checker
does not read application traces and does not choose exploration actions.
"""
from __future__ import annotations

import itertools
from dataclasses import dataclass, field

ALPHABET = ("C", "H", "P", "V", "X", "F", "E")
RAW_TRACE_COUNT = sum(len(ALPHABET) ** length for length in range(1, 6))


@dataclass
class Frame:
    frame_id: int
    outer_id: int
    child_id: int
    resolved: bool = False


@dataclass
class ModelState:
    commitment: int = 2
    returning: bool = False
    active_id: int = 1
    next_id: int = 2
    next_frame: int = 1
    stack: list = field(default_factory=list)
    success: dict = field(default_factory=dict)
    abandoned: set = field(default_factory=set)
    returned: set = field(default_factory=set)
    resolved_frames: set = field(default_factory=set)
    active_alive: bool = True


def initial_state() -> ModelState:
    """An active sequence just after its historical branch-start action."""
    return ModelState()


def _copy(state: ModelState) -> ModelState:
    return ModelState(
        commitment=state.commitment,
        returning=state.returning,
        active_id=state.active_id,
        next_id=state.next_id,
        next_frame=state.next_frame,
        stack=list(state.stack),
        success=dict(state.success),
        abandoned=set(state.abandoned),
        returned=set(state.returned),
        resolved_frames=set(state.resolved_frames),
        active_alive=state.active_alive,
    )


def _dead(state: ModelState) -> bool:
    return (
        not state.active_alive
        or state.active_id in state.abandoned
        or state.active_id in state.returned
    )


def apply_token(state: ModelState, token: str):
    """Return (new_state, status, failures).

    status is "ok" or "impossible". Impossible leaves the caller on the
    previous state; the returned state is still the unchanged copy.
    """
    nxt = _copy(state)
    failures = []
    depth_before = len(state.stack)
    success_before = sum(state.success.values())

    if token == "C":
        if state.returning or state.commitment <= 1 or _dead(state):
            return state, "impossible", []
        nxt.commitment -= 1
    elif token == "H":
        if state.returning or state.commitment != 1 or _dead(state):
            return state, "impossible", []
        frame = Frame(nxt.next_frame, state.active_id, nxt.next_id)
        nxt.next_frame += 1
        nxt.next_id += 1
        nxt.stack.append(frame)
        nxt.active_id = frame.child_id
        nxt.commitment = 2
        nxt.returning = False
        nxt.active_alive = True
    elif token in ("P", "V"):
        if (not state.stack or _dead(state)
                or state.stack[-1].child_id != state.active_id
                or state.stack[-1].resolved
                or state.stack[-1].frame_id in state.resolved_frames):
            return state, "impossible", []
        frame = nxt.stack.pop()
        if frame.resolved or frame.frame_id in nxt.resolved_frames:
            failures.append("duplicate_resolution")
        frame.resolved = True
        nxt.resolved_frames.add(frame.frame_id)
        nxt.success[frame.child_id] = nxt.success.get(frame.child_id, 0) + 1
        nxt.returned.add(frame.child_id)
        nxt.active_id = frame.outer_id
        nxt.commitment = 0
        nxt.returning = True
        nxt.active_alive = True
        if nxt.success.get(frame.outer_id, 0) != state.success.get(frame.outer_id, 0):
            failures.append("outer_return_success")
    elif token == "X":
        pass
    elif token == "F":
        if _dead(state):
            return state, "impossible", []
        nxt.returning = True
        nxt.commitment = 0
    elif token == "E":
        if not state.returning or _dead(state):
            return state, "impossible", []
        nxt.abandoned.add(nxt.active_id)
        for frame in nxt.stack:
            nxt.abandoned.add(frame.outer_id)
            if frame.frame_id in nxt.resolved_frames:
                failures.append("escape_resolved_frame")
        nxt.stack.clear()
        nxt.returning = False
        nxt.commitment = 0
        nxt.active_alive = False
    else:
        return state, "impossible", []

    depth_after = len(nxt.stack)
    if token == "C" and depth_after != depth_before:
        failures.append("continuation_depth")
    if token == "H" and depth_after != depth_before + 1:
        failures.append("handoff_depth")
    if token in ("P", "V") and depth_after != depth_before - 1:
        failures.append("witness_depth")
    if token in ("X", "F") and depth_after != depth_before:
        failures.append("nonwitness_pop")
    if token == "E" and depth_after != 0:
        failures.append("escape_depth")
    if depth_after < 0:
        failures.append("negative_stack")
    if token in ("P", "V"):
        if not nxt.returning or nxt.commitment != 0:
            failures.append("resume_not_return_phase")
        if sum(nxt.success.values()) != success_before + 1:
            failures.append("success_inflation")
    elif sum(nxt.success.values()) != success_before:
        failures.append("false_return_success")
    if token in ("P", "V") and depth_before < 1:
        failures.append("resume_without_witness")
    return nxt, "ok", failures


def enumerate_traces():
    """Classify every raw trace. Invariant failures stay attached to valid steps."""
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
        "failures": failures,
    }


def main(argv=None) -> int:
    del argv
    report = enumerate_traces()
    print(
        f"raw {report['raw_traces']} valid {report['valid_traces']} "
        f"rejected {report['rejected_traces']} "
        f"invariant_failures {report['invariant_failures']}"
    )
    return 0 if report["invariant_failures"] == 0 and report["raw_traces"] == RAW_TRACE_COUNT else 2


if __name__ == "__main__":
    raise SystemExit(main())
