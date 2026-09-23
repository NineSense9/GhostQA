
(function () {
  "use strict";
  const MODEL = {"storage_key":"forum_v0315","fail_path":"/api/export","initial":{"obs":{"heat_display":"8","heat_remaining":"8","topic_status":"跟进中","reopened":"否","note_kind":"","note_visibility":"","form_msg":"","search_state":"","handled":"","handled_note":"","accepted":"","reason_note":""},"revealed":{}},"entities":{"zones":[{"id":"c1","name":"夜读"},{"id":"c2","name":"城事"},{"id":"c3","name":"书评"}],"topics":[{"id":"t1","name":"望远镜"},{"id":"t2","name":"雨天菜单"},{"id":"t3","name":"周末市集"}],"people":[{"id":"p1","name":"陈汐"}]},"pages":{"home":{"title":"首页","blank":false,"entity_param":"","entity_source":"","obs":["search_state"],"obs_by_entity":{},"controls":[{"kind":"link","testid":"nav_zones","text":"分类","href":"categories.html","effect":"goto"},{"kind":"link","testid":"nav_threads","text":"讨论串","href":"threads.html","effect":"goto"},{"kind":"link","testid":"nav_help","text":"帮助","href":"help.html","effect":"goto"},{"kind":"input","testid":"search_box","text":"检索词"},{"kind":"button","testid":"btn_query_submit","text":"提交查询","effect":"search","message":"forum search query too long","input":"search_box","obs_key":"search_state"}]},"categories":{"title":"分类","blank":false,"entity_param":"","entity_source":"","obs":[],"obs_by_entity":{},"controls":[{"kind":"link","testid":"open_zone_c1","text":"夜读","href":"category.html?id=c1","effect":"goto"},{"kind":"link","testid":"open_zone_c2","text":"城事","href":"category.html?id=c2","effect":"goto"},{"kind":"link","testid":"open_zone_c3","text":"书评","href":"category.html?id=c3","effect":"goto"},{"kind":"link","testid":"nav_compose","text":"写讨论","href":"compose.html","effect":"goto"},{"kind":"link","testid":"nav_drafts","text":"草稿","href":"drafts.html","effect":"goto"},{"kind":"link","testid":"nav_up_home","text":"返回首页","href":"index.html","effect":"goto"}]},"category":{"title":"分区","blank":false,"entity_param":"","entity_source":"zones","obs":[],"obs_by_entity":{},"controls":[{"kind":"link","testid":"open_topic_t1","text":"望远镜","href":"thread.html?id=t1","effect":"goto"},{"kind":"link","testid":"open_topic_t2","text":"雨天菜单","href":"thread.html?id=t2","effect":"goto"},{"kind":"link","testid":"open_topic_t3","text":"周末市集","href":"thread.html?id=t3","effect":"goto"},{"kind":"button","testid":"btn_pin","text":"收藏","effect":"dead"},{"kind":"link","testid":"nav_prefs","text":"偏好","href":"settings.html","effect":"goto"},{"kind":"link","testid":"nav_up_zones","text":"返回分类","href":"categories.html","effect":"goto"}]},"threads":{"title":"讨论串","blank":false,"entity_param":"","entity_source":"","obs":[],"obs_by_entity":{},"controls":[{"kind":"link","testid":"open_thread_t2","text":"雨天菜单","href":"thread.html?id=t2","effect":"goto"},{"kind":"link","testid":"open_thread_t1","text":"望远镜","href":"thread.html?id=t1","effect":"goto"},{"kind":"link","testid":"open_thread_t3","text":"周末市集","href":"thread.html?id=t3","effect":"goto"},{"kind":"link","testid":"nav_up_home_threads","text":"返回首页","href":"index.html","effect":"goto"}]},"thread":{"title":"讨论","blank":false,"entity_param":"id","entity_source":"topics","obs":[],"obs_by_entity":{"t1":["heat_display","heat_remaining","note_kind","note_visibility"]},"controls":[{"kind":"link","testid":"open_triage","text":"处理队列","href":"moderation.html?id=t1","effect":"goto","when_entity":"t1"},{"kind":"link","testid":"open_response","text":"查看回复","href":"reply.html?id=r1","effect":"goto","when_entity":"t1"},{"kind":"link","testid":"open_author","text":"查看作者","href":"profile.html?id=p1","effect":"goto","when_entity":"t1"},{"kind":"link","testid":"nav_replies","text":"全部回复","href":"replies.html?id=t1","effect":"goto","when_entity":"t1"},{"kind":"button","testid":"btn_cool","text":"下调热度","effect":"mutate","patch":[{"key":"heat_remaining","value":"6"}],"when_entity":"t1"},{"kind":"button","testid":"btn_staff_note","text":"内部记录","effect":"mutate","patch":[{"key":"note_kind","value":"内部"},{"key":"note_visibility","value":"公开"}],"when_entity":"t1"},{"kind":"link","testid":"nav_up_zone","text":"返回分区","href":"category.html?id=c1","effect":"goto","when_entity":"t1"},{"kind":"link","testid":"open_author","text":"查看作者","href":"profile.html?id=p1","effect":"goto","when_entity":"t2"},{"kind":"link","testid":"open_triage","text":"处理队列","href":"moderation.html?id=t2","effect":"goto","when_entity":"t2"},{"kind":"link","testid":"open_response","text":"查看回复","href":"reply.html?id=r2","effect":"goto","when_entity":"t2"},{"kind":"link","testid":"nav_up_threads","text":"返回讨论串","href":"threads.html","effect":"goto","when_entity":"t2"},{"kind":"link","testid":"open_response","text":"查看回复","href":"reply.html?id=r3","effect":"goto","when_entity":"t3"},{"kind":"link","testid":"open_author","text":"查看作者","href":"profile.html?id=p1","effect":"goto","when_entity":"t3"},{"kind":"link","testid":"nav_replies","text":"全部回复","href":"replies.html?id=t3","effect":"goto","when_entity":"t3"},{"kind":"link","testid":"nav_up_threads_t3","text":"返回讨论串","href":"threads.html","effect":"goto","when_entity":"t3"}]},"reply":{"title":"回复","blank":false,"entity_param":"","entity_source":"","obs":["topic_status","reopened"],"obs_by_entity":{},"controls":[{"kind":"link","testid":"open_author_reply","text":"查看作者","href":"profile.html?id=p1","effect":"goto"},{"kind":"link","testid":"open_topic_peer","text":"雨天菜单","href":"thread.html?id=t2","effect":"goto"},{"kind":"link","testid":"open_triage_reply","text":"处理队列","href":"moderation.html?id=t1","effect":"goto"},{"kind":"button","testid":"btn_close","text":"关闭","effect":"mutate","patch":[{"key":"topic_status","value":"已关闭"}]},{"kind":"button","testid":"btn_reopen","text":"重新打开","effect":"mutate","patch":[{"key":"reopened","value":"是"}]},{"kind":"link","testid":"nav_up_topic","text":"返回讨论","href":"thread.html?id=t1","effect":"goto"}]},"replies":{"title":"回复列表","blank":false,"entity_param":"","entity_source":"","obs":["note_kind","note_visibility"],"obs_by_entity":{},"controls":[{"kind":"link","testid":"open_response_r1","text":"首条","href":"reply.html?id=r1","effect":"goto"},{"kind":"link","testid":"open_response_r2","text":"下一条","href":"reply.html?id=r2","effect":"goto"},{"kind":"link","testid":"open_author_list","text":"查看作者","href":"profile.html?id=p1","effect":"goto"},{"kind":"link","testid":"nav_up_topic_list","text":"返回讨论","href":"thread.html?id=t1","effect":"goto"}]},"profile":{"title":"作者","blank":false,"entity_param":"","entity_source":"people","obs":[],"obs_by_entity":{},"controls":[{"kind":"link","testid":"open_case","text":"受理举报","href":"report.html?id=p1","effect":"goto"},{"kind":"link","testid":"open_author_topic","text":"雨天菜单","href":"thread.html?id=t2","effect":"goto"},{"kind":"link","testid":"open_author_replies","text":"作者回复","href":"replies.html?id=p1","effect":"goto"},{"kind":"link","testid":"nav_up_threads_author","text":"返回讨论串","href":"threads.html","effect":"goto"}]},"moderation":{"title":"处理","blank":false,"entity_param":"","entity_source":"","obs":[],"obs_by_entity":{},"controls":[{"kind":"button","testid":"btn_mark","text":"登记处理","effect":"mutate","patch":[{"key":"handled","value":"是"}],"reveal":"btn_follow"},{"kind":"button","testid":"btn_follow","text":"补充说明","effect":"mutate","patch":[{"key":"handled_note","value":"已补充"}],"reveal_after":"btn_mark"},{"kind":"link","testid":"nav_up_topic_mod","text":"返回讨论","href":"thread.html?id=t1","effect":"goto"}]},"report":{"title":"举报","blank":false,"entity_param":"","entity_source":"","obs":[],"obs_by_entity":{},"controls":[{"kind":"button","testid":"btn_accept","text":"受理登记","effect":"mutate","patch":[{"key":"accepted","value":"是"}],"reveal":"btn_reason"},{"kind":"button","testid":"btn_reason","text":"填写理由","effect":"mutate","patch":[{"key":"reason_note","value":"已填写"}],"reveal_after":"btn_accept"},{"kind":"link","testid":"nav_up_author","text":"返回作者","href":"profile.html?id=p1","effect":"goto"}]},"drafts":{"title":"草稿","blank":true,"entity_param":"","entity_source":"","obs":[],"obs_by_entity":{},"controls":[]},"compose":{"title":"撰写","blank":false,"entity_param":"","entity_source":"","obs":["form_msg"],"obs_by_entity":{},"controls":[{"kind":"input","testid":"topic_title","text":"标题"},{"kind":"button","testid":"btn_submit","text":"提交","effect":"form"},{"kind":"link","testid":"nav_up_home","text":"返回首页","href":"index.html","effect":"goto"}]},"settings":{"title":"偏好","blank":false,"entity_param":"","entity_source":"","obs":[],"obs_by_entity":{},"controls":[{"kind":"button","testid":"btn_probe","text":"测试同步","effect":"throw","message":"forum sync handshake failed"},{"kind":"button","testid":"btn_export","text":"导出","effect":"post"},{"kind":"link","testid":"nav_up_from_prefs","text":"返回分区","href":"category.html?id=c1","effect":"goto"}]},"search":{"title":"检索","blank":false,"entity_param":"","entity_source":"","obs":[],"obs_by_entity":{},"controls":[{"kind":"link","testid":"nav_up_home_search","text":"返回首页","href":"index.html","effect":"goto"}]},"help":{"title":"说明","blank":false,"entity_param":"","entity_source":"","obs":[],"obs_by_entity":{},"controls":[{"kind":"link","testid":"open_handbook","text":"打开手册","href":"handbook.html","effect":"goto"}]},"handbook":{"title":"手册","blank":false,"entity_param":"","entity_source":"","obs":[],"obs_by_entity":{},"controls":[{"kind":"link","testid":"nav_up_help","text":"返回说明","href":"help.html","effect":"goto"}]}}};
  function load() {
    try {
      const saved = JSON.parse(localStorage.getItem(MODEL.storage_key));
      if (saved && typeof saved === "object" && saved.obs) return saved;
    } catch (e) { /* fresh state */ }
    return JSON.parse(JSON.stringify(MODEL.initial));
  }
  function save(state) { localStorage.setItem(MODEL.storage_key, JSON.stringify(state)); }
  function el(tag, attrs, text) {
    const node = document.createElement(tag);
    if (attrs) Object.keys(attrs).forEach(function (key) { node.setAttribute(key, attrs[key]); });
    if (text != null) node.textContent = text;
    return node;
  }
  function qid(name) {
    try { return new URL(location.href).searchParams.get(name) || ""; }
    catch (e) { return ""; }
  }
  const state = load();
  const page = document.body.getAttribute("data-page");
  function entityTitle(spec, entity) {
    if (!entity || !spec.entity_source) return spec.title;
    const rows = MODEL.entities[spec.entity_source] || [];
    for (let i = 0; i < rows.length; i++) {
      if (rows[i].id === entity) return rows[i].name;
    }
    return spec.title;
  }
  function render() {
    const spec = MODEL.pages[page];
    const root = document.getElementById("root");
    if (!root) return;
    while (root.firstChild) root.removeChild(root.firstChild);
    if (!spec || spec.blank) return;
    const entity = spec.entity_param ? (qid(spec.entity_param) || "") : "";
    root.appendChild(el("h1", null, entityTitle(spec, entity)));
    root.appendChild(el("p", {class: "muted"}, "此页提供日常浏览、登记和返回入口。"));
    let obsKeys = (spec.obs || []).slice();
    const extra = spec.obs_by_entity && entity ? spec.obs_by_entity[entity] : null;
    if (extra) obsKeys = obsKeys.concat(extra);
    obsKeys.forEach(function (key) {
      const value = state.obs[key];
      if (value == null || value === "") return;
      root.appendChild(el("div", {"data-obs": key}, String(value)));
    });
    (spec.controls || []).forEach(function (ctl) {
      if (ctl.when_entity && ctl.when_entity !== entity) return;
      if (ctl.when_no_entity && entity) return;
      if (ctl.reveal_after && !state.revealed[ctl.reveal_after]) return;
      if (ctl.kind === "input") {
        const input = el("input", {
          id: ctl.testid, "data-testid": ctl.testid, type: "text", placeholder: ctl.text || ""
        });
        root.appendChild(input);
        return;
      }
      if (ctl.kind === "link") {
        const anchor = el("a", {href: ctl.href, "data-testid": ctl.testid}, ctl.text);
        root.appendChild(anchor);
        root.appendChild(el("br"));
        return;
      }
      const button = el("button", {"data-testid": ctl.testid, type: "button"}, ctl.text);
      button.onclick = function () { apply(ctl); };
      root.appendChild(button);
    });
  }
  function apply(ctl) {
    if (ctl.effect === "dead") return;
    if (ctl.effect === "throw") throw new Error(ctl.message || "error");
    if (ctl.effect === "search") {
      const box = document.getElementById(ctl.input);
      if (box && box.value.length > 24) throw new RangeError(ctl.message || "query too long");
      state.obs[ctl.obs_key || "search_state"] = "已检索";
      save(state);
      render();
      return;
    }
    if (ctl.effect === "form") {
      state.obs.form_msg = "已创建";
      save(state);
      render();
      return;
    }
    if (ctl.effect === "post") {
      fetch(MODEL.fail_path, {method: "POST"});
      return;
    }
    if (ctl.effect === "mutate") {
      (ctl.patch || []).forEach(function (item) { state.obs[item.key] = item.value; });
      if (ctl.reveal) state.revealed[ctl.reveal] = true;
      save(state);
      render();
    }
  }
  render();
})();
