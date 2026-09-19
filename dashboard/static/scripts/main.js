/* ============================================================================
   GhostQA Dashboard — frontend controller
   Polls the run API, streams screenshots, grows the state graph, renders the
   decision log and confirmed-bug evidence. No framework, no build step.
   ========================================================================== */
'use strict';

const API = '';
const POLL_MS = 1200;
const STALE_MS = 45000;   // no events + no status change this long => stalled

const S = {
  runId: null,
  events: [],           // all step events seen so far
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
  mixNew: $('mix-new'), mixSimilar: $('mix-similar'), mixIdentical: $('mix-identical'),
  mNew: $('m-new'), mSimilar: $('m-similar'), mIdentical: $('m-identical'),
  bugList: $('bugs'), bugCount: $('bug-count'),
  bench: $('bench'), benchCount: $('bench-count'),
  log: $('log'), logCount: $('log-count'),
  form: $('run-form'), btnRun: $('btn-run'), btnRunTxt: $('btn-run-txt'),
  reportLink: $('report-link'),
};

const STATUS_TEXT = {
  idle: '空闲', running: '探索中', validating: '校验中',
  done: '已完成', error: '出错',
};

/* ------------------------------ helpers --------------------------------- */

function setConn(live, text) {
  els.conn.classList.toggle('is-live', !!live);
  els.connTxt.textContent = text;
}

function fmtAction(a) {
  if (!a) return ['?', ''];
  const verb = (a.type || 'act').toUpperCase();
  const detail = a.text || a.value || a.target_eid || a.key || '';
  return [verb, String(detail).slice(0, 70)];
}

function setPill(el, status) {
  el.className = 'status-pill is-' + status;
  el.textContent = STATUS_TEXT[status] || status;
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
  };
  img.onerror = () => { /* keep last good frame; transient during run */ };
  img.alt = altText || '探索器当前所见页面截图';
  img.src = url;
}

function updateActionStrip(ev) {
  const [verb, detail] = fmtAction(ev.action);
  els.verb.textContent = verb;
  els.target.textContent = detail || '（无文本目标）';
  els.url.textContent = (ev.dst && ev.dst.url ? ev.dst.url : '').replace(/^https?:\/\//, '');
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
  const row = document.createElement('div');
  row.className = 'log-row';
  row.dataset.seq = ev.seq;
  row.tabIndex = 0;
  row.setAttribute('role', 'button');
  row.innerHTML =
    `<span class="log-i">${String(ev.index + 1).padStart(2, '0')}</span>` +
    `<span class="log-txt">${escapeHtml(verb + ' ' + detail)}</span>` +
    `<span class="log-tag ${cls}">${tag}</span>`;
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
  // Only 'step' events belong in the decision log; run_done/run_error are
  // terminal signals handled by the status polling path.
  const steps = list.filter((e) => e.type === 'step');
  if (!steps.length) return;
  if (S.events.length === 0) els.log.innerHTML = '';
  for (const ev of steps) {
    S.events.push(ev);
    els.log.appendChild(renderLogRow(ev));
    // Auto-follow the newest frame while running.
    if (S.status === 'running' || S.status === 'validating') selectEvent(ev);
  }
  els.logCount.textContent = String(S.events.length);
  els.log.scrollTop = els.log.scrollHeight;
  els.steps.textContent = String(S.events.length);
  S.lastEventAt = Date.now();
  // Live telemetry derived from the stream, so the console reports progress
  // while a run is in flight instead of waiting for the final summary.
  els.tActions.textContent = String(S.events.length);
  const bugsSeen = steps.reduce((n, e) => n + (e.findings || []).length, 0);
  if (bugsSeen) els.cands.textContent = String(bugsSeen);
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => (
    { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]
  ));
}

/* ------------------------------- graph ---------------------------------- */

const REL_COLOR = { NEW: '#3ddad7', SIMILAR: '#a78bfa', IDENTICAL: '#6b7280' };

