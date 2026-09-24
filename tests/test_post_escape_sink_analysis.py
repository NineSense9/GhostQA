"""Preregistered v0.3.22 sink measurement tests. No browser."""
import json
import os

from benchmark.post_escape_sink_analysis import (
    CELLS,
    DIAGNOSTIC_BUDGETS,
    DOMINANCE_THRESHOLD,
    POSITIVE_TARGETS,
    analyze_cell,
    build_historical_audit,
    build_navigation_graph,
    build_protocol,
    build_static_report,
    cell_persistent,
    classify_static,
    derive_v0322_diagnosis,
    freeze_status,
    is_form_hub,
    load_bundle,
    tarjan_sccs,
)


def _edge(src, dst, action, parent_return=False):
    return {
        "src": src,
        "dst": dst,
        "action": action,
        "parent_return": parent_return,
        "navigates": not parent_return,
    }


def _node(node_id, page, entity=""):
    return {"id": node_id, "page": page, "entity": entity, "branch_actions": [], "eligible_buttons": []}


def test_closed_cycle_has_no_outgoing_edge():
    adjacency = {"a": ["b"], "b": ["a"], "c": ["a"]}
    components = tarjan_sccs(["a", "b", "c"], adjacency)
    by_member = {member: component for component in components for member in component}
    assert set(by_member["a"]) == {"a", "b"}
    assert by_member["c"] == ["c"]


def test_cycle_with_an_exit_is_not_closed():
    graph = build_navigation_graph({
        "nodes": [_node("a", "a.html"), _node("b", "b.html"), _node("c", "c.html")],
        "edges": [_edge("a", "b", "forward"), _edge("b", "a", "back"), _edge("a", "c", "leave")],
    })
    component = next(item for item in graph["components"] if "a" in item)
    number = graph["scc_of"]["a"]
    assert "b" in component
    assert graph["outgoing"][number]
    assert classify_static(1.0, len(graph["outgoing"][number]), False, True) == "policy_attractor_with_static_exit"
    assert classify_static(1.0, 0, False, True) == "closed_scc"
    assert classify_static(0.2, 0, False, True) == "no_dominant_scc"
    assert classify_static(1.0, 0, True, True) == "ambiguous"


def test_form_hub_is_structural_and_not_a_page_name():
    graph = build_navigation_graph({
        "nodes": [
            _node("loop", "loop.html"),
            _node("form", "form.html"),
            _node("entity", "detail.html", "e1"),
        ],
        "edges": [
            _edge("loop", "form", "open_form"),
            _edge("form", "loop", "open_loop"),
            _edge("form", "entity", "return_to_entity", parent_return=True),
        ],
    })
    assert is_form_hub("form", graph)
    assert not is_form_hub("loop", graph)
    assert not is_form_hub("entity", graph)
    assert "settings" not in "".join(graph["nodes"])


def test_exact_matrix_and_threshold_are_frozen():
    assert DOMINANCE_THRESHOLD == 0.60
    assert DIAGNOSTIC_BUDGETS == (240, 480)
    assert len(CELLS) == 8
    assert [budget for _app, budget in CELLS] == [240, 480] * 4
    assert tuple(dict.fromkeys(app for app, _budget in CELLS)) == POSITIVE_TARGETS
    status = freeze_status()
    assert status["ok"]
    assert status["product_default_changed"] is False


def _row(app, budget, **overrides):
    row = {
        "app": app,
        "budget": budget,
        "template_589_recovered": False,
        "productive_entity_reentry": False,
        "productive_reentry_step": None,
        "template_first_confirm_step": None,
        "sequence_scoped_return_cycle_after_escape": True,
        "abandoned_sequence_continues": False,
        "dominant_scc_visit_count": 80,
        "suffix_steps": 100,
        "final_quartile_same_scc": True,
        "final_quartile_idle_visit_fraction": 1.0,
        "trajectory_prefix_match": True,
    }
    row.update(overrides)
    return row


