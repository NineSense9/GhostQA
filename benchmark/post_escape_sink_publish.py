"""Publish the v0.3.22 post-escape diagnosis from frozen evidence.

Does not choose actions and does not alter the candidate or targets.
"""
from __future__ import annotations

import os
import shutil

from benchmark.algorithm_freeze import sha256_file
from benchmark.post_escape_sink_analysis import (
    CELLS,
    CANDIDATE,
    DIAGNOSTIC_BUDGETS,
    HISTORICAL_BUDGET,
    POSITIVE_TARGETS,
    PUBLICATION_DIR,
    ROOT,
    RUN_DIR,
    SEED,
    STARTING_HEAD,
    VALIDATION_DIR,
    V0321_PUBLICATION,
    _write,
    analyze_cell,
    build_static_report,
    compare_prefix,
    derive_v0322_diagnosis,
    freeze_status,
    load_bundle,
    load_jsonl,
    public_copy,
)

EVIDENCE_FILES = (
    "config.json",
    "events.jsonl",
    "sequence_events.json",
    "summary.json",
    "graph.json",
    "DONE",
)


def _rel(*parts: str) -> str:
    return "/".join(parts)


def published_cell(dest: str, app: str, budget: int) -> str:
    return os.path.join(dest, "evidence", app, f"b{budget}")


def run_cell(run_root: str, app: str, budget: int) -> str:
    return os.path.join(run_root, f"{app}_b{budget}_s{SEED}")


def _copy_cell(src: str, dest: str) -> None:
    os.makedirs(dest, exist_ok=True)
    for name in EVIDENCE_FILES:
        source = os.path.join(src, name)
        if not os.path.isfile(source):
            raise SystemExit("missing diagnostic file " + source)
        shutil.copyfile(source, os.path.join(dest, name))


def _historical_events(app: str) -> list:
    stem = f"{CANDIDATE}_b{HISTORICAL_BUDGET}_s{SEED}"
    path = os.path.join(
        ROOT, V0321_PUBLICATION.replace("/", os.sep), "evidence", app, stem + ".events.jsonl")
    return load_jsonl(path)


def _bundle_from_dir(app: str, budget: int, directory: str) -> dict:
    from benchmark.post_escape_sink_analysis import _load
    return {
        "app": app,
        "budget": budget,
        "events": load_jsonl(os.path.join(directory, "events.jsonl")),
        "sequence": _load(os.path.join(directory, "sequence_events.json")),
        "summary": _load(os.path.join(directory, "summary.json")),
        "topology": _load(os.path.join(ROOT, "apps", app, "topology.json")),
    }


def measurement_rows(source: str, *, layout: str) -> list[dict]:
    rows = []
    for app in POSITIVE_TARGETS:
        historical = analyze_cell(load_bundle(app, HISTORICAL_BUDGET, historical=True))
        historical["trajectory_prefix_match"] = True
        historical["source"] = "v0.3.21-b120"
        rows.append(historical)
        historical_events = _historical_events(app)
        for budget in DIAGNOSTIC_BUDGETS:
            if layout == "runs":
                directory = run_cell(source, app, budget)
            else:
                directory = published_cell(source, app, budget)
            bundle = _bundle_from_dir(app, budget, directory)
            row = analyze_cell(bundle)
            row["trajectory_prefix_match"] = compare_prefix(historical_events, bundle["events"])
            row["source"] = f"v0.3.22-b{budget}"
            rows.append(row)
    return rows


def _cycle_fields(cycle: dict | None) -> dict:
    cycle = cycle or {}
    return {
        "sequence_instance_id": cycle.get("sequence_instance_id"),
        "branch_key": cycle.get("branch_key") or "",
        "branch_start_step": cycle.get("branch_start_step"),
        "horizon_step": cycle.get("horizon_step"),
        "return_attempt_count": cycle.get("return_attempt_count"),
        "return_cycle_escape_step": cycle.get("return_cycle_escape_step"),
        "terminal_step": cycle.get("terminal_step"),
        "terminal_outcome": cycle.get("terminal_outcome") or "",
        "active_same_sequence_afterward": bool(cycle.get("events_after_terminal")),
    }


