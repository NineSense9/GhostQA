"""v0.3.37 outcome gate. Written before any fresh policy result."""
from __future__ import annotations

from benchmark.fresh_transfer_v0336_analysis import (
    OUTCOME_MEANING,
    derive_v0336_outcome,
    loop_bug_confirmed,
    passing_facts,
)

__all__ = [
    "OUTCOME_MEANING",
    "derive_v0337_outcome",
    "loop_bug_confirmed",
    "passing_facts",
]


def derive_v0337_outcome(**facts) -> dict:
    derived = derive_v0336_outcome(**facts)
    derived["outcome_meaning"] = {
        "A": "At least three new positives keep every Guard bug, confirm the navigation-loop bug, and record a loop-exit selection",
        "B": "Guard bugs are kept and at least three positives are evaluable, but fewer than three also confirm the navigation-loop bug and record a loop-exit selection",
        "C": OUTCOME_MEANING["C"],
        "D": OUTCOME_MEANING["D"],
    }[derived["outcome"]]
    return derived
