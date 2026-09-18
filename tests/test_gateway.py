"""OpenAICompatibleGateway offline tests (no network)."""
from ghostqa.agent.gateway import OpenAICompatibleGateway


def test_parse_scores_validation():
    gw = OpenAICompatibleGateway(base_url="http://x", api_key="k", model="m")
    assert gw._parse_scores('{"scores": [0.1, 0.9, 0.5]}', 3) == [0.1, 0.9, 0.5]
    assert gw._parse_scores("prefix\n{\"scores\": [2, -1, 0.5]}\nsuffix", 3) == [1.0, 0.0, 0.5]
    assert gw._parse_scores('{"scores": [0.1]}', 3) is None          # wrong length
    assert gw._parse_scores("not json at all", 3) is None
    assert gw._parse_scores('{"scores": "high"}', 3) is None


def test_unavailable_without_config():
    gw = OpenAICompatibleGateway(base_url="", api_key="", model="")
    assert not gw.available
    scores = gw.score_actions("page", ["a", "b"])
    assert scores == {0: 0.5, 1: 0.5}                                # neutral fallback
    assert gw.calls == 0


def test_degrades_after_repeated_failures():
    gw = OpenAICompatibleGateway(base_url="http://127.0.0.1:1/none",
                                 api_key="k", model="m", timeout=0.2,
                                 max_retries=0)
    for _ in range(3):
        gw.score_actions("page-unique-" + str(_), ["a"])             # bypass cache
    assert gw.degraded
    assert not gw.available
    # after degradation: neutral scores, no more network attempts
    calls_before = gw.calls
    gw.score_actions("another", ["a"])
    assert gw.calls == calls_before


def test_cache_hits_do_not_recall(monkeypatch):
    gw = OpenAICompatibleGateway(base_url="http://x", api_key="k", model="m")
    monkeypatch.setattr(gw, "_chat", lambda prompt: '{"scores": [0.7]}')
    s1 = gw.score_actions("page", ["only"])
    s2 = gw.score_actions("page", ["only"])
    assert s1 == s2 == {0: 0.7}
    assert gw.calls == 1
