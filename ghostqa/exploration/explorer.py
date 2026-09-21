"""Exploration main loop: observe -> policy -> execute -> oracle -> record.

v0.3 additions (non-breaking):
- Graph nodes are exact state_ids (cluster + semantic variant).
- Similarity class (IDENTICAL / SIMILAR / NEW) is recorded per arrival.
- Optional global relocate: reset + replay a known path to a frontier.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

from ..state.models import Step, Finding, ConfirmedBug
from ..state.graph import StateGraph
from ..state.signature import state_id, cluster_id, variant_key, state_signature
from ..state.similarity import classify_against_graph, IDENTICAL, SIMILAR, NEW
from ..executor.base import available_actions
from ..oracle.engine import OracleEngine
from .interaction import (
    diagnose_action_space, opportunities, is_progress_action, workflow_stage,
)



def _build_step_event(step, graph, state, new_state, relation, exec_result,
                      budget_used: int, episode_id: int,
                      restore_step: bool = False) -> dict:
    """Serialize one executed step into a UI-friendly event dict.

    Pure observability: reads state only, never mutates the run. Consumed by
    the dashboard via the `on_step` hook.
    """
    src = graph.nodes.get(step.state_sig_before) if graph else None
    dst = graph.nodes.get(step.state_sig_after) if graph else None
    meta = dict(new_state.meta) if new_state and getattr(new_state, "meta", None) else {}
    return {
        "type": "step",
        "index": step.index,
        "decision_mode": getattr(step, "decision_mode", "") or "",
        "episode_id": episode_id,
        "budget_used": budget_used,
        "restore": restore_step,
        "action": step.action.to_dict(),
        "relation": relation,
        "findings": [f.to_dict() for f in step.findings],
        "src": {
            "sig": step.state_sig_before,
            "url": src.url if src else (state.url if state else ""),
            "title": src.title if src else (state.title if state else ""),
            "brief": (src.brief if src else "")[:400],
            "cluster_id": src.cluster_id if src else "",
            "visits": src.visits if src else 1,
            "screenshot": src.screenshot if src else "",
        },
        "dst": {
            "sig": step.state_sig_after,
            "url": dst.url if dst else (new_state.url if new_state else ""),
            "title": dst.title if dst else (new_state.title if new_state else ""),
            "brief": (dst.brief if dst else "")[:400],
            "cluster_id": dst.cluster_id if dst else "",
            "visits": dst.visits if dst else 1,
            "is_new": bool(dst and dst.visits <= 1),
            "screenshot": (dst.screenshot if dst else "") or meta.get("screenshot", ""),
        },
        "crashed": bool(exec_result.crashed) if exec_result else False,
        "js_errors": list(exec_result.js_errors) if exec_result else [],
        "http_errors": list(exec_result.http_errors) if exec_result else [],
        "events": list(exec_result.events) if exec_result else [],
        "elapsed_ms": meta.get("elapsed_ms", 0),
        "graph_stats": {
            "nodes": len(graph.nodes) if graph else 0,
            "edges": len(graph.edges) if graph else 0,
        },
    }


@dataclass
class RunResult:
    app: str
    policy: str
    steps: list = field(default_factory=list)       # list[Step]
    graph: StateGraph = None
    candidates: list = field(default_factory=list)  # list[Finding] deduped by fingerprint
    actions_executed: int = 0
    repeat_actions: int = 0
    llm_calls: int = 0
    pseudo_tokens: int = 0
    wall_seconds: float = 0.0
    relocate_count: int = 0
    restore_failures: int = 0
    similarity_counts: dict = field(default_factory=dict)
    restore_actions: int = 0
    input_actions_executed: int = 0
    progress_actions: int = 0
    unique_inputs_touched: int = 0
    max_workflow_depth: int = 0
    raw_action_count_mean: float = 0.0
    interaction_opportunity_mean: float = 0.0
    action_space_trace: list = field(default_factory=list)
    reset_events: list = field(default_factory=list)
    relocation_decisions: list = field(default_factory=list)
    relocation_metrics: dict = field(default_factory=dict)
    postreach_metrics: dict = field(default_factory=dict)
    sequence_metrics: dict = field(default_factory=dict)
    sequence_events: list = field(default_factory=list)

    def actions(self):
        """Flattened global action list. Do not use for replay.

        Replay/ddmin must call reproduction_actions(finding) so episode
        boundaries (reset / relocate / crash recovery) are respected.
        """
        return [s.action for s in self.steps]

    def step_for_finding(self, finding):
        for s in self.steps:
            if s.index == finding.step_index:
                return s
        fp = finding.fingerprint()
        for s in self.steps:
            for f in s.findings:
                if f.fingerprint() == fp:
                    return s
        return None

    def reproduction_actions(self, finding):
        """Episode-local prefix from the last reset through the finding.

        Relocate restore-path actions are included when they belong to the
        same episode. Prior episodes are not.
        """
        step = self.step_for_finding(finding)
        if step is None:
            return []
        return [s.action for s in self.steps
                if s.episode_id == step.episode_id and s.index <= step.index]

    episode_prefix_for_finding = reproduction_actions

    def finding_artifact(self, finding) -> dict:
        """Serialize a finding with derived episode_id (Finding is unchanged)."""
        from .metrics import finding_artifact
        return finding_artifact(self, finding)

    def make_confirmed(self, finding, reproduction, original_length=None):
        """ConfirmedBug with episode provenance for artifacts."""
        prefix = self.reproduction_actions(finding)
        n = original_length if original_length is not None else len(prefix)
        step = self.step_for_finding(finding)
        return ConfirmedBug(
            finding=finding,
            reproduction=reproduction,
            original_length=n,
            source_episode_id=None if step is None else step.episode_id,
            original_global_step=finding.step_index,
            episode_local_reproduction_length=n,
        )

    @property
    def productive_actions(self) -> int:
        return max(0, self.actions_executed - self.restore_actions)

    @property
    def restore_ratio(self) -> float:
        if not self.actions_executed:
            return 0.0
        return round(self.restore_actions / self.actions_executed, 3)

    @property
    def input_action_share(self) -> float:
        if not self.actions_executed:
            return 0.0
        return round(self.input_actions_executed / self.actions_executed, 3)


def _state_brief(state) -> str:
    elems = ", ".join(f"{e.role}:{e.text}" for e in state.elements[:12])
    facts = ",".join(f"{k}={state.obs[k]}" for k in list(state.obs)[:8]
                     if not str(k).startswith("input_"))
    return f"[{state.title}] {state.url} | {facts} | elements: {elems}"


def _id_fns(state_model: str):
    if state_model == "structural":
        return state_signature, state_signature, lambda s: "none"
    return state_id, cluster_id, variant_key


def _candidates(state, policy, sig, can_back, input_vocab, ctx) -> tuple:
    diag = diagnose_action_space(state, can_back, input_vocab)
    pp = getattr(policy, "payload_policy", None)
    if pp is not None and getattr(policy, "progressive", False):
        return pp.actions_for(state, sig, can_back, ctx), diag
    return available_actions(state, can_back=can_back, input_vocab=input_vocab), diag


def run_exploration(executor, policy, budget: int, oracle: OracleEngine = None,
                    input_vocab=None, spec_brief: str = "",
                    state_model: str = "semantic", on_step=None) -> RunResult:
    """on_step: optional callback invoked after each executed step as
    on_step(step, graph, budget_used) — pure observability hook used by the
    dashboard; does not affect exploration semantics."""
    oracle = oracle or OracleEngine()
    id_fn, cluster_fn, variant_fn = _id_fns(state_model)
    result = RunResult(app=executor.observe().app, policy=policy.name,
                       graph=StateGraph())
    graph = result.graph
    llm = getattr(policy, "llm", None)

    state = executor.reset()
    sig = id_fn(state)
    state.meta["sig"] = sig
    graph.add_state(sig, state.url, state.title, brief=_state_brief(state),
                    cluster_id=cluster_fn(state), variant_key=variant_fn(state),
                    relation=NEW)
    history_sigs = [sig]
    sig_url_map = {sig: state.url}
    recent_action_keys: list = []
    seen_fingerprints = set()
    effective_clicks = set()
    entered_new_state = True
    entered_new_variant = False
    pending_restore: list = []
    restore_target = ""
    episode_id = 0
    result.reset_events.append(
        {"before_step": 0, "reason": "initial", "episode_id": 0})
    t0 = time.time()
    inputs_touched: set = set()
    diag_raw_total = 0
    diag_opp_total = 0
    diag_n = 0
    pp = getattr(policy, "payload_policy", None)

    for step_idx in range(budget):
        if len(executor.ground_truth().get("__halt__", [])):
            break
        can_back = True
        pr = getattr(policy, "postreach", None)
        enum_ctx = {
            "sig": sig, "step_index": step_idx, "budget": budget,
            "page_progressed": bool(pp and sig in getattr(pp, "progress_pages", ())),
            "no_better_frontier": bool(pr is not None and pr.enabled()),
        }
        if pr is not None:
            enum_ctx.update(pr.enum_flags(sig, graph))
        actions, diag = _candidates(state, policy, sig, can_back, input_vocab, enum_ctx)
        result.action_space_trace.append(diag)
        diag_raw_total += diag["total_actions"]
        diag_opp_total += diag["unique_interaction_targets"]
        diag_n += 1
        if not actions and not pending_restore:
            break
        graph.record_observed(sig, [a.key() for a in actions])
        graph.record_opportunities(sig, opportunities(state, can_back))
        result.max_workflow_depth = max(result.max_workflow_depth,
                                        workflow_stage(state.url))

        if not pending_restore:
            relocate = getattr(policy, "maybe_relocate", None)
            target = relocate(graph, state, actions, {
                "sig": sig, "step_index": step_idx, "budget": budget,
                "state_brief": _state_brief(state),
            }) if relocate else None
            if target and target != sig:
                path = graph.shortest_path(graph.start_sig, target)
                if path is not None:
                    ledger = getattr(policy, "relocation_ledger", None)
                    from_cluster = cluster_fn(state) if state else ""
                    if ledger is not None:
                        ledger.note_chain_relocate()
                        ledger.mark_executed(len(path), from_cluster)
                        if getattr(policy, "relocate_mode", "") == "lease":
                            ledger.grant_lease()
                    state = executor.reset()
                    episode_id += 1
                    result.reset_events.append({
                        "before_step": step_idx, "reason": "relocate",
                        "episode_id": episode_id,
                    })
                    sig = id_fn(state)
                    state.meta["sig"] = sig
                    history_sigs = [sig]
                    sig_url_map[sig] = state.url
                    pending_restore = list(path)
                    restore_target = target if pending_restore else ""
                    result.relocate_count += 1
                    actions, diag = _candidates(
                        state, policy, sig, True, input_vocab, enum_ctx)
                    graph.record_observed(sig, [a.key() for a in actions])
                    graph.record_opportunities(sig, opportunities(state, True))
                else:
                    graph.mark_restore_failure(target)
                    result.restore_failures += 1

        cycle_detected = (len(history_sigs) >= 4 and history_sigs[-1] == history_sigs[-3]
                          and history_sigs[-2] == history_sigs[-4])
        ctx = {
            "sig": sig,
            "step_index": step_idx,
            "budget": budget,
            "state_brief": _state_brief(state),
            "spec_brief": spec_brief,
            "recent_action_keys": recent_action_keys[-10:],
            "cycle_detected": cycle_detected,
            "entered_new_state": entered_new_state,
            "entered_new_variant": entered_new_variant,
            "history_sigs": history_sigs,
        }

        restore_step = False
        if pending_restore:
            action = pending_restore.pop(0)
            restore_step = True
        else:
            if not actions:
                break
            action = policy.select(graph, state, actions, ctx)
        if recent_action_keys and action.key() in recent_action_keys[-3:]:
            result.repeat_actions += 1

        exec_result = executor.execute(action)
        new_state = exec_result.state if not exec_result.crashed else None
        new_sig = id_fn(new_state) if new_state else "CRASHED"
        dst_is_new = new_state is not None and graph.is_new_state(new_sig)
        relation = NEW
        if new_state is not None:
            relation = classify_against_graph(
                graph, new_state, id_fn=id_fn, cluster_fn=cluster_fn)

        if restore_step and (exec_result.crashed or not exec_result.ok):
            pending_restore = []
            result.restore_failures += 1
            if restore_target:
                graph.mark_restore_failure(restore_target)
            restore_target = ""

        findings = oracle.inspect(state, action, exec_result, new_state, {
            "step_index": step_idx,
            "history_sigs": history_sigs,
            "ground_truth": executor.ground_truth() if not exec_result.crashed else {},
            "sig_url_map": sig_url_map,
            "effective_clicks": effective_clicks,
        })
        if action.type == "click" and not exec_result.crashed:
            if (exec_result.events or new_sig != sig
                    or (new_state and new_state.obs != state.obs)):
                effective_clicks.add((sig, action.target_eid))
        for f in findings:
            if f.fingerprint() not in seen_fingerprints:
                seen_fingerprints.add(f.fingerprint())
                result.candidates.append(f)
            if f.kind in ("dead_action", "nav_loop"):
                graph.flag_node(sig, "had_l2_finding")

        graph.add_transition(
            sig, state.url, state.title, action.key(), new_sig,
            new_state.url if new_state else "",
            new_state.title if new_state else "",
            action=action,
            src_cluster=cluster_fn(state) if state else "",
            src_variant=variant_fn(state) if state else "",
            dst_cluster=cluster_fn(new_state) if new_state else "",
            dst_variant=variant_fn(new_state) if new_state else "",
            dst_relation=relation if dst_is_new else IDENTICAL,
            dst_screenshot=(new_state.meta.get("screenshot", "")
                            if new_state and getattr(new_state, "meta", None) else ""),
        )
        result.steps.append(Step(index=step_idx, state_sig_before=sig,
                                 action=action, state_sig_after=new_sig,
                                 findings=findings, episode_id=episode_id,
                                 decision_mode=ctx.get("decision_mode", "")))
        result.actions_executed += 1
        recent_action_keys.append(action.key())
        if on_step is not None:
            try:
                on_step(_build_step_event(
                    step=result.steps[-1], graph=graph,
                    state=state, new_state=new_state, relation=relation,
                    exec_result=exec_result, budget_used=result.actions_executed,
                    episode_id=episode_id, restore_step=restore_step))
            except Exception:
                pass  # observability must never break exploration
        if restore_step:
            result.restore_actions += 1
            ledger = getattr(policy, "relocation_ledger", None)
            if ledger is not None:
                ledger.on_restore_step(
                    ok=bool(exec_result.ok and not exec_result.crashed),
                    last=not pending_restore)
        if action.type == "input":
            result.input_actions_executed += 1
            if action.target_eid:
                inputs_touched.add(action.target_eid)
            if pp is not None:
                pp.mark(sig, action.target_eid or "", action.text or "")
        if is_progress_action(action, state):
            result.progress_actions += 1
            if pp is not None:
                pp.mark_progress(sig)
                if new_state is not None:
                    pp.mark_progress(new_sig)

        seqc = getattr(policy, "sequence", None)
        if seqc is not None and not restore_step:
            seqc.after(sig, action, state, new_state, relation, findings,
                       new_sig, bool(exec_result.crashed), graph, step_idx)

        pr = getattr(policy, "postreach", None)
        if pr is not None and not restore_step:
            via = is_progress_action(action, state)
            pr.ledger.arrive(
                sig, graph, step_idx, via_progress=False,
                cluster_id=cluster_fn(state) if state else "",
                arrival_type=action.type)
            if new_state is not None and new_sig not in ("CRASHED", "", sig):
                pr.ledger.arrive(
                    new_sig, graph, step_idx, via_progress=via,
                    cluster_id=cluster_fn(new_state),
                    arrival_type=action.type)
            pr.after(sig, action, relation if new_state else "",
                     findings, new_sig, bool(exec_result.crashed), state=state)

        ledger = getattr(policy, "relocation_ledger", None)
        if ledger is not None and not restore_step and not exec_result.crashed:
            dst_cluster = cluster_fn(new_state) if new_state else ""
            new_cluster = bool(
                dst_cluster
                and sum(1 for n in graph.nodes.values()
                        if n.cluster_id == dst_cluster) <= 1)
            ledger.on_productive_step(
                relation=relation if new_state else "",
                new_cluster=new_cluster,
                had_finding=bool(findings),
                cluster_id=dst_cluster,
                returned_to_prev=(dst_cluster == getattr(ledger, "_from_cluster", "")
                                  and bool(dst_cluster)),
            )

        if exec_result.crashed:
            pending_restore = []
            restore_target = ""
            state = executor.reset()
            episode_id += 1
            result.reset_events.append({
                "before_step": step_idx + 1, "reason": "crash_recovery",
                "episode_id": episode_id,
            })
            sig = id_fn(state)
            state.meta["sig"] = sig
            history_sigs = [sig]
            sig_url_map = {sig: state.url}
            entered_new_state = False
            entered_new_variant = False
            continue

        if restore_step and not pending_restore and restore_target:
            if new_sig != restore_target:
                result.restore_failures += 1
                graph.mark_restore_failure(restore_target)
            restore_target = ""

        state = new_state
        sig = new_sig
        state.meta["sig"] = sig
        history_sigs.append(sig)
        sig_url_map[sig] = state.url
        entered_new_state = relation == NEW
        entered_new_variant = relation == SIMILAR
        result.max_workflow_depth = max(result.max_workflow_depth,
                                        workflow_stage(state.url))

    result.wall_seconds = time.time() - t0
    result.similarity_counts = dict(graph.similarity_counts)
    ledger = getattr(policy, "relocation_ledger", None)
    if ledger is not None:
        ledger.close_open()
        result.relocation_decisions = list(ledger.decisions)
        result.relocation_metrics = ledger.metrics()
    pr = getattr(policy, "postreach", None)
    if pr is not None:
        result.postreach_metrics = pr.ledger.snapshot()
    seqc = getattr(policy, "sequence", None)
    if seqc is not None:
        seqc.close_open(step=result.actions_executed)
        result.sequence_metrics = seqc.metrics()
        result.sequence_events = list(seqc.events)
    result.unique_inputs_touched = len(inputs_touched)
    if diag_n:
        result.raw_action_count_mean = round(diag_raw_total / diag_n, 2)
        result.interaction_opportunity_mean = round(diag_opp_total / diag_n, 2)
    if llm is not None:
        result.llm_calls = getattr(llm, "calls", 0)
        result.pseudo_tokens = getattr(llm, "pseudo_tokens", 0)
    return result
