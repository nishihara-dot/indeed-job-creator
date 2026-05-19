'use strict';

// ──────────────────────────────────────────────
// State
// ──────────────────────────────────────────────
let generatedData = null;   // last AI-generated job (not yet saved)
let jobs = [];              // list from server
let selectedIds = new Set();

// ──────────────────────────────────────────────
// Tabs
// ──────────────────────────────────────────────
document.querySelectorAll('.tab-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
    btn.classList.add('active');
    document.getElementById('tab-' + btn.dataset.tab).classList.add('active');
    if (btn.dataset.tab === 'list') loadJobs();
  });
});

// ──────────────────────────────────────────────
// Extra fields toggle
// ──────────────────────────────────────────────
function toggleExtra(btn) {
  const fields = document.getElementById('extra-fields');
  fields.classList.toggle('open');
  btn.textContent = fields.classList.contains('open')
    ? '− 追加情報を閉じる'
    : '＋ 追加情報を入力する（応募先URL・担当者情報など）';
}

// ──────────────────────────────────────────────
// Persona preset toggle
// ──────────────────────────────────────────────
function onPersonaChange(sel) {
  const custom = document.getElementById('target_persona_custom');
  custom.style.display = sel.value === 'custom' ? 'block' : 'none';
}

function getTargetPersona() {
  const sel = document.getElementById('target_persona_preset');
  if (!sel) return '';

  const parts = [];
  const preset = sel.value === 'custom' ? val('target_persona_custom') : sel.value;
  if (preset) parts.push(preset);

  const age = val('target_age');
  if (age) parts.push(`想定年齢：${age}`);

  const exp = val('target_experience');
  if (exp) parts.push(`前職・経験：${exp}`);

  return parts.join('／');
}

// ──────────────────────────────────────────────
// File upload → extract text
// ──────────────────────────────────────────────
async function handleFileUpload(input) {
  const file = input.files[0];
  if (!file) return;

  const status = document.getElementById('file-upload-status');
  status.textContent = '読み込み中...';
  status.className = 'file-upload-status loading';

  const form = new FormData();
  form.append('file', file);

  try {
    const res = await fetch('/api/extract-text', { method: 'POST', body: form });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'エラーが発生しました');
    }
    const data = await res.json();
    const ta = document.getElementById('request_text');
    ta.value = ta.value ? ta.value + '\n\n' + data.text : data.text;
    status.textContent = `✓ ${file.name} を読み込みました`;
    status.className = 'file-upload-status success';
  } catch (e) {
    status.textContent = '✕ ' + e.message;
    status.className = 'file-upload-status error';
  }

  input.value = '';
}

// ──────────────────────────────────────────────
// Generate
// ──────────────────────────────────────────────
async function generateJob() {
  const url = document.getElementById('company_url').value.trim();
  const text = document.getElementById('request_text').value.trim();

  if (!url) { toast('企業URLを入力してください', 'error'); return; }
  if (!url.startsWith('http')) { toast('URLはhttp/httpsで始めてください', 'error'); return; }
  if (!text) { toast('採用依頼文を入力してください', 'error'); return; }

  const btn = document.getElementById('generate-btn');
  btn.classList.add('loading');
  btn.disabled = true;

  try {
    const res = await fetch('/api/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        company_url: url,
        request_text: text,
        application_url: document.getElementById('application_url').value.trim(),
        contact_name: document.getElementById('contact_name').value.trim(),
        contact_phone: document.getElementById('contact_phone').value.trim(),
        contact_email: document.getElementById('contact_email').value.trim(),
        target_persona: getTargetPersona(),
      }),
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'エラーが発生しました');
    }
    generatedData = await res.json();
    fillPreview(generatedData);
    toast('求人票を生成しました！内容を確認・編集して保存してください', 'success');
  } catch (e) {
    toast('生成に失敗しました: ' + e.message, 'error');
  } finally {
    btn.classList.remove('loading');
    btn.disabled = false;
  }
}

