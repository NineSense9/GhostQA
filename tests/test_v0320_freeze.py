"""v0.3.20 suite freeze matches the generated targets."""
import json
import os

from benchmark.algorithm_freeze import verify_freeze
from benchmark.fresh_composite_generator import APP_NAMES, generated_relpaths
from benchmark.fresh_composite_qualify import _public_qualification, qualify_path

SUITE = os.path.join(
    "experiments", "frozen", "v0.3.20-fresh-composite-suite", "freeze.json")
QUAL = os.path.join(
    "experiments", "validation", "v0.3.20", "static-qualification.json")


def test_suite_and_target_freezes_match_files():
    assert verify_freeze(SUITE) == []
    suite = json.load(open(SUITE, encoding="utf-8"))
    assert suite["round"] == "v0.3.20"
    assert suite["protocol_commit"] == "c278b8274d92c509ea4d29de286150e51c4918ea"
    assert suite["no_target_policy_evaluation_before_freeze"] is True
    assert suite["candidate_source_sha256"] == (
        "0bfec3c7bd2811f154daa83bc81fde632976b8ab6e1da9ee6a208cf81c4bb42c")
    for name in APP_NAMES:
        path = os.path.join(
            "experiments", "frozen", "v0.3.20-fresh-composite-suite", name, "freeze.json")
        assert verify_freeze(path) == []
        rec = json.load(open(path, encoding="utf-8"))
        assert rec["target"] == name
        for rel in generated_relpaths(name):
            assert rel in rec["files"]
            assert rel in suite["files"]


def test_qualification_artifact_recomputes():
    saved = json.load(open(QUAL, encoding="utf-8"))
    assert saved["round"] == "v0.3.20"
    assert saved["branch_horizon"] == 3
    for name in APP_NAMES:
        got = _public_qualification(qualify_path(os.path.join("apps", name, "topology.json")))
        assert got == saved["apps"][name]
        assert got["qualified"] is True
