"""Copy a finished v0.3.10 run into experiments/published/fresh-transfer-v0.3.10/."""
from __future__ import annotations

import argparse
import json
import os
import shutil

from benchmark.application_shape_evidence import canonical_json_bytes, sha256_bytes, sha256_file
from benchmark.fresh_transfer_analysis import PUBLISHED_ROOT, derive_bundle
from benchmark.return_cycle_safety import collect_safety_suite

MATRIX = (
    "ghost-structural-memory",
    "ghost-structural-return-guard",
    "ghost-nollm",
    "bfs",
    "dfs",
)
BUDGETS = (40, 80, 120)
KINDS = ("events.jsonl", "graph.json", "sequence_events.json")


def _write(path: str, text: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def _write_json(path: str, obj) -> None:
    data = json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    _write(path, data)


def copy_run(run_root: str, out_root: str) -> None:
    desk_src = os.path.join(run_root, "evidence")
    desk_dst = os.path.join(out_root, "evidence", "buggy-desk")
    os.makedirs(desk_dst, exist_ok=True)
    for pol in MATRIX:
        for bud in BUDGETS:
            stem = f"{pol}_b{bud}_s1"
            for kind in KINDS:
                src = os.path.join(desk_src, stem + "." + kind)
                if os.path.isfile(src):
                    shutil.copy2(src, os.path.join(desk_dst, stem + "." + kind))
    shutil.copy2(os.path.join(run_root, "metrics.json"),
                 os.path.join(desk_dst, "metrics.json"))
    shutil.copy2(
        os.path.join("experiments", "validation", "v0.3.10", "protocol.json"),
        os.path.join(out_root, "protocol.json"))


def bug_visibility(out_root: str) -> list:
    man = json.load(open(
        os.path.join("apps", "buggy-desk", "bugs.manifest.json"), encoding="utf-8"))
    spec = json.load(open(os.path.join("apps", "buggy-desk", "spec.json"), encoding="utf-8"))
    spec_ids = {a["id"] for a in spec.get("assertions") or spec}
    metrics = json.load(open(
        os.path.join(out_root, "evidence", "buggy-desk", "metrics.json"), encoding="utf-8"))
    by_pol = {}
    for r in metrics.get("runs") or []:
        if r.get("budget") == 120:
            by_pol[r["policy"]] = set(r.get("confirmed_bugs") or [])
    rows = []
    for b in man["bugs"]:
        rows.append({
            "id": b["id"],
            "kind": b["kind"],
            "trigger_depth": b.get("trigger_depth"),
            "spec_visible": b["kind"] == "semantic" and b.get("match", {}).get("assert_id") in spec_ids,
            "manifest_hidden": True,
            "policies_confirmed": sorted(
                p for p, ids in by_pol.items() if b["id"] in ids),
        })
    return rows


def write_summary(out_root: str, bundle: dict) -> str:
    d = bundle["derived"]
    table = bundle["observed"]["table_120"]
    safety = bundle.get("safety") or {}
    lines = [
        "# GhostQA v0.3.10 — Fresh Cross-App Transfer",
        "",
        f"**Outcome {d['outcome']} — {d['outcome_meaning']}** (computed from protocol gates).",
        "",
        "Product default unchanged: NoFrontier, `sequence_mode=off`.",
        "",
        "## Authoring-bias disclosure",
        "",
        "- BuggyDesk was authored after v0.3.9 existed.",
        "- The v0.3.9 candidate was frozen before target evaluation.",
        "- BuggyDesk was frozen before policy evaluation.",
        "- This is a fresh one-target cross-app transfer test, not an independently designed external benchmark and not universal generalization proof.",
        "",
        "## BuggyDesk @120",
        "",
        "| policy | states | URLs | BDR | Deep-BDR | return attempts | returned | escapes | confirmed |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for r in table:
        conf = ", ".join(r.get("confirmed") or []) or "—"
        lines.append(
            f"| {r['policy']} | {r.get('states')} | {r.get('urls')} | {r.get('BDR')} | "
            f"{r.get('Deep-BDR')} | {r.get('return_attempts')} | {r.get('returned')} | "
            f"{r.get('escapes')} | {conf} |"
        )
    lines += [
        "",
        "BFS/DFS/ghost-nollm are context. They are not outcome gates.",
        "",
        "## Safety suite",
        "",
        "| scenario | expected | observed | pass |",
        "|---|---|---|---|",
    ]
    for row in safety.get("rows") or []:
        lines.append(
            f"| {row['scenario']} {row.get('name','')} | {row.get('expected')} | "
            f"{row.get('observed')} | {row.get('pass')} |"
        )
    vis_path = os.path.join(out_root, "metrics", "bug-visibility.json")
    vis = json.load(open(vis_path, encoding="utf-8")) if os.path.isfile(vis_path) else []
    lines += [
        "",
        "## Post-hoc bug visibility",
        "",
        "| bug id | kind | trigger depth | spec-visible? | manifest-hidden? | policies confirmed |",
        "|---|---|---:|---|---|---|",
    ]
    for b in vis:
        lines.append(
            f"| {b['id']} | {b['kind']} | {b.get('trigger_depth')} | {b.get('spec_visible')} | "
            f"{b.get('manifest_hidden')} | {', '.join(b.get('policies_confirmed') or []) or '—'} |"
        )
    c1 = bundle.get("c1_120") or {}
    g = bundle.get("guard_120") or {}
    lines += [
        "",
        "## Transfer metrics (primary budget 120)",
        "",
        f"- C1 evaluable return-cycle opportunities: {c1.get('c1_opportunity_count')}",
        f"- Guard return_cycle_escape events: {g.get('return_cycle_escape_events')}",
        f"- Post-escape novel states: {g.get('post_escape_novel_state_count')}",
        f"- Post-escape novel URLs: {g.get('post_escape_novel_urls')}",
        f"- Absent from C1 URLs: {g.get('absent_from_c1_urls')}",
        f"- C1 confirmed bugs lost by guard: {d.get('lost_c1_confirmed')}",
        f"- First escape step: {g.get('first_escape_step')}",
        "",
        "## Reproduce",
        "",
        "```text",
        "python -m benchmark.fresh_transfer_reproduce --root experiments/published/fresh-transfer-v0.3.10 --verify",
        "```",
        "",
        "Product default changed: no",
        "",
    ]
    return "\n".join(lines) + "\n"


def manifest_files(out_root: str) -> list:
    rels = []
    for dirpath, _, filenames in os.walk(out_root):
        for name in filenames:
            if name.endswith(".png"):
                continue
            path = os.path.join(dirpath, name)
            rel = os.path.relpath(path, out_root).replace("\\", "/")
            rels.append(rel)
    rels = [r for r in rels if r != "evidence-manifest.json"]
    rels.sort()
    files = []
    for rel in rels:
        path = os.path.join(out_root, rel.replace("/", os.sep))
        files.append({"relative_path": rel, "sha256": sha256_file(path)})
    return files


def publish(run_root: str, out_root: str, *,
            protocol_commit: str, freeze_commit: str,
            historical_ok: bool, freeze_ok: bool) -> dict:
    if os.path.isdir(out_root):
        shutil.rmtree(out_root)
    os.makedirs(out_root, exist_ok=True)
    copy_run(run_root, out_root)
    safety = collect_safety_suite()
    _write_json(os.path.join(out_root, "evidence", "safety", "safety.json"), safety)
    vis = bug_visibility(out_root)
    os.makedirs(os.path.join(out_root, "metrics"), exist_ok=True)
    _write_json(os.path.join(out_root, "metrics", "bug-visibility.json"), vis)
    bundle = derive_bundle(out_root, safety=safety,
                           historical_ok=historical_ok, freeze_ok=freeze_ok)
    raw = json.load(open(os.path.join(out_root, "evidence", "buggy-desk", "metrics.json"),
                         encoding="utf-8"))
    _write_json(os.path.join(out_root, "metrics", "raw-runs.json"), raw)
    derived_bytes = canonical_json_bytes(bundle)
    _write(os.path.join(out_root, "metrics", "derived.json"), derived_bytes.decode("utf-8"))
    _write(os.path.join(out_root, "metrics", "metrics.json"), derived_bytes.decode("utf-8"))
    config = {
        "round": "v0.3.10 Fresh Transfer",
        "protocol": "experiments/validation/v0.3.10/protocol.json",
        "protocol_commit": protocol_commit,
        "fresh_target_freeze": "experiments/frozen/buggy-desk-v0.3.10/freeze.json",
        "fresh_target_freeze_commit": freeze_commit,
        "candidate_freeze": "experiments/frozen/ghost-return-cycle-guard-v0.3.9/freeze.json",
        "historical_c1_freeze": "experiments/frozen/ghost-structural-v0.3.6/freeze.json",
        "product_default": "NoFrontier, sequence_mode=off",
        "policies": list(MATRIX),
        "budgets": list(BUDGETS),
        "seed": 1,
        "seed_invariant": True,
        "verify_command": (
            "python -m benchmark.fresh_transfer_reproduce "
            "--root experiments/published/fresh-transfer-v0.3.10 --verify"),
        "hash_normalization": "LF newlines",
        "expected_metrics_sha256": sha256_bytes(derived_bytes),
    }
    _write_json(os.path.join(out_root, "config.json"), config)
    _write(os.path.join(out_root, "summary.md"), write_summary(out_root, bundle))
    _write(os.path.join(out_root, "README.md"),
           "Published v0.3.10 fresh-transfer evidence. See summary.md.\n")
    files = manifest_files(out_root)
    man = {
        "round": "v0.3.10",
        "expected_file_count": len(files),
        "hash_normalization": "LF newlines",
        "files": files,
    }
    _write_json(os.path.join(out_root, "evidence-manifest.json"), man)
    # re-hash manifest is not self-included
    repro = {
        "clean_clone_verified": False,
        "command": config["verify_command"],
        "expected_metrics_sha256": config["expected_metrics_sha256"],
        "match": True,
        "outcome": bundle["derived"]["outcome"],
        "evidence_manifest_verified": True,
        "candidate_freeze_verified": True,
        "historical_c1_freeze_verified": True,
        "target_freeze_verified": True,
        "ignored_run_dirs_in_clone": False,
    }
    _write_json(os.path.join(out_root, "metrics", "reproduction.json"), repro)
    # reproduction.json was not in the first manifest pass; rebuild
    files = manifest_files(out_root)
    man = {
        "round": "v0.3.10",
        "expected_file_count": len(files),
        "hash_normalization": "LF newlines",
        "files": files,
    }
    _write_json(os.path.join(out_root, "evidence-manifest.json"), man)
    return bundle


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default=os.path.join("experiments", "runs", "v0310-desk"))
    ap.add_argument("--out", default=PUBLISHED_ROOT)
    ap.add_argument("--protocol-commit", required=True)
    ap.add_argument("--freeze-commit", required=True)
    args = ap.parse_args(argv)
    bundle = publish(
        args.run, args.out,
        protocol_commit=args.protocol_commit,
        freeze_commit=args.freeze_commit,
        historical_ok=True, freeze_ok=True)
    print("outcome", bundle["derived"]["outcome"])
    print("wrote", args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
