"""Replay validation + ddmin minimization tests."""
from ghostqa.executor.sim import SimExecutor
from ghostqa.minimizer.ddmin import ddmin, minimize_reproduction
from ghostqa.oracle.engine import OracleEngine
from ghostqa.replay.validator import validate_candidate, make_bug_test
from ghostqa.state.models import Action, Finding
from benchmark.sim_apps import make_sim_shop


def shop_factory():
    return SimExecutor(make_sim_shop()[0])


def crash_finding(step_index):
    return Finding(kind="crash", severity="high", description="pay crash",
                   step_index=step_index,
                   evidence={"action": "click[btn_pay]", "page": "checkout",
                             "page_url": "sim://sim-shop/checkout",
                             "url": "sim://sim-shop/checkout"})


# Path with redundant detours, then the crash:
# home -> products -> back -> cart -> remove -> checkout -> pay(crash)
REDUNDANT_PATH = [
    Action("click", "nav_products"),
    Action("back"),
    Action("click", "nav_cart"),
    Action("click", "btn_remove"),
    Action("click", "btn_checkout"),
    Action("click", "btn_pay"),
]


def test_validate_confirms_real_crash():
    _, spec, _ = make_sim_shop()
    oracle = OracleEngine(spec)
    f = crash_finding(step_index=5)
    vr = validate_candidate(shop_factory, REDUNDANT_PATH, f, oracle)
    assert vr.confirmed


def test_validate_rejects_false_positive():
    _, spec, _ = make_sim_shop()
    oracle = OracleEngine(spec)
    # claim a crash at step 1 (only nav_products executed - no crash there)
    f = crash_finding(step_index=0)
    vr = validate_candidate(shop_factory, REDUNDANT_PATH[:1], f, oracle)
    assert not vr.confirmed


def test_ddmin_shrinks_to_minimal():
    _, spec, _ = make_sim_shop()
    oracle = OracleEngine(spec)
    f = crash_finding(step_index=5)
    minimal = minimize_reproduction(shop_factory, REDUNDANT_PATH, f, oracle)
    # must keep: nav_cart -> btn_remove (empty cart) -> btn_checkout -> btn_pay
    assert [a.key() for a in minimal] == [
        "click:nav_cart:", "click:btn_remove:", "click:btn_checkout:", "click:btn_pay:"]
    assert len(minimal) < len(REDUNDANT_PATH)


def test_ddmin_pure_predicate():
    # classic ddmin sanity: bug requires both "b" and "d" present
    def test(seq):
        keys = {a.key() for a in seq}
        return "b" in keys and "d" in keys

    class FakeAction:
        def __init__(self, k):
            self.type = "click"
            self._k = k
        def key(self):
            return self._k

    seq = [FakeAction(k) for k in ["a", "b", "c", "d", "e"]]
    minimal = ddmin(seq, test)
    assert sorted(a.key() for a in minimal) == ["b", "d"]


def test_semantic_bug_reproduces_and_minimizes():
    _, spec, _ = make_sim_shop()
    oracle = OracleEngine(spec)
    path = [Action("click", "nav_products"), Action("back"),
            Action("click", "nav_cart"), Action("click", "btn_remove")]
    f = Finding(kind="semantic", severity="high", description="stale total",
                step_index=3, evidence={"assert_id": "cart_total_consistent",
                                        "url": "sim://sim-shop/cart"})
    vr = validate_candidate(shop_factory, path, f, oracle)
    assert vr.confirmed
    minimal = minimize_reproduction(shop_factory, path, f, oracle)
    assert [a.key() for a in minimal] == ["click:nav_cart:", "click:btn_remove:"]
