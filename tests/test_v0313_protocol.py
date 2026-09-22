"""v0.3.13 protocol is preregistered and not yet executed."""
import json
import os

from benchmark.algorithm_freeze import sha256_file

PROTOCOL = os.path.join("experiments", "validation", "v0.3.13", "protocol.json")
ANALYSIS = os.path.join(
    "experiments", "validation", "v0.3.13", "regression-analysis.json")


def _proto():
    with open(PROTOCOL, encoding="utf-8") as handle:
        return json.load(handle)


def test_protocol_is_unexecuted_stack_preregistration():
    proto = _proto()
    assert proto["executed"] is False
    assert proto["version"] == "v0.3.13"
    assert proto["starting_head"] == "23a5e3688433bfc532abc578ec919083368db604"
    assert proto["candidate"]["identity"] == "ghost-structural-nested-stack-guard"
    assert proto["candidate"]["product_default"] is False
    assert proto["candidate"]["replaces_v0_3_12_identity"] is False
    assert proto["candidate"]["no_is_hub_monkeypatch"] is True
    assert proto["policies"] == {
        "G": "ghost-structural-return-guard",
        "F": "ghost-structural-nested-return-guard",
        "S": "ghost-structural-nested-stack-guard",
    }
    assert proto["matrix"]["budgets"] == [40, 80, 120]
    assert proto["matrix"]["cells_total"] == 18
    assert proto["matrix"]["seeds"] == [1]
    assert proto["historical_outcomes_preserved"]["v0.3.12"] == "C"
    assert proto["historical_outcomes_preserved"]["v0.3.11"] == "D"
    assert proto["product_default"]["unchanged"] is True
    assert proto["product_default"]["promotion_prohibited"] is True
    assert proto["outcome_gates"]["priority"] == "C, then D, then B, else A"
    assert proto["unwind_rule"]["partial_restore"] is False
    assert sha256_file(ANALYSIS) == proto["regression_analysis_sha256"]
