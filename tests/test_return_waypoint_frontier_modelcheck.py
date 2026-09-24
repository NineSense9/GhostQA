"""Bounded lifecycle model for v0.3.21 return-waypoint frontier escape."""
from benchmark.return_waypoint_frontier_modelcheck import (
    RAW_TRACE_COUNT, apply_token, enumerate_traces, initial_state,
)


def _run(tokens: str):
    state = initial_state()
    statuses = []
    for token in tokens:
        state, status, failures = apply_token(state, token)
        statuses.append(status)
        assert failures == []
        if status == "impossible":
            break
    return state, statuses


def test_waypoint_model_covers_every_short_trace_without_invariant_failures():
    report = enumerate_traces()
    assert RAW_TRACE_COUNT == 37448
    assert report["raw_traces"] == 37448
    assert report["valid_traces"] + report["rejected_traces"] == 37448
    assert report["invariant_failures"] == 0
    assert report["failures"] == []
    assert report["valid_traces"] > 0
    assert report["rejected_traces"] > 0


def test_escape_requires_resume_known_waypoint_and_frontier():
    state, statuses = _run("RTFE")
    assert statuses == ["ok", "ok", "ok", "ok"]
    assert state.phase == "escaped"
    assert state.success == 0
    assert state.returned == 0
    assert state.escapes == 1
    assert state.active_return is False
    assert state.ranked == 0
    assert state.suppressed is True

    state, statuses = _run("TFE")
    assert statuses[0] == "impossible"
    assert state.escapes == 0

    state, statuses = _run("RUFE")
    assert statuses[-1] == "impossible"
    assert state.escapes == 0
    assert state.place == "unknown"

    state, statuses = _run("RP")
    assert state.phase == "completed"
    assert state.success == 1
    assert state.escapes == 0

    state, statuses = _run("RTFPE")
    assert state.phase == "completed"
    assert state.escapes == 0

    state, statuses = _run("RTNE")
    assert statuses[-1] == "impossible"
    assert state.escapes == 0
    assert state.frontier is False

    state, statuses = _run("RTFCE")
    assert state.phase == "abandoned"
    assert state.terminals == 1
    assert state.escapes == 0

    state, statuses = _run("RTFEE")
    assert statuses[-1] == "impossible"
    assert state.escapes == 1
    assert state.terminals == 1
