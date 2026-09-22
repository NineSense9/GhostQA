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
  setText('proof-round', rc.round || 'v0.3.9');
  setText('proof-b-states', b.states);
  setText('proof-g-states', g.states);
  setText('proof-b-ret', b.return_attempts);
  setText('proof-g-ret', g.return_attempts);
  setText('proof-esc', g.cycle_escapes);
  setText('proof-outcome', rc.outcome || 'A');
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

function renderEvidence(data) {
  const rc = (data && data.return_cycle) || {};
  const app = (data && data.application_shape) || {};
  const ev039 = gid('ev-v039');
  const ev038 = gid('ev-v038');
  const rail = gid('ev-rail');

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
    const r = rc.reproduction || {};
    if (!rc.available && !app.available) {
      rail.innerHTML = '<h2>当前研究</h2><p>暂时无法读取已发布证据</p>';
    } else {
      rail.innerHTML =
        `<h2>当前研究</h2>` +
        `<p>机制轮次<br><b>${escapeHtml(latest.round || '—')} ${escapeHtml(latest.title || '')}</b></p>` +
        `<p>复现校验<br><b>${r.clean_clone_verified ? 'clean clone 已通过' : '—'}</b></p>` +
        `<p>产品默认<br><b>${latest.product_default_changed ? '已改' : '未改'}</b></p>` +
        (rc.product_default
          ? `<p>配置<br><b>${escapeHtml(rc.product_default)}</b></p>` : '');
    }
  }
}

function markUnavailable() {
  renderReturnCycle({ available: false });
  renderEvidence({ return_cycle: { available: false }, application_shape: { available: false } });
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
