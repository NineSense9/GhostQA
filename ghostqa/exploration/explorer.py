"""Exploration main loop: observe -> policy -> execute -> oracle -> record."""
from __future__ import annotations

import time
from dataclasses import dataclass, field

from ..state.models import Step, Finding
from ..state.graph import StateGraph
from ..state.signature import state_signature
from ..executor.base import available_actions
from ..oracle.engine import OracleEngine


@dataclass
class RunResult:
    app: str
    policy: str
    steps: list = field(default_factory=list)       # list[Step]
    graph: StateGraph = None
    candidates: list = field(default_factory=list)  # list[Finding] deduped by bug_key
    actions_executed: int = 0
    repeat_actions: int = 0
    llm_calls: int = 0
    pseudo_tokens: int = 0
    wall_seconds: float = 0.0

    def actions(self):
        return [s.action for s in self.steps]


def _state_brief(state) -> str:
    elems = ", ".join(f"{e.role}:{e.text}" for e in state.elements[:12])
    return f"[{state.title}] {state.url} | elements: {elems}"


def run_exploration(executor, policy, budget: int, oracle: OracleEngine = None,
                    input_vocab=None, spec_brief: str = "") -> RunResult:
    oracle = oracle or OracleEngine()
    result = RunResult(app=executor.observe().app, policy=policy.name,
                       graph=StateGraph())
    graph = result.graph
    llm = getattr(policy, "llm", None)

    state = executor.reset()
    sig = state_signature(state)
    state.meta["sig"] = sig
    graph.add_state(sig, state.url, state.title, brief=_state_brief(state))
    history_sigs = [sig]
    sig_url_map = {sig: state.url}
    recent_action_keys: list = []
    seen_fingerprints = set()
    entered_new_state = True                 # the initial state is novel by definition
    t0 = time.time()

    for step_idx in range(budget):
        if len(executor.ground_truth().get("__halt__", [])):
            break
        can_back = True
        actions = available_actions(state, can_back=can_back, input_vocab=input_vocab)
        if not actions:
            break

        cycle_detected = (len(history_sigs) >= 4 and history_sigs[-1] == history_sigs[-3]
                          and history_sigs[-2] == history_sigs[-4])
        ctx = {
            "sig": sig,
            "step_index": step_idx,
            "state_brief": _state_brief(state),
            "spec_brief": spec_brief,
            "recent_action_keys": recent_action_keys[-10:],
            "cycle_detected": cycle_detected,
            "entered_new_state": entered_new_state,   # True iff we just arrived somewhere unknown
            "history_sigs": history_sigs,
        }
        action = policy.select(graph, state, actions, ctx)
        if recent_action_keys and action.key() in recent_action_keys[-3:]:
            result.repeat_actions += 1

        exec_result = executor.execute(action)
        new_state = exec_result.state if not exec_result.crashed else None
        new_sig = state_signature(new_state) if new_state else "CRASHED"
        # record destination novelty BEFORE it is added to the graph
        dst_is_new = new_state is not None and graph.is_new_state(new_sig)

        findings = oracle.inspect(state, action, exec_result, new_state, {
            "step_index": step_idx,
            "history_sigs": history_sigs,
            "ground_truth": executor.ground_truth() if not exec_result.crashed else {},
            "sig_url_map": sig_url_map,
        })
        for f in findings:
            if f.fingerprint() not in seen_fingerprints:
                seen_fingerprints.add(f.fingerprint())
                result.candidates.append(f)
            if f.kind in ("dead_action", "nav_loop"):
                graph.flag_node(sig, "had_l2_finding")

        graph.add_transition(sig, state.url, state.title, action.key(), new_sig,
                             new_state.url if new_state else "",
                             new_state.title if new_state else "")
        result.steps.append(Step(index=step_idx, state_sig_before=sig,
                                 action=action, state_sig_after=new_sig,
                                 findings=findings))
        result.actions_executed += 1
        recent_action_keys.append(action.key())

        if exec_result.crashed:
            state = executor.reset()          # restart after crash
            sig = state_signature(state)
            state.meta["sig"] = sig
            history_sigs = [sig]
            sig_url_map = {sig: state.url}
            entered_new_state = False
            continue

        state = new_state
        sig = new_sig
        state.meta["sig"] = sig
        history_sigs.append(sig)
        sig_url_map[sig] = state.url
        entered_new_state = dst_is_new

    result.wall_seconds = time.time() - t0
    if llm is not None:
        result.llm_calls = getattr(llm, "calls", 0)
        result.pseudo_tokens = getattr(llm, "pseudo_tokens", 0)
    return result
