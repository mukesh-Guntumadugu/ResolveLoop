/* ResolveLoop demo UI. Vanilla JS, no build step, no network dependencies beyond the API itself.
 * Every request carries X-Tenant-ID and X-API-Key from the settings strip (persisted in localStorage).
 * URLs are relative to the mount point so the app works at /ui/, at / and behind a proxy prefix. */
(function () {
  'use strict';

  // ---------- helpers ----------
  const BASE = location.pathname.replace(/\/ui\/?.*$/, '').replace(/\/$/, '');
  const url = (path) => BASE + '/' + path;
  const $ = (sel, root) => (root || document).querySelector(sel);
  const $$ = (sel, root) => Array.from((root || document).querySelectorAll(sel));
  const esc = (s) => String(s == null ? '' : s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const json = (o) => esc(JSON.stringify(o, null, 2));
  const compact = (o) => (o == null ? '—' : typeof o === 'object' ? esc(JSON.stringify(o)) : esc(o));
  const badge = (s, extra) => `<span class="badge s-${esc(s)} ${extra || ''}">${esc(s)}</span>`;
  const when = (iso) => { if (!iso) return ''; const d = new Date(iso); return isNaN(d) ? esc(iso) : d.toLocaleTimeString([], { hour12: false }); };
  const uuid = () => (crypto.randomUUID ? crypto.randomUUID() : 'k-' + Math.random().toString(16).slice(2) + Date.now().toString(16));
  const newestFirst = (arr) => (Array.isArray(arr) ? arr.slice().reverse() : []);
  // Run an async action once per click: the button is disabled until the request settles, so a double
  // click (or a synthetic click plus keyboard activation) cannot fire the same POST twice.
  // Replace an element's HTML only when the generated markup differs from what we last wrote, so the
  // 3-second poll does not rebuild clickable lists that have not changed.
  const lastHtml = new WeakMap();
  function setHtml(el, html) {
    if (lastHtml.get(el) === html) return false;
    lastHtml.set(el, html); el.innerHTML = html; return true;
  }
  async function guarded(btn, fn) {
    if (!btn || btn.dataset.busy) return;
    btn.dataset.busy = '1'; btn.disabled = true;
    try { await fn(); } finally { delete btn.dataset.busy; btn.disabled = false; }
  }

  const settings = {
    get tenant() { return (localStorage.getItem('rl.tenant') || 'demo').trim() || 'demo'; },
    set tenant(v) { localStorage.setItem('rl.tenant', v); },
    get key() { return localStorage.getItem('rl.key') || ''; },
    set key(v) { localStorage.setItem('rl.key', v); },
  };

  function toast(kind, title, text) {
    const box = $('#toasts');
    const el = document.createElement('div');
    el.className = 'toast ' + kind;
    el.innerHTML = `<b>${esc(title)}</b>${esc(text)}`;
    box.appendChild(el);
    setTimeout(() => el.remove(), kind === 'error' ? 7000 : 3500);
  }

  class ApiErr extends Error {
    constructor(env) { super(env.message); this.env = env; }
  }

  async function api(method, path, body, opts = {}) {
    const headers = { 'X-Tenant-ID': settings.tenant, 'X-API-Key': settings.key, 'Accept': 'application/json' };
    if (body !== undefined) headers['Content-Type'] = 'application/json';
    let res;
    try {
      res = await fetch(url(path), { method, headers, body: body === undefined ? undefined : JSON.stringify(body) });
    } catch (e) {
      const env = { status: 'error', code: 'NETWORK', message: 'Cannot reach the ResolveLoop API: ' + e.message, data: null };
      if (!opts.quiet) toast('error', env.code, env.message);
      setConn(false);
      throw new ApiErr(env);
    }
    let env;
    try { env = await res.json(); } catch (e) { env = null; }
    if (!env || typeof env !== 'object' || !('status' in env)) {
      // FastAPI validation errors arrive as {detail: [...]}; wrap them in the envelope shape.
      const msg = env && env.detail ? (typeof env.detail === 'string' ? env.detail : JSON.stringify(env.detail)) : res.statusText || ('HTTP ' + res.status);
      env = { status: res.ok ? 'ok' : 'error', code: 'HTTP_' + res.status, message: msg, correlation_id: null, data: env };
    }
    env.http = res.status;
    setConn(true);
    if (!res.ok) {
      if (!opts.quiet) toast('error', `${env.code} (HTTP ${res.status})`, env.message);
      throw new ApiErr(env);
    }
    return env;
  }

  function setConn(ok) {
    const el = $('#conn-status');
    el.className = 'conn ' + (ok ? 'ok' : 'bad');
    el.textContent = ok ? '● connected' : '● offline';
  }

  // ---------- state ----------
  const state = {
    tab: 'customer',
    chat: JSON.parse(sessionStorage.getItem('rl.chat') || '[]'),  // {role:'user'|'bot', text, env, outcome, pending}
    accounts: [],
    cases: [],
    selectedCase: sessionStorage.getItem('rl.case') || null,  // id
    toolsSpec: null,
    toolsRenderedFor: null,
    learnResult: null,   // {caseId, ok, env}
    playbooks: [],
    selectedPb: sessionStorage.getItem('rl.pb') || null,
    pbDetail: null,
    editRenderedFor: null,
    busy: false,
  };

  // ---------- settings strip ----------
  function initSettings() {
    $('#set-tenant').value = settings.tenant;
    $('#set-key').value = settings.key;
    $('#set-tenant').addEventListener('change', (e) => { settings.tenant = e.target.value.trim() || 'demo'; refresh(true); });
    $('#set-key').addEventListener('input', (e) => { settings.key = e.target.value; });
    $('#set-key').addEventListener('change', () => refresh(true));
    $('#settings-form').addEventListener('submit', (e) => { e.preventDefault(); refresh(true); });
  }

  // ---------- tabs ----------
  function initTabs() {
    $$('.tab').forEach((b) => b.addEventListener('click', () => showTab(b.dataset.tab)));
    const fromHash = location.hash.replace('#', '');
    if (['customer', 'desk', 'reviewer', 'audit'].includes(fromHash)) state.tab = fromHash;
    showTab(state.tab);
  }
  function showTab(name) {
    state.tab = name;
    $$('.tab').forEach((b) => b.classList.toggle('active', b.dataset.tab === name));
    $$('.panel').forEach((p) => p.classList.toggle('active', p.id === 'tab-' + name));
    history.replaceState(null, '', '#' + name);
    refresh(true);
  }

  // ---------- polling ----------
  async function refresh(force) {
    if (state.busy && !force) return;
    if (document.hidden && !force) return;
    state.busy = true;
    sessionStorage.setItem('rl.case', state.selectedCase || '');
    sessionStorage.setItem('rl.pb', state.selectedPb || '');
    try {
      if (state.tab === 'customer') await refreshCustomer();
      else if (state.tab === 'desk') await refreshDesk();
      else if (state.tab === 'reviewer') await refreshReviewer();
      else if (state.tab === 'audit') await refreshAudit();
    } catch (e) {
      if (!(e instanceof ApiErr)) console.error(e);
    } finally {
      state.busy = false;
    }
  }

  // ======================================================================
  // TAB 1: CUSTOMER (simulated eGain action call)
  // ======================================================================
  function initCustomer() {
    $('#chat-form').addEventListener('submit', async (e) => {
      e.preventDefault();
      const text = $('#chat-message').value.trim();
      if (!text) return;
      $('#chat-message').value = '';
      await guarded($('#chat-form button[type=submit]'), () => sendResolve($('#chat-account').value.trim() || 'C002', text, false));
    });
    $$('.chip').forEach((c) => c.addEventListener('click', () => { $('#chat-message').value = c.dataset.say; $('#chat-message').focus(); }));
    $('#chat-log').addEventListener('click', async (e) => {
      const btn = e.target.closest('button[data-confirm]');
      if (!btn) return;
      const idx = Number(btn.dataset.confirm);
      const m = state.chat[idx];
      if (!m || !m.pending) return;
      m.pending = false;
      renderChat();
      await sendResolve(m.account, m.utterance, true);
    });
  }

  async function sendResolve(account, utterance, confirm) {
    state.chat.push({ role: 'user', text: confirm ? `Yes, apply the fix (${account})` : `[${account}] ${utterance}` });
    renderChat();
    const body = { account_id: account, utterance, confirm, idempotency_key: uuid() };
    let env;
    try {
      env = await api('POST', 'v1/resolve', body, { quiet: true });
    } catch (e) {
      env = e.env;
      state.chat.push({ role: 'bot', outcome: 'error', env, account, utterance });
      renderChat();
      return;
    }
    const d = env.data || {};
    state.chat.push({ role: 'bot', outcome: d.outcome || 'unknown', env, account, utterance, pending: d.outcome === 'needs_confirmation' });
    renderChat();
    refreshAccountsMini();
  }

  function renderChat() {
    sessionStorage.setItem('rl.chat', JSON.stringify(state.chat));
    const log = $('#chat-log');
    if (!state.chat.length) { log.innerHTML = '<div class="chat-empty">No messages yet. Pick an account and describe the problem.</div>'; return; }
    log.innerHTML = state.chat.map((m, i) => {
      if (m.role === 'user') return `<div class="msg user"><div class="who">Customer</div>${esc(m.text)}</div>`;
      const env = m.env || {}; const d = env.data || {};
      let body = '';
      if (m.outcome === 'error') {
        body = `<div class="outcome">Request failed</div><div class="kv"><b>${esc(env.code)}</b> &middot; ${esc(env.message)}</div>`;
      } else if (m.outcome === 'escalate') {
        body = `<div class="outcome">⚠ Escalating to a specialist</div>
          <div class="kv">${esc(d.reason || env.message)}</div>
          ${d.execution ? `<div class="kv">Execution ${badge(d.execution.status)} <span class="mono">${esc(d.execution.id)}</span></div>` : ''}
          ${d.match ? `<div class="kv muted">match: ${esc(d.match.decision || 'match')} (score ${Number(d.match.score || 0).toFixed(2)})</div>` : ''}
          <div class="kv"><b>Your options:</b><ul>${(d.escalation_options || []).map((o) => `<li>${esc(o)}</li>`).join('')}</ul></div>`;
      } else if (m.outcome === 'needs_confirmation') {
        body = `<div class="outcome">❓ Approved fix found</div>
          <div class="kv">${esc(d.prompt)}</div>
          <div class="kv"><b>Proposed actions:</b><ul>${(d.proposed_actions || []).map((o) => `<li><code>${esc(o)}</code></li>`).join('')}</ul></div>
          <div class="kv muted">Playbook ${esc(d.playbook && d.playbook.name)} v${esc(d.playbook && d.playbook.version)} &middot; execution ${badge(d.execution && d.execution.status)}</div>
          ${m.pending ? `<div class="actions"><button class="ok" data-confirm="${i}">Yes, apply the fix</button></div>` : '<div class="kv muted">confirmed</div>'}`;
      } else if (m.outcome === 'resolved') {
        const sa = d.state_after || {};
        body = `<div class="outcome">✅ Fixed and verified <span class="badge verified">VERIFIED</span>${d.replayed ? ' <span class="badge">REPLAYED</span>' : ''}</div>
          <div class="kv">Playbook <b>${esc(d.playbook && d.playbook.name)}</b> v${esc(d.playbook && d.playbook.version)}</div>
          <div class="kv">Execution ${badge(d.execution && d.execution.status)} <span class="mono">${esc(d.execution && d.execution.id)}</span></div>
          <div class="kv"><b>State after:</b> <span class="diff">${Object.keys(sa).map((k) => `<span class="same">${esc(k)}=${esc(JSON.stringify(sa[k]))}</span>`).join('')}</span></div>`;
      } else {
        body = `<div class="outcome">${esc(env.message)}</div>`;
      }
      return `<div class="msg bot o-${esc(m.outcome)}"><div class="who">Orbit support agent &middot; ${esc(env.code || '')}</div>${body}
        <details><summary>raw JSON</summary><pre>${json(env)}</pre></details></div>`;
    }).join('');
    log.scrollTop = log.scrollHeight;
  }

  async function refreshCustomer() { await refreshAccountsMini(); }

  async function refreshAccountsMini() {
    const env = await api('GET', 'v1/accounts', undefined, { quiet: true });
    state.accounts = env.data || [];
    const sel = $('#chat-account').value.trim();
    const dot = (v) => `<span class="dot ${v === true ? 't' : v === false ? 'f' : 'n'}"></span>`;
    $('#accounts-mini').innerHTML = state.accounts.length ? `<table>
      <tr class="muted"><td>id</td><td>role</td><td>plan</td><td title="active">act</td><td title="migrated">mig</td><td title="export_permission">exp</td></tr>
      ${state.accounts.map((a) => `<tr class="${a.id === sel ? 'sel' : ''}" data-acc="${esc(a.id)}"><td><b>${esc(a.id)}</b></td><td>${esc(a.role)}</td><td>${esc(a.plan)}</td><td>${dot(a.active)}</td><td>${dot(a.migrated)}</td><td>${dot(a.export_permission)}</td></tr>`).join('')}
      </table><div class="hint">click a row to chat as that account &middot; green = true, red = false, grey = unknown</div>` : '<span class="muted">No accounts. Reset the demo data on the Audit tab.</span>';
    $$('#accounts-mini tr[data-acc]').forEach((tr) => tr.addEventListener('click', () => { $('#chat-account').value = tr.dataset.acc; refreshAccountsMini(); }));
  }

  // ======================================================================
  // TAB 2: HUMAN DESK
  // ======================================================================
  function initDesk() {
    $('#newcase-form').addEventListener('submit', async (e) => {
      e.preventDefault();
      const body = { customer_id: $('#nc-customer').value.trim(), utterance: $('#nc-utterance').value.trim(), context: { category: $('#nc-category').value.trim() }, channel: 'desk' };
      await guarded($('#newcase-form button[type=submit]'), async () => {
        try {
          const env = await api('POST', 'v1/cases', body);
          toast('ok', 'Case created', env.data.id);
          state.selectedCase = env.data.id;
          state.learnResult = null;
          await refreshDesk();
        } catch (e) { /* toast shown */ }
      });
    });
    $('#case-list').addEventListener('click', (e) => {
      const li = e.target.closest('li[data-id]');
      if (!li) return;
      state.selectedCase = li.dataset.id;
      state.learnResult = null;
      state.toolsRenderedFor = null;
      refreshDesk();
    });
  }

  async function refreshDesk() {
    const env = await api('GET', 'v1/cases', undefined, { quiet: true });
    state.cases = newestFirst(env.data);
    renderCaseList();
    if (state.selectedCase && !state.cases.some((c) => c.id === state.selectedCase)) state.selectedCase = null;
    if (!state.selectedCase) { $('#case-detail').innerHTML = '<div class="muted">Select a case on the left, or create one.</div>'; state.toolsRenderedFor = null; return; }
    await renderCaseDetail();
  }

  function renderCaseList() {
    $('#cases-count').textContent = state.cases.length ? `(${state.cases.length})` : '';
    setHtml($('#case-list'), state.cases.length ? state.cases.map((c) => `
      <li data-id="${esc(c.id)}" class="${c.id === state.selectedCase ? 'sel' : ''}">
        <div class="cl-top"><span class="cl-id">${esc(c.id)}</span>${badge(c.status)}</div>
        <div class="cl-utt"><b>${esc(c.customer_id)}</b> &middot; ${esc(c.utterance)}</div>
        <div class="cl-meta">${esc(c.channel)} &middot; ${when(c.created_at)} &middot; ${esc(c.verification_state)}</div>
      </li>`).join('') : '<li class="muted">No cases yet.</li>');
  }

  async function renderCaseDetail() {
    const id = state.selectedCase;
    const box = $('#case-detail');
    if (!box.dataset.forCase || box.dataset.forCase !== id) {
      box.dataset.forCase = id;
      box.innerHTML = `
        <div id="cd-head"></div>
        <div class="detail-grid">
          <div><h3>Account profile</h3><div id="cd-profile" class="profile muted">loading…</div></div>
          <div><h3>Case history</h3><ul id="cd-history" class="history"></ul></div>
        </div>
        <h3 style="margin-top:14px">Allowlisted tools</h3>
        <div id="cd-tools" class="muted">loading…</div>
        <div id="cd-learn"></div>
        <h3 style="margin-top:14px">Live trace <span class="muted" id="cd-trace-count"></span></h3>
        <ol id="cd-trace" class="trace"></ol>`;
    }
    const [caseEnv, traceEnv] = await Promise.all([
      api('GET', `v1/cases/${encodeURIComponent(id)}`, undefined, { quiet: true }),
      api('GET', `v1/cases/${encodeURIComponent(id)}/trace`, undefined, { quiet: true }),
    ]);
    const c = caseEnv.data; const trace = traceEnv.data || [];
    if (state.selectedCase !== id) return;

    // Only rebuild the header (and its buttons) when something in it changed, so a poll never swaps a
    // button out from under the user's click.
    const headKey = [c.status, c.verification_state, (c.history || []).length].join('|');
    if ($('#cd-head').dataset.key !== headKey) {
    $('#cd-head').dataset.key = headKey;
    $('#cd-head').innerHTML = `
      <div class="row" style="justify-content:space-between">
        <div><h2 style="margin:0">${esc(c.customer_id)} &middot; ${esc(c.utterance)}</h2>
          <div class="muted mono">${esc(c.id)} &middot; trace ${esc(c.trace_id)} &middot; ${esc(c.channel)} &middot; ${esc((c.context || {}).category || '')}</div></div>
        <div class="row">${badge(c.status)} <span class="badge ${c.verification_state === 'verified' ? 'verified' : 'unverified'}">${esc(c.verification_state)}</span></div>
      </div>
      <div class="actions">
        <button id="cd-escalate" class="warn">Escalate</button>
        <button id="cd-resolve" class="ok">Mark resolved</button>
        <button id="cd-learn-btn" class="primary">Learn procedure</button>
      </div>`;
    $('#cd-escalate').onclick = (e) => guarded(e.currentTarget, async () => { try { await api('POST', `v1/cases/${id}/escalate`); toast('ok', 'Escalated', 'cases.escalate recorded in the trace'); await refreshDesk(); } catch (err) {} });
    $('#cd-resolve').onclick = (e) => guarded(e.currentTarget, async () => { try { const r = await api('POST', `v1/cases/${id}/status/HUMAN_RESOLVED`); toast('ok', 'HUMAN_RESOLVED', 'verification: ' + r.data.verification_state); await refreshDesk(); } catch (err) {} });
    $('#cd-learn-btn').onclick = (e) => guarded(e.currentTarget, () => learnFromCase(id));
    $('#cd-history').innerHTML = (c.history || []).map((h) => `<li>${when(h.at)} → ${badge(h.to)} <span class="muted">${esc(h.note || '')}</span></li>`).join('');
    }

    try {
      const p = (await api('GET', `v1/accounts/${encodeURIComponent(c.customer_id)}`, undefined, { quiet: true })).data;
      const html = `<dl>${['id', 'plan', 'role', 'active', 'migrated', 'export_permission'].map((k) => `<dt>${esc(k)}</dt><dd>${fmtVal(p[k])}</dd>`).join('')}</dl>`;
      if ($('#cd-profile').innerHTML !== html) { $('#cd-profile').className = 'profile'; $('#cd-profile').innerHTML = html; }
    } catch (e) { $('#cd-profile').innerHTML = `<span class="problem">${esc(e.env.code)}: ${esc(e.env.message)}</span>`; }

    if (state.toolsRenderedFor !== id) { await renderTools(c); state.toolsRenderedFor = id; }
    renderLearn(id);
    renderTrace(trace);
  }

  function fmtVal(v) {
    if (v === true) return '<span class="badge yes">true</span>';
    if (v === false) return '<span class="badge no">false</span>';
    if (v == null) return '<span class="badge">unknown</span>';
    return esc(v);
  }

  async function renderTools(c) {
    if (!state.toolsSpec) state.toolsSpec = (await api('GET', 'v1/tools', undefined, { quiet: true })).data || [];
    const defaults = { account_id: c.customer_id, case_id: c.id, feature: 'export', channel: 'email' };
    const box = $('#cd-tools');
    box.className = 'tools';
    box.innerHTML = `
      <label class="consent"><input type="checkbox" id="cd-consent"> <span><b>Customer consent obtained</b> &mdash; required before any <span class="badge kind-mutation">mutation</span> tool runs</span></label>
      ${state.toolsSpec.map((t, i) => `
        <div class="tool" data-tool="${esc(t.tool_id)}" data-kind="${esc(t.kind)}">
          <div class="tool-head"><span><code>${esc(t.tool_id)}</code> <span class="badge kind-${esc(t.kind)}">${esc(t.kind)}</span></span>
            <button class="small ${t.kind === 'mutation' ? 'danger' : 'primary'} run-tool" data-i="${i}">Run</button></div>
          <div class="tool-desc">${esc(t.description)}</div>
          <div class="tool-params">${t.params.map((p) => `<label>${esc(p)} <input type="text" data-param="${esc(p)}" value="${esc(defaults[p] || '')}"></label>`).join('')}</div>
        </div>`).join('')}`;
    const consent = $('#cd-consent');
    const syncConsent = () => $$('.tool[data-kind=mutation] .run-tool', box).forEach((b) => { b.disabled = !consent.checked; b.title = consent.checked ? '' : 'Tick the consent box first'; });
    consent.addEventListener('change', syncConsent);
    syncConsent();
    $$('.run-tool', box).forEach((b) => b.addEventListener('click', () => guarded(b, async () => {
      const t = state.toolsSpec[Number(b.dataset.i)];
      const wrap = b.closest('.tool');
      const params = {};
      $$('input[data-param]', wrap).forEach((inp) => { if (inp.value.trim() !== '') params[inp.dataset.param] = inp.value.trim(); });
      const body = { case_id: c.id, tool_id: t.tool_id, params, actor_id: 'specialist-1', actor_type: 'human', consent: consent.checked };
      try {
        const env = await api('POST', 'v1/tools/invoke', body);
        toast(env.data.success ? 'ok' : 'error', t.tool_id + (env.data.success ? ' succeeded' : ' returned success=false'), JSON.stringify(env.data.result));
      } catch (e) { /* toast shown; the failed call is still recorded in the trace */ }
      await refreshDesk();
    }).then(syncConsent)));
  }

  async function learnFromCase(id) {
    try {
      const env = await api('POST', `v1/cases/${id}/learn`, undefined, { quiet: true });
      state.learnResult = { caseId: id, ok: true, env };
      toast('ok', env.code, env.message + ' — see the Reviewer tab');
    } catch (e) {
      state.learnResult = { caseId: id, ok: false, env: e.env };
      toast('error', e.env.code, e.env.message);
    }
    renderLearn(id);
  }

  function renderLearn(id) {
    const box = $('#cd-learn');
    const r = state.learnResult;
    if (!r || r.caseId !== id) { setHtml(box, ''); return; }
    const env = r.env; const d = env.data || {};
    if (r.ok) {
      const changed = setHtml(box, `<div class="note" style="margin-top:12px"><b>HTTP ${env.http} ${esc(env.code)}</b> &mdash; ${esc(env.message)}<br>
        Candidate <b>${esc(d.name)}</b> v${esc(d.version)} ${badge(d.status)} <span class="mono">${esc(d.id)}</span><br>
        steps: ${(d.steps || []).map((s) => `<code>${esc(s.tool)}</code>`).join(', ')} &middot; verifier: <code>${esc(d.verifier && d.verifier.tool)}</code> &middot; ${(d.prerequisites || []).length} prerequisite(s)
        ${(d.review_notes || []).length ? `<br>review notes: ${d.review_notes.map(esc).join('; ')}` : ''}
        <div class="actions"><button class="primary small" id="cd-open-reviewer">Open in Reviewer</button></div></div>`);
      if (changed) $('#cd-open-reviewer').onclick = () => { state.selectedPb = d.id; showTab('reviewer'); };
    } else {
      const details = (d && d.details) || [];
      setHtml(box, `<div class="note" style="margin-top:12px;background:#fdecec;border-color:#f3b4b4;color:#6b1414"><b>HTTP ${env.http} ${esc(env.code)}</b> &mdash; knowledge gap: ${esc(env.message)}
        ${details.length ? `<ul>${details.map((x) => `<li>${esc(x)}</li>`).join('')}</ul>` : ''}</div>`);
    }
  }

  function renderTrace(trace) {
    $('#cd-trace-count').textContent = trace.length ? `(${trace.length} events)` : '';
    const box = $('#cd-trace');
    const prev = box.childElementCount;
    box.innerHTML = trace.length ? trace.map((e, i) => `
      <li class="${e.success ? '' : 'fail'} ${i >= prev ? 'flash' : ''}">
        <div class="tr-head">
          <span class="badge actor-${esc(e.actor_type)}">${esc(e.actor_type)}</span><span class="muted mono">${esc(e.actor_id)}</span>
          <span class="tr-tool">${esc(e.tool_id)}</span>
          <span class="badge ${e.success ? 'yes' : 'no'}">${e.success ? 'success' : 'failed' + (e.error ? ': ' + esc(e.error) : '')}</span>
          ${e.execution_id ? `<span class="muted mono">exec ${esc(e.execution_id)}</span>` : ''}
          <span class="tr-time">${when(e.timestamp)}</span>
        </div>
        <div class="tr-body">
          <b>inputs</b><span class="mono">${compact(e.safe_inputs)}</span>
          <b>output</b><span class="mono">${compact(e.safe_output)}</span>
          ${e.before_state && e.after_state ? `<b>state</b><span>${diff(e.before_state, e.after_state)}</span>` : ''}
        </div>
      </li>`).join('') : '<li class="muted" style="padding-left:10px">No tool actions recorded yet.</li>';
  }

  function diff(a, b) {
    const keys = Array.from(new Set([...Object.keys(a || {}), ...Object.keys(b || {})]));
    const changed = keys.filter((k) => JSON.stringify(a[k]) !== JSON.stringify(b[k]));
    if (!changed.length) return '<span class="diff"><span class="same">no state change</span></span>';
    return `<span class="diff">${changed.map((k) => `<span>${esc(k)}: ${esc(JSON.stringify(a[k]))} → ${esc(JSON.stringify(b[k]))}</span>`).join('')}</span>`;
  }

  // ======================================================================
  // TAB 3: REVIEWER
  // ======================================================================
  function initReviewer() {
    $('#pb-table tbody').addEventListener('click', (e) => {
      const tr = e.target.closest('tr[data-id]');
      if (!tr) return;
      state.selectedPb = tr.dataset.id;
      state.editRenderedFor = null;
      refreshReviewer();
    });
  }

  async function refreshReviewer() {
    const env = await api('GET', 'v1/playbooks', undefined, { quiet: true });
    state.playbooks = newestFirst(env.data);
    $('#pb-count').textContent = state.playbooks.length ? `(${state.playbooks.length})` : '';
    setHtml($('#pb-table tbody'), state.playbooks.length ? state.playbooks.map((p) => `
      <tr data-id="${esc(p.id)}" class="clickable ${p.id === state.selectedPb ? 'sel' : ''}">
        <td>v${esc(p.version)}</td><td>${badge(p.status)}</td><td>${esc(p.name)}<div class="muted mono">${esc(p.id)}</div></td><td>${esc(p.intent)}</td><td>${esc(p.risk)}</td>
      </tr>`).join('') : '<tr><td colspan="5" class="muted">No playbooks yet. Resolve a case on the Human desk and click "Learn procedure".</td></tr>');
    if (state.selectedPb && !state.playbooks.some((p) => p.id === state.selectedPb)) state.selectedPb = null;
    if (!state.selectedPb) { $('#pb-detail').innerHTML = '<div class="muted">Select a playbook to review it.</div>'; state.editRenderedFor = null; return; }
    const d = (await api('GET', `v1/playbooks/${encodeURIComponent(state.selectedPb)}`, undefined, { quiet: true })).data;
    state.pbDetail = d;
    renderPbDetail(d);
  }

  function renderPbDetail(p) {
    const box = $('#pb-detail');
    const key = p.id + ':' + p.status + ':' + (p.history || []).length;
    if (box.dataset.key !== key) {
      box.dataset.key = key;
      const can = (to) => ({ DRAFT: ['REVIEW_PENDING', 'REJECTED'], REVIEW_PENDING: ['APPROVED', 'REJECTED'], APPROVED: ['RETIRED'], RETIRED: ['APPROVED'], REJECTED: [] }[p.status] || []).includes(to);
      const problems = p.validation || [];
      box.innerHTML = `
        <div class="row" style="justify-content:space-between">
          <div><h2 style="margin:0">${esc(p.name)}</h2><div class="muted mono">${esc(p.id)} &middot; lineage ${esc(p.lineage_id)} &middot; from case ${esc(p.source_case_id)}</div></div>
          <div class="row">${badge(p.status)} <span class="badge">v${esc(p.version)}</span> <span class="badge">risk: ${esc(p.risk)}</span></div>
        </div>
        <div class="pb-section"><b>Intent:</b> ${esc(p.intent)} &middot; <b>Extractor:</b> ${esc(p.extractor)}<br>${esc(p.summary)}</div>
        <div class="row" style="margin-top:10px">
          <label class="hint">reviewer <input type="text" id="pb-reviewer" value="reviewer-1" size="10"></label>
          <label class="hint">note <input type="text" id="pb-note" placeholder="optional" size="24"></label>
        </div>
        <div class="actions">
          <button class="ok" data-act="approve" ${can('APPROVED') && p.status !== 'RETIRED' ? '' : 'disabled'}>Approve</button>
          <button class="danger" data-act="reject" ${can('REJECTED') ? '' : 'disabled'}>Reject</button>
          <button class="warn" data-act="retire" ${can('RETIRED') ? '' : 'disabled'}>Retire</button>
          <button data-act="rollback" ${p.status === 'RETIRED' ? '' : 'disabled'} title="Re-approve this retired version">Rollback</button>
          <button id="pb-edit-toggle">Edit</button>
        </div>
        <div id="pb-edit" class="edit-form" style="display:none"></div>
        <div class="detail-grid" style="margin-top:14px">
          <div>
            <div class="pb-section"><h4>Match examples (${(p.match_examples || []).length})</h4><ul>${(p.match_examples || []).map((m) => `<li>${esc(m)}</li>`).join('')}</ul></div>
            <div class="pb-section"><h4>Prerequisites (checked against live state)</h4><ul>${(p.prerequisites || []).map((q) => `<li class="mono">${q.field ? `${esc(q.field)} ${esc(q.op || '==')} ${esc(JSON.stringify(q.value))}` : `${esc(q.tool)}(${esc(JSON.stringify(q.params))}) expects ${esc(JSON.stringify(q.expect))}`}</li>`).join('')}</ul></div>
            <div class="pb-section"><h4>Steps</h4><ul>${(p.steps || []).map((s) => `<li class="mono">${esc(s.tool)}(${esc(JSON.stringify(s.params))}) ${s.requires_consent ? '<span class="badge kind-mutation">consent</span>' : ''} ${s.idempotent ? '<span class="badge">idempotent</span>' : ''}</li>`).join('')}</ul></div>
            <div class="pb-section"><h4>Verifier</h4><div class="mono">${esc(p.verifier && p.verifier.tool)}(${esc(JSON.stringify(p.verifier && p.verifier.params))}) expects ${esc(JSON.stringify(p.verifier && p.verifier.expect))}</div></div>
          </div>
          <div>
            <div class="pb-section"><h4>Stop conditions</h4><ul>${(p.stop_conditions || []).map((m) => `<li>${esc(m)}</li>`).join('')}</ul></div>
            <div class="pb-section"><h4>Validation</h4>${problems.length ? `<ul>${problems.map((m) => `<li class="problem">${esc(m)}</li>`).join('')}</ul>` : '<span class="badge yes">passes all policy checks</span>'}
              ${(p.review_notes || []).length ? `<div class="hint">notes: ${p.review_notes.map(esc).join('; ')}</div>` : ''}</div>
            <div class="pb-section"><h4>History</h4><ul class="history">${(p.history || []).map((h) => `<li>${when(h.at)} ${badge(h.to)} by ${esc(h.by)} <span class="muted">${esc(h.note || '')}</span></li>`).join('')}</ul>
              ${p.previous_version_id ? `<div class="hint">previous version: <span class="mono">${esc(p.previous_version_id)}</span></div>` : ''}
              ${p.approved_at ? `<div class="hint">approved ${when(p.approved_at)} by ${esc(p.reviewer_id)}</div>` : ''}</div>
          </div>
        </div>
        <div class="pb-section"><h4>Provenance (${(p.provenance || []).length} trace events the candidate was built from)</h4><ol id="pb-prov" class="trace"></ol></div>
        <details class="pb-section"><summary class="hint">raw JSON</summary><pre>${json(p)}</pre></details>`;
      $$('button[data-act]', box).forEach((b) => b.addEventListener('click', () => guarded(b, async () => {
        const body = { reviewer_id: $('#pb-reviewer').value.trim() || 'reviewer-1', note: $('#pb-note').value.trim() || null };
        try {
          const env = await api('POST', `v1/playbooks/${p.id}/${b.dataset.act}`, body);
          toast('ok', b.dataset.act.toUpperCase(), `${env.data.name} v${env.data.version} is now ${env.data.status}`);
          await refreshReviewer();
        } catch (e) {
          const probs = e.env && e.env.data && e.env.data.problems;
          if (probs) toast('error', 'Validation problems', probs.join('; '));
        }
      })));
      $('#pb-edit-toggle').onclick = () => { const f = $('#pb-edit'); f.style.display = f.style.display === 'none' ? '' : 'none'; if (f.style.display !== 'none') renderEditForm(p); };
      state.editRenderedFor = null;
    }
    // Provenance can be rendered on every poll (no user input inside).
    const prov = (p.provenance || []).filter(Boolean);
    $('#pb-prov').innerHTML = prov.length ? prov.map((e) => `<li class="${e.success ? '' : 'fail'}"><div class="tr-head"><span class="badge actor-${esc(e.actor_type)}">${esc(e.actor_type)}</span><span class="tr-tool">${esc(e.tool_id)}</span><span class="badge ${e.success ? 'yes' : 'no'}">${e.success ? 'success' : 'failed'}</span><span class="muted mono">${esc(e.id)}</span><span class="tr-time">${when(e.timestamp)}</span></div>
      <div class="tr-body"><b>inputs</b><span class="mono">${compact(e.safe_inputs)}</span><b>output</b><span class="mono">${compact(e.safe_output)}</span>${e.before_state && e.after_state ? `<b>state</b><span>${diff(e.before_state, e.after_state)}</span>` : ''}</div></li>`).join('') : '<li class="muted" style="padding-left:10px">none</li>';
  }

  function renderEditForm(p) {
    if (state.editRenderedFor === p.id) return;
    state.editRenderedFor = p.id;
    const role = (p.prerequisites || []).find((q) => q.field === 'role');
    const roleNow = role ? (role.op === 'in' ? 'both' : role.value === 'analyst' ? 'analyst' : 'other') : 'none';
    const f = $('#pb-edit');
    f.innerHTML = `
      <div class="stack">
        <div><b>Edit</b> creates a new version (v${p.version + 1}) in REVIEW_PENDING; the current version is untouched until the new one is approved.</div>
        <label>Match examples (one per line)<textarea id="ed-examples">${esc((p.match_examples || []).join('\n'))}</textarea></label>
        <label>Role prerequisite
          <select id="ed-role">
            <option value="keep">keep as is (${esc(roleNow === 'both' ? 'analyst or admin' : roleNow === 'analyst' ? 'analyst only' : roleNow === 'none' ? 'no role prerequisite' : JSON.stringify(role.value))})</option>
            <option value="analyst">analyst only</option>
            <option value="both">analyst or admin</option>
          </select></label>
        <div class="actions"><button class="primary" id="ed-submit">Submit new version for review</button><button id="ed-cancel">Cancel</button></div>
      </div>`;
    $('#ed-cancel').onclick = () => { f.style.display = 'none'; };
    $('#ed-submit').onclick = (ev) => guarded(ev.currentTarget, async () => {
      const changes = {};
      const examples = $('#ed-examples').value.split('\n').map((s) => s.trim()).filter(Boolean);
      if (JSON.stringify(examples) !== JSON.stringify(p.match_examples || [])) changes.match_examples = examples;
      const roleChoice = $('#ed-role').value;
      if (roleChoice !== 'keep') {
        const entry = roleChoice === 'both' ? { field: 'role', op: 'in', value: ['analyst', 'admin'] } : { field: 'role', op: '==', value: 'analyst' };
        const others = (p.prerequisites || []).filter((q) => q.field !== 'role');
        const idx = (p.prerequisites || []).findIndex((q) => q.field === 'role');
        const prereqs = others.slice();
        prereqs.splice(idx < 0 ? others.length : idx, 0, entry);
        changes.prerequisites = prereqs;
      }
      if (!Object.keys(changes).length) { toast('error', 'Nothing changed', 'Edit the examples or the role prerequisite first.'); return; }
      try {
        const env = await api('POST', `v1/playbooks/${p.id}/edit`, { reviewer_id: $('#pb-reviewer').value.trim() || 'reviewer-1', changes });
        toast('ok', `HTTP ${env.http} ${env.code}`, `${env.message}: v${env.data.version}`);
        state.selectedPb = env.data.id;
        state.editRenderedFor = null;
        await refreshReviewer();
      } catch (e) { /* toast shown */ }
    });
  }

  // ======================================================================
  // TAB 4: AUDIT
  // ======================================================================
  function initAudit() {
    $('#btn-reset').onclick = (e) => guarded(e.currentTarget, () => doReset(false));
    $('#btn-reset-keep').onclick = (e) => guarded(e.currentTarget, () => doReset(true));
  }

  async function doReset(keep) {
    const msg = keep ? 'Reset accounts, cases, traces, executions and the audit log, but KEEP playbooks?' : 'Reset ALL demo data for this tenant, including playbooks?';
    if (!confirm(msg)) return;
    try {
      const env = await api('POST', 'v1/admin/reset' + (keep ? '?keep_playbooks=true' : ''));
      toast('ok', 'Reset done', `${env.data.accounts_seeded} accounts seeded; playbooks ${env.data.playbooks_kept ? 'kept' : 'cleared'}`);
      state.chat = []; renderChat();
      state.selectedCase = null; state.learnResult = null; state.toolsRenderedFor = null;
      if (!keep) state.selectedPb = null;
      await refresh(true);
    } catch (e) { /* toast shown */ }
  }

  async function refreshAudit() {
    const [sum, ex, au] = await Promise.all([
      api('GET', 'v1/summary', undefined, { quiet: true }),
      api('GET', 'v1/executions', undefined, { quiet: true }),
      api('GET', 'v1/audit?limit=200', undefined, { quiet: true }),
    ]);
    const s = sum.data || {};
    $('#summary-strip').innerHTML = ['account', 'case', 'event', 'playbook', 'execution', 'audit'].map((k) => `<div class="stat"><div class="n">${esc(s[k] == null ? '—' : s[k])}</div><div class="l">${esc(k)}s</div></div>`).join('');
    const exs = newestFirst(ex.data);
    $('#exec-count').textContent = exs.length ? `(${exs.length})` : '';
    $('#exec-table tbody').innerHTML = exs.length ? exs.map((x) => `<tr><td class="mono">${esc(x.id)}</td><td>${badge(x.status)}${x.replayed ? ' <span class="badge">replayed</span>' : ''}</td><td class="mono">${esc(x.case_id)}</td><td class="mono">${esc(x.playbook_id)} v${esc(x.playbook_version)}</td><td>${esc(x.principal_id)}</td><td class="mono">${esc((x.idempotency_key || '').slice(0, 8))}</td><td>${when(x.created_at)}<details><summary class="hint">result</summary><pre>${json(x.result)}</pre></details></td></tr>`).join('') : '<tr><td colspan="7" class="muted">No executions yet.</td></tr>';
    const aus = newestFirst(au.data);
    $('#audit-count').textContent = aus.length ? `(${aus.length})` : '';
    $('#audit-table tbody').innerHTML = aus.length ? aus.map((a) => `<tr><td>${when(a.timestamp)}</td><td>${esc(a.actor_id)}</td><td><b>${esc(a.action)}</b></td><td class="mono">${esc(a.subject_type)} ${esc(a.subject_id)}</td><td class="mono wrap">${compact(a.detail)}</td></tr>`).join('') : '<tr><td colspan="5" class="muted">Empty.</td></tr>';
  }

  // ---------- boot ----------
  function boot() {
    initSettings();
    initCustomer();
    initDesk();
    initReviewer();
    initAudit();
    initTabs();
    setInterval(() => refresh(false), 3000);
    fetch(url('health')).then((r) => setConn(r.ok)).catch(() => setConn(false));
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot); else boot();
})();
