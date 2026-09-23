"""Pure lifecycle model of return-phase entry drain.

Enumerates every token string of length 1..5 over
T, B, F, N, L, X, R, P, E. Impossible transitions are rejected without
changing state. Possible transitions must keep the lifecycle invariants.
This checker does not read application traces and does not choose actions.
"""
from __future__ import annotations

import itertools
from dataclasses import dataclass

ALPHABET = ("T", "B", "F", "N", "L", "X", "R", "P", "E")
RAW_TRACE_COUNT = sum(len(ALPHABET) ** length for length in range(1, 6))


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


def initial_state() -> ModelState:
    """Before the false-to-true boundary. One button is visible if T fires."""
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
    if state.phase == "drain" and (
        state.attempts or state.history or state.success or not state.obligation
    ):
        failures.append("probe_mutated_obligation")
    if state.phase == "left" and (state.success or not state.obligation):
        failures.append("cross_hub_claimed_return")
    if state.phase == "ready" and (state.success or not state.obligation):
        failures.append("exhaustion_cleared_obligation")
    if state.phase == "done" and (state.success != 1 or state.obligation):
        failures.append("parent_completion")
    if state.phase == "dead" and (state.success != 0 or state.obligation):
        failures.append("escape_completed")
    if state.phase == "idle" and (state.obligation or state.success or state.attempts):
        failures.append("early_obligation")
    return failures


def apply_token(state: ModelState, token: str):
    """Return (state, status, failures). Impossible leaves the prior state."""
    if token not in ALPHABET or state.phase in ("done", "dead"):
        return state, "impossible", []
    nxt = _copy(state)
    if token == "T":
        if state.phase != "idle" or state.obligation or state.buttons < 1:
            return state, "impossible", []
        nxt.phase = "drain"
        nxt.obligation = True
    elif token == "B":
        if state.phase != "drain" or state.buttons < 1:
            return state, "impossible", []
        nxt.buttons -= 1
        nxt.drained += 1
        nxt.clicks += 1
        nxt.accounted += 1
    elif token == "F":
        if state.phase != "drain" or state.buttons < 1:
            return state, "impossible", []
        nxt.buttons -= 1
        nxt.drained += 1
        nxt.clicks += 1
        nxt.accounted += 1
    elif token == "N":
        if state.phase != "drain" or state.revealed:
            return state, "impossible", []
        nxt.revealed = True
        nxt.buttons += 1
    elif token == "L":
        if state.phase != "drain" or state.buttons < 1:
            return state, "impossible", []
        nxt.buttons -= 1
        nxt.drained += 1
        nxt.clicks += 1
        nxt.accounted += 1
        nxt.phase = "left"
        nxt.obligation = True
    elif token == "X":
        if state.phase != "drain" or state.buttons != 0:
            return state, "impossible", []
        nxt.phase = "ready"
        nxt.obligation = True
    elif token == "R":
        if state.phase not in ("ready", "left"):
            return state, "impossible", []
        nxt.attempts += 1
        nxt.history += 1
    elif token == "P":
        if state.phase not in ("ready", "left") or state.attempts < 1 or state.success:
            return state, "impossible", []
        nxt.success = 1
        nxt.obligation = False
        nxt.phase = "done"
    elif token == "E":
        if state.phase not in ("ready", "left") or state.history < 1 or state.success:
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
