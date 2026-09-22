"""L1/L2 escape lifecycle against committed v0.3.10 evidence. No new targets."""
from benchmark.fresh_transfer_analysis import (
    GUARD, PRIMARY_BUDGET, PUBLISHED_ROOT, load_cell_files,
)
from benchmark.return_cycle_accounting import (
    L1, L2, UNCLASSIFIED, classify_escape_lifecycle, lifecycle_counts,
)


def test_v0310_seven_escapes_are_six_l1_and_one_l2():
    _events, _graph, seq = load_cell_files(PUBLISHED_ROOT, GUARD, PRIMARY_BUDGET)
    rec = classify_escape_lifecycle(seq)
    assert rec["escape_count"] == 7
    assert rec["L1"] == 6
    assert rec["L2"] == 1
    assert rec["unclassified"] == 0
    assert rec["return_cycle_abandoned_terminals"] == 6
    assert rec["ok"] is True
    assert rec["return_inflation_events"] == []
    classes = [r["class"] for r in rec["escapes"]]
    assert classes.count(L1) == 6
    assert classes.count(L2) == 1
    assert UNCLASSIFIED not in classes
    l2 = next(r for r in rec["escapes"] if r["class"] == L2)
    assert l2["sequence_instance_id"] is None
    assert l2["abandoned_terminal"] is False
    assert l2["prior_terminal_outcome"] == "finding"
    for r in rec["escapes"]:
        if r["class"] == L1:
            assert r["sequence_instance_id"]
            assert r["abandoned_terminal"] is True
            assert r["returned_terminal"] is False


def test_lifecycle_counts_helper():
    _events, _graph, seq = load_cell_files(PUBLISHED_ROOT, GUARD, PRIMARY_BUDGET)
    c = lifecycle_counts(seq)
    assert c == {
        "escapes": 7,
        "L1_open_instance": 6,
        "L2_already_terminal": 1,
        "unclassified": 0,
        "abandoned_terminals": 6,
        "return_inflation": 0,
        "ok": True,
    }


def test_l1_synthetic_open_instance():
    seq = [
        {"step": 0, "event": "branch_start", "branch_key": "p:click:a",
         "sequence_instance_id": "seq-0001", "exact_sig": "P"},
        {"step": 3, "event": "sequence_horizon_reached", "branch_key": "p:click:a",
         "sequence_instance_id": "seq-0001"},
        {"step": 5, "event": "return_cycle_escape", "branch_key": "p:click:a",
         "active_branch": "p:click:a", "sequence_instance_id": "seq-0001",
         "repeated_destination_sig": "A", "parent_hub_sig": "P"},
        {"step": 5, "event": "sequence_terminal", "outcome": "return_cycle_abandoned",
         "branch_key": "p:click:a", "sequence_instance_id": "seq-0001"},
    ]
    rec = classify_escape_lifecycle(seq)
    assert rec["L1"] == 1 and rec["L2"] == 0 and rec["ok"]


def test_l2_synthetic_finding_then_escape():
    seq = [
        {"step": 0, "event": "branch_start", "branch_key": "p:click:a",
         "sequence_instance_id": "seq-0001", "exact_sig": "P"},
        {"step": 4, "event": "sequence_terminal", "outcome": "finding",
         "branch_key": "p:click:a", "sequence_instance_id": "seq-0001"},
        {"step": 7, "event": "return_cycle_escape", "branch_key": "p:click:a",
         "active_branch": "p:click:a", "sequence_instance_id": None,
         "repeated_destination_sig": "A", "parent_hub_sig": "P"},
    ]
    rec = classify_escape_lifecycle(seq)
    assert rec["L1"] == 0 and rec["L2"] == 1 and rec["unclassified"] == 0
    assert rec["escapes"][0]["prior_terminal_outcome"] == "finding"


def test_second_terminal_on_l2_is_unclassified():
    seq = [
        {"step": 0, "event": "branch_start", "branch_key": "p:click:a",
         "sequence_instance_id": "seq-0001"},
        {"step": 4, "event": "sequence_terminal", "outcome": "finding",
         "branch_key": "p:click:a", "sequence_instance_id": "seq-0001"},
        {"step": 7, "event": "return_cycle_escape", "branch_key": "p:click:a",
         "active_branch": "p:click:a", "sequence_instance_id": None,
         "repeated_destination_sig": "A", "parent_hub_sig": "P"},
        {"step": 7, "event": "sequence_terminal", "outcome": "return_cycle_abandoned",
         "branch_key": "p:click:a", "sequence_instance_id": None},
    ]
    rec = classify_escape_lifecycle(seq)
    assert rec["unclassified"] == 1
    assert rec["ok"] is False
