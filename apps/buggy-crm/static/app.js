
(function () {
  "use strict";
  const V = {"app":"buggy-crm","seed":1059087843,"seed_hex":"3f2065e3","brand":"北衡客户","accounts":[{"id":"a1","name":"临江制造","related":["a2","a3"]},{"id":"a2","name":"北原能源","related":["a1","a3"]},{"id":"a3","name":"星河科技","related":["a1"]}],"contacts":[{"id":"c1","name":"苏晚","account":"a1"},{"id":"c2","name":"韩澈","account":"a1"},{"id":"c3","name":"沈予","account":"a2"}],"opps":[{"id":"o1","title":"续约扩容","account":"a1","related":["o2","o3"]},{"id":"o2","title":"年度框架","account":"a1","related":["o1"]},{"id":"o3","title":"服务升级","account":"a2","related":["o1"]}],"team":[{"id":"u1","name":"苏晚"},{"id":"u2","name":"韩澈"},{"id":"u3","name":"沈予"}]};
  function load(key, fallback) {
    try {
      const s = JSON.parse(localStorage.getItem(key));
      if (s && typeof s === "object") return s;
    } catch (e) { /* fall through */ }
    return JSON.parse(JSON.stringify(fallback));
  }
  function save(key, s) { localStorage.setItem(key, JSON.stringify(s)); }
  function el(tag, attrs, text) {
    const e = document.createElement(tag);
    if (attrs) for (const k in attrs) e.setAttribute(k, attrs[k]);
    if (text != null) e.textContent = text;
    return e;
  }
  function go(page) { location.href = page; }
  function qid(name) {
    try { return new URL(location.href).searchParams.get(name) || ""; }
    catch (e) { return ""; }
  }
  function nav(root, links) {
    const bar = el("nav");
    (links || []).forEach(function (item) {
      const a = el("a", {href: item[1]}, item[0]);
      if (item[2]) a.setAttribute("data-testid", item[2]);
      bar.appendChild(a);
    });
    root.appendChild(bar);
  }
  const page = document.body.getAttribute("data-page");

  const DEFAULT_STATE = {
    accounts: V.accounts.map(function (a) {
      return {id: a.id, name: a.name, related: a.related.slice(),
              forecast: 8, forecastDisplay: 8, status: "open",
              reopened: false, notes: []};
    }),
    contacts: V.contacts.map(function (c) {
      return {id: c.id, name: c.name, account: c.account};
    }),
    opps: V.opps.map(function (o) {
      return {id: o.id, title: o.title, account: o.account,
              related: o.related.slice(), status: "open", reopened: false};
    })
  };
  const state = load("bc_state", DEFAULT_STATE);
  function accById(id) {
    return state.accounts.find(function (a) { return a.id === id; }) || state.accounts[0];
  }
  function contactById(id) {
    return state.contacts.find(function (c) { return c.id === id; }) || state.contacts[0];
  }
  function oppById(id) {
    return state.opps.find(function (o) { return o.id === id; }) || state.opps[0];
  }
  function statusLabel(st) { return st === "closed" ? "已关闭" : "跟进中"; }
  const pages = {
    home: function () {
      const root = document.getElementById("root");
      root.appendChild(el("h1", null, V.brand));
      root.appendChild(el("p", {class: "muted"}, "客户、联系人、商机与活动。"));
      nav(root, [
        ["客户", "accounts.html", "nav_accounts"],
        ["联系人", "contacts.html", "nav_contacts"],
        ["商机", "opportunities.html", "nav_opportunities"],
        ["活动", "activity.html", "nav_activity"],
        ["新建商机", "compose.html", "nav_compose"],
        ["管道", "pipeline.html", "nav_pipeline"],
        ["团队", "team.html", "nav_team"],
        ["设置", "settings.html", "nav_settings"],
        ["帮助", "help.html", "nav_help"]
      ]);
      root.appendChild(el("div", {"data-obs": "account_count"}, String(state.accounts.length)));
      const box = el("input", {id: "search_box", "data-testid": "search_box", type: "search", placeholder: "搜索客户"});
      const btn = el("button", {"data-testid": "search_btn"}, "搜索");
      btn.onclick = function () {
        if (box.value.length > 24) throw new RangeError("crm search query too long");
        go("accounts.html");
      };
      root.appendChild(box); root.appendChild(btn);
    },
    accounts: function () {
      const root = document.getElementById("root");
      root.appendChild(el("h1", null, "客户"));
      nav(root, [["返回工作台", "index.html", "nav_home"], ["新建商机", "compose.html", "nav_compose"]]);
      state.accounts.forEach(function (a) {
        root.appendChild(el("a", {href: "account.html?id=" + a.id, "data-testid": "account_" + a.id}, a.name));
        root.appendChild(el("br"));
      });
    },
    account: function () {
      const root = document.getElementById("root");
      const a = accById(qid("id") || "a1");
      root.appendChild(el("h1", null, a.name));
      root.appendChild(el("div", {"data-obs": "account_name"}, a.name));
      root.appendChild(el("div", {"data-obs": "account_status"}, statusLabel(a.status)));
      root.appendChild(el("div", {"data-obs": "reopen_state"}, a.reopened ? "是" : "否"));
      root.appendChild(el("div", {"data-obs": "forecast_display", id: "forecast_display"}, String(a.forecastDisplay)));
      root.appendChild(el("div", {"data-obs": "forecast_remaining", id: "forecast_remaining"}, String(a.forecast)));
      nav(root, [
        ["返回客户列表", "accounts.html", "nav_back_accounts"],
        ["联系人", "contacts.html", "nav_contacts"],
        ["活动", "activity.html?id=" + a.id, "nav_activity"]
      ]);
      root.appendChild(el("p", {class: "muted"}, "关联客户"));
      a.related.forEach(function (rid) {
        const rel = accById(rid);
        root.appendChild(el("a", {href: "account.html?id=" + rid, "data-testid": "related_" + rid}, rel.name));
        root.appendChild(el("br"));
      });
      const watch = el("button", {"data-testid": "btn_watch"}, "关注");
      const pause = el("button", {"data-testid": "btn_pause_forecast"}, "下调预测");
      pause.onclick = function () {
        a.forecast = Math.max(0, a.forecast - 2);
        save("bc_state", state);
        document.getElementById("forecast_remaining").textContent = String(a.forecast);
      };
      const closeBtn = el("button", {"data-testid": "btn_close"}, "关闭");
      closeBtn.onclick = function () { a.status = "closed"; save("bc_state", state); go("account.html?id=" + a.id); };
      const reopen = el("button", {"data-testid": "btn_reopen"}, "重新打开");
      reopen.onclick = function () { a.reopened = true; save("bc_state", state); go("account.html?id=" + a.id); };
      const note = el("button", {"data-testid": "btn_internal_note"}, "内部备注");
      note.onclick = function () {
        a.notes.push({kind: "内部", visibility: "客户可见", text: "内部跟进"});
        save("bc_state", state); go("account.html?id=" + a.id);
      };
      root.appendChild(watch); root.appendChild(pause); root.appendChild(closeBtn);
      root.appendChild(reopen); root.appendChild(note);
    },
    contacts: function () {
      const root = document.getElementById("root");
      root.appendChild(el("h1", null, "联系人"));
      nav(root, [["返回工作台", "index.html", "nav_home"]]);
      state.contacts.forEach(function (c) {
        root.appendChild(el("a", {href: "contact.html?id=" + c.id, "data-testid": "contact_" + c.id}, c.name));
        root.appendChild(el("br"));
      });
    },
    contact: function () {
      const root = document.getElementById("root");
      const c = contactById(qid("id") || "c1");
      const a = accById(c.account);
      root.appendChild(el("h1", null, c.name));
      root.appendChild(el("div", {"data-obs": "contact_name"}, c.name));
      nav(root, [
        ["返回联系人列表", "contacts.html", "nav_back_contacts"],
        ["所属客户", "account.html?id=" + a.id, "nav_account_" + a.id]
      ]);
    },
    opportunities: function () {
      const root = document.getElementById("root");
      root.appendChild(el("h1", null, "商机"));
      nav(root, [["返回工作台", "index.html", "nav_home"], ["新建商机", "compose.html", "nav_compose"]]);
      state.opps.forEach(function (o) {
        root.appendChild(el("a", {href: "opportunity.html?id=" + o.id, "data-testid": "opp_" + o.id}, o.title));
        root.appendChild(el("br"));
      });
    },
    opportunity: function () {
      const root = document.getElementById("root");
      const o = oppById(qid("id") || "o1");
      root.appendChild(el("h1", null, o.title));
      root.appendChild(el("div", {"data-obs": "opp_title"}, o.title));
      root.appendChild(el("div", {"data-obs": "opp_status"}, statusLabel(o.status)));
      nav(root, [
        ["返回商机列表", "opportunities.html", "nav_back_opportunities"],
        ["所属客户", "account.html?id=" + o.account, "nav_account_" + o.account]
      ]);
      o.related.forEach(function (rid) {
        const rel = oppById(rid);
        root.appendChild(el("a", {href: "opportunity.html?id=" + rid, "data-testid": "related_opp_" + rid}, rel.title));
        root.appendChild(el("br"));
      });
    },
    activity: function () {
      const root = document.getElementById("root");
      const id = qid("id") || "a1";
      const a = accById(id);
      root.appendChild(el("h1", null, a.name + " · 活动"));
      nav(root, [["返回客户", "account.html?id=" + a.id, "nav_back_account"]]);
      const notes = [];
      state.accounts.forEach(function (x) { x.notes.forEach(function (n) { notes.push(n); }); });
      if (!notes.length) { root.appendChild(el("p", {class: "muted"}, "暂无活动。")); return; }
      notes.forEach(function (n) {
        const card = el("div", {class: "card"});
        card.appendChild(el("div", {"data-obs": "note_kind"}, n.kind));
        card.appendChild(el("div", {"data-obs": "note_visibility"}, n.visibility));
        root.appendChild(card);
      });
    },
    pipeline: function () { /* intentionally blank */ },
    team: function () {
      const root = document.getElementById("root");
      root.appendChild(el("h1", null, "团队"));
      nav(root, [["返回工作台", "index.html", "nav_home"]]);
      (V.team || []).forEach(function (u) {
        root.appendChild(el("a", {href: "accounts.html", "data-testid": "agent_" + u.id}, u.name + "的客户"));
        root.appendChild(el("br"));
      });
    },
    settings: function () {
      const root = document.getElementById("root");
      root.appendChild(el("h1", null, "设置"));
      nav(root, [["返回工作台", "index.html", "nav_home"]]);
      const test = el("button", {"data-testid": "btn_test_sync"}, "测试同步");
      test.onclick = function () { throw new Error("crm sync handshake failed"); };
      const exp = el("button", {"data-testid": "btn_export"}, "导出");
      exp.onclick = function () {
        fetch("/api/export", {method: "POST"}).then(function (r) {
          root.appendChild(el("div", {role: "alert"}, "导出失败：" + r.status));
        });
      };
      root.appendChild(test); root.appendChild(exp);
    },
    compose: function () {
      const root = document.getElementById("root");
      root.appendChild(el("h1", null, "新建商机"));
      nav(root, [["返回工作台", "index.html", "nav_home"]]);
      const input = el("input", {id: "opp_title", "data-testid": "opp_title", type: "text", placeholder: "商机标题"});
      const btn = el("button", {"data-testid": "btn_create"}, "提交");
      const msg = el("div", {"data-obs": "form_msg", id: "form_msg"}, "");
      btn.onclick = function () { msg.textContent = "已创建"; };
      root.appendChild(input); root.appendChild(btn); root.appendChild(msg);
    },
    help: function () {
      const root = document.getElementById("root");
      root.appendChild(el("h1", null, "使用说明"));
      root.appendChild(el("a", {href: "handbook.html", "data-testid": "btn_handbook"}, "打开现场手册"));
    },
    handbook: function () {
      const root = document.getElementById("root");
      root.appendChild(el("h1", null, "现场手册"));
      root.appendChild(el("a", {href: "help.html", "data-testid": "btn_help"}, "返回使用说明"));
    }
  };
  if (pages[page]) pages[page]();
})();
