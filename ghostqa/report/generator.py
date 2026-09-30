"""Report generator: JSON + self-contained HTML bug report."""
from __future__ import annotations

import html
import json


def report_for_saved_run(cfg, summary, bugs, status) -> dict | None:
    """Report shell for a run that stopped or crashed before report.json existed.

    A finished run stays on its stored report. This does not invent a
    minimized path; the caller passes the saved candidates separately.
    """
    if status not in ("error", "stopped"):
        return None
    if not isinstance(cfg, dict):
        cfg = {}
    if not isinstance(summary, dict):
        summary = {}
    if not isinstance(bugs, list):
        bugs = []
    url = str(cfg.get("url") or "")
    app = "web:" + url.split("//", 1)[-1] if "://" in url else (url or "web")
    return {
        "app": app,
        "policy": str(cfg.get("policy") or "ghost"),
        "config": cfg,
        "summary": {
            "actions_executed": summary.get("actions", 0),
            "states_discovered": summary.get("states", 0),
            "candidate_findings": summary.get("candidates", 0),
            "confirmed_bugs": summary.get("confirmed", len(bugs)),
            "llm_calls": summary.get("llm_calls", 0),
            "pseudo_tokens": summary.get("pseudo_tokens", 0),
            "wall_seconds": summary.get("wall_seconds", 0),
        },
        "bugs": bugs,
        "replay_state": status,
    }


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
<table><tr><th>原始路径长度</th><th>最小复现长度</th><th>episode</th><th>global step</th><th>验证状态</th></tr>
<tr><td>{orig}</td><td>{mini}</td><td>{epid}</td><td>{gstep}</td><td>已重放确认</td></tr></table>
<div class="path"><b>最小复现路径</b>：{path}</div>
{extra}
</div>"""


def _repro_step_html(action: dict) -> str:
    """Show the visible control name when the dashboard stored one.

    An input keeps its typed text. The name does not replace the payload.
    """
    kind = html.escape(str(action.get("type") or ""))
    eid = str(action.get("target_eid") or "")
    label = str(action.get("label") or "").strip()
    payload = action.get("text")
    payload_s = "" if payload is None else str(payload)
    title = f' title="{html.escape(eid)}"' if eid and label else ""
    if label and payload_s:
        return f"<code{title}>{kind}[{html.escape(label)}]={html.escape(payload_s)}</code>"
    if label:
        return f"<code{title}>{kind}[{html.escape(label)}]</code>"
    return f"<code>{kind}[{html.escape(eid)}]</code>"


def _finding_key(item: dict):
    """Match a candidate to a confirmed bug without reading replay results."""
    if not isinstance(item, dict):
        return None
    finding = item.get("finding")
    if isinstance(finding, dict):
        item = finding
    if not item.get("kind") and not item.get("description"):
        return None
    step = item.get("step_index")
    return (
        str(item.get("kind") or ""),
        "" if step is None else str(step),
        str(item.get("description") or ""),
    )


def pending_findings(candidates, confirmed_bugs) -> list:
    """Candidates that are not already listed as confirmed bugs."""
    confirmed = set()
    for bug in confirmed_bugs or []:
        key = _finding_key(bug)
        if key is not None:
            confirmed.add(key)
    pending = []
    for item in candidates or []:
        key = _finding_key(item)
        if key is None or key in confirmed:
            continue
        pending.append(item)
    return pending


def _pending_heading(report: dict) -> str:
    """A stop or a crash did not finish replay. A finished run did."""
    if report.get("replay_state") in ("stopped", "error"):
        return "重放未完成"
    return "未通过重放"


def _pending_card(item: dict, heading: str) -> str:
    """Evidence only. An unfinished or failed replay has no minimized path."""
    evidence = item.get("evidence") if isinstance(item.get("evidence"), dict) else {}
    kind = html.escape(str(item.get("kind") or "candidate"))
    desc = html.escape(str(item.get("description") or ""))
    sev = str(item.get("severity") or "")
    badge = f' <span class="badge {sev}">{sev}</span>' if sev in ("high", "medium", "low") else ""
    extra = ""
    url = evidence.get("url") or evidence.get("page") or ""
    if url:
        extra += f'<div class="path">{html.escape(str(url))}</div>'
    action = evidence.get("action") or ""
    if action:
        extra += f'<div class="path">{html.escape(str(action))}</div>'
    eid = evidence.get("eid") or ""
    if eid:
        extra += f'<div class="path">{html.escape(str(eid))}</div>'
    obs = evidence.get("obs") if isinstance(evidence.get("obs"), dict) else {}
    bits = []
    for key, val in list(obs.items())[:6]:
        if val is not None and not isinstance(val, (str, int, float, bool)):
            continue
        shown = "（空）" if val is None or val == "" else str(val)
        bits.append(f"<code>{html.escape(str(key))}</code> {html.escape(shown)}")
    if bits:
        extra += '<div class="path">' + " · ".join(bits) + "</div>"
    return (
        f'<div class="card"><b>{html.escape(heading)}</b>{badge} '
        f"<code>{kind}</code>　{desc}<br>{extra}</div>"
    )


def render_html(report: dict, candidates=None) -> str:
    bugs_html = ""
    for i, b in enumerate(report["bugs"], 1):
        path = " → ".join(
            _repro_step_html(a) for a in b["reproduction"]) or "（空）"
        f = b["finding"]
        evidence = f.get("evidence") or {}
        extra = ""
        url = evidence.get("url") or ""
        if url:
            extra += f'<div class="path">{html.escape(str(url))}</div>'
        obs = evidence.get("obs") if isinstance(evidence.get("obs"), dict) else {}
        bits = []
        for key, val in list(obs.items())[:6]:
            if val is not None and not isinstance(val, (str, int, float, bool)):
                continue
            shown = "（空）" if val is None or val == "" else str(val)
            bits.append(
                f"<code>{html.escape(str(key))}</code> {html.escape(shown)}")
        if bits:
            extra += '<div class="path">' + " · ".join(bits) + "</div>"
        bugs_html += _BUG_TMPL.format(
            idx=i, sev=f["severity"], kind=f["kind"],
            desc=html.escape(f["description"]),
            orig=b["original_length"], mini=len(b["reproduction"]), path=path,
            epid=b.get("source_episode_id", ""),
            gstep=b.get("original_global_step", f.get("step_index", "")),
            extra=extra)
    if not bugs_html:
        bugs_html = '<div class="card">未发现已确认缺陷。</div>'
    heading = _pending_heading(report)
    pending = pending_findings(candidates, report.get("bugs") or [])
    if pending and heading == "重放未完成":
        bugs_html += "<div class=\"card\">重放没有跑完，这些候选还不能当成已确认缺陷。</div>"
    for item in pending:
        bugs_html += _pending_card(item, heading)
    s = report["summary"]
    return _HTML_TMPL.format(
        app=html.escape(report["app"]), policy=report["policy"],
        actions=s["actions_executed"], states=s["states_discovered"],
        cands=s["candidate_findings"], confirmed=s["confirmed_bugs"],
        llm=s["llm_calls"], tokens=s["pseudo_tokens"], secs=s["wall_seconds"],
        bugs_html=bugs_html)


def write_report(report: dict, json_path: str, html_path: str = None, candidates=None):
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    if html_path:
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(render_html(report, candidates))