def _matrix(**by_target):
    rows = []
    for app in POSITIVE_TARGETS:
        spec = by_target.get(app, {})
        for budget in (120, 240, 480):
            rows.append(_row(app, budget, **spec.get(budget, spec.get("all", {}))))
    return rows


def test_persistent_conclusion_requires_both_losers_and_live_contrasts():
    rows = _matrix(**{
        "buggy-campus": {"all": {}},
        "buggy-studio": {"all": {}},
        "buggy-warehouse": {"all": {
            "template_589_recovered": True,
            "productive_entity_reentry": True,
            "productive_reentry_step": 40,
            "template_first_confirm_step": 90,
        }},
        "buggy-booking": {"all": {
            "template_589_recovered": True,
            "productive_entity_reentry": True,
            "productive_reentry_step": 40,
            "template_first_confirm_step": 90,
        }},
    })
    derived = derive_v0322_diagnosis(rows, protocol_valid=True, semantic_unchanged=True)
    assert derived["diagnostic_conclusion"] == "persistent_post_terminal_sink"
    assert derived["promotion_readiness"] == "not_ready"
    assert derived["product_default_changed"] is False


def test_budget_delay_requires_reentry_before_recovery():
    recovered = {
        "template_589_recovered": True,
        "productive_entity_reentry": True,
        "productive_reentry_step": 30,
        "template_first_confirm_step": 70,
    }
    rows = _matrix(**{
        "buggy-campus": {120: {}, 240: recovered, 480: recovered},
        "buggy-studio": {120: {}, 240: {}, 480: recovered},
        "buggy-warehouse": {"all": recovered},
        "buggy-booking": {"all": recovered},
    })
    derived = derive_v0322_diagnosis(rows)
    assert derived["diagnostic_conclusion"] == "budget_delay"
    assert derived["facts"]["first_recovery_budget"]["buggy-campus"] == 240
    assert derived["facts"]["first_recovery_budget"]["buggy-studio"] == 480


def test_split_recovery_is_mixed():
    recovered = {
        "template_589_recovered": True,
        "productive_entity_reentry": True,
        "productive_reentry_step": 30,
        "template_first_confirm_step": 70,
    }
    rows = _matrix(**{
        "buggy-campus": {120: {}, 240: {}, 480: {}},
        "buggy-studio": {120: {}, 240: recovered, 480: recovered},
        "buggy-warehouse": {"all": recovered},
        "buggy-booking": {"all": recovered},
    })
    derived = derive_v0322_diagnosis(rows)
    assert derived["diagnostic_conclusion"] == "mixed_or_inconclusive"


def test_protocol_flag_and_missing_cells_are_invalid():
    derived = derive_v0322_diagnosis([], protocol_valid=False)
    assert derived["diagnostic_conclusion"] == "protocol_invalid"
    derived = derive_v0322_diagnosis(_matrix(), semantic_unchanged=False)
    assert derived["diagnostic_conclusion"] == "protocol_invalid"


def test_contrast_loss_and_prefix_mismatch_are_mixed():
    preserved = {
        "template_589_recovered": True,
        "productive_entity_reentry": True,
        "productive_reentry_step": 10,
        "template_first_confirm_step": 20,
    }
    rows = _matrix(**{
        "buggy-campus": {"all": {}},
        "buggy-studio": {"all": {}},
        "buggy-warehouse": {120: preserved, 240: {}, 480: {}},
        "buggy-booking": {"all": preserved},
    })
    assert derive_v0322_diagnosis(rows)["diagnostic_conclusion"] == "mixed_or_inconclusive"
    rows = _matrix(**{
        "buggy-campus": {"all": {"trajectory_prefix_match": False}},
        "buggy-studio": {"all": {}},
        "buggy-warehouse": {"all": {
            "template_589_recovered": True,
            "productive_entity_reentry": True,
            "productive_reentry_step": 10,
            "template_first_confirm_step": 20,
        }},
        "buggy-booking": {"all": {
            "template_589_recovered": True,
            "productive_entity_reentry": True,
            "productive_reentry_step": 10,
            "template_first_confirm_step": 20,
        }},
    })
    derived = derive_v0322_diagnosis(rows)
    assert derived["diagnostic_conclusion"] == "mixed_or_inconclusive"
    assert "trajectory_prefix_mismatch" in derived["facts"]["reasons"]


