"""Published v0.3.14 artifact matches the frozen gate. No browser rerun."""
import json
import os

from benchmark.horizon_handoff_analysis import derive_v0314_outcome

ROOT = os.path.join("experiments", "published", "horizon-handoff-v0.3.14")


def _load(name):
    with open(os.path.join(ROOT, name), encoding="utf-8") as handle:
        return json.load(handle)


def test_published_round_is_outcome_a_without_promotion():
    config = _load("config.json")
    mechanism = _load(os.path.join("metrics", "mechanism.json"))
    safety = _load(os.path.join("metrics", "safety.json"))
    regression = _load(os.path.join("metrics", "regression.json"))
    reaudit = _load("v0313-restore-reaudit.json")
    derived = mechanism["derived"]
    assert config["outcome"] == "A"
    assert config["product_default_changed"] is False
    assert config["promotion_prohibited"] is True
    assert config["v0_3_13_outcome"] == "C"
    assert config["v0_3_12_outcome"] == "C"
    assert config["v0_3_11_outcome"] == "D"
    assert derived["outcome"] == "A"
    assert derived["crm_repair"] is True
    assert derived["ops_repair"] is True
    assert derived["lost_cases"] == []
    assert derived["product_default_changed"] is False
    assert derived["generalization_claim"] is False
    assert mechanism["witness_violations"] == 0
    assert mechanism["terminal_accounting_violations"] == 0
    for app in ("buggy-desk", "deepbench", "wiki", "buggy-shop"):
        assert regression["cases"][app]["lost_vs_guard"] == []
    crm = mechanism["targets"]["buggy-crm"]["cells"][
        "ghost-structural-horizon-handoff-guard@120"]
    ops = mechanism["targets"]["buggy-ops"]["cells"][
        "ghost-structural-horizon-handoff-guard@120"]
    assert crm["states"] > 5 and crm["normalized_unique_urls"] > 5
    assert ops["states"] > 5 and ops["normalized_unique_urls"] > 5
    assert crm["nested_continuation_events"] > 0
    assert crm["horizon_handoff_started_events"] > 0
    assert ops["nested_continuation_events"] > 0
    assert ops["horizon_handoff_started_events"] > 0
    assert safety["h_series_cases"] == 20
    assert safety["h_series_failures"] == 0
    assert safety["model_raw_traces"] == 19607
    assert safety["model_invariant_failures"] == 0
    assert safety["exhaustive_traces"] == 5800
    assert safety["exhaustive_failures"] == 0
    assert reaudit["apps"]["buggy-desk"]["old_bad_restore_count"] == 1
    assert reaudit["apps"]["buggy-desk"]["corrected_residual_bad_count"] == 0
    assert reaudit["apps"]["deepbench"]["old_bad_restore_count"] == 33
    assert reaudit["apps"]["deepbench"]["corrected_residual_bad_count"] == 0
    assert reaudit["counterfactual_gate"]["counterfactual_outcome"] == "C"
    again = derive_v0314_outcome(
        candidate_freeze_ok=True,
        historical_freezes_ok=True,
        h_series_failures=safety["h_series_failures"],
        model_invariant_failures=safety["model_invariant_failures"],
        historical_safety_regressed=False,
        witness_violations=mechanism["witness_violations"],
        terminal_accounting_violations=mechanism["terminal_accounting_violations"],
        return_inflation=mechanism["return_inflation"],
        wrong_child_or_parent_resume=mechanism["wrong_child_or_parent_resume"],
        app_specific_logic=False,
        product_default_changed=False,
        post_freeze_semantic_tuning=False,
        crm_repair=derived["crm_repair"],
        ops_repair=derived["ops_repair"],
        confirmed={
            app: regression["cases"][app]["candidate_confirmed"]
            for app in ("buggy-desk", "deepbench", "wiki", "buggy-shop")
        },
    )
    assert again["outcome"] == "A"
