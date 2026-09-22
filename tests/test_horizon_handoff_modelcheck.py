"""Bounded horizon-handoff model. Do not shrink the generator to hide failures."""
from benchmark.horizon_handoff_modelcheck import (
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


def test_raw_trace_count_and_invariants():
    report = enumerate_traces()
    assert RAW_TRACE_COUNT == 19607
    assert report["raw_traces"] == 19607
    assert report["valid_traces"] + report["rejected_traces"] == 19607
    assert report["invariant_failures"] == 0
    assert report["failures"] == []
    assert report["valid_traces"] > 0
    assert report["rejected_traces"] > 0


def test_representative_traces():
    state, statuses = _run("C")
    assert statuses == ["ok"]
    assert state.stack == []
    assert state.commitment == 1

    state, statuses = _run("H")
    assert statuses == ["impossible"]

    state, statuses = _run("CH")
    assert statuses == ["ok", "ok"]
    assert len(state.stack) == 1
    assert state.commitment == 2
    assert state.returning is False

    state, statuses = _run("CHP")
    assert statuses == ["ok", "ok", "ok"]
    assert state.stack == []
    assert state.returning is True
    assert state.commitment == 0
    assert sum(state.success.values()) == 1

    state, statuses = _run("CHX")
    assert len(state.stack) == 1
    assert sum(state.success.values()) == 0

    state, statuses = _run("CHF")
    assert len(state.stack) == 1
    assert state.returning is True
    assert sum(state.success.values()) == 0

    state, statuses = _run("CHCHP")
    assert len(state.stack) == 1
    assert state.returning is True
    assert sum(state.success.values()) == 1

    state, statuses = _run("CHFE")
    assert statuses == ["ok", "ok", "ok", "ok"]
    assert state.stack == []
    assert sum(state.success.values()) == 0
    assert state.active_alive is False
    stuck, statuses = _run("CHCHE")
    assert statuses[-1] == "impossible"
    assert len(stuck.stack) == 2


def test_two_level_lifo_witness_outside_the_length_cap():
    state = initial_state()
    for token in "CHCHPV":
        state, status, failures = apply_token(state, token)
        assert status == "ok"
        assert failures == []
    assert state.stack == []
    assert state.returning is True
    assert state.commitment == 0
    assert state.active_id == 1
    assert sum(state.success.values()) == 2