def test_historical_b120_audit_matches_committed_evidence():
    rows = {
        app: analyze_cell(load_bundle(app, 120, historical=True))
        for app in POSITIVE_TARGETS
    }
    for app, row in rows.items():
        assert row["first_waypoint_escape_step"] == 21
        assert row["next_action_eid"] == "open_side"
        assert row["next_action_label"] == "branch"
        assert row["first_escape_stack_depth"] == 0
        assert row["first_escape_match_strength"] == "exact"
        assert row["local_residual_count"] == 2
        assert row["structural_residual_count"] == 4
        assert row["residual_tried_before_escape"] == []
        horizon = row["horizon_cycle"]
        assert horizon["return_cycle_escape_step"] == 67
        assert horizon["terminal_outcome"] == "return_cycle_abandoned"
        assert horizon["events_after_terminal"] == []
        assert row["post_abandon_step"] == 38
        assert cell_persistent(row, semantic_unchanged=True) is row["persistent_sink"]
    assert rows["buggy-campus"]["template_lost"] == ["BUG-CP5", "BUG-CP8", "BUG-CP9"]
    assert rows["buggy-studio"]["template_lost"] == ["BUG-ST5", "BUG-ST8", "BUG-ST9"]
    assert rows["buggy-warehouse"]["template_589_recovered"] is True
    assert rows["buggy-booking"]["template_589_recovered"] is True
    assert rows["buggy-campus"]["static"]["classification"] == "closed_scc"
    assert rows["buggy-studio"]["static"]["classification"] == "closed_scc"
    assert rows["buggy-campus"]["static"]["entity_reachable"] is False
    assert rows["buggy-warehouse"]["static"]["classification"] == "policy_attractor_with_static_exit"
    assert rows["buggy-booking"]["static"]["entity_reachable"] is True
    assert rows["buggy-warehouse"]["static"]["form_hub_edge_to_entity"] is True
    assert rows["buggy-campus"]["static"]["form_hub_edge_to_entity"] is False
    assert rows["buggy-campus"]["waypoint_escape_count"] == 1
    assert rows["buggy-warehouse"]["waypoint_escape_count"] == 2
    assert rows["buggy-campus"]["productive_entity_reentry"] is False
    assert rows["buggy-warehouse"]["productive_entity_reentry"] is True
    assert rows["buggy-campus"]["dominant_scc_visit_fraction"] >= DOMINANCE_THRESHOLD
    assert rows["buggy-campus"]["persistent_sink"] is True
    assert rows["buggy-warehouse"]["persistent_sink"] is False


def test_preregistered_files_match_recomputed_audit():
    root = os.path.join("experiments", "validation", "v0.3.22")
    protocol = json.load(open(os.path.join(root, "protocol.json"), encoding="utf-8"))
    assert protocol["executed"] is False
    assert protocol["dominance_threshold"] == DOMINANCE_THRESHOLD
    assert protocol["starting_head"] == "deda60a7ef7494466d12598b9418234c09b543f4"
    assert protocol["matrix"]["cells_total"] == 8
    assert protocol["product_default_changed"] is False
    assert [(item["app"], item["budget"]) for item in protocol["matrix"]["cells"]] == list(CELLS)
    fresh = build_protocol()
    assert fresh["v0_3_21_immutable"]["candidate_source_sha256"] == protocol["v0_3_21_immutable"]["candidate_source_sha256"]
    audit = json.load(open(os.path.join(root, "v03121-post-escape-audit.json"), encoding="utf-8"))
    assert audit == build_historical_audit()
    static = json.load(open(os.path.join(root, "static-scc-analysis.json"), encoding="utf-8"))
    rows = [analyze_cell(load_bundle(app, 120, historical=True)) for app in POSITIVE_TARGETS]
    assert static == build_static_report(rows)
