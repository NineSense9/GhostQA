
(function () {
  "use strict";
  const MODEL = {"storage_key":"directory_v0315","fail_path":"/api/export","initial":{"obs":{"heat_display":"8","heat_remaining":"8","form_msg":"","search_state":""},"revealed":{}},"entities":{"people":[{"id":"h1","name":"林夏"},{"id":"h2","name":"许昭"}],"teams":[{"id":"m1","name":"值班"}],"offices":[{"id":"o1","name":"二号楼"}],"roles":[{"id":"r1","name":"归档"}]},"pages":{"home":{"title":"首页","blank":false,"entity_param":"","entity_source":"","obs":["search_state"],"obs_by_entity":{},"controls":[{"kind":"link","testid":"nav_people","text":"人员","href":"people.html","effect":"goto"},{"kind":"link","testid":"nav_teams","text":"班组","href":"teams.html","effect":"goto"},{"kind":"link","testid":"nav_offices","text":"办公点","href":"offices.html","effect":"goto"},{"kind":"link","testid":"nav_roles","text":"职责","href":"roles.html","effect":"goto"},{"kind":"link","testid":"nav_lookup","text":"检索","href":"search.html","effect":"goto"},{"kind":"link","testid":"nav_help","text":"帮助","href":"help.html","effect":"goto"},{"kind":"link","testid":"nav_prefs_word","text":"设置","href":"settings.html","effect":"goto"},{"kind":"input","testid":"search_box","text":"检索词"},{"kind":"button","testid":"btn_query_submit","text":"提交查询","effect":"search","message":"directory search query too long","input":"search_box","obs_key":"search_state"}]},"people":{"title":"人员","blank":false,"entity_param":"id","entity_source":"people","obs":[],"obs_by_entity":{"h1":["heat_display","heat_remaining"]},"controls":[{"kind":"link","testid":"open_highlight","text":"林夏","href":"people.html?id=h1","effect":"goto","when_no_entity":true},{"kind":"button","testid":"btn_pin","text":"收藏","effect":"dead","when_no_entity":true},{"kind":"link","testid":"nav_up_home","text":"返回首页","href":"index.html","effect":"goto","when_no_entity":true},{"kind":"button","testid":"btn_adjust","text":"下调班次","effect":"mutate","patch":[{"key":"heat_remaining","value":"6"}],"when_entity":"h1"},{"kind":"link","testid":"nav_up_people","text":"返回人员","href":"people.html","effect":"goto","when_entity":"h1"}]},"teams":{"title":"班组","blank":false,"entity_param":"id","entity_source":"teams","obs":[],"obs_by_entity":{},"controls":[{"kind":"link","testid":"open_team","text":"值班","href":"teams.html?id=m1","effect":"goto","when_no_entity":true},{"kind":"link","testid":"nav_up_home_teams","text":"返回首页","href":"index.html","effect":"goto","when_no_entity":true},{"kind":"link","testid":"nav_up_teams","text":"返回班组","href":"teams.html","effect":"goto","when_entity":"m1"}]},"offices":{"title":"办公点","blank":true,"entity_param":"","entity_source":"","obs":[],"obs_by_entity":{},"controls":[]},"roles":{"title":"职责","blank":false,"entity_param":"","entity_source":"roles","obs":[],"obs_by_entity":{},"controls":[{"kind":"link","testid":"nav_up_home_roles","text":"返回首页","href":"index.html","effect":"goto"}]},"search":{"title":"检索","blank":false,"entity_param":"","entity_source":"","obs":[],"obs_by_entity":{},"controls":[{"kind":"link","testid":"nav_up_home_search","text":"返回首页","href":"index.html","effect":"goto"}]},"settings":{"title":"偏好","blank":false,"entity_param":"","entity_source":"","obs":["form_msg"],"obs_by_entity":{},"controls":[{"kind":"button","testid":"btn_probe","text":"测试同步","effect":"throw","message":"directory sync handshake failed"},{"kind":"button","testid":"btn_export","text":"导出","effect":"post"},{"kind":"input","testid":"topic_title","text":"标题"},{"kind":"button","testid":"btn_submit","text":"提交","effect":"form"},{"kind":"link","testid":"nav_up_help","text":"返回说明","href":"help.html","effect":"goto"}]},"help":{"title":"说明","blank":false,"entity_param":"","entity_source":"","obs":[],"obs_by_entity":{},"controls":[{"kind":"link","testid":"open_handbook","text":"查阅规程","href":"settings.html","effect":"goto"}]}}};
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
