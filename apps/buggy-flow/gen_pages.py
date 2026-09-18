"""Generate the static HTML shells for BuggyFlow (run once).

    python gen_pages.py
"""
import os

PAGES = {
    "index.html": ("home", "BuggyFlow·首页"),
    "register.html": ("register", "注册"),
    "login.html": ("login", "登录"),
    "dashboard.html": ("dashboard", "工作台"),
    "wizard.html": ("wizard", "新建项目"),
    "project.html": ("project", "项目详情"),
    "members.html": ("members", "成员与权限"),
    "tasks.html": ("tasks", "任务"),
    "billing.html": ("billing", "账单"),
    "settings.html": ("settings", "系统设置"),
    "help.html": ("help", "帮助中心"),
    "docs.html": ("docs", "文档"),
    "about.html": ("about", "关于"),
    "reports.html": ("reports", "报表"),
    "history.html": ("history", "操作历史"),
    "changelog.html": ("changelog", "更新日志"),
}

TMPL = """<!DOCTYPE html>
<html lang="zh">
<head><meta charset="utf-8"><title>{title}</title>
<style>
body {{ font-family: system-ui, "Microsoft YaHei", sans-serif; margin: 2rem; }}
a {{ margin-right: .6rem; }} button {{ margin: .2rem .3rem .2rem 0; padding: .3rem .8rem; }}
input {{ padding: .3rem; }} [role=alert] {{ color: #c00; margin-top: .5rem; }}
.muted {{ color: #666; font-size: .9rem; }}
nav {{ margin-bottom: 1rem; }}
</style></head>
<body data-page="{page}"><div id="root"></div><script src="app.js"></script></body>
</html>
"""

out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
os.makedirs(out, exist_ok=True)
for name, (page, title) in PAGES.items():
    with open(os.path.join(out, name), "w", encoding="utf-8") as f:
        f.write(TMPL.format(page=page, title=title))
    print("wrote", name)
