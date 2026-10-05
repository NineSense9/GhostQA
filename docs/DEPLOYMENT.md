# GhostQA public release

After every accepted code, frontend, or research update:

1. Run the relevant tests.
2. If the UI changed, run visual QA (`tools/dashboard_visual_qa.py`).
3. Commit on `main`.
4. Push `main`. Confirm local `HEAD` equals `origin/main`.
5. Deploy **that exact SHA** to the public server.
6. Verify the public URL in a real browser, both themes if UI changed.
7. Record the commit SHA and deployment status.

A change is not done when it only works locally.

## Public target

- Dashboard: http://39.106.200.173:8787/
- Showcase JSON: http://39.106.200.173:8787/api/showcase

Remote layout:

- App: `/opt/ghostqa/app`
- Venv: `/opt/ghostqa/venv`
- Playwright browsers: `/opt/ghostqa/playwright`
- Optional Chromium binary override: `GHOSTQA_CHROMIUM_EXECUTABLE` (systemd). Use this when the venv Playwright build expects `chromium_headless_shell` but the host already has `chromium-1243/chrome-linux64/chrome`.
- Service user: `ghostqa`
- Units: `ghostqa-dashboard.service`, `ghostqa-buggyshop.service`
- BuggyShop: `127.0.0.1:3939` (loopback only)
- Dashboard: `0.0.0.0:8787`

## Deploy the pushed SHA

From the operator machine, using the local SSH helper (password is not
stored in this repository):

```text
cd /opt/ghostqa/app
git fetch origin
git checkout main
git reset --hard <PUSHED_SHA>
# pip install only if dependencies changed
sudo systemctl restart ghostqa-buggyshop
sudo systemctl restart ghostqa-dashboard
git rev-parse HEAD   # must equal local HEAD and origin/main
```

Do not reinstall Chromium unless the browser runtime is actually missing.
If Live fails with `chromium_headless_shell` not found, point systemd at the
installed Chrome instead of downloading a second browser:

`GHOSTQA_CHROMIUM_EXECUTABLE=/opt/ghostqa/playwright/chromium-1243/chrome-linux64/chrome`

Confirm:

- both units `active` and `enabled`
- port 3939 is loopback-only
- port 8787 is reachable publicly
- `/api/showcase` and the Evidence page agree with the published experiment
  versions (through v0.3.38); research candidates remain separate from the
  unchanged product default
- public Overview, Evidence, Live, and a short Live run still work

Never put passwords in git, systemd units, or command logs.

## 录制前主流程与健康检查

主录制使用 dashboard 自带的购物车案例，不需要先启动 BuggyShop：

```bash
curl -fsS http://127.0.0.1:8787/cases/cart.html >/dev/null
python -m pytest -q tests/test_dashboard.py tests/test_web_integration.py
```

浏览器中依次验证首页、实时探索和报告链接。连续运行 3 次购物车案例，确认阶段栏进入探索、候选、重放、最小化和报告；主案例通常产生 1 个候选、1 个确认缺陷和 1 步最小路径。模型可用时，AI 观测中应至少出现一次门控；模型不可用时，页面必须明确显示程序评分降级。

## 超时和 partial

单候选重放的导航超时只影响该候选。服务继续处理后续候选，最终状态为 `partial`；未完成候选进入报告的“重放未完成”区域，不计入已确认缺陷。停止操作仍发生在下一步或下一候选之间，不中断已经发出的浏览器调用。

## 端口约束

PPT 预览使用 5062，已有本地服务使用 8873。启动 dashboard 或临时验证服务前先检查端口占用，选择其他空闲端口，避免覆盖这两个服务。

## 打包前页面检查

```bash
python -m pytest -q tests/test_dashboard.py tests/test_dashboard_layout.py
python tools/dashboard_submission_qa.py --url http://127.0.0.1:8787 --out output/playwright/submission-local --mock
python tools/dashboard_submission_qa.py --url http://39.106.200.173:8787 --out output/playwright/submission-public --cart-repeats 3
```

第二条命令用 Mock 检查本地完整流程，不能作为真实模型收益证据；第三条命令关闭 Mock，保存实际公网运行记录。每组案例独立记录 run_id、配置、状态、事件、图、缺陷和报告，刷新后检查是否恢复同一运行。

界面验收覆盖 1280×720、1366×768、1920×1080、1024×768 和 390×844。展开缺陷后，断言、观测值及复现路径均应可读；右栏统一滚动，不截断卡片。截图默认显示完整画面，“放大画面”后可以滚动查看原始截图。状态图和日志不应相互覆盖。

多页面目录的长路径可能需要大量重放才能完成最小化，不能把探索阶段的 `wall_seconds` 当成整次运行耗时。验收脚本默认等待每组运行 30 分钟，可用 `--run-timeout` 调整；等待超时只结束验收等待，不会取消后端运行。应保留 run_id，继续检查事件是否推进，等终态后再记录确认结果。

状态图随画布大小重新适配，完整节点范围不能被最低缩放比例裁切。报告页也要在窄屏打开检查：长地址应换行，路径长度表格不得把页面撑出屏幕。

仅修改 HTML、CSS、前端脚本时，文件由服务即时读取，可以先更新静态资源而不重启执行中的服务；修改 Python 服务代码时，必须等所有运行进入终态后再重启。部署记录分别保存源码 SHA、静态资源哈希、服务状态和本次验收 run_id。
