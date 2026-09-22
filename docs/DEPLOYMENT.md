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
- `/api/showcase` still reports v0.3.9 Outcome A, product default unchanged,
  and the published return-cycle numbers
- public Overview, Evidence, Live, and a short Live run still work

Never put passwords in git, systemd units, or command logs.
