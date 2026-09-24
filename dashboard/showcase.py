"""Presentation-safe research payload for the dashboard.

Reads committed published artifacts only. Never invents numbers.
Does not import exploration runtime.
"""
from __future__ import annotations

import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PUBLISHED = os.path.join(ROOT, "experiments", "published")
V039 = os.path.join(PUBLISHED, "return-cycle-guard-v0.3.9")
V038 = os.path.join(PUBLISHED, "application-shape-v0.3.8")
V0310 = os.path.join(PUBLISHED, "fresh-transfer-v0.3.10")
V0311 = os.path.join(PUBLISHED, "multi-target-replication-v0.3.11")
V0312 = os.path.join(PUBLISHED, "nested-hub-parent-v0.3.12")
V0313 = os.path.join(PUBLISHED, "nested-stack-v0.3.13")
V0314 = os.path.join(PUBLISHED, "horizon-handoff-v0.3.14")
V0315 = os.path.join(PUBLISHED, "fresh-handoff-v0.3.15")
V0316 = os.path.join(PUBLISHED, "reentry-frontier-v0.3.16")
V0317 = os.path.join(PUBLISHED, "local-action-drain-v0.3.17")
V0318 = os.path.join(PUBLISHED, "return-entry-drain-v0.3.18")
V0319 = os.path.join(PUBLISHED, "finding-return-entry-v0.3.19")
V0320 = os.path.join(PUBLISHED, "fresh-composite-v0.3.20")
V0321 = os.path.join(PUBLISHED, "return-waypoint-frontier-v0.3.21")
V0322 = os.path.join(PUBLISHED, "post-escape-sink-v0.3.22")
V0323 = os.path.join(PUBLISHED, "residual-frontier-debt-v0.3.23")
V0324 = os.path.join(PUBLISHED, "episode-drain-epoch-v0.3.24")


def _load(path, default=None):
    if not os.path.isfile(path):
        return default
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return default


def _short_hash(h: str, head: int = 8, tail: int = 4) -> str:
    if not h:
        return ""
    if len(h) <= head + tail + 1:
        return h
    return f"{h[:head]}…{h[-tail:]}"


def _v039(root: str | None = None) -> dict:
    base = root or V039
    metrics = _load(os.path.join(base, "metrics", "metrics.json"))
    repro = _load(os.path.join(base, "metrics", "reproduction.json"))
    config = _load(os.path.join(base, "config.json"))
    man = _load(os.path.join(base, "evidence-manifest.json"))
    if not metrics:
        return {"available": False}
    shop = (metrics.get("observed") or {}).get("shop") or {}
    base_s = shop.get("baseline") or {}
    cand = shop.get("candidate") or {}
    derived = metrics.get("derived") or {}
    interp = metrics.get("interpretation") or {}
    deep = (metrics.get("observed") or {}).get("deepbench") or []
    deep120 = next(
        (r for r in deep
         if r.get("policy") == "ghost-structural-return-guard" and r.get("budget") == 120),
        {},
    )
    deep_c1 = next(
        (r for r in deep
         if r.get("policy") == "ghost-structural-memory" and r.get("budget") == 120),
        {},
    )
    n_files = len((man or {}).get("files") or [])
    return {
        "available": True,
        "round": "v0.3.9",
        "title": "Return-Cycle Guard",
        "outcome": derived.get("outcome"),
        "outcome_meaning": interp.get("outcome_meaning"),
        "product_default_changed": bool(interp.get("product_default_changed")),
        "generalization_claim": bool(interp.get("generalization_claim")),
        "inspected_case": True,
        "baseline": {
            "states": base_s.get("states"),
            "urls": base_s.get("n_urls"),
            "return_attempts": base_s.get("return_attempt_events"),
            "successful_return": base_s.get("successful_return_to_parent_events"),
            "confirmed": base_s.get("confirmed_bugs") or [],
        },
        "candidate": {
            "states": cand.get("states"),
            "urls": cand.get("n_urls"),
            "return_attempts": cand.get("return_attempt_events"),
            "successful_return": cand.get("successful_return_to_parent_events"),
            "cycle_escapes": cand.get("return_cycle_escape_events"),
            "post_escape_new_states": cand.get("post_escape_new_state_count"),
            "post_escape_new_urls": cand.get("post_escape_new_urls") or [],
            "escape_step": cand.get("escape_step"),
            "confirmed": cand.get("confirmed_bugs") or [],
        },
        "deepbench120": {
            "c1_confirmed": deep_c1.get("confirmed_bugs") or [],
            "guard_confirmed": deep120.get("confirmed_bugs") or [],
            "lost_from_baseline": derived.get("lost_from_baseline_120") or [],
            "guard_escapes": deep120.get("return_cycle_escape_events"),
            "depth": deep120.get("max_workflow_depth"),
        },
        "reproduction": {
            "clean_clone_verified": bool((repro or {}).get("clean_clone_verified")),
            "match": bool((repro or {}).get("match")),
            "command": (repro or {}).get("command") or (config or {}).get("verify_command"),
            "metrics_sha256": (repro or {}).get("expected_metrics_sha256"),
            "metrics_sha256_short": _short_hash((repro or {}).get("expected_metrics_sha256") or ""),
            "evidence_files": n_files,
            "candidate_freeze_verified": bool((repro or {}).get("candidate_freeze_verified")),
            "historical_c1_freeze_verified": bool(
                (repro or {}).get("historical_c1_freeze_verified")),
            "evidence_manifest_verified": bool(
                (repro or {}).get("evidence_manifest_verified")),
        },
        "product_default": (config or {}).get("product_default"),
        "command": (config or {}).get("verify_command") or (
            (repro or {}).get("command")),
    }


def _v038(root: str | None = None) -> dict:
    base = root or V038
    collapse = _load(os.path.join(base, "metrics", "shop-collapse.json"))
    repro = _load(os.path.join(base, "metrics", "reproduction.json"))
    config = _load(os.path.join(base, "config.json"))
    man = _load(os.path.join(base, "evidence-manifest.json"))
    if not collapse:
        return {"available": False}
    obs = collapse.get("observed") or {}
    c1 = obs.get("ghost-structural-memory") or {}
    interp = collapse.get("interpretation") or {}
    n_files = len((man or {}).get("files") or [])
    cmd = (repro or {}).get("command") or (config or {}).get("verify_command")
    return {
        "available": True,
        "round": "v0.3.8",
        "title": "Application-shape analysis",
        "root_cause": interp.get("primary_failure_class"),
        "c1": {
            "states": c1.get("n_states") or c1.get("states"),
            "urls": c1.get("n_urls"),
            "return_attempts": c1.get("return_attempt_events"),
            "successful_return": c1.get("successful_return_to_parent_events"),
        },
        "reproduction": {
            "clean_clone_verified": bool((repro or {}).get("clean_clone_verified")),
            "match": bool((repro or {}).get("match")),
            "command": cmd,
            "analysis_sha256": (repro or {}).get("expected_analysis_sha256"),
            "analysis_sha256_short": _short_hash(
                (repro or {}).get("expected_analysis_sha256") or ""),
            "evidence_files": n_files,
            "evidence_manifest_verified": bool(
                (repro or {}).get("evidence_manifest_verified")),
        },
        "command": cmd,
    }


