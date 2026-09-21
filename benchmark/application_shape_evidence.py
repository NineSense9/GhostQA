"""v0.3.8 committed-evidence loaders and derived metrics.

Sole source of published numbers. Never falls back to experiments/runs.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from collections import Counter

from benchmark.application_shape import (
    SOURCE_MODELED_SHOP_PAGES, graph_descriptors, static_shop_descriptors,
)

SHOP_POLICIES = (
    "bfs", "ghost-deferred", "ghost-sequence", "ghost-structural-memory",
)
FLOW_POLICIES = (
    "dfs", "bfs", "ghost-deferred", "ghost-sequence", "ghost-structural-memory",
)
EVIDENCE_KINDS = ("events.jsonl", "graph.json", "sequence_events.json")
PUBLISHED_ROOT = os.path.join(
    "experiments", "published", "application-shape-v0.3.8")
FREEZE_REL = os.path.join(
    "experiments", "frozen", "ghost-structural-v0.3.6", "freeze.json")


def sha256_file(path: str) -> str:
    """SHA256 of file bytes with newlines normalized to LF.

    Git text files are LF in the object store; Windows working trees may be
    CRLF. Reproduction must not depend on core.autocrlf.
    """
    with open(path, "rb") as f:
        data = f.read().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return hashlib.sha256(data).hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_json_bytes(obj) -> bytes:
    return json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8") + b"\n"


def page_name(url: str) -> str:
    if not url:
        return ""
    path = re.sub(r"^https?://[^/]+", "", url)
    path = path.split("?", 1)[0]
    name = path.rsplit("/", 1)[-1]
    return name or path


def load_json(path: str):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_jsonl(path: str) -> list:
    rows = []
    with open(path, encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid JSONL {path}:{i}: {exc}") from exc
    return rows


def steps_only(events: list) -> list:
    return [e for e in events if e.get("kind") == "step"]


def evidence_dir(root: str, app: str) -> str:
    return os.path.join(root, "evidence", app)


def stem(policy: str, budget: int = 120, seed: int = 1) -> str:
    return f"{policy}_b{budget}_s{seed}"


def evidence_path(root: str, app: str, policy: str, kind: str) -> str:
    return os.path.join(evidence_dir(root, app), f"{stem(policy)}.{kind}")


def validate_raw_file(path: str, kind: str) -> None:
    if kind.endswith("events.jsonl"):
        rows = load_jsonl(path)
        for e in rows:
            if e.get("kind") == "step" and e.get("index") is None:
                raise ValueError(f"{path}: step missing index")
        return
    obj = load_json(path)
    if kind.endswith("graph.json"):
        if not isinstance(obj, dict):
            raise ValueError(f"{path}: graph not an object")
        if "nodes" not in obj or "edges" not in obj:
            raise ValueError(f"{path}: graph missing nodes/edges")
        return
    if kind.endswith("sequence_events.json"):
        if not isinstance(obj, list):
            raise ValueError(f"{path}: sequence_events not a list")
        for e in obj:
            if not isinstance(e, dict) or "event" not in e:
                raise ValueError(f"{path}: bad sequence event")
        return
    raise ValueError(f"unknown kind {kind}")


def expected_matrix() -> list:
    rows = []
    for pol in SHOP_POLICIES:
        for kind in EVIDENCE_KINDS:
            rows.append(("shop", pol, kind))
    for pol in FLOW_POLICIES:
        for kind in EVIDENCE_KINDS:
            rows.append(("flow", pol, kind))
    return rows


def build_manifest(root: str) -> dict:
    files = []
    for app, pol, kind in expected_matrix():
        rel = os.path.join("evidence", app, f"{stem(pol)}.{kind}").replace("\\", "/")
        path = os.path.join(root, rel.replace("/", os.sep))
        if not os.path.isfile(path):
            raise FileNotFoundError(rel)
        validate_raw_file(path, kind)
        ekind = ("events" if kind.startswith("events")
                 else "graph" if kind.startswith("graph")
                 else "sequence_events")
        files.append({
            "relative_path": rel,
            "sha256": sha256_file(path),
            "app": "buggy-shop" if app == "shop" else "buggy-flow",
            "policy": pol,
            "budget": 120,
            "seed": 1,
            "diagnostic_rerun": True,
            "independent_trial": False,
            "evidence_kind": ekind,
            "source_round": "v0.3.8",
            "source_head_at_run": "unknown",
            "algorithm_freeze_manifest": FREEZE_REL.replace("\\", "/"),
        })
    return {
        "round": "v0.3.8",
        "diagnostic_rerun": True,
        "independent_trial": False,
        "files": files,
    }


def verify_manifest(root: str, manifest: dict) -> list:
    """Return list of mismatch strings; empty means OK."""
    bad = []
    seen = set()
    for rec in manifest.get("files") or []:
        rel = rec.get("relative_path") or ""
        if rel in seen:
            bad.append(f"duplicate {rel}")
        seen.add(rel)
        path = os.path.join(root, rel.replace("/", os.sep))
        if not os.path.isfile(path):
            bad.append(f"missing {rel}")
            continue
        got = sha256_file(path)
        if got != rec.get("sha256"):
            bad.append(f"hash {rel}: {got} != {rec.get('sha256')}")
        if rec.get("budget") != 120 or rec.get("seed") != 1:
            bad.append(f"budget/seed {rel}")
        if rec.get("diagnostic_rerun") is not True:
            bad.append(f"diagnostic_rerun {rel}")
        if rec.get("independent_trial") is not False:
            bad.append(f"independent_trial {rel}")
    for app, pol, kind in expected_matrix():
        rel = os.path.join("evidence", app, f"{stem(pol)}.{kind}").replace("\\", "/")
        if rel not in seen:
            bad.append(f"matrix missing {rel}")
    return bad


def seq_counts(seq_events: list) -> dict:
    outcomes = Counter()
    events = Counter()
    for e in seq_events:
        events[e.get("event") or ""] += 1
        if e.get("event") == "sequence_terminal":
            outcomes[e.get("outcome") or "unknown"] += 1
    return {
        "branch_start_events": events.get("branch_start", 0),
        "return_attempt_events": events.get("return_attempt", 0),
        "successful_return_to_parent_events": outcomes.get("returned", 0),
        "sequence_terminal_outcomes": {
            "lost_parent": outcomes.get("lost_parent", 0),
            "finding": outcomes.get("finding", 0),
            "returned": outcomes.get("returned", 0),
            "crash": outcomes.get("crash", 0),
            "budget_end": outcomes.get("budget_end", 0),
        },
        "event_types": dict(events),
    }


def unique_pages(graph: dict) -> list:
    pages = sorted({page_name(n.get("url") or "") for n in graph.get("nodes") or []
                    if page_name(n.get("url") or "")})
    return pages


def first_eid(events: list) -> str:
    steps = steps_only(events)
    if not steps:
        return ""
    return ((steps[0].get("action") or {}).get("target_eid") or "")


def url_visits(events: list, needle: str) -> int:
    n = 0
    for s in steps_only(events):
        blob = (s.get("src_url") or "") + (s.get("dst_url") or "")
        if needle in blob:
            n += 1
    return n


def h1_confirm_step(events: list):
    for s in steps_only(events):
        js = " ".join(s.get("js_errors") or [])
        if "changelog detail" in js:
            return s.get("index")
    return None


def billing_entries(events: list) -> list:
    out = []
    for s in steps_only(events):
        eid = ((s.get("action") or {}).get("target_eid") or "")
        dst = s.get("dst_url") or ""
        src = s.get("src_url") or ""
        if eid == "btn_billing" or (
                "billing" in dst and "billing" not in src):
            out.append(s.get("index"))
    return out


def qty_actions(events: list) -> list:
    out = []
    for s in steps_only(events):
        eid = ((s.get("action") or {}).get("target_eid") or "")
        if eid == "btn_qty_up":
            out.append([s.get("index"), "up"])
        elif eid == "btn_qty_down":
            out.append([s.get("index"), "down"])
    return out


def has_h2_finding(events: list) -> bool:
    for s in steps_only(events):
        for f in s.get("findings") or []:
            if (f.get("assert_id") == "bill_qty_non_negative"
                    or "bill_qty_non_negative" in json.dumps(f)):
                return True
    return False


def derive_shop_policy(root: str, policy: str) -> dict:
    g = load_json(evidence_path(root, "shop", policy, "graph.json"))
    ev = load_jsonl(evidence_path(root, "shop", policy, "events.jsonl"))
    seq = load_json(evidence_path(root, "shop", policy, "sequence_events.json"))
    pages = unique_pages(g)
    return {
        "policy": policy,
        "n_states": len(g.get("nodes") or []),
        "n_urls": len(pages),
        "pages": pages,
        "n_steps": len(steps_only(ev)),
        "observed": seq_counts(seq),
        "descriptors": graph_descriptors(g.get("nodes") or [], g.get("edges") or [], seq),
    }


def derive_flow_policy(root: str, policy: str) -> dict:
    g = load_json(evidence_path(root, "flow", policy, "graph.json"))
    ev = load_jsonl(evidence_path(root, "flow", policy, "events.jsonl"))
    seq = load_json(evidence_path(root, "flow", policy, "sequence_events.json"))
    pages = unique_pages(g)
    return {
        "policy": policy,
        "n_states": len(g.get("nodes") or []),
        "pages": pages,
        "n_steps": len(steps_only(ev)),
        "first_action": first_eid(ev),
        "settings_visits": url_visits(ev, "settings"),
        "changelog_visits": url_visits(ev, "changelog"),
        "h1_confirm_step": h1_confirm_step(ev),
        "billing_entry_steps": billing_entries(ev),
        "qty_actions": qty_actions(ev),
        "h2_finding": has_h2_finding(ev),
        "observed_seq": seq_counts(seq),
    }


def derive_shop_collapse(root: str) -> dict:
    c0 = derive_shop_policy(root, "ghost-sequence")
    c1 = derive_shop_policy(root, "ghost-structural-memory")
    bfs = derive_shop_policy(root, "bfs")
    deferred = derive_shop_policy(root, "ghost-deferred")
    return {
        "observed": {
            "ghost-sequence": c0["observed"] | {
                "n_states": c0["n_states"], "n_urls": c0["n_urls"],
                "pages": c0["pages"]},
            "ghost-structural-memory": c1["observed"] | {
                "n_states": c1["n_states"], "n_urls": c1["n_urls"],
                "pages": c1["pages"]},
            "bfs": {"n_states": bfs["n_states"], "n_urls": bfs["n_urls"],
                    "pages": bfs["pages"]},
            "ghost-deferred": {"n_states": deferred["n_states"],
                               "n_urls": deferred["n_urls"],
                               "pages": deferred["pages"]},
            "old_return_success_events": 2,
            "old_field_source": "misassigned_branch_start_count",
        },
        "interpretation": {
            "primary_failure_class": "return_to_parent_mismatch_after_nested_hub",
            "structural_memory_added_cause": False,
            "fingerprint_primary_cause": False,
            "fingerprint_note": (
                "No evidence that fingerprint/semantic-variant explosion is "
                "the primary cause; the persistent return loop is sufficient "
                "to explain the six-state coverage lock."),
        },
    }


def derive_h1_h2(root: str) -> dict:
    flow = {p: derive_flow_policy(root, p) for p in FLOW_POLICIES}
    def pack(p):
        r = flow[p]
        return {
            "first_action": r["first_action"],
            "settings_visits": r["settings_visits"],
            "changelog_visits": r["changelog_visits"],
            "confirm_step": r["h1_confirm_step"],
            "confirmed": r["h1_confirm_step"] is not None,
        }
    return {
        "h1": {
            "observed": {
                "path": ["index.html", "settings.html", "changelog.html",
                         "btn_changelog_detail"],
                "dfs": pack("dfs"),
                "bfs": pack("bfs"),
                "ghost_deferred": pack("ghost-deferred"),
                "ghost_sequence": pack("ghost-sequence"),
                "ghost_structural_memory": pack("ghost-structural-memory"),
            },
            "interpretation": {
                "failure_class": "reach_failure",
                "immediate_mechanism": (
                    "step-0 action ranking/classification sends C0/C1 to login; "
                    "settings/changelog unvisited in this run"),
                "claim_boundary": "this run / this route, not all shallow bugs",
            },
        },
        "h2": {
            "observed": {
                k.replace("-", "_"): {
                    "billing_entry_steps": flow[k]["billing_entry_steps"],
                    "qty_actions": flow[k]["qty_actions"],
                    "h2_finding": flow[k]["h2_finding"],
                    "reached_billing": bool(flow[k]["billing_entry_steps"]),
                }
                for k in FLOW_POLICIES
            },
            "interpretation": {
                "failure_class": "global_miss_policy_specific",
                "dfs_bfs_c0": "reach_failure",
                "ghost_deferred": "reached_billing_no_qty_down",
                "c1": "reached_billing_qty_sequence_never_below_zero",
                "oracle_blind": False,
            },
        },
    }


def derive_descriptors(root: str) -> dict:
    shop = {p: derive_shop_policy(root, p) for p in SHOP_POLICIES}
    static = static_shop_descriptors()
    return {
        "source_modeled": {
            "mean_shortest_path_depth": {
                "value": static["mean_shortest_path_depth"],
                "provenance": "source_modeled",
            },
            "max_shortest_path_depth": {
                "value": static["max_shortest_path_depth"],
                "provenance": "source_modeled",
            },
            "home_is_hub": {
                "value": static["home_is_hub"],
                "provenance": "source_modeled",
            },
            "pages": {
                "value": SOURCE_MODELED_SHOP_PAGES,
                "provenance": "source_modeled",
            },
        },
        "runtime_observed": {
            p: {
                "n_states": {"value": v["n_states"], "provenance": "runtime_observed"},
                "n_urls": {"value": v["n_urls"], "provenance": "runtime_observed"},
                "pages": {"value": v["pages"], "provenance": "runtime_observed"},
            }
            for p, v in shop.items()
        },
        "trace_derived": {
            p: {
                "branch_start_events": {
                    "value": v["observed"]["branch_start_events"],
                    "provenance": "trace_derived",
                },
                "return_attempt_events": {
                    "value": v["observed"]["return_attempt_events"],
                    "provenance": "trace_derived",
                },
                "successful_return_to_parent_events": {
                    "value": v["observed"]["successful_return_to_parent_events"],
                    "provenance": "trace_derived",
                },
            }
            for p, v in shop.items()
            if p in ("ghost-sequence", "ghost-structural-memory")
        },
    }


def derive_canonical_analysis(root: str) -> dict:
    """Deterministic analysis object. URLs stored as page names only."""
    return {
        "round": "v0.3.8",
        "diagnostic_rerun": True,
        "independent_trial": False,
        "static_shop": static_shop_descriptors(),
        "shop": {p: derive_shop_policy(root, p) for p in SHOP_POLICIES},
        "flow": {p: derive_flow_policy(root, p) for p in FLOW_POLICIES},
        "shop_collapse": derive_shop_collapse(root),
        "h1_h2": derive_h1_h2(root),
        "descriptors": derive_descriptors(root),
    }


def write_derived(root: str) -> dict:
    analysis = derive_canonical_analysis(root)
    metrics = os.path.join(root, "metrics")
    os.makedirs(metrics, exist_ok=True)
    mapping = {
        "analysis.json": analysis,
        "shop-collapse.json": analysis["shop_collapse"],
        "h1-h2.json": analysis["h1_h2"],
        "descriptors.json": analysis["descriptors"],
    }
    hashes = {}
    for name, obj in mapping.items():
        raw = canonical_json_bytes(obj)
        path = os.path.join(metrics, name)
        with open(path, "wb") as f:
            f.write(raw)
        hashes[name] = sha256_bytes(raw)
    analysis_hash = hashes["analysis.json"]
    return {"analysis": analysis, "hashes": hashes,
            "analysis_sha256": analysis_hash}
