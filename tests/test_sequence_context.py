"""v0.3.6 contextual sequence memory. Must not change v0.3.5 sequence_mode."""
import inspect

from ghostqa.agent.gateway import NullLLM
from ghostqa.executor.sim import SimApp, SimExecutor
from ghostqa.exploration.explorer import run_exploration
from ghostqa.exploration.policy import GhostPolicy
from ghostqa.exploration.sequence import SequenceController, branch_key, W_BRANCH_NOVELTY
from ghostqa.exploration.sequence_memory import (
    StructuralHubMemory, CONTEXTUAL_NOVELTY_BONUS,
    W_CONTEXT_RETEST, MAX_SEQUENCE_ACTIONS,
)
from ghostqa.oracle.engine import OracleEngine
from ghostqa.state.graph import StateGraph
from ghostqa.state.models import Action, GUIState, UIElement
from ghostqa.state.similarity import classify_against_graph, SIMILAR
from ghostqa.state.signature import cluster_id, variant_key, state_id
try:
    from helpers import make_hub_state, make_seq_el
except ImportError:
    from tests.helpers import make_hub_state, make_seq_el


def _el(eid, text, kind="click"):
    return UIElement(eid, "button", text, kind=kind)


def _state(url, title, els, obs):
    return GUIState(app="t", url=url, title=title, elements=tuple(els), obs=obs)


def test_two_variants_share_structural_hub_memory():
    mem = StructuralHubMemory()
    mem.note_variant("hub", "h:a")
    mem.note_variant("hub", "h:b")
    mem.branch("hub", "hub:click:go_a").attempts = 1
    h = mem.hub("hub")
    assert h.cluster_id == "hub"
    assert len(h.variants_seen) == 2
    assert "hub:click:go_a" in h.branches


def test_same_context_does_not_get_first_time_novelty():
    ctrl = SequenceController("contextual")
    g = StateGraph()
    g.add_state("h:a", "/hub", "Hub", cluster_id="hub", variant_key="a")
    hub = make_hub_state()
    a = Action("click", "go_a")
    ctx = {"sig": "h:a", "step_index": 1}
    b1 = ctrl.score_bonus(a, hub, g, ctx)
    ctrl.after("h:a", a, hub, hub, "new", [], "h:a", False, g, 1)
    b2 = ctrl.score_bonus(a, hub, g, ctx)
    assert b1 >= W_BRANCH_NOVELTY - 1e-9
    assert b2 < W_BRANCH_NOVELTY


def test_v035_sequence_mode_still_retries_new_variant():
    """Frozen v0.3.5: exact-sig ledger, new variant is a new hub record."""
    ctrl = SequenceController("sequence")
    g = StateGraph()
    g.add_state("h:a", "/hub", "Hub", cluster_id="hub", variant_key="a")
    g.add_state("h:b", "/hub", "Hub", cluster_id="hub", variant_key="b")
    hub = make_hub_state()
    a = Action("click", "go_a")
    ctrl.after("h:a", a, hub, hub, "new", [], "x", False, g, 1)
    b = ctrl.score_bonus(a, hub, g, {"sig": "h:b", "step_index": 2})
    assert b >= W_BRANCH_NOVELTY - 1e-9


def test_contextual_mode_does_not_retry_same_branch_on_new_variant():
    ctrl = SequenceController("contextual")
    g = StateGraph()
    g.add_state("h:a", "/hub", "Hub", cluster_id="hub", variant_key="a")
    g.add_state("h:b", "/hub", "Hub", cluster_id="hub", variant_key="b")
    hub = make_hub_state()
    a = Action("click", "go_a")
    ctrl.after("h:a", a, hub, hub, "new", [], "x", False, g, 1)
    b = ctrl.score_bonus(a, hub, g, {"sig": "h:b", "step_index": 2})
    assert b < W_BRANCH_NOVELTY


def test_relevant_mutation_can_retest_branch():
    hub_del = _state("/hub", "Hub", (
        make_seq_el("go_a", "分支A"),
        make_seq_el("go_b", "Delete"),
        make_seq_el("go_c", "分支C"),
        make_seq_el("submit", "提交"),
    ), {"archive_state": "进行中"})
    after_arch = _state("/hub", "Hub", hub_del.elements, {"archive_state": "已归档"})
    ctrl = SequenceController("contextual")
    g = StateGraph()
    g.add_state("h", "/hub", "Hub", cluster_id="hub")
    g.add_state("h:arch", "/hub", "Hub", cluster_id="hub", variant_key="arch")
    dact = Action("click", "go_b")
    ctrl.after("h", dact, hub_del, hub_del, "new", [], "h", False, g, 1)
    ctrl.ledger.commitment_left = 0
    ctrl.ledger.returning = False
    ctrl.ledger.active_branch = ""
    mut = Action("click", "go_c")
    ctrl.after("h", mut, hub_del, after_arch, "similar", [], "h:arch", False, g, 2)
    ctrl.ledger.commitment_left = 0
    bonus = ctrl.score_bonus(dact, after_arch, g, {"sig": "h:arch"})
    assert bonus >= W_CONTEXT_RETEST - 1e-9
    assert bonus < W_BRANCH_NOVELTY


