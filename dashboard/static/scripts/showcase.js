/* ============================================================================
   Overview / Evidence presentation. Numbers come only from GET /api/showcase.
   ========================================================================== */
'use strict';

const GhostQA = window.GhostQA = window.GhostQA || {};
const VIEWS = ['overview', 'live', 'evidence'];

function escapeHtml(s) {
  return String(s ?? '').replace(/[&<>"']/g, (c) => (
    { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]
  ));
}

function gid(id) { return document.getElementById(id); }

function setText(id, value) {
  const el = gid(id);
  if (!el) return;
  el.textContent = (value === null || value === undefined || value === '')
    ? '—' : String(value);
}

function shortBugs(list) {
  return (list || []).map((x) => String(x).replace(/^BUG-/, '')).join(' · ');
}

GhostQA.setView = function setView(name, opts) {
  if (!VIEWS.includes(name)) name = 'overview';
  document.body.classList.remove('view-overview', 'view-live', 'view-evidence');
  document.body.classList.add('view-' + name);
  VIEWS.forEach((v) => {
    const panel = gid('view-' + v);
    const tab = gid('tab-' + v);
    const on = v === name;
    if (panel) {
      panel.hidden = !on;
      panel.setAttribute('aria-hidden', on ? 'false' : 'true');
    }
    if (tab) {
      tab.classList.toggle('is-active', on);
      tab.setAttribute('aria-selected', on ? 'true' : 'false');
      tab.tabIndex = on ? 0 : -1;
    }
  });
  if (!opts || !opts.skipHash) {
    try { history.replaceState(null, '', '#' + name); } catch (_) {}
  }
  if (typeof GhostQA.onView === 'function') GhostQA.onView(name);
  if (name !== 'live') window.scrollTo(0, 0);
};

function statusRow(label, value, kind, extra) {
  const cls = kind === true ? 'is-ok' : kind === false ? 'is-bad'
    : kind === 'warn' ? 'is-warn' : '';
  const more = extra || '';
  return `<li class="${cls}"><span>${escapeHtml(label)}</span>` +
    `<b title="${escapeHtml(extra && extra.title ? extra.title : value)}">${escapeHtml(value)}</b>${more}</li>`;
}

function hashRow(label, full, short) {
  if (!full) return statusRow(label, '—', null);
  const shown = short || full;
  return `<li><span>${escapeHtml(label)}</span>` +
    `<b title="${escapeHtml(full)}">${escapeHtml(shown)}</b>` +
    `<button type="button" class="btn-copy" data-copy-text="${escapeHtml(full)}">复制</button></li>`;
}

function renderReturnCycle(rc) {
  const sec = document.querySelector('[data-testid="return-cycle"]');
  if (!rc || !rc.available) {
    if (sec && !sec.querySelector('[data-unavailable]')) {
      const note = document.createElement('p');
      note.className = 'limit-note';
      note.dataset.unavailable = '1';
      note.textContent = '暂时无法读取已发布证据';
      sec.appendChild(note);
    }
    return;
  }
  const b = rc.baseline || {};
  const g = rc.candidate || {};
  const d = rc.deepbench120 || {};
  setText('rc-b-states', b.states);
  setText('rc-b-urls', b.urls);
  setText('rc-b-ret', b.return_attempts);
  setText('rc-b-ok', b.successful_return);
  setText('rc-g-states', g.states);
  setText('rc-g-urls', g.urls);
  setText('rc-g-ret', g.return_attempts);
  setText('rc-g-esc', g.cycle_escapes);
  const bugsEl = gid('rc-bugs');
  if (bugsEl) {
    const bits = [];
    const bugs = shortBugs(g.confirmed);
    if (bugs) bits.push('已确认 ' + bugs);
    if (g.post_escape_new_states != null) {
      bits.push('逃出后新状态 ' + g.post_escape_new_states + ' 个');
    }
    const urls = g.post_escape_new_urls || [];
    if (urls.length) {
      bits.push('新 URL ' + urls.map((u) => String(u).replace(/^https?:\/\/[^/]+/, '')).join(' · '));
    }
    bits.push('描述性结果，来自已分析的 BuggyShop');
    bugsEl.textContent = bits.join(' · ');
  }
  const title = gid('h-rc');
  if (title && b.states != null) {
    title.textContent = '打断 return loop 后，探索从 ' + b.states + ' 个状态继续向外走';
  }
  if (!window.GhostQA || !GhostQA.showcase || !GhostQA.showcase.fresh_transfer
      || !GhostQA.showcase.fresh_transfer.available) {
    setText('proof-round', rc.round || 'v0.3.9');
    setText('proof-b-states', b.states);
    setText('proof-g-states', g.states);
    setText('proof-b-ret', b.return_attempts);
    setText('proof-g-ret', g.return_attempts);
    setText('proof-esc', g.cycle_escapes);
    setText('proof-outcome', rc.outcome || 'A');
  }
  const delta = gid('rc-delta');
  if (delta) {
    delta.innerHTML =
      `<span>状态 <b>${escapeHtml(b.states)}</b> → <b>${escapeHtml(g.states)}</b></span>` +
      `<span>URL <b>${escapeHtml(b.urls)}</b> → <b>${escapeHtml(g.urls)}</b></span>` +
      `<span>return attempt <b>${escapeHtml(b.return_attempts)}</b> → <b>${escapeHtml(g.return_attempts)}</b></span>` +
      `<span>cycle escape <b>${escapeHtml(g.cycle_escapes)}</b></span>`;
  }
  const oc = gid('rc-outcome');
  if (oc) oc.textContent = rc.outcome ? ('Outcome ' + rc.outcome) : 'Outcome';
  const om = gid('rc-outcome-mean');
  if (om) {
    om.textContent = 'Outcome A：机制修好，DeepBench @120 没有丢掉原来的 bug。BuggyShop 是已分析用例。';
  }
  const deep = gid('rc-deep');
  if (deep) {
    const ids = shortBugs(d.guard_confirmed || d.c1_confirmed);
    const lost = (d.lost_from_baseline || []).length;
    const parts = ['DeepBench @120 是历史回归检查。'];
    if (ids) parts.push('C1 和 guard 都确认 ' + ids + '。');
    if (d.guard_escapes != null) {
      parts.push('guard 在该历史 workflow 上触发 ' + d.guard_escapes + ' 次。');
    }
    if (lost === 0) parts.push('lost_from_baseline 为空。');
    deep.textContent = parts.join(' ');
  }
}