// ──────────────────────────────────────────────
// Fill preview fields
// ──────────────────────────────────────────────
function fillPreview(data) {
  const fields = [
    'job_title', 'company_name', 'prefecture', 'city',
    'employment_type', 'salary_type',
    'description', 'requirements', 'preferred_skills',
    'working_hours', 'holidays', 'benefits', 'selection_process', 'contact_email',
  ];
  fields.forEach(f => {
    const el = document.getElementById('p_' + f);
    if (el) el.value = data[f] || '';
  });
  setVal('p_salary_min', data.salary_min || '');
  setVal('p_salary_max', data.salary_max || '');
  setVal('p_hire_count', data.hire_count || '');

  // appeal points
  const tagsEl = document.getElementById('p_appeal_tags');
  tagsEl.innerHTML = '';
  let pts = data.appeal_points;
  if (typeof pts === 'string') {
    try { pts = JSON.parse(pts); } catch { pts = [pts]; }
  }
  if (Array.isArray(pts)) {
    pts.forEach(pt => {
      const tag = document.createElement('span');
      tag.className = 'appeal-tag';
      tag.textContent = pt;
      tagsEl.appendChild(tag);
    });
  }

  document.getElementById('preview-empty').style.display = 'none';
  document.getElementById('preview-form').style.display = 'block';
  document.getElementById('preview-card').scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function clearPreview() {
  generatedData = null;
  document.getElementById('preview-empty').style.display = 'block';
  document.getElementById('preview-form').style.display = 'none';
}

// ──────────────────────────────────────────────
// Save (create new)
// ──────────────────────────────────────────────
async function saveJob() {
  const payload = collectPreviewForm();
  if (!payload.job_title) { toast('求人タイトルを入力してください', 'error'); return; }
  if (!payload.company_name) { toast('会社名を入力してください', 'error'); return; }

  // carry over fields not in preview form
  if (generatedData) {
    payload.company_url = payload.company_url || generatedData.company_url;
    payload.application_url = payload.application_url || generatedData.application_url;
    payload.contact_name = payload.contact_name || generatedData.contact_name;
    payload.contact_phone = payload.contact_phone || generatedData.contact_phone;
    payload.original_request = generatedData.original_request;
    payload.appeal_points = generatedData.appeal_points;
  }

  try {
    const res = await fetch('/api/jobs', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw new Error((await res.json()).detail);
    toast('求人を保存しました', 'success');
    clearPreview();
  } catch (e) {
    toast('保存に失敗しました: ' + e.message, 'error');
  }
}

function collectPreviewForm() {
  return {
    job_title: val('p_job_title'),
    company_name: val('p_company_name'),
    prefecture: val('p_prefecture'),
    city: val('p_city'),
    employment_type: val('p_employment_type'),
    salary_min: intOrNull('p_salary_min'),
    salary_max: intOrNull('p_salary_max'),
    salary_type: val('p_salary_type'),
    description: val('p_description'),
    requirements: val('p_requirements'),
    preferred_skills: val('p_preferred_skills'),
    working_hours: val('p_working_hours'),
    holidays: val('p_holidays'),
    benefits: val('p_benefits'),
    selection_process: val('p_selection_process'),
    hire_count: intOrNull('p_hire_count'),
    contact_email: val('p_contact_email'),
  };
}

// ──────────────────────────────────────────────
// Load job list
// ──────────────────────────────────────────────
async function loadJobs() {
  try {
    const res = await fetch('/api/jobs');
    jobs = await res.json();
    renderJobs();
  } catch (e) {
    toast('求人一覧の取得に失敗しました', 'error');
  }
}

function renderJobs() {
  const tbody = document.getElementById('jobs-tbody');
  const empty = document.getElementById('jobs-empty');
  selectedIds = new Set();
  updateSelectionUI();

  if (jobs.length === 0) {
    tbody.innerHTML = '';
    empty.style.display = 'block';
    return;
  }
  empty.style.display = 'none';

  tbody.innerHTML = jobs.map(j => {
    const loc = [j.prefecture, j.city].filter(Boolean).join('');
    const salary = formatSalary(j.salary_min, j.salary_max, j.salary_type);
    const typeTag = employmentTag(j.employment_type);
    const date = j.created_at ? j.created_at.slice(0, 10) : '';
    return `<tr id="row-${j.id}">
      <td><input type="checkbox" class="row-check" data-id="${j.id}" onchange="onRowCheck(this)"></td>
      <td><strong>${esc(j.job_title || '')}</strong></td>
      <td>${esc(j.company_name || '')}</td>
      <td>${esc(loc)}</td>
      <td>${typeTag}</td>
      <td>${salary}</td>
      <td>${date}</td>
      <td>
        <button class="btn btn-outline btn-sm" onclick="openEdit(${j.id})">編集</button>
        <button class="btn btn-secondary btn-sm" style="margin-left:4px" onclick="duplicateJob(${j.id})">複製</button>
        <button class="btn btn-danger btn-sm" style="margin-left:4px" onclick="deleteJob(${j.id})">削除</button>
      </td>
    </tr>`;
  }).join('');
}

function formatSalary(min, max, type) {
  if (!min && !max) return '<span class="tag tag-gray">要相談</span>';
  const unit = type || '月給';
  const fmt = n => n ? Number(n).toLocaleString() : '';
  const range = [fmt(min), fmt(max)].filter(Boolean).join('〜');
  return `${range}円（${unit}）`;
}

function employmentTag(type) {
  const map = {
    '正社員': 'tag-blue',
    '契約社員': 'tag-purple',
    'パート・アルバイト': 'tag-orange',
    '派遣社員': 'tag-green',
    '業務委託': 'tag-gray',
  };
  const cls = map[type] || 'tag-gray';
  return `<span class="tag ${cls}">${esc(type || '')}</span>`;
}

// ──────────────────────────────────────────────
// Selection
// ──────────────────────────────────────────────
function onRowCheck(el) {
  const id = parseInt(el.dataset.id);
  if (el.checked) selectedIds.add(id);
  else selectedIds.delete(id);
  document.getElementById('row-' + id).classList.toggle('selected', el.checked);
  updateSelectionUI();
}

function onCheckAll() {
  const checked = document.getElementById('check-all').checked;
  document.querySelectorAll('.row-check').forEach(cb => {
    cb.checked = checked;
    const id = parseInt(cb.dataset.id);
    if (checked) selectedIds.add(id);
    else selectedIds.delete(id);
    document.getElementById('row-' + id).classList.toggle('selected', checked);
  });
  updateSelectionUI();
}

function toggleSelectAll() {
  const allChecked = selectedIds.size === jobs.length && jobs.length > 0;
  document.getElementById('check-all').checked = !allChecked;
  onCheckAll();
}

function updateSelectionUI() {
  const n = selectedIds.size;
  document.getElementById('selected-count').textContent = `${n}件選択中`;
  document.getElementById('export-btn').disabled = n === 0;
  document.getElementById('delete-bulk-btn').disabled = n === 0;
}

// ──────────────────────────────────────────────
// Export CSV
// ──────────────────────────────────────────────
async function exportSelected() {
  if (selectedIds.size === 0) return;
  try {
    const res = await fetch('/api/export', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ job_ids: Array.from(selectedIds) }),
    });
    if (!res.ok) throw new Error((await res.json()).detail);
    const blob = await res.blob();
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = `indeed_jobs_${dateStr()}.csv`;
    a.click();
    URL.revokeObjectURL(a.href);
    toast(`${selectedIds.size}件の求人をエクスポートしました`, 'success');
  } catch (e) {
    toast('エクスポートに失敗しました: ' + e.message, 'error');
  }
}

