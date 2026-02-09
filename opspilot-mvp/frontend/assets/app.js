/* OpsPilot MVP UI (vanilla JS) */

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => Array.from(document.querySelectorAll(sel));

const state = {
  apiBase: localStorage.getItem('opspilot_apiBase') || '',
  user: localStorage.getItem('opspilot_user') || 'operator',
  role: localStorage.getItem('opspilot_role') || 'operator',
  skill: 'patching_exclusion',
  selectedRun: null,
  runs: [],
};

function api(path){
  const base = state.apiBase.replace(/\/$/, '');
  return base + path;
}

async function request(path, options={}){
  const headers = Object.assign({
    'Content-Type': 'application/json',
    'X-User': state.user,
    'X-Role': state.role,
  }, options.headers || {});

  const res = await fetch(api(path), Object.assign({}, options, {headers}));
  const ct = res.headers.get('content-type') || '';
  let data = null;
  if(ct.includes('application/json')) data = await res.json();
  else data = await res.text();
  if(!res.ok) throw new Error(data?.detail || data || ('HTTP ' + res.status));
  return data;
}

function setTheme(theme){
  if(theme === 'light') document.documentElement.setAttribute('data-theme', 'light');
  else document.documentElement.removeAttribute('data-theme');
  localStorage.setItem('opspilot_theme', theme);
}

function initTheme(){
  const saved = localStorage.getItem('opspilot_theme');
  if(saved){
    setTheme(saved);
  } else {
    const prefersLight = window.matchMedia && window.matchMedia('(prefers-color-scheme: light)').matches;
    setTheme(prefersLight ? 'light' : 'dark');
  }
}

function toggleTheme(){
  const isLight = document.documentElement.getAttribute('data-theme') === 'light';
  setTheme(isLight ? 'dark' : 'light');
}

function badgeForStatus(status){
  const s = (status || '').toLowerCase();
  if(s.includes('succeed') || s.includes('dry_run')) return '<span class="badge good">' + status + '</span>';
  if(s.includes('pending')) return '<span class="badge warn">' + status + '</span>';
  if(s.includes('fail') || s.includes('reject')) return '<span class="badge bad">' + status + '</span>';
  return '<span class="badge">' + status + '</span>';
}

function badgeForRisk(risk){
  if(risk === 'high') return '<span class="badge bad">HIGH</span>';
  if(risk === 'medium') return '<span class="badge warn">MEDIUM</span>';
  return '<span class="badge good">LOW</span>';
}

function routeTo(route){
  $$('.nav-item').forEach(b => b.classList.toggle('active', b.dataset.route === route));
  $$('.view').forEach(v => v.classList.add('hidden'));
  $('#view-' + route).classList.remove('hidden');
}

async function refreshHealth(){
  try{
    const h = await request('/api/health', {method:'GET', headers: {'Content-Type': undefined}});
    $('#healthChip').textContent = h.gemini_configured ? 'Gemini: ON' : 'Gemini: OFF (stub)';
    $('#modelPill').textContent = 'Model: ' + (h.model || '—');
  }catch(e){
    $('#healthChip').textContent = 'Backend: OFF';
  }
}

async function refreshRuns(){
  const runs = await request('/api/runs', {method:'GET', headers: {'Content-Type': undefined}});
  state.runs = runs;

  // metrics
  $('#mTotal').textContent = runs.length;
  const pending = runs.filter(r => r.status === 'pending_approval').length;
  $('#mPending').textContent = pending;
  $('#mLast').textContent = runs[0]?.status || '—';

  // table
  const el = $('#runsTable');
  const head = `
    <div class="trow thead">
      <div>Run</div><div>Skill</div><div>Requested</div><div>Status</div>
    </div>`;

  const rows = runs.slice(0, 10).map(r => {
    return `
      <div class="trow" data-run="${r.run_id}">
        <div><strong>${r.run_id}</strong><div class="muted" style="font-size:12px">${r.environment} • ${new Date(r.created_at).toLocaleString()}</div></div>
        <div>${r.plan?.intent?.skill || '—'}<div class="muted" style="font-size:12px">${(r.plan?.intent?.summary||'').slice(0,42)}${(r.plan?.intent?.summary||'').length>42?'…':''}</div></div>
        <div>${r.requested_by}<div class="muted" style="font-size:12px">${r.role}</div></div>
        <div>${badgeForStatus(r.status)}</div>
      </div>`;
  }).join('');

  el.innerHTML = head + (rows || '<div class="empty">No runs yet. Click “New Run”.</div>');

  $$('#runsTable .trow[data-run]').forEach(row => {
    row.addEventListener('click', () => openRun(row.dataset.run));
  });
}

