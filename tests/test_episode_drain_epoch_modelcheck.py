"""Bounded episode model and the historical model chain."""
from benchmark.episode_drain_epoch_modelcheck import (
    RAW_TRACE_COUNT, apply_token, enumerate_traces, initial_state,
)
from benchmark.finding_return_entry_modelcheck import enumerate_traces as finding_enum
from benchmark.finding_return_entry_modelcheck import RAW_TRACE_COUNT as FINDING_RAW
from benchmark.horizon_handoff_modelcheck import enumerate_traces as handoff_enum
from benchmark.horizon_handoff_modelcheck import RAW_TRACE_COUNT as HANDOFF_RAW
from benchmark.local_action_drain_modelcheck import enumerate_traces as local_enum
from benchmark.local_action_drain_modelcheck import RAW_TRACE_COUNT as LOCAL_RAW
from benchmark.reentry_frontier_modelcheck import enumerate_traces as reentry_enum
from benchmark.reentry_frontier_modelcheck import RAW_TRACE_COUNT as REENTRY_RAW
from benchmark.residual_frontier_debt_modelcheck import enumerate_traces as debt_enum
from benchmark.residual_frontier_debt_modelcheck import RAW_TRACE_COUNT as DEBT_RAW
from benchmark.return_cycle_modelcheck import run_exhaustive_check
from benchmark.return_entry_drain_modelcheck import enumerate_traces as entry_enum
from benchmark.return_entry_drain_modelcheck import RAW_TRACE_COUNT as ENTRY_RAW
from benchmark.return_waypoint_frontier_modelcheck import enumerate_traces as waypoint_enum
from benchmark.return_waypoint_frontier_modelcheck import RAW_TRACE_COUNT as WAYPOINT_RAW


def _run(tokens: str):
    state = initial_state()
    statuses = []
    for token in tokens:
        state, status, failures = apply_token(state, token)
        statuses.append(status)
        assert failures == [], (tokens, token, failures)
        if status == "impossible":
            break
    return state, statuses


def test_episode_model_covers_66429_traces_without_invariant_failures():
    report = enumerate_traces()
    assert RAW_TRACE_COUNT == 66429
    assert report["raw_traces"] == 66429
    assert report["valid_traces"] + report["rejected_traces"] == 66429
    assert report["invariant_failures"] == 0
    assert report["failures"] == []


def test_relocation_invalidates_same_hub_keys_and_keeps_cross_hub_keys():
    state, statuses = _run("SPR")
    assert statuses == ["possible", "possible", "possible"]
    assert state.episode == 1
    assert state.current_same == 0
    assert state.invalidated_same == 1
    assert state.cross == 1
    assert state.replaying is True
    assert state.return_success == 0


def test_restore_cannot_revalidate_and_witness_can():
    blocked, blocked_status = _run("SRXQ")
    assert blocked_status[-1] == "impossible"
    assert blocked.episode == 1
    state, statuses = _run("SRXWQ")
    assert statuses == ["possible"] * 5
    assert state.episode == 1
    assert state.current_same == 1
    assert state.invalidated_same == 0
    assert state.replaying is False


def test_duplicate_failure_and_reset():
    state, statuses = _run("SD")
    assert statuses == ["possible", "possible"]
    assert state.current_same == 1
    failed, failed_status = _run("SRXF")
    assert failed_status[-1] == "possible"
    assert failed.return_success == 0
    assert failed.fake_success == 0
    assert failed.episode == 1
    assert failed.replaying is False
    cleared, cleared_status = _run("SPN")
    assert cleared_status[-1] == "possible"
    assert cleared.episode == 0
    assert cleared.cross == 0
    assert cleared.current_same == 0


def test_historical_model_chain_is_green():
    expectations = (
        (run_exhaustive_check(), 5800, "failures"),
        (handoff_enum(), HANDOFF_RAW, "invariant_failures"),
        (reentry_enum(), REENTRY_RAW, "invariant_failures"),
        (local_enum(), LOCAL_RAW, "invariant_failures"),
        (entry_enum(), ENTRY_RAW, "invariant_failures"),
        (finding_enum(), FINDING_RAW, "invariant_failures"),
        (waypoint_enum(), WAYPOINT_RAW, "invariant_failures"),
        (debt_enum(), DEBT_RAW, "invariant_failures"),
    )
    assert HANDOFF_RAW == 19607
    assert REENTRY_RAW == 37448
    assert LOCAL_RAW == 66429
    assert ENTRY_RAW == 66429
    assert FINDING_RAW == 66429
    assert WAYPOINT_RAW == 37448
    assert DEBT_RAW == 66429
    returned = expectations[0][0]
    assert returned["traces_enumerated"] >= 5800
    assert returned["failures"] == 0
    for report, raw, key in expectations[1:]:
        assert report["raw_traces"] == raw
        assert report[key] == 0
        assert report["failures"] == []