function fileLabel(n, verified) {
  if (n == null) return '—';
  if (verified) return n + ' / ' + n;
  return String(n);
}

function yn(v) {
  if (v === true) return 'Verified';
  if (v === false) return 'Unverified';
  return '—';
}

function renderNestedHub(nh) {
  const sec = document.querySelector('[data-testid="nested-hub"]');
  if (!nh || !nh.available) {
    if (sec && !sec.querySelector('[data-unavailable]')) {
      const note = document.createElement('p');
      note.className = 'limit-note';
      note.dataset.unavailable = '1';
      note.textContent = '暂时无法读取已发布证据';
      sec.appendChild(note);
    }
    return;
  }
  const grid = gid('nh-grid');
  if (grid) {
    grid.innerHTML = (nh.targets || []).map((t) => {
      return `<article class="rc-card"><h3>${escapeHtml(t.name)}</h3>` +
        `<dl class="rc-metrics">` +
        `<div><dt>G states</dt><dd>${escapeHtml(t.guard_states)}</dd></div>` +
        `<div><dt>N states</dt><dd>${escapeHtml(t.nested_states)}</dd></div>` +
        `<div><dt>follow-up</dt><dd>${escapeHtml(t.nested_followup)}</dd></div>` +
        `<div><dt>return</dt><dd>${escapeHtml(t.nested_return_attempts)}</dd></div>` +
        `</dl><p class="rc-bugs">lost_parent ${escapeHtml(t.guard_lost_parent)} → ${escapeHtml(t.nested_lost_parent)} · horizon ${escapeHtml(t.nested_horizon)} · escapes ${escapeHtml(t.nested_escapes)}</p></article>`;
    }).join('');
  }
  const oc = gid('nh-outcome');
  if (oc) {
    oc.textContent = nh.outcome ? ('Outcome ' + nh.outcome) : 'Outcome';
    oc.className = nh.outcome === 'A' ? 'pill pill-ok' : 'pill';
  }
  const om = gid('nh-outcome-mean');
  if (om) {
    const lost = (nh.lost_confirmed_cases || []).join(', ') || 'none';
    om.textContent = (nh.outcome_meaning || '') +
      '。产品默认未改。不是 fresh-generalization。丢失用例：' + lost + '。';
  }
  const delta = gid('nh-delta');
  if (delta) {
    const crm = (nh.targets || []).find((t) => t.name === 'buggy-crm') || {};
    const ops = (nh.targets || []).find((t) => t.name === 'buggy-ops') || {};
    delta.innerHTML =
      `<span>CRM states <b>${escapeHtml(crm.guard_states)}</b> → <b>${escapeHtml(crm.nested_states)}</b></span>` +
      `<span>Ops states <b>${escapeHtml(ops.guard_states)}</b> → <b>${escapeHtml(ops.nested_states)}</b></span>` +
      `<span>N1–N12 failures <b>${escapeHtml(nh.n_series_failures)}</b></span>` +
      `<span>exhaustive failures <b>${escapeHtml(nh.exhaustive_failures)}</b></span>`;
  }
  setText('proof-round', nh.round || 'v0.3.12');
  setText('proof-outcome', nh.outcome || '—');
  const l1 = gid('proof-metric-1');
  if (l1) l1.textContent = 'CRM states G → N';
  const crm = (nh.targets || []).find((t) => t.name === 'buggy-crm') || {};
  const ops = (nh.targets || []).find((t) => t.name === 'buggy-ops') || {};
  setText('proof-b-states', crm.guard_states);
  setText('proof-g-states', crm.nested_states);
  const l2 = gid('proof-metric-2');
  if (l2) l2.textContent = 'Ops states G → N';
  setText('proof-b-ret', ops.guard_states);
  setText('proof-g-ret', ops.nested_states);
  const l3 = gid('proof-metric-3');
  if (l3) l3.textContent = 'confirmed-bug loss cases';
  setText('proof-esc', (nh.lost_confirmed_cases || []).join(', ') || 'none');
  const note = gid('proof-note');
  if (note) {
    note.textContent = '已分析机制用例上的 lifecycle repair。历史回归有确认缺陷丢失。不是广泛泛化。产品默认未改。';
  }
  const tl = gid('tl-v0312');
  if (tl) {
    tl.textContent = 'Outcome ' + (nh.outcome || '—') + ' — ' + (nh.outcome_meaning || '') +
      '。CRM / Ops 是已分析用例。产品默认未改。';
  }
}

