"""Bounded lifecycle model for v0.3.18 return-phase entry drain."""
from benchmark.return_entry_drain_modelcheck import (
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


def test_return_entry_model_covers_every_short_trace_without_invariant_failures():
    report = enumerate_traces()
    assert RAW_TRACE_COUNT == 66429
    assert report["raw_traces"] == 66429
    assert report["valid_traces"] + report["rejected_traces"] == 66429
    assert report["invariant_failures"] == 0
    assert report["failures"] == []
    assert report["valid_traces"] > 0
    assert report["rejected_traces"] > 0


def test_representative_return_entry_traces():
    state, statuses = _run("T")
    assert statuses == ["ok"]
    assert state.phase == "drain"
    assert state.obligation is True
    assert state.attempts == 0

    state, statuses = _run("TT")
    assert statuses == ["ok", "impossible"]

    state, statuses = _run("B")
    assert statuses == ["impossible"]

    state, statuses = _run("TBXRP")
    assert statuses == ["ok", "ok", "ok", "ok", "ok"]
    assert state.phase == "done"
    assert state.success == 1
    assert state.terminals == 0

    state, statuses = _run("TL")
    assert statuses == ["ok", "ok"]
    assert state.phase == "left"
    assert state.success == 0
    assert state.obligation is True

    state, statuses = _run("TBE")
    assert statuses == ["ok", "ok", "impossible"]

    state, statuses = _run("TF")
    assert statuses == ["ok", "ok"]
    assert state.terminals == 0
    assert state.attempts == 0
