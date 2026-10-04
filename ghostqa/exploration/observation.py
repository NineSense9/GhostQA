"""Observe a selection without changing the frozen policy's scoring or cache.

Each run owns its policy. The two method probes are installed only during
select(), call the original methods once, and are removed even on failure.
"""
from .policy import GhostPolicy


def select_observed(policy, graph, state, actions, ctx):
    if type(policy) is not GhostPolicy:
        return policy.select(graph, state, actions, ctx)
    captured = {}
    originals = {}
    instance_methods = {}
    for name in ('_gate_reasons', '_semantic_scores'):
        originals[name] = getattr(policy, name)
        if name in policy.__dict__:
            instance_methods[name] = policy.__dict__[name]

    def gate(scores, ranked, inner_ctx):
        reasons = originals['_gate_reasons'](scores, ranked, inner_ctx)
        captured.update(program_scores=dict(scores), trigger=list(reasons))
        return reasons

    def semantic(inner_graph, inner_state, topk, inner_ctx):
        cached = inner_ctx['sig'] in policy._semantic_cache
        scores = originals['_semantic_scores'](inner_graph, inner_state, topk, inner_ctx)
        captured.update(cache_hit=cached, topk=list(topk), scores=dict(scores))
        return scores

    calls_before = getattr(policy.llm, 'calls', 0)
    policy._gate_reasons, policy._semantic_scores = gate, semantic
    try:
        chosen = policy.select(graph, state, actions, ctx)
    finally:
        for name in originals:
            if name in instance_methods:
                setattr(policy, name, instance_methods[name])
            else:
                delattr(policy, name)
    calls = getattr(policy.llm, 'calls', 0)
    unavailable = not policy.use_llm or bool(getattr(policy.llm, 'degraded', False))
    fallback = bool(getattr(policy.llm, 'last_fallback', False) or unavailable)
    mode = 'model_gate' if 'topk' in captured else 'program'
    decision = {
        'mode': mode, 'chosen': chosen.brief(), 'chosen_key': chosen.key(),
        'model_used': calls > calls_before and not fallback,
        'model_calls': calls, 'model_attempted': calls > calls_before,
        'cache_hit': captured.get('cache_hit', False),
        'fallback': fallback, 'model_unavailable': unavailable,
        'model_kind': 'mock' if policy.llm.__class__.__name__ == 'MockLLM' else 'real',
        'program_path': 'topk' not in captured or fallback,
        'trigger': captured.get('trigger', []),
        'top_k': [
            {'key': a.key(), 'label': a.brief(),
             'score': round(captured['scores'].get(a.key(), 0.5), 3),
             'combined_score': round(captured['program_scores'][a.key()]
                 + policy.w['w3_semantic'] * captured['scores'].get(a.key(), 0.5), 3)}
            for a in captured.get('topk', [])],
    }
    ctx['decision_mode'], ctx['last_decision'] = mode, decision
    return chosen