def _v0310(root: str | None = None) -> dict:
    base = root or V0310
    metrics = _load(os.path.join(base, "metrics", "metrics.json"))
    repro = _load(os.path.join(base, "metrics", "reproduction.json"))
    config = _load(os.path.join(base, "config.json"))
    man = _load(os.path.join(base, "evidence-manifest.json"))
    if not metrics:
        return {"available": False}
    derived = metrics.get("derived") or {}
    interp = metrics.get("interpretation") or {}
    c1 = metrics.get("c1_120") or {}
    guard = metrics.get("guard_120") or {}
    safety = metrics.get("safety") or {}
    table = (metrics.get("observed") or {}).get("table_120") or []
    n_files = len((man or {}).get("files") or [])
    return {
        "available": True,
        "round": "v0.3.10",
        "title": "Fresh Cross-App Transfer",
        "outcome": derived.get("outcome"),
        "outcome_meaning": interp.get("outcome_meaning") or derived.get("outcome_meaning"),
        "target": "buggy-desk",
        "candidate": "ghost-structural-return-guard",
        "product_default_changed": bool(interp.get("product_default_changed")),
        "generalization_claim": bool(interp.get("generalization_claim")),
        "scope": interp.get("scope"),
        "baseline": {
            "states": c1.get("states"),
            "urls": c1.get("normalized_unique_urls"),
            "return_attempts": c1.get("return_attempt_events"),
            "successful_return": c1.get("successful_return_to_parent_events"),
            "opportunities": c1.get("c1_opportunity_count"),
            "confirmed": c1.get("confirmed_bugs") or [],
        },
        "candidate_run": {
            "states": guard.get("states"),
            "urls": guard.get("normalized_unique_urls"),
            "return_attempts": guard.get("return_attempt_events"),
            "successful_return": guard.get("successful_return_to_parent_events"),
            "cycle_escapes": guard.get("return_cycle_escape_events"),
            "post_escape_new_states": guard.get("post_escape_novel_state_count"),
            "post_escape_new_urls": guard.get("post_escape_novel_urls") or [],
            "absent_from_c1_urls": guard.get("absent_from_c1_urls") or [],
            "escape_step": guard.get("first_escape_step"),
            "confirmed": guard.get("confirmed_bugs") or [],
            "bdr": guard.get("bug_discovery_rate"),
            "deep_bdr": guard.get("deep_bug_discovery_rate"),
        },
        "safety": {
            "all_pass": bool(safety.get("all_pass")),
            "s1_escapes": safety.get("s1_escapes"),
            "s2_escapes": safety.get("s2_escapes"),
            "s3_escapes": safety.get("s3_escapes"),
            "s4_escapes": safety.get("s4_escapes"),
            "s5_escapes": safety.get("s5_escapes"),
        },
        "table_120": table,
        "lost_c1_confirmed": derived.get("lost_c1_confirmed") or [],
        "reproduction": {
            "clean_clone_verified": bool((repro or {}).get("clean_clone_verified")),
            "match": bool((repro or {}).get("match")),
            "command": (repro or {}).get("command") or (config or {}).get("verify_command"),
            "metrics_sha256": (repro or {}).get("expected_metrics_sha256"),
            "metrics_sha256_short": _short_hash(
                (repro or {}).get("expected_metrics_sha256") or ""),
            "evidence_files": n_files,
            "candidate_freeze_verified": bool((repro or {}).get("candidate_freeze_verified")),
            "historical_c1_freeze_verified": bool(
                (repro or {}).get("historical_c1_freeze_verified")),
            "target_freeze_verified": bool((repro or {}).get("target_freeze_verified")),
            "evidence_manifest_verified": bool(
                (repro or {}).get("evidence_manifest_verified")),
        },
        "product_default": (config or {}).get("product_default"),
        "command": (config or {}).get("verify_command") or (
            (repro or {}).get("command")),
    }


def _v0311(root: str | None = None) -> dict:
    base = root or V0311
    metrics = _load(os.path.join(base, "metrics", "metrics.json"))
    repro = _load(os.path.join(base, "metrics", "reproduction.json"))
    config = _load(os.path.join(base, "config.json"))
    man = _load(os.path.join(base, "evidence-manifest.json"))
    per = _load(os.path.join(base, "metrics", "per-target.json"))
    safety = _load(os.path.join(base, "metrics", "safety.json"))
    if not metrics:
        return {"available": False}
    derived = metrics.get("derived") or {}
    interp = metrics.get("interpretation") or {}
    replication = metrics.get("replication") or []
    n_files = len((man or {}).get("files") or [])
    targets = []
    for row in replication:
        name = row.get("target")
        cell = (per or {}).get(name) or {}
        c1 = cell.get("c1_120") or {}
        guard = cell.get("guard_120") or {}
        life = cell.get("lifecycle") or {}
        targets.append({
            "name": name,
            "c1_states": c1.get("states"),
            "guard_states": guard.get("states"),
            "c1_urls": c1.get("normalized_unique_urls"),
            "guard_urls": guard.get("normalized_unique_urls"),
            "opportunity": row.get("opportunity"),
            "escape": row.get("escape"),
            "novel_after_escape": row.get("novel_after_escape"),
            "c1_bugs_lost": row.get("c1_bugs_lost") or [],
            "transfer_demonstrated": bool(row.get("transfer_demonstrated")),
            "L1": life.get("L1"),
            "L2": life.get("L2"),
            "unclassified": life.get("unclassified"),
            "confirmed": guard.get("confirmed_bugs") or [],
        })
    exh = (safety or {}).get("exhaustive") or {}
    return {
        "available": True,
        "round": "v0.3.11",
        "title": "Preregistered Multi-Target Replication",
        "outcome": derived.get("outcome"),
        "outcome_meaning": interp.get("outcome_meaning") or derived.get("outcome_meaning"),
        "promotion_readiness": derived.get("promotion_readiness"),
        "product_default_changed": bool(
            interp.get("product_default_changed", derived.get("product_default_changed"))),
        "generalization_claim": bool(interp.get("generalization_claim")),
        "scope": interp.get("scope"),
        "targets": targets,
        "evaluable_targets": derived.get("evaluable_targets"),
        "transfer_targets": derived.get("transfer_targets"),
        "exhaustive_traces": exh.get("traces_enumerated"),
        "exhaustive_failures": exh.get("failures"),
        "s1_s7_pass": bool((safety or {}).get("s1_s7_all_pass", (safety or {}).get("all_pass"))),
        "reproduction": {
            "clean_clone_verified": bool((repro or {}).get("clean_clone_verified")),
            "match": bool((repro or {}).get("match")),
            "command": (repro or {}).get("command") or (config or {}).get("verify_command"),
            "metrics_sha256": (repro or {}).get("expected_metrics_sha256"),
            "metrics_sha256_short": _short_hash((repro or {}).get("expected_metrics_sha256") or ""),
            "evidence_files": n_files,
            "candidate_freeze_verified": bool((repro or {}).get("candidate_freeze_verified")),
            "historical_c1_freeze_verified": bool(
                (repro or {}).get("historical_c1_freeze_verified")),
            "target_freeze_verified": bool((repro or {}).get("target_freeze_verified")),
            "generator_freeze_verified": bool((repro or {}).get("generator_freeze_verified")),
            "evidence_manifest_verified": bool(
                (repro or {}).get("evidence_manifest_verified")),
        },
        "product_default": (config or {}).get("product_default"),
        "command": (config or {}).get("verify_command") or (
            (repro or {}).get("command")),
    }


