"""GhostQA Dashboard backend (v0.4 preview).

Pure presentation layer: it NEVER changes exploration/benchmark semantics.
Runs are executed in-process via run_exploration with the additive `on_step`
hook; events and artifacts land in dashboard_runs/<run_id>/ (gitignored).

    python -m dashboard.server [--port 8787]

API:
    GET  /                         -> single-page dashboard
    POST /api/runs                 -> start a run {url, policy, budget, spec, mock_llm}
    GET  /api/runs                 -> list runs
    GET  /api/runs/{id}            -> run status + summary
    GET  /api/runs/{id}/events?after=N  -> event stream (polling)
    GET  /api/runs/{id}/graph      -> current state graph
    GET  /api/runs/{id}/bugs       -> confirmed bugs (after validation)
    GET  /api/runs/{id}/report.html-> generated report (after run)
    GET  /api/runs/{id}/shot       -> latest browser screenshot (png)
    GET  /api/benchmarks           -> published benchmark metrics
    GET  /api/showcase             -> presentation-safe research evidence
"""
from __future__ import annotations

import argparse
import json
import os
import queue
import threading
import time
import traceback
import uuid

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, Response
from fastapi.staticfiles import StaticFiles

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUNS_DIR = os.path.join(ROOT, "dashboard_runs")
STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
PUBLISHED_DIR = os.path.join(ROOT, "experiments", "published")

os.makedirs(RUNS_DIR, exist_ok=True)

app = FastAPI(title="GhostQA Dashboard")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

RUNS: dict = {}
RUNS_LOCK = threading.Lock()


def _run_dir(run_id: str) -> str:
    return os.path.join(RUNS_DIR, run_id)


def _write_json(path: str, obj) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def _read_json(path: str, default=None):
    if not os.path.isfile(path):
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _index_shots(handle: "RunHandle", run_dir: str) -> None:
    shots = os.path.join(run_dir, "screenshots")
    if not os.path.isdir(shots):
        return
    for name in sorted(os.listdir(shots)):
        if not name.endswith(".png"):
            continue
        path = os.path.join(shots, name)
        handle.shot_index[name] = path
        handle.latest_shot = path


class RunHandle:
    def __init__(self, run_id: str, cfg: dict):
        self.id = run_id
        self.cfg = cfg
        self.status = "running"          # running | validating | done | error
        self.error = ""
        self.created = time.time()
        self.events: queue.Queue = queue.Queue()
        self.event_log: list = []
        self.latest_shot: str = ""
        self.graph: dict = {"nodes": [], "edges": []}
        self.summary: dict = {}
        self.bugs: list = []
        self.candidates: list = []
        self.report_html = ""
        self.shot_index: dict = {}       # basename -> abs path, for /shot/{name}

    def emit(self, ev: dict):
        """Consume one step event produced by run_exploration(on_step=...)."""
        ev = dict(ev)
        ev["seq"] = len(self.event_log)
        self.event_log.append(ev)
        for side in ("src", "dst"):
            shot = (ev.get(side) or {}).get("screenshot")
            if shot:
                self.shot_index[shot_basename(shot)] = shot
                self.latest_shot = shot
        try:
            with open(os.path.join(_run_dir(self.id), "events.jsonl"), "a",
                      encoding="utf-8") as f:
                f.write(json.dumps(ev, ensure_ascii=False) + "\n")
        except OSError:
            pass


