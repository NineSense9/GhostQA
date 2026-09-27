"""v0.3.34 outcome gate. Written before any fresh policy result."""
from __future__ import annotations

from benchmark.fresh_transfer_v0333_analysis import (
    OUTCOME_MEANING,
    derive_v0333_outcome,
    pair_confirmed,
    passing_facts,
)

__all__ = [
    "OUTCOME_MEANING",
    "derive_v0334_outcome",
    "pair_confirmed",
    "passing_facts",
]


def derive_v0334_outcome(**facts) -> dict:
    return derive_v0333_outcome(**facts)
