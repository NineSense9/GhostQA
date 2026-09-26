
(function () {
  "use strict";
  const MODEL = {"storage_key":"harbor_v0326","fail_path":"/api/export","initial":{"obs":{"score_shown":"8","score_live":"6","shown_qty":"8","live_qty":"8","status_label":"跟进中","reopened":"否","note_kind":"","note_visible":"","handled":"","handled_label":"","handled_note":"","form_msg":"","search_state":"","scratch_a":"","scratch_b":"","hold_mark":"","tag_mark":""},"revealed":{}},"entities":{"records":[{"id":"r1","name":"丁卷"},{"id":"r2","name":"乙卷"},{"id":"r3","name":"丙卷"}],"shifts":[{"id":"s1","name":"午班"},{"id":"s2","name":"晚班"},{"id":"s3","name":"早班"}]},"pages":{"home":{"title":"首页","blank":false,"entity_param":"","entity_source":"","obs":["search_state"],"obs_by_entity":{},"controls":[{"kind":"link","testid":"nav_roster","text":"名册","href":"roster.html","effect":"goto"},{"kind":"link","testid":"nav_board","text":"看板","href":"board.html","effect":"goto"},{"kind":"link","testid":"nav_blank","text":"空白页","href":"blank.html","effect":"goto"},{"kind":"link","testid":"open_aid","text":"帮助","href":"help.html","effect":"goto"},{"kind":"input","testid":"search_box","text":"检索词"},{"kind":"button","testid":"btn_query_submit","text":"提交查询","effect":"search","message":"harbor search query too long","input":"search_box","obs_key":"search_state"}]},"blank":{"title":"空白页","blank":true,"entity_param":"","entity_source":"","obs":[],"obs_by_entity":{},"controls":[]},"roster":{"title":"名册","blank":false,"entity_param":"","entity_source":"","obs":[],"obs_by_entity":{},"controls":[{"kind":"link","testid":"open_r1","text":"丁卷","href":"chart.html?id=r1","effect":"goto"},{"kind":"link","testid":"open_r2","text":"乙卷","href":"chart.html?id=r2","effect":"goto"},{"kind":"link","testid":"open_r3","text":"丙卷","href":"chart.html?id=r3","effect":"goto"},{"kind":"link","testid":"nav_up_home","text":"返回首页","href":"index.html","effect":"goto"}]},"chart":{"title":"图表","blank":false,"entity_param":"id","entity_source":"records","obs":[],"obs_by_entity":{"r1":["shown_qty","live_qty"],"r2":["shown_qty","live_qty"],"r3":["shown_qty","live_qty"]},"controls":[{"kind":"link","testid":"open_order","text":"医嘱","href":"order.html","effect":"goto","when_entity":"r1"},{"kind":"link","testid":"open_desk","text":"台面","href":"desk.html","effect":"goto","when_entity":"r1"},{"kind":"link","testid":"open_finding","text":"记分页","href":"finding.html","effect":"goto","when_entity":"r1"},{"kind":"button","testid":"btn_pin","text":"收藏","effect":"dead","when_entity":"r1"},{"kind":"button","testid":"btn_cool","text":"下调数量","effect":"mutate","patch":[{"key":"live_qty","value":"6"}],"when_entity":"r1"},{"kind":"link","testid":"nav_up_roster","text":"返回名册","href":"roster.html","effect":"goto","when_entity":"r1"},{"kind":"link","testid":"open_order","text":"医嘱","href":"order.html","effect":"goto","when_entity":"r2"},{"kind":"link","testid":"open_desk","text":"台面","href":"desk.html","effect":"goto","when_entity":"r2"},{"kind":"link","testid":"open_finding","text":"记分页","href":"finding.html","effect":"goto","when_entity":"r2"},{"kind":"button","testid":"btn_pin","text":"收藏","effect":"dead","when_entity":"r2"},{"kind":"button","testid":"btn_cool","text":"下调数量","effect":"mutate","patch":[{"key":"live_qty","value":"6"}],"when_entity":"r2"},{"kind":"link","testid":"nav_up_roster","text":"返回名册","href":"roster.html","effect":"goto","when_entity":"r2"},{"kind":"link","testid":"open_order","text":"医嘱","href":"order.html","effect":"goto","when_entity":"r3"},{"kind":"link","testid":"open_desk","text":"台面","href":"desk.html","effect":"goto","when_entity":"r3"},{"kind":"link","testid":"open_finding","text":"记分页","href":"finding.html","effect":"goto","when_entity":"r3"},{"kind":"button","testid":"btn_pin","text":"收藏","effect":"dead","when_entity":"r3"},{"kind":"button","testid":"btn_cool","text":"下调数量","effect":"mutate","patch":[{"key":"live_qty","value":"6"}],"when_entity":"r3"},{"kind":"link","testid":"nav_up_roster","text":"返回名册","href":"roster.html","effect":"goto","when_entity":"r3"}]},"order":{"title":"医嘱","blank":false,"entity_param":"","entity_source":"","obs":["status_label","reopened"],"obs_by_entity":{},"controls":[{"kind":"link","testid":"open_slip","text":"单据","href":"slip.html","effect":"goto"},{"kind":"button","testid":"btn_close","text":"关闭条目","effect":"mutate","patch":[{"key":"status_label","value":"已关闭"}]},{"kind":"button","testid":"btn_reopen","text":"重新打开","effect":"mutate","patch":[{"key":"reopened","value":"是"}]},{"kind":"link","testid":"nav_up_chart","text":"返回图表","href":"chart.html?id=r1","effect":"goto"}]},"slip":{"title":"单据","blank":false,"entity_param":"","entity_source":"","obs":["handled","handled_label","handled_note"],"obs_by_entity":{},"controls":[{"kind":"button","testid":"btn_mark","text":"登记处理","effect":"mutate","patch":[{"key":"handled","value":"是"},{"key":"handled_label","value":"未登记"}],"reveal":"btn_follow"},{"kind":"button","testid":"btn_follow","text":"补充说明","effect":"mutate","patch":[{"key":"handled_note","value":"已补充"}],"reveal_after":"btn_mark"},{"kind":"link","testid":"nav_up_order","text":"返回医嘱","href":"order.html","effect":"goto"}]},"board":{"title":"看板","blank":false,"entity_param":"","entity_source":"","obs":["note_kind","note_visible"],"obs_by_entity":{},"controls":[{"kind":"link","testid":"open_s1","text":"午班","href":"slot.html?id=s1","effect":"goto"},{"kind":"link","testid":"open_s2","text":"晚班","href":"slot.html?id=s2","effect":"goto"},{"kind":"link","testid":"open_s3","text":"早班","href":"slot.html?id=s3","effect":"goto"},{"kind":"link","testid":"nav_up_home_board","text":"返回首页","href":"index.html","effect":"goto"}]},"slot":{"title":"班次","blank":false,"entity_param":"id","entity_source":"shifts","obs":[],"obs_by_entity":{"s1":["note_kind","note_visible","handled","handled_label"],"s2":["note_kind","note_visible","handled","handled_label"],"s3":["note_kind","note_visible","handled","handled_label"]},"controls":[{"kind":"link","testid":"open_notice","text":"通知","href":"notice.html","effect":"goto","when_entity":"s1"},{"kind":"button","testid":"btn_internal","text":"内部标注","effect":"mutate","patch":[{"key":"note_kind","value":"内部"},{"key":"note_visible","value":"公开"}],"when_entity":"s1"},{"kind":"button","testid":"btn_mark","text":"登记处理","effect":"mutate","patch":[{"key":"handled","value":"是"},{"key":"handled_label","value":"未登记"}],"when_entity":"s1"},{"kind":"link","testid":"nav_up_board","text":"返回看板","href":"board.html","effect":"goto","when_entity":"s1"},{"kind":"link","testid":"open_notice","text":"通知","href":"notice.html","effect":"goto","when_entity":"s2"},{"kind":"button","testid":"btn_internal","text":"内部标注","effect":"mutate","patch":[{"key":"note_kind","value":"内部"},{"key":"note_visible","value":"公开"}],"when_entity":"s2"},{"kind":"button","testid":"btn_mark","text":"登记处理","effect":"mutate","patch":[{"key":"handled","value":"是"},{"key":"handled_label","value":"未登记"}],"when_entity":"s2"},{"kind":"link","testid":"nav_up_board","text":"返回看板","href":"board.html","effect":"goto","when_entity":"s2"},{"kind":"link","testid":"open_notice","text":"通知","href":"notice.html","effect":"goto","when_entity":"s3"},{"kind":"button","testid":"btn_internal","text":"内部标注","effect":"mutate","patch":[{"key":"note_kind","value":"内部"},{"key":"note_visible","value":"公开"}],"when_entity":"s3"},{"kind":"button","testid":"btn_mark","text":"登记处理","effect":"mutate","patch":[{"key":"handled","value":"是"},{"key":"handled_label","value":"未登记"}],"when_entity":"s3"},{"kind":"link","testid":"nav_up_board","text":"返回看板","href":"board.html","effect":"goto","when_entity":"s3"}]},"notice":{"title":"通知","blank":false,"entity_param":"","entity_source":"","obs":["note_kind","note_visible"],"obs_by_entity":{},"controls":[{"kind":"link","testid":"nav_up_slot","text":"返回班次","href":"slot.html?id=s1","effect":"goto"}]},"desk":{"title":"台面","blank":false,"entity_param":"","entity_source":"","obs":[],"obs_by_entity":{},"controls":[{"kind":"link","testid":"open_lane","text":"问询单","href":"lane.html?id=s1","effect":"goto"},{"kind":"link","testid":"open_pad","text":"附记","href":"pad.html","effect":"goto"},{"kind":"link","testid":"open_leaf","text":"附页","href":"leaf.html","effect":"goto"},{"kind":"link","testid":"nav_up_chart_desk","text":"返回图表","href":"chart.html?id=r1","effect":"goto"}]},"lane":{"title":"问询","blank":false,"entity_param":"id","entity_source":"","obs":[],"obs_by_entity":{"dest":["hold_mark","tag_mark"]},"controls":[{"kind":"link","testid":"open_lane_b","text":"下一段","href":"lane.html?id=s2","effect":"goto","when_entity":"s1"},{"kind":"link","testid":"nav_up_desk","text":"返回台面","href":"desk.html","effect":"goto","when_entity":"s1"},{"kind":"link","testid":"open_dest","text":"尾页","href":"lane.html?id=dest","effect":"goto","when_entity":"s2"},{"kind":"link","testid":"nav_up_lane","text":"返回上页","href":"lane.html?id=s1","effect":"goto","when_entity":"s2"},{"kind":"button","testid":"btn_hold","text":"记下","effect":"mutate","patch":[{"key":"hold_mark","value":"是"}],"when_entity":"dest"},{"kind":"button","testid":"btn_tag","text":"加标记","effect":"mutate","patch":[{"key":"tag_mark","value":"是"}],"when_entity":"dest"},{"kind":"link","testid":"nav_up_lane_b","text":"返回上页","href":"lane.html?id=s2","effect":"goto","when_entity":"dest"}]},"finding":{"title":"记分","blank":false,"entity_param":"","entity_source":"","obs":["score_shown","score_live","scratch_a","scratch_b"],"obs_by_entity":{},"controls":[{"kind":"button","testid":"btn_note_a","text":"记一笔","effect":"mutate","patch":[{"key":"scratch_a","value":"已记"}]},{"kind":"button","testid":"btn_note_b","text":"标重点","effect":"mutate","patch":[{"key":"scratch_b","value":"已标"}]},{"kind":"link","testid":"nav_up_chart_finding","text":"返回图表","href":"chart.html?id=r1","effect":"goto"}]},"pad":{"title":"附记","blank":false,"entity_param":"","entity_source":"","obs":[],"obs_by_entity":{},"controls":[{"kind":"link","testid":"nav_up_desk_pad","text":"返回台面","href":"desk.html","effect":"goto"}]},"leaf":{"title":"附页","blank":false,"entity_param":"","entity_source":"","obs":[],"obs_by_entity":{},"controls":[{"kind":"link","testid":"nav_up_desk_leaf","text":"返回台面","href":"desk.html","effect":"goto"}]},"help":{"title":"说明","blank":false,"entity_param":"","entity_source":"","obs":[],"obs_by_entity":{},"controls":[{"kind":"link","testid":"open_loop","text":"偏好页","href":"settings.html","effect":"goto"}]},"settings":{"title":"偏好","blank":false,"entity_param":"","entity_source":"","obs":["form_msg"],"obs_by_entity":{},"controls":[{"kind":"input","testid":"topic_title","text":"标题"},{"kind":"button","testid":"btn_submit","text":"提交","effect":"form"},{"kind":"button","testid":"btn_probe","text":"提交同步","effect":"throw","message":"harbor sync handshake failed"},{"kind":"button","testid":"btn_export","text":"提交导出","effect":"post"},{"kind":"link","testid":"open_loop","text":"说明页","href":"help.html","effect":"goto"},{"kind":"link","testid":"nav_up_chart_prefs","text":"返回图表","href":"chart.html?id=r1","effect":"goto"}]}}};
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
