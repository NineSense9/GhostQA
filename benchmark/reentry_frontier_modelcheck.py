"""Pure lifecycle model of early parent re-entry and local frontier lease.

Enumerates every token string of length 1..5 over
P, V, H, W, L, A, X, N. Impossible transitions are rejected without
changing state. Possible transitions must keep the lifecycle invariants.
This checker does not read application traces and does not choose actions.
"""
from __future__ import annotations

import itertools
from dataclasses import dataclass, field

ALPHABET = ("P", "V", "H", "W", "L", "A", "X", "N")
RAW_TRACE_COUNT = sum(len(ALPHABET) ** length for length in range(1, 6))


@dataclass
class Seq:
    sid: int
    terminal: str = ""


@dataclass
class Frame:
    outer: int
    child: int


@dataclass
class ModelState:
    active: int | None = 1
    commitment: int = 2
    returning: bool = False
    frontier: int = 1
    lease: int = 0
    next_id: int = 2
    seqs: dict = field(default_factory=dict)
    stack: list = field(default_factory=list)
    deferred: set = field(default_factory=set)
    horizon_emitted: set = field(default_factory=set)
    leased_keys: int = 0


def initial_state() -> ModelState:
    """Active sequence just after its opening branch action. One local key."""
    state = ModelState()
    state.seqs = {1: Seq(1)}
    return state


def _copy(state: ModelState) -> ModelState:
    return ModelState(
        active=state.active,
        commitment=state.commitment,
        returning=state.returning,
        frontier=state.frontier,
        lease=state.lease,
        next_id=state.next_id,
        seqs={sid: Seq(seq.sid, seq.terminal) for sid, seq in state.seqs.items()},
        stack=list(state.stack),
        deferred=set(state.deferred),
        horizon_emitted=set(state.horizon_emitted),
        leased_keys=state.leased_keys,
    )


def _dead(state: ModelState, sid: int | None) -> bool:
    if sid is None or sid not in state.seqs:
        return True
    return bool(state.seqs[sid].terminal)


def _mark(state: ModelState, sid: int, outcome: str, failures: list) -> None:
    seq = state.seqs.get(sid)
    if seq is None:
        failures.append("missing_sequence")
        return
    if seq.terminal:
        failures.append("double_completion")
        return
    seq.terminal = outcome


def _emit_horizon(state: ModelState, sid: int | None, failures: list) -> None:
    if sid is None:
        return
    if sid in state.horizon_emitted:
        failures.append("duplicate_horizon")
        return
    if sid not in state.deferred:
        return
    state.deferred.discard(sid)
    state.horizon_emitted.add(sid)


def _restore_outer(state: ModelState, frame: Frame, *, lease: bool, failures: list) -> None:
    state.stack.pop()
    state.active = frame.outer
    if lease and state.frontier > 0:
        state.lease = 1
        state.commitment = 1
        state.returning = False
    else:
        state.lease = 0
        state.commitment = 0
        state.returning = True
        _emit_horizon(state, frame.outer, failures)


