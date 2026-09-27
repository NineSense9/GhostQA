"""v0.3.29 outcome. Written before the two cells finish."""
from __future__ import annotations

GUARD_KEEP = {
    "buggy-campus": [
        "BUG-CP2", "BUG-CP3", "BUG-CP5", "BUG-CP8", "BUG-CP9",
        "BUG-CP10", "BUG-CP11", "BUG-CP12",
    ],
    "buggy-studio": [
        "BUG-ST2", "BUG-ST3", "BUG-ST5", "BUG-ST8", "BUG-ST9",
        "BUG-ST10", "BUG-ST11", "BUG-ST12",
    ],
}
SETTINGS = {
    "buggy-campus": ["BUG-CP4", "BUG-CP6", "BUG-CP7"],
    "buggy-studio": ["BUG-ST4", "BUG-ST6", "BUG-ST7"],
}


def derive_v0329_outcome(confirmed: dict) -> dict:
    lost = []
    found = []
    missing = []
    for app, keep in GUARD_KEEP.items():
        got = set(confirmed.get(app) or [])
        for bug in keep:
            if bug not in got:
                lost.append({"app": app, "bug": bug})
        for bug in SETTINGS[app]:
            if bug in got:
                found.append(bug)
            else:
                missing.append(bug)
    if lost:
        outcome = "regression"
    elif not missing:
        outcome = "already_covered"
    else:
        outcome = "still_open"
    return {
        "outcome": outcome,
        "lost_guard_bugs": lost,
        "settings_confirmed": found,
        "settings_missing": missing,
        "candidate_change": False,
        "product_default_changed": False,
        "promotion_readiness": "not_ready",
    }
