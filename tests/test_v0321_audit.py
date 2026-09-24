"""The v0.3.21 loss audit is recomputed from the frozen v0.3.20 publication."""
import json
import os

from benchmark.return_waypoint_loss_audit import build_audit

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
AUDIT = os.path.join(
    ROOT, "experiments", "validation", "v0.3.21", "v0320-waypoint-loss-analysis.json")


def test_committed_waypoint_audit_matches_recompute():
    with open(AUDIT, encoding="utf-8") as handle:
        saved = json.load(handle)
    assert saved == build_audit()


def test_four_positives_share_the_step21_entity_waypoint():
    audit = build_audit()
    assert [row["app"] for row in audit["targets"]] == [
        "buggy-campus", "buggy-warehouse", "buggy-studio", "buggy-booking",
    ]
    expected = {
        "buggy-campus": ("module.html", "course.html", "courses.html", ["BUG-CP5", "BUG-CP8", "BUG-CP9"]),
        "buggy-warehouse": ("zone.html", "warehouse.html", "warehouses.html", ["BUG-WH5", "BUG-WH8", "BUG-WH9"]),
        "buggy-studio": ("scene.html", "project.html", "projects.html", ["BUG-ST5", "BUG-ST8", "BUG-ST9"]),
        "buggy-booking": ("room.html", "venue.html", "venues.html", ["BUG-BK5", "BUG-BK8", "BUG-BK9"]),
    }
    for target in audit["targets"]:
        mid_page, entity_page, parent_page, lost = expected[target["app"]]
        assert target["lost_vs_guard"] == lost
        divergence = target["first_divergence"]
        assert divergence["action_index"] == 11
        assert divergence["guard"]["action_eid"] == "nav_up_child"
        assert divergence["guard"]["last_label"] == "return_hub"
        assert divergence["candidate"]["action_eid"] == "btn_mark"
        assert divergence["candidate"]["last_label"] == "return_entry_drain"
        assert target["child_parent_witness"]["step"] == 20
        resume = target["parent_frame_resume_to_return"]
        assert resume["step"] == 20
        assert resume["stack_depth"] == 0
        assert resume["returning"] is True
        mid = target["common_step_mid_to_entity"]
        parent = target["common_step_entity_to_list"]
        assert mid["action_index"] == 21
        assert mid["src_page"] == mid_page
        assert mid["dst_page"] == entity_page
        assert mid["last_label"] == "return_hub"
        assert mid["active_branch"] == resume["resumed_branch"]
        assert parent["action_index"] == 22
        assert parent["src_page"] == entity_page
        assert parent["dst_page"] == parent_page
        assert parent["last_label"] == "return_hub"
        assert parent["active_branch"] == resume["resumed_branch"]
        assert mid["dst_cluster"] != resume["original_parent_hub_cluster"]
        residual = target["residual_at_first_waypoint"]
        assert residual["btn_pin"]["first_occurrence"] is None
        assert residual["btn_cool"]["first_occurrence"] is None
        assert residual["btn_pin"]["residual_at_first_waypoint"] is True
        assert residual["btn_cool"]["residual_at_first_waypoint"] is True
        assert residual["open_side"]["residual_at_first_waypoint"] is True
        assert residual["nav_prefs"]["residual_at_first_waypoint"] is True
        observed = set(target["entity_graph"]["observed"])
        assert {"btn_pin", "btn_cool", "open_side", "nav_prefs", "open_mid", "nav_up_list", "back"} <= observed
    assert audit["targets"][0]["residual_at_first_waypoint"]["open_side"]["first_occurrence"] is None
    assert audit["targets"][2]["residual_at_first_waypoint"]["open_side"]["first_occurrence"] is None
    assert audit["targets"][1]["residual_at_first_waypoint"]["open_side"]["first_occurrence"] == 57
    assert audit["targets"][3]["residual_at_first_waypoint"]["open_side"]["first_occurrence"] == 57