// ──────────────────────────────────────────────
// Delete
// ──────────────────────────────────────────────
async function deleteJob(id) {
  if (!confirm('この求人を削除しますか？')) return;
  try {
    const res = await fetch(`/api/jobs/${id}`, { method: 'DELETE' });
    if (!res.ok) throw new Error((await res.json()).detail);
    jobs = jobs.filter(j => j.id !== id);
    selectedIds.delete(id);
    renderJobs();
    toast('削除しました', 'success');
  } catch (e) {
    toast('削除に失敗しました: ' + e.message, 'error');
  }
}

async function deleteSelected() {
  if (selectedIds.size === 0) return;
  if (!confirm(`選択中の${selectedIds.size}件を削除しますか？`)) return;
  const ids = Array.from(selectedIds);
  let ok = 0;
  for (const id of ids) {
    try {
      await fetch(`/api/jobs/${id}`, { method: 'DELETE' });
      ok++;
    } catch {}
  }
  await loadJobs();
  toast(`${ok}件削除しました`, 'success');
}

// ──────────────────────────────────────────────
// Duplicate
// ──────────────────────────────────────────────
async function duplicateJob(id) {
  const job = jobs.find(j => j.id === id);
  if (!job) return;

  const payload = {
    company_name: job.company_name,
    company_url: job.company_url,
    job_title: job.job_title + '（コピー）',
    prefecture: job.prefecture,
    city: job.city,
    employment_type: job.employment_type,
    salary_min: job.salary_min,
    salary_max: job.salary_max,
    salary_type: job.salary_type,
    description: job.description,
    requirements: job.requirements,
    preferred_skills: job.preferred_skills,
    working_hours: job.working_hours,
    holidays: job.holidays,
    benefits: job.benefits,
    selection_process: job.selection_process,
    hire_count: job.hire_count,
    appeal_points: job.appeal_points,
    application_url: job.application_url,
    contact_name: job.contact_name,
    contact_phone: job.contact_phone,
    contact_email: job.contact_email,
    original_request: job.original_request,
  };

  try {
    const res = await fetch('/api/jobs', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw new Error((await res.json()).detail);
    await loadJobs();
    toast(`「${job.job_title}」を複製しました`, 'success');
  } catch (e) {
    toast('複製に失敗しました: ' + e.message, 'error');
  }
}

// ──────────────────────────────────────────────
// Regenerate in modal
// ──────────────────────────────────────────────
async function regenerateInModal() {
  const companyUrl = val('m_company_url');
  const originalRequest = val('m_original_request');

  if (!companyUrl) {
    toast('「AI再生成用の情報」を展開して企業URLを入力してください', 'error');
    return;
  }
  if (!originalRequest) {
    toast('「AI再生成用の情報」を展開して採用依頼文を入力してください', 'error');
    return;
  }

  const btn = document.getElementById('regen-btn');
  btn.classList.add('loading');
  btn.disabled = true;

  try {
    const res = await fetch('/api/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        company_url: companyUrl,
        request_text: originalRequest,
        application_url: val('m_application_url'),
        contact_name: '',
        contact_phone: '',
        contact_email: val('m_contact_email'),
      }),
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'エラーが発生しました');
    }
    const data = await res.json();

    const fields = [
      'job_title', 'company_name', 'prefecture', 'city',
      'employment_type', 'salary_type',
      'description', 'requirements', 'preferred_skills',
      'working_hours', 'holidays', 'benefits', 'selection_process',
    ];
    fields.forEach(f => setVal('m_' + f, data[f] || ''));
    setVal('m_salary_min', data.salary_min || '');
    setVal('m_salary_max', data.salary_max || '');

    toast('再生成しました。内容を確認して保存してください', 'success');
  } catch (e) {
    toast('再生成に失敗しました: ' + e.message, 'error');
  } finally {
    btn.classList.remove('loading');
    btn.disabled = false;
  }
}

