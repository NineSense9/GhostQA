"""Bounded lifecycle model for v0.3.19 finding-gated return entry."""
from benchmark.finding_return_entry_modelcheck import (
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


def test_finding_trigger_model_covers_every_short_trace_without_invariant_failures():
    report = enumerate_traces()
    assert RAW_TRACE_COUNT == 66429
    assert report["raw_traces"] == 66429
    assert report["valid_traces"] + report["rejected_traces"] == 66429
    assert report["invariant_failures"] == 0
    assert report["failures"] == []
    assert report["valid_traces"] > 0
    assert report["rejected_traces"] > 0


def test_only_finding_entry_activates_drain_and_horizon_does_not():
    state, statuses = _run("F")
    assert statuses == ["ok"]
    assert state.phase == "drain"
    assert state.drain_started == 1
    assert state.triggers == 1
    assert state.attempts == 0

    state, statuses = _run("H")
    assert statuses == ["ok"]
    assert state.phase == "historical"
    assert state.drain_started == 0
    assert state.triggers == 0
    assert state.obligation is True

    state, statuses = _run("HF")
    assert statuses == ["ok", "impossible"]
    assert state.drain_started == 0

    state, statuses = _run("HB")
    assert statuses == ["ok", "impossible"]

    state, statuses = _run("HRP")
    assert statuses == ["ok", "ok", "ok"]
    assert state.phase == "done"
    assert state.success == 1
    assert state.drain_started == 0

    state, statuses = _run("FBXRP")
    assert statuses == ["ok", "ok", "ok", "ok", "ok"]
    assert state.phase == "done"
    assert state.attempts == 1
    assert state.terminals == 0

    state, statuses = _run("FL")
    assert statuses == ["ok", "ok"]
    assert state.phase == "left"
    assert state.obligation is True
    assert state.success == 0

    state, statuses = _run("B")
    assert statuses == ["impossible"]

    state, statuses = _run("FF")
    assert statuses == ["ok", "impossible"]
    assert state.reused == 0
