"""Sim executor behavior tests."""
import pytest

from ghostqa.state.models import Action
from ghostqa.executor.sim import SimExecutor
from benchmark.sim_apps import make_sim_shop


def test_navigate_and_guard():
    ex = SimExecutor(make_sim_shop()[0])
    s = ex.observe()
    assert s.meta["page"] == "home"
    # profile guarded by login
    r = ex.execute(Action("click", "nav_profile"))
    assert r.state.meta["page"] == "login"
    # login then profile reachable
    ex.execute(Action("click", "btn_login"))
    assert ex.observe().meta["page"] == "profile"


def test_crash_and_reset():
    ex = SimExecutor(make_sim_shop()[0])
    ex.execute(Action("click", "nav_cart"))
    ex.execute(Action("click", "btn_remove"))     # empty the cart first
    ex.execute(Action("click", "btn_checkout"))
    r = ex.execute(Action("click", "btn_pay"))
    assert r.crashed
    with pytest.raises(RuntimeError):
        ex.observe()
    s = ex.reset()
    assert s.meta["page"] == "home"


def test_pay_with_items_goes_profile():
    ex = SimExecutor(make_sim_shop()[0])
    ex.execute(Action("click", "nav_cart"))
    ex.execute(Action("click", "btn_checkout"))
    r = ex.execute(Action("click", "btn_pay"))
    assert not r.crashed
    assert r.state.meta["page"] == "profile"


def test_input_overflow_js_error():
    ex = SimExecutor(make_sim_shop()[0])
    r = ex.execute(Action("input", "search_box", "x" * 25))
    assert r.js_errors, "expected js error on overflow input"
    r2 = ex.execute(Action("input", "search_box", "苹果"))
    assert not r2.js_errors


def test_cart_total_stale_after_remove():
    ex = SimExecutor(make_sim_shop()[0])
    ex.execute(Action("click", "nav_cart"))
    r = ex.execute(Action("click", "btn_remove"))
    assert r.state.obs["cart_count"] == 0
    assert r.state.obs["cart_total_display_num"] == 5   # BUG: stale total
    assert ex.ground_truth()["cart"] == []


def test_dead_action_favorite():
    ex = SimExecutor(make_sim_shop()[0])
    ex.execute(Action("click", "nav_products"))
    ex.execute(Action("click", "item_apple"))
    before = ex.observe()
    r = ex.execute(Action("click", "btn_fav"))
    after = r.state
    assert before.obs == after.obs
    assert not r.events