// ──────────────────────────────────────────────
// Edit modal
// ──────────────────────────────────────────────
function openEdit(id) {
  const job = jobs.find(j => j.id === id);
  if (!job) return;

  setVal('m_id', job.id);
  setVal('m_company_url', job.company_url || '');
  setVal('m_original_request', job.original_request || '');
  const fields = [
    'job_title', 'company_name', 'prefecture', 'city',
    'employment_type', 'salary_type',
    'description', 'requirements', 'preferred_skills',
    'working_hours', 'holidays', 'benefits', 'selection_process',
    'contact_email', 'application_url',
  ];
  fields.forEach(f => setVal('m_' + f, job[f] || ''));
  setVal('m_salary_min', job.salary_min || '');
  setVal('m_salary_max', job.salary_max || '');
  setVal('m_hire_count', job.hire_count || '');

  document.getElementById('edit-modal').classList.add('open');
}

function closeModal() {
  document.getElementById('edit-modal').classList.remove('open');
}

async function saveEdit() {
  const id = parseInt(val('m_id'));
  const payload = {
    job_title: val('m_job_title'),
    company_name: val('m_company_name'),
    prefecture: val('m_prefecture'),
    city: val('m_city'),
    employment_type: val('m_employment_type'),
    salary_min: intOrNull('m_salary_min'),
    salary_max: intOrNull('m_salary_max'),
    salary_type: val('m_salary_type'),
    description: val('m_description'),
    requirements: val('m_requirements'),
    preferred_skills: val('m_preferred_skills'),
    working_hours: val('m_working_hours'),
    holidays: val('m_holidays'),
    benefits: val('m_benefits'),
    selection_process: val('m_selection_process'),
    hire_count: intOrNull('m_hire_count'),
    contact_email: val('m_contact_email'),
    application_url: val('m_application_url'),
  };

  try {
    const res = await fetch(`/api/jobs/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw new Error((await res.json()).detail);
    closeModal();
    await loadJobs();
    toast('更新しました', 'success');
  } catch (e) {
    toast('更新に失敗しました: ' + e.message, 'error');
  }
}

// close modal on backdrop click
document.getElementById('edit-modal').addEventListener('click', function(e) {
  if (e.target === this) closeModal();
});

// ──────────────────────────────────────────────
// Toast notifications
// ──────────────────────────────────────────────
function toast(msg, type = 'info') {
  const icons = { success: '✓', error: '✕', info: 'ℹ' };
  const container = document.getElementById('toasts');
  const el = document.createElement('div');
  el.className = `toast toast-${type}`;
  el.innerHTML = `<span>${icons[type] || 'ℹ'}</span><span>${esc(msg)}</span>`;
  container.appendChild(el);
  setTimeout(() => {
    el.classList.add('out');
    setTimeout(() => el.remove(), 300);
  }, 3500);
}

// ──────────────────────────────────────────────
// Utilities
// ──────────────────────────────────────────────
function val(id) {
  const el = document.getElementById(id);
  return el ? el.value.trim() : '';
}
function setVal(id, v) {
  const el = document.getElementById(id);
  if (el) el.value = v ?? '';
}
function intOrNull(id) {
  const v = val(id);
  return v ? parseInt(v) : null;
}
function esc(s) {
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}
function dateStr() {
  return new Date().toISOString().slice(0, 10).replace(/-/g, '');
}

// ──────────────────────────────────────────────
// Init
// ──────────────────────────────────────────────
loadJobs();
