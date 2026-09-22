# GhostQA dashboard demo

Two terminals. Keep BuggyShop running while the dashboard is open.

```bash
python apps/buggy-shop/server.py 3939
python -m dashboard.server --port 8787
```

Open http://127.0.0.1:8787/

The top bar has a sun/moon control. The first visit follows the system
color scheme (or light if that is unavailable). After you pick a theme,
it is stored as `ghostqa-theme` and kept on refresh.

## 2-minute walkthrough

1. **总览** — default view. What GhostQA does, then the current research card (v0.3.11 Outcome D: only buggy-wiki is evaluable; crm/ops do not engage the return-cycle mechanism) plus historical v0.3.10 / v0.3.9. Numbers come from committed published artifacts, not hardcoded demo data. Primary button is **运行一次探索**.
2. **实时探索** — click 载入 BuggyShop 示例 (fills URL / spec / budget / Ghost NoLLM; does not start). Click 启动探索. Watch the screenshot, state graph, and decision log. Theme can be switched while a run is in progress; the graph restyles with the page.
3. **研究证据** — from 总览, **查看实验记录**. v0.3.11 Outcome D plus v0.3.10 / v0.3.9 Outcome A, freeze / clean-clone status, copyable reproduce commands. Product default remains unchanged.

## Fallback if a live run fails

Stay on 总览 and 研究证据. Both read `experiments/published/` and do not need a running exploration.

Typical live-run failures: BuggyShop not on :3939, Playwright browser missing (`python -m playwright install chromium`).

## Visual QA

```bash
python tools/dashboard_visual_qa.py --dashboard-url http://127.0.0.1:8787 --output-dir ./tmp-visual-qa
```

`--skip-live` captures Overview / Evidence / Live idle only, in both themes.
