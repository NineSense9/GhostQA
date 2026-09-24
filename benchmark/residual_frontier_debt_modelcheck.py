"""Pure residual-debt / SCC model.

Enumerates every token string of length 1..5 over D, C, O, A, R, P, N, X, F.
Impossible transitions are rejected without changing state. Possible
transitions must keep the debt invariants. This checker does not read
application traces and does not choose actions.
"""
from __future__ import annotations

import itertools
from dataclasses import dataclass

ALPHABET = ("D", "C", "O", "A", "R", "P", "N", "X", "F")
RAW_TRACE_COUNT = sum(len(ALPHABET) ** length for length in range(1, 6))


@dataclass
class ModelState:
    unresolved: int = 0
    remaining: int = 0
    created: int = 0
    consumed: int = 0
    resolved: int = 0
    scc: str = "none"
    active: bool = False
    target_outside: bool = False
    path_ok: bool = True
    replaying: bool = False
    burst: int = 0
    match_ready: bool = False
    arrived: bool = False
    return_success: int = 0
    replay_terminals: int = 0
    relocations: int = 0
    failures: int = 0


def initial_state() -> ModelState:
    return ModelState()


def _copy(state: ModelState) -> ModelState:
    return ModelState(
        unresolved=state.unresolved,
        remaining=state.remaining,
        created=state.created,
        consumed=state.consumed,
        resolved=state.resolved,
        scc=state.scc,
        active=state.active,
        target_outside=state.target_outside,
        path_ok=state.path_ok,
        replaying=state.replaying,
        burst=state.burst,
        match_ready=state.match_ready,
        arrived=state.arrived,
        return_success=state.return_success,
        replay_terminals=state.replay_terminals,
        relocations=state.relocations,
        failures=state.failures,
    )


def _invariants(state: ModelState) -> list:
    failures = []
    if min(
        state.unresolved, state.remaining, state.created, state.consumed,
        state.resolved, state.burst, state.relocations, state.failures,
        state.return_success, state.replay_terminals,
    ) < 0:
        failures.append("negative")
    if state.consumed + state.remaining != state.created:
        failures.append("token_conservation")
    if (state.unresolved == 0) != (state.remaining == 0):
        failures.append("resolve_mismatch")
    if state.resolved and (state.remaining != 0 or state.unresolved != 0):
        failures.append("resolved_with_remaining")
    if state.return_success != 0 or state.replay_terminals != 0:
        failures.append("false_return_success")
    if state.burst > 1:
        failures.append("zero_normal_loop")
    if state.replaying and state.burst < 1:
        failures.append("replay_without_relocation")
    if state.relocations < state.failures:
        failures.append("failure_without_relocation")
    return failures


def apply_token(state: ModelState, token: str):
    """Return (state, status, failures). Impossible leaves the prior state."""
    if token not in ALPHABET:
        return state, "impossible", []
    if state.replaying and token not in ("P", "F"):
        return state, "impossible", []
    nxt = _copy(state)
    nxt.match_ready = False
    if token == "D":
        if state.unresolved or state.replaying:
            return state, "impossible", []
        nxt.unresolved = 1
        nxt.remaining = 2
        nxt.created = 2
        nxt.consumed = 0
        nxt.resolved = 0
        nxt.active = False
        nxt.arrived = False
    elif token == "C":
        if state.replaying:
            return state, "impossible", []
        nxt.scc = "closed"
        nxt.target_outside = True
        nxt.path_ok = True
    elif token == "O":
        if state.replaying:
            return state, "impossible", []
        nxt.scc = "open"
        nxt.target_outside = False
        nxt.path_ok = True
    elif token == "A":
        if state.replaying:
            return state, "impossible", []
        nxt.active = True
    elif token == "R":
        if not (
            state.unresolved > 0
            and state.remaining > 0
            and state.scc == "closed"
            and not state.active
            and state.scc != "open"
            and state.target_outside
            and state.path_ok
            and state.burst == 0
            and not state.replaying
        ):
            return state, "impossible", []
        nxt.replaying = True
        nxt.burst = 1
        nxt.relocations += 1
        nxt.arrived = False
    elif token == "P":
        if not state.replaying:
            return state, "impossible", []
        nxt.replaying = False
        nxt.arrived = True
        nxt.scc = "none"
        nxt.target_outside = False
        nxt.burst = state.burst
    elif token == "N":
        if state.replaying:
            return state, "impossible", []
        nxt.burst = 0
        nxt.match_ready = state.remaining > 0 and state.unresolved > 0
    elif token == "X":
        if (
            state.replaying or not state.match_ready or state.remaining <= 0
            or state.unresolved <= 0
        ):
            return state, "impossible", []
        nxt.remaining -= 1
        nxt.consumed += 1
        nxt.match_ready = False
        if nxt.remaining == 0:
            nxt.unresolved = 0
            nxt.resolved = 1
    elif token == "F":
        if not state.replaying:
            return state, "impossible", []
        nxt.replaying = False
        nxt.arrived = False
        nxt.scc = "none"
        nxt.target_outside = False
        nxt.path_ok = False
        nxt.failures += 1
        nxt.burst = state.burst
    else:
        return state, "impossible", []
    failures = _invariants(nxt)
    if token == "P" and (
        nxt.consumed != state.consumed
        or nxt.resolved != state.resolved
        or nxt.remaining != state.remaining
        or nxt.return_success != 0
        or nxt.replay_terminals != 0
    ):
        failures.append("replay_consumed_or_success")
    if token == "F" and (
        nxt.resolved != state.resolved or nxt.remaining != state.remaining
        or nxt.consumed != state.consumed
    ):
        failures.append("failure_resolved")
    if token == "R" and (
        state.unresolved <= 0 or state.scc != "closed" or state.active
        or not state.target_outside or not state.path_ok or state.burst != 0
    ):
        failures.append("illegal_relocation")
    if token == "X" and state.consumed + 1 != nxt.consumed:
        failures.append("consume_without_match")
    if nxt.resolved and nxt.remaining != 0:
        failures.append("resolve_before_zero")
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
        f"failures {report['invariant_failures']}")
    if report["failures"]:
        print(report["failures"][:5])
    return 0 if report["invariant_failures"] == 0 and report["raw_traces"] == RAW_TRACE_COUNT else 1


if __name__ == "__main__":
    raise SystemExit(main())
