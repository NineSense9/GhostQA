"""Report generator: JSON + self-contained HTML bug report."""
from __future__ import annotations

import html
import json


def build_report(run_result, confirmed_bugs, config: dict) -> dict:
    return {
        "app": run_result.app,
        "policy": run_result.policy,
        "config": config,
        "summary": {
            "actions_executed": run_result.actions_executed,
            "states_discovered": len(run_result.graph.nodes) if run_result.graph else 0,
            "candidate_findings": len(run_result.candidates),
            "confirmed_bugs": len(confirmed_bugs),
            "llm_calls": run_result.llm_calls,
            "pseudo_tokens": run_result.pseudo_tokens,
            "wall_seconds": round(run_result.wall_seconds, 2),
        },
        "bugs": [b.to_dict() for b in confirmed_bugs],
        "graph": run_result.graph.to_dict() if run_result.graph else {},
        "trace": [s.to_dict() for s in run_result.steps],
    }


_HTML_TMPL = """<!DOCTYPE html>
<html lang="zh"><head><meta charset="utf-8"><title>GhostQA 测试报告 - {app}</title>
<style>
body{{font-family:system-ui,"Microsoft YaHei",sans-serif;margin:2rem;background:#fafafa;color:#222}}
h1{{font-size:1.4rem}} .card{{background:#fff;border:1px solid #e3e3e3;border-radius:8px;
padding:1rem 1.2rem;margin:.8rem 0;box-shadow:0 1px 2px rgba(0,0,0,.04)}}
.badge{{display:inline-block;padding:.1rem .55rem;border-radius:999px;font-size:.75rem;color:#fff}}
.high{{background:#d64545}} .medium{{background:#e69500}} .low{{background:#6b8afd}}
table{{border-collapse:collapse;margin:.5rem 0}} td,th{{border:1px solid #ddd;padding:.3rem .8rem;font-size:.85rem}}
code{{background:#f0f0f0;padding:.05rem .3rem;border-radius:4px;font-size:.82rem}}
.path{{font-size:.85rem;line-height:1.9}}
</style></head><body>
<h1>GhostQA 缺陷报告 · {app}</h1>
<div class="card"><b>测试策略</b>：{policy} ｜ <b>执行动作</b>：{actions} ｜
<b>发现状态</b>：{states} ｜ <b>候选异常</b>：{cands} ｜ <b>已确认 Bug</b>：{confirmed} ｜
<b>LLM 调用</b>：{llm} 次 / {tokens} tokens ｜ <b>耗时</b>：{secs}s</div>
{bugs_html}
</body></html>"""

_BUG_TMPL = """<div class="card">
<b>#{idx}</b> <span class="badge {sev}">{sev}</span> <code>{kind}</code>　{desc}<br>
<table><tr><th>原始路径长度</th><th>最小复现长度</th><th>验证状态</th></tr>
<tr><td>{orig}</td><td>{mini}</td><td>已重放确认</td></tr></table>
<div class="path"><b>最小复现路径</b>：{path}</div>
</div>"""


def render_html(report: dict) -> str:
    bugs_html = ""
    for i, b in enumerate(report["bugs"], 1):
        path = " → ".join(
            f"<code>{a['type']}[{a.get('target_eid') or ''}]</code>"
            for a in b["reproduction"]) or "（空）"
        f = b["finding"]
        bugs_html += _BUG_TMPL.format(
            idx=i, sev=f["severity"], kind=f["kind"],
            desc=html.escape(f["description"]),
            orig=b["original_length"], mini=len(b["reproduction"]), path=path)
    if not bugs_html:
        bugs_html = '<div class="card">未发现已确认缺陷。</div>'
    s = report["summary"]
    return _HTML_TMPL.format(
        app=html.escape(report["app"]), policy=report["policy"],
        actions=s["actions_executed"], states=s["states_discovered"],
        cands=s["candidate_findings"], confirmed=s["confirmed_bugs"],
        llm=s["llm_calls"], tokens=s["pseudo_tokens"], secs=s["wall_seconds"],
        bugs_html=bugs_html)


def write_report(report: dict, json_path: str, html_path: str = None):
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    if html_path:
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(render_html(report))
