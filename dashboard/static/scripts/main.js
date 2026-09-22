/* ============================================================================
   GhostQA Dashboard — live exploration controller
   Polls the run API, streams screenshots, grows the state graph, renders the
   decision log and confirmed-bug evidence. No framework, no build step.
   ========================================================================== */
'use strict';

const API = '';
const POLL_MS = 1200;
const STALE_MS = 45000;

const REDUCE = window.matchMedia
  ? window.matchMedia('(prefers-reduced-motion: reduce)').matches
  : false;

const THEME_KEY = 'ghostqa-theme';
const THEME_COLOR = { light: '#f2efe8', dark: '#1c1d1f' };

const S = {
  runId: null,
  events: [],
  seenSeq: -1,
  status: 'idle',
  lastShot: '',
  activeRow: null,
  bugs: [],
  cy: null,
  pollTimer: null,
  failedOnce: false,
  graphSig: '',
  firstLayout: true,
  startSig: '',
  staleRun: false,
  runStartedAt: 0,
  lastEventAt: 0,
  logPinned: true,
  lastGraph: null,
};

const $ = (id) => document.getElementById(id);
const els = {
  status: $('r-status'), steps: $('r-steps'), states: $('r-states'),
  cands: $('r-cands'), bugs: $('r-bugs'), llm: $('r-llm'),
  conn: $('conn'), connTxt: $('conn-txt'),
  vpPill: $('vp-pill'), shot: $('shot'), vpEmpty: $('viewport-empty'),
  verb: $('a-verb'), target: $('a-target'), url: $('a-url'),
  graphCount: $('graph-count'),
  tActions: $('t-actions'), tNodes: $('t-nodes'), tEdges: $('t-edges'),
  tRelocate: $('t-relocate'), tWall: $('t-wall'), tBugs: $('t-bugs'),
  tUrls: $('t-urls'),
  mixNew: $('mix-new'), mixSimilar: $('mix-similar'), mixIdentical: $('mix-identical'),
  mNew: $('m-new'), mSimilar: $('m-similar'), mIdentical: $('m-identical'),
  bugList: $('bugs'), bugCount: $('bug-count'),
  log: $('log'), logCount: $('log-count'),
  form: $('run-form'), btnRun: $('btn-run'), btnRunTxt: $('btn-run-txt'),
  reportLink: $('report-link'),
  liveBar: document.querySelector('.live-bar'),
  liveComplete: $('live-complete'),
  liveError: $('live-error'),
  liveHint: $('live-hint'),
  liveIntro: $('live-intro'),
  graphEmpty: $('graph-empty'),
  logLatest: $('log-latest'),
  policyHint: $('policy-hint'),
  policyResearch: $('policy-research'),
  viewport: $('viewport'),
};

const STATUS_TEXT = {
  idle: '空闲', running: '探索中', validating: '校验中',
  done: '已完成', error: '出错',
};

const POLICY_HINT = {
  ghost: '产品默认 · NoFrontier，sequence off',
  'ghost-nollm': '不调用模型',
  bfs: '广度优先',
  dfs: '深度优先',
  'workflow-bfs': '按 workflow 阶段推进',
  'ghost-structural-memory': 'Structural hub memory',
  'ghost-structural-return-guard': 'Structural memory + exact-repeat return-cycle escape.',
  'ghost-structural-nested-return-guard': 'Research only. Nested-hub preservation. v0.3.12 Outcome C, not the default.',
  'ghost-structural-nested-stack-guard': 'Research only. Suspended-parent stack. v0.3.13 is not the default.',
  'ghost-structural-horizon-handoff-guard': 'Research only. Horizon handoff. v0.3.14 is not the default.',
};

const RESEARCH_POLICIES = {
  'ghost-structural-memory': true,
  'ghost-structural-return-guard': true,
  'ghost-structural-nested-return-guard': true,
  'ghost-structural-nested-stack-guard': true,
};

/* ------------------------------ theme ----------------------------------- */

function readTheme() {
  return document.documentElement.getAttribute('data-theme') === 'dark' ? 'dark' : 'light';
}

function cssVar(name) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

