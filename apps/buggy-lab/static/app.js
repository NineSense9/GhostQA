
(function () {
  "use strict";
  const MODEL = {"storage_key":"lab_v0315","fail_path":"/api/export","initial":{"obs":{"heat_display":"8","heat_remaining":"8","run_note":"待观测","topic_status":"跟进中","reopened":"否","note_kind":"","note_visibility":"","form_msg":"","search_state":"","batch_note":"","baseline":"","compare_note":""},"revealed":{}},"entities":{"projects":[{"id":"p1","name":"夜航观测"},{"id":"p2","name":"东岸对照"}],"experiments":[{"id":"e1","name":"振荡复核"},{"id":"e2","name":"温度曲线"},{"id":"e3","name":"溶剂对照"}],"runs":[{"id":"u1","name":"午后批次"}],"samples":[{"id":"s1","name":"瓶B"},{"id":"s2","name":"瓶A"}],"results":[{"id":"q1","name":"空白漂移"}]},"pages":{"home":{"title":"首页","blank":false,"entity_param":"","entity_source":"","obs":["search_state"],"obs_by_entity":{},"controls":[{"kind":"link","testid":"nav_projects","text":"项目","href":"projects.html","effect":"goto"},{"kind":"link","testid":"nav_experiments","text":"实验","href":"experiments.html","effect":"goto"},{"kind":"link","testid":"nav_help","text":"帮助","href":"help.html","effect":"goto"},{"kind":"input","testid":"search_box","text":"检索词"},{"kind":"button","testid":"btn_query_submit","text":"提交查询","effect":"search","message":"lab search query too long","input":"search_box","obs_key":"search_state"}]},"projects":{"title":"项目","blank":false,"entity_param":"","entity_source":"","obs":[],"obs_by_entity":{},"controls":[{"kind":"link","testid":"open_proj_p1","text":"夜航观测","href":"project.html?id=p1","effect":"goto"},{"kind":"link","testid":"open_proj_p2","text":"东岸对照","href":"project.html?id=p2","effect":"goto"},{"kind":"link","testid":"nav_up_home","text":"返回首页","href":"index.html","effect":"goto"}]},"project":{"title":"项目明细","blank":false,"entity_param":"","entity_source":"projects","obs":[],"obs_by_entity":{},"controls":[{"kind":"link","testid":"open_exp_e1","text":"振荡复核","href":"experiment.html?id=e1","effect":"goto"},{"kind":"link","testid":"open_exp_e3","text":"溶剂对照","href":"experiment.html?id=e3","effect":"goto"},{"kind":"link","testid":"nav_runs","text":"批次列表","href":"runs.html","effect":"goto"},{"kind":"link","testid":"nav_prefs","text":"偏好","href":"settings.html","effect":"goto"},{"kind":"link","testid":"nav_compose","text":"写记录","href":"compose.html","effect":"goto"},{"kind":"button","testid":"btn_pin","text":"收藏","effect":"dead"},{"kind":"link","testid":"nav_up_projects","text":"返回项目","href":"projects.html","effect":"goto"}]},"experiments":{"title":"实验","blank":false,"entity_param":"","entity_source":"","obs":[],"obs_by_entity":{},"controls":[{"kind":"link","testid":"open_exp_e2","text":"温度曲线","href":"experiment.html?id=e2","effect":"goto"},{"kind":"link","testid":"open_exp_e1b","text":"振荡复核","href":"experiment.html?id=e1","effect":"goto"},{"kind":"link","testid":"open_exp_e3b","text":"溶剂对照","href":"experiment.html?id=e3","effect":"goto"},{"kind":"link","testid":"nav_samples","text":"样品架","href":"samples.html","effect":"goto"},{"kind":"link","testid":"nav_up_home_exp","text":"返回首页","href":"index.html","effect":"goto"}]},"experiment":{"title":"实验明细","blank":false,"entity_param":"id","entity_source":"experiments","obs":[],"obs_by_entity":{},"controls":[{"kind":"link","testid":"open_run_u1","text":"午后批次","href":"run.html?id=u1","effect":"goto","when_entity":"e1"},{"kind":"link","testid":"open_result_side","text":"空白漂移","href":"result.html?id=q1","effect":"goto","when_entity":"e1"},{"kind":"link","testid":"nav_results","text":"结果列表","href":"results.html","effect":"goto","when_entity":"e1"},{"kind":"link","testid":"nav_up_project","text":"返回项目","href":"project.html?id=p1","effect":"goto","when_entity":"e1"},{"kind":"link","testid":"open_result_q1","text":"空白漂移","href":"result.html?id=q1","effect":"goto","when_entity":"e2"},{"kind":"link","testid":"open_run_side","text":"午后批次","href":"run.html?id=u1","effect":"goto","when_entity":"e2"},{"kind":"link","testid":"nav_notebook_side","text":"记录本","href":"notebook.html?id=q1","effect":"goto","when_entity":"e2"},{"kind":"link","testid":"nav_up_experiments","text":"返回实验","href":"experiments.html","effect":"goto","when_entity":"e2"}]},"run":{"title":"批次","blank":false,"entity_param":"","entity_source":"runs","obs":["run_note","heat_display","heat_remaining"],"obs_by_entity":{},"controls":[{"kind":"link","testid":"open_sample_s1","text":"瓶B","href":"sample.html?id=s1","effect":"goto"},{"kind":"link","testid":"open_result_from_run","text":"空白漂移","href":"result.html?id=q1","effect":"goto"},{"kind":"link","testid":"open_sample_s2","text":"瓶A","href":"sample.html?id=s2","effect":"goto"},{"kind":"button","testid":"btn_staff_note","text":"内部记录","effect":"mutate","patch":[{"key":"note_kind","value":"内部"},{"key":"note_visibility","value":"公开"}]},{"kind":"button","testid":"btn_cool","text":"下调读数","effect":"mutate","patch":[{"key":"heat_remaining","value":"6"}]},{"kind":"link","testid":"nav_up_exp","text":"返回实验","href":"experiment.html?id=e1","effect":"goto"}]},"sample":{"title":"样品","blank":false,"entity_param":"","entity_source":"samples","obs":[],"obs_by_entity":{},"controls":[{"kind":"button","testid":"btn_obs","text":"记录观测","effect":"mutate","patch":[{"key":"run_note","value":"已观测"}],"reveal":"btn_batch"},{"kind":"button","testid":"btn_batch","text":"补充批次","effect":"mutate","patch":[{"key":"batch_note","value":"已补充"}],"reveal_after":"btn_obs"},{"kind":"link","testid":"nav_up_run","text":"返回批次","href":"run.html?id=u1","effect":"goto"}]},"result":{"title":"结果","blank":false,"entity_param":"","entity_source":"results","obs":["topic_status","reopened","note_kind","note_visibility"],"obs_by_entity":{},"controls":[{"kind":"link","testid":"open_compare","text":"对照","href":"compare.html?id=q1","effect":"goto"},{"kind":"link","testid":"open_notebook","text":"记录本","href":"notebook.html?id=q1","effect":"goto"},{"kind":"link","testid":"open_run_again","text":"午后批次","href":"run.html?id=u1","effect":"goto"},{"kind":"button","testid":"btn_close","text":"关闭","effect":"mutate","patch":[{"key":"topic_status","value":"已关闭"}]},{"kind":"button","testid":"btn_reopen","text":"重新打开","effect":"mutate","patch":[{"key":"reopened","value":"是"}]},{"kind":"link","testid":"nav_up_exp_result","text":"返回实验","href":"experiment.html?id=e2","effect":"goto"}]},"compare":{"title":"对照","blank":false,"entity_param":"","entity_source":"","obs":[],"obs_by_entity":{},"controls":[{"kind":"button","testid":"btn_pin_base","text":"固定基线","effect":"mutate","patch":[{"key":"baseline","value":"是"}],"reveal":"btn_compare_note"},{"kind":"button","testid":"btn_compare_note","text":"补充对照","effect":"mutate","patch":[{"key":"compare_note","value":"已补充"}],"reveal_after":"btn_pin_base"},{"kind":"link","testid":"nav_up_result","text":"返回结果","href":"result.html?id=q1","effect":"goto"}]},"notebook":{"title":"记录本","blank":false,"entity_param":"","entity_source":"","obs":[],"obs_by_entity":{},"controls":[{"kind":"link","testid":"open_compare_from_note","text":"查看对照","href":"compare.html?id=q1","effect":"goto"},{"kind":"link","testid":"nav_up_result_note","text":"返回结果","href":"result.html?id=q1","effect":"goto"}]},"runs":{"title":"批次列表","blank":false,"entity_param":"","entity_source":"","obs":[],"obs_by_entity":{},"controls":[{"kind":"link","testid":"open_run_list","text":"午后批次","href":"run.html?id=u1","effect":"goto"},{"kind":"link","testid":"nav_up_project_runs","text":"返回项目","href":"project.html?id=p1","effect":"goto"}]},"samples":{"title":"样品架","blank":true,"entity_param":"","entity_source":"","obs":[],"obs_by_entity":{},"controls":[]},"results":{"title":"结果列表","blank":false,"entity_param":"","entity_source":"","obs":[],"obs_by_entity":{},"controls":[{"kind":"link","testid":"open_result_list","text":"空白漂移","href":"result.html?id=q1","effect":"goto"},{"kind":"link","testid":"nav_up_home_results","text":"返回首页","href":"index.html","effect":"goto"}]},"compose":{"title":"撰写","blank":false,"entity_param":"","entity_source":"","obs":["form_msg"],"obs_by_entity":{},"controls":[{"kind":"input","testid":"topic_title","text":"标题"},{"kind":"button","testid":"btn_submit","text":"提交","effect":"form"},{"kind":"link","testid":"nav_up_home","text":"返回首页","href":"index.html","effect":"goto"}]},"settings":{"title":"偏好","blank":false,"entity_param":"","entity_source":"","obs":[],"obs_by_entity":{},"controls":[{"kind":"button","testid":"btn_probe","text":"测试同步","effect":"throw","message":"lab sync handshake failed"},{"kind":"button","testid":"btn_export","text":"导出","effect":"post"},{"kind":"link","testid":"nav_up_from_prefs","text":"返回项目","href":"project.html?id=p1","effect":"goto"}]},"search":{"title":"检索","blank":false,"entity_param":"","entity_source":"","obs":[],"obs_by_entity":{},"controls":[{"kind":"link","testid":"nav_up_home_search","text":"返回首页","href":"index.html","effect":"goto"}]},"help":{"title":"说明","blank":false,"entity_param":"","entity_source":"","obs":[],"obs_by_entity":{},"controls":[{"kind":"link","testid":"open_handbook","text":"打开手册","href":"handbook.html","effect":"goto"}]},"handbook":{"title":"手册","blank":false,"entity_param":"","entity_source":"","obs":[],"obs_by_entity":{},"controls":[{"kind":"link","testid":"nav_up_help","text":"返回说明","href":"help.html","effect":"goto"}]}}};
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
