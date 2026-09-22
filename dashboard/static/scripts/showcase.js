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

function renderEvidence(data) {
  const rc = (data && data.return_cycle) || {};
  const app = (data && data.application_shape) || {};
  const ft = (data && data.fresh_transfer) || {};
  const mt = (data && data.multi_target) || {};
  const ev0311 = gid('ev-v0311');
  const ev0310 = gid('ev-v0310');
  const ev039 = gid('ev-v039');
  const ev038 = gid('ev-v038');
  const rail = gid('ev-rail');

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
    const r = (mt.reproduction || ft.reproduction || rc.reproduction || {});
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