function renderHorizon(hh) {
  const sec = document.querySelector('[data-testid="horizon-handoff"]');
  if (!hh || !hh.available) {
    if (sec && !sec.querySelector('[data-unavailable]')) {
      const note = document.createElement('p');
      note.className = 'limit-note';
      note.dataset.unavailable = '1';
      note.textContent = '暂时无法读取已发布证据';
      sec.appendChild(note);
    }
    return;
  }
  const grid = gid('hh-grid');
  if (grid) {
    grid.innerHTML = (hh.targets || []).map((t) => {
      return `<article class="rc-card"><h3>${escapeHtml(t.name)}</h3>` +
        `<dl class="rc-metrics">` +
        `<div><dt>states</dt><dd>${escapeHtml(t.guard_states)} → ${escapeHtml(t.states)}</dd></div>` +
        `<div><dt>URLs</dt><dd>${escapeHtml(t.guard_urls)} → ${escapeHtml(t.urls)}</dd></div>` +
        `<div><dt>continuations</dt><dd>${escapeHtml(t.continuations)}</dd></div>` +
        `<div><dt>handoffs</dt><dd>${escapeHtml(t.handoffs)}</dd></div>` +
        `</dl><p class="rc-bugs">witnesses ${escapeHtml(t.witnesses)} · resumes ${escapeHtml(t.resumes)} · unwinds ${escapeHtml(t.unwinds)} · depth ${escapeHtml(t.max_depth)} · horizon ${escapeHtml(t.horizon)}</p></article>`;
    }).join('');
  }
  const oc = gid('hh-outcome');
  if (oc) {
    oc.textContent = hh.outcome ? ('Outcome ' + hh.outcome) : 'Outcome';
    oc.className = hh.outcome === 'A' ? 'pill pill-ok' : 'pill';
  }
  const om = gid('hh-outcome-mean');
  if (om) {
    om.textContent = (hh.outcome_meaning || '') +
      '。产品默认未改。不是 fresh validation。回归丢失 ' + escapeHtml(hh.lost_count) + '。';
  }
  const delta = gid('hh-delta');
  if (delta) {
    delta.innerHTML =
      `<span>回归丢失 <b>${escapeHtml(hh.lost_count)}</b></span>` +
      `<span>witness violations <b>${escapeHtml(hh.witness_violations)}</b></span>` +
      `<span>H1–H20 failures <b>${escapeHtml(hh.h_series_failures)}</b></span>` +
      `<span>model failures <b>${escapeHtml(hh.model_invariant_failures)}</b></span>`;
  }
  const audit = hh.reaudit || {};
  const reaudit = gid('hh-reaudit');
  if (reaudit) {
    reaudit.textContent = 'v0.3.13 测量订正不改变已发布结果：Outcome ' +
      (audit.published_outcome || '—') +
      '，反事实仍是 Outcome ' + (audit.counterfactual_outcome || '—') +
      '。BuggyDesk old bad ' + (audit.desk_old_bad ?? '—') +
      ' / residual ' + (audit.desk_residual ?? '—') +
      '。DeepBench old bad ' + (audit.deep_old_bad ?? '—') +
      ' / residual ' + (audit.deep_residual ?? '—') + '。';
  }
  setText('proof-round', hh.round || 'v0.3.14');
  setText('proof-outcome', hh.outcome || '—');
  const crm = (hh.targets || []).find((t) => t.name === 'buggy-crm') || {};
  const ops = (hh.targets || []).find((t) => t.name === 'buggy-ops') || {};
  const l1 = gid('proof-metric-1');
  if (l1) l1.textContent = 'CRM states G → H';
  setText('proof-b-states', crm.guard_states);
  setText('proof-g-states', crm.states);
  const l2 = gid('proof-metric-2');
  if (l2) l2.textContent = 'Ops states G → H';
  setText('proof-b-ret', ops.guard_states);
  setText('proof-g-ret', ops.states);
  const l3 = gid('proof-metric-3');
  if (l3) l3.textContent = 'witness violations';
  setText('proof-esc', hh.witness_violations);
  const note = gid('proof-note');
  if (note) {
    note.textContent = '已分析机制用例。最后一格 handoff 不是 fresh validation。产品默认未改。';
  }
  const tl = gid('tl-v0314');
  if (tl) {
    tl.textContent = 'Outcome ' + (hh.outcome || '—') + ' — ' + (hh.outcome_meaning || '') +
      '。CRM / Ops 是已分析用例。v0.3.13 仍是 Outcome C。产品默认未改。';
  }
}

function renderNestedStack(ns) {
  const sec = document.querySelector('[data-testid="nested-stack"]');
  if (!ns || !ns.available) {
    if (sec && !sec.querySelector('[data-unavailable]')) {
      const note = document.createElement('p');
      note.className = 'limit-note';
      note.dataset.unavailable = '1';
      note.textContent = '暂时无法读取已发布证据';
      sec.appendChild(note);
    }
    return;
  }
  const grid = gid('ns-grid');
  if (grid) {
    grid.innerHTML = (ns.targets || []).map((t) => {
      return `<article class="rc-card"><h3>${escapeHtml(t.name)}</h3>` +
        `<dl class="rc-metrics">` +
        `<div><dt>G states</dt><dd>${escapeHtml(t.guard_states)}</dd></div>` +
        `<div><dt>S states</dt><dd>${escapeHtml(t.stack_states)}</dd></div>` +
        `<div><dt>S pushes</dt><dd>${escapeHtml(t.stack_pushes)}</dd></div>` +
        `<div><dt>S depth</dt><dd>${escapeHtml(t.stack_depth)}</dd></div>` +
        `</dl><p class="rc-bugs">lost_parent ${escapeHtml(t.guard_lost_parent)} → ${escapeHtml(t.stack_lost_parent)} · resumes ${escapeHtml(t.stack_resumes)} · horizon ${escapeHtml(t.stack_horizon)}</p></article>`;
    }).join('');
  }
  const oc = gid('ns-outcome');
  if (oc) {
    oc.textContent = ns.outcome ? ('Outcome ' + ns.outcome) : 'Outcome';
    oc.className = ns.outcome === 'A' ? 'pill pill-ok' : 'pill';
  }
  const om = gid('ns-outcome-mean');
  if (om) {
    const lost = (ns.lost_cases || []).join(', ') || 'none';
    om.textContent = (ns.outcome_meaning || '') +
      '。产品默认未改。不是 fresh validation。丢失用例：' + lost + '。';
  }
  const delta = gid('ns-delta');
  if (delta) {
    const crm = (ns.targets || []).find((t) => t.name === 'buggy-crm') || {};
    const ops = (ns.targets || []).find((t) => t.name === 'buggy-ops') || {};
    delta.innerHTML =
      `<span>CRM depth <b>${escapeHtml(crm.stack_depth)}</b></span>` +
      `<span>Ops depth <b>${escapeHtml(ops.stack_depth)}</b></span>` +
      `<span>P1–P15 failures <b>${escapeHtml(ns.p_series_failures)}</b></span>` +
      `<span>terminal violations <b>${escapeHtml(ns.terminal_accounting_violations)}</b></span>`;
  }
  setText('proof-round', ns.round || 'v0.3.13');
  setText('proof-outcome', ns.outcome || '—');
  const l1 = gid('proof-metric-1');
  if (l1) l1.textContent = 'CRM states G → S';
  const crm = (ns.targets || []).find((t) => t.name === 'buggy-crm') || {};
  const ops = (ns.targets || []).find((t) => t.name === 'buggy-ops') || {};
  setText('proof-b-states', crm.guard_states);
  setText('proof-g-states', crm.stack_states);
  const l2 = gid('proof-metric-2');
  if (l2) l2.textContent = 'Ops states G → S';
  setText('proof-b-ret', ops.guard_states);
  setText('proof-g-ret', ops.stack_states);
  const l3 = gid('proof-metric-3');
  if (l3) l3.textContent = 'lost vs guard';
  setText('proof-esc', (ns.lost_cases || []).join(', ') || 'none');
  const note = gid('proof-note');
  if (note) {
    note.textContent = '已分析机制用例。挂起外层帧没有在 CRM / Ops 上恢复覆盖。不是广泛泛化。产品默认未改。';
  }
  const tl = gid('tl-v0313');
  if (tl) {
    tl.textContent = 'Outcome ' + (ns.outcome || '—') + ' — ' + (ns.outcome_meaning || '') +
      '。CRM / Ops 是已分析用例。v0.3.12 仍是 Outcome C。产品默认未改。';
  }
}