def _v0312(root: str | None = None) -> dict:
    base = root or V0312
    mechanism = _load(os.path.join(base, "metrics", "mechanism.json"))
    regression = _load(os.path.join(base, "metrics", "regression.json"))
    safety = _load(os.path.join(base, "metrics", "safety.json"))
    repro = _load(os.path.join(base, "metrics", "reproduction.json"))
    config = _load(os.path.join(base, "config.json"))
    man = _load(os.path.join(base, "evidence-manifest.json"))
    if not mechanism:
        return {"available": False}
    derived = mechanism.get("derived") or {}
    targets = []
    for name in ("buggy-crm", "buggy-ops"):
        block = (mechanism.get("targets") or {}).get(name) or {}
        cells = block.get("cells") or {}
        guard = cells.get("ghost-structural-return-guard@120") or {}
        nested = cells.get("ghost-structural-nested-return-guard@120") or {}
        targets.append({
            "name": name,
            "guard_states": guard.get("states"),
            "guard_urls": guard.get("normalized_unique_urls"),
            "guard_lost_parent": guard.get("sequence_lost_parent"),
            "guard_return_attempts": guard.get("return_attempt_events"),
            "nested_states": nested.get("states"),
            "nested_urls": nested.get("normalized_unique_urls"),
            "nested_lost_parent": nested.get("sequence_lost_parent"),
            "nested_followup": nested.get("nested_branch_followup_events"),
            "nested_horizon": nested.get("sequence_horizon_reached"),
            "nested_return_attempts": nested.get("return_attempt_events"),
            "nested_returned": nested.get("sequence_instances_returned"),
            "nested_escapes": nested.get("return_cycle_escape_events"),
            "confirmed": nested.get("confirmed_bugs") or [],
            "repair": bool((block.get("assessment_120") or {}).get("mechanism_repair")),
        })
    lost = {}
    for key, case in ((regression or {}).get("cases") or {}).items():
        lost[key] = case.get("lost") or []
    n_files = len((man or {}).get("files") or [])
    return {
        "available": True,
        "round": "v0.3.12",
        "title": "Nested-Hub Parent Preservation",
        "outcome": derived.get("outcome"),
        "outcome_meaning": derived.get("outcome_meaning"),
        "product_default_changed": bool(derived.get("product_default_changed")),
        "generalization_claim": bool(derived.get("generalization_claim")),
        "crm_repair": bool(derived.get("crm_repair")),
        "ops_repair": bool(derived.get("ops_repair")),
        "lost_confirmed_cases": derived.get("lost_confirmed_cases") or [],
        "lost": lost,
        "targets": targets,
        "n_series_cases": (safety or {}).get("n_series_cases"),
        "n_series_failures": (safety or {}).get("n_series_failures"),
        "s1_s7_cases": (safety or {}).get("s1_s7_cases"),
        "s1_s7_failures": (safety or {}).get("s1_s7_failures"),
        "exhaustive_traces": (safety or {}).get("exhaustive_traces"),
        "exhaustive_failures": (safety or {}).get("exhaustive_candidate_failures"),
        "reproduction": {
            "clean_clone_verified": bool((repro or {}).get("clean_clone_verified")),
            "match": bool((repro or {}).get("match")),
            "command": (repro or {}).get("command") or (config or {}).get("verify_command"),
            "metrics_sha256": (repro or {}).get("expected_mechanism_sha256"),
            "metrics_sha256_short": _short_hash(
                (repro or {}).get("expected_mechanism_sha256") or ""),
            "evidence_files": n_files,
            "candidate_freeze_verified": bool((repro or {}).get("candidate_freeze_verified")),
            "historical_c1_freeze_verified": bool(
                (repro or {}).get("historical_c1_freeze_verified")),
            "historical_guard_freeze_verified": bool(
                (repro or {}).get("historical_guard_freeze_verified")),
            "target_freeze_verified": bool((repro or {}).get("target_freeze_verified")),
            "evidence_manifest_verified": bool(
                (repro or {}).get("evidence_manifest_verified")),
        },
        "product_default": (config or {}).get("product_default"),
        "command": (config or {}).get("verify_command") or (
            (repro or {}).get("command")),
    }


def _v0313(root: str | None = None) -> dict:
    base = root or V0313
    mechanism = _load(os.path.join(base, "metrics", "mechanism.json"))
    regression = _load(os.path.join(base, "metrics", "regression.json"))
    safety = _load(os.path.join(base, "metrics", "stack-safety.json"))
    repro = _load(os.path.join(base, "metrics", "reproduction.json"))
    config = _load(os.path.join(base, "config.json"))
    man = _load(os.path.join(base, "evidence-manifest.json"))
    if not mechanism:
        return {"available": False}
    derived = mechanism.get("derived") or {}
    audit = mechanism.get("stack_audit") or {}
    targets = []
    for name in ("buggy-crm", "buggy-ops"):
        block = (mechanism.get("targets") or {}).get(name) or {}
        cells = block.get("cells") or {}
        guard = cells.get("ghost-structural-return-guard@120") or {}
        flat = cells.get("ghost-structural-nested-return-guard@120") or {}
        stack = cells.get("ghost-structural-nested-stack-guard@120") or {}
        targets.append({
            "name": name,
            "guard_states": guard.get("states"),
            "guard_urls": guard.get("normalized_unique_urls"),
            "guard_lost_parent": guard.get("sequence_lost_parent"),
            "flat_states": flat.get("states"),
            "flat_urls": flat.get("normalized_unique_urls"),
            "flat_lost_parent": flat.get("sequence_lost_parent"),
            "stack_states": stack.get("states"),
            "stack_urls": stack.get("normalized_unique_urls"),
            "stack_lost_parent": stack.get("sequence_lost_parent"),
            "stack_pushes": stack.get("suspended_frame_push_events"),
            "stack_resumes": stack.get("suspended_frame_resume_events"),
            "stack_depth": stack.get("max_suspended_stack_depth"),
            "stack_horizon": stack.get("sequence_horizon_reached"),
            "stack_returns": stack.get("sequence_instances_returned"),
            "repair": bool((block.get("assessment_120") or {}).get("pass")),
        })
    lost = {}
    confirmed = {}
    for key, case in ((regression or {}).get("cases") or {}).items():
        lost[key] = case.get("lost_vs_guard") or []
        confirmed[key] = case.get("stack_confirmed") or []
    return {
        "available": True,
        "round": "v0.3.13",
        "title": "Suspended Parent Frames",
        "outcome": derived.get("outcome"),
        "outcome_meaning": derived.get("outcome_meaning"),
        "product_default_changed": bool(derived.get("product_default_changed")),
        "generalization_claim": bool(derived.get("generalization_claim")),
        "crm_repair": bool(derived.get("crm_repair")),
        "ops_repair": bool(derived.get("ops_repair")),
        "lost_cases": derived.get("lost_cases") or [],
        "additional_lost": derived.get("additional_lost") or {},
        "lost": lost,
        "stack_confirmed": confirmed,
        "targets": targets,
        "p_series_cases": (safety or {}).get("p_series_cases"),
        "p_series_failures": (safety or {}).get("p_series_failures"),
        "s1_s7_cases": (safety or {}).get("s1_s7_cases"),
        "s1_s7_failures": (safety or {}).get("s1_s7_failures"),
        "exhaustive_traces": (safety or {}).get("exhaustive_traces"),
        "exhaustive_failures": (safety or {}).get("exhaustive_failures"),
        "terminal_accounting_violations": audit.get("terminal_accounting_violations"),
        "restore_without_child_return": bool(audit.get("restore_without_child_return")),
        "stack_frame_corruption": bool(audit.get("stack_frame_corruption")),
        "return_inflation": bool(audit.get("return_inflation")),
        "reproduction": {
            "clean_clone_verified": bool((repro or {}).get("clean_clone_verified")),
            "match": bool((repro or {}).get("match")),
            "command": (repro or {}).get("command") or (config or {}).get("verify_command"),
            "metrics_sha256": (repro or {}).get("expected_mechanism_sha256"),
            "metrics_sha256_short": _short_hash(
                (repro or {}).get("expected_mechanism_sha256") or ""),
            "evidence_files": len((man or {}).get("files") or []),
            "candidate_freeze_verified": bool((repro or {}).get("candidate_freeze_verified")),
            "historical_guard_freeze_verified": bool(
                (repro or {}).get("historical_guard_freeze_verified")),
            "evidence_manifest_verified": bool(
                (repro or {}).get("evidence_manifest_verified")),
        },
        "product_default": (config or {}).get("product_default"),
        "command": (config or {}).get("verify_command") or (
            (repro or {}).get("command")),
    }


