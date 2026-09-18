/* BuggyShop shared logic. Deterministic state in localStorage ("gq_state").
 * Reset = localStorage.clear() + reload. Seeded bugs marked BUG-Wx. */
(function () {
  "use strict";

  const DEFAULT_STATE = {
    cart: [{ name: "红富士苹果", price: 5, qty: 1 }],
    stock: 2,
    logged: false,
  };

  function load() {
    try {
      const s = JSON.parse(localStorage.getItem("gq_state"));
      if (s && typeof s === "object") return s;
    } catch (e) { /* fall through */ }
    return JSON.parse(JSON.stringify(DEFAULT_STATE));
  }
  function save(s) { localStorage.setItem("gq_state", JSON.stringify(s)); }
  function cartTotal(s) { return s.cart.reduce((t, i) => t + i.price * i.qty, 0); }
  function el(tag, attrs, text) {
    const e = document.createElement(tag);
    if (attrs) for (const k in attrs) e.setAttribute(k, attrs[k]);
    if (text != null) e.textContent = text;
    return e;
  }
  function go(page) { location.href = page; }

  const page = document.body.getAttribute("data-page");
  const state = load();

  const pages = {
    // ------------------------------------------------------------ home
    home() {
      const root = document.getElementById("root");
      root.appendChild(el("h1", null, "幽灵商城"));
      const nav = el("nav");
      [["商品列表", "products.html"], ["购物车", "cart.html"],
       ["注册", "register.html"], ["登录", "login.html"],
       ["个人中心", "profile.html"], ["活动专区", "promo.html"]].forEach(([t, href]) => {
        const a = el("a", { href }, t);
        nav.appendChild(a); nav.appendChild(document.createTextNode(" "));
      });
      root.appendChild(nav);
      root.appendChild(el("hr"));
      const box = el("input", { id: "search_box", "data-testid": "search_box",
                                type: "text", placeholder: "搜索商品" });
      const btn = el("button", { "data-testid": "search_btn" }, "搜索");
      btn.onclick = () => {
        const q = box.value;
        if (q.length > 20) {
          // BUG-W8: over-long query throws uncaught RangeError
          throw new RangeError("搜索关键词过长: max 20 chars");
        }
        go("products.html");
      };
      root.appendChild(box); root.appendChild(btn);
    },

    // ------------------------------------------------------------ products
    products() {
      const root = document.getElementById("root");
      root.appendChild(el("h1", null, "商品列表"));
      const a = el("a", { href: "detail.html", "data-testid": "item_apple" },
                   "红富士苹果 ¥5");
      root.appendChild(a);
      root.appendChild(el("br"));
      const help = el("a", { href: "help.html", "data-testid": "nav_help" }, "帮助中心");
      root.appendChild(help);
      root.appendChild(el("br"));
      root.appendChild(el("a", { href: "index.html" }, "返回首页"));
    },

    // ------------------------------------------------------------ detail
    detail() {
      const root = document.getElementById("root");
      root.appendChild(el("h1", null, "商品详情·苹果"));
      const stock = el("div", { "data-obs": "stock_num", id: "stock" },
                       String(state.stock));
      root.appendChild(el("div", null, "库存："));
      root.appendChild(stock);

      const add = el("button", { "data-testid": "btn_add" }, "加入购物车");
      add.onclick = () => {
        state.cart.push({ name: "红富士苹果", price: 5, qty: 1 });
        save(state);
        go("cart.html");
      };
      const fav = el("button", { "data-testid": "btn_fav" }, "收藏");
      // BUG-W3: favorite button has no handler at all (dead action)
      const buy = el("button", { "data-testid": "btn_buy" }, "立即购买");
      buy.onclick = () => {
        // BUG-W7: no stock guard -> stock can go negative
        state.stock -= 1;
        save(state);
        document.getElementById("stock").textContent = String(state.stock);
      };
      root.appendChild(add); root.appendChild(fav); root.appendChild(buy);
      root.appendChild(el("br"));
      root.appendChild(el("a", { href: "products.html" }, "返回列表"));
    },

    // ------------------------------------------------------------ cart
    cart() {
      const root = document.getElementById("root");
      root.appendChild(el("h1", null, "购物车"));
      const list = el("ul", { id: "cart_list" });
      root.appendChild(list);
      state.cart.forEach((item, idx) => {
        const li = el("li", null, item.name + " ¥");
        li.appendChild(el("span", { "data-obs": "cart_item_price" },
                          String(item.price * item.qty)));
        list.appendChild(li);
      });
      const total = el("div", { "data-obs": "cart_total", id: "cart_total" },
                       String(cartTotal(state)));
      root.appendChild(el("div", null, "总价：¥"));
      root.appendChild(total);

      const rm = el("button", { "data-testid": "btn_remove" }, "删除首个商品");
      rm.onclick = () => {
        // BUG-W5: removes item and re-renders list, but #cart_total is stale
        state.cart.shift();
        save(state);
        const ul = document.getElementById("cart_list");
        ul.innerHTML = "";
        state.cart.forEach((item) => {
          const li = el("li", null, item.name + " ¥");
          li.appendChild(el("span", { "data-obs": "cart_item_price" },
                            String(item.price * item.qty)));
          ul.appendChild(li);
        });
        // intentionally NOT updating #cart_total
      };
      const co = el("a", { href: "checkout.html", "data-testid": "btn_checkout" },
                    "去结算");
      root.appendChild(rm); root.appendChild(co);
      root.appendChild(el("br"));
      root.appendChild(el("a", { href: "index.html" }, "返回首页"));
    },

    // ------------------------------------------------------------ checkout
    checkout() {
      const root = document.getElementById("root");
      root.appendChild(el("h1", null, "订单结算"));
      root.appendChild(el("div", { "data-obs": "checkout_total" },
                          "应付：¥" + cartTotal(state)));
      const pay = el("button", { "data-testid": "btn_pay" }, "立即支付");
      pay.onclick = () => {
        if (state.cart.length === 0) {
          // BUG-W1: paying an empty cart throws uncaught error (state-dependent crash)
          setTimeout(() => {
            throw new Error("Cannot read properties of null (reading 'total')");
          }, 0);
          return;
        }
        // BUG-W2: backend always 500s
        fetch("/api/pay", { method: "POST" })
          .then((r) => {
            const t = el("div", { role: "alert" }, "支付失败：" + r.status);
            root.appendChild(t);
          })
          .catch(() => root.appendChild(el("div", { role: "alert" }, "网络错误")));
      };
      root.appendChild(pay);
      root.appendChild(el("br"));
      root.appendChild(el("a", { href: "cart.html" }, "返回购物车"));
    },

    // ------------------------------------------------------------ register
    register() {
      const root = document.getElementById("root");
      root.appendChild(el("h1", null, "注册"));
      const input = el("input", { id: "reg_user", "data-testid": "reg_user",
                                  type: "text", placeholder: "用户名" });
      const btn = el("button", { "data-testid": "btn_reg" }, "提交注册");
      const msg = el("div", { "data-obs": "form_msg", id: "reg_msg" }, "");
      btn.onclick = () => {
        // BUG-W6: always shows success even when username is empty
        msg.textContent = "注册成功";
      };
      root.appendChild(input); root.appendChild(btn); root.appendChild(msg);
      root.appendChild(el("br"));
      root.appendChild(el("a", { href: "index.html" }, "返回首页"));
    },

    // ------------------------------------------------------------ login
    login() {
      const root = document.getElementById("root");
      root.appendChild(el("h1", null, "登录"));
      const input = el("input", { id: "login_user", "data-testid": "login_user",
                                  type: "text", placeholder: "用户名" });
      const btn = el("button", { "data-testid": "btn_login" }, "登录");
      btn.onclick = () => { state.logged = true; save(state); go("profile.html"); };
      root.appendChild(input); root.appendChild(btn);
      root.appendChild(el("br"));
      root.appendChild(el("a", { href: "index.html" }, "返回首页"));
    },

    // ------------------------------------------------------------ profile
    profile() {
      const root = document.getElementById("root");
      root.appendChild(el("h1", null, "个人中心"));
      // BUG-W10: page renders user panel even when NOT logged in (no redirect)
      root.appendChild(el("div", { "data-obs": "login_state" },
                          state.logged ? "已登录" : "未登录"));
      root.appendChild(el("div", null, "我的订单 / 我的收藏 / 收货地址"));
      root.appendChild(el("a", { href: "index.html" }, "返回首页"));
    },

    // ------------------------------------------------------------ help loop
    help() {
      const root = document.getElementById("root");
      root.appendChild(el("h1", null, "帮助中心"));
      // BUG-W4: help <-> help2 loop, no way back to the shop
      root.appendChild(el("a", { href: "help2.html", "data-testid": "btn_more" },
                          "更多帮助"));
    },
    help2() {
      const root = document.getElementById("root");
      root.appendChild(el("h1", null, "更多帮助"));
      root.appendChild(el("a", { href: "help.html", "data-testid": "btn_back_help" },
                          "返回帮助"));
    },

    // ------------------------------------------------------------ promo
    promo() {
      // BUG-W9: promo page renders nothing (blank)
      document.getElementById("root").innerHTML = "";
    },
  };

  if (pages[page]) pages[page]();
})();
