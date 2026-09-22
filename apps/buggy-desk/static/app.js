/* BuggyDesk shared logic. Deterministic state in localStorage ("bd_state").
 * Reset = localStorage.clear() + reload.
 * Seeded defects are not labeled in the DOM or in client comments.
 */
(function () {
  "use strict";

  const DEFAULT_STATE = {
    tickets: [
      {id: "1001", title: "登录超时", status: "open", sla: 8, slaDisplay: 8,
       customer: "c1", related: ["1002", "1003"], notes: [], reopened: false},
      {id: "1002", title: "发票字段缺失", status: "open", sla: 6, slaDisplay: 6,
       customer: "c1", related: ["1001", "1003"], notes: [], reopened: false},
      {id: "1003", title: "导出任务卡住", status: "open", sla: 4, slaDisplay: 4,
       customer: "c2", related: ["1001"], notes: [], reopened: false}
    ],
    customers: [
      {id: "c1", name: "星河科技"},
      {id: "c2", name: "青木贸易"}
    ],
    articles: [
      {id: "a1", title: "如何重置会话"},
      {id: "a2", title: "发票字段说明"},
      {id: "a3", title: "导出失败排查"}
    ]
  };

  function load() {
    try {
      const s = JSON.parse(localStorage.getItem("bd_state"));
      if (s && typeof s === "object" && Array.isArray(s.tickets)) return s;
    } catch (e) { /* fall through */ }
    return JSON.parse(JSON.stringify(DEFAULT_STATE));
  }
  function save(s) { localStorage.setItem("bd_state", JSON.stringify(s)); }
  function el(tag, attrs, text) {
    const e = document.createElement(tag);
    if (attrs) for (const k in attrs) e.setAttribute(k, attrs[k]);
    if (text != null) e.textContent = text;
    return e;
  }
  function go(page) { location.href = page; }
  function qid(name) {
    try {
      return new URL(location.href).searchParams.get(name) || "";
    } catch (e) {
      return "";
    }
  }
  function ticketById(id) {
    return state.tickets.find((t) => t.id === id) || state.tickets[0];
  }
  function customerById(id) {
    return state.customers.find((c) => c.id === id) || state.customers[0];
  }
  function statusLabel(st) {
    if (st === "closed") return "已关闭";
    if (st === "open") return "处理中";
    return st;
  }

  const page = document.body.getAttribute("data-page");
  const state = load();

  function nav(root, links) {
    const bar = el("nav");
    (links || []).forEach(([t, href, tid]) => {
      const a = el("a", {href}, t);
      if (tid) a.setAttribute("data-testid", tid);
      bar.appendChild(a);
    });
    root.appendChild(bar);
  }

  const pages = {
    home() {
      const root = document.getElementById("root");
      root.appendChild(el("h1", null, "北辰支持台"));
      root.appendChild(el("p", {class: "muted"},
        "内部支持工作台：工单、客户资料、知识库与值班安排。"));
      nav(root, [
        ["工单队列", "tickets.html", "nav_tickets"],
        ["客户", "customers.html", "nav_customers"],
        ["知识库", "kb.html", "nav_kb"],
        ["值班团队", "team.html", "nav_team"],
        ["新建工单", "compose.html", "nav_compose"],
        ["报表", "reports.html", "nav_reports"],
        ["设置", "settings.html", "nav_settings"],
        ["个人资料", "profile.html", "nav_profile"],
        ["帮助", "help.html", "nav_help"],
        ["集成", "integrations.html", "nav_integrations"]
      ]);
      const openN = state.tickets.filter((t) => t.status === "open").length;
      root.appendChild(el("div", {"data-obs": "open_ticket_count"}, String(openN)));
      root.appendChild(el("p", {class: "muted"}, "今日开放工单见上。"));
      const box = el("input", {
        id: "search_box", "data-testid": "search_box", type: "search",
        placeholder: "搜索工单或客户"
      });
      const btn = el("button", {"data-testid": "search_btn"}, "搜索");
      btn.onclick = () => {
        const q = box.value;
        if (q.length > 24) {
          throw new RangeError("search query too long: max 24 chars");
        }
        go("tickets.html");
      };
      root.appendChild(box);
      root.appendChild(btn);
    },

    tickets() {
      const root = document.getElementById("root");
      root.appendChild(el("h1", null, "工单队列"));
      nav(root, [
        ["返回工作台", "index.html", "nav_home"],
        ["新建工单", "compose.html", "nav_compose"]
      ]);
      state.tickets.forEach((t) => {
        const a = el("a", {
          href: "ticket.html?id=" + t.id,
          "data-testid": "ticket_" + t.id
        }, "#" + t.id + " " + t.title);
        root.appendChild(a);
        root.appendChild(el("br"));
      });
    },

    ticket() {
      const root = document.getElementById("root");
      const t = ticketById(qid("id") || "1001");
      const cust = customerById(t.customer);
      root.appendChild(el("h1", null, "工单 #" + t.id));
      root.appendChild(el("div", {"data-obs": "ticket_title"}, t.title));
      root.appendChild(el("div", {"data-obs": "ticket_status"}, statusLabel(t.status)));
      root.appendChild(el("div", {"data-obs": "reopen_state"}, t.reopened ? "是" : "否"));
      root.appendChild(el("div", null, "剩余时限（小时）："));
      root.appendChild(el("div", {"data-obs": "sla_display", id: "sla_display"},
                          String(t.slaDisplay)));
      root.appendChild(el("div", {"data-obs": "sla_remaining", id: "sla_remaining"},
                          String(t.sla)));
      nav(root, [
        ["返回工单列表", "tickets.html", "nav_back_tickets"],
        ["客户 " + cust.name, "customer.html?id=" + cust.id, "nav_customer_" + cust.id]
      ]);
      root.appendChild(el("p", {class: "muted"}, "相关工单"));
      t.related.forEach((rid) => {
        const rel = ticketById(rid);
        const a = el("a", {
          href: "ticket.html?id=" + rid,
          "data-testid": "related_" + rid
        }, "#" + rid + " " + rel.title);
        root.appendChild(a);
        root.appendChild(el("br"));
      });
      const watch = el("button", {"data-testid": "btn_watch"}, "关注");
      const pause = el("button", {"data-testid": "btn_pause_sla"}, "暂停时限");
      pause.onclick = () => {
        t.sla = Math.max(0, t.sla - 2);
        save(state);
        document.getElementById("sla_remaining").textContent = String(t.sla);
      };
      const closeBtn = el("button", {"data-testid": "btn_close"}, "关闭工单");
      closeBtn.onclick = () => {
        t.status = "closed";
        save(state);
        go("ticket.html?id=" + t.id);
      };
      const reopen = el("button", {"data-testid": "btn_reopen"}, "重新打开");
      reopen.onclick = () => {
        t.reopened = true;
        save(state);
        go("ticket.html?id=" + t.id);
      };
      const note = el("button", {"data-testid": "btn_internal_note"}, "添加内部备注");
      note.onclick = () => {
        t.notes.push({kind: "内部", text: "内部排查记录", visibility: "客户可见"});
        save(state);
        go("ticket.html?id=" + t.id);
      };
      root.appendChild(watch);
      root.appendChild(pause);
      root.appendChild(closeBtn);
      root.appendChild(reopen);
      root.appendChild(note);
    },

    customers() {
      const root = document.getElementById("root");
      root.appendChild(el("h1", null, "客户"));
      nav(root, [["返回工作台", "index.html", "nav_home"]]);
      state.customers.forEach((c) => {
        const a = el("a", {
          href: "customer.html?id=" + c.id,
          "data-testid": "customer_" + c.id
        }, c.name);
        root.appendChild(a);
        root.appendChild(el("br"));
      });
    },

    customer() {
      const root = document.getElementById("root");
      const c = customerById(qid("id") || "c1");
      root.appendChild(el("h1", null, c.name));
      root.appendChild(el("div", {"data-obs": "customer_name"}, c.name));
      nav(root, [
        ["返回客户列表", "customers.html", "nav_back_customers"],
        ["客户动态", "activity.html?id=" + c.id, "nav_activity"]
      ]);
      const mine = state.tickets.filter((t) => t.customer === c.id);
      mine.forEach((t) => {
        const a = el("a", {
          href: "ticket.html?id=" + t.id,
          "data-testid": "cust_ticket_" + t.id
        }, "#" + t.id + " " + t.title);
        root.appendChild(a);
        root.appendChild(el("br"));
      });
    },

    activity() {
      const root = document.getElementById("root");
      const c = customerById(qid("id") || "c1");
      root.appendChild(el("h1", null, c.name + " · 动态"));
      nav(root, [
        ["返回客户", "customer.html?id=" + c.id, "nav_back_customer"]
      ]);
      const notes = [];
      state.tickets.filter((t) => t.customer === c.id).forEach((t) => {
        t.notes.forEach((n) => notes.push(n));
      });
      if (!notes.length) {
        root.appendChild(el("p", {class: "muted"}, "暂无动态。"));
        return;
      }
      notes.forEach((n) => {
        const card = el("div", {class: "card"});
        card.appendChild(el("div", {"data-obs": "note_kind"}, n.kind));
        card.appendChild(el("div", {"data-obs": "note_visibility"}, n.visibility));
        card.appendChild(el("div", null, n.text));
        root.appendChild(card);
      });
    },

    kb() {
      const root = document.getElementById("root");
      root.appendChild(el("h1", null, "知识库"));
      nav(root, [["返回工作台", "index.html", "nav_home"]]);
      state.articles.forEach((a) => {
        const link = el("a", {
          href: "article.html?id=" + a.id,
          "data-testid": "article_" + a.id
        }, a.title);
        root.appendChild(link);
        root.appendChild(el("br"));
      });
    },

    article() {
      const root = document.getElementById("root");
      const id = qid("id") || "a1";
      const a = state.articles.find((x) => x.id === id) || state.articles[0];
      root.appendChild(el("h1", null, a.title));
      root.appendChild(el("p", null, "标准处理步骤与常见原因说明。"));
      nav(root, [["返回知识库", "kb.html", "nav_back_kb"]]);
    },

    reports() {
      /* Intentionally empty body: the reports view fails to render. */
    },

    team() {
      const root = document.getElementById("root");
      root.appendChild(el("h1", null, "值班团队"));
      nav(root, [["返回工作台", "index.html", "nav_home"]]);
      [["u1", "陈可"], ["u2", "林夏"], ["u3", "周宁"]].forEach(([id, name]) => {
        const a = el("a", {
          href: "tickets.html",
          "data-testid": "agent_" + id
        }, name + "的队列");
        root.appendChild(a);
        root.appendChild(el("br"));
      });
    },

    settings() {
      const root = document.getElementById("root");
      root.appendChild(el("h1", null, "工作台设置"));
      nav(root, [["返回工作台", "index.html", "nav_home"]]);
      root.appendChild(el("p", {class: "muted"}, "通知、时区与工单默认优先级。"));
      const saveBtn = el("button", {"data-testid": "btn_save_settings"}, "保存设置");
      saveBtn.onclick = () => {
        root.appendChild(el("div", {role: "status"}, "已保存"));
      };
      root.appendChild(saveBtn);
    },

    profile() {
      const root = document.getElementById("root");
      root.appendChild(el("h1", null, "个人资料"));
      nav(root, [["返回工作台", "index.html", "nav_home"]]);
      root.appendChild(el("div", {"data-obs": "agent_name"}, "值班座席"));
      root.appendChild(el("p", {class: "muted"}, "当前班次：白班。"));
    },

    integrations() {
      const root = document.getElementById("root");
      root.appendChild(el("h1", null, "通道集成"));
      nav(root, [["返回工作台", "index.html", "nav_home"]]);
      root.appendChild(el("p", {class: "muted"}, "邮件、即时通讯与外部工单通道。"));
      const test = el("button", {"data-testid": "btn_test_conn"}, "测试连接");
      test.onclick = () => {
        throw new Error("channel handshake failed: missing adapter");
      };
      const hook = el("button", {"data-testid": "btn_webhook"}, "发送探测");
      hook.onclick = () => {
        fetch("/api/webhook", {method: "POST"})
          .then((r) => {
            root.appendChild(el("div", {role: "alert"}, "探测失败：" + r.status));
          })
          .catch(() => root.appendChild(el("div", {role: "alert"}, "网络错误")));
      };
      root.appendChild(test);
      root.appendChild(hook);
    },

    compose() {
      const root = document.getElementById("root");
      root.appendChild(el("h1", null, "新建工单"));
      nav(root, [["返回工作台", "index.html", "nav_home"]]);
      const input = el("input", {
        id: "ticket_title", "data-testid": "ticket_title",
        type: "text", placeholder: "工单标题"
      });
      const btn = el("button", {"data-testid": "btn_create"}, "提交工单");
      const msg = el("div", {"data-obs": "form_msg", id: "form_msg"}, "");
      btn.onclick = () => {
        msg.textContent = "工单已创建";
      };
      root.appendChild(input);
      root.appendChild(btn);
      root.appendChild(msg);
    },

    help() {
      const root = document.getElementById("root");
      root.appendChild(el("h1", null, "值班说明"));
      root.appendChild(el("a", {href: "handbook.html", "data-testid": "btn_handbook"},
                          "打开现场手册"));
    },

    handbook() {
      const root = document.getElementById("root");
      root.appendChild(el("h1", null, "现场手册"));
      root.appendChild(el("a", {href: "help.html", "data-testid": "btn_help"},
                          "返回值班说明"));
    }
  };

  if (pages[page]) pages[page]();
})();
