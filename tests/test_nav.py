"""Navigation-history correctness (unit, no browser)."""
from ghostqa.executor.nav import should_record_navigation, urls_differ


def test_same_page_click_is_not_navigation():
    url = "http://127.0.0.1:9/detail.html"
    assert not should_record_navigation(url, url, "click")


def test_real_navigation_is_recorded():
    before = "http://127.0.0.1:9/index.html"
    after = "http://127.0.0.1:9/products.html"
    assert should_record_navigation(before, after, "click")
    assert urls_differ(before, after)


def test_back_never_records():
    before = "http://127.0.0.1:9/products.html"
    after = "http://127.0.0.1:9/index.html"
    assert not should_record_navigation(before, after, "back")


def test_wait_and_scroll_never_record():
    a, b = "http://x/a", "http://x/b"
    assert not should_record_navigation(a, b, "wait")
    assert not should_record_navigation(a, b, "scroll")


def test_input_that_navigates_is_recorded():
    assert should_record_navigation("http://x/form", "http://x/done", "input")


def test_query_only_change_counts_as_navigation():
    # Document URL changed (even if only the query). The volatile-query
    # *cluster* question is handled by state signatures, not the back stack.
    assert should_record_navigation(
        "http://x/page", "http://x/page?x=1", "click")