function syncThemeToggle() {
  const btn = document.getElementById('theme-toggle');
  if (!btn) return;
  const t = readTheme();
  const next = t === 'dark' ? 'light' : 'dark';
  btn.setAttribute('aria-label', next === 'light' ? '切换到浅色主题' : '切换到深色主题');
  btn.setAttribute('title', next === 'light' ? '切换到浅色' : '切换到深色');
  btn.setAttribute('aria-pressed', t === 'dark' ? 'true' : 'false');
  btn.dataset.theme = t;
}

function applyGraphTheme() {
  if (S.cy) {
    S.cy.style().fromJson(graphStyles()).update();
  }
}

function applyTheme(theme, persist) {
  const t = theme === 'dark' ? 'dark' : 'light';
  document.documentElement.setAttribute('data-theme', t);
  document.documentElement.style.colorScheme = t;
  const meta = document.querySelector('meta[name="theme-color"]');
  if (meta) meta.setAttribute('content', THEME_COLOR[t]);
  if (persist) {
    try { localStorage.setItem(THEME_KEY, t); } catch (_) {}
  }
  syncThemeToggle();
  applyGraphTheme();
  document.dispatchEvent(new CustomEvent('ghostqa-themechange', { detail: { theme: t } }));
}

function toggleTheme() {
  applyTheme(readTheme() === 'dark' ? 'light' : 'dark', true);
}

/* ------------------------------ helpers --------------------------------- */

function setConn(live, text) {
  if (!els.conn) return;
  els.conn.classList.toggle('is-live', !!live);
  if (els.connTxt) els.connTxt.textContent = text;
}

function fmtAction(a) {
  if (!a) return ['?', ''];
  const verb = (a.type || 'act').toUpperCase();
  const detail = a.text || a.value || a.target_eid || a.key || '';
  return [verb, String(detail).slice(0, 70)];
}

function shortPath(url) {
  if (!url) return '';
  try {
    const u = new URL(url, 'http://local');
    const p = u.pathname.replace(/\/+$/, '');
    return p.split('/').pop() || p || u.host;
  } catch (_) {
    return String(url).replace(/^https?:\/\/[^/]+/, '');
  }
}

function setPill(el, status) {
  if (!el) return;
  el.className = 'status-pill is-' + status;
  el.textContent = STATUS_TEXT[status] || status;
}

function setRunButton(status, stale) {
  if (!els.btnRun || !els.btnRunTxt) return;
  const active = (status === 'running' || status === 'validating') && !stale;
  els.btnRun.disabled = active;
  if (status === 'running' && !stale) els.btnRunTxt.textContent = '探索中…';
  else if (status === 'validating' && !stale) els.btnRunTxt.textContent = '正在重放验证…';
  else if (status === 'done') els.btnRunTxt.textContent = '再跑一次';
  else if (stale || status === 'error') els.btnRunTxt.textContent = '重新启动';
  else els.btnRunTxt.textContent = '启动探索';
}

function setBarStatus(status) {
  if (els.liveBar) els.liveBar.dataset.status = status || 'idle';
  document.body.classList.toggle('is-running', status === 'running');
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => (
    { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]
  ));
}

function elapsedLabel() {
  if (!S.runStartedAt) return '0s';
  return Math.max(0, Math.round((Date.now() - S.runStartedAt) / 1000)) + 's';
}

/* ---------------------------- viewport ---------------------------------- */

function showShot(url, altText) {
  if (!url || url === S.lastShot) return;
  S.lastShot = url;
  const img = new Image();
  img.onload = () => {
    els.shot.src = url;
    els.shot.hidden = false;
    els.vpEmpty.hidden = true;
    if (els.viewport) els.viewport.classList.add('has-shot');
    els.shot.alt = altText || '探索器当前所见页面截图';
  };
  img.onerror = () => { /* keep last good frame */ };
  img.src = url;
}

