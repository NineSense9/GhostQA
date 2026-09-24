
(function () {
  "use strict";
  const MODEL = {"storage_key":"catalog_v0320","fail_path":"/api/export","initial":{"obs":{"shown_qty":"8","live_qty":"6","form_msg":"","search_state":"","score_shown":"","score_live":""},"revealed":{}},"entities":{"products":[{"id":"p1","name":"纸灯"},{"id":"p2","name":"木梳"},{"id":"p3","name":"麻布袋"}]},"pages":{"home":{"title":"首页","blank":false,"entity_param":"","entity_source":"","obs":["search_state"],"obs_by_entity":{},"controls":[{"kind":"link","testid":"nav_categories","text":"分类","href":"categories.html","effect":"goto"},{"kind":"link","testid":"nav_search","text":"查找","href":"search.html","effect":"goto"},{"kind":"link","testid":"open_aid","text":"帮助","href":"help.html","effect":"goto"},{"kind":"input","testid":"search_box","text":"检索词"},{"kind":"button","testid":"btn_query_submit","text":"提交查询","effect":"search","message":"catalog search query too long","input":"search_box","obs_key":"search_state"}]},"categories":{"title":"分类","blank":false,"entity_param":"","entity_source":"","obs":[],"obs_by_entity":{},"controls":[{"kind":"link","testid":"open_p1","text":"纸灯","href":"product.html?id=p1","effect":"goto"},{"kind":"link","testid":"open_p2","text":"木梳","href":"product.html?id=p2","effect":"goto"},{"kind":"link","testid":"open_p3","text":"麻布袋","href":"product.html?id=p3","effect":"goto"},{"kind":"link","testid":"nav_products","text":"全部样品","href":"products.html","effect":"goto"},{"kind":"link","testid":"open_compare","text":"并排页","href":"compare.html","effect":"goto"},{"kind":"link","testid":"nav_up_home","text":"返回首页","href":"index.html","effect":"goto"}]},"products":{"title":"样品","blank":false,"entity_param":"","entity_source":"","obs":[],"obs_by_entity":{},"controls":[{"kind":"link","testid":"nav_up_categories","text":"返回分类","href":"categories.html","effect":"goto"}]},"product":{"title":"样品明细","blank":false,"entity_param":"id","entity_source":"products","obs":[],"obs_by_entity":{"p1":["shown_qty","live_qty"],"p2":["shown_qty","live_qty"],"p3":["shown_qty","live_qty"]},"controls":[{"kind":"link","testid":"nav_up_products","text":"返回样品","href":"products.html","effect":"goto","when_entity":"p1"},{"kind":"link","testid":"nav_up_products","text":"返回样品","href":"products.html","effect":"goto","when_entity":"p2"},{"kind":"link","testid":"nav_up_products","text":"返回样品","href":"products.html","effect":"goto","when_entity":"p3"}]},"compare":{"title":"并排","blank":true,"entity_param":"","entity_source":"","obs":[],"obs_by_entity":{},"controls":[]},"search":{"title":"查找","blank":false,"entity_param":"","entity_source":"","obs":[],"obs_by_entity":{},"controls":[{"kind":"link","testid":"nav_up_home_search","text":"返回首页","href":"index.html","effect":"goto"}]},"help":{"title":"说明","blank":false,"entity_param":"","entity_source":"","obs":[],"obs_by_entity":{},"controls":[{"kind":"link","testid":"open_loop","text":"偏好页","href":"settings.html","effect":"goto"}]},"settings":{"title":"偏好","blank":false,"entity_param":"","entity_source":"","obs":["form_msg"],"obs_by_entity":{},"controls":[{"kind":"input","testid":"topic_title","text":"标题"},{"kind":"button","testid":"btn_submit","text":"提交","effect":"form"},{"kind":"button","testid":"btn_pin","text":"保存草稿","effect":"dead"},{"kind":"button","testid":"btn_probe","text":"提交同步","effect":"throw","message":"catalog sync handshake failed"},{"kind":"button","testid":"btn_export","text":"提交导出","effect":"post"},{"kind":"link","testid":"open_loop","text":"说明页","href":"help.html","effect":"goto"},{"kind":"link","testid":"nav_up_home_prefs","text":"返回首页","href":"index.html","effect":"goto"}]}}};
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
