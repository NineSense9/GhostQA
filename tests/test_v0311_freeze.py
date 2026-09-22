"""v0.3.11 suite freeze identity. Required once freeze.json exists."""
import json
import os

from benchmark.algorithm_freeze import sha256_file, verify_freeze
from benchmark.target_freeze import (
    GENERATOR_FILES, V0311_SUITE_FREEZE, V0311_TARGET_FREEZES,
    build_v0311_suite_freeze, v0311_target_files,
)
from benchmark.multitarget_vocab import APP_NAMES


def test_generator_and_target_files_exist():
    for rel in GENERATOR_FILES:
        assert os.path.isfile(rel.replace("/", os.sep)), rel
    for name in APP_NAMES:
        for rel in v0311_target_files(name):
            assert os.path.isfile(rel.replace("/", os.sep)), rel


def test_suite_freeze_builder_stable():
    a = build_v0311_suite_freeze(
        freeze_commit="x", protocol_commit="p", purpose="t")
    b = build_v0311_suite_freeze(
        freeze_commit="x", protocol_commit="p", purpose="t")
    assert a["files"] == b["files"]
    sample = GENERATOR_FILES[0]
    assert a["files"][sample]["sha256"] == sha256_file(sample.replace("/", os.sep))


def test_v0311_freeze_files_if_present():
    if not os.path.isfile(V0311_SUITE_FREEZE):
        return
    assert verify_freeze(V0311_SUITE_FREEZE) == []
    freeze = json.load(open(V0311_SUITE_FREEZE, encoding="utf-8"))
    assert freeze["round"] == "v0.3.11"
    assert freeze["no_target_policy_evaluation_before_freeze"] is True
    assert freeze["manifest_is_judge_only"] is True
    for name in APP_NAMES:
        path = V0311_TARGET_FREEZES[name]
        assert os.path.isfile(path)
        assert verify_freeze(path) == []
        rec = json.load(open(path, encoding="utf-8"))
        assert rec["target"] == name
        for rel in v0311_target_files(name):
            assert rel in rec["files"], rel
