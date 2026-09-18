"""Generate the static HTML shells for BuggyShop (run once).

    python gen_pages.py
"""
import os

PAGES = {
    "index.html": ("home", "幽灵商城·首页"),
    "products.html": ("products", "商品列表"),
    "detail.html": ("detail", "商品详情·苹果"),
    "cart.html": ("cart", "购物车"),
    "checkout.html": ("checkout", "订单结算"),
    "register.html": ("register", "注册"),
    "login.html": ("login", "登录"),
    "profile.html": ("profile", "个人中心"),
    "help.html": ("help", "帮助中心"),
    "help2.html": ("help2", "更多帮助"),
    "promo.html": ("promo", "活动专区"),
}

TMPL = """<!DOCTYPE html>
<html lang="zh">
<head><meta charset="utf-8"><title>{title}</title>
<style>
body {{ font-family: system-ui, "Microsoft YaHei", sans-serif; margin: 2rem; }}
a {{ margin-right: .6rem; }} button {{ margin: .2rem .3rem .2rem 0; padding: .3rem .8rem; }}
input {{ padding: .3rem; }} [role=alert] {{ color: #c00; margin-top: .5rem; }}
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