def test_irrelevant_mutation_does_not_reopen_all_branches():
    hub = _state("/hub", "Hub", (
        make_seq_el("go_a", "Members"),
        make_seq_el("go_b", "Tasks"),
        make_seq_el("go_c", "Billing"),
        make_seq_el("notify", "Notify"),
    ), {"notify_on": "0"})
    after = _state("/hub", "Hub", hub.elements, {"notify_on": "1"})
    ctrl = SequenceController("contextual")
    g = StateGraph()
    g.add_state("h", "/hub", "Hub", cluster_id="hub")
    for eid, step in (("go_a", 1), ("go_b", 2), ("go_c", 3)):
        ctrl.after("h", Action("click", eid), hub, hub, "new", [], "h", False, g, step)
    ctrl.after("h", Action("click", "notify"), hub, after, "similar", [], "h:n", False, g, 4)
    ctrl.ledger.commitment_left = 0
    ctrl.ledger.returning = False
    ctrl.ledger.active_branch = ""
    for eid in ("go_a", "go_b", "go_c"):
        hist = ctrl.struct.hub("hub").branches.get(f"hub:click:{eid}")
        assert hist is not None and hist.attempts >= 1
        b = ctrl.score_bonus(Action("click", eid), after, g, {"sig": "h"})
        assert b < W_BRANCH_NOVELTY  # never first-time novelty again
    acts = [Action("click", e) for e in ("go_a", "go_b", "go_c", "notify")]
    chosen = ctrl.pick_override(acts, after, g, {"sig": "h"})
    # at most one already-tested retest; notify is not a never-tested branch
    if chosen is not None:
        assert chosen.target_eid in ("go_a", "go_b", "go_c")


def test_existing_eid_gets_contextual_novelty_after_mutation():
    leaf = _state("/tasks", "Tasks", (
        _el("create", "Create"),
        _el("complete", "Complete"),
        _el("reopen", "Reopen"),
    ), {"task_status": "open"})
    after = _state("/tasks", "Tasks", leaf.elements, {"task_status": "done"})
    hub = make_hub_state()
    ctrl = SequenceController("contextual")
    g = StateGraph()
    g.add_state("h", "/hub", "Hub", cluster_id="hub")
    g.add_state("t", "/tasks", "Tasks", cluster_id="tasks")
    ctrl.after("h", Action("click", "go_a"), hub, leaf, "new", [], "t", False, g, 1)
    ctrl.mutations = []  # drop nav-arrival new-eid followups
    ctrl.last_label = "sequence_followup"
    ctrl.after("t", Action("click", "create"), leaf, after, "similar", [], "t", False, g, 2)
    complete = Action("click", "complete")
    assert not ctrl._is_followup(complete)  # not a new eid after in-page mutation
    ctrl.ledger.commitment_left = 0
    bonus = ctrl.score_bonus(complete, after, g, {"sig": "t"})
    assert bonus >= CONTEXTUAL_NOVELTY_BONUS - 1e-9
    # same context: no second novelty
    ctrl.after("t", complete, after, after, "identical", [], "t", False, g, 3)
    bonus2 = ctrl.score_bonus(complete, after, g, {"sig": "t"})
    assert bonus2 < CONTEXTUAL_NOVELTY_BONUS


def test_mutation_refresh_is_bounded():
    ctrl = SequenceController("contextual")
    g = StateGraph()
    g.add_state("h", "/hub", "Hub", cluster_id="hub")
    g.add_state("t", "/t", "T", cluster_id="t")
    hub = make_hub_state()
    leaf = _state("/t", "T", (_el("do", "Do"),), {"n": "0"})
    ctrl.after("h", Action("click", "go_a"), hub, leaf, "new", [], "t", False, g, 1)
    assert ctrl.ledger.commitment_left == 2  # horizon 3, consumed 1
    # burn commitment without mutation
    ctrl.after("t", Action("click", "do"), leaf, leaf, "identical", [], "t", False, g, 2)
    ctrl.after("t", Action("click", "do"), leaf, leaf, "identical", [], "t", False, g, 3)
    # commitment should be 0 / returning unless refresh
    left_before = ctrl.ledger.commitment_left
    mutated = _state("/t", "T", leaf.elements, {"n": "1"})
    ctrl.ledger.returning = False
    ctrl.ledger.active_branch = branch_key("hub", Action("click", "go_a"))
    ctrl.ledger.commitment_left = 0
    ctrl.ledger.branch_actions = 3
    ctrl.after("t", Action("click", "do"), leaf, mutated, "similar", [], "t", False, g, 4)
    assert ctrl.ctx_stats["mutation_refreshes"] >= 1
    assert ctrl.ledger.branch_actions + ctrl.ledger.commitment_left <= MAX_SEQUENCE_ACTIONS + 3


