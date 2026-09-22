
(function () {
  "use strict";
  const V = {"app":"buggy-ops","seed":4252390393,"seed_hex":"fd7653f9","brand":"朔风值守","services":[{"id":"svc1","name":"登录中枢"},{"id":"svc2","name":"结算网关"},{"id":"svc3","name":"消息总线"}],"incidents":[{"id":"i1","title":"队列堆积","service":"svc1","related":["i2","i3"]},{"id":"i2","title":"证书将过期","service":"svc1","related":["i1"]},{"id":"i3","title":"错误突增","service":"svc2","related":["i1"]}],"alerts":[{"id":"al1","title":"P2 队列堆积","service":"svc1","remaining":6,"remainingDisplay":6},{"id":"al2","title":"P3 证书将过期","service":"svc2","remaining":4,"remainingDisplay":4}],"runbooks":[{"id":"rb1","title":"证书轮换"},{"id":"rb2","title":"限流开关"},{"id":"rb3","title":"回滚步骤"}],"deploys":[{"id":"d1","service":"svc1","version":"1.4.2"},{"id":"d2","service":"svc1","version":"1.4.1"},{"id":"d3","service":"svc2","version":"2.0.0"}],"team":[{"id":"u1","name":"陈可"},{"id":"u2","name":"韩澈"}]};
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
