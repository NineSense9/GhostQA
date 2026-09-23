"""The v0.3.16 candidate freeze matches the files that will be evaluated."""
import os

from benchmark.algorithm_freeze import verify_freeze

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FREEZE = os.path.join(
    ROOT, "experiments", "frozen", "ghost-reentry-frontier-v0.3.16", "freeze.json")


def test_v0316_candidate_freeze_matches():
    assert verify_freeze(FREEZE) == []


def test_historical_candidate_and_suite_freezes_still_match():
    assert verify_freeze(os.path.join(
        ROOT, "experiments", "frozen", "ghost-horizon-handoff-v0.3.14", "freeze.json")) == []
    assert verify_freeze(os.path.join(
        ROOT, "experiments", "frozen", "v0.3.15-fresh-handoff-suite", "freeze.json")) == []