def apply_token(state: ModelState, token: str):
    """Return (state, status, failures). Impossible leaves the prior state."""
    if token not in ALPHABET:
        return state, "impossible", []
    nxt = _copy(state)
    failures: list = []
    active = state.active
    dead = _dead(state, active)
    depth_before = len(state.stack)
    returned_before = sum(1 for seq in state.seqs.values() if seq.terminal == "returned")

    if token in ("P", "V"):
        if dead or state.returning or state.commitment < 2 or state.lease:
            return state, "impossible", []
        _mark(nxt, active, "returned", failures)
        frame = nxt.stack[-1] if nxt.stack else None
        if frame is not None and frame.child == active:
            _restore_outer(nxt, frame, lease=nxt.frontier > 0, failures=failures)
        else:
            nxt.active = None
            nxt.commitment = 0
            nxt.returning = False
            nxt.lease = 0
    elif token == "H":
        if dead or state.returning or state.commitment != 1 or state.lease:
            return state, "impossible", []
        if active in nxt.horizon_emitted and active in nxt.deferred:
            return state, "impossible", []
        child = nxt.next_id
        nxt.next_id += 1
        nxt.seqs[child] = Seq(child)
        nxt.stack.append(Frame(active, child))
        nxt.deferred.add(active)
        nxt.active = child
        nxt.commitment = 2
        nxt.returning = False
        nxt.lease = 0
    elif token == "W":
        if (not state.stack or dead or state.stack[-1].child != active
                or state.frontier > 0 or state.lease):
            return state, "impossible", []
        frame = state.stack[-1]
        _mark(nxt, active, "returned", failures)
        _restore_outer(nxt, frame, lease=False, failures=failures)
    elif token == "L":
        if (not state.stack or dead or state.stack[-1].child != active
                or state.frontier <= 0 or state.lease):
            return state, "impossible", []
        frame = state.stack[-1]
        _mark(nxt, active, "returned", failures)
        _restore_outer(nxt, frame, lease=True, failures=failures)
    elif token == "A":
        if state.lease != 1 or state.frontier <= 0 or dead or state.returning:
            return state, "impossible", []
        if nxt.leased_keys >= 1 and state.frontier <= 0:
            failures.append("repeated_key")
        nxt.leased_keys += 1
        nxt.frontier -= 1
        nxt.lease = 0
        child = nxt.next_id
        nxt.next_id += 1
        nxt.seqs[child] = Seq(child)
        nxt.stack.append(Frame(active, child))
        nxt.deferred.add(active)
        nxt.active = child
        nxt.commitment = 2
        nxt.returning = False
    elif token == "X":
        if not state.stack:
            return state, "impossible", []
        if not dead and active is not None:
            _mark(nxt, active, "abandoned", failures)
        for frame in list(nxt.stack):
            outer = nxt.seqs.get(frame.outer)
            if outer is not None and not outer.terminal:
                _mark(nxt, frame.outer, "abandoned", failures)
            elif outer is not None and outer.terminal == "returned":
                failures.append("escape_false_return")
        nxt.stack.clear()
        nxt.lease = 0
        nxt.commitment = 0
        nxt.returning = False
        nxt.active = None
        nxt.deferred.clear()
    elif token == "N":
        if dead or state.lease:
            return state, "impossible", []
        if state.returning:
            pass
        elif state.commitment > 1:
            nxt.commitment -= 1
        elif state.commitment == 1:
            nxt.commitment = 0
            nxt.returning = True
        else:
            return state, "impossible", []
    else:
        return state, "impossible", []

    if len(nxt.stack) < 0:
        failures.append("negative_stack")
    if nxt.lease not in (0, 1):
        failures.append("lease_slot")
    if nxt.frontier < 0:
        failures.append("negative_frontier")
    if token in ("P", "V"):
        returned_after = sum(1 for seq in nxt.seqs.values() if seq.terminal == "returned")
        if returned_after != returned_before + 1:
            failures.append("reentry_close_count")
        if state.stack and len(nxt.stack) != depth_before - 1:
            failures.append("reentry_witness")
        if not state.stack and nxt.active is not None:
            failures.append("sibling_still_active")
    if token == "H" and len(nxt.stack) != depth_before + 1:
        failures.append("handoff_depth")
    if token == "L":
        if nxt.lease != 1 or nxt.commitment != 1 or nxt.returning:
            failures.append("lease_grant")
        if len(nxt.stack) != depth_before - 1:
            failures.append("witness_depth")
        if state.active in nxt.horizon_emitted and state.active not in state.horizon_emitted:
            failures.append("lease_emitted_horizon")
    if token == "W":
        if not nxt.returning or nxt.commitment != 0 or nxt.lease != 0:
            failures.append("empty_witness_return")
        if len(nxt.stack) != depth_before - 1:
            failures.append("witness_depth")
    if token == "A":
        if nxt.frontier != state.frontier - 1 or nxt.lease != 0:
            failures.append("lease_consume")
        if len(nxt.stack) != depth_before + 1:
            failures.append("lease_handoff_depth")
        if nxt.leased_keys != state.leased_keys + 1:
            failures.append("repeated_key")
    if token == "X":
        if nxt.stack or nxt.lease:
            failures.append("escape_unwind")
        returned_after = sum(1 for seq in nxt.seqs.values() if seq.terminal == "returned")
        if returned_after != returned_before:
            failures.append("escape_false_return")
    if token == "N" and len(nxt.stack) != depth_before:
        failures.append("ordinary_depth")
    if token == "H" and depth_before + 1 != len(nxt.stack):
        failures.append("resume_without_witness")
    return nxt, "ok", failures


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
        f"invariant_failures {report['invariant_failures']}"
    )
    for failure in report["failures"]:
        print(failure)
    ok = (
        report["invariant_failures"] == 0
        and report["raw_traces"] == RAW_TRACE_COUNT
    )
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