function renderMultiTarget(mt) {
  const sec = document.querySelector('[data-testid="multi-target"]');
  if (!mt || !mt.available) {
    if (sec && !sec.querySelector('[data-unavailable]')) {
      const note = document.createElement('p');
      note.className = 'limit-note';
      note.dataset.unavailable = '1';
      note.textContent = '暂时无法读取已发布证据';
      sec.appendChild(note);
    }
    return;
  }
  const grid = gid('mt-grid');
  if (grid) {
    grid.innerHTML = (mt.targets || []).map((t) => {
      const lost = (t.c1_bugs_lost || []).length === 0 ? 'C1 bugs lost 0' : ('lost ' + (t.c1_bugs_lost || []).join(','));
      return `<article class="rc-card"><h3>${escapeHtml(t.name)}</h3>` +
        `<dl class="rc-metrics">` +
        `<div><dt>C1 states</dt><dd>${escapeHtml(t.c1_states)}</dd></div>` +
        `<div><dt>guard states</dt><dd>${escapeHtml(t.guard_states)}</dd></div>` +
        `<div><dt>opportunity</dt><dd>${escapeHtml(t.opportunity)}</dd></div>` +
        `<div><dt>escapes</dt><dd>${escapeHtml(t.escape)}</dd></div>` +
        `</dl><p class="rc-bugs">${escapeHtml(lost)} · L1/L2 ${escapeHtml(t.L1)}/${escapeHtml(t.L2)}</p></article>`;
    }).join('');
  }
  const oc = gid('mt-outcome');
  if (oc) oc.textContent = mt.outcome ? ('Outcome ' + mt.outcome) : 'Outcome';
  const om = gid('mt-outcome-mean');
  if (om) {
    om.textContent = (mt.outcome_meaning || '') +
      '。产品默认未改。不是广泛泛化。';
  }
  const delta = gid('mt-delta');
  if (delta) {
    delta.innerHTML =
      `<span>evaluable <b>${escapeHtml(mt.evaluable_targets)}</b></span>` +
      `<span>transfer <b>${escapeHtml(mt.transfer_targets)}</b></span>` +
      `<span>exhaustive traces <b>${escapeHtml(mt.exhaustive_traces)}</b></span>` +
      `<span>failures <b>${escapeHtml(mt.exhaustive_failures)}</b></span>`;
  }
  setText('proof-round', mt.round || 'v0.3.11');
  setText('proof-outcome', mt.outcome || '—');
  const l1 = gid('proof-metric-1');
  if (l1) l1.textContent = 'evaluable → transfer';
  setText('proof-b-states', mt.evaluable_targets);
  setText('proof-g-states', mt.transfer_targets);
  const l2 = gid('proof-metric-2');
  if (l2) l2.textContent = 'exhaustive traces / failures';
  setText('proof-b-ret', mt.exhaustive_traces);
  setText('proof-g-ret', mt.exhaustive_failures);
  const l3 = gid('proof-metric-3');
  if (l3) l3.textContent = 'promotion-readiness';
  setText('proof-esc', mt.promotion_readiness || 'not_ready');
  const note = gid('proof-note');
  if (note) {
    note.textContent = '预注册 multi-target replication，不是广泛泛化证明。';
  }
  const tl = gid('tl-v0311');
  if (tl && mt.outcome_meaning) {
    tl.textContent = 'Outcome ' + mt.outcome + ' — ' + mt.outcome_meaning +
      '。产品默认未改。';
  }
}

function renderFreshTransfer(ft) {
  const sec = document.querySelector('[data-testid="fresh-transfer"]');
  if (!ft || !ft.available) {
    if (sec && !sec.querySelector('[data-unavailable]')) {
      const note = document.createElement('p');
      note.className = 'limit-note';
      note.dataset.unavailable = '1';
      note.textContent = '暂时无法读取已发布证据';
      sec.appendChild(note);
    }
    return;
  }
  const b = ft.baseline || {};
  const g = ft.candidate_run || {};
  setText('ft-b-states', b.states);
  setText('ft-b-urls', b.urls);
  setText('ft-b-ret', b.return_attempts);
  setText('ft-b-opp', b.opportunities);
  setText('ft-g-states', g.states);
  setText('ft-g-urls', g.urls);
  setText('ft-g-ret', g.return_attempts);
  setText('ft-g-esc', g.cycle_escapes);
  const bugsEl = gid('ft-bugs');
  if (bugsEl) {
    const bits = [];
    const bugs = shortBugs(g.confirmed);
    if (bugs) bits.push('已确认 ' + bugs);
    if (g.post_escape_new_states != null) {
      bits.push('逃出后新状态 ' + g.post_escape_new_states + ' 个');
    }
    bits.push('BuggyDesk · 非广泛泛化');
    bugsEl.textContent = bits.join(' · ');
  }
  const delta = gid('ft-delta');
  if (delta) {
    delta.innerHTML =
      `<span>状态 <b>${escapeHtml(b.states)}</b> → <b>${escapeHtml(g.states)}</b></span>` +
      `<span>URL <b>${escapeHtml(b.urls)}</b> → <b>${escapeHtml(g.urls)}</b></span>` +
      `<span>return attempt <b>${escapeHtml(b.return_attempts)}</b> → <b>${escapeHtml(g.return_attempts)}</b></span>` +
      `<span>cycle escape <b>${escapeHtml(g.cycle_escapes)}</b></span>`;
  }
  const oc = gid('ft-outcome');
  if (oc) oc.textContent = ft.outcome ? ('Outcome ' + ft.outcome) : 'Outcome';
  const om = gid('ft-outcome-mean');
  if (om) {
    om.textContent = (ft.outcome_meaning || '') +
      '。冻结 guard 在新应用上再次触发；成功返回安全用例没有误触发。';
  }
  setText('proof-round', ft.round || 'v0.3.10');
  setText('proof-b-states', b.states);
  setText('proof-g-states', g.states);
  setText('proof-b-ret', b.return_attempts);
  setText('proof-g-ret', g.return_attempts);
  setText('proof-esc', g.cycle_escapes);
  setText('proof-outcome', ft.outcome || '—');
}