function graphStyles() {
  return [
    { selector: 'node', style: {
        'background-color': '#171a1f',
        'background-opacity': 1,
        'border-width': 2,
        'border-color': '#3ddad7',
        'width': 26, 'height': 26,
        'label': 'data(label)',
        'font-family': 'IBM Plex Mono, monospace',
        'font-size': 15,
        'font-weight': 500,
        'color': '#e2e7ed',
        'text-valign': 'bottom',
        'text-halign': 'center',
        'text-margin-y': 7,
        'text-max-width': '150px',
        'text-wrap': 'ellipsis',
        'text-opacity': 1,
        'transition-property': 'background-color, border-color, width, height',
        'transition-duration': 260,
    }},
    { selector: 'node[rel = "SIMILAR"]',   style: { 'border-color': '#a78bfa' }},
    { selector: 'node[rel = "IDENTICAL"]', style: { 'border-color': '#6b7280' }},
    { selector: 'node[?flagged]', style: {
        'background-color': '#ffb347', 'border-color': '#ffb347',
        'width': 36, 'height': 36, 'color': '#ffb347',
        'font-size': 17,
        'font-weight': 600,
    }},
    { selector: 'node[?isNew]', style: { 'background-color': '#3ddad7' }},
    { selector: 'edge', style: {
        'width': 1,
        'line-color': '#3a4250',
        'target-arrow-color': '#3a4250',
        'target-arrow-shape': 'triangle',
        'arrow-scale': 0.6,
        'curve-style': 'bezier',
        'opacity': 0.85,
    }},
    { selector: 'edge[rel = "NEW"]',       style: { 'line-color': '#3ddad7', 'target-arrow-color': '#3ddad7' }},
    { selector: 'edge[rel = "SIMILAR"]',   style: { 'line-color': '#a78bfa', 'target-arrow-color': '#a78bfa' }},
    { selector: 'edge[rel = "IDENTICAL"]', style: { 'line-color': '#6b7280', 'target-arrow-color': '#6b7280', 'line-style': 'dashed' }},
    { selector: ':selected', style: { 'border-width': 2.5, 'border-color': '#ffb347' }},
  ];
}

function initGraph() {
  if (S.cy) return;
  S.cy = cytoscape({
    container: $('graph'),
    elements: [],
    style: graphStyles(),
    layout: { name: 'preset' },
    wheelSensitivity: 0.22,
    minZoom: 0.25,
    maxZoom: 3,
  });
  // Simple force-directed settling, cheap enough to re-run on each refresh.
  S.cy.on('tap', 'node', (e) => {
    const sig = e.target.id();
    const found = [...S.events].reverse().find(
      (ev) => ev.dst && ev.dst.sig === sig && ev.dst.screenshot);
    if (found) {
      showShot(found.dst.screenshot, found.dst.title || sig);
      updateActionStrip(found);
    }
  });
  // Exposed for debugging and automated visual QA.
  window.__cy = S.cy;
}

function graphSignature(payload) {
  const nodes = (payload.nodes || []).map((n) => n.sig +
    (n.flags && n.flags.length ? '!' : '')).join(',');
  const edges = (payload.edges || []).map((e) => e.src + '>' + e.dst).join(',');
  return nodes + '|' + edges;
}