function updateActionStrip(ev) {
  const [verb, detail] = fmtAction(ev.action);
  const fullUrl = (ev.dst && ev.dst.url) ? ev.dst.url : '';
  els.verb.textContent = verb;
  els.target.textContent = detail || '（无文本目标）';
  els.target.title = detail || '';
  els.url.textContent = fullUrl.replace(/^https?:\/\//, '');
  els.url.title = fullUrl;
}

/* ------------------------------- log ------------------------------------ */

function tagFor(ev) {
  if (ev.findings && ev.findings.length) return ['BUG', 'tag-bug'];
  if (ev.crashed) return ['CRASH', 'tag-crash'];
  const r = (ev.relation || '').toLowerCase();
  if (r.includes('new')) return ['NEW', 'tag-new'];
  if (r.includes('similar')) return ['SIM', 'tag-similar'];
  if (r.includes('identical')) return ['ID', 'tag-identical'];
  return ['—', 'tag-identical'];
}

function renderLogRow(ev) {
  const [verb, detail] = fmtAction(ev.action);
  const [tag, cls] = tagFor(ev);
  const src = shortPath(ev.src && ev.src.url);
  const dst = shortPath(ev.dst && ev.dst.url);
  const path = (src || dst) ? `${src || '—'} → ${dst || '—'}` : '';
  const mode = ev.decision_mode || '';
  const row = document.createElement('div');
  row.className = 'log-row';
  row.dataset.seq = ev.seq;
  row.tabIndex = 0;
  row.setAttribute('role', 'button');
  row.innerHTML =
    `<span class="log-i">${String(ev.index + 1).padStart(3, '0')}</span>` +
    `<span class="log-txt"><b>${escapeHtml(verb + ' ' + detail)}</b>` +
    (path ? `<span class="log-path">${escapeHtml(path)}</span>` : '') +
    `</span>` +
    `<span class="log-tag ${cls}">${tag}` +
    (mode ? `<span class="log-mode">${escapeHtml(mode)}</span>` : '') +
    `</span>`;
  const activate = () => selectEvent(ev);
  row.addEventListener('click', activate);
  row.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); activate(); }
  });
  return row;
}

function selectEvent(ev) {
  if (S.activeRow) S.activeRow.classList.remove('is-active');
  const row = els.log.querySelector(`.log-row[data-seq="${ev.seq}"]`);
  if (row) { row.classList.add('is-active'); S.activeRow = row; }
  const shot = (ev.dst && ev.dst.screenshot) || (ev.src && ev.src.screenshot) || '';
  showShot(shot, `第 ${ev.index + 1} 步后的页面`);
  updateActionStrip(ev);
}

function appendEvents(list) {
  const steps = list.filter((e) => e.type === 'step');
  if (!steps.length) return;
  if (S.events.length === 0) els.log.innerHTML = '';
  for (const ev of steps) {
    S.events.push(ev);
    els.log.appendChild(renderLogRow(ev));
    if (S.status === 'running' || S.status === 'validating') selectEvent(ev);
  }
  els.logCount.textContent = String(S.events.length);
  if (S.logPinned) els.log.scrollTop = els.log.scrollHeight;
  if (els.logLatest) els.logLatest.hidden = S.logPinned;
  els.steps.textContent = String(S.events.length);
  S.lastEventAt = Date.now();
  els.tActions.textContent = String(S.events.length);
  const bugsSeen = S.events.reduce((n, e) => n + (e.findings || []).length, 0);
  if (bugsSeen) els.cands.textContent = String(bugsSeen);
}

/* ------------------------------- graph ---------------------------------- */