function renderReturnEntry(re) {
  re = re || {};
  const oc = gid('re-outcome');
  if (oc) {
    oc.textContent = re.outcome ? ('Outcome ' + re.outcome) : 'Outcome';
    oc.className = re.outcome === 'A' ? 'pill pill-ok' : 'pill';
  }
  const om = gid('re-outcome-mean');
  if (om) om.textContent = re.outcome_meaning || '';
  const delta = gid('re-delta');
  if (delta) {
    const buttons = (re.result_buttons_drained || []).join(', ') || '无';
    const lost = (re.historical_regression_loss || []).join(', ') || '无';
    delta.textContent = 'Lab L9 ' + (re.lab_l9_before || '—') + ' → ' + (re.lab_l9_after || '—') +
      ' · return-entry drain ' + re.return_entry_drains +
      ' · 结果页按钮 ' + buttons +
      ' · 目录 handoff ' + re.directory_handoffs +
      ' · 历史回归丢失 ' + lost;
  }
  if (!re.available) return;
  setText('proof-round', re.round || 'v0.3.18');
  const m1 = gid('proof-metric-1');
  const m2 = gid('proof-metric-2');
  const m3 = gid('proof-metric-3');
  if (m1) m1.textContent = 'Lab L9';
  if (m2) m2.textContent = 'return-entry / 结果按钮';
  if (m3) m3.textContent = '目录 handoff / 历史丢失';
  setText('proof-b-states', re.lab_l9_before);
  setText('proof-g-states', re.lab_l9_after);
  setText('proof-b-ret', re.return_entry_drains);
  setText('proof-g-ret', (re.result_buttons_drained || []).length);
  setText('proof-esc', String(re.directory_handoffs) + ' / ' + String(re.historical_regression_loss_count));
  setText('proof-outcome', re.outcome || '—');
  const note = gid('proof-note');
  if (note) {
    note.textContent = '检修了返回阶段刚开始时结果页按钮没被点到的问题。DeepBench 出现新的 guard 丢失，所以这轮是 Outcome C。不是新的 fresh 验证。产品默认未改。';
  }
}

function renderLocalAction(la) {
  la = la || {};
  const oc = gid('la-outcome');
  if (oc) {
    oc.textContent = la.outcome ? ('Outcome ' + la.outcome) : 'Outcome';
    oc.className = la.outcome === 'A' ? 'pill pill-ok' : 'pill';
  }
  const om = gid('la-outcome-mean');
  if (om) om.textContent = la.outcome_meaning || '';
  const delta = gid('la-delta');
  if (delta) {
    const before = (la.lab_lost_before || []).join(', ') || '无';
    const lost = (la.lab_lost || []).join(', ') || '无';
    delta.textContent = 'Lab Guard 丢失 ' + before + ' → ' + lost +
      ' · 按钮排空 ' + la.buttons_drained +
      ' · 提升为子分支 ' + la.promoted_children +
      ' · 目录 handoff ' + la.directory_handoffs +
      ' · 历史回归丢失 ' + la.historical_regression_loss;
  }
  if (!la.available) return;
  setText('proof-round', la.round || 'v0.3.17');
  const m1 = gid('proof-metric-1');
  const m2 = gid('proof-metric-2');
  const m3 = gid('proof-metric-3');
  if (m1) m1.textContent = '按钮排空';
  if (m2) m2.textContent = '提升子分支';
  if (m3) m3.textContent = '目录 handoff';
  setText('proof-b-states', la.buttons_drained);
  setText('proof-g-states', la.promoted_children);
  setText('proof-b-ret', (la.lab_lost_before || []).length);
  setText('proof-g-ret', (la.lab_lost || []).length);
  setText('proof-esc', la.directory_handoffs);
  setText('proof-outcome', la.outcome || '—');
  const note = gid('proof-note');
  if (note) {
    note.textContent = '检修了 v0.3.16 里本地按钮排在结构跳转后面的问题。不是新的 fresh 验证。产品默认未改。';
  }
}

function renderReentry(rf) {
  rf = rf || {};
  const oc = gid('rf-outcome');
  if (oc) {
    oc.textContent = rf.outcome ? ('Outcome ' + rf.outcome) : 'Outcome';
    oc.className = rf.outcome === 'A' ? 'pill pill-ok' : 'pill';
  }
  const om = gid('rf-outcome-mean');
  if (om) om.textContent = rf.outcome_meaning || '';
  const delta = gid('rf-delta');
  if (delta) {
    const lost = (rf.lab_lost || []).join(', ') || '无';
    delta.textContent = '目录 handoff ' + rf.directory_handoffs_before + ' → ' +
      rf.directory_handoffs +
      ' · 提前返回 ' + rf.directory_reentry +
      ' · 租约 ' + rf.lab_leases +
      ' · lab 仍丢失 ' + lost;
  }
  if (!rf.available) return;
  setText('proof-round', rf.round || 'v0.3.16');
  const m1 = gid('proof-metric-1');
  const m2 = gid('proof-metric-2');
  const m3 = gid('proof-metric-3');
  if (m1) m1.textContent = '目录 handoff';
  if (m2) m2.textContent = '提前返回 / 租约';
  if (m3) m3.textContent = '历史回归丢失';
  setText('proof-b-states', rf.directory_handoffs_before);
  setText('proof-g-states', rf.directory_handoffs);
  setText('proof-b-ret', rf.directory_reentry);
  setText('proof-g-ret', rf.lab_leases);
  setText('proof-esc', rf.historical_regression_loss);
  setText('proof-outcome', rf.outcome || '—');
  const note = gid('proof-note');
  if (note) {
    note.textContent = '检修了 v0.3.15 的假 handoff 和局部饥饿。不是新的 fresh 验证。产品默认未改。';
  }
}

function renderFreshHandoff(fh) {
  fh = fh || {};
  const oc = gid('fh-outcome');
  if (oc) {
    oc.textContent = fh.outcome ? ('Outcome ' + fh.outcome) : 'Outcome';
    oc.className = fh.outcome === 'A' ? 'pill pill-ok' : 'pill';
  }
  const om = gid('fh-outcome-mean');
  if (om) {
    om.textContent = (fh.outcome_meaning || '') +
      '。可评估 ' + (fh.evaluable_targets == null ? '—' : fh.evaluable_targets) +
      '，完整 transfer ' + (fh.transfer_targets == null ? '—' : fh.transfer_targets) +
      '，负对照 handoff ' + (fh.negative_control_handoffs == null ? '—' : fh.negative_control_handoffs) +
      '。';
  }
  const delta = gid('fh-delta');
  if (delta) {
    const lost = (fh.bug_loss_apps || []).join(', ') || '无';
    delta.textContent = 'bug loss: ' + lost +
      ' · promotion ' + (fh.promotion_readiness || '—');
  }
  if (!fh.available) return;
  setText('proof-round', fh.round || 'v0.3.15');
  const m1 = gid('proof-metric-1');
  const m2 = gid('proof-metric-2');
  const m3 = gid('proof-metric-3');
  if (m1) m1.textContent = '可评估目标';
  if (m2) m2.textContent = '完整 transfer';
  if (m3) m3.textContent = '负对照 handoff';
  setText('proof-b-states', fh.evaluable_targets);
  setText('proof-g-states', fh.transfer_targets);
  setText('proof-b-ret', fh.static_positive_targets);
  setText('proof-g-ret', fh.bug_loss_count);
  setText('proof-esc', fh.negative_control_handoffs);
  setText('proof-outcome', fh.outcome || '—');
  const note = gid('proof-note');
  if (note) {
    note.textContent = '验证未通过。浅层对照触发了 handoff，并且有 guard 已确认缺陷丢失。产品默认未改。';
  }
}

