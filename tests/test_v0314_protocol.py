"""v0.3.14 protocol is preregistered and not yet executed."""
import json
import os

from benchmark.algorithm_freeze import sha256_file

PROTOCOL = os.path.join("experiments", "validation", "v0.3.14", "protocol.json")
REAUDIT = os.path.join(
    "experiments", "validation", "v0.3.14", "v0313-restore-reaudit.json")


def _proto():
    with open(PROTOCOL, encoding="utf-8") as handle:
        return json.load(handle)


def test_protocol_is_unexecuted_horizon_preregistration():
    proto = _proto()
    assert proto["executed"] is False
    assert proto["version"] == "v0.3.14"
    assert proto["starting_head"] == "202abe12310f30e552fbff5317e593682f60a726"
    assert proto["reaudit_commit"] == "f7f40864e3eceefae4bc02d1f7e270c07253cc0f"
    assert sha256_file(REAUDIT) == proto["reaudit_sha256"]
    assert proto["candidate"]["identity"] == "ghost-structural-horizon-handoff-guard"
    assert proto["candidate"]["product_default"] is False
    assert proto["candidate"]["replaces_historical_identities"] is False
    assert proto["candidate"]["no_is_hub_monkeypatch"] is True
    assert proto["candidate"]["no_threshold_N"] is True
    assert proto["candidate"]["branch_horizon_unchanged"] == 3
    assert proto["matrix"]["cells_total"] == 10
    assert proto["matrix"]["seed"] == 1
    assert proto["matrix"]["candidate_only"] is True
    assert proto["model_raw_traces"] == 19607
    assert proto["historical_outcomes_preserved"] == {
        "v0.3.11": "D",
        "v0.3.12": "C",
        "v0.3.13": "C",
    }
    assert proto["product_default"]["unchanged"] is True
    assert proto["product_default"]["outcome_A_promotes"] is False
    assert proto["outcome_gates"]["priority"] == "C, then D, then B, else A"
    assert proto["v0313_measurement_erratum"]["publication_rewritten"] is False
    assert proto["v0313_measurement_erratum"]["counterfactual_with_restore_flag_false"] == "C"
    assert proto["unwind_rule"]["partial_restore"] is False
    assert "commitment_left > 1" in proto["continuation_condition"]["when_all"]
    assert "commitment_left == 1" in proto["handoff_condition"]["when_all"]
    assert "ledger.return_success greater than the value before the call" == (
        proto["witness_definition"]["not_sufficient"])