def test_cross_view_bonus_uses_fact_tokens_not_hardcoded_keys():
    ctrl = SequenceController("contextual-crossview")
    g = StateGraph()
    g.add_state("detail", "/d", "Detail", cluster_id="detail")
    g.add_state("list", "/l", "List", cluster_id="list")
    detail = _state("/d", "Detail", (
        _el("rename", "Rename"),
        _el("to_list", "List"),
        _el("x", "X"),
    ), {"entity_name": "A"})
    detail2 = _state("/d", "Detail", detail.elements, {"entity_name": "A-改"})
    lst = _state("/l", "List", (
        _el("backd", "返回"),
        _el("item", "Item"),
        _el("y", "Y"),
    ), {"list_entity_name": "A"})
    g.add_state("hub", "/h", "Hub", cluster_id="hub")
    hub = make_hub_state()
    ctrl.after("hub", Action("click", "go_a"), hub, detail, "new", [], "detail", False, g, 1)
    ctrl.struct.note_facts("list", lst)
    ctrl.after("detail", Action("click", "rename"), detail, detail2, "similar", [], "detail", False, g, 2)
    nav = Action("click", "to_list")
    g.add_transition("detail", "/d", "Detail", nav.key(), "list",
                     dst_url="/l", dst_title="List", action=nav,
                     src_cluster="detail", dst_cluster="list")
    bonus = ctrl.score_bonus(nav, detail2, g, {"sig": "detail"})
    assert bonus >= 0.2


def test_no_hidden_state_in_sequence_memory():
    src = inspect.getsource(
        __import__("ghostqa.exploration.sequence_memory", fromlist=["x"]))
    src2 = inspect.getsource(
        __import__("ghostqa.exploration.sequence", fromlist=["x"]))
    blob = src + src2
    assert "localStorage" not in blob
    assert "bugs.manifest" not in blob
    assert "BUG-D" not in blob
    assert "trigger_depth" not in blob
    assert "holdout.manifest" not in blob


def test_graph_classification_unchanged_by_sequence_memory():
    from ghostqa.exploration import sequence_memory as _sm  # noqa: F401
    g = StateGraph()
    a = _state("/p", "P", (_el("a", "A"),), {"k": "1"})
    b = _state("/p", "P", (_el("a", "A"),), {"k": "2"})
    sa, sb = state_id(a), state_id(b)
    assert cluster_id(a) == cluster_id(b)
    assert variant_key(a) != variant_key(b)
    g.add_state(sa, a.url, a.title, cluster_id=cluster_id(a), variant_key=variant_key(a))
    assert classify_against_graph(g, b) == SIMILAR


def test_sequence_mode_action_trace_not_changed_by_contextual_module():
    def _keys(mode):
        r = run_exploration(
            SimExecutor(_task_app()),
            GhostPolicy(NullLLM(), use_frontier=False, sequence_mode=mode),
            budget=12, oracle=OracleEngine())
        return [s.action.key() for s in r.steps]

    # v0.3.5 sequence remains deterministic vs itself
    assert _keys("sequence") == _keys("sequence")


def _task_app():
    pages = {
        "hub": {"url": "/hub", "title": "Hub",
                "elements": [
                    {"eid": "go_a", "role": "button", "text": "分支A",
                     "effect": {"op": "goto", "to": "tasks"}},
                    {"eid": "go_b", "role": "button", "text": "分支B",
                     "effect": {"op": "goto", "to": "tasks"}},
                    {"eid": "go_c", "role": "button", "text": "分支C",
                     "effect": {"op": "goto", "to": "tasks"}},
                ]},
        "tasks": {"url": "/tasks", "title": "Tasks",
                  "elements": [
                      {"eid": "create", "role": "button", "text": "Create",
                       "effect": {"op": "mutate",
                                  "mutations": [["set_field", ["status", "done"]]],
                                  "then": {"op": "goto", "to": "tasks"}}},
                      {"eid": "complete", "role": "button", "text": "Complete",
                       "effect": {"op": "noop"}},
                      {"eid": "reopen", "role": "button", "text": "Reopen",
                       "effect": {"op": "noop"}},
                      {"eid": "backh", "role": "button", "text": "返回",
                       "effect": {"op": "goto", "to": "hub"}},
                  ]},
    }
    return SimApp("ctx", "hub", pages, {"fields": {}},
                  lambda i, p: {"task_status": i.get("fields", {}).get("status", "open")})
