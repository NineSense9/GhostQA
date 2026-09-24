"""Bounded residual-debt model and synthetic outcome order."""
from benchmark.residual_frontier_debt_analysis import (
    derive_v0323_outcome, passing_facts,
)
from benchmark.residual_frontier_debt_modelcheck import (
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


def test_debt_model_covers_every_short_trace_without_invariant_failures():
    report = enumerate_traces()
    assert RAW_TRACE_COUNT == 66429
    assert report["raw_traces"] == 66429
    assert report["valid_traces"] + report["rejected_traces"] == 66429
    assert report["invariant_failures"] == 0
    assert report["failures"] == []
    assert report["valid_traces"] > 0
    assert report["rejected_traces"] > 0


def test_relocation_requires_debt_closed_scc_and_a_normal_release():
    state, statuses = _run("DCRPNX")
    assert statuses == ["ok"] * 6
    assert state.consumed == 1
    assert state.remaining == 1
    assert state.unresolved == 1
    assert state.resolved == 0
    assert state.return_success == 0
    assert state.replay_terminals == 0

    state, statuses = _run("CR")
    assert statuses[-1] == "impossible"
    assert state.relocations == 0

    state, statuses = _run("DOR")
    assert statuses[-1] == "impossible"
    assert state.relocations == 0

    state, statuses = _run("DACR")
    assert statuses[-1] == "impossible"
    assert state.active is True
    assert state.relocations == 0

    state, statuses = _run("DCRPR")
    assert statuses[-1] == "impossible"
    assert state.relocations == 1
    assert state.burst == 1
    assert state.consumed == 0

    state, statuses = _run("DCRF")
    assert state.failures == 1
    assert state.resolved == 0
    assert state.remaining == 2
    assert state.consumed == 0

    state, statuses = _run("DCRP")
    assert state.arrived is True
    assert state.resolved == 0
    assert state.remaining == 2

    state, statuses = _run("DX")
    assert statuses[-1] == "impossible"
    assert state.consumed == 0

    state, statuses = _run("DCRPNXNX")
    assert state.remaining == 0
    assert state.unresolved == 0
    assert state.resolved == 1
    assert state.return_success == 0


def test_outcome_order_is_c_then_d_then_b_then_a():
    assert derive_v0323_outcome()["outcome"] == "A"
    muted = passing_facts()
    muted["campus_engaged"] = False
    muted["studio_engaged"] = False
    muted["campus_mechanism"] = False
    muted["studio_mechanism"] = False
    muted["campus_589"] = False
    muted["studio_589"] = False
    assert derive_v0323_outcome(**muted)["outcome"] == "D"

    partial = passing_facts()
    partial["studio_mechanism"] = False
    partial["studio_589"] = False
    partial["studio_engaged"] = True
    assert derive_v0323_outcome(**partial)["outcome"] == "B"

    harmful = passing_facts()
    harmful["guard_bug_loss"] = ["BUG-L1"]
    assert derive_v0323_outcome(**harmful)["outcome"] == "C"
    assert derive_v0323_outcome(catalog_relocations=1)["outcome"] == "C"
    assert derive_v0323_outcome(relocation_open_scc_violations=1)["outcome"] == "C"
    assert derive_v0323_outcome(relocation_pending_scc_violations=1)["outcome"] == "C"
    assert derive_v0323_outcome(model_raw_traces=1)["outcome"] == "C"
    assert derive_v0323_outcome(product_default_changed=True)["outcome"] == "C"
    assert derive_v0323_outcome(arrival_clears_debt=1)["outcome"] == "C"
    assert derive_v0323_outcome(zero_normal_loop_violations=1)["outcome"] == "C"
    assert derive_v0323_outcome(warehouse_harmful_relocation=True)["outcome"] == "C"