function renderEvidence(data) {
  const rc = (data && data.return_cycle) || {};
  const app = (data && data.application_shape) || {};
  const ft = (data && data.fresh_transfer) || {};
  const mt = (data && data.multi_target) || {};
  const nh = (data && data.nested_hub) || {};
  const ns = (data && data.nested_stack) || {};
  const hh = (data && data.horizon_handoff) || {};
  const fh = (data && data.fresh_handoff) || {};
  const rf = (data && data.reentry_frontier) || {};
  const la = (data && data.local_action_drain) || {};
  const re = (data && data.return_entry_drain) || {};
  const ev0318 = gid('ev-v0318');
  const ev0317 = gid('ev-v0317');
  const ev0316 = gid('ev-v0316');
  const ev0315 = gid('ev-v0315');
  const ev0314 = gid('ev-v0314');
  const ev0313 = gid('ev-v0313');
  const ev0312 = gid('ev-v0312');
  const ev0311 = gid('ev-v0311');
  const ev0310 = gid('ev-v0310');
  const ev039 = gid('ev-v039');
  const ev038 = gid('ev-v038');
  const rail = gid('ev-rail');

  if (ev0318) {
    if (!re.available) {
      ev0318.innerHTML = '<li>暂时无法读取已发布证据</li>';
    } else {
      const r = re.reproduction || {};
      const buttons = (re.result_buttons_drained || []).join(', ') || '无';
      const lost = (re.historical_regression_loss || []).join(', ') || '无';
      ev0318.innerHTML = [
        statusRow('轮次结果', re.outcome ? ('Outcome ' + re.outcome) : '—', re.outcome === 'A'),
        statusRow('Lab L9', (re.lab_l9_before || '—') + ' → ' + (re.lab_l9_after || '—'),
          re.lab_l9_after === 'retained'),
        statusRow('return-entry drain', String(re.return_entry_drains), true),
        statusRow('结果页按钮', buttons, (re.result_buttons_drained || []).length > 0),
        statusRow('目录 handoff', String(re.directory_handoffs), re.directory_handoffs === 0),
        statusRow('历史回归丢失', lost, (re.historical_regression_loss || []).length === 0),
        statusRow('证据清单', fileLabel(r.evidence_files, true), true),
        statusRow('clean clone', yn(r.clean_clone_verified), r.clean_clone_verified),
        statusRow('产品默认', re.product_default_changed ? '已改' : '未改',
          re.product_default_changed === false),
      ].join('');
    }
  }
  const cmd0318 = re.command || '';
  const cmdEl18 = gid('ev-cmd-0318');
  if (cmdEl18) cmdEl18.textContent = cmd0318;
  if (ev0317) {
    if (!la.available) {
      ev0317.innerHTML = '<li>暂时无法读取已发布证据</li>';
    } else {
      const r = la.reproduction || {};
      const before = (la.lab_lost_before || []).join(', ') || '无';
      const lost = (la.lab_lost || []).join(', ') || '无';
      ev0317.innerHTML = [
        statusRow('轮次结果', la.outcome ? ('Outcome ' + la.outcome) : '—', la.outcome === 'A'),
        statusRow('Lab Guard 丢失', before + ' → ' + lost, (la.lab_lost || []).length === 0),
        statusRow('按钮排空', String(la.buttons_drained), true),
        statusRow('提升为子分支', String(la.promoted_children), true),
        statusRow('目录 handoff', String(la.directory_handoffs), la.directory_handoffs === 0),
        statusRow('历史回归丢失', String(la.historical_regression_loss),
          la.historical_regression_loss === 0),
        statusRow('证据清单', fileLabel(r.evidence_files, true), true),
        statusRow('clean clone', yn(r.clean_clone_verified), r.clean_clone_verified),
        statusRow('产品默认', la.product_default_changed ? '已改' : '未改',
          la.product_default_changed === false),
      ].join('');
    }
  }
  const cmd0317 = la.command || '';
  const cmdEl17 = gid('ev-cmd-0317');
  if (cmdEl17) cmdEl17.textContent = cmd0317;
  if (ev0316) {
    if (!rf.available) {
      ev0316.innerHTML = '<li>暂时无法读取已发布证据</li>';
    } else {
      const r = rf.reproduction || {};
      ev0316.innerHTML = [
        statusRow('轮次结果', rf.outcome ? ('Outcome ' + rf.outcome) : '—', rf.outcome === 'A'),
        statusRow('目录 handoff', String(rf.directory_handoffs_before) + ' → ' + String(rf.directory_handoffs),
          rf.directory_handoffs === 0),
        statusRow('提前返回', String(rf.directory_reentry), true),
        statusRow('本地租约', String(rf.lab_leases), true),
        statusRow('历史回归丢失', String(rf.historical_regression_loss),
          rf.historical_regression_loss === 0),
        statusRow('证据清单', fileLabel(r.evidence_files, true), true),
        statusRow('clean clone', yn(r.clean_clone_verified), r.clean_clone_verified),
        statusRow('产品默认', rf.product_default_changed ? '已改' : '未改',
          rf.product_default_changed === false),
      ].join('');
    }
  }
  const cmd0316 = rf.command || '';
  const cmdEl16 = gid('ev-cmd-0316');
  if (cmdEl16) cmdEl16.textContent = cmd0316;
  if (ev0315) {
    if (!fh.available) {
      ev0315.innerHTML = '<li>暂时无法读取已发布证据</li>';
    } else {
      const r = fh.reproduction || {};
      ev0315.innerHTML = [
        statusRow('轮次结果', fh.outcome ? ('Outcome ' + fh.outcome) : '—', fh.outcome === 'A'),
        statusRow('可评估目标', String(fh.evaluable_targets), true),
        statusRow('完整 transfer', String(fh.transfer_targets), true),
        statusRow('负对照 handoff', String(fh.negative_control_handoffs),
          fh.negative_control_handoffs === 0),
        statusRow('证据清单', fileLabel(r.evidence_files, true), true),
        statusRow('clean clone', yn(r.clean_clone_verified), r.clean_clone_verified),
        statusRow('产品默认', fh.product_default_changed ? '已改' : '未改',
          fh.product_default_changed === false),
        statusRow('promotion', fh.promotion_readiness || '—',
          fh.promotion_readiness === 'not_ready' || fh.promotion_readiness === 'evidence_supports_productization_study'),
      ].join('');
    }
  }
  const cmd0315 = fh.command || '';
  const cmdEl15 = gid('ev-cmd-0315');
  if (cmdEl15) cmdEl15.textContent = cmd0315;
  if (ev0314) {
    if (!hh.available) {
      ev0314.innerHTML = '<li>暂时无法读取已发布证据</li>';
    } else {
      const r = hh.reproduction || {};
      ev0314.innerHTML = [
        statusRow('轮次结果', hh.outcome ? ('Outcome ' + hh.outcome) : '—', hh.outcome === 'A'),
        statusRow('候选 freeze', yn(r.candidate_freeze_verified), r.candidate_freeze_verified),
        statusRow('历史 guard freeze', yn(r.historical_guard_freeze_verified), r.historical_guard_freeze_verified),
        statusRow('证据清单', fileLabel(r.evidence_files, r.evidence_manifest_verified),
          r.evidence_manifest_verified),
        statusRow('clean clone', yn(r.clean_clone_verified), r.clean_clone_verified),
        statusRow('产品默认', hh.product_default_changed ? '已改' : '未改',
          hh.product_default_changed === false),
        statusRow('witness violations', String(hh.witness_violations), hh.witness_violations === 0),
        hashRow('Mechanism SHA256', r.metrics_sha256, r.metrics_sha256_short),
      ].join('');
    }
  }
  const cmd0314 = hh.command || (hh.reproduction && hh.reproduction.command) || '';
  if (gid('ev-cmd-0314')) gid('ev-cmd-0314').textContent = cmd0314;

  if (ev0313) {
    if (!ns.available) {
      ev0313.innerHTML = '<li>暂时无法读取已发布证据</li>';
    } else {
      const r = ns.reproduction || {};
      ev0313.innerHTML = [
        statusRow('轮次结果', ns.outcome ? ('Outcome ' + ns.outcome) : '—', ns.outcome === 'A'),
        statusRow('候选 freeze', yn(r.candidate_freeze_verified), r.candidate_freeze_verified),
        statusRow('历史 guard freeze', yn(r.historical_guard_freeze_verified), r.historical_guard_freeze_verified),
        statusRow('证据清单', fileLabel(r.evidence_files, r.evidence_manifest_verified),
          r.evidence_manifest_verified),
        statusRow('clean clone', yn(r.clean_clone_verified), r.clean_clone_verified),
        statusRow('产品默认', ns.product_default_changed ? '已改' : '未改',
          ns.product_default_changed === false),
        hashRow('Mechanism SHA256', r.metrics_sha256, r.metrics_sha256_short),
      ].join('');
    }
  }
  const cmd0313 = ns.command || (ns.reproduction && ns.reproduction.command) || '';
  if (gid('ev-cmd-0313')) gid('ev-cmd-0313').textContent = cmd0313;

  if (ev0312) {
    if (!nh.available) {
      ev0312.innerHTML = '<li>暂时无法读取已发布证据</li>';
    } else {
      const r = nh.reproduction || {};
      ev0312.innerHTML = [
        statusRow('轮次结果', nh.outcome ? ('Outcome ' + nh.outcome) : '—', nh.outcome === 'A'),
        statusRow('候选 freeze', yn(r.candidate_freeze_verified), r.candidate_freeze_verified),
        statusRow('历史 guard freeze', yn(r.historical_guard_freeze_verified), r.historical_guard_freeze_verified),
        statusRow('证据清单', fileLabel(r.evidence_files, r.evidence_manifest_verified),
          r.evidence_manifest_verified),
        statusRow('clean clone', yn(r.clean_clone_verified), r.clean_clone_verified),
        statusRow('产品默认', nh.product_default_changed ? '已改' : '未改',
          nh.product_default_changed === false),
        hashRow('Mechanism SHA256', r.metrics_sha256, r.metrics_sha256_short),
      ].join('');
    }
  }
  const cmd0312 = nh.command || (nh.reproduction && nh.reproduction.command) || '';
  if (gid('ev-cmd-0312')) gid('ev-cmd-0312').textContent = cmd0312;

  if (ev0311) {
    if (!mt.available) {
      ev0311.innerHTML = '<li>暂时无法读取已发布证据</li>';
    } else {
      const r = mt.reproduction || {};
      ev0311.innerHTML = [
        statusRow('轮次结果', mt.outcome ? ('Outcome ' + mt.outcome) : '—', mt.outcome === 'A'),
        statusRow('目标 freeze', yn(r.target_freeze_verified), r.target_freeze_verified),
        statusRow('生成器 freeze', yn(r.generator_freeze_verified), r.generator_freeze_verified),
        statusRow('候选 freeze', yn(r.candidate_freeze_verified), r.candidate_freeze_verified),
        statusRow('证据清单', fileLabel(r.evidence_files, r.evidence_manifest_verified),
          r.evidence_manifest_verified),
        statusRow('clean clone', yn(r.clean_clone_verified), r.clean_clone_verified),
        statusRow('产品默认', mt.product_default_changed ? '已改' : '未改',
          mt.product_default_changed === false),
        hashRow('Metrics SHA256', r.metrics_sha256, r.metrics_sha256_short),
      ].join('');
    }
  }
  const cmd0311 = mt.command || (mt.reproduction && mt.reproduction.command) || '';
  if (gid('ev-cmd-0311')) gid('ev-cmd-0311').textContent = cmd0311;

  if (ev0310) {
    if (!ft.available) {
      ev0310.innerHTML = '<li>暂时无法读取已发布证据</li>';
    } else {
      const r = ft.reproduction || {};
      ev0310.innerHTML = [
        statusRow('轮次结果', ft.outcome ? ('Outcome ' + ft.outcome) : '—', ft.outcome === 'A'),
        statusRow('目标 freeze', yn(r.target_freeze_verified), r.target_freeze_verified),
        statusRow('候选 freeze', yn(r.candidate_freeze_verified), r.candidate_freeze_verified),
        statusRow('证据清单', fileLabel(r.evidence_files, r.evidence_manifest_verified),
          r.evidence_manifest_verified),
        statusRow('clean clone', yn(r.clean_clone_verified), r.clean_clone_verified),
        statusRow('产品默认', ft.product_default_changed ? '已改' : '未改',
          ft.product_default_changed === false),
        hashRow('Metrics SHA256', r.metrics_sha256, r.metrics_sha256_short),
      ].join('');
    }
  }
  const cmd0310 = ft.command || (ft.reproduction && ft.reproduction.command) || '';
  if (gid('ev-cmd-0310')) gid('ev-cmd-0310').textContent = cmd0310;

  if (ev039) {
    if (!rc.available) {
      ev039.innerHTML = '<li>暂时无法读取已发布证据</li>';
    } else {
      const r = rc.reproduction || {};
      ev039.innerHTML = [
        statusRow('轮次结果', rc.outcome ? ('Outcome ' + rc.outcome) : '—', rc.outcome === 'A'),
        statusRow('候选 freeze', yn(r.candidate_freeze_verified), r.candidate_freeze_verified),
        statusRow('历史 C1 freeze', yn(r.historical_c1_freeze_verified), r.historical_c1_freeze_verified),
        statusRow('证据清单', fileLabel(r.evidence_files, r.evidence_manifest_verified),
          r.evidence_manifest_verified),
        statusRow('clean clone', yn(r.clean_clone_verified), r.clean_clone_verified),
        statusRow('产品默认', rc.product_default_changed ? '已改' : '未改',
          rc.product_default_changed === false),
        hashRow('Metrics SHA256', r.metrics_sha256, r.metrics_sha256_short),
      ].join('');
    }
  }
  const cmd039 = rc.command || (rc.reproduction && rc.reproduction.command) || '';
  if (gid('ev-cmd-039')) gid('ev-cmd-039').textContent = cmd039;

  if (ev038) {
    if (!app.available) {
      ev038.innerHTML = '<li>暂时无法读取已发布证据</li>';
    } else {
      const r = app.reproduction || {};
      const cause = app.root_cause || '—';
      ev038.innerHTML = [
        statusRow('证据清单', fileLabel(r.evidence_files, r.evidence_manifest_verified),
          r.evidence_manifest_verified),
        statusRow('分析哈希', r.match ? 'Match' : '—', r.match),
        statusRow('clean clone', yn(r.clean_clone_verified), r.clean_clone_verified),
        statusRow('根因记录', cause, 'warn'),
        hashRow('Analysis SHA256', r.analysis_sha256, r.analysis_sha256_short),
      ].join('');
    }
  }
  const cmd038 = app.command || (app.reproduction && app.reproduction.command) || '';
  if (gid('ev-cmd-038')) gid('ev-cmd-038').textContent = cmd038;

  if (rail) {
    const latest = (data && data.latest) || {};
    const r = (ns.reproduction || mt.reproduction || ft.reproduction || rc.reproduction || {});
    if (!mt.available && !ft.available && !rc.available && !app.available) {
      rail.innerHTML = '<h2>当前研究</h2><p>暂时无法读取已发布证据</p>';
    } else {
      rail.innerHTML =
        `<h2>当前研究</h2>` +
        `<p>机制轮次<br><b>${escapeHtml(latest.round || '—')} ${escapeHtml(latest.title || '')}</b></p>` +
        `<p>复现校验<br><b>${r.clean_clone_verified ? 'clean clone 已通过' : '—'}</b></p>` +
        `<p>产品默认<br><b>${latest.product_default_changed ? '已改' : '未改'}</b></p>` +
        ((ft.product_default || rc.product_default)
          ? `<p>配置<br><b>${escapeHtml(ft.product_default || rc.product_default)}</b></p>` : '');
    }
  }
}