function setSkill(skill){
  state.skill = skill;
  $$('.seg').forEach(b => b.classList.toggle('active', b.dataset.skill === skill));
}

function fillExample(){
  const samples = {
    patching_exclusion: 'Exclude servers web-01, web-02 from the Feb patch window. Reason: app release freeze. Change ID: CHG123456',
    storage_ops: 'Mount volume vol-1a2b at /data on host app-01. Verify filesystem and app health before and after. In prod requires approval.',
    manageengine_downtime: 'Schedule downtime for monitors PAYMENTS-API and PAYMENTS-DB from 2026-02-10 01:00 to 03:00 IST. Reason: maintenance. CHG123456',
    vuln_triage: 'Segment latest Tenable export by team (Wintel/Linux/App) and prioritize critical exploitable findings. Propose ticket titles and owners.',
    solarwinds_event: 'IP SLA indicates primary circuit DOWN at Pune-DC for device core-sw-01. Trigger AWX failover check and notify site DL.',
  };
  $('#message').value = samples[state.skill] || samples.patching_exclusion;
}

function renderPlan(run){
  if(!run?.plan) return;
  const risk = run.plan.intent.risk;
  $('#riskPill').textContent = 'Risk: ' + risk.toUpperCase();

  const steps = run.plan.steps.map(s => `
    <div class="step">
      <div style="display:flex; justify-content:space-between; gap:10px; align-items:center">
        <h3>${s.id} • ${s.title}</h3>
        ${badgeForRisk(run.plan.intent.risk)}
      </div>
      <p>${s.action}</p>
      <div class="meta">
        <span class="pill">tool: ${s.tool}</span>
        <span class="pill">safe: ${s.safe ? 'yes' : 'no'}</span>
      </div>
    </div>
  `).join('');

  const header = `
    <div class="step" style="border-style:solid">
      <h3>${run.plan.intent.skill} • ${run.plan.intent.summary}</h3>
      <p>${run.approval_required ? 'Approval required before execution.' : 'No approval required. Dry-run executes automatically.'}</p>
      <div class="meta">
        <span class="pill">requested by: ${run.requested_by}</span>
        <span class="pill">env: ${run.environment}</span>
        <span class="pill">status: ${run.status}</span>
      </div>
    </div>`;

  $('#planPreview').innerHTML = header + steps;
}

async function generatePlan(){
  const payload = {
    message: $('#message').value.trim(),
    skill_hint: state.skill,
    environment: $('#envSelect').value,
    change_id: $('#changeId').value.trim() || null,
    extra: {},
  };
  if(!payload.message) return;
  $('#runNow').disabled = true;
  $('#runNow').textContent = 'Working…';

  try{
    const data = await request('/api/chat', {method:'POST', body: JSON.stringify(payload)});
    renderPlan(data.run);
    state.selectedRun = data.run.run_id;
    await refreshRuns();
    // show details in artifacts view too
    openRun(data.run.run_id);
  }catch(e){
    alert(e.message);
  }finally{
    $('#runNow').disabled = false;
    $('#runNow').textContent = 'Generate plan';
  }
}

async function openRun(runId){
  state.selectedRun = runId;
  routeTo('artifacts');

  const run = await request('/api/runs/' + runId, {method:'GET', headers: {'Content-Type': undefined}});
  $('#detailStatus').textContent = run.status;

  $('#runDetails').classList.remove('empty');
  $('#runDetails').innerHTML = `
    <h3>Run ${run.run_id}</h3>
    <div class="kv"><div>Skill</div><div>${run.plan.intent.skill}</div></div>
    <div class="kv"><div>Summary</div><div>${run.plan.intent.summary}</div></div>
    <div class="kv"><div>Risk</div><div>${run.plan.intent.risk}</div></div>
    <div class="kv"><div>Approval</div><div>${run.approval_required ? 'required' : 'not required'}</div></div>
    <div class="kv"><div>Requested by</div><div>${run.requested_by} (${run.role})</div></div>
    <div class="kv"><div>Environment</div><div>${run.environment}</div></div>
    <div class="kv"><div>Created</div><div>${new Date(run.created_at).toLocaleString()}</div></div>
    <div class="kv"><div>Status</div><div>${badgeForStatus(run.status)}</div></div>
  `;

  $('#evidenceBox').textContent = JSON.stringify(run.evidence || [], null, 2);
}

