# GhostQA dashboard demo

Two terminals. Keep BuggyShop running while the dashboard is open.

```bash
python apps/buggy-shop/server.py 3939
python -m dashboard.server --port 8787
```

Open http://127.0.0.1:8787/

## 2-minute walkthrough

1. **总览** — default view. What GhostQA does, then the v0.3.9 return-cycle repair (6 → 22 states, 116 → 15 return tries). Numbers come from committed published artifacts, not hardcoded demo data.
2. **实时探索** — click 载入 BuggyShop 示例 (fills URL / spec / budget / Ghost NoLLM; does not start). Click 启动探索. Watch the screenshot, state graph, and decision log.
3. **研究证据** — Outcome A, freeze / clean-clone status, copyable reproduce commands.

## Fallback if a live run fails

Stay on 总览 and 研究证据. Both read `experiments/published/` and do not need a running exploration.

Typical live-run failures: BuggyShop not on :3939, Playwright browser missing (`python -m playwright install chromium`).

## Visual QA (optional)

```bash
python tools/dashboard_visual_qa.py --dashboard-url http://127.0.0.1:8787 --output-dir ./tmp-visual-qa
```

`--skip-live` captures Overview / Evidence / Live idle only.