def _v0314(root: str | None = None) -> dict:
    base = root or V0314
    mechanism = _load(os.path.join(base, "metrics", "mechanism.json"))
    regression = _load(os.path.join(base, "metrics", "regression.json"))
    safety = _load(os.path.join(base, "metrics", "safety.json"))
    repro = _load(os.path.join(base, "metrics", "reproduction.json"))
    config = _load(os.path.join(base, "config.json"))
    man = _load(os.path.join(base, "evidence-manifest.json"))
    reaudit = _load(os.path.join(base, "v0313-restore-reaudit.json"))
    if not mechanism:
        return {"available": False}
    derived = mechanism.get("derived") or {}
    targets = []
    for name in ("buggy-crm", "buggy-ops"):
        block = (mechanism.get("targets") or {}).get(name) or {}
        cell = ((block.get("cells") or {}).get(
            "ghost-structural-horizon-handoff-guard@120") or {})
        guard = ((block.get("history_120") or {}).get("guard") or {})
        targets.append({
            "name": name,
            "guard_states": guard.get("states"),
            "guard_urls": guard.get("normalized_unique_urls"),
            "states": cell.get("states"),
            "urls": cell.get("normalized_unique_urls"),
            "continuations": cell.get("nested_continuation_events"),
            "handoffs": cell.get("horizon_handoff_started_events"),
            "witnesses": cell.get("child_parent_witness_events"),
            "resumes": cell.get("parent_frame_resume_to_return_events"),
            "unwinds": cell.get("horizon_handoff_unwind_events"),
            "max_depth": cell.get("max_handoff_stack_depth"),
            "horizon": cell.get("sequence_horizon_reached"),
            "returns": cell.get("sequence_instances_returned"),
            "repair": bool((block.get("assessment_120") or {}).get("pass")),
        })
    lost = {}
    for key, case in ((regression or {}).get("cases") or {}).items():
        lost[key] = case.get("lost_vs_guard") or []
    apps = (reaudit or {}).get("apps") or {}
    gate = (reaudit or {}).get("counterfactual_gate") or {}
    return {
        "available": True,
        "round": "v0.3.14",
        "title": "Horizon Handoff",
        "outcome": derived.get("outcome"),
        "outcome_meaning": derived.get("outcome_meaning"),
        "product_default_changed": bool(derived.get("product_default_changed")),
        "generalization_claim": bool(derived.get("generalization_claim")),
        "crm_repair": bool(derived.get("crm_repair")),
        "ops_repair": bool(derived.get("ops_repair")),
        "lost_cases": derived.get("lost_cases") or [],
        "lost": lost,
        "lost_count": sum(len(items or []) for items in lost.values()),
        "witness_violations": mechanism.get("witness_violations"),
        "terminal_accounting_violations": mechanism.get(
            "terminal_accounting_violations"),
        "targets": targets,
        "h_series_cases": (safety or {}).get("h_series_cases"),
        "h_series_failures": (safety or {}).get("h_series_failures"),
        "model_raw_traces": (safety or {}).get("model_raw_traces"),
        "model_invariant_failures": (safety or {}).get("model_invariant_failures"),
        "reaudit": {
            "published_outcome": (reaudit or {}).get("v0313_published_outcome"),
            "counterfactual_outcome": gate.get("counterfactual_outcome"),
            "desk_old_bad": ((apps.get("buggy-desk") or {}).get(
                "old_bad_restore_count")),
            "desk_residual": ((apps.get("buggy-desk") or {}).get(
                "corrected_residual_bad_count")),
            "deep_old_bad": ((apps.get("deepbench") or {}).get(
                "old_bad_restore_count")),
            "deep_residual": ((apps.get("deepbench") or {}).get(
                "corrected_residual_bad_count")),
        },
        "reproduction": {
            "clean_clone_verified": bool((repro or {}).get("clean_clone_verified")),
            "match": bool((repro or {}).get("match")),
            "command": (repro or {}).get("command") or (config or {}).get("verify_command"),
            "metrics_sha256": (repro or {}).get("expected_mechanism_sha256"),
            "metrics_sha256_short": _short_hash(
                (repro or {}).get("expected_mechanism_sha256") or ""),
            "evidence_files": len((man or {}).get("files") or []),
            "candidate_freeze_verified": bool((repro or {}).get("candidate_freeze_verified")),
            "historical_guard_freeze_verified": bool(
                (repro or {}).get("historical_guard_freeze_verified")),
            "evidence_manifest_verified": bool(
                (repro or {}).get("evidence_manifest_verified")),
        },
        "product_default": (config or {}).get("product_default"),
        "command": (config or {}).get("verify_command") or (
            (repro or {}).get("command")),
    }


def _v0315(root: str | None = None) -> dict:
    base = root or V0315
    aggregate = _load(os.path.join(base, "metrics", "aggregate.json"))
    control = _load(os.path.join(base, "metrics", "negative-control.json"))
    repro = _load(os.path.join(base, "metrics", "reproduction.json"))
    config = _load(os.path.join(base, "config.json"))
    man = _load(os.path.join(base, "evidence-manifest.json"))
    if not aggregate:
        return {"available": False}
    derived = aggregate.get("derived") or {}
    return {
        "available": True,
        "round": "v0.3.15",
        "title": "Fresh Handoff Validation",
        "outcome": derived.get("outcome"),
        "outcome_meaning": derived.get("outcome_meaning"),
        "evaluable_targets": aggregate.get("actual_evaluable_positive_targets"),
        "transfer_targets": aggregate.get("full_transfer_targets"),
        "static_positive_targets": aggregate.get("static_positive_targets"),
        "bug_loss_apps": aggregate.get("bug_loss_apps") or [],
        "bug_loss_count": len(aggregate.get("bug_loss_apps") or []),
        "negative_control_handoffs": aggregate.get("negative_control_handoffs"),
        "witness_violations": aggregate.get("witness_violations"),
        "terminal_accounting_violations": aggregate.get("terminal_accounting_violations"),
        "promotion_readiness": derived.get("promotion_readiness"),
        "product_default_changed": bool(derived.get("product_default_changed")),
        "generalization_claim": bool(derived.get("generalization_claim")),
        "lifecycle_equivalence": (control or {}).get("lifecycle_equivalence"),
        "reproduction": {
            "clean_clone_verified": bool((repro or {}).get("clean_clone_verified")),
            "command": (repro or {}).get("command") or (
                "python -m benchmark.fresh_handoff_reproduce "
                "--root experiments/published/fresh-handoff-v0.3.15 --verify"),
            "evidence_files": len((man or {}).get("files") or []),
            "verified_head": (repro or {}).get("verified_head"),
        },
        "product_default": (config or {}).get("product_default_changed"),
        "command": (
            "python -m benchmark.fresh_handoff_reproduce "
            "--root experiments/published/fresh-handoff-v0.3.15 --verify"),
    }


def _v0316(root: str | None = None) -> dict:
    base = root or V0316
    mechanism = _load(os.path.join(base, "metrics", "mechanism.json"))
    regression = _load(os.path.join(base, "metrics", "regression.json"))
    repro = _load(os.path.join(base, "metrics", "reproduction.json"))
    man = _load(os.path.join(base, "evidence-manifest.json"))
    if not mechanism:
        return {"available": False}
    derived = mechanism.get("derived") or {}
    fresh = mechanism.get("fresh") or {}
    directory = (fresh.get("buggy-directory") or {})
    lab = (fresh.get("buggy-lab") or {})
    drow = directory.get("candidate") or {}
    lrow = lab.get("candidate") or {}
    regression_loss = 0
    for block in ((regression or {}).get("historical") or {}).values():
        regression_loss += len(block.get("lost_vs_guard") or [])
    witness = 0
    terminal = 0
    for cell in (mechanism.get("cells") or {}).values():
        witness += int(cell.get("witness_violations") or 0)
        terminal += int(cell.get("terminal_accounting_violations") or 0)
    return {
        "available": True,
        "round": "v0.3.16",
        "title": "Early Parent Re-entry",
        "outcome": derived.get("outcome"),
        "outcome_meaning": derived.get("outcome_meaning"),
        "directory_handoffs_before": 2,
        "directory_handoffs": drow.get("horizon_handoff_started_events"),
        "directory_reentry": drow.get("early_parent_reentry_events"),
        "lab_lost_before": ["BUG-L1", "BUG-L10", "BUG-L8", "BUG-L9"],
        "lab_lost": lab.get("lost_vs_guard") or [],
        "lab_leases": lrow.get("local_frontier_lease_granted_events"),
        "lab_lease_actions": lrow.get("local_frontier_lease_action_events"),
        "historical_regression_loss": regression_loss,
        "witness_violations": witness,
        "terminal_accounting_violations": terminal,
        "promotion_readiness": derived.get("promotion_readiness"),
        "product_default_changed": bool(derived.get("product_default_changed")),
        "generalization_claim": False,
        "reproduction": {
            "clean_clone_verified": bool((repro or {}).get("clean_clone_verified")),
            "command": (repro or {}).get("command") or (
                "python -m benchmark.reentry_frontier_reproduce "
                "--root experiments/published/reentry-frontier-v0.3.16 --verify"),
            "evidence_files": len((man or {}).get("files") or []),
        },
        "command": (
            "python -m benchmark.reentry_frontier_reproduce "
            "--root experiments/published/reentry-frontier-v0.3.16 --verify"),
    }


