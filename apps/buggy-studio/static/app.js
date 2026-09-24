
(function () {
  "use strict";
  const MODEL = {"storage_key":"studio_v0320","fail_path":"/api/export","initial":{"obs":{"score_shown":"8","score_live":"6","shown_qty":"8","live_qty":"8","status_label":"跟进中","reopened":"否","note_kind":"","note_visible":"","handled":"","handled_label":"","handled_note":"","form_msg":"","search_state":"","variant_note":"原稿","scratch_a":"","scratch_b":"","hold_mark":"","tag_mark":""},"revealed":{}},"entities":{"list_rows":[{"id":"p1","name":"晨雾短片"},{"id":"p2","name":"港湾纪录"},{"id":"p3","name":"夜市动画"}],"side_rows":[{"id":"a1","name":"布景图"},{"id":"a2","name":"音轨"},{"id":"a3","name":"台词本"}]},"pages":{"home":{"title":"首页","blank":false,"entity_param":"","entity_source":"","obs":["search_state"],"obs_by_entity":{},"controls":[{"kind":"link","testid":"nav_projects","text":"项目","href":"projects.html","effect":"goto"},{"kind":"link","testid":"nav_compare_blank","text":"对照页","href":"compare.html","effect":"goto"},{"kind":"link","testid":"open_aid","text":"帮助","href":"help.html","effect":"goto"},{"kind":"input","testid":"search_box","text":"检索词"},{"kind":"button","testid":"btn_query_submit","text":"提交查询","effect":"search","message":"studio search query too long","input":"search_box","obs_key":"search_state"}]},"compare":{"title":"对照页","blank":true,"entity_param":"","entity_source":"","obs":[],"obs_by_entity":{},"controls":[]},"projects":{"title":"项目","blank":false,"entity_param":"","entity_source":"","obs":[],"obs_by_entity":{},"controls":[{"kind":"link","testid":"open_row_p1","text":"晨雾短片","href":"project.html?id=p1","effect":"goto"},{"kind":"link","testid":"open_row_p2","text":"港湾纪录","href":"project.html?id=p2","effect":"goto"},{"kind":"link","testid":"open_row_p3","text":"夜市动画","href":"project.html?id=p3","effect":"goto"},{"kind":"link","testid":"open_finding","text":"批注页","href":"comments.html","effect":"goto"},{"kind":"link","testid":"nav_up_home","text":"返回首页","href":"index.html","effect":"goto"}]},"project":{"title":"项目明细","blank":false,"entity_param":"id","entity_source":"list_rows","obs":[],"obs_by_entity":{"p1":["shown_qty","live_qty"],"p2":["shown_qty","live_qty"],"p3":["shown_qty","live_qty"]},"controls":[{"kind":"link","testid":"open_mid","text":"场次","href":"scene.html","effect":"goto","when_entity":"p1"},{"kind":"link","testid":"open_side","text":"素材","href":"assets.html","effect":"goto","when_entity":"p1"},{"kind":"link","testid":"nav_prefs","text":"偏好","href":"settings.html","effect":"goto","when_entity":"p1"},{"kind":"button","testid":"btn_pin","text":"收藏","effect":"dead","when_entity":"p1"},{"kind":"button","testid":"btn_cool","text":"下调数量","effect":"mutate","patch":[{"key":"live_qty","value":"6"}],"when_entity":"p1"},{"kind":"link","testid":"nav_up_list","text":"返回上页","href":"projects.html","effect":"goto","when_entity":"p1"},{"kind":"link","testid":"open_mid","text":"场次","href":"scene.html","effect":"goto","when_entity":"p2"},{"kind":"link","testid":"open_side","text":"素材","href":"assets.html","effect":"goto","when_entity":"p2"},{"kind":"link","testid":"nav_prefs","text":"偏好","href":"settings.html","effect":"goto","when_entity":"p2"},{"kind":"button","testid":"btn_pin","text":"收藏","effect":"dead","when_entity":"p2"},{"kind":"button","testid":"btn_cool","text":"下调数量","effect":"mutate","patch":[{"key":"live_qty","value":"6"}],"when_entity":"p2"},{"kind":"link","testid":"nav_up_list","text":"返回上页","href":"projects.html","effect":"goto","when_entity":"p2"},{"kind":"link","testid":"open_mid","text":"场次","href":"scene.html","effect":"goto","when_entity":"p3"},{"kind":"link","testid":"open_side","text":"素材","href":"assets.html","effect":"goto","when_entity":"p3"},{"kind":"link","testid":"nav_prefs","text":"偏好","href":"settings.html","effect":"goto","when_entity":"p3"},{"kind":"button","testid":"btn_pin","text":"收藏","effect":"dead","when_entity":"p3"},{"kind":"button","testid":"btn_cool","text":"下调数量","effect":"mutate","patch":[{"key":"live_qty","value":"6"}],"when_entity":"p3"},{"kind":"link","testid":"nav_up_list","text":"返回上页","href":"projects.html","effect":"goto","when_entity":"p3"}]},"scene":{"title":"场次","blank":false,"entity_param":"","entity_source":"","obs":[],"obs_by_entity":{},"controls":[{"kind":"link","testid":"open_child_a","text":"成片","href":"render.html?id=a","effect":"goto"},{"kind":"link","testid":"open_child_b","text":"成片","href":"render.html?id=b","effect":"goto"},{"kind":"link","testid":"open_child_c","text":"成片","href":"render.html?id=c","effect":"goto"},{"kind":"button","testid":"btn_close","text":"关闭条目","effect":"mutate","patch":[{"key":"status_label","value":"已关闭"}]},{"kind":"button","testid":"btn_reopen","text":"重新打开","effect":"mutate","patch":[{"key":"reopened","value":"是"}]},{"kind":"link","testid":"nav_up_row","text":"返回上页","href":"project.html?id=p1","effect":"goto"}]},"render":{"title":"成片","blank":false,"entity_param":"id","entity_source":"","obs":[],"obs_by_entity":{"a":["status_label","reopened","handled","handled_label","handled_note"],"b":["status_label","reopened","handled","handled_label","handled_note"],"c":["status_label","reopened","handled","handled_label","handled_note"]},"controls":[{"kind":"button","testid":"btn_mark","text":"登记处理","effect":"mutate","patch":[{"key":"handled","value":"是"},{"key":"handled_label","value":"未登记"}],"reveal":"btn_follow","when_entity":"a"},{"kind":"button","testid":"btn_follow","text":"补充说明","effect":"mutate","patch":[{"key":"handled_note","value":"已补充"}],"reveal_after":"btn_mark","when_entity":"a"},{"kind":"link","testid":"nav_up_child","text":"返回上页","href":"scene.html","effect":"goto","when_entity":"a"},{"kind":"button","testid":"btn_mark","text":"登记处理","effect":"mutate","patch":[{"key":"handled","value":"是"},{"key":"handled_label","value":"未登记"}],"reveal":"btn_follow","when_entity":"b"},{"kind":"button","testid":"btn_follow","text":"补充说明","effect":"mutate","patch":[{"key":"handled_note","value":"已补充"}],"reveal_after":"btn_mark","when_entity":"b"},{"kind":"link","testid":"nav_up_child","text":"返回上页","href":"scene.html","effect":"goto","when_entity":"b"},{"kind":"button","testid":"btn_mark","text":"登记处理","effect":"mutate","patch":[{"key":"handled","value":"是"},{"key":"handled_label","value":"未登记"}],"reveal":"btn_follow","when_entity":"c"},{"kind":"button","testid":"btn_follow","text":"补充说明","effect":"mutate","patch":[{"key":"handled_note","value":"已补充"}],"reveal_after":"btn_mark","when_entity":"c"},{"kind":"link","testid":"nav_up_child","text":"返回上页","href":"scene.html","effect":"goto","when_entity":"c"}]},"assets":{"title":"素材","blank":false,"entity_param":"","entity_source":"","obs":["note_kind","note_visible","variant_note"],"obs_by_entity":{},"controls":[{"kind":"link","testid":"open_side_a1","text":"布景图","href":"asset.html?id=a1","effect":"goto"},{"kind":"link","testid":"open_side_a2","text":"音轨","href":"asset.html?id=a2","effect":"goto"},{"kind":"link","testid":"open_side_a3","text":"台词本","href":"asset.html?id=a3","effect":"goto"},{"kind":"link","testid":"nav_up_home_side","text":"返回首页","href":"index.html","effect":"goto"}]},"asset":{"title":"素材明细","blank":false,"entity_param":"id","entity_source":"side_rows","obs":[],"obs_by_entity":{"a1":["variant_note","note_kind","note_visible"],"a2":["variant_note","note_kind","note_visible"],"a3":["variant_note","note_kind","note_visible"]},"controls":[{"kind":"link","testid":"open_mid_b","text":"版本","href":"versions.html","effect":"goto","when_entity":"a1"},{"kind":"link","testid":"open_cross","text":"审片页","href":"review.html","effect":"goto","when_entity":"a1"},{"kind":"button","testid":"btn_variant","text":"改注记","effect":"mutate","patch":[{"key":"variant_note","value":"已改"}],"when_entity":"a1"},{"kind":"button","testid":"btn_staff_note","text":"内部摘记","effect":"mutate","patch":[{"key":"note_kind","value":"内部"},{"key":"note_visible","value":"公开"}],"when_entity":"a1"},{"kind":"link","testid":"nav_up_side","text":"返回上页","href":"assets.html","effect":"goto","when_entity":"a1"},{"kind":"link","testid":"open_mid_b","text":"版本","href":"versions.html","effect":"goto","when_entity":"a2"},{"kind":"link","testid":"open_cross","text":"审片页","href":"review.html","effect":"goto","when_entity":"a2"},{"kind":"button","testid":"btn_variant","text":"改注记","effect":"mutate","patch":[{"key":"variant_note","value":"已改"}],"when_entity":"a2"},{"kind":"button","testid":"btn_staff_note","text":"内部摘记","effect":"mutate","patch":[{"key":"note_kind","value":"内部"},{"key":"note_visible","value":"公开"}],"when_entity":"a2"},{"kind":"link","testid":"nav_up_side","text":"返回上页","href":"assets.html","effect":"goto","when_entity":"a2"},{"kind":"link","testid":"open_mid_b","text":"版本","href":"versions.html","effect":"goto","when_entity":"a3"},{"kind":"link","testid":"open_cross","text":"审片页","href":"review.html","effect":"goto","when_entity":"a3"},{"kind":"button","testid":"btn_variant","text":"改注记","effect":"mutate","patch":[{"key":"variant_note","value":"已改"}],"when_entity":"a3"},{"kind":"button","testid":"btn_staff_note","text":"内部摘记","effect":"mutate","patch":[{"key":"note_kind","value":"内部"},{"key":"note_visible","value":"公开"}],"when_entity":"a3"},{"kind":"link","testid":"nav_up_side","text":"返回上页","href":"assets.html","effect":"goto","when_entity":"a3"}]},"versions":{"title":"版本","blank":false,"entity_param":"","entity_source":"","obs":["note_kind","note_visible"],"obs_by_entity":{},"controls":[{"kind":"link","testid":"open_child_b_a","text":"发布单","href":"publish.html?id=a","effect":"goto"},{"kind":"link","testid":"open_child_b_b","text":"发布单","href":"publish.html?id=b","effect":"goto"},{"kind":"link","testid":"open_child_b_c","text":"发布单","href":"publish.html?id=c","effect":"goto"},{"kind":"button","testid":"btn_close","text":"关闭条目","effect":"mutate","patch":[{"key":"status_label","value":"已关闭"}]},{"kind":"button","testid":"btn_reopen","text":"重新打开","effect":"mutate","patch":[{"key":"reopened","value":"是"}]},{"kind":"link","testid":"nav_up_side_row","text":"返回上页","href":"asset.html?id=a1","effect":"goto"}]},"publish":{"title":"发布","blank":false,"entity_param":"id","entity_source":"","obs":[],"obs_by_entity":{"a":["status_label","reopened","handled","handled_label","handled_note"],"b":["status_label","reopened","handled","handled_label","handled_note"],"c":["status_label","reopened","handled","handled_label","handled_note"]},"controls":[{"kind":"button","testid":"btn_mark","text":"登记处理","effect":"mutate","patch":[{"key":"handled","value":"是"},{"key":"handled_label","value":"未登记"}],"reveal":"btn_follow","when_entity":"a"},{"kind":"button","testid":"btn_follow","text":"补充说明","effect":"mutate","patch":[{"key":"handled_note","value":"已补充"}],"reveal_after":"btn_mark","when_entity":"a"},{"kind":"link","testid":"nav_up_child","text":"返回上页","href":"versions.html","effect":"goto","when_entity":"a"},{"kind":"button","testid":"btn_mark","text":"登记处理","effect":"mutate","patch":[{"key":"handled","value":"是"},{"key":"handled_label","value":"未登记"}],"reveal":"btn_follow","when_entity":"b"},{"kind":"button","testid":"btn_follow","text":"补充说明","effect":"mutate","patch":[{"key":"handled_note","value":"已补充"}],"reveal_after":"btn_mark","when_entity":"b"},{"kind":"link","testid":"nav_up_child","text":"返回上页","href":"versions.html","effect":"goto","when_entity":"b"},{"kind":"button","testid":"btn_mark","text":"登记处理","effect":"mutate","patch":[{"key":"handled","value":"是"},{"key":"handled_label","value":"未登记"}],"reveal":"btn_follow","when_entity":"c"},{"kind":"button","testid":"btn_follow","text":"补充说明","effect":"mutate","patch":[{"key":"handled_note","value":"已补充"}],"reveal_after":"btn_mark","when_entity":"c"},{"kind":"link","testid":"nav_up_child","text":"返回上页","href":"versions.html","effect":"goto","when_entity":"c"}]},"comments":{"title":"批注","blank":false,"entity_param":"","entity_source":"","obs":["score_shown","score_live","scratch_a","scratch_b"],"obs_by_entity":{},"controls":[{"kind":"button","testid":"btn_note_a","text":"记一笔","effect":"mutate","patch":[{"key":"scratch_a","value":"已记"}]},{"kind":"button","testid":"btn_note_b","text":"标重点","effect":"mutate","patch":[{"key":"scratch_b","value":"已标"}]},{"kind":"link","testid":"nav_up_finding","text":"返回上页","href":"projects.html","effect":"goto"},{"kind":"link","testid":"nav_up_anchor","text":"返回名册","href":"review.html","effect":"goto"}]},"review":{"title":"审片","blank":false,"entity_param":"","entity_source":"","obs":[],"obs_by_entity":{},"controls":[{"kind":"link","testid":"open_lane_a","text":"渲染列","href":"renders.html?id=s1","effect":"goto"},{"kind":"link","testid":"open_finding_b","text":"批注页","href":"comments.html","effect":"goto"},{"kind":"link","testid":"open_leaf","text":"手册页","href":"handbook.html","effect":"goto"},{"kind":"link","testid":"nav_up_home_anchor","text":"返回首页","href":"index.html","effect":"goto"}]},"renders":{"title":"渲染列","blank":false,"entity_param":"id","entity_source":"","obs":[],"obs_by_entity":{"dest":["hold_mark","tag_mark"]},"controls":[{"kind":"link","testid":"open_lane_b","text":"下一段","href":"renders.html?id=s2","effect":"goto","when_entity":"s1"},{"kind":"link","testid":"nav_up_anchor_a","text":"返回上页","href":"review.html","effect":"goto","when_entity":"s1"},{"kind":"link","testid":"open_dest","text":"渲染页","href":"renders.html?id=dest","effect":"goto","when_entity":"s2"},{"kind":"link","testid":"nav_up_lane","text":"返回上页","href":"renders.html?id=s1","effect":"goto","when_entity":"s2"},{"kind":"button","testid":"btn_hold","text":"记下","effect":"mutate","patch":[{"key":"hold_mark","value":"是"}],"when_entity":"dest"},{"kind":"button","testid":"btn_tag","text":"加标记","effect":"mutate","patch":[{"key":"tag_mark","value":"是"}],"when_entity":"dest"},{"kind":"link","testid":"nav_up_lane_b","text":"返回上页","href":"renders.html?id=s2","effect":"goto","when_entity":"dest"}]},"handbook":{"title":"手册","blank":false,"entity_param":"","entity_source":"","obs":[],"obs_by_entity":{},"controls":[{"kind":"link","testid":"nav_up_help","text":"返回说明","href":"help.html","effect":"goto"}]},"help":{"title":"说明","blank":false,"entity_param":"","entity_source":"","obs":[],"obs_by_entity":{},"controls":[{"kind":"link","testid":"open_loop","text":"打开手册","href":"handbook.html","effect":"goto"},{"kind":"link","testid":"open_extra_0","text":"场次一览","href":"scenes.html","effect":"goto"}]},"scenes":{"title":"场次一览","blank":false,"entity_param":"","entity_source":"","obs":[],"obs_by_entity":{},"controls":[{"kind":"link","testid":"nav_up_extra_0","text":"返回上页","href":"help.html","effect":"goto"}]},"settings":{"title":"偏好","blank":false,"entity_param":"","entity_source":"","obs":["form_msg"],"obs_by_entity":{},"controls":[{"kind":"input","testid":"topic_title","text":"标题"},{"kind":"button","testid":"btn_submit","text":"提交","effect":"form"},{"kind":"button","testid":"btn_probe","text":"提交同步","effect":"throw","message":"studio sync handshake failed"},{"kind":"button","testid":"btn_export","text":"提交导出","effect":"post"},{"kind":"link","testid":"nav_up_from_prefs","text":"返回上页","href":"project.html?id=p1","effect":"goto"}]}}};
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
