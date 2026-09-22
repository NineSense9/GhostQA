"""BuggyDesk freeze identity. Skipped until freeze.json exists; then required."""
import json
import os

from benchmark.algorithm_freeze import sha256_file, verify_freeze
from benchmark.target_freeze import DESK_FILES, DESK_FREEZE, build_desk_freeze


def test_desk_files_exist():
    for rel in DESK_FILES:
        assert os.path.isfile(rel.replace("/", os.sep)), rel


def test_desk_freeze_builder_hashes_are_stable():
    a = build_desk_freeze(freeze_commit="x", purpose="t")
    b = build_desk_freeze(freeze_commit="x", purpose="t")
    assert a["files"] == b["files"]
    sample = DESK_FILES[0]
    assert a["files"][sample]["sha256"] == sha256_file(sample.replace("/", os.sep))


def test_desk_freeze_file_if_present():
    if not os.path.isfile(DESK_FREEZE):
        return
    assert verify_freeze(DESK_FREEZE) == []
    freeze = json.load(open(DESK_FREEZE, encoding="utf-8"))
    assert freeze["target"] == "buggy-desk"
    assert freeze["manifest_is_judge_only"] is True
    assert freeze["no_target_policy_evaluation_before_freeze"] is True
    assert freeze["hash_normalization"] == "LF newlines"
    for rel in DESK_FILES:
        assert rel in freeze["files"], rel