def slim_row(row: dict) -> dict:
    static = row.get("static") or {}
    return {
        "app": row["app"],
        "budget": row["budget"],
        "source": row.get("source"),
        "first_waypoint_escape_step": row.get("first_waypoint_escape_step"),
        "waypoint_escape_count": row.get("waypoint_escape_count"),
        "second_waypoint_escape_count": row.get("second_waypoint_escape_count"),
        "template_589_recovered": row.get("template_589_recovered"),
        "template_lost": row.get("template_lost") or [],
        "template_first_confirm_step": row.get("template_first_confirm_step"),
        "all_guard_bugs_retained": row.get("all_guard_bugs_retained"),
        "post_abandon_step": row.get("post_abandon_step"),
        "sink_entry_step": row.get("sink_entry_step"),
        "suffix_steps": row.get("suffix_steps"),
        "suffix_unique_urls": row.get("suffix_unique_urls"),
        "suffix_unique_states": row.get("suffix_unique_states"),
        "dominant_scc_visit_count": row.get("dominant_scc_visit_count"),
        "dominant_scc_visit_fraction": row.get("dominant_scc_visit_fraction"),
        "dominant_edge": row.get("dominant_edge"),
        "dominant_edge_count": row.get("dominant_edge_count"),
        "dominant_edge_fraction": row.get("dominant_edge_fraction"),
        "repeated_edge_count": row.get("repeated_edge_count"),
        "no_new_url_streak_max": row.get("no_new_url_streak_max"),
        "no_new_state_streak_max": row.get("no_new_state_streak_max"),
        "entity_reentry_count_after_abandon": row.get("entity_reentry_count_after_abandon"),
        "entity_residual_action_count_after_abandon": row.get("entity_residual_action_count_after_abandon"),
        "productive_entity_reentry": row.get("productive_entity_reentry"),
        "productive_reentry_step": row.get("productive_reentry_step"),
        "second_useful_frontier": bool(
            (row.get("second_waypoint_escape_count") or 0) > 0
            or (row.get("entity_residual_action_count_after_abandon") or 0) > 0
        ),
        "final_quartile_same_scc": row.get("final_quartile_same_scc"),
        "final_quartile_idle_visit_fraction": row.get("final_quartile_idle_visit_fraction"),
        "active_sequence_after_abandonment": row.get("active_sequence_after_abandonment"),
        "new_branch_start_count_after_abandon": row.get("new_branch_start_count_after_abandon"),
        "sequence_scoped_return_cycle_after_escape": row.get("sequence_scoped_return_cycle_after_escape"),
        "abandoned_sequence_continues": row.get("abandoned_sequence_continues"),
        "trajectory_prefix_match": row.get("trajectory_prefix_match", True),
        "persistent_sink": row.get("persistent_sink"),
        "horizon_cycle": _cycle_fields(row.get("horizon_cycle")),
        "static_classification": static.get("classification"),
        "static_scc_size": static.get("scc_size"),
        "static_closed": static.get("closed"),
        "static_outgoing_edge_count": static.get("outgoing_edge_count"),
        "static_entity_reachable": static.get("entity_reachable"),
        "static_shortest_entity_path_length": static.get("shortest_entity_path_length"),
        "static_form_hub_edge_to_entity": static.get("form_hub_edge_to_entity"),
        "suffix_page_histogram": row.get("suffix_page_histogram") or [],
        "suffix_edge_histogram": row.get("suffix_edge_histogram") or [],
    }


def _by_app(rows: list[dict]) -> dict:
    grouped = {}
    for row in rows:
        grouped.setdefault(row["app"], {})[int(row["budget"])] = row
    return grouped


