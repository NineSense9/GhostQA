"""v0.3.7 freeze verification and manifest isolation. Does not open holdout."""
import inspect
import json
import os
import tempfile

from benchmark.algorithm_freeze import (
    DEFAULT_FREEZE, assert_frozen, sha256_file, verify_freeze,
)
from benchmark.web_runner import make_policy


FROZEN_FILES = [
    "ghostqa/exploration/policy.py",
    "ghostqa/exploration/sequence.py",
    "ghostqa/exploration/sequence_memory.py",
    "ghostqa/exploration/interaction.py",
    "ghostqa/exploration/payload.py",
]


def test_current_tree_matches_structural_freeze():
    assert verify_freeze(DEFAULT_FREEZE) == []


def test_validation_aborts_when_frozen_hash_changes():
    freeze = json.load(open(DEFAULT_FREEZE, encoding="utf-8"))
    freeze["files"]["ghostqa/exploration/payload.py"]["sha256"] = "0" * 64
    with tempfile.TemporaryDirectory() as td:
        path = os.path.join(td, "freeze.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(freeze, f)
        bad = verify_freeze(path)
        assert bad
        try:
            assert_frozen(path)
            raised = False
        except SystemExit:
            raised = True
        assert raised


def test_make_policy_structural_matches_freeze_config():
    p = make_policy("ghost-structural-memory", 1)
    assert p.use_frontier is False
    assert p.sequence_mode == "structural"
    assert getattr(p, "postreach_mode", "off") in ("off", None, "")
    assert p.llm is None or p.llm.__class__.__name__ == "NullLLM"


def test_exploration_modules_do_not_read_manifests():
    mods = [
        "ghostqa.exploration.policy",
        "ghostqa.exploration.sequence",
        "ghostqa.exploration.sequence_memory",
        "ghostqa.exploration.payload",
        "ghostqa.exploration.explorer",
        "ghostqa.oracle.engine",
    ]
    for name in mods:
        src = inspect.getsource(__import__(name, fromlist=["x"]))
        assert "holdout.manifest" not in src, name
        assert "bugs.manifest.json" not in src, name


def test_frozen_file_sha256_helper_is_stable():
    path = os.path.join("ghostqa", "exploration", "payload.py")
    assert sha256_file(path) == sha256_file(path)
