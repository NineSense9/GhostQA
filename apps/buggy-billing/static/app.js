
(function () {
  "use strict";
  const MODEL = {"storage_key":"billing_v0315","fail_path":"/api/export","initial":{"obs":{"fee_display":"8","fee_remaining":"8","invoice_book":"120","topic_status":"跟进中","reopened":"否","note_kind":"","note_visibility":"","form_msg":"","search_state":"","slip_note":"","refund_mark":"","refund_note":""},"revealed":{}},"entities":{"accounts":[{"id":"a1","name":"北原能源"},{"id":"a2","name":"临江制造"},{"id":"a3","name":"星河科技"}],"invoices":[{"id":"i1","name":"六月维保"},{"id":"i2","name":"四月托管"},{"id":"i3","name":"五月备件"}]},"pages":{"home":{"title":"首页","blank":false,"entity_param":"","entity_source":"","obs":["search_state"],"obs_by_entity":{},"controls":[{"kind":"link","testid":"nav_accounts","text":"账户","href":"accounts.html","effect":"goto"},{"kind":"link","testid":"nav_invoices","text":"发票","href":"invoices.html","effect":"goto"},{"kind":"link","testid":"nav_help","text":"帮助","href":"help.html","effect":"goto"},{"kind":"input","testid":"search_box","text":"检索词"},{"kind":"button","testid":"btn_query_submit","text":"提交查询","effect":"search","message":"billing search query too long","input":"search_box","obs_key":"search_state"}]},"accounts":{"title":"账户","blank":false,"entity_param":"","entity_source":"","obs":[],"obs_by_entity":{},"controls":[{"kind":"link","testid":"open_acct_a1","text":"北原能源","href":"account.html?id=a1","effect":"goto"},{"kind":"link","testid":"open_acct_a2","text":"临江制造","href":"account.html?id=a2","effect":"goto"},{"kind":"link","testid":"open_acct_a3","text":"星河科技","href":"account.html?id=a3","effect":"goto"},{"kind":"link","testid":"nav_compose","text":"写单据","href":"compose.html","effect":"goto"},{"kind":"link","testid":"nav_payments","text":"收款列表","href":"payments.html","effect":"goto"},{"kind":"link","testid":"nav_up_home","text":"返回首页","href":"index.html","effect":"goto"}]},"account":{"title":"账户明细","blank":false,"entity_param":"","entity_source":"accounts","obs":[],"obs_by_entity":{},"controls":[{"kind":"link","testid":"open_bill_i1","text":"六月维保","href":"invoice.html?id=i1","effect":"goto"},{"kind":"link","testid":"open_bill_i2","text":"四月托管","href":"invoice.html?id=i2","effect":"goto"},{"kind":"link","testid":"nav_credits","text":"抵扣","href":"credits.html","effect":"goto"},{"kind":"link","testid":"nav_prefs","text":"偏好","href":"settings.html","effect":"goto"},{"kind":"button","testid":"btn_pin","text":"收藏","effect":"dead"},{"kind":"link","testid":"nav_up_accounts","text":"返回账户","href":"accounts.html","effect":"goto"}]},"invoices":{"title":"发票","blank":false,"entity_param":"","entity_source":"","obs":[],"obs_by_entity":{},"controls":[{"kind":"link","testid":"open_inv_i2","text":"四月托管","href":"invoice.html?id=i2","effect":"goto"},{"kind":"link","testid":"open_inv_i1","text":"六月维保","href":"invoice.html?id=i1","effect":"goto"},{"kind":"link","testid":"open_inv_i3","text":"另一张发票","href":"invoice.html?id=i1","effect":"goto"},{"kind":"link","testid":"nav_up_home_inv","text":"返回首页","href":"index.html","effect":"goto"}]},"invoice":{"title":"发票明细","blank":false,"entity_param":"id","entity_source":"invoices","obs":[],"obs_by_entity":{"i1":["fee_display","fee_remaining","invoice_book","note_kind","note_visibility"],"i2":["invoice_book"]},"controls":[{"kind":"link","testid":"open_receipt","text":"收款单","href":"payment.html?id=i1","effect":"goto","when_entity":"i1"},{"kind":"link","testid":"open_refund","text":"退回单","href":"refund.html?id=i1","effect":"goto","when_entity":"i1"},{"kind":"link","testid":"open_dispute","text":"争议单","href":"disputes.html?id=i1","effect":"goto","when_entity":"i1"},{"kind":"link","testid":"open_credit","text":"抵扣单","href":"credits.html?id=i1","effect":"goto","when_entity":"i1"},{"kind":"button","testid":"btn_adjust","text":"下调费用","effect":"mutate","patch":[{"key":"fee_remaining","value":"6"}],"when_entity":"i1"},{"kind":"button","testid":"btn_staff_note","text":"内部记录","effect":"mutate","patch":[{"key":"note_kind","value":"内部"},{"key":"note_visibility","value":"公开"}],"when_entity":"i1"},{"kind":"link","testid":"nav_up_acct","text":"返回账户","href":"account.html?id=a1","effect":"goto","when_entity":"i1"},{"kind":"link","testid":"open_dispute","text":"争议单","href":"disputes.html?id=i2","effect":"goto","when_entity":"i2"},{"kind":"link","testid":"open_receipt","text":"收款单","href":"payment.html?id=i2","effect":"goto","when_entity":"i2"},{"kind":"link","testid":"open_refund","text":"退回单","href":"refund.html?id=i2","effect":"goto","when_entity":"i2"},{"kind":"link","testid":"open_credit","text":"抵扣单","href":"credits.html?id=i2","effect":"goto","when_entity":"i2"},{"kind":"link","testid":"nav_up_invoices","text":"返回发票","href":"invoices.html","effect":"goto","when_entity":"i2"}]},"payment":{"title":"收款","blank":false,"entity_param":"","entity_source":"","obs":[],"obs_by_entity":{},"controls":[{"kind":"button","testid":"btn_post","text":"登记到账","effect":"mutate","patch":[{"key":"invoice_book","value":"80"}],"reveal":"btn_slip"},{"kind":"button","testid":"btn_slip","text":"追加回单","effect":"mutate","patch":[{"key":"slip_note","value":"已追加"}],"reveal_after":"btn_post"},{"kind":"link","testid":"nav_up_bill","text":"返回发票","href":"invoice.html?id=i1","effect":"goto"}]},"dispute":{"title":"争议","blank":false,"entity_param":"","entity_source":"","obs":[],"obs_by_entity":{},"controls":[{"kind":"link","testid":"open_refund_case","text":"退回单","href":"refund.html?id=i2","effect":"goto"},{"kind":"link","testid":"open_inv_case","text":"四月托管","href":"invoice.html?id=i2","effect":"goto"},{"kind":"link","testid":"open_credit_case","text":"抵扣单","href":"credits.html?id=i2","effect":"goto"},{"kind":"link","testid":"nav_up_bill_dispute","text":"返回发票","href":"invoice.html?id=i2","effect":"goto"}]},"refund":{"title":"退回","blank":false,"entity_param":"","entity_source":"","obs":[],"obs_by_entity":{},"controls":[{"kind":"button","testid":"btn_mark","text":"登记退回","effect":"mutate","patch":[{"key":"refund_mark","value":"是"}],"reveal":"btn_note"},{"kind":"button","testid":"btn_note","text":"补充说明","effect":"mutate","patch":[{"key":"refund_note","value":"已补充"}],"reveal_after":"btn_mark"},{"kind":"link","testid":"nav_up_credit","text":"返回抵扣","href":"credits.html?id=i2","effect":"goto"},{"kind":"link","testid":"nav_up_dispute","text":"返回争议","href":"disputes.html?id=i2","effect":"goto"}]},"credits":{"title":"抵扣","blank":false,"entity_param":"","entity_source":"","obs":["topic_status","reopened","note_kind","note_visibility"],"obs_by_entity":{},"controls":[{"kind":"button","testid":"btn_close","text":"关闭","effect":"mutate","patch":[{"key":"topic_status","value":"已关闭"}]},{"kind":"button","testid":"btn_reopen","text":"重新打开","effect":"mutate","patch":[{"key":"reopened","value":"是"}]},{"kind":"link","testid":"nav_up_refund","text":"返回退款","href":"refund.html?id=i2","effect":"goto"}]},"payments":{"title":"收款列表","blank":true,"entity_param":"","entity_source":"","obs":[],"obs_by_entity":{},"controls":[]},"refunds":{"title":"退回列表","blank":false,"entity_param":"","entity_source":"","obs":[],"obs_by_entity":{},"controls":[{"kind":"link","testid":"open_refund_a","text":"一笔退回","href":"refund.html?id=i1","effect":"goto"},{"kind":"link","testid":"open_refund_b","text":"另一笔退回","href":"refund.html?id=i2","effect":"goto"},{"kind":"link","testid":"nav_up_home_refunds","text":"返回首页","href":"index.html","effect":"goto"}]},"reports":{"title":"账期汇总","blank":false,"entity_param":"","entity_source":"","obs":[],"obs_by_entity":{},"controls":[{"kind":"link","testid":"nav_up_home_period","text":"返回首页","href":"index.html","effect":"goto"}]},"compose":{"title":"撰写","blank":false,"entity_param":"","entity_source":"","obs":["form_msg"],"obs_by_entity":{},"controls":[{"kind":"input","testid":"topic_title","text":"标题"},{"kind":"button","testid":"btn_submit","text":"提交","effect":"form"},{"kind":"link","testid":"nav_up_home","text":"返回首页","href":"index.html","effect":"goto"}]},"settings":{"title":"偏好","blank":false,"entity_param":"","entity_source":"","obs":[],"obs_by_entity":{},"controls":[{"kind":"button","testid":"btn_probe","text":"测试同步","effect":"throw","message":"billing sync handshake failed"},{"kind":"button","testid":"btn_export","text":"导出","effect":"post"},{"kind":"link","testid":"nav_up_from_prefs","text":"返回账户","href":"account.html?id=a1","effect":"goto"}]},"search":{"title":"检索","blank":false,"entity_param":"","entity_source":"","obs":[],"obs_by_entity":{},"controls":[{"kind":"link","testid":"nav_up_home_search","text":"返回首页","href":"index.html","effect":"goto"}]},"help":{"title":"说明","blank":false,"entity_param":"","entity_source":"","obs":[],"obs_by_entity":{},"controls":[{"kind":"link","testid":"open_handbook","text":"打开手册","href":"handbook.html","effect":"goto"}]},"handbook":{"title":"手册","blank":false,"entity_param":"","entity_source":"","obs":[],"obs_by_entity":{},"controls":[{"kind":"link","testid":"nav_up_help","text":"返回说明","href":"help.html","effect":"goto"}]}}};
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
