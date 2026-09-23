"""v0.3.15 suite freeze matches the generated targets."""
import json
import os

from benchmark.algorithm_freeze import verify_freeze
from benchmark.fresh_handoff_generator import APP_NAMES, generated_relpaths
from benchmark.fresh_handoff_qualify import qualify_path

SUITE = os.path.join(
    "experiments", "frozen", "v0.3.15-fresh-handoff-suite", "freeze.json")
QUAL = os.path.join(
    "experiments", "validation", "v0.3.15", "topology-qualification.json")


def test_suite_and_target_freezes_match_files():
    assert verify_freeze(SUITE) == []
    suite = json.load(open(SUITE, encoding="utf-8"))
    assert suite["round"] == "v0.3.15"
    assert suite["protocol_commit"] == "4681d444dc45905c8c644528dae7c253dd936233"
    assert suite["no_target_policy_evaluation_before_freeze"] is True
    assert suite["candidate_source_sha256"] == (
        "827b8e64f953012ceec06fe3e0302c343a016463b5b1f88191e7a0a486c2467e")
    for name in APP_NAMES:
        path = os.path.join(
            "experiments", "frozen", "v0.3.15-fresh-handoff-suite", name, "freeze.json")
        assert verify_freeze(path) == []
        rec = json.load(open(path, encoding="utf-8"))
        assert rec["target"] == name
        for rel in generated_relpaths(name):
            assert rel in rec["files"]
            assert rel in suite["files"]


def test_qualification_artifact_recomputes():
    saved = json.load(open(QUAL, encoding="utf-8"))
    assert saved["round"] == "v0.3.15"
    for name in APP_NAMES:
        got = qualify_path(os.path.join("apps", name, "topology.json"))
        assert got == saved["apps"][name]
        if name == "buggy-directory":
            assert got["qualified"] is False
            assert got["qualifying_chain_count"] == 0
        else:
            assert got["qualified"] is True
            assert got["qualifying_chain_count"] >= 2
