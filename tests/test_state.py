"""State model / signature / similarity / graph tests."""
from ghostqa.state.models import GUIState, UIElement, Action
from ghostqa.state.signature import (
    state_signature, ahash64, hamming, normalize_url,
    state_id, cluster_id, variant_key, variant_facts,
)
from ghostqa.state.similarity import (
    state_similarity, classify_against_graph, IDENTICAL, SIMILAR, NEW,
)
from ghostqa.state.graph import StateGraph


def make_state(url="/home", title="首页", elements=None, obs=None):
    return GUIState(app="t", url=url, title=title,
                    elements=tuple(elements or []), obs=obs or {})


def test_signature_stable_and_order_insensitive():
    e1 = UIElement("a", "button", "确定")
    e2 = UIElement("b", "link", "首页")
    s1 = make_state(elements=[e1, e2])
    s2 = make_state(elements=[e2, e1])          # different order
    assert state_signature(s1) == state_signature(s2)


def test_signature_changes_on_text_change():
    e1 = UIElement("a", "button", "确定")
    e2 = UIElement("a", "button", "取消")
    assert state_signature(make_state(elements=[e1])) != \
           state_signature(make_state(elements=[e2]))


def test_signature_ignores_volatile_query():
    e = UIElement("a", "button", "确定")
    s1 = make_state(url="/home?t=123", elements=[e])
    s2 = make_state(url="/home?t=999", elements=[e])
    assert normalize_url(s1.url) == normalize_url(s2.url)
    assert state_signature(s1) == state_signature(s2)


def test_ahash_and_hamming():
    h1 = ahash64([0] * 32 + [255] * 32)
    h2 = ahash64([0] * 32 + [255] * 32)
    h3 = ahash64([255] * 64)
    assert hamming(h1, h2) == 0
    assert hamming(h1, h3) == 32          # h1 has 32 bits set, h3 all 64


def test_similarity_levels():
    e1 = UIElement("a", "button", "确定")
    e2 = UIElement("b", "link", "购物车")
    s1 = make_state(elements=[e1, e2])
    s2 = make_state(elements=[e2, e1])
    assert state_similarity(s1, s2) == IDENTICAL
    s3 = make_state(url="/other", title="别的", elements=[e1])
    assert state_similarity(s1, s3) == NEW


def test_graph_transitions_and_untried():
    g = StateGraph()
    g.add_transition("s1", "/a", "A", "click:x", "s2", "/b", "B")
    g.add_transition("s1", "/a", "A", "click:x", "s2", "/b", "B")
    assert len(g.nodes) == 2
    assert g.edge_count("s1", "click:x") == 2
    assert g.untried_actions("s1", ["click:x", "click:y"]) == ["click:y"]
    assert g.is_new_state("s3")
    assert not g.is_new_state("s1")
    assert g.stats()["total_transitions"] == 2


def test_action_key_unique():
    assert Action("click", "a").key() != Action("input", "a", "x").key()
    assert Action("input", "a", "x").key() != Action("input", "a", "y").key()


def test_cart_variants_same_cluster_different_id():
    e = [UIElement("rm", "button", "删除"), UIElement("pay", "button", "结算")]
    empty = make_state(url="/cart", title="购物车", elements=e, obs={"cart_count": "0"})
    full = make_state(url="/cart", title="购物车", elements=e, obs={"cart_count": "1"})
    assert cluster_id(empty) == cluster_id(full)
    assert variant_key(empty) != variant_key(full)
    assert state_id(empty) != state_id(full)
    assert state_similarity(empty, full) == SIMILAR


def test_variant_ignores_input_buffers_and_clocks():
    e = [UIElement("a", "button", "确定")]
    a = make_state(elements=e, obs={"cart_count": "1", "input_search": "foo", "clock": "12:01"})
    b = make_state(elements=e, obs={"cart_count": "1", "input_search": "bar", "clock": "12:02"})
    assert variant_facts(a) == variant_facts(b)
    assert variant_key(a) == variant_key(b)
    assert state_id(a) == state_id(b)


def test_volatile_query_does_not_split_cluster():
    e = [UIElement("a", "button", "确定")]
    s1 = make_state(url="/home?t=123", elements=e, obs={"stock": "2"})
    s2 = make_state(url="/home?t=456", elements=e, obs={"stock": "2"})
    assert cluster_id(s1) == cluster_id(s2)
    assert state_id(s1) == state_id(s2)


def test_stock_zero_is_new_variant():
    e = [UIElement("buy", "button", "购买")]
    a = make_state(url="/detail", title="详情", elements=e, obs={"stock_num": "2"})
    b = make_state(url="/detail", title="详情", elements=e, obs={"stock_num": "0"})
    assert cluster_id(a) == cluster_id(b)
    assert state_similarity(a, b) == SIMILAR


def test_logged_in_out_are_variants_when_structure_matches():
    e = [UIElement("x", "button", "退出")]
    a = make_state(url="/dash", title="工作台", elements=e, obs={"login_state": "未登录"})
    b = make_state(url="/dash", title="工作台", elements=e, obs={"login_state": "已登录"})
    assert state_similarity(a, b) == SIMILAR


def test_graph_records_clusters_and_shortest_path():
    g = StateGraph()
    a1 = Action("click", "go")
    g.add_transition("c1:v0", "/a", "A", a1.key(), "c2:v0", "/b", "B",
                     action=a1, src_cluster="c1", src_variant="v0",
                     dst_cluster="c2", dst_variant="v0", dst_relation=NEW)
    a2 = Action("click", "next")
    g.add_transition("c2:v0", "/b", "B", a2.key(), "c2:v1", "/b", "B",
                     action=a2, src_cluster="c2", src_variant="v0",
                     dst_cluster="c2", dst_variant="v1", dst_relation=SIMILAR)
    assert g.cluster_count() == 2
    assert g.variant_count() == 3
    path = g.shortest_path("c1:v0", "c2:v1")
    assert path is not None and [p.key() for p in path] == [a1.key(), a2.key()]


def test_classify_against_graph_levels():
    g = StateGraph()
    e = [UIElement("a", "button", "确定")]
    s1 = make_state(url="/cart", title="购物车", elements=e, obs={"cart_count": "0"})
    g.add_state(state_id(s1), s1.url, s1.title,
                cluster_id=cluster_id(s1), variant_key=variant_key(s1),
                relation=NEW)
    assert classify_against_graph(g, s1) == IDENTICAL
    s2 = make_state(url="/cart", title="购物车", elements=e, obs={"cart_count": "1"})
    assert classify_against_graph(g, s2) == SIMILAR
    s3 = make_state(url="/other", title="别的", elements=[UIElement("b", "link", "x")])
    assert classify_against_graph(g, s3) == NEW
