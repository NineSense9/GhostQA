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


def build_showcase(*, v039_root: str | None = None, v038_root: str | None = None,
                   v0310_root: str | None = None, v0311_root: str | None = None,
                   v0312_root: str | None = None, v0313_root: str | None = None,
                   v0314_root: str | None = None, v0315_root: str | None = None) -> dict:
    v039 = _v039(v039_root)
    v038 = _v038(v038_root)
    v0310 = _v0310(v0310_root)
    v0311 = _v0311(v0311_root)
    v0312 = _v0312(v0312_root)
    v0313 = _v0313(v0313_root)
    v0314 = _v0314(v0314_root)
    v0315 = _v0315(v0315_root)
    if v0315.get("available"):
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
        ],
    }