async function refreshApprovals(){
  const list = $('#approvalList');
  const runs = await request('/api/runs', {method:'GET', headers: {'Content-Type': undefined}});
  const pending = runs.filter(r => r.status === 'pending_approval');

  if(!pending.length){
    list.innerHTML = '<div class="empty">No pending approvals 🎉</div>';
    return;
  }

  list.innerHTML = pending.map(r => `
    <div class="item" data-run="${r.run_id}">
      <div class="item-top">
        <div>
          <div class="item-title">${r.plan.intent.skill} • ${r.run_id}</div>
          <div class="item-sub">${r.plan.intent.summary} — <strong>${r.plan.intent.risk.toUpperCase()}</strong> risk</div>
          <div class="item-sub">Requested by ${r.requested_by} (${r.role}) • env ${r.environment}</div>
        </div>
        <div>${badgeForStatus(r.status)}</div>
      </div>
      <div class="item-actions">
        <button class="secondary" data-action="view">View</button>
        <button class="primary" data-action="approve">Approve</button>
        <button class="ghost" data-action="reject">Reject</button>
      </div>
    </div>
  `).join('');

  $$('#approvalList .item').forEach(el => {
    const runId = el.dataset.run;
    el.querySelector('[data-action="view"]').addEventListener('click', () => openRun(runId));
    el.querySelector('[data-action="approve"]').addEventListener('click', () => decide(runId, 'approved'));
    el.querySelector('[data-action="reject"]').addEventListener('click', () => decide(runId, 'rejected'));
  });
}

async function decide(runId, decision){
  const comment = prompt(`Add a comment for ${decision} (optional):`) || null;
  try{
    await request('/api/runs/' + runId + '/approve', {method:'POST', body: JSON.stringify({decision, comment})});
    await refreshApprovals();
    await refreshRuns();
    openRun(runId);
  }catch(e){
    alert(e.message);
  }
}

async function simulateSolarWinds(){
  const payload = {
    site: 'Pune-DC',
    device: 'core-sw-01',
    state: 'PRIMARY_DOWN',
    circuit: 'ISP-A',
    change_id: $('#changeId').value.trim() || null,
  };
  try{
    const res = await request('/api/solarwinds/webhook', {method:'POST', body: JSON.stringify(payload)});
    await refreshRuns();
    openRun(res.run_id);
  }catch(e){
    alert(e.message);
  }
}

function initNav(){
  $$('.nav-item').forEach(btn => {
    btn.addEventListener('click', () => routeTo(btn.dataset.route));
  });
}

function initLauncher(){
  $$('.seg').forEach(btn => {
    btn.addEventListener('click', () => setSkill(btn.dataset.skill));
  });

  $('#fillExample').addEventListener('click', fillExample);
  $('#runNow').addEventListener('click', generatePlan);

  // quick actions
  $$('.quick-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      setSkill(btn.dataset.skill);
      routeTo('run');
      fillExample();
    });
  });

  // upload
  $('#uploadBtn').addEventListener('click', () => $('#fileInput').click());
  $('#fileInput').addEventListener('change', async () => {
    const f = $('#fileInput').files[0];
    if(!f) return;
    $('#uploadMeta').textContent = f.name;
    const fd = new FormData();
    fd.append('file', f);

    try{
      const res = await fetch(api('/api/vuln/upload'), {
        method: 'POST',
        headers: {
          'X-User': state.user,
          'X-Role': state.role,
        },
        body: fd,
      });
      const data = await res.json();
      if(!res.ok) throw new Error(data?.detail || 'Upload failed');
      await refreshRuns();
      openRun(data.run_id);
    }catch(e){
      alert(e.message);
    }
  });
}

