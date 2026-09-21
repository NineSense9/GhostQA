"""One-shot protocol guard. Does not score holdout bugs."""
import json
import os
import tempfile

from benchmark.validation_runner import load_protocol


def test_preregistered_protocol_is_not_yet_executed():
    proto = load_protocol(os.path.join(
        "experiments", "validation", "v0.3.7", "protocol.json"))
    assert proto["executed"] is False
    assert "ghost-structural-memory" in proto["policies"]
    assert "ghost-contextual" not in proto["policies"]
    assert proto["budgets"] == [40, 80, 120]
    assert proto["trials"] == [1]


def test_holdout_refuses_second_primary_run(monkeypatch):
    from benchmark import validation_runner as vr

    with tempfile.TemporaryDirectory() as td:
        proto_path = os.path.join(td, "protocol.json")
        freeze = os.path.join(
            "experiments", "frozen", "ghost-structural-v0.3.6", "freeze.json")
        with open(proto_path, "w", encoding="utf-8") as f:
            json.dump({
                "executed": True,
                "algorithm_freeze": freeze,
                "policies": ["dfs"],
                "budgets": [40],
                "trials": [1],
                "v1_holdout": {
                    "app": "buggy-flow",
                    "manifest": "holdout.manifest.json",
                },
            }, f)
        monkeypatch.setattr("sys.argv", [
            "validation_runner", "--protocol", proto_path,
            "--target", "holdout", "--out", os.path.join(td, "out"),
        ])
        assert vr.main() == 2
