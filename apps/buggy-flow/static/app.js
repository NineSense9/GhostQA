/* BuggyFlow shared logic. Deterministic state in localStorage ("bf_state").
 * Reset = localStorage.clear() + reload.
 * Seeded bugs are NOT marked with data-bug-id (tester/judge isolation).
 */
(function () {
  "use strict";

  const DEFAULT_STATE = {
    registered: false,
    username: "",
    logged: false,
    wizardStep: 1,
    wizardName: "",
    wizardType: "内部",
    project: null,
    dashName: "",
    archived: false,
    members: [],
    memberCountDisplay: 0,
    tasks: [],
    billQty: 1,
    coupon: false,
    billPriceDisplay: 100,
    guestCanEdit: "false",
    notify: false,
  };

  function load() {
    try {
      const s = JSON.parse(localStorage.getItem("bf_state"));
      if (s && typeof s === "object") return s;
    } catch (e) { /* fall through */ }
    return JSON.parse(JSON.stringify(DEFAULT_STATE));
  }
  function save(s) { localStorage.setItem("bf_state", JSON.stringify(s)); }
  function el(tag, attrs, text) {
    const e = document.createElement(tag);
    if (attrs) for (const k in attrs) e.setAttribute(k, attrs[k]);
    if (text != null) e.textContent = text;
    return e;
  }
  function go(page) { location.href = page; }
  function expectedPrice(s) {
    const base = 100 * s.billQty;
    return s.coupon ? Math.round(base * 0.8) : base;
  }

  const page = document.body.getAttribute("data-page");
  const state = load();

  function nav(root, extras) {
    const bar = el("nav");
    const links = extras || [];
    links.forEach(([t, href, tid]) => {
      const a = el("a", { href }, t);
      if (tid) a.setAttribute("data-testid", tid);
      bar.appendChild(a);
    });
    root.appendChild(bar);
    root.appendChild(el("hr"));
  }

  const pages = {
    home() {
      const root = document.getElementById("root");
      root.appendChild(el("h1", null, "BuggyFlow 项目工作台"));
      root.appendChild(el("p", { "class": "muted" },
        "团队项目管理：创建项目、成员权限、任务与账单。"));
      nav(root, [
        ["登录", "login.html", "nav_login"],
        ["注册", "register.html", "nav_register"],
        ["帮助中心", "help.html", "nav_help"],
        ["关于", "about.html", "nav_about"],
        ["系统设置", "settings.html", "nav_settings"],
      ]);
    },

    register() {
      const root = document.getElementById("root");
      root.appendChild(el("h1", null, "注册"));
      nav(root, [["首页", "index.html", "nav_home"]]);
      const input = el("input", { id: "reg_user", "data-testid": "reg_user",
                                  type: "text", placeholder: "用户名" });
      const btn = el("button", { "data-testid": "btn_reg" }, "提交注册");
      const msg = el("div", { "data-obs": "form_msg", id: "reg_msg" }, "");
      btn.onclick = () => {
        state.username = input.value;
        state.registered = true;
        save(state);
        // BUG-D4: always shows success even when username is empty
        msg.textContent = "注册成功";
      };
      root.appendChild(input); root.appendChild(btn); root.appendChild(msg);
    },

    login() {
      const root = document.getElementById("root");
      root.appendChild(el("h1", null, "登录"));
      nav(root, [["首页", "index.html", "nav_home"]]);
      const input = el("input", { id: "login_user", "data-testid": "login_user",
                                  type: "text", placeholder: "用户名" });
      const btn = el("button", { "data-testid": "btn_login" }, "登录");
      const demo = el("button", { "data-testid": "btn_demo_login" }, "演示登录");
      btn.onclick = () => {
        if (state.registered && input.value === state.username) {
          state.logged = true;
          save(state);
          go("dashboard.html");
        } else {
          root.appendChild(el("div", { role: "alert" }, "登录失败"));
        }
      };
      demo.onclick = () => {
        state.logged = true;
        state.username = state.username || "演示用户";
        save(state);
        go("dashboard.html");
      };
      root.appendChild(input); root.appendChild(btn); root.appendChild(demo);
    },

    dashboard() {
      const root = document.getElementById("root");
      root.appendChild(el("h1", null, "工作台"));
      // Intentionally reachable without login (login_gate_dashboard).
      root.appendChild(el("div", { "data-obs": "login_state" },
                          state.logged ? "已登录" : "未登录"));
      if (state.project) {
        root.appendChild(el("div", { "data-obs": "dash_project_name" },
                            state.dashName));
        root.appendChild(el("div", { "data-obs": "real_project_name" },
                            state.project.name));
      }
      root.appendChild(el("div", { "data-obs": "project_count" },
                          state.project ? "1" : "0"));
      nav(root, [
        ["首页", "index.html", "nav_home"],
        ["帮助中心", "help.html", "nav_help"],
        ["系统设置", "settings.html", "nav_settings"],
      ]);
      const np = el("button", { "data-testid": "btn_new_project" }, "新建项目");
      np.onclick = () => {
        if (!state.logged) { go("login.html"); return; }
        state.wizardStep = 1;
        state.wizardName = "";
        state.wizardType = "内部";
        save(state);
        go("wizard.html");
      };
      const op = el("button", { "data-testid": "btn_open_project" }, "打开项目");
      op.onclick = () => {
        if (state.project) go("project.html");
      };
      const lo = el("button", { "data-testid": "btn_logout" }, "退出");
      lo.onclick = () => { state.logged = false; save(state); go("index.html"); };
      root.appendChild(np); root.appendChild(op); root.appendChild(lo);
    },

    wizard() {
      const root = document.getElementById("root");
      root.appendChild(el("h1", null, "新建项目"));
      root.appendChild(el("div", { "data-obs": "wizard_step" },
                          String(state.wizardStep)));
      nav(root, [["工作台", "dashboard.html", "nav_dash"]]);
      if (state.wizardStep === 1) {
        const input = el("input", { id: "proj_name", "data-testid": "proj_name",
                                    type: "text", placeholder: "项目名称" });
        input.value = state.wizardName || "";
        const next = el("button", { "data-testid": "btn_wiz_next" }, "下一步");
        next.onclick = () => {
          const name = input.value;
          if (name.length > 20) {
            // BUG-D5
            throw new RangeError("项目名过长: max 20 chars");
          }
          // BUG-D6: empty name is allowed
          state.wizardName = name;
          state.wizardStep = 2;
          save(state);
          go("wizard.html");
        };
        root.appendChild(input); root.appendChild(next);
      } else if (state.wizardStep === 2) {
        root.appendChild(el("p", null, "选择类型（当前：" + state.wizardType + "）"));
        const intern = el("button", { "data-testid": "btn_type_internal" }, "内部项目");
        const client = el("button", { "data-testid": "btn_type_client" }, "客户项目");
        intern.onclick = () => { state.wizardType = "内部"; save(state); };
        client.onclick = () => { state.wizardType = "客户"; save(state); };
        const next = el("button", { "data-testid": "btn_wiz_next" }, "下一步");
        next.onclick = () => { state.wizardStep = 3; save(state); go("wizard.html"); };
        root.appendChild(intern); root.appendChild(client); root.appendChild(next);
      } else {
        root.appendChild(el("p", null, "确认创建：" + (state.wizardName || "（空名称）")
                            + " / " + state.wizardType));
        const ok = el("button", { "data-testid": "btn_wiz_confirm" }, "确认创建");
        ok.onclick = () => {
          state.project = { name: state.wizardName, type: state.wizardType };
          state.dashName = state.wizardName;
          state.archived = false;
          state.members = [];
          state.memberCountDisplay = 0;
          state.tasks = [];
          state.guestCanEdit = "false";
          save(state);
          go("project.html");
        };
        root.appendChild(ok);
      }
    },

    project() {
      const root = document.getElementById("root");
      root.appendChild(el("h1", null, "项目详情"));
      const name = state.project ? state.project.name : "";
      root.appendChild(el("div", { "data-obs": "project_name" }, name));
      root.appendChild(el("div", { "data-obs": "archive_state" },
                          state.archived ? "已归档" : "进行中"));
      root.appendChild(el("div", { "data-obs": "guest_can_edit" },
                          state.guestCanEdit));
      nav(root, [["工作台", "dashboard.html", "nav_dash"]]);
      const members = el("button", { "data-testid": "btn_members" }, "成员与权限");
      members.onclick = () => go("members.html");
      const tasks = el("button", { "data-testid": "btn_tasks" }, "任务");
      tasks.onclick = () => go("tasks.html");
      const billing = el("button", { "data-testid": "btn_billing" }, "账单");
      billing.onclick = () => go("billing.html");
      const archive = el("button", { "data-testid": "btn_archive" }, "归档");
      archive.onclick = () => { state.archived = true; save(state); go("project.html"); };
      const unarch = el("button", { "data-testid": "btn_unarchive" }, "取消归档");
      unarch.onclick = () => { state.archived = false; save(state); go("project.html"); };
      const del = el("button", { "data-testid": "btn_delete" }, "删除项目");
      del.onclick = () => {
        if (!state.archived && state.project) {
          // BUG-D13: deleting after unarchive (archived==false, project exists
          // and we previously archived) throws. We detect "was unarchived" by
          // a sticky flag set on unarchive... actually any delete of an active
          // project after it has been created is too shallow. Only throw when
          // the project has ever been archived: use members.length or a flag.
        }
        if (state._wasArchived && !state.archived) {
          throw new Error("delete after unarchive: invalid state");
        }
        state.project = null;
        save(state);
        go("dashboard.html");
      };
      const rename = el("button", { "data-testid": "btn_rename" }, "重命名");
      rename.onclick = () => {
        if (state.project) {
          state.project.name = (state.project.name || "项目") + "-改";
          // BUG-D14: dashName intentionally NOT updated
          save(state);
          go("project.html");
        }
      };
      const guestEdit = el("button", { "data-testid": "btn_guest_edit" }, "访客编辑");
      guestEdit.onclick = () => {
        // BUG-D9: still allowed after archive + guest role
        const isGuest = state.members.some((m) => m.role === "访客");
        if (isGuest) {
          state.guestCanEdit = "true";
          save(state);
          go("project.html");
        }
      };
      root.appendChild(members); root.appendChild(tasks); root.appendChild(billing);
      root.appendChild(archive); root.appendChild(unarch); root.appendChild(del);
      root.appendChild(rename); root.appendChild(guestEdit);
    },

    members() {
      const root = document.getElementById("root");
      root.appendChild(el("h1", null, "成员与权限"));
      nav(root, [["返回项目", "project.html", "nav_project"]]);
      const real = String(state.members.length);
      root.appendChild(el("div", { "data-obs": "member_count" },
                          String(state.memberCountDisplay)));
      root.appendChild(el("div", { "data-obs": "member_count_real" }, real));
      root.appendChild(el("div", { "data-obs": "member_role" },
                          state.members[0] ? state.members[0].role : "无"));
      const add = el("button", { "data-testid": "btn_add_alice" }, "添加成员 Alice");
      add.onclick = () => {
        state.members.push({ name: "Alice", role: "成员" });
        state.memberCountDisplay = state.members.length;
        save(state);
        go("members.html");
      };
      const guest = el("button", { "data-testid": "btn_set_guest" }, "设为访客");
      guest.onclick = () => {
        if (state.members[0]) state.members[0].role = "访客";
        save(state);
        go("members.html");
      };
      const rm = el("button", { "data-testid": "btn_remove_member" }, "移除成员");
      rm.onclick = () => {
        state.members.shift();
        // BUG-D12: memberCountDisplay intentionally NOT updated
        save(state);
        go("members.html");
      };
      root.appendChild(add); root.appendChild(guest); root.appendChild(rm);
    },

    tasks() {
      const root = document.getElementById("root");
      root.appendChild(el("h1", null, "任务"));
      nav(root, [["返回项目", "project.html", "nav_project"]]);
      const t = state.tasks[0];
      root.appendChild(el("div", { "data-obs": "task_count" },
                          String(state.tasks.length)));
      root.appendChild(el("div", { "data-obs": "task_status" },
                          t ? t.status : "无"));
      root.appendChild(el("div", { "data-obs": "task_reopened" },
                          t && t.reopened ? "true" : "false"));
      const nw = el("button", { "data-testid": "btn_new_task" }, "新建任务");
      nw.onclick = () => {
        state.tasks = [{ title: "默认任务", status: "进行中", reopened: false }];
        save(state);
        go("tasks.html");
      };
      const done = el("button", { "data-testid": "btn_complete_task" }, "完成任务");
      done.onclick = () => {
        if (state.tasks[0]) state.tasks[0].status = "已完成";
        save(state);
        go("tasks.html");
      };
      const reopen = el("button", { "data-testid": "btn_reopen_task" }, "重新打开");
      reopen.onclick = () => {
        if (state.tasks[0]) {
          state.tasks[0].reopened = true;
          // BUG-D10: status stays 已完成
          save(state);
          go("tasks.html");
        }
      };
      root.appendChild(nw); root.appendChild(done); root.appendChild(reopen);
    },

    billing() {
      const root = document.getElementById("root");
      root.appendChild(el("h1", null, "账单"));
      nav(root, [["返回项目", "project.html", "nav_project"]]);
      root.appendChild(el("div", { "data-obs": "bill_qty" }, String(state.billQty)));
      root.appendChild(el("div", { "data-obs": "bill_coupon" },
                          state.coupon ? "on" : "off"));
      root.appendChild(el("div", { "data-obs": "bill_price" },
                          String(state.billPriceDisplay)));
      root.appendChild(el("div", { "data-obs": "bill_price_expected" },
                          String(expectedPrice(state))));
      const up = el("button", { "data-testid": "btn_qty_up" }, "增加数量");
      up.onclick = () => {
        state.billQty += 1;
        // BUG-D11: display price not recomputed after qty change
        save(state);
        go("billing.html");
      };
      const down = el("button", { "data-testid": "btn_qty_down" }, "减少数量");
      down.onclick = () => {
        state.billQty -= 1; // BUG-H2: can go negative
        save(state);
        go("billing.html");
      };
      const coupon = el("button", { "data-testid": "btn_coupon" }, "应用优惠");
      coupon.onclick = () => {
        state.coupon = true;
        state.billPriceDisplay = expectedPrice(state);
        save(state);
        go("billing.html");
      };
      const exp = el("button", { "data-testid": "btn_export" }, "导出账单");
      exp.onclick = () => {
        fetch("/api/export", { method: "POST" })
          .then((r) => {
            const t = el("div", { role: "alert" }, "导出失败：" + r.status);
            root.appendChild(t);
          });
      };
      root.appendChild(up); root.appendChild(down);
      root.appendChild(coupon); root.appendChild(exp);
    },

    settings() {
      const root = document.getElementById("root");
      root.appendChild(el("h1", null, "系统设置"));
      nav(root, [
        ["首页", "index.html", "nav_home"],
        ["报表", "reports.html", "nav_reports"],
        ["操作历史", "history.html", "nav_history"],
        ["更新日志", "changelog.html", "nav_changelog"],
      ]);
      // Visible clock is NOT data-obs: must not explode state variants.
      root.appendChild(el("p", { "class": "muted" },
                          "服务器时间（展示用）" + Date.now()));
      const tog = el("button", { "data-testid": "btn_toggle_notify" }, "切换通知");
      tog.onclick = () => { state.notify = !state.notify; save(state); };
      const saveBtn = el("button", { "data-testid": "btn_save_settings" }, "保存设置");
      // BUG-D3: save is a dead action (no handler)
      root.appendChild(tog); root.appendChild(saveBtn);
      root.appendChild(el("p", null, "主题、语言、通知、隐私、实验开关均为可探索无缺陷区域。"));
      ["主题-浅色", "主题-深色", "语言-中文", "语言-EN"].forEach((t) => {
        const b = el("button", { "data-testid": "btn_" + t }, t);
        b.onclick = () => { /* legit no-op besides mutation observer */ };
        root.appendChild(b);
      });
    },

    help() {
      const root = document.getElementById("root");
      root.appendChild(el("h1", null, "帮助中心"));
      // BUG-D8: help <-> docs loop, no way back to the product
      root.appendChild(el("a", { href: "docs.html", "data-testid": "btn_more_docs" },
                          "相关文档"));
      root.appendChild(el("p", null, "如何创建项目、邀请成员、归档工作流的说明文字。"));
      root.appendChild(el("p", null, "常见问题 1：如何导出账单？见文档。"));
      root.appendChild(el("p", null, "常见问题 2：访客权限说明。"));
    },
    docs() {
      const root = document.getElementById("root");
      root.appendChild(el("h1", null, "文档"));
      root.appendChild(el("a", { href: "help.html", "data-testid": "btn_more_help" },
                          "相关帮助"));
      root.appendChild(el("p", null, "API 说明、字段字典、权限矩阵（无缺陷诱饵页）。"));
    },
    about() {
      const root = document.getElementById("root");
      root.appendChild(el("h1", null, "关于 BuggyFlow"));
      nav(root, [["首页", "index.html", "nav_home"]]);
      const ver = el("button", { "data-testid": "btn_version" }, "版本信息");
      ver.onclick = () => {
        throw new Error("version info: undefined is not a function");
      };
      root.appendChild(ver);
      root.appendChild(el("p", null, "开源演示工作台，用于评估探索式测试策略。"));
    },
    reports() {
      // BUG-D2: blank
      document.getElementById("root").innerHTML = "";
    },
    history() {
      const root = document.getElementById("root");
      root.appendChild(el("h1", null, "操作历史"));
      nav(root, [["系统设置", "settings.html", "nav_settings"]]);
      ["登录", "查看帮助", "打开设置", "返回首页"].forEach((t, i) => {
        root.appendChild(el("p", null, "#" + i + " " + t + " — 合法记录"));
      });
    },
    changelog() {
      const root = document.getElementById("root");
      root.appendChild(el("h1", null, "更新日志"));
      nav(root, [["系统设置", "settings.html", "nav_settings"]]);
      root.appendChild(el("p", null, "v0.3 冻结的 DeepBench 应用。"));
      const d = el("button", { "data-testid": "btn_changelog_detail" }, "查看详情");
      d.onclick = () => {
        // BUG-H1 holdout
        throw new Error("changelog detail: not implemented");
      };
      root.appendChild(d);
    },
  };

  // Track unarchive for BUG-D13
  const _save = save;
  save = function (s) {
    if (s.archived) s._wasArchived = true;
    _save(s);
  };

  if (pages[page]) pages[page]();
})();
