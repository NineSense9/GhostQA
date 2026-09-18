"""Three-level state similarity: identical / similar-cluster / new."""
from __future__ import annotations

from .models import GUIState
from .signature import state_signature, hamming, normalize_url

IDENTICAL = "identical"
SIMILAR = "similar"
NEW = "new"


def element_jaccard(a: GUIState, b: GUIState) -> float:
    sa = {(e.role, e.text) for e in a.elements}
    sb = {(e.role, e.text) for e in b.elements}
    if not sa and not sb:
        return 1.0
    union = sa | sb
    if not union:
        return 1.0
    return len(sa & sb) / len(union)


def state_similarity(a: GUIState, b: GUIState,
                     jaccard_threshold: float = 0.8,
                     ahash_threshold: int = 10) -> str:
    """Classify the relationship between two states."""
    if state_signature(a) == state_signature(b):
        return IDENTICAL
    if normalize_url(a.url) == normalize_url(b.url):
        if element_jaccard(a, b) >= jaccard_threshold:
            return SIMILAR
        if a.screenshot_ahash is not None and b.screenshot_ahash is not None:
            if hamming(a.screenshot_ahash, b.screenshot_ahash) <= ahash_threshold:
                return SIMILAR
    return NEW