function graphStyles() {
  const c = (name, fallback) => cssVar(name) || fallback;
  const node = c('--graph-node', '#ffffff');
  const label = c('--graph-label', '#161513');
  const edge = c('--graph-edge', '#b7b1a6');
  const neu = c('--graph-new', '#0d6b66');
  const similar = c('--graph-similar', '#3d5a80');
  const identical = c('--graph-identical', '#6f6c64');
  const flagged = c('--graph-flagged', '#9a4e0b');
  const active = c('--graph-active', '#9a4e0b');
  return [
    { selector: 'node', style: {
        'background-color': node,
        'background-opacity': 1,
        'border-width': 2,
        'border-color': neu,
        'width': 26, 'height': 26,
        'label': 'data(label)',
        'font-family': 'IBM Plex Mono, monospace',
        'font-size': 15,
        'font-weight': 500,
        'color': label,
        'text-valign': 'bottom',
        'text-halign': 'center',
        'text-margin-y': 7,
        'text-max-width': '150px',
        'text-wrap': 'ellipsis',
        'text-opacity': 1,
        'shape': 'ellipse',
        'transition-property': 'background-color, border-color, width, height',
        'transition-duration': REDUCE ? 0 : 200,
    }},
    { selector: 'node[rel = "SIMILAR"]',   style: { 'border-color': similar }},
    { selector: 'node[rel = "IDENTICAL"]', style: { 'border-color': identical, 'border-style': 'dashed' }},
    { selector: 'node[?isNew]', style: { 'background-color': neu, 'color': label }},
    { selector: 'node[?flagged]', style: {
        'background-color': flagged, 'border-color': flagged,
        'width': 36, 'height': 36, 'color': flagged,
        'font-size': 17,
        'font-weight': 600,
        'shape': 'diamond',
    }},
    { selector: 'node[?active]', style: {
        'border-width': 3, 'border-color': active,
        'width': 32, 'height': 32,
    }},
    { selector: 'edge', style: {
        'width': 1,
        'line-color': edge,
        'target-arrow-color': edge,
        'target-arrow-shape': 'triangle',
        'arrow-scale': 0.6,
        'curve-style': 'bezier',
        'opacity': 0.85,
    }},
    { selector: 'edge[rel = "NEW"]',       style: { 'line-color': neu, 'target-arrow-color': neu }},
    { selector: 'edge[rel = "SIMILAR"]',   style: { 'line-color': similar, 'target-arrow-color': similar }},
    { selector: 'edge[rel = "IDENTICAL"]', style: { 'line-color': identical, 'target-arrow-color': identical, 'line-style': 'dashed' }},
    { selector: ':selected', style: { 'border-width': 2.5, 'border-color': active }},
  ];
}

function initGraph() {
  if (S.cy) return;
  const box = $('graph');
  if (!box || box.offsetWidth < 8) return;
  S.cy = cytoscape({
    container: box,
    elements: [],
    style: graphStyles(),
    layout: { name: 'preset' },
    wheelSensitivity: 0.22,
    minZoom: 0.25,
    maxZoom: 3,
  });
  S.cy.on('tap', 'node', (e) => {
    const sig = e.target.id();
    const found = [...S.events].reverse().find(
      (ev) => ev.dst && ev.dst.sig === sig && ev.dst.screenshot);
    if (found) {
      showShot(found.dst.screenshot, found.dst.title || sig);
      updateActionStrip(found);
    }
  });
  S.cy.on('dbltap', () => fitGraph());
  window.__cy = S.cy;
}

function fitGraph() {
  if (S.cy) S.cy.fit(undefined, 48);
}

function graphSignature(payload) {
  const nodes = (payload.nodes || []).map((n) => n.sig +
    (n.flags && n.flags.length ? '!' : '')).join(',');
  const edges = (payload.edges || []).map((e) => e.src + '>' + e.dst).join(',');
  return nodes + '|' + edges;
}