function syncGraph(payload) {
  initGraph();
  const cy = S.cy;
  const nodes = payload.nodes || [];
  const edges = payload.edges || [];
  const known = new Set(cy.nodes().map((n) => n.id()));

  for (const n of nodes) {
    const data = {
      id: n.sig,
      label: shortLabel(n),
      rel: n.relation || 'NEW',
      flagged: Array.isArray(n.flags) && n.flags.length > 0,
      isNew: (n.visits || 0) <= 1,
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

  // Re-layout only when the topology actually changed — otherwise the graph
  // would jitter on every poll and labels would never settle.
  const sig = graphSignature(payload);
  if (sig === S.graphSig) return;
  S.graphSig = sig;
  if (!S.startSig && nodes.length) S.startSig = nodes[0].sig;

  // A BFS-depth layered layout is both deterministic and semantically right:
  // distance from the start state maps to horizontal position, so growth of
  // the exploration is legible without the jitter of a force simulation.
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
  // Any node unreachable from the start (isolated or cyclic entry) gets its
  // own depth so the layer stays clean instead of collapsing to zero.
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
    animate: cy.nodes().length > 1 && !S.firstLayout,
    animationDuration: 380, animationEasing: 'ease-out',
    fit: true, padding: 48,
  }).run();

  // Clamp zoom: never balloon a tiny graph, never shrink labels illegibly.
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
      '<p class="empty">尚无已确认缺陷。<br>运行结束后，通过复现校验与 ddmin 最小化的问题会出现在这里。</p>';
    return;
  }
  for (const b of list) {
    const f = b.finding || {};
    const card = document.createElement('article');
    card.className = 'bug';
    const steps = (b.reproduction || [])
      .map((a) => `<li>${escapeHtml(fmtAction(a).join(' '))}</li>`).join('');
    const saved = (b.original_length || 0) - (b.reproduction || []).length;
    card.innerHTML =
      `<div class="bug-head" role="button" tabindex="0" aria-expanded="false">
         <span class="bug-kind">${escapeHtml(f.kind || 'defect')}</span>
         <span class="bug-desc">${escapeHtml(f.description || '')}</span>
       </div>
       <div class="bug-body">
         <div class="repro-meta">
           <span>原始 <b>${b.original_length ?? '?'}</b> 步</span>
           <span>最小化 <b>${(b.reproduction || []).length}</b> 步</span>
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

/* ------------------------------ benchmarks ------------------------------ */

function renderBenchmarks(list) {
  els.benchCount.textContent = String(list.length);
  els.bench.innerHTML = '';
  if (!list.length) {
    els.bench.innerHTML = '<p class="empty">暂无已发布指标。</p>';
    return;
  }
  for (const b of list) {
    const runs = (b.metrics && b.metrics.runs) || [];
    // Aggregate per policy: mean budget used and mean bug-discovery rate.
    const byPolicy = {};
    for (const r of runs) {
      const k = r.policy || '?';
      const e = byPolicy[k] = byPolicy[k] || { n: 0, bdr: 0, deep: 0, budget: 0, bugs: 0 };
      e.n += 1;
      e.bdr += r.bug_discovery_rate || 0;
      e.deep += r.deep_bug_discovery_rate || 0;
      e.budget += r.budget || 0;
      e.bugs += (r.confirmed_bugs || []).length;
    }
    const rows = Object.entries(byPolicy).map(([k, e]) => ({
      policy: k,
      bdr: e.bdr / e.n,
      deep: e.deep / e.n,
      budget: Math.round(e.budget / e.n),
      bugs: (e.bugs / e.n).toFixed(1),
    })).sort((a, c) => c.bdr - a.bdr);

    const card = document.createElement('article');
    card.className = 'bench';
    const maxBdr = Math.max(0.0001, ...rows.map((r) => r.bdr));
    card.innerHTML =
      `<div class="bench-head">
         <span class="bench-name">${escapeHtml(b.name)}</span>
         <span class="bench-meta">${rows.length} 策略 · ${runs.length} 次运行</span>
       </div>
       <table class="bench-tbl">
         <thead><tr><th>策略</th><th>BDR</th><th>Deep</th><th>预算</th><th>缺陷</th></tr></thead>
         <tbody>${rows.map((r) => `
           <tr>
             <td class="bench-p">${escapeHtml(r.policy)}</td>
             <td><span class="bar" style="width:${(r.bdr / maxBdr * 100).toFixed(0)}%"></span><b>${r.bdr.toFixed(3)}</b></td>
             <td>${r.deep.toFixed(3)}</td>
             <td>${r.budget}</td>
             <td>${r.bugs}</td>
           </tr>`).join('')}</tbody>
       </table>`;
    els.bench.appendChild(card);
  }
}

/* ------------------------------- polling -------------------------------- */

async function getJSON(path) {
  const res = await fetch(API + path, { cache: 'no-store' });
  if (!res.ok) throw new Error(`HTTP ${res.status} ${path}`);
  return res.json();
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
  // The button is disabled only while *this* run is active. A stale run left
  // behind by a crash must never lock the operator out of starting a new one.
  const active = (st.status === 'running' || st.status === 'validating');
  els.btnRun.disabled = active && !S.staleRun;
  els.btnRunTxt.textContent = (active && !S.staleRun) ? '探索进行中…' : '启动探索';
  if (active && S.runStartedAt && Date.now() - S.runStartedAt > STALE_MS
      && S.lastEventAt && Date.now() - S.lastEventAt > STALE_MS) {
    S.staleRun = true;   // no new events for a long while: treat as stalled
    els.btnRun.disabled = false;
    els.btnRunTxt.textContent = '重新启动';
  }
  // LLM call count is only known at the end of a run; show a placeholder
  // rather than a misleading zero while it is still working.
  if (st.status === 'running' || st.status === 'validating') {
    els.llm.textContent = '…';
  }
  if (st.candidates && st.candidates.length) {
    els.cands.textContent = String(st.candidates.length);
  }

  // Events (incremental).
  try {
    const ev = await getJSON(`/api/runs/${S.runId}/events?after=${S.seenSeq}`);
    if (ev.events && ev.events.length) {
      appendEvents(ev.events);
      S.seenSeq = ev.events[ev.events.length - 1].seq;
    }
  } catch (_) { /* transient */ }

  // Graph.
  try { syncGraph(await getJSON(`/api/runs/${S.runId}/graph`)); } catch (_) {}

  // Bugs (only meaningful once validation finished, but cheap to poll).
  try { renderBugs(await getJSON(`/api/runs/${S.runId}/bugs`)); } catch (_) {}

  // Summary / telemetry. Only available once the run finishes; while it is
  // in flight the stream-derived counters above carry the display.
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
    stopPolling();
    setConn(true, '已完成');
  } else if (st.status === 'error') {
    els.reportLink.hidden = true;
    stopPolling();
    setConn(false, '运行出错');
    els.log.insertAdjacentHTML('beforeend',
      `<p class="empty" style="color:var(--danger)">运行出错：${escapeHtml((st.error || '').split('\n').pop() || '未知错误')}</p>`);
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

els.form.addEventListener('submit', async (e) => {
  e.preventDefault();
  const payload = {
    url: $('f-url').value.trim(),
    spec: $('f-spec').value.trim(),
    policy: $('f-policy').value,
    budget: parseInt($('f-budget').value, 10) || 40,
    mock_llm: $('f-mock').checked,
  };

  // Reset the console to a clean slate for the new run.
  S.events = []; S.seenSeq = -1; S.lastShot = ''; S.activeRow = null;
  S.graphSig = ''; S.firstLayout = true; S.startSig = '';
  S.staleRun = false; S.runStartedAt = Date.now(); S.lastEventAt = Date.now();
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
  els.shot.removeAttribute("src");
  els.shot.hidden = true;
  els.vpEmpty.hidden = false;
  els.reportLink.hidden = true;
  els.reportLink.removeAttribute("href");
  els.verb.textContent = '—';
  els.target.textContent = '等待首个动作';
  els.url.textContent = '';
  renderBugs([]);
  if (S.cy) { S.cy.destroy(); S.cy = null; }
  els.graphCount.textContent = '0 节点 / 0 边';

  els.btnRun.disabled = true;
  els.btnRunTxt.textContent = '正在启动…';
  setConn(true, '连接中');
  els.status.textContent = '启动中';
  setPill(els.vpPill, 'running');

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
    els.log.innerHTML =
      `<p class="empty" style="color:var(--danger)">无法启动运行：${escapeHtml(err.message)}</p>`;
  }
});

// Restore the most recent run if the page is reloaded mid-session.
(async function restore() {
  // Published benchmark evidence is static — load it once, independently of
  // any live run.
  try { renderBenchmarks(await getJSON('/api/benchmarks')); } catch (_) {}

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
