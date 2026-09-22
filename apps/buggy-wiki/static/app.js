
(function () {
  "use strict";
  const V = {"app":"buggy-wiki","seed":3204138653,"seed_hex":"befb469d","brand":"竹简文库","spaces":[{"id":"s1","name":"工程"},{"id":"s2","name":"支持"},{"id":"s3","name":"运营"}],"pages":[{"id":"p1","title":"权限模型","space":"s1","backlinks":["p2","p3"],"tags":["t1"]},{"id":"p2","title":"故障分级","space":"s1","backlinks":["p1"],"tags":["t1","t2"]},{"id":"p3","title":"备份策略","space":"s2","backlinks":["p1"],"tags":["t2"]}],"tags":[{"id":"t1","name":"流程"},{"id":"t2","name":"规范"}],"revisions":[{"id":"r1","page":"p1","n":"3"},{"id":"r2","page":"p1","n":"2"},{"id":"r3","page":"p2","n":"1"}]};
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
