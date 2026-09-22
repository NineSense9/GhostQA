"""v0.3.13 candidate freeze. Identity only; no target evaluation."""
import json
import os

from benchmark.algorithm_freeze import verify_freeze
from benchmark.nested_stack_run import STACK, make_policy
from ghostqa.exploration.nested_stack_guard import (
    NestedStackReturnGuardGhostPolicy, SuspendedParentSequenceController,
)
from ghostqa.exploration.return_cycle_guard import ReturnCycleGuardSequenceController

FREEZE = os.path.join(
    "experiments", "frozen", "ghost-nested-stack-guard-v0.3.13", "freeze.json")


def test_candidate_freeze_files_match():
    assert verify_freeze(FREEZE) == []


def test_candidate_freeze_identity():
    freeze = json.load(open(FREEZE, encoding="utf-8"))
    assert freeze["algorithm_name"] == STACK
    assert freeze["policy"]["constructor"] == "NestedStackReturnGuardGhostPolicy"
    assert freeze["policy"]["controller"] == "SuspendedParentSequenceController"
    assert freeze["policy"]["product_default"] is False
    assert freeze["policy"]["parent_stack"] is True
    assert freeze["policy"]["replaces_v0_3_12_identity"] is False
    policy = make_policy(STACK, 1)
    assert isinstance(policy, NestedStackReturnGuardGhostPolicy)
    assert isinstance(policy.sequence, SuspendedParentSequenceController)
    assert issubclass(
        SuspendedParentSequenceController, ReturnCycleGuardSequenceController)
    assert policy.sequence.mode == "structural"
    assert policy.use_frontier is False
    assert policy.name == "ghost-structural-nested-stack-guard"