def _md_cell(value) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _next_question(conclusion: str) -> str:
    if conclusion == "persistent_post_terminal_sink":
        return (
            "Potential next research question: can ordinary no-active-sequence "
            "exploration detect repeated SCC/edge recurrence with no state or "
            "frontier progress and yield to a previously known global residual "
            "frontier without creating new sequence success?"
        )
    if conclusion == "budget_delay":
        return "The next question is budget allocation. A loop guard is not the indicated design."
    if conclusion == "mixed_or_inconclusive":
        return "The next question is a target-agnostic differential analysis of the split that remains."
    return "The next question is to repair the protocol failure before any new mechanism."


def _public_paragraph(derived: dict, grouped: dict) -> str:
    conclusion = derived["diagnostic_conclusion"]
    losers = derived["facts"].get("losing_targets") or []
    if conclusion in ("persistent_post_terminal_sink", "budget_delay") and losers == [
        "buggy-campus", "buggy-studio"
    ]:
        return public_copy(conclusion)
    if conclusion == "mixed_or_inconclusive":
        parts = []
        for app in POSITIVE_TARGETS:
            flags = [
                f"b{budget}={'recovered' if grouped[app][budget]['template_589_recovered'] else 'lost'}"
                for budget in (120, 240, 480)
            ]
            parts.append(app + " " + ", ".join(flags))
        detail = "; ".join(parts)
        reasons = ", ".join(derived["facts"].get("reasons") or []) or "no single mechanism"
        return (
            "v0.3.22 没有改策略。b240/b480 没有收敛到单一机制，诊断为 mixed_or_inconclusive"
            f"（{reasons}）。模板 5/8/9：{detail}。"
            "这不是新修复，也不是 fresh validation。"
        )
    return public_copy(conclusion)


