"""Browser navigation-history helpers.

GhostQA keeps an explicit back-stack instead of calling `page.go_back()`,
because hash/SPA routing and our reset semantics are easier to reason about
with a stack we own. The stack must only record *actual* document navigations.
Same-page clicks (favorite, submit, toggle, delete) must not pollute it.
"""
from __future__ import annotations


def urls_differ(url_before: str, url_after: str) -> bool:
    return (url_before or "") != (url_after or "")


def should_record_navigation(url_before: str, url_after: str,
                             action_type: str) -> bool:
    """True iff this action produced a real navigation that Back should undo.

    `back` itself pops the stack; recording it would bounce between the same
    two URLs. Wait/scroll never change the document URL by themselves.
    """
    if action_type in ("back", "wait", "scroll"):
        return False
    return urls_differ(url_before, url_after)
