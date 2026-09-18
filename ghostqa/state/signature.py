"""State signature & visual hashing. Program-computed, zero model cost."""
from __future__ import annotations

import hashlib
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

from .models import GUIState


def normalize_url(url: str) -> str:
    """Remove volatile query params (timestamps, sessions) to stabilize signatures."""
    parts = urlsplit(url)
    volatile = {"t", "ts", "timestamp", "_", "sid", "session", "token", "rand"}
    qs = [(k, v) for k, v in parse_qsl(parts.query) if k.lower() not in volatile]
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(qs), ""))


def state_signature(state: GUIState) -> str:
    """Structural signature: url + title + sorted (role, text) of elements."""
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
