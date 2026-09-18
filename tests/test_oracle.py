"""Oracle engine tests across L1/L2/L3."""
from ghostqa.oracle.engine import OracleEngine
from ghostqa.state.models import Action
from ghostqa.executor.sim import SimExecutor
from benchmark.sim_apps import make_sim_shop


def run_actions(ex, actions, oracle):
    """Execute actions, collecting findings with proper ctx."""
    from ghostqa.state.signature import state_signature
    state = ex.observe()
    hist = [state_signature(state)]
    all_findings = []
    for i, a in enumerate(actions):
        r = ex.execute(a)
        new = r.state if not r.crashed else None
        fs = oracle.inspect(state, a, r, new, {
            "step_index": i, "history_sigs": hist,
            "ground_truth": ex.ground_truth() if not r.crashed else {},
        })
        all_findings.extend(fs)
        if r.crashed:
            break
        state = new
        hist.append(state_signature(state))
    return all_findings


def test_l1_crash_detected():
    app, spec, _ = make_sim_shop()
    ex = SimExecutor(app)
    oracle = OracleEngine(spec)
    fs = run_actions(ex, [Action("click", "nav_cart"),
                          Action("click", "btn_remove"),
                          Action("click", "btn_checkout"),
                          Action("click", "btn_pay")], oracle)
    assert any(f.kind == "crash" and f.severity == "high" for f in fs)


def test_l2_dead_action_detected():
    app, spec, _ = make_sim_shop()
    ex = SimExecutor(app)
    oracle = OracleEngine(spec)
    fs = run_actions(ex, [Action("click", "nav_products"),
                          Action("click", "item_apple"),
                          Action("click", "btn_fav")], oracle)
    assert any(f.kind == "dead_action" and f.evidence["eid"] == "btn_fav" for f in fs)


def test_l2_nav_loop_detected():
    app, spec, _ = make_sim_shop()
    ex = SimExecutor(app)
    oracle = OracleEngine(spec)
    fs = run_actions(ex, [Action("click", "nav_products"),
                          Action("click", "nav_help"),
                          Action("click", "btn_more"),
                          Action("click", "btn_back_help"),
                          Action("click", "btn_more"),
                          Action("click", "btn_back_help")], oracle)
    assert any(f.kind == "nav_loop" for f in fs)


def test_l3_cart_total_semantic():
    app, spec, _ = make_sim_shop()
    ex = SimExecutor(app)
    oracle = OracleEngine(spec)
    fs = run_actions(ex, [Action("click", "nav_cart"),
                          Action("click", "btn_remove")], oracle)
    sem = [f for f in fs if f.kind == "semantic"]
    assert any(f.evidence["assert_id"] == "cart_total_consistent" for f in sem)


def test_l3_stock_negative():
    app, spec, _ = make_sim_shop()
    ex = SimExecutor(app)
    oracle = OracleEngine(spec)
    fs = run_actions(ex, [Action("click", "nav_products"),
                          Action("click", "item_apple"),
                          Action("click", "btn_buy"),
                          Action("click", "btn_buy"),
                          Action("click", "btn_buy")], oracle)
    assert any(f.evidence.get("assert_id") == "stock_non_negative"
               for f in fs if f.kind == "semantic")


def test_l3_register_false_success():
    app, spec, _ = make_sim_shop()
    ex = SimExecutor(app)
    oracle = OracleEngine(spec)
    fs = run_actions(ex, [Action("click", "nav_register"),
                          Action("input", "reg_user", ""),
                          Action("click", "btn_reg")], oracle)
    assert any(f.evidence.get("assert_id") == "register_requires_username"
               for f in fs if f.kind == "semantic")


def test_no_false_positive_on_clean_flow():
    app, spec, _ = make_sim_shop()
    ex = SimExecutor(app)
    oracle = OracleEngine(spec)
    fs = run_actions(ex, [Action("click", "nav_cart")], oracle)
    assert not [f for f in fs if f.kind == "semantic"]


def test_spec_brief_includes_desc_and_when():
    from ghostqa.oracle.spec import format_spec_brief
    spec = [{"id": "cart_total_consistent",
             "desc": "购物车显示总价应与列表商品金额之和一致",
             "when": {"url_contains": "/cart"}}]
    brief = format_spec_brief(spec)
    assert "cart_total_consistent" in brief
    assert "购物车显示总价" in brief
    assert "url_contains=/cart" in brief
    assert len(brief) < 800
