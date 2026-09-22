"""v0.3.14 candidate freeze matches the preregistered sources."""
import json
import os

from benchmark.algorithm_freeze import sha256_file, verify_freeze

FREEZE = os.path.join(
    "experiments", "frozen", "ghost-horizon-handoff-v0.3.14", "freeze.json")


def test_horizon_candidate_freeze_matches_working_tree():
    assert verify_freeze(FREEZE) == []
    freeze = json.loads(open(FREEZE, encoding="utf-8").read())
    assert freeze["algorithm_name"] == "ghost-structural-horizon-handoff-guard"
    assert freeze["protocol_commit"] == "ab883e94a6661f1183e30dccba84ed506e92dab6"
    assert freeze["policy"]["product_default"] is False
    assert freeze["policy"]["continuation_when"] == "commitment_left > 1"
    assert freeze["policy"]["handoff_when"] == "commitment_left == 1"
    assert freeze["policy"]["no_is_hub_monkeypatch"] is True
    protocol = "experiments/validation/v0.3.14/protocol.json"
    assert sha256_file(protocol) == freeze["files"][protocol]["sha256"]
