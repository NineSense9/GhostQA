"""State model / signature / similarity / graph tests."""
from ghostqa.state.models import GUIState, UIElement, Action
from ghostqa.state.signature import state_signature, ahash64, hamming, normalize_url
from ghostqa.state.similarity import state_similarity, IDENTICAL, SIMILAR, NEW
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
