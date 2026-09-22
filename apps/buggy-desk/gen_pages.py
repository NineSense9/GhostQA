"""Generate the static HTML shells for BuggyDesk (run once).

    python gen_pages.py
"""
import os

PAGES = {
    "index.html": ("home", "北辰支持台·工作台"),
    "tickets.html": ("tickets", "工单队列"),
    "ticket.html": ("ticket", "工单详情"),
    "customers.html": ("customers", "客户"),
    "customer.html": ("customer", "客户详情"),
    "activity.html": ("activity", "客户动态"),
    "kb.html": ("kb", "知识库"),
    "article.html": ("article", "知识文章"),
    "reports.html": ("reports", "支持报表"),
    "team.html": ("team", "值班团队"),
    "settings.html": ("settings", "工作台设置"),
    "profile.html": ("profile", "个人资料"),
    "integrations.html": ("integrations", "通道集成"),
    "compose.html": ("compose", "新建工单"),
    "help.html": ("help", "值班说明"),
    "handbook.html": ("handbook", "现场手册"),
}

TMPL = """<!DOCTYPE html>
<html lang="zh">
<head><meta charset="utf-8"><title>{title}</title>
<style>
body {{ font-family: system-ui, "Microsoft YaHei", sans-serif; margin: 1.5rem 2rem; color: #1f2933; }}
a {{ margin-right: .7rem; }} button {{ margin: .2rem .3rem .2rem 0; padding: .3rem .8rem; }}
input, textarea {{ padding: .3rem; margin-right: .4rem; }} [role=alert] {{ color: #b42318; margin-top: .5rem; }}
.muted {{ color: #5b6770; font-size: .9rem; }} nav {{ margin-bottom: 1rem; }}
.card {{ border: 1px solid #d8dee4; padding: .8rem 1rem; margin: .6rem 0; border-radius: 4px; }}
h1 {{ font-size: 1.35rem; }}
</style></head>
<body data-page="{page}"><div id="root"></div><script src="app.js"></script></body>
</html>
"""

out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
os.makedirs(out, exist_ok=True)
for name, (page, title) in PAGES.items():
    with open(os.path.join(out, name), "w", encoding="utf-8", newline="\n") as f:
        f.write(TMPL.format(page=page, title=title))
    print("wrote", name)
