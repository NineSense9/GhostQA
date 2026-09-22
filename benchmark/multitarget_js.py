"""Frozen JS templates for v0.3.11 generated apps. __VOCAB__ is replaced."""

SHARED_HEAD = r"""
(function () {
  "use strict";
  const V = __VOCAB__;
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
"""

CRM_JS = SHARED_HEAD + r"""
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
"""

WIKI_JS = SHARED_HEAD + r"""
  const DEFAULT_STATE = {
    spaces: V.spaces.slice(),
    pages: V.pages.map(function (p) {
      return {id: p.id, title: p.title, space: p.space, backlinks: p.backlinks.slice(),
              tags: p.tags.slice(), published: true, unpublished: false,
              displayRev: "1", restoredRev: "1"};
    }),
    tags: V.tags.slice(),
    revisions: V.revisions.slice(),
    draft: {title: "", preview: 0, body: ""}
  };
  const state = load("bw_state", DEFAULT_STATE);
  function pageById(id) {
    return state.pages.find(function (p) { return p.id === id; }) || state.pages[0];
  }
  function spaceById(id) {
    return state.spaces.find(function (s) { return s.id === id; }) || state.spaces[0];
  }
  const pages = {
    home: function () {
      const root = document.getElementById("root");
      root.appendChild(el("h1", null, V.brand));
      root.appendChild(el("p", {class: "muted"}, "空间、页面、历史与反向链接。"));
      nav(root, [
        ["空间", "spaces.html", "nav_spaces"],
        ["页面", "pages.html", "nav_pages"],
        ["标签", "tags.html", "nav_tags"],
        ["编辑器", "editor.html", "nav_editor"],
        ["检索", "search.html", "nav_search"],
        ["设置", "settings.html", "nav_settings"],
        ["帮助", "help.html", "nav_help"]
      ]);
      root.appendChild(el("div", {"data-obs": "page_count"}, String(state.pages.length)));
      const box = el("input", {id: "search_box", "data-testid": "search_box", type: "search", placeholder: "检索"});
      const btn = el("button", {"data-testid": "search_btn"}, "搜索");
      btn.onclick = function () {
        if (box.value.length > 24) throw new RangeError("wiki search query too long");
        go("pages.html");
      };
      root.appendChild(box); root.appendChild(btn);
    },
    spaces: function () {
      const root = document.getElementById("root");
      root.appendChild(el("h1", null, "空间"));
      nav(root, [["返回首页", "index.html", "nav_home"]]);
      state.spaces.forEach(function (s) {
        root.appendChild(el("a", {href: "space.html?id=" + s.id, "data-testid": "space_" + s.id}, s.name));
        root.appendChild(el("br"));
      });
    },
    space: function () {
      const root = document.getElementById("root");
      const s = spaceById(qid("id") || "s1");
      root.appendChild(el("h1", null, s.name));
      nav(root, [["返回空间列表", "spaces.html", "nav_back_spaces"]]);
      state.pages.filter(function (p) { return p.space === s.id; }).forEach(function (p) {
        root.appendChild(el("a", {href: "page.html?id=" + p.id, "data-testid": "space_page_" + p.id}, p.title));
        root.appendChild(el("br"));
      });
    },
    pages: function () {
      const root = document.getElementById("root");
      root.appendChild(el("h1", null, "页面"));
      nav(root, [["返回首页", "index.html", "nav_home"], ["编辑器", "editor.html", "nav_editor"]]);
      state.pages.forEach(function (p) {
        root.appendChild(el("a", {href: "page.html?id=" + p.id, "data-testid": "wiki_page_" + p.id}, p.title));
        root.appendChild(el("br"));
      });
    },
    page: function () {
      const root = document.getElementById("root");
      const p = pageById(qid("id") || "p1");
      root.appendChild(el("h1", null, p.title));
      root.appendChild(el("div", {"data-obs": "page_title"}, p.title));
      root.appendChild(el("div", {"data-obs": "publish_state"}, p.published ? "已发布" : "未发布"));
      root.appendChild(el("div", {"data-obs": "unpublish_flag"}, p.unpublished ? "是" : "否"));
      nav(root, [
        ["返回页面列表", "pages.html", "nav_back_pages"],
        ["历史", "history.html?id=" + p.id, "nav_history"],
        ["反向链接", "backlinks.html?id=" + p.id, "nav_backlinks"],
        ["编辑", "editor.html?id=" + p.id, "nav_editor"]
      ]);
      const watch = el("button", {"data-testid": "btn_watch"}, "关注");
      const unpub = el("button", {"data-testid": "btn_unpublish"}, "取消发布");
      unpub.onclick = function () { p.unpublished = true; save("bw_state", state); go("page.html?id=" + p.id); };
      root.appendChild(watch); root.appendChild(unpub);
      root.appendChild(el("p", {class: "muted"}, "反向链接"));
      p.backlinks.forEach(function (rid) {
        const rel = pageById(rid);
        root.appendChild(el("a", {href: "page.html?id=" + rid, "data-testid": "backlink_" + rid}, rel.title));
        root.appendChild(el("br"));
      });
    },
    history: function () {
      const root = document.getElementById("root");
      const p = pageById(qid("id") || "p1");
      root.appendChild(el("h1", null, p.title + " · 历史"));
      nav(root, [
        ["返回页面", "page.html?id=" + p.id, "nav_back_page"],
        ["返回页面列表", "pages.html", "nav_back_pages"]
      ]);
      state.revisions.filter(function (r) { return r.page === p.id; }).forEach(function (r) {
        root.appendChild(el("a", {href: "revision.html?id=" + r.id, "data-testid": "rev_" + r.id}, "修订 " + r.n));
        root.appendChild(el("br"));
      });
    },
    revision: function () {
      const root = document.getElementById("root");
      const rid = qid("id") || "r1";
      const r = state.revisions.find(function (x) { return x.id === rid; }) || state.revisions[0];
      const p = pageById(r.page);
      root.appendChild(el("h1", null, "修订 " + r.n));
      root.appendChild(el("div", {"data-obs": "rev_n"}, r.n));
      root.appendChild(el("div", {"data-obs": "display_rev", id: "display_rev"}, p.displayRev));
      root.appendChild(el("div", {"data-obs": "restored_rev", id: "restored_rev"}, p.restoredRev));
      nav(root, [
        ["返回历史", "history.html?id=" + p.id, "nav_back_history"],
        ["返回页面", "page.html?id=" + p.id, "nav_back_page"]
      ]);
      const restore = el("button", {"data-testid": "btn_restore_rev"}, "恢复此修订");
      restore.onclick = function () {
        p.restoredRev = r.n;
        save("bw_state", state);
        document.getElementById("restored_rev").textContent = p.restoredRev;
      };
      root.appendChild(restore);
    },
    tags: function () {
      const root = document.getElementById("root");
      root.appendChild(el("h1", null, "标签"));
      nav(root, [["返回首页", "index.html", "nav_home"]]);
      state.tags.forEach(function (t) {
        root.appendChild(el("a", {href: "pages.html", "data-testid": "tag_" + t.id}, t.name));
        root.appendChild(el("br"));
      });
    },
    backlinks: function () {
      const root = document.getElementById("root");
      const p = pageById(qid("id") || "p1");
      root.appendChild(el("h1", null, "反向链接"));
      nav(root, [["返回页面", "page.html?id=" + p.id, "nav_back_page"]]);
      p.backlinks.forEach(function (rid) {
        const rel = pageById(rid);
        const card = el("div", {class: "card"});
        card.appendChild(el("div", {"data-obs": "link_kind"}, "内部"));
        card.appendChild(el("div", {"data-obs": "link_visibility"}, "公开"));
        card.appendChild(el("a", {href: "page.html?id=" + rid, "data-testid": "bl_" + rid}, rel.title));
        root.appendChild(card);
      });
    },
    editor: function () {
      const root = document.getElementById("root");
      root.appendChild(el("h1", null, "编辑器"));
      nav(root, [["返回页面列表", "pages.html", "nav_back_pages"]]);
      const input = el("input", {id: "page_title", "data-testid": "page_title", type: "text", placeholder: "标题"});
      const preview = el("button", {"data-testid": "btn_preview"}, "预览");
      const pub = el("button", {"data-testid": "btn_publish"}, "发布");
      const msg = el("div", {"data-obs": "form_msg", id: "form_msg"}, "");
      const pcount = el("div", {"data-obs": "preview_count", id: "preview_count"}, String(state.draft.preview));
      const draft = el("div", {"data-obs": "draft_len", id: "draft_len"}, String((input.value || "").length));
      preview.onclick = function () {
        state.draft.preview += 1;
        state.draft.body = input.value || "";
        save("bw_state", state);
        pcount.textContent = String(state.draft.preview);
        draft.textContent = String((input.value || "").length);
      };
      pub.onclick = function () { msg.textContent = "已发布"; };
      root.appendChild(input); root.appendChild(preview); root.appendChild(pub);
      root.appendChild(msg); root.appendChild(pcount); root.appendChild(draft);
    },
    search: function () { /* intentionally blank */ },
    settings: function () {
      const root = document.getElementById("root");
      root.appendChild(el("h1", null, "设置"));
      nav(root, [["返回首页", "index.html", "nav_home"]]);
      const test = el("button", {"data-testid": "btn_test_plugin"}, "测试插件");
      test.onclick = function () { throw new Error("wiki plugin handshake failed"); };
      const prev = el("button", {"data-testid": "btn_api_preview"}, "远程预览");
      prev.onclick = function () {
        fetch("/api/preview", {method: "POST"}).then(function (r) {
          root.appendChild(el("div", {role: "alert"}, "预览失败：" + r.status));
        });
      };
      root.appendChild(test); root.appendChild(prev);
    },
    help: function () {
      const root = document.getElementById("root");
      root.appendChild(el("h1", null, "快捷说明"));
      root.appendChild(el("a", {href: "shortcuts.html", "data-testid": "btn_shortcuts"}, "打开快捷键"));
    },
    shortcuts: function () {
      const root = document.getElementById("root");
      root.appendChild(el("h1", null, "快捷键"));
      root.appendChild(el("a", {href: "help.html", "data-testid": "btn_help"}, "返回快捷说明"));
    }
  };
  if (pages[page]) pages[page]();
})();
"""