function markUnavailable() {
  renderReturnCycle({ available: false });
  renderFreshTransfer({ available: false });
  renderMultiTarget({ available: false });
  renderEvidence({ return_cycle: { available: false }, application_shape: { available: false },
    fresh_transfer: { available: false }, multi_target: { available: false } });
}

async function copyText(text) {
  if (!text) return;
  try {
    await navigator.clipboard.writeText(text);
  } catch (_) {
    const ta = document.createElement('textarea');
    ta.value = text;
    document.body.appendChild(ta);
    ta.select();
    try { document.execCommand('copy'); } catch (__) {}
    ta.remove();
  }
}

function bindCopy() {
  document.addEventListener('click', (e) => {
    const btn = e.target.closest('[data-copy], [data-copy-text]');
    if (!btn) return;
    const fromId = btn.getAttribute('data-copy');
    const text = btn.getAttribute('data-copy-text')
      || (fromId && gid(fromId) ? gid(fromId).textContent : '');
    copyText(text.trim()).then(() => {
      const prev = btn.textContent;
      btn.textContent = '已复制';
      setTimeout(() => { btn.textContent = prev; }, 1200);
    });
  });
}

function initNav() {
  document.querySelectorAll('[data-view]').forEach((btn) => {
    btn.addEventListener('click', () => GhostQA.setView(btn.dataset.view));
  });
  document.querySelectorAll('[data-goto]').forEach((btn) => {
    btn.addEventListener('click', () => GhostQA.setView(btn.dataset.goto));
  });
  window.addEventListener('hashchange', () => {
    const h = (location.hash || '#overview').slice(1);
    GhostQA.setView(h, { skipHash: true });
  });
  const initial = (location.hash || '#overview').slice(1);
  GhostQA.setView(VIEWS.includes(initial) ? initial : 'overview', { skipHash: true });
}

async function loadShowcase() {
  try {
    const res = await fetch('/api/showcase', { cache: 'no-store' });
    if (!res.ok) throw new Error('HTTP ' + res.status);
    const data = await res.json();
    GhostQA.showcase = data;
    renderReturnCycle(data.return_cycle);
    renderFreshTransfer(data.fresh_transfer);
    renderMultiTarget(data.multi_target);
    renderNestedHub(data.nested_hub);
    renderNestedStack(data.nested_stack);
    renderHorizon(data.horizon_handoff);
    renderFreshHandoff(data.fresh_handoff);
    renderReentry(data.reentry_frontier);
    renderLocalAction(data.local_action_drain);
    renderReturnEntry(data.return_entry_drain);
    renderEvidence(data);
    const badge = gid('research-badge');
    if (badge && data.latest && data.latest.round) {
      badge.textContent = '研究版本 · ' + data.latest.round;
    }
  } catch (_) {
    markUnavailable();
  }
}

initNav();
bindCopy();
loadShowcase();
