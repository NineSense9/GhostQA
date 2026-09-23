"""Pure lifecycle model of local action drain before the structural frontier.

Enumerates every token string of length 1..5 over
S, B, R, J, W, E, X, H, F. Impossible transitions are rejected without
changing state. Possible transitions must keep the lifecycle invariants.
This checker does not read application traces and does not choose actions.
"""
from __future__ import annotations

import itertools
from dataclasses import dataclass, field

ALPHABET = ("S", "B", "R", "J", "W", "E", "X", "H", "F")
RAW_TRACE_COUNT = sum(len(ALPHABET) ** length for length in range(1, 6))


@dataclass
class ModelState:
    phase: str = "pre"
    buttons: int = 0
    revealed: bool = False
    structural: int = 1
    drained: int = 0
    outer: str = ""
    child: str = ""
    stack: int = 0
    probe_sequences: int = 0
    finding_terminals: int = 0
    clicks: int = 0
    accounted: int = 0


def initial_state() -> ModelState:
    """Before any child witness. One structural key is known. No drain yet."""
    return ModelState()


def _copy(state: ModelState) -> ModelState:
    return ModelState(
        phase=state.phase,
        buttons=state.buttons,
        revealed=state.revealed,
        structural=state.structural,
        drained=state.drained,
        outer=state.outer,
        child=state.child,
        stack=state.stack,
        probe_sequences=state.probe_sequences,
        finding_terminals=state.finding_terminals,
        clicks=state.clicks,
        accounted=state.accounted,
    )


def _invariants(state: ModelState, token: str) -> list:
    failures = []
    if state.stack < 0:
        failures.append("negative_stack")
    if state.buttons < 0 or state.drained < 0 or state.structural < 0:
        failures.append("negative_count")
    if state.probe_sequences != 0:
        failures.append("same_hub_started_sequence")
    if state.finding_terminals != 0:
        failures.append("finding_terminal")
    if state.clicks != state.accounted:
        failures.append("double_browser_action")
    if state.phase == "drain" and state.outer != "suspended":
        failures.append("drain_without_witness")
    if state.phase == "struct" and (state.buttons != 0 or state.outer != "suspended"):
        failures.append("structural_before_exhaustion")
    if state.phase == "child" and state.child != "open":
        failures.append("resume_without_witness")
    if token == "W" and state.phase != "drain":
        failures.append("resume_without_witness")
    if token == "E" and (state.phase != "dead" or state.outer != "abandoned" or state.stack != 0):
        failures.append("escape_unwind")
    if token == "F" and state.outer != "suspended":
        failures.append("finding_terminal")
    if token in ("B", "F") and state.phase == "drain" and state.probe_sequences != 0:
        failures.append("same_hub_started_sequence")
    if state.outer not in ("", "suspended", "returned", "abandoned"):
        failures.append("terminal_conservation")
    return failures


def apply_token(state: ModelState, token: str):
    """Return (state, status, failures). Impossible leaves the prior state."""
    if token not in ALPHABET:
        return state, "impossible", []
    if state.phase == "dead":
        return state, "impossible", []
    nxt = _copy(state)
    if token == "S":
        if state.phase != "pre" or state.outer:
            return state, "impossible", []
        nxt.phase = "drain"
        nxt.buttons = 1
        nxt.outer = "suspended"
        nxt.structural = 1
    elif token == "B":
        if state.phase != "drain" or state.buttons < 1:
            return state, "impossible", []
        nxt.buttons -= 1
        nxt.drained += 1
        nxt.clicks += 1
        nxt.accounted += 1
    elif token == "R":
        if state.phase != "drain" or state.revealed:
            return state, "impossible", []
        nxt.revealed = True
        nxt.buttons += 1
    elif token == "J":
        if state.phase != "drain" or state.buttons < 1:
            return state, "impossible", []
        nxt.buttons -= 1
        nxt.phase = "child"
        nxt.child = "open"
        nxt.clicks += 1
        nxt.accounted += 1
    elif token == "W":
        if state.phase != "child" or state.child != "open":
            return state, "impossible", []
        nxt.child = "returned"
        nxt.phase = "drain"
        nxt.drained += 1
    elif token == "E":
        if state.phase != "child" or state.child != "open":
            return state, "impossible", []
        nxt.child = "abandoned"
        nxt.outer = "abandoned"
        nxt.phase = "dead"
        nxt.stack = 0
    elif token == "X":
        if state.phase != "drain" or state.buttons != 0:
            return state, "impossible", []
        if state.structural > 0:
            nxt.phase = "struct"
        else:
            nxt.phase = "dead"
            nxt.outer = "returned"
    elif token == "H":
        if state.phase != "struct" or state.structural < 1 or state.buttons != 0:
            return state, "impossible", []
        nxt.structural -= 1
        nxt.stack += 1
        nxt.phase = "dead"
        nxt.clicks += 1
        nxt.accounted += 1
    elif token == "F":
        if state.phase != "drain" or state.buttons < 1:
            return state, "impossible", []
        nxt.buttons -= 1
        nxt.drained += 1
        nxt.clicks += 1
        nxt.accounted += 1
    else:
        return state, "impossible", []
    return nxt, "ok", _invariants(nxt, token)


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
