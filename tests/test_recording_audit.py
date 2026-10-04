import pytest
from dashboard.server import replay_until_stop


def test_empty_minimization_is_not_a_confirmed_bug():
    confirmed, unfinished = [], []
    replay_until_stop(['bug'], lambda: False, lambda f: True,
                      lambda f: [], lambda f, r: confirmed.append(f),
                      lambda f, e: unfinished.append(str(e)))
    assert confirmed == []
    assert len(unfinished) == 1


def test_replay_errors_propagate_without_an_unfinished_handler():
    def validate(f):
        raise TimeoutError('entry navigation timeout')
    with pytest.raises(TimeoutError):
        replay_until_stop(['bug'], lambda: False, validate,
                          lambda f: [f], lambda f, r: None)


def test_replay_closes_executor_even_when_reset_raises():
    from ghostqa.replay.validator import _replay
    from ghostqa.oracle.engine import OracleEngine
    class BrokenExecutor:
        closed = False
        def reset(self):
            raise TimeoutError('Page.goto: timeout')
        def close(self):
            self.closed = True
    executor = BrokenExecutor()
    with pytest.raises(TimeoutError):
        _replay(lambda: executor, [], OracleEngine())
    assert executor.closed


def test_ai_observer_keeps_frozen_policy_selection_and_reports_cache():
    from ghostqa.exploration.observation import select_observed
    from ghostqa.exploration.policy import GhostPolicy
    from ghostqa.agent.gateway import MockLLM
    from ghostqa.state.graph import StateGraph
    from ghostqa.state.models import Action, GUIState
    policy = GhostPolicy(MockLLM())
    original_score = policy._semantic_scores
    ctx = {'sig': 'exact:1', 'step_index': 0}
    state = GUIState(app='test', url='/cart', title='购物车')
    actions = [Action('click', 'pay'), Action('back')]
    chosen = select_observed(policy, StateGraph(), state, actions, ctx)
    assert ctx['last_decision']['chosen_key'] == chosen.key()
    assert ctx['last_decision']['model_used'] is True
    assert policy._semantic_scores == original_score
    select_observed(policy, StateGraph(), state, actions, ctx)
    assert ctx['last_decision']['cache_hit'] is True
    assert ctx['last_decision']['model_used'] is False


def test_ai_observer_reports_failed_calls_as_fallback_not_model_success():
    from ghostqa.exploration.observation import select_observed
    from ghostqa.exploration.policy import GhostPolicy
    from ghostqa.agent.gateway import MockLLM
    from ghostqa.state.graph import StateGraph
    from ghostqa.state.models import Action, GUIState
    class FailedGateway(MockLLM):
        last_fallback = True
    ctx = {'sig': 'exact:1', 'step_index': 0}
    select_observed(GhostPolicy(FailedGateway()), StateGraph(),
                    GUIState(app='test', url='/cart', title='购物车'), [Action('back')], ctx)
    assert ctx['last_decision']['fallback'] is True
    assert ctx['last_decision']['model_used'] is False


def test_navigation_timeout_during_action_is_unfinished():
    from ghostqa.replay.validator import _replay
    from ghostqa.executor.base import ExecResult
    from ghostqa.oracle.engine import OracleEngine
    from ghostqa.state.models import Action, GUIState
    class Executor:
        def reset(self):
            return GUIState(app='test', url='/cart', title='购物车')
        def execute(self, action):
            return ExecResult(ok=False, message='Page.goto: Timeout 15000ms exceeded.')
    with pytest.raises(TimeoutError, match='Page.goto'):
        _replay(Executor, [Action('back')], OracleEngine())