function syncGraph(payload) {
  S.lastGraph = payload;
  const nodes = payload.nodes || [];
  const edges = payload.edges || [];
  if (els.graphEmpty) els.graphEmpty.hidden = nodes.length > 0;
  if (!nodes.length) return;
  initGraph();
  if (!S.cy) return;
  const cy = S.cy;
  const known = new Set(cy.nodes().map((n) => n.id()));
  const last = S.events.length ? S.events[S.events.length - 1] : null;
  const activeSig = last && last.dst ? last.dst.sig : '';

  for (const n of nodes) {
    const data = {
      id: n.sig,
      label: shortLabel(n),
      rel: n.relation || 'NEW',
      flagged: Array.isArray(n.flags) && n.flags.length > 0,
      isNew: (n.visits || 0) <= 1,
      active: n.sig === activeSig,
      url: n.url || '',
    };
    const existing = cy.getElementById(n.sig);
    if (existing.nonempty()) existing.data(data);
    else cy.add({ data });
    known.delete(n.sig);
  }
  for (const gone of known) cy.getElementById(gone).remove();

  for (const e of edges) {
    const id = e.src + '>' + (e.action_key || '');
    const data = {
      id, source: e.src, target: e.dst, rel: e.rel || e.relation || 'NEW',
    };
    const existing = cy.getElementById(id);
    if (existing.nonempty()) existing.data(data);
    else if (cy.getElementById(e.src).nonempty() && cy.getElementById(e.dst).nonempty()) {
      cy.add({ data });
    }
  }

  els.graphCount.textContent = `${nodes.length} 节点 / ${edges.length} 边`;
  els.tNodes.textContent = String(nodes.length);
  els.tEdges.textContent = String(edges.length);
  els.states.textContent = String(nodes.length);
  if (els.tUrls) {
    const urls = new Set(nodes.map((n) => n.url).filter(Boolean));
    els.tUrls.textContent = String(urls.size);
  }

  const sig = graphSignature(payload);
  if (sig === S.graphSig) return;
  S.graphSig = sig;
  if (!S.startSig && nodes.length) S.startSig = nodes[0].sig;

  const start = S.startSig;
  const depth = {};
  const adj = {};
  for (const e of edges) {
    (adj[e.src] = adj[e.src] || []).push(e.dst);
  }
  const queue = [];
  if (start && cy.getElementById(start).nonempty()) {
    depth[start] = 0;
    queue.push(start);
  } else if (cy.nodes().length) {
    const first = cy.nodes()[0].id();
    depth[first] = 0;
    queue.push(first);
  }
  while (queue.length) {
    const cur = queue.shift();
    for (const nxt of (adj[cur] || [])) {
      if (depth[nxt] === undefined && cy.getElementById(nxt).nonempty()) {
        depth[nxt] = depth[cur] + 1;
        queue.push(nxt);
      }
    }
  }
  for (const n of cy.nodes()) {
    if (depth[n.id()] === undefined) depth[n.id()] = 0;
  }
  const COL_W = 230, ROW_H = 118;
  const layers = {};
  for (const n of cy.nodes()) {
    const d = depth[n.id()];
    (layers[d] = layers[d] || []).push(n.id());
  }
  const positions = {};
  for (const d of Object.keys(layers).map(Number).sort((a, b) => a - b)) {
    const ids = layers[d];
    const offset = -(ids.length - 1) / 2;
    ids.forEach((id, i) => {
      positions[id] = { x: d * COL_W, y: (offset + i) * ROW_H };
    });
  }
  cy.layout({
    name: 'preset', positions: (n) => positions[n.id()],
    animate: cy.nodes().length > 1 && !S.firstLayout && !REDUCE,
    animationDuration: 380, animationEasing: 'ease-out',
    fit: true, padding: 48,
  }).run();

  const z = cy.zoom();
  if (z > 1.5) cy.zoom(1.5);
  else if (z < 0.78) cy.zoom(0.78);
  cy.center();
  S.firstLayout = false;
}

function shortLabel(n) {
  const t = (n.title || n.url || n.sig || '').replace(/^https?:\/\/[^/]+/, '');
  const s = t.trim() || n.sig.slice(0, 10);
  return s.length > 22 ? s.slice(0, 21) + '…' : s;
}

/* -------------------------------- bugs ---------------------------------- */