def _do_run(handle: RunHandle):
    from ghostqa.__main__ import _make_policy
    from ghostqa.agent.gateway import MockLLM, NullLLM, OpenAICompatibleGateway
    from ghostqa.executor.playwright_web import PlaywrightWebExecutor
    from ghostqa.exploration.explorer import run_exploration
    from ghostqa.minimizer.ddmin import minimize_reproduction
    from ghostqa.oracle.engine import OracleEngine
    from ghostqa.oracle.spec import load_spec
    from ghostqa.replay.validator import validate_candidate
    from ghostqa.report.generator import build_report, write_report

    cfg = handle.cfg
    run_dir = _run_dir(handle.id)
    os.makedirs(run_dir, exist_ok=True)
    shots = os.path.join(run_dir, "screenshots")
    os.makedirs(shots, exist_ok=True)
    _write_json(os.path.join(run_dir, "meta.json"), {
        "cfg": cfg, "created": handle.created, "status": "running"})
    # Truncate so emit() can append incrementally.
    open(os.path.join(run_dir, "events.jsonl"), "w", encoding="utf-8").close()
    spec = load_spec(cfg["spec"]) if cfg.get("spec") else []
    oracle = OracleEngine(spec)
    spec_brief = "; ".join(f"{a['id']}: {a.get('desc', '')}" for a in spec)
    if cfg.get("mock_llm"):
        llm = MockLLM()
    else:
        gw = OpenAICompatibleGateway()
        llm = gw if gw.available else None
    policy = _make_policy(cfg.get("policy", "ghost"), llm, cfg.get("seed", 0))

    web = PlaywrightWebExecutor(cfg["url"], headless=True, screenshots_dir=shots)
    try:
        result = run_exploration(web, policy, int(cfg.get("budget", 60)),
                                 oracle=oracle, spec_brief=spec_brief,
                                 on_step=handle.emit)
        handle.candidates = [result.finding_artifact(f) for f in result.candidates]
        result.graph.save(os.path.join(run_dir, "graph.json"))
        handle.graph = result.graph.to_dict()
        with open(os.path.join(run_dir, "events.jsonl"), "w", encoding="utf-8") as f:
            for ev in handle.event_log:
                f.write(json.dumps(ev, ensure_ascii=False) + "\n")

        handle.status = "validating"
        _write_json(os.path.join(run_dir, "meta.json"), {
            "cfg": cfg, "created": handle.created, "status": "validating"})
        shared = web.share_handle()
        factory = lambda: PlaywrightWebExecutor(cfg["url"], headless=True,
                                                shared=shared)
        confirmed = []
        for finding in result.candidates:
            repro_actions = result.reproduction_actions(finding)
            vr = validate_candidate(factory, repro_actions, finding, oracle)
            if not vr.confirmed:
                continue
            repro = minimize_reproduction(factory, repro_actions, finding, oracle)
            confirmed.append(result.make_confirmed(finding, repro))
        handle.bugs = [b.to_dict() for b in confirmed]

        report = build_report(result, confirmed, cfg)
        write_report(report, os.path.join(run_dir, "report.json"),
                     os.path.join(run_dir, "report.html"))
        handle.report_html = os.path.join(run_dir, "report.html")
        handle.summary = {
            "actions": result.actions_executed,
            "states": len(result.graph.nodes),
            "candidates": len(result.candidates),
            "confirmed": len(confirmed),
            "llm_calls": result.llm_calls,
            "wall_seconds": round(result.wall_seconds, 1),
            "relocate_count": getattr(result, "relocate_count", 0),
            "similarity_counts": getattr(result, "similarity_counts", {}),
        }
        handle.status = "done"
        _write_json(os.path.join(run_dir, "meta.json"), {
            "cfg": cfg, "created": handle.created, "status": "done",
            "summary": handle.summary})
        _write_json(os.path.join(run_dir, "bugs.json"), handle.bugs)
        _write_json(os.path.join(run_dir, "candidates.json"), handle.candidates)
        handle.emit({"type": "run_done", "summary": handle.summary})
    except Exception:
        handle.status = "error"
        handle.error = traceback.format_exc(limit=5)
        _write_json(os.path.join(run_dir, "meta.json"), {
            "cfg": cfg, "created": handle.created, "status": "error",
            "error": handle.error})
        handle.emit({"type": "run_error", "error": handle.error})
    finally:
        web.close()