function initTopbar(){
  $('#newRunBtn').addEventListener('click', () => routeTo('run'));
  $('#ctaRun').addEventListener('click', () => routeTo('run'));
  $('#ctaDemoEvent').addEventListener('click', simulateSolarWinds);
  $('#refreshRuns').addEventListener('click', refreshRuns);
  $('#refreshApprovals').addEventListener('click', refreshApprovals);

  // quick search: just filter recent list and open first match
  $('#quickSearch').addEventListener('keydown', (e) => {
    if(e.key === 'Enter'){
      const q = e.target.value.toLowerCase();
      const hit = state.runs.find(r =>
        r.run_id.toLowerCase().includes(q) ||
        (r.plan?.intent?.skill || '').toLowerCase().includes(q) ||
        (r.message || '').toLowerCase().includes(q)
      );
      if(hit) openRun(hit.run_id);
    }
  });
}

function initSettings(){
  $('#apiBase').value = state.apiBase;
  $('#setUser').value = state.user;
  $('#setRole').value = state.role;

  $('#saveSettings').addEventListener('click', () => {
    state.apiBase = $('#apiBase').value.trim();
    state.user = $('#setUser').value.trim() || 'operator';
    state.role = $('#setRole').value;

    localStorage.setItem('opspilot_apiBase', state.apiBase);
    localStorage.setItem('opspilot_user', state.user);
    localStorage.setItem('opspilot_role', state.role);

    updateUserCard();
    refreshHealth();
    refreshRuns();
    alert('Saved ✅');
  });

  $('#resetSettings').addEventListener('click', () => {
    localStorage.removeItem('opspilot_apiBase');
    localStorage.removeItem('opspilot_user');
    localStorage.removeItem('opspilot_role');
    location.reload();
  });
}

function updateUserCard(){
  $('#userName').textContent = state.user;
  $('#userRole').textContent = state.role;
  $('#avatar').textContent = (state.user[0] || 'U').toUpperCase();
}

function initModal(){
  const modal = $('#modal');
  const openBtn = $('#switchUserBtn');
  const closeBtn = $('#modalClose');
  const cancelBtn = $('#modalCancel');
  const saveBtn = $('#modalSave');
  const userInput = $('#modalUser');
  const roleSelect = $('#modalRole');

  // If any modal element is missing, don't crash the whole app
  if(!modal || !openBtn || !closeBtn || !cancelBtn || !saveBtn || !userInput || !roleSelect){
    console.warn('[OpsPilot] Modal elements missing. Check IDs in index.html.');
    return;
  }

  const open = (e) => {
    if(e){ e.preventDefault(); e.stopPropagation(); }
    userInput.value = state.user;
    roleSelect.value = state.role;
    modal.classList.remove('hidden');
    document.body.classList.add('modal-open');
    userInput.focus();
  };

  const close = (e) => {
    if(e){ e.preventDefault(); e.stopPropagation(); }
    modal.classList.add('hidden');
    document.body.classList.remove('modal-open');
  };

  openBtn.addEventListener('click', open);
  closeBtn.addEventListener('click', close);
  cancelBtn.addEventListener('click', close);

  saveBtn.addEventListener('click', (e) => {
    e.preventDefault();
    e.stopPropagation();

    state.user = userInput.value.trim() || 'operator';
    state.role = roleSelect.value;

    localStorage.setItem('opspilot_user', state.user);
    localStorage.setItem('opspilot_role', state.role);

    updateUserCard();
    close();
    refreshRuns();
    refreshApprovals();
  });

  // Close when clicking outside the card (overlay click)
  modal.addEventListener('click', (e) => {
    const card = e.target.closest('.modal-card');
    if(!card) close(e);
  });

  // ESC closes modal
  window.addEventListener('keydown', (e) => {
    if(e.key === 'Escape' && !modal.classList.contains('hidden')){
      close(e);
    }
  });
}

function initThemeToggle(){
  $('#themeToggle').addEventListener('click', toggleTheme);
}

async function boot(){
  initTheme();
  initNav();
  initLauncher();
  initTopbar();
  initSettings();
  initModal();
  initThemeToggle();
  updateUserCard();

  setSkill(state.skill);
  routeTo('dashboard');

  await refreshHealth();
  await refreshRuns();
  await refreshApprovals();
}

window.addEventListener('DOMContentLoaded', () => {
  boot();
});