function renderBugs(list) {
  S.bugs = list;
  els.bugCount.textContent = String(list.length);
  els.tBugs.textContent = String(list.length);
  els.bugList.innerHTML = '';
  if (!list.length) {
    els.bugList.innerHTML =
      '<p class="empty">还没有确认缺陷。<br>运行结束后，通过复现校验与 ddmin 的问题会出现在这里。</p>';
    return;
  }
  for (const b of list) {
    const f = b.finding || {};
    const card = document.createElement('article');
    card.className = 'bug';
    const steps = (b.reproduction || [])
      .map((a) => `<li>${escapeHtml(fmtAction(a).join(' '))}</li>`).join('');
    const saved = (b.original_length || 0) - (b.reproduction || []).length;
    const n = (b.reproduction || []).length;
    card.innerHTML =
      `<div class="bug-head" role="button" tabindex="0" aria-expanded="false">
         <span class="bug-kind">${escapeHtml(f.kind || 'defect')}</span>
         <span class="bug-status">重放通过 · ${n} 步复现</span>
         <span class="bug-desc">${escapeHtml(f.description || '')}</span>
       </div>
       <div class="bug-body">
         <div class="repro-meta">
           <span>原始 <b>${b.original_length ?? '?'}</b> 步</span>
           <span>最小化 <b>${n}</b> 步</span>
           <span>裁剪 <b>${saved > 0 ? saved : 0}</b> 步</span>
         </div>
         <ol class="repro-steps">${steps || '<li>（空复现序列）</li>'}</ol>
       </div>`;
    const head = card.querySelector('.bug-head');
    const toggle = () => {
      const open = card.classList.toggle('is-open');
      head.setAttribute('aria-expanded', String(open));
    };
    head.addEventListener('click', toggle);
    head.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); toggle(); }
    });
    els.bugList.appendChild(card);
  }
}

/* -------------------------------- mix ----------------------------------- */

function renderMix(counts) {
  const n = counts.NEW ?? counts.new ?? 0;
  const s = counts.SIMILAR ?? counts.similar ?? 0;
  const i = counts.IDENTICAL ?? counts.identical ?? 0;
  const total = n + s + i || 1;
  els.mixNew.style.width = (n / total * 100) + '%';
  els.mixSimilar.style.width = (s / total * 100) + '%';
  els.mixIdentical.style.width = (i / total * 100) + '%';
  els.mNew.textContent = String(n);
  els.mSimilar.textContent = String(s);
  els.mIdentical.textContent = String(i);
}

/* ------------------------------- polling -------------------------------- */

async function getJSON(path) {
  const res = await fetch(API + path, { cache: 'no-store' });
  if (!res.ok) throw new Error(`HTTP ${res.status} ${path}`);
  return res.json();
}

function showComplete(st) {
  if (!els.liveComplete) return;
  const m = st.summary || {};
  const steps = m.actions ?? S.events.length;
  const states = m.states ?? els.states.textContent;
  const bugs = m.confirmed ?? S.bugs.length;
  const report = st.status === 'done' && S.runId;
  els.liveComplete.hidden = false;
  els.liveComplete.textContent =
    `${steps} 步 · ${states} 个状态 · ${bugs} 个已确认缺陷` +
    (report ? ' · 报告已就绪' : '');
}

function showError(message, detail) {
  if (!els.liveError) return;
  els.liveError.hidden = false;
  els.liveError.innerHTML =
    `<p>${escapeHtml(message)}</p>` +
    (detail
      ? `<details><summary>详细错误</summary><pre>${escapeHtml(detail)}</pre></details>`
      : '');
}

