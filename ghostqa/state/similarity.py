"""Three-level state similarity: identical / similar-cluster / new.

Wired into StateGraph + Explorer (not an isolated utility):
    IDENTICAL  exact state_id (same cluster AND same variant)
    SIMILAR    same structural cluster, different semantic variant
               OR same URL with near-duplicate element set
    NEW        different structural cluster
"""
from __future__ import annotations

from .models import GUIState
from .signature import (
    state_signature, state_id, cluster_id, hamming, normalize_url,
)

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
    """Classify the relationship between two observed states."""
    if state_id(a) == state_id(b):
        return IDENTICAL
    if cluster_id(a) == cluster_id(b):
        return SIMILAR
    if normalize_url(a.url) == normalize_url(b.url):
        if element_jaccard(a, b) >= jaccard_threshold:
            return SIMILAR
        if a.screenshot_ahash is not None and b.screenshot_ahash is not None:
            if hamming(a.screenshot_ahash, b.screenshot_ahash) <= ahash_threshold:
                return SIMILAR
    return NEW


def classify_against_graph(graph, state: GUIState,
                           id_fn=state_id, cluster_fn=cluster_id) -> str:
    """Place `state` relative to an already-built StateGraph.

    Called by Explorer *before* the new node is inserted, so IDENTICAL means
    "we have been here exactly", SIMILAR means "known page, new business
    variant", NEW means "unknown structure".
    """
    sid = id_fn(state)
    if sid in graph.nodes:
        return IDENTICAL
    cid = cluster_fn(state)
    for node in graph.nodes.values():
        if getattr(node, "cluster_id", "") == cid:
            return SIMILAR
    # Fallback for graphs populated before cluster_id existed: structural sig.
    struct = state_signature(state)
    if any(n.sig == struct or n.sig.startswith(struct + ":")
           for n in graph.nodes.values()):
        return SIMILAR
    return NEW
