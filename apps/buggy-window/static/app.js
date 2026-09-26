
(function () {
  "use strict";
  const MODEL = {"storage_key":"window_v0326","fail_path":"/api/export","initial":{"obs":{"score_shown":"8","score_live":"6","form_msg":"","search_state":"","scratch_a":"","scratch_b":"空","hold_mark":"","tag_mark":""},"revealed":{}},"entities":{},"pages":{"home":{"title":"首页","blank":false,"entity_param":"","entity_source":"","obs":["search_state"],"obs_by_entity":{},"controls":[{"kind":"link","testid":"nav_counter","text":"柜台","href":"counter.html","effect":"goto"},{"kind":"link","testid":"open_aid","text":"帮助","href":"help.html","effect":"goto"},{"kind":"input","testid":"search_box","text":"检索词"},{"kind":"button","testid":"btn_query_submit","text":"提交查询","effect":"search","message":"window search query too long","input":"search_box","obs_key":"search_state"}]},"counter":{"title":"柜台","blank":false,"entity_param":"","entity_source":"","obs":[],"obs_by_entity":{},"controls":[{"kind":"link","testid":"open_t1","text":"取号","href":"ticket.html?id=t1","effect":"goto"},{"kind":"link","testid":"open_t2","text":"补打","href":"ticket.html?id=t2","effect":"goto"},{"kind":"link","testid":"open_lane","text":"问询单","href":"slip.html?id=s1","effect":"goto"},{"kind":"link","testid":"nav_up_home","text":"返回首页","href":"index.html","effect":"goto"}]},"ticket":{"title":"取号","blank":false,"entity_param":"id","entity_source":"","obs":[],"obs_by_entity":{"t1":["score_shown","score_live","scratch_a","scratch_b"],"t2":["score_shown","score_live","scratch_a","scratch_b"]},"controls":[{"kind":"button","testid":"btn_note_a","text":"记一笔","effect":"mutate","patch":[{"key":"scratch_a","value":"已记"}],"when_entity":"t1"},{"kind":"button","testid":"btn_note_b","text":"标重点","effect":"mutate","patch":[{"key":"scratch_b","value":"已标"}],"when_entity":"t1"},{"kind":"link","testid":"nav_up_counter","text":"返回柜台","href":"counter.html","effect":"goto","when_entity":"t1"},{"kind":"button","testid":"btn_note_a","text":"记一笔","effect":"mutate","patch":[{"key":"scratch_a","value":"已记"}],"when_entity":"t2"},{"kind":"button","testid":"btn_note_b","text":"标重点","effect":"mutate","patch":[{"key":"scratch_b","value":"已标"}],"when_entity":"t2"},{"kind":"link","testid":"nav_up_counter","text":"返回柜台","href":"counter.html","effect":"goto","when_entity":"t2"}]},"slip":{"title":"问询","blank":false,"entity_param":"id","entity_source":"","obs":[],"obs_by_entity":{"dest":["hold_mark","tag_mark"]},"controls":[{"kind":"link","testid":"open_lane_b","text":"下一页","href":"slip.html?id=s2","effect":"goto","when_entity":"s1"},{"kind":"link","testid":"nav_up_counter_a","text":"返回柜台","href":"counter.html","effect":"goto","when_entity":"s1"},{"kind":"link","testid":"open_dest","text":"回执","href":"slip.html?id=dest","effect":"goto","when_entity":"s2"},{"kind":"link","testid":"nav_up_lane","text":"返回上页","href":"slip.html?id=s1","effect":"goto","when_entity":"s2"},{"kind":"button","testid":"btn_hold","text":"记下","effect":"mutate","patch":[{"key":"hold_mark","value":"是"}],"when_entity":"dest"},{"kind":"button","testid":"btn_tag","text":"加标记","effect":"mutate","patch":[{"key":"tag_mark","value":"是"}],"when_entity":"dest"},{"kind":"link","testid":"nav_up_lane_b","text":"返回上页","href":"slip.html?id=s2","effect":"goto","when_entity":"dest"}]},"help":{"title":"说明","blank":false,"entity_param":"","entity_source":"","obs":[],"obs_by_entity":{},"controls":[{"kind":"link","testid":"open_loop","text":"偏好页","href":"settings.html","effect":"goto"}]},"settings":{"title":"偏好","blank":false,"entity_param":"","entity_source":"","obs":["form_msg"],"obs_by_entity":{},"controls":[{"kind":"input","testid":"topic_title","text":"标题"},{"kind":"button","testid":"btn_submit","text":"提交","effect":"form"},{"kind":"button","testid":"btn_pin","text":"保存草稿","effect":"dead"},{"kind":"button","testid":"btn_probe","text":"提交同步","effect":"throw","message":"window sync handshake failed"},{"kind":"button","testid":"btn_export","text":"提交导出","effect":"post"},{"kind":"link","testid":"open_loop","text":"说明页","href":"help.html","effect":"goto"},{"kind":"link","testid":"nav_up_home_prefs","text":"返回首页","href":"index.html","effect":"goto"}]}}};
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