async function tick() {
  if (!S.runId) return;
  let st;
  try {
    st = await getJSON(`/api/runs/${S.runId}`);
    S.failedOnce = false;
    setConn(true, '已连接');
  } catch (err) {
    if (!S.failedOnce) { setConn(false, '连接中断'); S.failedOnce = true; }
    return;
  }

  S.status = st.status;
  els.status.textContent = STATUS_TEXT[st.status] || st.status;
  setPill(els.vpPill, st.status);
  setBarStatus(st.status);
  const active = (st.status === 'running' || st.status === 'validating');
  if (active && S.runStartedAt && Date.now() - S.runStartedAt > STALE_MS
      && S.lastEventAt && Date.now() - S.lastEventAt > STALE_MS) {
    S.staleRun = true;
  }
  setRunButton(st.status, S.staleRun);
  if (els.liveHint) els.liveHint.hidden = st.status !== 'idle' && !!S.runId;
  if (els.liveIntro) els.liveIntro.hidden = st.status !== 'idle';
  if (active) els.llm.textContent = '…';
  if (st.candidates && st.candidates.length) {
    els.cands.textContent = String(st.candidates.length);
  }
  if (active) els.tWall.textContent = elapsedLabel();

  try {
    const ev = await getJSON(`/api/runs/${S.runId}/events?after=${S.seenSeq}`);
    if (ev.events && ev.events.length) {
      appendEvents(ev.events);
      S.seenSeq = ev.events[ev.events.length - 1].seq;
    }
  } catch (_) { /* transient */ }

  try { syncGraph(await getJSON(`/api/runs/${S.runId}/graph`)); } catch (_) {}
  try { renderBugs(await getJSON(`/api/runs/${S.runId}/bugs`)); } catch (_) {}

  if (st.summary && Object.keys(st.summary).length) {
    const m = st.summary;
    els.tActions.textContent = String(m.actions ?? 0);
    els.tNodes.textContent = String(m.states ?? 0);
    els.tRelocate.textContent = String(m.relocate_count ?? 0);
    els.tWall.textContent = (m.wall_seconds ?? 0) + 's';
    els.llm.textContent = String(m.llm_calls ?? 0);
    els.bugs.textContent = String(m.confirmed ?? 0);
    els.cands.textContent = String(m.candidates ?? 0);
    if (m.similarity_counts) renderMix(m.similarity_counts);
  }

  if (st.status === 'done') {
    els.reportLink.href = `/api/runs/${S.runId}/report.html`;
    els.reportLink.hidden = false;
    showComplete(st);
    if (els.liveError) els.liveError.hidden = true;
    stopPolling();
    setConn(true, '已完成');
  } else if (st.status === 'error') {
    els.reportLink.hidden = true;
    stopPolling();
    setConn(false, '运行出错');
    const raw = st.error || '';
    const last = raw.split('\n').filter(Boolean).pop() || '未知错误';
    showError(
      '这次运行没有完成。可以重新启动；之前的报告文件不会被删除。',
      raw);
    els.log.insertAdjacentHTML('beforeend',
      `<p class="empty" style="color:var(--danger)">运行出错：${escapeHtml(last)}</p>`);
  }
}

function startPolling() {
  stopPolling();
  tick();
  S.pollTimer = setInterval(tick, POLL_MS);
}

function stopPolling() {
  if (S.pollTimer) { clearInterval(S.pollTimer); S.pollTimer = null; }
}

/* ------------------------------- start ---------------------------------- */

function validateForm() {
  const url = $('f-url').value.trim();
  const budget = parseInt($('f-budget').value, 10);
  let ok = true;
  const errUrl = $('err-url');
  const errBudget = $('err-budget');
  if (errUrl) errUrl.textContent = '';
  if (errBudget) errBudget.textContent = '';
  if (!/^https?:\/\//i.test(url)) {
    if (errUrl) errUrl.textContent = '请输入 http:// 或 https:// 地址';
    ok = false;
  }
  if (!Number.isFinite(budget) || budget < 1 || budget > 400) {
    if (errBudget) errBudget.textContent = '预算需要在 1–400 步之间';
    ok = false;
  }
  return ok;
}

function updatePolicyHint() {
  const name = $('f-policy').value;
  if (els.policyHint) els.policyHint.textContent = POLICY_HINT[name] || '';
  if (els.policyResearch) els.policyResearch.hidden = !RESEARCH_POLICIES[name];
}