def _hydrate_runs() -> None:
    """Reload completed runs from dashboard_runs/ so a refresh keeps history."""
    if not os.path.isdir(RUNS_DIR):
        return
    for name in os.listdir(RUNS_DIR):
        run_dir = os.path.join(RUNS_DIR, name)
        if not os.path.isdir(run_dir):
            continue
        try:
            meta = _read_json(os.path.join(run_dir, "meta.json"), {}) or {}
            report = _read_json(os.path.join(run_dir, "report.json"), {}) or {}
        except Exception:
            continue
        if not meta and not report:
            continue
        try:
            cfg = meta.get("cfg") or report.get("config") or {}
            handle = RunHandle(name, cfg)
            handle.created = float(meta.get("created") or os.path.getmtime(run_dir))
            handle.status = meta.get("status") or ("done" if report else "error")
            if handle.status == "running":
                handle.status = "error"
                handle.error = "interrupted (server restarted)"
            handle.summary = meta.get("summary") or {}
            if not handle.summary and report.get("summary"):
                s = report["summary"]
                handle.summary = {
                    "actions": s.get("actions_executed", 0),
                    "states": s.get("states_discovered", 0),
                    "candidates": s.get("candidate_findings", 0),
                    "confirmed": s.get("confirmed_bugs", 0),
                    "llm_calls": s.get("llm_calls", 0),
                    "wall_seconds": s.get("wall_seconds", 0),
                }
            handle.bugs = _read_json(os.path.join(run_dir, "bugs.json"),
                                     report.get("bugs") or []) or []
            handle.candidates = _read_json(
                os.path.join(run_dir, "candidates.json"), []) or []
            events_path = os.path.join(run_dir, "events.jsonl")
            if os.path.isfile(events_path):
                with open(events_path, encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            handle.event_log.append(json.loads(line))
                        except json.JSONDecodeError:
                            continue
            handle.graph = _read_json(os.path.join(run_dir, "graph.json"),
                                      {"nodes": [], "edges": []}) or {
                "nodes": [], "edges": []}
            report_html = os.path.join(run_dir, "report.html")
            if os.path.isfile(report_html):
                handle.report_html = report_html
            _index_shots(handle, run_dir)
            RUNS[name] = handle
        except Exception:
            continue


_hydrate_runs()


@app.get("/favicon.ico")
def favicon():
    svg = (
        "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'>"
        "<rect width='32' height='32' rx='4' fill='#0a0b0d'/>"
        "<text x='16' y='22' text-anchor='middle' font-size='16' "
        "font-family='monospace' fill='#3ddad7'>G</text></svg>"
    )
    return Response(content=svg, media_type="image/svg+xml")


@app.get("/", response_class=HTMLResponse)
def index():
    with open(os.path.join(STATIC_DIR, "index.html"), encoding="utf-8") as f:
        return f.read()


@app.post("/api/runs")
def start_run(cfg: dict):
    if not cfg.get("url"):
        raise HTTPException(400, "url required")
    run_id = uuid.uuid4().hex[:8]
    handle = RunHandle(run_id, cfg)
    with RUNS_LOCK:
        RUNS[run_id] = handle
    threading.Thread(target=_do_run, args=(handle,), daemon=True).start()
    return {"run_id": run_id}


@app.get("/api/runs")
def list_runs():
    with RUNS_LOCK:
        return [{"id": h.id, "status": h.status, "cfg": h.cfg,
                 "summary": h.summary, "created": h.created}
                for h in RUNS.values()]


def _get(run_id: str) -> RunHandle:
    h = RUNS.get(run_id)
    if h is None:
        raise HTTPException(404, "run not found")
    return h


@app.get("/api/runs/{run_id}")
def run_status(run_id: str):
    h = _get(run_id)
    return {"id": h.id, "status": h.status, "error": h.error,
            "cfg": h.cfg, "summary": h.summary,
            "candidates": h.candidates, "events": len(h.event_log)}


@app.get("/api/runs/{run_id}/events")
def run_events(run_id: str, after: int = -1):
    h = _get(run_id)
    events = h.event_log[after + 1:] if after >= -1 else h.event_log
    return {"status": h.status, "events": [_public_event(run_id, e) for e in events]}


def shot_basename(path: str) -> str:
    """OS-agnostic basename. Windows paths must work on Linux CI."""
    if not path:
        return ""
    return str(path).replace("\\", "/").rsplit("/", 1)[-1]


def is_safe_shot_name(name: str) -> bool:
    """Reject path traversal in /shot/{name} on every OS."""
    if not name or not name.endswith(".png"):
        return False
    if "/" in name or "\\" in name or ".." in name:
        return False
    if shot_basename(name) != name:
        return False
    return True


def _public_event(run_id: str, ev: dict) -> dict:
    """Rewrite absolute screenshot paths into servable URLs."""
    ev = dict(ev)
    for side in ("src", "dst"):
        d = dict(ev.get(side) or {})
        shot = d.get("screenshot")
        d["screenshot"] = (f"/api/runs/{run_id}/shot/{shot_basename(shot)}"
                           if shot else "")
        ev[side] = d
    return ev


@app.get("/api/runs/{run_id}/graph")
def run_graph(run_id: str):
    h = _get(run_id)
    path = os.path.join(_run_dir(run_id), "graph.json")
    data = None
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = h.graph
    for node in data.get("nodes", []):
        shot = node.get("screenshot")
        node["screenshot"] = (f"/api/runs/{run_id}/shot/{shot_basename(shot)}"
                              if shot else "")
    for edge in data.get("edges", []):
        edge.pop("screenshot", None)
    return data


@app.get("/api/runs/{run_id}/bugs")
def run_bugs(run_id: str):
    return _get(run_id).bugs


@app.get("/api/runs/{run_id}/report.html")
def run_report(run_id: str):
    h = _get(run_id)
    if h.report_html and os.path.exists(h.report_html):
        return FileResponse(h.report_html)
    raise HTTPException(404, "report not ready")


@app.get("/api/runs/{run_id}/shot")
def run_shot(run_id: str):
    """Latest screenshot of this run."""
    h = _get(run_id)
    if h.latest_shot and os.path.exists(h.latest_shot):
        return FileResponse(h.latest_shot)
    raise HTTPException(404, "no screenshot yet")


@app.get("/api/runs/{run_id}/shot/{name}")
def run_shot_named(run_id: str, name: str):
    """Serve one screenshot by basename (path-traversal safe)."""
    h = _get(run_id)
    if not is_safe_shot_name(name):
        raise HTTPException(400, "bad name")
    path = h.shot_index.get(name) or os.path.join(_run_dir(run_id), "screenshots", name)
    if not os.path.isfile(path):
        raise HTTPException(404, "screenshot not found")
    return FileResponse(path, media_type="image/png")


@app.get("/api/showcase")
def showcase():
    """Committed research artifacts, curated for Overview / Evidence."""
    from dashboard.showcase import build_showcase
    return build_showcase()


@app.get("/api/benchmarks")
def benchmarks():
    out = []
    if os.path.isdir(PUBLISHED_DIR):
        for name in sorted(os.listdir(PUBLISHED_DIR)):
            mp = os.path.join(PUBLISHED_DIR, name, "metrics.json")
            if os.path.exists(mp):
                try:
                    with open(mp, encoding="utf-8") as f:
                        out.append({"name": name, "metrics": json.load(f)})
                except Exception:
                    pass
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8787)
    ap.add_argument("--host", default="127.0.0.1")
    args = ap.parse_args()
    import uvicorn
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