def _v0317(root: str | None = None) -> dict:
    base = root or V0317
    mechanism = _load(os.path.join(base, "metrics", "mechanism.json"))
    regression = _load(os.path.join(base, "metrics", "regression.json"))
    repro = _load(os.path.join(base, "metrics", "reproduction.json"))
    man = _load(os.path.join(base, "evidence-manifest.json"))
    if not mechanism:
        return {"available": False}
    derived = mechanism.get("derived") or {}
    fresh = mechanism.get("fresh") or {}
    lab = fresh.get("buggy-lab") or {}
    directory = (fresh.get("buggy-directory") or {}).get("candidate") or {}
    row = lab.get("candidate") or {}
    guard = set(lab.get("guard_confirmed") or [])
    previous = set(lab.get("v0316_confirmed") or [])
    lost_before = sorted(guard - previous)
    regression_loss = 0
    for block in ((regression or {}).get("historical") or {}).values():
        regression_loss += len(block.get("lost_vs_guard") or [])
    return {
        "available": True,
        "round": "v0.3.17",
        "title": "Local Action Drain",
        "outcome": derived.get("outcome"),
        "outcome_meaning": derived.get("outcome_meaning"),
        "lab_lost_before": lost_before,
        "lab_lost": lab.get("lost_vs_guard") or [],
        "buttons_drained": row.get("local_action_keys_drained"),
        "promoted_children": row.get("local_action_promoted_to_child_events"),
        "directory_handoffs": directory.get("horizon_handoff_started_events"),
        "historical_regression_loss": regression_loss,
        "forum_full_transfer": bool(mechanism.get("forum_full_transfer")),
        "billing_full_transfer": bool(mechanism.get("billing_full_transfer")),
        "promotion_readiness": derived.get("promotion_readiness"),
        "product_default_changed": bool(derived.get("product_default_changed")),
        "generalization_claim": False,
        "scope": "inspected repair, not fresh validation",
        "reproduction": {
            "clean_clone_verified": bool((repro or {}).get("clean_clone_verified")),
            "command": (repro or {}).get("command") or (
                "python -m benchmark.local_action_drain_reproduce "
                "--root experiments/published/local-action-drain-v0.3.17 --verify"),
            "evidence_files": len((man or {}).get("files") or []),
        },
        "command": (
            "python -m benchmark.local_action_drain_reproduce "
            "--root experiments/published/local-action-drain-v0.3.17 --verify"),
    }


def _v0318(root: str | None = None) -> dict:
    base = root or V0318
    mechanism = _load(os.path.join(base, "metrics", "mechanism.json"))
    regression = _load(os.path.join(base, "metrics", "regression.json"))
    repro = _load(os.path.join(base, "metrics", "reproduction.json"))
    man = _load(os.path.join(base, "evidence-manifest.json"))
    if not mechanism:
        return {"available": False}
    derived = mechanism.get("derived") or {}
    fresh = mechanism.get("fresh") or {}
    lab = fresh.get("buggy-lab") or {}
    directory = (fresh.get("buggy-directory") or {}).get("candidate") or {}
    row = lab.get("candidate") or {}
    result = (mechanism.get("diagnosis") or {}).get("result") or {}
    previous = _load(os.path.join(V0317, "metrics", "mechanism.json")) or {}
    previous_lost = ((previous.get("fresh") or {}).get("buggy-lab") or {}).get("lost_vs_guard") or []
    regression_loss = []
    for block in ((regression or {}).get("historical") or {}).values():
        regression_loss.extend(block.get("lost_vs_guard") or [])
    return {
        "available": True,
        "round": "v0.3.18",
        "title": "Return-Phase Entry Drain",
        "outcome": derived.get("outcome"),
        "outcome_meaning": derived.get("outcome_meaning"),
        "lab_l9_before": "lost" if "BUG-L9" in previous_lost else "retained",
        "lab_l9_after": "lost" if "BUG-L9" in (lab.get("lost_vs_guard") or []) else "retained",
        "lab_lost": lab.get("lost_vs_guard") or [],
        "return_entry_drains": row.get("return_entry_drain_started_events"),
        "result_buttons_drained": list(result.get("selected_eids") or []),
        "directory_handoffs": directory.get("horizon_handoff_started_events"),
        "historical_regression_loss": regression_loss,
        "historical_regression_loss_count": len(regression_loss),
        "forum_full_transfer": bool(mechanism.get("forum_full_transfer")),
        "billing_full_transfer": bool(mechanism.get("billing_full_transfer")),
        "promotion_readiness": derived.get("promotion_readiness"),
        "product_default_changed": bool(derived.get("product_default_changed")),
        "generalization_claim": False,
        "fresh_validation": False,
        "scope": "inspected repair, not fresh validation",
        "reproduction": {
            "clean_clone_verified": bool((repro or {}).get("clean_clone_verified")),
            "command": (repro or {}).get("command") or (
                "python -m benchmark.return_entry_drain_reproduce "
                "--root experiments/published/return-entry-drain-v0.3.18 --verify"),
            "evidence_files": len((man or {}).get("files") or []),
        },
        "command": (
            "python -m benchmark.return_entry_drain_reproduce "
            "--root experiments/published/return-entry-drain-v0.3.18 --verify"),
    }


def _v0319(root: str | None = None) -> dict:
    base = root or V0319
    mechanism = _load(os.path.join(base, "metrics", "mechanism.json"))
    regression = _load(os.path.join(base, "metrics", "regression.json"))
    repro = _load(os.path.join(base, "metrics", "reproduction.json"))
    man = _load(os.path.join(base, "evidence-manifest.json"))
    if not mechanism:
        return {"available": False}
    derived = mechanism.get("derived") or {}
    fresh = mechanism.get("fresh") or {}
    lab = fresh.get("buggy-lab") or {}
    directory = (fresh.get("buggy-directory") or {}).get("candidate") or {}
    row = lab.get("candidate") or {}
    historical = (regression or {}).get("historical") or {}
    deep = historical.get("deepbench") or {}
    deep_row = deep.get("candidate") or {}
    deep_diag = mechanism.get("deep") or {}
    regression_loss = []
    for block in historical.values():
        regression_loss.extend(block.get("lost_vs_guard") or [])
    return {
        "available": True,
        "round": "v0.3.19",
        "title": "Finding-Gated Return-Entry Drain",
        "outcome": derived.get("outcome"),
        "outcome_meaning": derived.get("outcome_meaning"),
        "lab_lost": lab.get("lost_vs_guard") or [],
        "deep_lost": deep.get("lost_vs_guard") or [],
        "finding_drains": row.get("finding_return_entry_trigger_events"),
        "horizon_bypasses": deep_row.get("finding_return_entry_horizon_bypass_events"),
        "deep_horizon_drains": deep_diag.get("horizon_only_drains"),
        "deep_finding_drains": deep_diag.get("finding_drains"),
        "directory_handoffs": directory.get("horizon_handoff_started_events"),
        "forum_full_transfer": bool(mechanism.get("forum_full_transfer")),
        "billing_full_transfer": bool(mechanism.get("billing_full_transfer")),
        "historical_regression_loss": regression_loss,
        "historical_regression_loss_count": len(regression_loss),
        "promotion_readiness": derived.get("promotion_readiness"),
        "product_default_changed": bool(derived.get("product_default_changed")),
        "generalization_claim": False,
        "fresh_validation": False,
        "scope": "inspected trigger-narrowing repair, not fresh validation",
        "reproduction": {
            "clean_clone_verified": bool((repro or {}).get("clean_clone_verified")),
            "command": (repro or {}).get("command") or (
                "python -m benchmark.finding_return_entry_reproduce "
                "--root experiments/published/finding-return-entry-v0.3.19 --verify"),
            "evidence_files": len((man or {}).get("files") or []),
        },
        "command": (
            "python -m benchmark.finding_return_entry_reproduce "
            "--root experiments/published/finding-return-entry-v0.3.19 --verify"),
    }


