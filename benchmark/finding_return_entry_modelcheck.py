"""Pure lifecycle model of finding-gated return-entry drain.

Enumerates every token string of length 1..5 over
F, H, B, N, L, X, R, P, E. Impossible transitions are rejected without
changing state. Possible transitions must keep the lifecycle invariants.
This checker does not read application traces and does not choose actions.
"""
from __future__ import annotations

import itertools
from dataclasses import dataclass

ALPHABET = ("F", "H", "B", "N", "L", "X", "R", "P", "E")
RAW_TRACE_COUNT = sum(len(ALPHABET) ** length for length in range(1, 6))
_RETURN_PHASES = ("ready", "left", "historical")


@dataclass
class ModelState:
    phase: str = "idle"
    buttons: int = 1
    revealed: bool = False
    drained: int = 0
    attempts: int = 0
    history: int = 0
    terminals: int = 0
    success: int = 0
    obligation: bool = False
    clicks: int = 0
    accounted: int = 0
    contamination: int = 0
    drain_started: int = 0
    triggers: int = 0
    reused: int = 0
    parent_corruption: int = 0
    entry: str = ""


def initial_state() -> ModelState:
    """Before a false-to-true boundary. One button is visible if F fires."""
    return ModelState()


def _copy(state: ModelState) -> ModelState:
    return ModelState(
        phase=state.phase,
        buttons=state.buttons,
        revealed=state.revealed,
        drained=state.drained,
        attempts=state.attempts,
        history=state.history,
        terminals=state.terminals,
        success=state.success,
        obligation=state.obligation,
        clicks=state.clicks,
        accounted=state.accounted,
        contamination=state.contamination,
        drain_started=state.drain_started,
        triggers=state.triggers,
        reused=state.reused,
        parent_corruption=state.parent_corruption,
        entry=state.entry,
    )


def _invariants(state: ModelState) -> list:
    failures = []
    if state.buttons < 0 or state.drained < 0 or state.attempts < 0 or state.history < 0:
        failures.append("negative_count")
    if state.terminals != 0:
        failures.append("duplicate_terminal")
    if state.contamination != 0:
        failures.append("return_cycle_contamination")
    if state.clicks != state.accounted:
        failures.append("double_browser_action")
    if state.attempts != state.history:
        failures.append("attempt_history_split")
    if state.success not in (0, 1):
        failures.append("false_return_success")
    if state.reused != 0:
        failures.append("reused_trigger")
    if state.parent_corruption != 0:
        failures.append("parent_corruption")
    if state.drain_started != state.triggers or state.drain_started not in (0, 1):
        failures.append("trigger_provenance")
    if state.entry == "H" and state.drain_started != 0:
        failures.append("horizon_activated_drain")
    if state.entry == "F" and state.drain_started != 1:
        failures.append("finding_without_drain")
    if state.phase == "drain" and (
        state.entry != "F" or state.attempts or state.history or state.success
        or not state.obligation or state.triggers != 1
    ):
        failures.append("probe_mutated_obligation")
    if state.phase == "left" and (
        state.entry != "F" or state.success or not state.obligation
    ):
        failures.append("cross_hub_claimed_return")
    if state.phase == "ready" and (
        state.entry != "F" or state.success or not state.obligation
    ):
        failures.append("exhaustion_cleared_obligation")
    if state.phase == "historical" and (
        state.entry != "H" or state.success or not state.obligation or state.drain_started
    ):
        failures.append("horizon_left_historical_return")
    if state.phase == "done" and (state.success != 1 or state.obligation):
        failures.append("parent_completion")
    if state.phase == "dead" and (state.success != 0 or state.obligation):
        failures.append("escape_completed")
    if state.phase == "idle" and (
        state.obligation or state.success or state.attempts or state.drain_started
    ):
        failures.append("early_obligation")
    return failures


def apply_token(state: ModelState, token: str):
    """Return (state, status, failures). Impossible leaves the prior state."""
    if token not in ALPHABET or state.phase in ("done", "dead"):
        return state, "impossible", []
    nxt = _copy(state)
    if token == "F":
        if state.phase != "idle" or state.obligation or state.buttons < 1 or state.entry:
            return state, "impossible", []
        nxt.phase = "drain"
        nxt.obligation = True
        nxt.drain_started = 1
        nxt.triggers = 1
        nxt.entry = "F"
    elif token == "H":
        if state.phase != "idle" or state.obligation or state.entry:
            return state, "impossible", []
        nxt.phase = "historical"
        nxt.obligation = True
        nxt.entry = "H"
    elif token == "B":
        if state.phase != "drain" or state.entry != "F" or state.buttons < 1:
            return state, "impossible", []
        nxt.buttons -= 1
        nxt.drained += 1
        nxt.clicks += 1
        nxt.accounted += 1
    elif token == "N":
        if state.phase != "drain" or state.entry != "F" or state.revealed:
            return state, "impossible", []
        nxt.revealed = True
        nxt.buttons += 1
    elif token == "L":
        if state.phase != "drain" or state.entry != "F" or state.buttons < 1:
            return state, "impossible", []
        nxt.buttons -= 1
        nxt.drained += 1
        nxt.clicks += 1
        nxt.accounted += 1
        nxt.phase = "left"
        nxt.obligation = True
    elif token == "X":
        if state.phase != "drain" or state.entry != "F" or state.buttons != 0:
            return state, "impossible", []
        nxt.phase = "ready"
        nxt.obligation = True
    elif token == "R":
        if state.phase not in _RETURN_PHASES:
            return state, "impossible", []
        nxt.attempts += 1
        nxt.history += 1
    elif token == "P":
        if state.phase not in _RETURN_PHASES or state.attempts < 1 or state.success:
            return state, "impossible", []
        nxt.success = 1
        nxt.obligation = False
        nxt.phase = "done"
    elif token == "E":
        if state.phase not in _RETURN_PHASES or state.history < 1 or state.success:
            return state, "impossible", []
        nxt.obligation = False
        nxt.phase = "dead"
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
