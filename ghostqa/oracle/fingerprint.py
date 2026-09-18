"""BugFingerprint: the single identity scheme for a bug across the whole system.

Discovery, dedup, replay validation, benchmark manifest matching and reports
MUST all use this module. No module may invent its own matching rules.

Fingerprint = kind-specific canonical string -> sha1 (16 hex chars).

    crash:       crash      | norm_url(page) | action
    js_error:    js_error   | norm_url       | norm_error
    http_error:  http_error | norm_url       | norm_error(endpoint+status)
    dead_action: dead_action| page           | eid
    nav_loop:    nav_loop   | sorted cycle urls
    blank:       blank      | norm_url
    semantic:    semantic   | assert_id      | norm_url
"""
from __future__ import annotations

import hashlib
import re


def normalize_url(url: str) -> str:
    if not url:
        return ""
    u = url.split("#", 1)[0].split("?", 1)[0]
    u = re.sub(r"^(https?|sim)://[^/]+", "", u)   # strip scheme+host
    return u.rstrip("/").lower() or "/"


_WS = re.compile(r"\s+")
_DIGITS = re.compile(r"\d+")


def normalize_error(msg: str) -> str:
    if not msg:
        return ""
    first = str(msg).splitlines()[0]
    first = _DIGITS.sub("#", first)
    return _WS.sub(" ", first).strip().lower()[:120]


def _canonical(kind: str, parts: list) -> str:
    raw = kind + "|" + "|".join(p for p in parts if p)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def fingerprint_of(kind: str, evidence: dict) -> str:
    """Compute a BugFingerprint from a finding's kind + evidence."""
    ev = evidence or {}
    url = normalize_url(ev.get("url", ""))
    if kind == "crash":
        return _canonical(kind, [normalize_url(ev.get("page_url") or ev.get("url", "")),
                                 ev.get("action", "")])
    if kind in ("js_error", "http_error"):
        return _canonical(kind, [url, normalize_error(ev.get("error", ""))])
    if kind == "dead_action":
        return _canonical(kind, [ev.get("page") or url, ev.get("eid", "")])
    if kind == "nav_loop":
        return _canonical(kind, [",".join(sorted(ev.get("cycle_urls", []))) or url])
    if kind == "blank":
        return _canonical(kind, [url])
    if kind == "semantic":
        return _canonical(kind, [ev.get("assert_id", ""), url])
    return _canonical(kind, [url, normalize_error(str(sorted(ev.items())))])


def fingerprint(finding) -> str:
    return fingerprint_of(finding.kind, finding.evidence)