def _v0320(root: str | None = None) -> dict:
    base = root or V0320
    derived = _load(os.path.join(base, "metrics", "aggregate.json")) or {}
    repro = _load(os.path.join(base, "metrics", "reproduction.json")) or {}
    man = _load(os.path.join(base, "evidence-manifest.json")) or {}
    if not derived:
        return {"available": False}
    return {
        "available": True,
        "round": "v0.3.20",
        "title": "Strong Fresh Composite Validation",
        "outcome": derived.get("outcome"),
        "outcome_meaning": derived.get("outcome_meaning"),
        "composite_evaluable": derived.get("composite_evaluable_positive_targets"),
        "full_transfer": derived.get("full_transfer_positive_targets"),
        "nested_transfer": derived.get("nested_transfer_positive_targets"),
        "finding_drain": derived.get("finding_drain_positive_targets"),
        "guard_loss_count": len(derived.get("guard_bug_losses") or []),
        "guard_bug_losses": derived.get("guard_bug_losses") or [],
        "catalog_events": derived.get("catalog_candidate_event_count"),
        "kiosk_handoffs": derived.get("kiosk_nested_handoff_count"),
        "horizon_drains": derived.get("horizon_only_drain_count"),
        "kiosk_finding_evaluable": derived.get("kiosk_finding_control_evaluable"),
        "promotion_readiness": derived.get("promotion_readiness"),
        "product_default_changed": bool(derived.get("product_default_changed")),
        "generalization_claim": False,
        "fresh_validation": True,
        "scope": "strong fresh multi-target evidence, not universal generalization",
        "cells": 42,
        "reproduction": {
            "clean_clone_verified": bool(repro.get("clean_clone_verified")),
            "command": repro.get("command") or (
                "python -m benchmark.fresh_composite_reproduce "
                "--root experiments/published/fresh-composite-v0.3.20 --verify"),
            "evidence_files": len(man.get("files") or []),
        },
        "command": (
            "python -m benchmark.fresh_composite_reproduce "
            "--root experiments/published/fresh-composite-v0.3.20 --verify"),
    }


def _v0321(root: str | None = None) -> dict:
    base = root or V0321
    mechanism = _load(os.path.join(base, "metrics", "mechanism.json")) or {}
    derived = mechanism.get("derived") or {}
    facts = mechanism.get("facts") or {}
    repro = _load(os.path.join(base, "metrics", "reproduction.json")) or {}
    man = _load(os.path.join(base, "evidence-manifest.json")) or {}
    if not derived:
        return {"available": False}
    return {
        "available": True,
        "round": "v0.3.21",
        "title": "Return-Waypoint Frontier Escape",
        "outcome": derived.get("outcome"),
        "outcome_meaning": derived.get("outcome_meaning"),
        "engaged": derived.get("mechanism_engaged_count"),
        "recovered": derived.get("positives_fully_recovered"),
        "template_recovered": facts.get("template_589_recovered"),
        "catalog_escapes": facts.get("catalog_waypoint_escapes"),
        "kiosk_escapes": facts.get("kiosk_waypoint_escapes"),
        "historical_loss_count": len(facts.get("historical_guard_loss") or []),
        "promotion_readiness": derived.get("promotion_readiness"),
        "product_default_changed": bool(derived.get("product_default_changed")),
        "generalization_claim": False,
        "fresh_validation": False,
        "scope": "inspected repair of the v0.3.20 targets, not fresh validation",
        "cells": 24,
        "reproduction": {
            "clean_clone_verified": bool(repro.get("clean_clone_verified")),
            "command": repro.get("command") or (
                "python -m benchmark.return_waypoint_frontier_reproduce "
                "--root experiments/published/return-waypoint-frontier-v0.3.21 --verify"),
            "evidence_files": len(man.get("files") or []),
        },
        "command": (
            "python -m benchmark.return_waypoint_frontier_reproduce "
            "--root experiments/published/return-waypoint-frontier-v0.3.21 --verify"),
    }


def _v0322(root: str | None = None) -> dict:
    base = root or V0322
    diagnostic = _load(os.path.join(base, "metrics", "budget-diagnostic.json")) or {}
    per = _load(os.path.join(base, "metrics", "per-target.json")) or {}
    repro = _load(os.path.join(base, "metrics", "reproduction.json")) or {}
    man = _load(os.path.join(base, "evidence-manifest.json")) or {}
    if not diagnostic.get("diagnostic_conclusion"):
        return {"available": False}
    rows = {
        (row.get("app"), int(row.get("budget") or 0)): row
        for row in (per.get("rows") or [])
    }

    def cell(app: str, budget: int) -> dict:
        return rows.get((app, budget)) or {}

    campus = cell("buggy-campus", 480)
    studio = cell("buggy-studio", 480)
    warehouse = cell("buggy-warehouse", 480)
    booking = cell("buggy-booking", 480)
    preserved = bool(
        warehouse.get("template_589_recovered")
        and warehouse.get("productive_entity_reentry")
        and booking.get("template_589_recovered")
        and booking.get("productive_entity_reentry")
    )
    return {
        "available": True,
        "round": "v0.3.22",
        "title": "Post-Escape Sink Diagnosis",
        "kind": "diagnostic",
        "diagnosis": diagnostic.get("diagnostic_conclusion"),
        "meaning": diagnostic.get("meaning") or "",
        "campus_b480_template_recovered": bool(campus.get("template_589_recovered")),
        "studio_b480_template_recovered": bool(studio.get("template_589_recovered")),
        "warehouse_booking_preserved": preserved,
        "dominant_sink_fraction": {
            "buggy-campus": campus.get("dominant_scc_visit_fraction"),
            "buggy-studio": studio.get("dominant_scc_visit_fraction"),
        },
        "active_sequence_after_abandonment": {
            "buggy-campus": bool(campus.get("active_sequence_after_abandonment")),
            "buggy-studio": bool(studio.get("active_sequence_after_abandonment")),
        },
        "public_copy": diagnostic.get("public_copy") or "",
        "promotion_readiness": diagnostic.get("promotion_readiness") or "not_ready",
        "product_default_changed": bool(diagnostic.get("product_default_changed")),
        "generalization_claim": False,
        "fresh_validation": False,
        "v0321_outcome": "C",
        "scope": "failure diagnosis of the frozen v0.3.21 split, not a repair and not fresh validation",
        "cells": 8,
        "reproduction": {
            "clean_clone_verified": bool(repro.get("clean_clone_verified")),
            "command": repro.get("command") or (
                "python -m benchmark.post_escape_sink_reproduce "
                "--root experiments/published/post-escape-sink-v0.3.22 --verify"),
            "evidence_files": len(man.get("files") or []),
        },
        "command": (
            "python -m benchmark.post_escape_sink_reproduce "
            "--root experiments/published/post-escape-sink-v0.3.22 --verify"),
    }


