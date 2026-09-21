"""Offline v0.3.8 analysis: python -m benchmark.application_shape_analysis

Reads diagnostic traces / graphs. Does not run the frozen policy itself
unless --run is passed (that path is diagnostic_runner).
"""
from __future__ import annotations

import argparse
import json
import os
from collections import Counter

from benchmark.application_shape import (
    STATIC_FLOW, STATIC_SHOP, first_hub_event, graph_descriptors,
    label_text, static_shop_descriptors, url_of,
)


def load_jsonl(path):
    rows = []
    if not os.path.isfile(path):
        return rows
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def steps_only(events):
    return [e for e in events if e.get("kind") == "step"]


def summarize_shop_policy(trace_dir, stem):
    events = load_jsonl(os.path.join(trace_dir, stem + ".events.jsonl"))
    graph = load_json(os.path.join(trace_dir, stem + ".graph.json"))
    seqp = os.path.join(trace_dir, stem + ".sequence_events.json")
    seq_events = load_json(seqp) if os.path.isfile(seqp) else []
    steps = steps_only(events)
    urls_in_order = []
    for s in steps:
        u = s.get("dst_url") or s.get("src_url") or ""
        if not urls_in_order or urls_in_order[-1] != u:
            urls_in_order.append(u)
    first_hub = None
    for e in events:
        if e.get("kind") == "seq_after" and e.get("is_hub"):
            first_hub = e
            break
    labels = Counter(s.get("decision_mode") or "normal" for s in steps)
    new_stops = 0
    for i, s in enumerate(steps):
        if s.get("dst_is_new"):
            new_stops += 1
        if (s.get("n_nodes") or 0) >= 6 and i > 8:
            break
    desc = graph_descriptors(graph.get("nodes") or [], graph.get("edges") or [],
                             seq_events)
    actions = []
    for s in steps[:40]:
        act = s.get("action") or {}
        actions.append({
            "i": s.get("index"),
            "mode": s.get("decision_mode"),
            "src": s.get("src_url"),
            "dst": s.get("dst_url"),
            "eid": act.get("target_eid"),
            "text": act.get("text"),
            "new": s.get("dst_is_new"),
            "label": s.get("last_label"),
            "commit": s.get("commitment_left"),
            "returning": s.get("returning"),
            "branch": s.get("active_branch"),
            "findings": s.get("findings"),
        })
    return {
        "stem": stem,
        "n_steps": len(steps),
        "n_states": desc["n_states"],
        "urls": desc["urls"],
        "url_order": urls_in_order[:20],
        "decision_modes": dict(labels),
        "first_hub_step": None if first_hub is None else first_hub.get("step"),
        "first_hub_n_branch": None if first_hub is None else first_hub.get("n_branch_clicks"),
        "descriptors": desc,
        "prefix40": actions,
        "sequence_event_types": dict(Counter(
            e.get("event") for e in seq_events)),
    }


def h1_hits(events):
    hits = []
    for s in steps_only(events):
        js = " ".join(s.get("js_errors") or [])
        url = (s.get("src_url") or "") + (s.get("dst_url") or "")
        eid = ((s.get("action") or {}).get("target_eid") or "")
        if "changelog" in url or "changelog" in eid or "changelog" in js:
            hits.append({
                "index": s.get("index"),
                "url": s.get("src_url"),
                "eid": eid,
                "js": s.get("js_errors"),
                "mode": s.get("decision_mode"),
            })
        if "changelog detail" in js:
            hits.append({"index": s.get("index"), "confirmed_js": True,
                         "eid": eid, "mode": s.get("decision_mode")})
    return hits


def h2_hits(events):
    hits = []
    for s in steps_only(events):
        eid = ((s.get("action") or {}).get("target_eid") or "")
        url = (s.get("src_url") or "") + " " + (s.get("dst_url") or "")
        if "billing" in url or "qty" in eid:
            hits.append({
                "index": s.get("index"),
                "url": s.get("src_url"),
                "eid": eid,
                "findings": s.get("findings"),
                "mode": s.get("decision_mode"),
            })
    return hits


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--shop-dir", default="")
    ap.add_argument("--flow-dir", default="")
    ap.add_argument("--out", default="")
    args = ap.parse_args()
    report = {
        "static_shop": static_shop_descriptors(),
        "static_flow": STATIC_FLOW,
        "shop": {},
        "flow": {},
    }
    if args.shop_dir:
        for name in ("bfs", "ghost-deferred", "ghost-sequence",
                     "ghost-structural-memory"):
            stem = f"{name}_b120_s1"
            p = os.path.join(args.shop_dir, stem + ".graph.json")
            if os.path.isfile(p):
                report["shop"][name] = summarize_shop_policy(args.shop_dir, stem)
    if args.flow_dir:
        for name in ("dfs", "bfs", "ghost-deferred", "ghost-sequence",
                     "ghost-structural-memory"):
            stem = f"{name}_b120_s1"
            evp = os.path.join(args.flow_dir, stem + ".events.jsonl")
            if os.path.isfile(evp):
                ev = load_jsonl(evp)
                g = load_json(os.path.join(args.flow_dir, stem + ".graph.json"))
                seqp = os.path.join(args.flow_dir, stem + ".sequence_events.json")
                seqe = load_json(seqp) if os.path.isfile(seqp) else []
                report["flow"][name] = {
                    "descriptors": graph_descriptors(
                        g.get("nodes") or [], g.get("edges") or [], seqe),
                    "h1": h1_hits(ev),
                    "h2": h2_hits(ev),
                    "n_steps": len(steps_only(ev)),
                    "urls": sorted({n.get("url") for n in g.get("nodes") or []}),
                    "prefix25": [
                        {
                            "i": s.get("index"),
                            "mode": s.get("decision_mode"),
                            "src": s.get("src_url"),
                            "dst": s.get("dst_url"),
                            "eid": (s.get("action") or {}).get("target_eid"),
                            "js": s.get("js_errors"),
                        }
                        for s in steps_only(ev)[:25]
                    ],
                }
    if args.out:
        os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print("wrote", args.out)
    else:
        print(json.dumps(report, ensure_ascii=False, indent=2)[:4000])


if __name__ == "__main__":
    main()