OPS_JS = SHARED_HEAD + r"""
  const DEFAULT_STATE = {
    services: V.services.slice(),
    incidents: V.incidents.map(function (i) {
      return {id: i.id, title: i.title, service: i.service, related: i.related.slice(),
              status: "open", acked: false, reopened: false};
    }),
    alerts: V.alerts.map(function (a) {
      return {id: a.id, title: a.title, service: a.service,
              remaining: a.remaining, remainingDisplay: a.remainingDisplay};
    }),
    runbooks: V.runbooks.slice(),
    deploys: V.deploys.map(function (d) {
      return {id: d.id, service: d.service, version: d.version, rolled: false};
    })
  };
  const state = load("bo_state", DEFAULT_STATE);
  function svcById(id) {
    return state.services.find(function (s) { return s.id === id; }) || state.services[0];
  }
  function incById(id) {
    return state.incidents.find(function (i) { return i.id === id; }) || state.incidents[0];
  }
  function alertById(id) {
    return state.alerts.find(function (a) { return a.id === id; }) || state.alerts[0];
  }
  function deployById(id) {
    return state.deploys.find(function (d) { return d.id === id; }) || state.deploys[0];
  }
  function statusLabel(st) { return st === "closed" ? "已关闭" : "处理中"; }
  const pages = {
    home: function () {
      const root = document.getElementById("root");
      root.appendChild(el("h1", null, V.brand));
      root.appendChild(el("p", {class: "muted"}, "服务、事件、告警、发布与手册。"));
      nav(root, [
        ["服务", "services.html", "nav_services"],
        ["事件", "incidents.html", "nav_incidents"],
        ["告警", "alerts.html", "nav_alerts"],
        ["手册", "runbooks.html", "nav_runbooks"],
        ["发布", "deploys.html", "nav_deploys"],
        ["团队", "teams.html", "nav_teams"],
        ["新建事件", "compose.html", "nav_compose"],
        ["设置", "settings.html", "nav_settings"],
        ["帮助", "help.html", "nav_help"]
      ]);
      root.appendChild(el("div", {"data-obs": "open_incident_count"},
        String(state.incidents.filter(function (i) { return i.status === "open"; }).length)));
      const box = el("input", {id: "search_box", "data-testid": "search_box", type: "search", placeholder: "搜索事件"});
      const btn = el("button", {"data-testid": "search_btn"}, "搜索");
      btn.onclick = function () {
        if (box.value.length > 24) throw new RangeError("ops search query too long");
        go("incidents.html");
      };
      root.appendChild(box); root.appendChild(btn);
    },
    services: function () {
      const root = document.getElementById("root");
      root.appendChild(el("h1", null, "服务"));
      nav(root, [["返回工作台", "index.html", "nav_home"]]);
      state.services.forEach(function (s) {
        root.appendChild(el("a", {href: "service.html?id=" + s.id, "data-testid": "service_" + s.id}, s.name));
        root.appendChild(el("br"));
      });
    },
    service: function () {
      const root = document.getElementById("root");
      const s = svcById(qid("id") || "svc1");
      root.appendChild(el("h1", null, s.name));
      root.appendChild(el("div", {"data-obs": "service_name"}, s.name));
      nav(root, [
        ["返回服务列表", "services.html", "nav_back_services"],
        ["事件", "incidents.html?service=" + s.id, "nav_service_incidents"],
        ["告警", "alerts.html?service=" + s.id, "nav_service_alerts"],
        ["发布", "deploys.html?service=" + s.id, "nav_service_deploys"]
      ]);
    },
    incidents: function () {
      const root = document.getElementById("root");
      const sid = qid("service");
      root.appendChild(el("h1", null, "事件"));
      const links = [["返回工作台", "index.html", "nav_home"]];
      if (sid) links.push(["返回服务", "service.html?id=" + sid, "nav_back_service"]);
      else links.push(["服务", "services.html", "nav_services"]);
      nav(root, links);
      const rows = sid ? state.incidents.filter(function (i) { return i.service === sid; }) : state.incidents;
      rows.forEach(function (i) {
        root.appendChild(el("a", {href: "incident.html?id=" + i.id, "data-testid": "incident_" + i.id}, i.title));
        root.appendChild(el("br"));
      });
    },
    incident: function () {
      const root = document.getElementById("root");
      const i = incById(qid("id") || "i1");
      const s = svcById(i.service);
      root.appendChild(el("h1", null, i.title));
      root.appendChild(el("div", {"data-obs": "incident_title"}, i.title));
      root.appendChild(el("div", {"data-obs": "incident_status"}, statusLabel(i.status)));
      root.appendChild(el("div", {"data-obs": "ack_state"}, i.acked ? "是" : "否"));
      root.appendChild(el("div", {"data-obs": "reopen_state"}, i.reopened ? "是" : "否"));
      nav(root, [
        ["返回事件列表", "incidents.html?service=" + i.service, "nav_back_incidents"],
        ["所属服务", "service.html?id=" + s.id, "nav_owning_service"],
        ["工作台", "index.html", "nav_home"]
      ]);
      root.appendChild(el("p", {class: "muted"}, "关联事件"));
      i.related.forEach(function (rid) {
        const rel = incById(rid);
        root.appendChild(el("a", {href: "incident.html?id=" + rid, "data-testid": "related_" + rid}, rel.title));
        root.appendChild(el("br"));
      });
      const pin = el("button", {"data-testid": "btn_pin"}, "钉住");
      const ack = el("button", {"data-testid": "btn_ack"}, "确认");
      ack.onclick = function () { i.acked = true; i.status = "closed"; save("bo_state", state); go("incident.html?id=" + i.id); };
      const reopen = el("button", {"data-testid": "btn_reopen"}, "重新打开");
      reopen.onclick = function () { i.reopened = true; save("bo_state", state); go("incident.html?id=" + i.id); };
      root.appendChild(pin); root.appendChild(ack); root.appendChild(reopen);
    },
    alerts: function () {
      const root = document.getElementById("root");
      root.appendChild(el("h1", null, "告警"));
      nav(root, [["返回工作台", "index.html", "nav_home"], ["服务", "services.html", "nav_services"]]);
      state.alerts.forEach(function (a) {
        root.appendChild(el("a", {href: "alert.html?id=" + a.id, "data-testid": "alert_" + a.id}, a.title));
        root.appendChild(el("br"));
      });
    },
    alert: function () {
      const root = document.getElementById("root");
      const a = alertById(qid("id") || "al1");
      root.appendChild(el("h1", null, a.title));
      root.appendChild(el("div", {"data-obs": "silence_display", id: "silence_display"}, String(a.remainingDisplay)));
      root.appendChild(el("div", {"data-obs": "silence_remaining", id: "silence_remaining"}, String(a.remaining)));
      nav(root, [
        ["返回告警列表", "alerts.html", "nav_back_alerts"],
        ["所属服务", "service.html?id=" + a.service, "nav_owning_service"]
      ]);
      const silence = el("button", {"data-testid": "btn_silence"}, "静默");
      silence.onclick = function () {
        a.remaining = Math.max(0, a.remaining - 2);
        save("bo_state", state);
        document.getElementById("silence_remaining").textContent = String(a.remaining);
      };
      root.appendChild(silence);
    },
    runbooks: function () {
      const root = document.getElementById("root");
      root.appendChild(el("h1", null, "手册"));
      nav(root, [["返回工作台", "index.html", "nav_home"]]);
      state.runbooks.forEach(function (r) {
        root.appendChild(el("a", {href: "runbook.html?id=" + r.id, "data-testid": "runbook_" + r.id}, r.title));
        root.appendChild(el("br"));
      });
    },
    runbook: function () {
      const root = document.getElementById("root");
      const id = qid("id") || "rb1";
      const r = state.runbooks.find(function (x) { return x.id === id; }) || state.runbooks[0];
      root.appendChild(el("h1", null, r.title));
      nav(root, [["返回手册列表", "runbooks.html", "nav_back_runbooks"]]);
      root.appendChild(el("p", {class: "muted"}, "按步骤执行，不要跳过前置检查。"));
    },
    deploys: function () {
      const root = document.getElementById("root");
      const sid = qid("service");
      root.appendChild(el("h1", null, "发布历史"));
      const links = [["返回工作台", "index.html", "nav_home"]];
      if (sid) links.push(["返回服务", "service.html?id=" + sid, "nav_back_service"]);
      nav(root, links);
      const rows = sid ? state.deploys.filter(function (d) { return d.service === sid; }) : state.deploys;
      rows.forEach(function (d) {
        root.appendChild(el("a", {href: "deploy.html?id=" + d.id, "data-testid": "deploy_" + d.id}, d.version));
        root.appendChild(el("br"));
      });
    },
    deploy: function () {
      const root = document.getElementById("root");
      const d = deployById(qid("id") || "d1");
      root.appendChild(el("h1", null, "发布 " + d.version));
      root.appendChild(el("div", {"data-obs": "deploy_version"}, d.version));
      root.appendChild(el("div", {"data-obs": "rolled"}, d.rolled ? "是" : "否"));
      nav(root, [
        ["返回发布列表", "deploys.html?service=" + d.service, "nav_back_deploys"],
        ["所属服务", "service.html?id=" + d.service, "nav_owning_service"]
      ]);
    },
    teams: function () { /* intentionally blank */ },
    settings: function () {
      const root = document.getElementById("root");
      root.appendChild(el("h1", null, "设置"));
      nav(root, [["返回工作台", "index.html", "nav_home"]]);
      const test = el("button", {"data-testid": "btn_test_pager"}, "测试呼叫");
      test.onclick = function () { throw new Error("ops pager handshake failed"); };
      const pageBtn = el("button", {"data-testid": "btn_page"}, "发送寻呼");
      pageBtn.onclick = function () {
        fetch("/api/page", {method: "POST"}).then(function (r) {
          root.appendChild(el("div", {role: "alert"}, "寻呼失败：" + r.status));
        });
      };
      root.appendChild(test); root.appendChild(pageBtn);
    },
    compose: function () {
      const root = document.getElementById("root");
      root.appendChild(el("h1", null, "新建事件"));
      nav(root, [["返回工作台", "index.html", "nav_home"]]);
      const input = el("input", {id: "inc_title", "data-testid": "inc_title", type: "text", placeholder: "事件标题"});
      const btn = el("button", {"data-testid": "btn_create"}, "提交");
      const msg = el("div", {"data-obs": "form_msg", id: "form_msg"}, "");
      btn.onclick = function () { msg.textContent = "已创建"; };
      root.appendChild(input); root.appendChild(btn); root.appendChild(msg);
    },
    help: function () {
      const root = document.getElementById("root");
      root.appendChild(el("h1", null, "值班说明"));
      root.appendChild(el("a", {href: "playbook.html", "data-testid": "btn_playbook"}, "打开应急手册"));
    },
    playbook: function () {
      const root = document.getElementById("root");
      root.appendChild(el("h1", null, "应急手册"));
      root.appendChild(el("a", {href: "help.html", "data-testid": "btn_help"}, "返回值班说明"));
    }
  };
  if (pages[page]) pages[page]();
})();
"""

JS_BY_APP = {
    "buggy-crm": CRM_JS,
    "buggy-wiki": WIKI_JS,
    "buggy-ops": OPS_JS,
}