def _v0323(root: str | None = None) -> dict:
    base = root or V0323
    mechanism = _load(os.path.join(base, "metrics", "mechanism.json")) or {}
    controls = _load(os.path.join(base, "metrics", "controls.json")) or {}
    safety = _load(os.path.join(base, "metrics", "safety.json")) or {}
    repro = _load(os.path.join(base, "metrics", "reproduction.json")) or {}
    man = _load(os.path.join(base, "evidence-manifest.json")) or {}
    derived = mechanism.get("derived") or {}
    positives = mechanism.get("positives") or {}
    if not derived.get("outcome"):
        return {"available": False}

    def cell(app: str) -> dict:
        item = positives.get(app) or {}
        debt = item.get("debt") or {}
        template = item.get("template") or {}
        return {
            "relocations": debt.get("residual_frontier_debt_relocations"),
            "consumed": debt.get("residual_frontier_tokens_consumed"),
            "created": debt.get("residual_frontier_debts_created"),
            "resolved": debt.get("residual_frontier_debts_resolved"),
            "template_589": bool(template.get("recovered")),
            "missing": template.get("missing") or [],
            "lost": item.get("lost_vs_guard") or [],
        }

    facts = safety.get("facts") or {}
    violations = sum(int(facts.get(key) or 0) for key in (
        "false_success_violations",
        "restore_sequence_violations",
        "consumption_violations",
        "zero_normal_loop_violations",
        "relocation_lifecycle_violations",
    ))
    catalog = ((controls.get("buggy-catalog") or {}).get("debt") or {})
    kiosk = ((controls.get("buggy-kiosk") or {}).get("debt") or {})
    campus = cell("buggy-campus")
    studio = cell("buggy-studio")
    warehouse = cell("buggy-warehouse")
    booking = cell("buggy-booking")
    return {
        "available": True,
        "round": "v0.3.23",
        "title": "Residual Frontier Debt Escape",
        "outcome": derived.get("outcome"),
        "outcome_meaning": derived.get("outcome_meaning") or "",
        "campus": campus,
        "studio": studio,
        "warehouse": warehouse,
        "booking": booking,
        "catalog_relocations": catalog.get("residual_frontier_debt_relocations"),
        "kiosk_relocations": kiosk.get("residual_frontier_debt_relocations"),
        "safety_violations": violations,
        "product_default_changed": bool(facts.get("product_default_changed")),
        "fresh_validation": False,
        "promotion_readiness": derived.get("promotion_readiness") or "not_ready",
        "v0322_diagnosis": "persistent_post_terminal_sink",
        "v0321_outcome": "C",
        "cells": 24,
        "scope": "inspected repair of the closed-SCC post-terminal starvation, not fresh validation",
        "public_copy": (
            "Campus 和 Studio 各发生 1 次债务回放，模板 5 和 8 收回，模板 9 仍缺。"
            "Warehouse 和 Booking 的债务在原组件里被普通动作消耗，回放次数为 0。"
            "Catalog 和 Kiosk 没有债务回放。这是已检查修复，不是 fresh validation。产品默认未改。"
        ),
        "reproduction": {
            "clean_clone_verified": bool(repro.get("clean_clone_verified")),
            "command": repro.get("command") or (
                "python -m benchmark.residual_frontier_debt_reproduce "
                "--root experiments/published/residual-frontier-debt-v0.3.23 --verify"),
            "evidence_files": len(man.get("files") or []),
        },
        "command": (
            "python -m benchmark.residual_frontier_debt_reproduce "
            "--root experiments/published/residual-frontier-debt-v0.3.23 --verify"),
    }


def _v0324(root: str | None = None) -> dict:
    base = root or V0324
    mechanism = _load(os.path.join(base, "metrics", "mechanism.json")) or {}
    controls = _load(os.path.join(base, "metrics", "controls.json")) or {}
    safety = _load(os.path.join(base, "metrics", "safety.json")) or {}
    repro = _load(os.path.join(base, "metrics", "reproduction.json")) or {}
    man = _load(os.path.join(base, "evidence-manifest.json")) or {}
    derived = mechanism.get("derived") or {}
    positives = mechanism.get("positives") or {}
    if not derived.get("outcome"):
        return {"available": False}

    def cell(app: str) -> dict:
        item = positives.get(app) or {}
        view = item.get("view") or {}
        debt = item.get("debt") or {}
        template = item.get("template") or {}
        return {
            "relocations": view.get("relocations", debt.get("residual_frontier_debt_relocations")),
            "episode_advances": view.get("advances"),
            "invalidated": view.get("invalidated"),
            "revalidated": view.get("revalidated"),
            "template_589": bool(template.get("recovered")),
            "missing": template.get("missing") or [],
            "lost": item.get("lost_vs_guard") or [],
        }

    facts = safety.get("facts") or {}
    violations = sum(int(facts.get(key) or 0) for key in (
        "episode_without_relocation",
        "cross_hub_invalidations",
        "restore_probe_violations",
        "duplicate_same_episode",
        "false_success",
    ))
    catalog = (controls.get("buggy-catalog") or {}).get("episode") or {}
    kiosk = (controls.get("buggy-kiosk") or {}).get("episode") or {}
    return {
        "available": True,
        "round": "v0.3.24",
        "title": "Episode-Scoped Local Drain Revalidation",
        "outcome": derived.get("outcome"),
        "outcome_meaning": derived.get("outcome_meaning") or "",
        "campus": cell("buggy-campus"),
        "studio": cell("buggy-studio"),
        "warehouse": cell("buggy-warehouse"),
        "booking": cell("buggy-booking"),
        "catalog_episode_advances": catalog.get("local_drain_episode_advances"),
        "kiosk_episode_advances": kiosk.get("local_drain_episode_advances"),
        "catalog_revalidated": catalog.get("local_drain_revalidated_probe_count"),
        "kiosk_revalidated": kiosk.get("local_drain_revalidated_probe_count"),
        "safety_violations": violations,
        "product_default_changed": bool(facts.get("product_default_changed")),
        "fresh_validation": False,
        "promotion_readiness": derived.get("promotion_readiness") or "not_ready",
        "v0323_outcome": "B",
        "v0322_diagnosis": "persistent_post_terminal_sink",
        "v0321_outcome": "C",
        "cells": 24,
        "scope": "inspected repair of reset-stale same-hub drain memory, not fresh validation",
        "public_copy": (
            "v0.3.24 修复的是 reset 之后的交互记忆失效：浏览器被 debt relocation "
            "重置后，旧 episode 里同页按钮的 mutation 已经消失，因此同页 drain 的"
            "去重标记也必须进入新 episode。结构 sequence、debt 和跨页 child 记忆仍然"
            "保持 run-scoped。Campus/Studio 的模板 9 在已检查用例上恢复，产品默认未改。"
            "这是 inspected repair，不是 fresh validation。"
        ),
        "reproduction": {
            "clean_clone_verified": bool(repro.get("clean_clone_verified")),
            "command": repro.get("command") or (
                "python -m benchmark.episode_drain_epoch_reproduce "
                "--root experiments/published/episode-drain-epoch-v0.3.24 --verify"),
            "evidence_files": len(man.get("files") or []),
        },
        "command": (
            "python -m benchmark.episode_drain_epoch_reproduce "
            "--root experiments/published/episode-drain-epoch-v0.3.24 --verify"),
    }


