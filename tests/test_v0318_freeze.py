"""The v0.3.18 candidate freeze matches the files that will be evaluated."""
import os

from benchmark.algorithm_freeze import verify_freeze
from benchmark.return_cycle_guard_reproduce import verify_candidate_identity

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FREEZE = os.path.join(
    ROOT, "experiments", "frozen", "ghost-return-entry-drain-v0.3.18", "freeze.json")


def test_v0318_candidate_freeze_matches():
    assert verify_freeze(FREEZE) == []


def test_historical_freezes_still_match():
    assert verify_candidate_identity() == []
    for rel in (
        "experiments/frozen/ghost-horizon-handoff-v0.3.14/freeze.json",
        "experiments/frozen/v0.3.15-fresh-handoff-suite/freeze.json",
        "experiments/frozen/ghost-reentry-frontier-v0.3.16/freeze.json",
        "experiments/frozen/ghost-local-action-drain-v0.3.17/freeze.json",
    ):
        assert verify_freeze(os.path.join(ROOT, rel)) == []
