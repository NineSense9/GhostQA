"""v0.3.12 candidate freeze. Identity only; no target evaluation."""
import json
import os

from benchmark.algorithm_freeze import verify_freeze
from benchmark.nested_hub_run import NESTED, make_policy
from ghostqa.exploration.nested_hub_guard import (
    NestedHubPreservingSequenceController, NestedHubReturnGuardGhostPolicy,
)
from ghostqa.exploration.return_cycle_guard import ReturnCycleGuardSequenceController

FREEZE = os.path.join(
    "experiments", "frozen", "ghost-nested-hub-guard-v0.3.12", "freeze.json")


def test_candidate_freeze_files_match():
    assert verify_freeze(FREEZE) == []


def test_candidate_freeze_identity():
    freeze = json.load(open(FREEZE, encoding="utf-8"))
    assert freeze["algorithm_name"] == NESTED
    assert freeze["policy"]["constructor"] == "NestedHubReturnGuardGhostPolicy"
    assert freeze["policy"]["controller"] == "NestedHubPreservingSequenceController"
    assert freeze["policy"]["product_default"] is False
    assert freeze["policy"]["no_threshold_N"] is True
    assert freeze["policy"]["no_parent_stack"] is True
    policy = make_policy(NESTED, 1)
    assert isinstance(policy, NestedHubReturnGuardGhostPolicy)
    assert isinstance(policy.sequence, NestedHubPreservingSequenceController)
    assert issubclass(
        NestedHubPreservingSequenceController, ReturnCycleGuardSequenceController)
    assert policy.sequence.mode == "structural"
    assert policy.use_frontier is False