def build_showcase(*, v039_root: str | None = None, v038_root: str | None = None,
                   v0310_root: str | None = None, v0311_root: str | None = None,
                   v0312_root: str | None = None, v0313_root: str | None = None,
                   v0314_root: str | None = None, v0315_root: str | None = None,
                   v0316_root: str | None = None,
                   v0317_root: str | None = None,
                   v0318_root: str | None = None,
                   v0319_root: str | None = None,
                   v0320_root: str | None = None,
                   v0321_root: str | None = None,
                   v0322_root: str | None = None,
                   v0323_root: str | None = None,
                   v0324_root: str | None = None) -> dict:
    v039 = _v039(v039_root)
    v038 = _v038(v038_root)
    v0310 = _v0310(v0310_root)
    v0311 = _v0311(v0311_root)
    v0312 = _v0312(v0312_root)
    v0313 = _v0313(v0313_root)
    v0314 = _v0314(v0314_root)
    v0315 = _v0315(v0315_root)
    v0316 = _v0316(v0316_root)
    v0317 = _v0317(v0317_root)
    v0318 = _v0318(v0318_root)
    v0319 = _v0319(v0319_root)
    v0320 = _v0320(v0320_root)
    v0321 = _v0321(v0321_root)
    v0322 = _v0322(v0322_root)
    v0323 = _v0323(v0323_root)
    v0324 = _v0324(v0324_root)
    if v0324.get("available"):
        latest = {
            "round": "v0.3.24",
            "title": "Episode-Scoped Local Drain Revalidation",
            "available": True,
            "outcome": v0324.get("outcome"),
            "product_default_changed": v0324.get("product_default_changed"),
        }
        latest_research = "v0.3.24"
    elif v0323.get("available"):
        latest = {
            "round": "v0.3.23",
            "title": "Residual Frontier Debt Escape",
            "available": True,
            "outcome": v0323.get("outcome"),
            "product_default_changed": v0323.get("product_default_changed"),
        }
        latest_research = "v0.3.23"
    elif v0322.get("available"):
        latest = {
            "round": "v0.3.22",
            "title": "Post-Escape Sink Diagnosis",
            "available": True,
            "diagnosis": v0322.get("diagnosis"),
            "product_default_changed": v0322.get("product_default_changed"),
        }
        latest_research = "v0.3.22"
    elif v0321.get("available"):
        latest = {
            "round": "v0.3.21",
            "title": "Return-Waypoint Frontier Escape",
            "available": True,
            "outcome": v0321.get("outcome"),
            "product_default_changed": v0321.get("product_default_changed"),
        }
        latest_research = "v0.3.21"
    elif v0320.get("available"):
        latest = {
            "round": "v0.3.20",
            "title": "Strong Fresh Composite Validation",
            "available": True,
            "outcome": v0320.get("outcome"),
            "product_default_changed": v0320.get("product_default_changed"),
        }
        latest_research = "v0.3.20"
    elif v0319.get("available"):
        latest = {
            "round": "v0.3.19",
            "title": "Finding-Gated Return-Entry Drain",
            "available": True,
            "outcome": v0319.get("outcome"),
            "product_default_changed": v0319.get("product_default_changed"),
        }
        latest_research = "v0.3.19"
    elif v0318.get("available"):
        latest = {
            "round": "v0.3.18",
            "title": "Return-Phase Entry Drain",
            "available": True,
            "outcome": v0318.get("outcome"),
            "product_default_changed": v0318.get("product_default_changed"),
        }
        latest_research = "v0.3.18"
    elif v0317.get("available"):
        latest = {
            "round": "v0.3.17",
            "title": "Local Action Drain",
            "available": True,
            "outcome": v0317.get("outcome"),
            "product_default_changed": v0317.get("product_default_changed"),
        }
        latest_research = "v0.3.17"
    elif v0316.get("available"):
        latest = {
            "round": "v0.3.16",
            "title": "Early Parent Re-entry",
            "available": True,
            "outcome": v0316.get("outcome"),
            "product_default_changed": v0316.get("product_default_changed"),
        }
        latest_research = "v0.3.16"
    elif v0315.get("available"):
        latest = {
            "round": "v0.3.15",
            "title": "Fresh Handoff Validation",
            "available": True,
            "outcome": v0315.get("outcome"),
            "product_default_changed": v0315.get("product_default_changed"),
        }
        latest_research = "v0.3.15"
    elif v0314.get("available"):
        latest = {
            "round": "v0.3.14",
            "title": "Horizon Handoff",
            "available": True,
            "outcome": v0314.get("outcome"),
            "product_default_changed": v0314.get("product_default_changed"),
        }
        latest_research = "v0.3.14"
    elif v0313.get("available"):
        latest = {
            "round": "v0.3.13",
            "title": "Suspended Parent Frames",
            "available": True,
            "outcome": v0313.get("outcome"),
            "product_default_changed": v0313.get("product_default_changed"),
        }
        latest_research = "v0.3.13"
    elif v0312.get("available"):
        latest = {
            "round": "v0.3.12",
            "title": "Nested-Hub Parent Preservation",
            "available": True,
            "outcome": v0312.get("outcome"),
            "product_default_changed": v0312.get("product_default_changed"),
        }
        latest_research = "v0.3.12"
    elif v0311.get("available"):
        latest = {
            "round": "v0.3.11",
            "title": "Preregistered Multi-Target Replication",
            "available": True,
            "outcome": v0311.get("outcome"),
            "product_default_changed": v0311.get("product_default_changed"),
        }
        latest_research = "v0.3.11"
    elif v0310.get("available"):
        latest = {
            "round": "v0.3.10",
            "title": "Fresh Cross-App Transfer",
            "available": True,
            "outcome": v0310.get("outcome"),
            "product_default_changed": v0310.get("product_default_changed"),
        }
        latest_research = "v0.3.10"
    else:
        latest = {
            "round": "v0.3.9",
            "title": "Return-Cycle Guard",
            "available": bool(v039.get("available")),
            "outcome": v039.get("outcome") if v039.get("available") else None,
            "product_default_changed": (
                v039.get("product_default_changed") if v039.get("available") else None),
        }
        latest_research = "v0.3.9"
    return {
        "project": {
            "name": "GhostQA",
            "product_preview": "v0.4 preview",
            "latest_research": latest_research,
        },
        "latest": latest,
        "episode_drain": v0324,
        "residual_frontier_debt": v0323,
        "post_escape_sink": v0322,
        "return_waypoint": v0321,
        "fresh_composite": v0320,
        "finding_return_entry": v0319,
        "return_entry_drain": v0318,
        "local_action_drain": v0317,
        "reentry_frontier": v0316,
        "fresh_handoff": v0315,
        "horizon_handoff": v0314,
        "nested_stack": v0313,
        "nested_hub": v0312,
        "multi_target": v0311,
        "fresh_transfer": v0310,
        "return_cycle": v039,
        "application_shape": v038,
        "timeline": [
            {"round": "v0.3.6", "title": "Structural Memory",
             "kind": "development benchmark"},
            {"round": "v0.3.7", "title": "Frozen Transfer Check",
             "kind": "one-shot generalization"},
            {"round": "v0.3.8", "title": "Root Cause",
             "kind": "application-shape analysis"},
            {"round": "v0.3.9", "title": "Return-Cycle Guard",
             "kind": "mechanism repair"},
            {"round": "v0.3.10", "title": "Fresh Cross-App Transfer",
             "kind": "one-target transfer"},
            {"round": "v0.3.11", "title": "Preregistered Multi-Target Replication",
             "kind": "multi-target replication"},
            {"round": "v0.3.12", "title": "Nested-Hub Parent Preservation",
             "kind": "mechanism repair"},
            {"round": "v0.3.13", "title": "Suspended Parent Frames",
             "kind": "mechanism development"},
            {"round": "v0.3.14", "title": "Horizon Handoff",
             "kind": "mechanism development"},
            {"round": "v0.3.15", "title": "Fresh Handoff Validation",
             "kind": "fresh multi-target validation"},
            {"round": "v0.3.16", "title": "Early Parent Re-entry",
             "kind": "inspected failure repair"},
            {"round": "v0.3.17", "title": "Local Action Drain",
             "kind": "inspected failure repair"},
            {"round": "v0.3.18", "title": "Return-Phase Entry Drain",
             "kind": "inspected failure repair"},
            {"round": "v0.3.19", "title": "Finding-Gated Return-Entry Drain",
             "kind": "inspected trigger-narrowing repair"},
            {"round": "v0.3.20", "title": "Strong Fresh Composite Validation",
             "kind": "fresh composite validation"},
            {"round": "v0.3.21", "title": "Return-Waypoint Frontier Escape",
             "kind": "inspected failure repair"},
            {"round": "v0.3.22", "title": "Post-Escape Sink Diagnosis",
             "kind": "failure diagnosis"},
            {"round": "v0.3.23", "title": "Residual Frontier Debt Escape",
             "kind": "inspected failure repair"},
        ],
    }