def render_summary(slim_rows: list[dict], derived: dict) -> str:
    grouped = _by_app(slim_rows)
    conclusion = derived["diagnostic_conclusion"]
    lines = [
        f"# v0.3.22 diagnostic: {conclusion}",
        "",
        derived["meaning"],
        "",
        "This round only characterizes four frozen v0.3.20 positive targets, the frozen v0.3.21 candidate, and budgets up to 480. It does not establish universal web behavior, an infinite loop, production readiness, or default-policy readiness.",
        "",
        f"Product default changed: false. Promotion readiness: {derived['promotion_readiness']}.",
        "v0.3.21 candidate result remains Outcome C.",
        "",
        _public_paragraph(derived, grouped),
        "",
        _next_question(conclusion),
        "",
        "## Static topology",
        "",
        "| target | sink SCC size | closed | outgoing edges | entity reachable | shortest entity path |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for app in POSITIVE_TARGETS:
        row = grouped[app][480]
        lines.append(
            "| {app} | {size} | {closed} | {out} | {reach} | {path} |".format(
                app=app,
                size=_md_cell(row["static_scc_size"]),
                closed=_md_cell(row["static_closed"]),
                out=_md_cell(row["static_outgoing_edge_count"]),
                reach=_md_cell(row["static_entity_reachable"]),
                path=_md_cell(row["static_shortest_entity_path_length"]),
            )
        )
    lines.extend([
        "",
        "## Runtime",
        "",
        "| target | budget | abandon step | sink fraction | max no-new-state streak | entity reentry | residual action | template recovered |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ])
    for app in POSITIVE_TARGETS:
        for budget in (120, 240, 480):
            row = grouped[app][budget]
            lines.append(
                "| {app} | {budget} | {abandon} | {frac} | {streak} | {reentry} | {residual} | {recovered} |".format(
                    app=app,
                    budget=budget,
                    abandon=_md_cell(row["post_abandon_step"]),
                    frac=_md_cell(row["dominant_scc_visit_fraction"]),
                    streak=_md_cell(row["no_new_state_streak_max"]),
                    reentry=_md_cell(row["entity_reentry_count_after_abandon"]),
                    residual=_md_cell(row["entity_residual_action_count_after_abandon"]),
                    recovered=_md_cell(row["template_589_recovered"]),
                )
            )
    lines.extend([
        "",
        "## Sequence scope",
        "",
        "| target | horizon branch | horizon step | cycle escape step | terminal | active same sequence afterward |",
        "|---|---|---:|---:|---|---:|",
    ])
    for app in POSITIVE_TARGETS:
        cycle = grouped[app][120]["horizon_cycle"]
        lines.append(
            "| {app} | {branch} | {horizon} | {escape} | {terminal} | {active} |".format(
                app=app,
                branch=cycle.get("branch_key") or "",
                horizon=_md_cell(cycle.get("horizon_step")),
                escape=_md_cell(cycle.get("return_cycle_escape_step")),
                terminal=cycle.get("terminal_outcome") or "",
                active=_md_cell(cycle.get("active_same_sequence_afterward")),
            )
        )
    lines.extend([
        "",
        "Budget 240 and 480 use the same horizon-cycle rule. Their steps are in `metrics/per-target.json`.",
        "",
        "## Contrast",
        "",
        "| target | first waypoint escape | second useful waypoint/frontier | 5/8/9 recovered @120 | recovered @240 | recovered @480 |",
        "|---|---:|---:|---:|---:|---:|",
    ])
    for app in POSITIVE_TARGETS:
        lines.append(
            "| {app} | {first} | {second} | {b120} | {b240} | {b480} |".format(
                app=app,
                first=_md_cell(grouped[app][120]["first_waypoint_escape_step"]),
                second=_md_cell(grouped[app][480]["second_useful_frontier"]),
                b120=_md_cell(grouped[app][120]["template_589_recovered"]),
                b240=_md_cell(grouped[app][240]["template_589_recovered"]),
                b480=_md_cell(grouped[app][480]["template_589_recovered"]),
            )
        )
    lines.extend([
        "",
        f"diagnostic_conclusion: {conclusion}",
        "",
    ])
    return "\n".join(lines)


def build_payloads(source: str, *, layout: str) -> dict:
    status = freeze_status()
    semantic = bool(status["ok"] and not status["product_default_changed"])
    rows = measurement_rows(source, layout=layout)
    slim = [slim_row(row) for row in rows]
    derived = derive_v0322_diagnosis(
        slim, protocol_valid=semantic, semantic_unchanged=semantic)
    per_target = {"rows": slim}
    suffix = {
        "rows": [
            {
                "app": row["app"],
                "budget": row["budget"],
                "pages": row["suffix_page_histogram"],
                "edges": row["suffix_edge_histogram"],
                "dominant_edge": row["dominant_edge"],
                "dominant_edge_fraction": row["dominant_edge_fraction"],
                "repeated_edge_count": row["repeated_edge_count"],
                "no_new_url_streak_max": row["no_new_url_streak_max"],
                "no_new_state_streak_max": row["no_new_state_streak_max"],
            }
            for row in slim
        ]
    }
    static = build_static_report(rows)
    diagnostic = {
        "diagnostic_conclusion": derived["diagnostic_conclusion"],
        "meaning": derived["meaning"],
        "promotion_readiness": derived["promotion_readiness"],
        "product_default_changed": False,
        "fresh_validation": False,
        "facts": derived["facts"],
        "public_copy": _public_paragraph(derived, _by_app(slim)),
        "next_question": _next_question(derived["diagnostic_conclusion"]),
    }
    return {
        "rows": rows,
        "slim": slim,
        "derived": derived,
        "per_target": per_target,
        "suffix": suffix,
        "static": static,
        "diagnostic": diagnostic,
        "freeze": status,
        "summary": render_summary(slim, derived),
    }


def _manifest(dest: str) -> dict:
    files = []
    for dirpath, _dirnames, filenames in os.walk(dest):
        for name in sorted(filenames):
            if name == "evidence-manifest.json":
                continue
            full = os.path.join(dirpath, name)
            rel = os.path.relpath(full, dest).replace("\\", "/")
            files.append({"relative_path": rel, "sha256": sha256_file(full)})
    files.sort(key=lambda item: item["relative_path"])
    return {"files": files, "hash_normalization": "LF newlines"}


def write_publication(source: str, dest: str, *, layout: str = "runs") -> dict:
    payloads = build_payloads(source, layout=layout)
    if os.path.isdir(dest):
        shutil.rmtree(dest)
    os.makedirs(dest, exist_ok=True)
    if layout == "runs":
        for app, budget in CELLS:
            _copy_cell(run_cell(source, app, budget), published_cell(dest, app, budget))
    protocol_src = os.path.join(ROOT, VALIDATION_DIR.replace("/", os.sep), "protocol.json")
    audit_src = os.path.join(ROOT, VALIDATION_DIR.replace("/", os.sep), "v03121-post-escape-audit.json")
    shutil.copyfile(protocol_src, os.path.join(dest, "protocol.json"))
    shutil.copyfile(audit_src, os.path.join(dest, "v03121-post-escape-audit.json"))
    metrics = os.path.join(dest, "metrics")
    os.makedirs(metrics, exist_ok=True)
    _write(os.path.join(dest, "static-scc-analysis.json"), payloads["static"])
    _write(os.path.join(metrics, "per-target.json"), payloads["per_target"])
    _write(os.path.join(metrics, "suffix-recurrence.json"), payloads["suffix"])
    _write(os.path.join(metrics, "scc.json"), payloads["static"])
    _write(os.path.join(metrics, "budget-diagnostic.json"), payloads["diagnostic"])
    with open(os.path.join(dest, "summary.md"), "w", encoding="utf-8", newline="\n") as handle:
        handle.write(payloads["summary"])
    reproduction = {
        "clean_clone_verified": False,
        "verified_head": "",
        "product_default_changed": False,
        "starting_head": STARTING_HEAD,
        "preregistration_commit": "5edcc22700a38eff3e9099ff43f0f33959994030",
        "command": (
            "python -m benchmark.post_escape_sink_reproduce "
            "--root experiments/published/post-escape-sink-v0.3.22 --verify"
        ),
        "per_target_sha256": sha256_file(os.path.join(metrics, "per-target.json")),
        "suffix_recurrence_sha256": sha256_file(os.path.join(metrics, "suffix-recurrence.json")),
        "scc_sha256": sha256_file(os.path.join(metrics, "scc.json")),
        "budget_diagnostic_sha256": sha256_file(os.path.join(metrics, "budget-diagnostic.json")),
        "diagnostic_conclusion": payloads["derived"]["diagnostic_conclusion"],
    }
    _write(os.path.join(metrics, "reproduction.json"), reproduction)
    _write(os.path.join(dest, "config.json"), {
        "round": "v0.3.22",
        "kind": "diagnostic",
        "candidate": CANDIDATE,
        "candidate_freeze": "experiments/frozen/ghost-return-waypoint-frontier-v0.3.21/freeze.json",
        "diagnostic_conclusion": payloads["derived"]["diagnostic_conclusion"],
        "product_default_changed": False,
        "promotion_readiness": "not_ready",
        "fresh_validation": False,
        "cell_count": len(CELLS),
        "cells": [f"{app}@{budget}" for app, budget in CELLS],
        "historical_reference": "experiments/published/return-waypoint-frontier-v0.3.21",
        "starting_head": STARTING_HEAD,
        "preregistration_commit": reproduction["preregistration_commit"],
        "verify_command": reproduction["command"],
        "v0_3_21_outcome": "C",
    })
    _write(os.path.join(dest, "evidence-manifest.json"), _manifest(dest))
    return payloads


def main(argv=None) -> int:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", default=os.path.join(ROOT, RUN_DIR.replace("/", os.sep)))
    parser.add_argument("--dest", default=os.path.join(ROOT, PUBLICATION_DIR.replace("/", os.sep)))
    args = parser.parse_args(argv)
    payloads = write_publication(args.run_root, args.dest, layout="runs")
    print(payloads["derived"]["diagnostic_conclusion"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
