"""State signature, cluster id, and semantic variant key.

Two-layer model
---------------
Structural cluster  = normalize(url) + title + sorted (role, text)
Semantic variant    = stable data-obs facts (whitelist: GUIState.obs minus
                      transient inputs and volatile keys)

Graph nodes are identified by state_id = cluster + variant.
This lets Cart(items=0) and Cart(items=1) be different variants of one
cluster, without hashing wall-clock text into the identity.
"""
from __future__ import annotations

import hashlib
import re
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

from .models import GUIState


VOLATILE_QUERY = {"t", "ts", "timestamp", "_", "sid", "session", "token", "rand"}

# obs keys that are form-buffer / clock / ads — never part of a variant.
_VOLATILE_OBS_EXACT = {
    "t", "ts", "timestamp", "clock", "now", "countdown", "rand", "ad",
    "time", "datetime", "nonce",
}
_VOLATILE_OBS_PREFIX = (
    "input_", "clock_", "time_", "ts_", "rand_", "ad_", "countdown_",
)
_VOLATILE_OBS_RE = re.compile(
    r"(time|clock|countdown|timestamp|session|token|rand|nonce)", re.I
)


def normalize_url(url: str) -> str:
    """Remove volatile query params (timestamps, sessions) to stabilize signatures."""
    parts = urlsplit(url)
    qs = [(k, v) for k, v in parse_qsl(parts.query) if k.lower() not in VOLATILE_QUERY]
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(qs), ""))


def state_signature(state: GUIState) -> str:
    """Structural cluster signature: url + title + sorted (role, text).

    Does **not** include obs. Kept as the cluster identity so existing tests
    and dead-action checks that compare structure stay stable.
    """
    h = hashlib.sha1()
    h.update(normalize_url(state.url).encode("utf-8"))
    h.update(b"|")
    h.update(state.title.encode("utf-8"))
    for role, text in sorted((e.role, e.text) for e in state.elements):
        h.update(b"|")
        h.update(role.encode("utf-8"))
        h.update(b":")
        h.update(text.encode("utf-8"))
    return h.hexdigest()[:16]


def cluster_id(state: GUIState) -> str:
    return state_signature(state)


def _is_volatile_obs_key(key: str) -> bool:
    if key in _VOLATILE_OBS_EXACT:
        return True
    if key.startswith(_VOLATILE_OBS_PREFIX):
        return True
    return bool(_VOLATILE_OBS_RE.search(key))


def _stabilize(value) -> str:
    if isinstance(value, list):
        return ",".join(_stabilize(v) for v in value)
    if isinstance(value, dict):
        return ",".join(f"{k}={_stabilize(value[k])}" for k in sorted(value))
    return str(value)


def variant_facts(state: GUIState) -> tuple:
    """Stable business facts drawn only from data-obs (GUIState.obs).

    Input buffers (`input_*`) are excluded: typing in a search box is not a
    new semantic state. Volatile keys (clocks, ads, tokens) are excluded
    to prevent state explosion.
    """
    items = []
    for key in sorted(state.obs):
        if _is_volatile_obs_key(key):
            continue
        items.append((key, _stabilize(state.obs[key])))
    return tuple(items)


def variant_key(state: GUIState) -> str:
    facts = variant_facts(state)
    if not facts:
        return "none"
    h = hashlib.sha1()
    for k, v in facts:
        h.update(k.encode("utf-8"))
        h.update(b"=")
        h.update(v.encode("utf-8"))
        h.update(b"|")
    return h.hexdigest()[:12]


def state_id(state: GUIState) -> str:
    """Exact node identity: structural cluster + semantic variant."""
    return f"{cluster_id(state)}:{variant_key(state)}"


def ahash64(pixels_gray: list, width: int = 8, height: int = 8) -> int:
    """64-bit average hash from a width*height grayscale pixel list. Pure python."""
    assert len(pixels_gray) == width * height
    avg = sum(pixels_gray) / len(pixels_gray)
    bits = 0
    for i, p in enumerate(pixels_gray):
        if p >= avg:
            bits |= (1 << i)
    return bits


def hamming(a: int, b: int) -> int:
    return bin(a ^ b).count("1")
