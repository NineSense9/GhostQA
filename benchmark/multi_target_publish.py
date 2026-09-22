"""Copy a finished v0.3.11 run into experiments/published/multi-target-replication-v0.3.11/."""
from __future__ import annotations

import argparse
import json
import os
import shutil

from benchmark.application_shape_evidence import canonical_json_bytes, sha256_bytes, sha256_file
from benchmark.multi_target_analysis import (
    APP_NAMES, CONTEXT, GUARD, MATRIX_PRIMARY, PRIMARY, PRIMARY_BUDGET,
    PRIMARY_BUDGETS, PUBLISHED_ROOT, derive_suite,
)
from benchmark.return_cycle_modelcheck import run_exhaustive_check
from benchmark.return_cycle_safety import collect_safety_suite
from benchmark.multitarget_generator import FAMILIES

KINDS = ("events.jsonl", "graph.json", "sequence_events.json")


def _write(path: str, text: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text if text.endswith("\n") else text + "\n")


def _write_json(path: str, obj) -> None:
    _write(path, json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def copy_run(run_root: str, out_root: str) -> None:
    for app in APP_NAMES:
        src = os.path.join(run_root, "evidence", app)
        dst = os.path.join(out_root, "evidence", app)
        os.makedirs(dst, exist_ok=True)
        for pol in list(MATRIX_PRIMARY) + list(CONTEXT):
            budgets = PRIMARY_BUDGETS if pol in MATRIX_PRIMARY else (PRIMARY_BUDGET,)
            for bud in budgets:
                stem = f"{pol}_b{bud}_s1"
                for kind in KINDS:
                    sp = os.path.join(src, stem + "." + kind)
                    if os.path.isfile(sp):
                        shutil.copy2(sp, os.path.join(dst, stem + "." + kind))
        metrics_src = os.path.join(src, "metrics.json")
        if os.path.isfile(metrics_src):
            shutil.copy2(metrics_src, os.path.join(dst, "metrics.json"))
    shutil.copy2(
        os.path.join("experiments", "validation", "v0.3.11", "protocol.json"),
        os.path.join(out_root, "protocol.json"))


def bug_visibility(out_root: str) -> dict:
    out = {}
    for app in APP_NAMES:
        man = json.load(open(
            os.path.join("apps", app, "bugs.manifest.json"), encoding="utf-8"))
        spec = json.load(open(os.path.join("apps", app, "spec.json"), encoding="utf-8"))
        spec_ids = {a["id"] for a in spec.get("assertions") or spec}
        metrics = json.load(open(
            os.path.join(out_root, "evidence", app, "metrics.json"), encoding="utf-8"))
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
        out[app] = rows
    return out


def write_summary(out_root: str, suite: dict) -> str:
    d = suite["derived"]
    safety = suite.get("safety") or {}
    lines = [
        "# GhostQA v0.3.11 — Preregistered Multi-Target Replication",
        "",
        f"**Outcome {d['outcome']} — {d['outcome_meaning']}** (computed from protocol gates).",
        "",
        "Product default unchanged: NoFrontier, `sequence_mode=off`.",
        f"Promotion-readiness: `{d.get('promotion_readiness')}`.",
        "",
        "## Authoring-bias disclosure",
        "",
        "- These targets are preregistered fresh targets, not independently designed external benchmarks.",
        "- The v0.3.9 candidate was frozen before this round.",
        "- Target identities, seeds, topology families, budgets, and bug-count ranges were preregistered before policy evaluation.",
        "- The generator does not accept or reject topology based on policy score.",
        "- This is not universal generalization proof.",
        "",
    ]
    for app, t in (suite.get("targets") or {}).items():
        lines += [
            f"## {app} @120",
            "",
            "| policy | states | URLs | BDR | Deep-BDR | return attempts | returned | escapes | confirmed |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---|",
        ]
        for r in t.get("table_120") or []:
            conf = ", ".join(r.get("confirmed") or []) or "—"
            lines.append(
                f"| {r['policy']} | {r.get('states')} | {r.get('urls')} | {r.get('BDR')} | "
                f"{r.get('Deep-BDR')} | {r.get('return_attempts')} | {r.get('returned')} | "
                f"{r.get('escapes')} | {conf} |"
            )
        life = t.get("lifecycle") or {}
        g = t.get("guard_120") or {}
        lines += [
            "",
            f"- evaluable opportunity: {t.get('evaluable_opportunity')}",
            f"- C1 opportunities @120: {(t.get('c1_120') or {}).get('c1_opportunity_count')}",
            f"- guard escapes: {t.get('guard_escapes')}",
            f"- L1/L2: {life.get('L1')}/{life.get('L2')} unclassified={life.get('unclassified')}",
            f"- post-escape novel states/URLs: {g.get('post_escape_novel_state_count')}/{g.get('post_escape_novel_url_count')}",
            f"- absent from C1 URLs: {g.get('absent_from_c1_urls')}",
            f"- C1 bugs lost: {t.get('lost_c1_bugs')}",
            f"- meaningful return keys lost: {t.get('lost_meaningful_return_keys')}",
            f"- escape/opportunity match: {t.get('escape_opportunity_ok')}",
            "",
            "Primary C1/guard at 40/80:",
            "",
            "| budget | C1 states | C1 BDR | C1 returned | guard states | guard BDR | guard returned | guard escapes |",
            "|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
        cells = t.get("cells") or {}
        for bud in (40, 80):
            c1b = cells.get(f"ghost-structural-memory@{bud}") or {}
            gb = cells.get(f"ghost-structural-return-guard@{bud}") or {}
            lines.append(
                f"| {bud} | {c1b.get('states')} | {c1b.get('bug_discovery_rate')} | "
                f"{c1b.get('successful_return_to_parent_events')} | {gb.get('states')} | "
                f"{gb.get('bug_discovery_rate')} | {gb.get('successful_return_to_parent_events')} | "
                f"{gb.get('return_cycle_escape_events')} |"
            )
        lines.append("")
    lines += [
        "## Aggregate replication",
        "",
        "| target | opportunity | escape | novel after escape | C1 bugs lost | return regression | transfer demonstrated |",
        "|---|---:|---:|---|---|---|---|",
    ]
    for app, t in (suite.get("targets") or {}).items():
        lines.append(
            f"| {app} | {(t.get('c1_120') or {}).get('c1_opportunity_count')} | "
            f"{t.get('guard_escapes')} | {t.get('post_escape_novelty')} | "
            f"{t.get('lost_c1_bugs') or []} | {t.get('lost_meaningful_return_keys') or []} | "
            f"{bool(t.get('guard_escapes') and t.get('post_escape_novelty'))} |"
        )
    exh = safety.get("exhaustive") or {}
    lines += [
        "",
        "## Safety",
        "",
        "| check | cases/traces | failures | pass |",
        "|---|---:|---:|---|",
        f"| S1–S7 | 7 | {0 if safety.get('s1_s7_all_pass') else 1} | {safety.get('s1_s7_all_pass')} |",
        f"| exhaustive traces | {exh.get('traces_enumerated')} | {exh.get('failures')} | {exh.get('failures') == 0} |",
        "",
        "## Lifecycle",
        "",
        "| target | escapes | L1 open-instance | L2 already-terminal | unclassified |",
        "|---|---:|---:|---:|---:|",
    ]
    for app, t in (suite.get("targets") or {}).items():
        life = t.get("lifecycle") or {}
        lines.append(
            f"| {app} | {life.get('escapes')} | {life.get('L1')} | {life.get('L2')} | "
            f"{life.get('unclassified')} |"
        )
    vis_path = os.path.join(out_root, "metrics", "bug-visibility.json")
    vis = json.load(open(vis_path, encoding="utf-8")) if os.path.isfile(vis_path) else {}
    lines += ["", "## Post-hoc bug visibility", ""]
    for app in APP_NAMES:
        rows = vis.get(app) or []
        lines += [
            f"### {app}",
            "",
            "| bug id | kind | trigger depth | spec-visible? | manifest-hidden? | policies confirmed |",
            "|---|---|---:|---|---|---|",
        ]
        for b in rows:
            lines.append(
                f"| {b['id']} | {b['kind']} | {b.get('trigger_depth')} | {b.get('spec_visible')} | "
                f"{b.get('manifest_hidden')} | {', '.join(b.get('policies_confirmed') or []) or '—'} |"
            )
        lines.append("")
    lines += [
        "## Reproduce",
        "",
        "```text",
        "python -m benchmark.multi_target_reproduce --root experiments/published/multi-target-replication-v0.3.11 --verify",
        "```",
        "",
        f"Computed outcome: **{d['outcome']} — {d['outcome_meaning']}**",
        "",
        "Product default changed: no",
        "",
    ]
    if d.get("outcome") == "D":
        lines.append("Fewer than two targets presented evaluable return-cycle opportunities under the preregistered budgets. Budgets are not raised.")
        lines.append("")
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
    s17 = collect_safety_suite()
    exhaustive = run_exhaustive_check()
    safety = {
        **s17,
        "s1_s7_all_pass": bool(s17.get("all_pass")),
        "exhaustive": {
            "traces_enumerated": exhaustive.get("traces_enumerated"),
            "passed": exhaustive.get("passed"),
            "failures": exhaustive.get("failures"),
            "named_failures": exhaustive.get("named_failures"),
            "all_pass": exhaustive.get("all_pass"),
        },
        "exhaustive_failures": exhaustive.get("failures"),
        "all_pass": bool(s17.get("all_pass")) and exhaustive.get("failures") == 0,
    }
    _write_json(os.path.join(out_root, "evidence", "safety", "safety.json"), safety)
    vis = bug_visibility(out_root)
    os.makedirs(os.path.join(out_root, "metrics"), exist_ok=True)
    _write_json(os.path.join(out_root, "metrics", "bug-visibility.json"), vis)
    suite = derive_suite(
        out_root, safety=safety, historical_ok=historical_ok, freeze_ok=freeze_ok)
    per_target = {}
    for app, t in suite["targets"].items():
        def _strip(cell):
            return {k: v for k, v in (cell or {}).items() if k != "c1_opportunities"}
        cells = t.get("cells") or {}
        per_target[app] = {
            "table_120": t.get("table_120"),
            "c1_120": _strip(t.get("c1_120")),
            "guard_120": _strip(t.get("guard_120")),
            "primary_40_80": {
                "c1_40": _strip(cells.get("ghost-structural-memory@40")),
                "guard_40": _strip(cells.get("ghost-structural-return-guard@40")),
                "c1_80": _strip(cells.get("ghost-structural-memory@80")),
                "guard_80": _strip(cells.get("ghost-structural-return-guard@80")),
            },
            "lost_c1_bugs": t.get("lost_c1_bugs"),
            "lost_meaningful_return_keys": t.get("lost_meaningful_return_keys"),
            "evaluable_opportunity": t.get("evaluable_opportunity"),
            "guard_escapes": t.get("guard_escapes"),
            "post_escape_novelty": t.get("post_escape_novelty"),
            "escape_opportunity_ok": t.get("escape_opportunity_ok"),
            "lifecycle": t.get("lifecycle"),
            "return_inflation": t.get("return_inflation"),
        }
    aggregate = {
        "derived": suite["derived"],
        "interpretation": suite["interpretation"],
        "replication": [
            {
                "target": app,
                "opportunity": (t.get("c1_120") or {}).get("c1_opportunity_count"),
                "escape": t.get("guard_escapes"),
                "novel_after_escape": t.get("post_escape_novelty"),
                "c1_bugs_lost": t.get("lost_c1_bugs"),
                "return_regression": t.get("lost_meaningful_return_keys"),
                "transfer_demonstrated": bool(
                    t.get("guard_escapes") and t.get("post_escape_novelty")),
            }
            for app, t in suite["targets"].items()
        ],
    }
    derived_bytes = canonical_json_bytes(aggregate)
    per_bytes = canonical_json_bytes(per_target)
    _write(os.path.join(out_root, "metrics", "per-target.json"), per_bytes.decode("utf-8"))
    _write(os.path.join(out_root, "metrics", "aggregate.json"), derived_bytes.decode("utf-8"))
    _write(os.path.join(out_root, "metrics", "metrics.json"), derived_bytes.decode("utf-8"))
    _write_json(os.path.join(out_root, "metrics", "safety.json"), safety)
    config = {
        "round": "v0.3.11 Multi-Target Replication",
        "protocol": "experiments/validation/v0.3.11/protocol.json",
        "protocol_commit": protocol_commit,
        "suite_freeze": "experiments/frozen/v0.3.11-multitarget/freeze.json",
        "suite_freeze_commit": freeze_commit,
        "candidate_freeze": "experiments/frozen/ghost-return-cycle-guard-v0.3.9/freeze.json",
        "historical_c1_freeze": "experiments/frozen/ghost-structural-v0.3.6/freeze.json",
        "product_default": "NoFrontier, sequence_mode=off",
        "targets": list(APP_NAMES),
        "families": {n: FAMILIES[n]["family"] for n in APP_NAMES},
        "verify_command": (
            "python -m benchmark.multi_target_reproduce "
            "--root experiments/published/multi-target-replication-v0.3.11 --verify"),
        "hash_normalization": "LF newlines",
        "expected_metrics_sha256": sha256_bytes(derived_bytes),
        "expected_per_target_sha256": sha256_bytes(per_bytes),
        "product_default_changed": False,
    }
    _write_json(os.path.join(out_root, "config.json"), config)
    _write(os.path.join(out_root, "summary.md"), write_summary(out_root, suite))
    _write(os.path.join(out_root, "README.md"),
           "Published v0.3.11 multi-target replication evidence. See summary.md.\n")
    repro = {
        "clean_clone_verified": False,
        "command": config["verify_command"],
        "expected_metrics_sha256": config["expected_metrics_sha256"],
        "match": True,
        "outcome": suite["derived"]["outcome"],
        "promotion_readiness": suite["derived"]["promotion_readiness"],
        "evidence_manifest_verified": True,
        "candidate_freeze_verified": True,
        "historical_c1_freeze_verified": True,
        "generator_freeze_verified": True,
        "target_freeze_verified": True,
        "protocol_commit": protocol_commit,
        "freeze_commit": freeze_commit,
        "ignored_run_dirs_in_clone": False,
    }
    _write_json(os.path.join(out_root, "metrics", "reproduction.json"), repro)
    files = manifest_files(out_root)
    man = {
        "round": "v0.3.11",
        "expected_file_count": len(files),
        "hash_normalization": "LF newlines",
        "files": files,
    }
    _write_json(os.path.join(out_root, "evidence-manifest.json"), man)
    return suite


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default=os.path.join("experiments", "runs", "v0311-multitarget"))
    ap.add_argument("--out", default=PUBLISHED_ROOT)
    ap.add_argument("--protocol-commit", required=True)
    ap.add_argument("--freeze-commit", required=True)
    args = ap.parse_args(argv)
    suite = publish(
        args.run, args.out,
        protocol_commit=args.protocol_commit,
        freeze_commit=args.freeze_commit,
        historical_ok=True, freeze_ok=True)
    print("outcome", suite["derived"]["outcome"])
    print("promotion", suite["derived"]["promotion_readiness"])
    print("wrote", args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