if (els.form) {
  els.form.addEventListener('submit', async (e) => {
    e.preventDefault();
    if (!validateForm()) return;
    const payload = {
      url: $('f-url').value.trim(),
      spec: $('f-spec').value.trim(),
      policy: $('f-policy').value,
      budget: parseInt($('f-budget').value, 10) || 40,
      mock_llm: $('f-mock').checked,
    };

    S.events = []; S.seenSeq = -1; S.lastShot = ''; S.activeRow = null;
    S.graphSig = ''; S.firstLayout = true; S.startSig = '';
    S.staleRun = false; S.runStartedAt = Date.now(); S.lastEventAt = Date.now();
    S.logPinned = true;
    els.log.innerHTML = '<p class="empty">正在初始化探索器…</p>';
    els.logCount.textContent = '0';
    els.steps.textContent = '0';
    els.states.textContent = '0';
    els.cands.textContent = '0';
    els.bugs.textContent = '0';
    els.llm.textContent = '0';
    els.tActions.textContent = '0';
    els.tWall.textContent = '0s';
    els.tRelocate.textContent = '0';
    if (els.tUrls) els.tUrls.textContent = '0';
    els.shot.removeAttribute('src');
    els.shot.hidden = true;
    els.vpEmpty.hidden = false;
    if (els.viewport) els.viewport.classList.remove('has-shot');
    els.reportLink.hidden = true;
    els.reportLink.removeAttribute('href');
    els.verb.textContent = '—';
    els.target.textContent = '等待首个动作';
    els.url.textContent = '';
    if (els.liveComplete) els.liveComplete.hidden = true;
    if (els.liveError) els.liveError.hidden = true;
    if (els.liveHint) els.liveHint.hidden = true;
    if (els.graphEmpty) els.graphEmpty.hidden = false;
    renderBugs([]);
    if (S.cy) { S.cy.destroy(); S.cy = null; }
    els.graphCount.textContent = '0 节点 / 0 边';

    els.btnRun.disabled = true;
    els.btnRunTxt.textContent = '正在启动…';
    setConn(true, '连接中');
    els.status.textContent = '启动中';
    setPill(els.vpPill, 'running');
    setBarStatus('running');

    try {
      const res = await fetch('/api/runs', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      if (!res.ok) throw new Error('HTTP ' + res.status);
      const data = await res.json();
      S.runId = data.run_id;
      try { sessionStorage.setItem('ghostqa-run', S.runId); } catch (_) {}
      startPolling();
    } catch (err) {
      els.btnRun.disabled = false;
      els.btnRunTxt.textContent = '启动探索';
      setConn(false, '启动失败');
      els.status.textContent = '出错';
      setPill(els.vpPill, 'error');
      setBarStatus('error');
      showError('无法启动运行。确认目标地址可访问后再试。', err.message);
      els.log.innerHTML =
        `<p class="empty" style="color:var(--danger)">无法启动运行：${escapeHtml(err.message)}</p>`;
    }
  });
}

const presetBtn = $('btn-preset');
if (presetBtn) {
  presetBtn.addEventListener('click', () => {
    $('f-url').value = 'http://127.0.0.1:3939';
    $('f-spec').value = 'apps/buggy-shop/spec.json';
    $('f-budget').value = '40';
    $('f-policy').value = 'ghost-nollm';
    $('f-mock').checked = true;
    updatePolicyHint();
  });
}

const policySel = $('f-policy');
if (policySel) {
  policySel.addEventListener('change', updatePolicyHint);
  updatePolicyHint();
}

const fitBtn = $('graph-fit');
if (fitBtn) fitBtn.addEventListener('click', fitGraph);

if (els.log) {
  els.log.addEventListener('scroll', () => {
    const el = els.log;
    S.logPinned = (el.scrollHeight - el.scrollTop - el.clientHeight) < 48;
    if (els.logLatest) els.logLatest.hidden = S.logPinned;
  });
}
if (els.logLatest) {
  els.logLatest.addEventListener('click', () => {
    S.logPinned = true;
    els.log.scrollTop = els.log.scrollHeight;
    els.logLatest.hidden = true;
  });
}

window.GhostQA = window.GhostQA || {};
window.GhostQA.getTheme = readTheme;
window.GhostQA.setTheme = function setTheme(t) { applyTheme(t, true); };
window.GhostQA.toggleTheme = toggleTheme;
window.GhostQA.onView = function onView(name) {
  if (name === 'live') {
    requestAnimationFrame(() => {
      if (S.lastGraph) syncGraph(S.lastGraph);
      else if (S.cy) { S.cy.resize(); fitGraph(); }
    });
  }
};

const themeBtn = document.getElementById('theme-toggle');
if (themeBtn) {
  themeBtn.addEventListener('click', toggleTheme);
}
syncThemeToggle();

(async function restore() {
  try {
    const saved = sessionStorage.getItem('ghostqa-run');
    if (!saved) return;
    const st = await getJSON('/api/runs/' + saved);
    if (!st || !st.id) return;
    S.runId = st.id;
    S.runStartedAt = Date.now();
    S.lastEventAt = Date.now();
    setConn(true, '已连接');
    startPolling();
  } catch (_) { /* nothing to restore */ }
})();
