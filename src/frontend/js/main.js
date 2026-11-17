// ChatLayout: state, persistence and wiring. Components only render HTML; all actions are handled here.
import { api } from './api.js';
import { conversationStore, settingsStore } from './store.js';
import { uid, now, esc, debounce, pageOf } from './util.js';
import { icon } from './icons.js';
import { renderSidebar } from './ui/sidebar.js';
import { renderChat } from './ui/chat.js';
import { renderConfig } from './ui/config.js';
import { renderEvidence } from './ui/evidence.js';
import { renderTrace } from './ui/trace.js';
import { PdfViewer } from './ui/pdfviewer.js';

const $ = (s) => document.querySelector(s);
const els = {
  app: $('#app'), sidebar: $('#sidebar'), chat: $('#chat'), config: $('#config'), form: $('#composer'),
  input: $('#input'), send: $('#send'), inspector: $('#inspector'), title: $('#conv-title'), health: $('#health'),
  pdf: $('#pdf'), toast: $('#toast'),
};

const state = {
  server: null, serverError: null, settings: null, conversations: [], activeId: null, selectedMsgId: null,
  query: '', editingId: null, configOpen: false, tab: 'evidence', inflight: null,
};
let pdf = null;

// ------------------------------------------------------------------ settings
const NUM_KEYS = ['top_k', 'budget_chars', 'max_new_per_search', 'max_book_searches', 'max_steps'];
const PRESET_KEYS = ['retriever', ...NUM_KEYS, 'external_tools'];

function defaultSettings(server) {
  const presetName = server?.presets?.hybrid_b2400 ? 'hybrid_b2400' : '';
  const d = (presetName && server.presets[presetName]) || server?.defaults || {};
  return {
    preset: presetName, retriever: d.retriever || 'dense', top_k: d.top_k ?? 3, budget_chars: d.budget_chars ?? 800,
    max_new_per_search: d.max_new_per_search ?? 3, max_book_searches: d.max_book_searches ?? 3, max_steps: d.max_steps ?? 6,
    external_tools: d.external_tools ?? true, provider: server?.default_provider || 'openrouter', model: '', chapter_no: '',
  };
}

function sanitizeSettings(s, server) {
  const out = { ...defaultSettings(server), ...(s || {}) };
  if (server) {
    if (!server.retrievers.some((r) => r.id === out.retriever)) out.retriever = defaultSettings(server).retriever;
    const p = server.providers.find((x) => x.id === out.provider);
    if (!p || !p.available) out.provider = server.default_provider;
    for (const k of NUM_KEYS) {
      const [lo, hi] = server.limits[k];
      out[k] = Math.min(hi, Math.max(lo, Number(out[k]) || lo));
    }
    if (out.chapter_no && !server.chapters.some((c) => c.chapter_no === out.chapter_no)) out.chapter_no = '';
  }
  return out;
}

function updateSetting(key, value) {
  const s = { ...state.settings };
  if (key === 'preset') {
    s.preset = value;
    if (value && state.server.presets[value]) for (const k of PRESET_KEYS) s[k] = state.server.presets[value][k];
  } else {
    s[key] = key === 'external_tools' ? Boolean(value) : NUM_KEYS.includes(key) ? Number(value) : value;
    if (PRESET_KEYS.includes(key)) s.preset = '';
    if (key === 'provider') s.model = '';
  }
  state.settings = sanitizeSettings(s, state.server);
  settingsStore.save(state.settings);
  renderConfigPanel();
}

function requestFromSettings(question) {
  const s = state.settings;
  return {
    question, provider: s.provider, model: s.model || null,
    config: { preset: s.preset || null, retriever: s.retriever, top_k: s.top_k, budget_chars: s.budget_chars,
      max_new_per_search: s.max_new_per_search, max_book_searches: s.max_book_searches, max_steps: s.max_steps,
      external_tools: s.external_tools },
    filters: s.chapter_no ? { chapter_no: s.chapter_no } : null,
  };
}

// ------------------------------------------------------------------ conversations
const active = () => state.conversations.find((c) => c.id === state.activeId) || null;
const findMsg = (id) => {
  for (const c of state.conversations) { const m = c.messages.find((x) => x.id === id); if (m) return [c, m]; }
  return [null, null];
};

async function save(conv) {
  conv.updated_at = now();
  state.conversations.sort((a, b) => b.updated_at.localeCompare(a.updated_at));
  try { await conversationStore.put(conv); } catch (e) { toast(`Không lưu được lịch sử: ${e.message}`); }
}

function selectConv(id) {
  state.activeId = id;
  const c = active();
  const last = c && [...c.messages].reverse().find((m) => m.role === 'assistant');
  state.selectedMsgId = last ? last.id : null;
  closeDrawers();
  renderAll();
}

async function deleteConv(id) {
  const c = state.conversations.find((x) => x.id === id);
  if (!c || !confirm(`Xoá cuộc trò chuyện “${c.title}”? Không thể hoàn tác.`)) return;
  if (state.inflight && c.messages.some((m) => m.id === state.inflight.msgId)) state.inflight.controller.abort();
  state.conversations = state.conversations.filter((x) => x.id !== id);
  await conversationStore.remove(id).catch(() => {});
  if (state.activeId === id) selectConv(state.conversations[0]?.id || null);
  else renderSidebarPanel();
}

async function finishRename(id, title) {
  const c = state.conversations.find((x) => x.id === id);
  state.editingId = null;
  if (c && title.trim() && title.trim() !== c.title) { c.title = title.trim().slice(0, 120); await save(c); }
  renderSidebarPanel();
  renderTopbar();
}

// ------------------------------------------------------------------ chat
async function send(question, { regenerate = null } = {}) {
  question = question.trim();
  if (!question || state.inflight) return;
  if (!state.server) { toast('Chưa kết nối backend: không thể gửi câu hỏi.'); return; }
  let conv = active();
  if (!conv) {
    conv = { id: uid('c'), title: question.slice(0, 60), created_at: now(), updated_at: now(), configuration: null, messages: [] };
    state.conversations.unshift(conv);
    state.activeId = conv.id;
  }
  const request = requestFromSettings(question);
  conv.configuration = { ...state.settings };
  let msg;
  if (regenerate) {
    msg = regenerate;
    Object.assign(msg, { status: 'pending', content: '', trace: null, chunks: {}, citations: [], error_kind: null, client_error: null,
      request, created_at: now() });
  } else {
    conv.messages.push({ id: uid('u'), role: 'user', content: question, created_at: now(), status: 'done', citations: [] });
    msg = { id: uid('a'), role: 'assistant', content: '', status: 'pending', created_at: now(), request, citations: [], chunks: {} };
    conv.messages.push(msg);
  }
  state.selectedMsgId = msg.id;
  const controller = new AbortController();
  state.inflight = { msgId: msg.id, started: Date.now(), controller };
  await save(conv);
  renderAll();
  scrollChatToEnd();
  try {
    const data = await api.chat({ ...request, query_id: msg.id }, controller.signal);
    const t = data.trace;
    Object.assign(msg, { status: t.status, content: t.answer || '', trace: t, chunks: data.chunks || {}, citations: t.citations || [],
      trace_id: t.query_id, error_kind: data.error_kind || null });
  } catch (e) {
    Object.assign(msg, { status: 'error', error_kind: e.name === 'AbortError' ? 'cancelled' : e.kind || 'backend',
      client_error: e.name === 'AbortError' ? 'Đã huỷ ở trình duyệt (backend có thể vẫn chạy xong lần gọi này).' : e.message });
  } finally {
    state.inflight = null;
    await save(conv);
    renderAll();
  }
}

function scrollChatToEnd() {
  els.chat.scrollTop = els.chat.scrollHeight;
}

// ------------------------------------------------------------------ rendering
function renderSidebarPanel() {
  els.sidebar.innerHTML = renderSidebar({
    conversations: state.conversations, activeId: state.activeId, query: state.query, editingId: state.editingId,
    persistent: conversationStore.persistent,
  });
  const input = els.sidebar.querySelector('[data-role="rename"]');
  if (input) { input.focus(); input.select(); }
}

function renderChatPanel() {
  const keep = els.chat.scrollTop;
  const atEnd = els.chat.scrollHeight - els.chat.scrollTop - els.chat.clientHeight < 40;
  els.chat.innerHTML = renderChat({ conv: active(), selectedId: state.selectedMsgId, inflight: state.inflight });
  els.chat.scrollTop = atEnd ? els.chat.scrollHeight : keep;
}

function renderConfigPanel() {
  els.config.innerHTML = state.serverError
    ? `<div class="cfg-bar error">${icon('alert', 14)} ${esc(state.serverError)}</div>`
    : renderConfig({ server: state.server, settings: state.settings, open: state.configOpen });
}

function renderInspector() {
  const [, msg] = findMsg(state.selectedMsgId);
  const tab = (id, label) => `<button type="button" role="tab" id="tab-${id}" aria-selected="${state.tab === id}" aria-controls="insp-body" data-action="tab" data-tab="${id}">${label}</button>`;
  const body = els.inspector.querySelector('.insp-body');
  const prev = body ? body.scrollTop : 0;
  els.inspector.innerHTML = `<div class="insp-head">
      <div class="tabs" role="tablist" aria-label="Inspector">${tab('evidence', 'Evidence')}${tab('trace', 'Execution trace')}</div>
      <button type="button" class="icon-btn only-drawer" data-action="close-drawers" aria-label="Đóng inspector">${icon('x')}</button>
    </div>
    <div class="insp-body" id="insp-body" role="tabpanel" aria-labelledby="tab-${state.tab}">
      ${msg ? `<p class="insp-for">Cho câu trả lời lúc ${new Date(msg.created_at).toLocaleString()}</p>` : ''}
      ${state.tab === 'evidence' ? renderEvidence(msg) : renderTrace(msg)}
    </div>`;
  els.inspector.querySelector('.insp-body').scrollTop = prev;
}

function renderTopbar() {
  els.title.textContent = active()?.title || 'Cuộc trò chuyện mới';
  els.send.disabled = Boolean(state.inflight) || !state.server;
  els.input.placeholder = state.inflight ? 'Đang chờ agent trả lời…' : 'Hỏi về nội dung sách…';
}

function renderAll() {
  renderSidebarPanel();
  renderChatPanel();
  renderConfigPanel();
  renderInspector();
  renderTopbar();
}

let toastTimer;
function toast(text) {
  els.toast.textContent = text;
  els.toast.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { els.toast.hidden = true; }, 3200);
}

// ------------------------------------------------------------------ drawers (small screens)
function closeDrawers() { els.app.classList.remove('sidebar-open', 'inspector-open'); }
function openInspector() {
  if (matchMedia('(max-width: 1180px)').matches) els.app.classList.add('inspector-open');
}

// ------------------------------------------------------------------ events
async function copy(text, label = 'Đã sao chép') {
  try { await navigator.clipboard.writeText(text); toast(label); } catch { toast('Trình duyệt chặn clipboard'); }
}

function openChunk(chunkId, msgEl) {
  const [, msg] = findMsg(msgEl?.dataset.msg || state.selectedMsgId);
  const page = msg?.chunks?.[chunkId]?.page ?? pageOf(chunkId);
  if (!page) { toast('Citation không hợp lệ: không xác định được trang'); return; }
  if (msg) state.selectedMsgId = msg.id;
  pdf.open(page, { focus: chunkId, msg });
}

document.addEventListener('click', (e) => {
  const a = e.target.closest('[data-action]');
  if (!a || els.pdf.contains(a)) return;
  const msgEl = a.closest('[data-msg]');
  const [, msg] = findMsg(msgEl?.dataset.msg);
  switch (a.dataset.action) {
    case 'new-conv': state.activeId = null; state.selectedMsgId = null; closeDrawers(); renderAll(); els.input.focus(); break;
    case 'select-conv': selectConv(a.dataset.id); break;
    case 'rename-conv': state.editingId = a.dataset.id; renderSidebarPanel(); break;
    case 'delete-conv': deleteConv(a.dataset.id); break;
    case 'toggle-config': state.configOpen = !state.configOpen; renderConfigPanel(); break;
    case 'example': els.input.value = a.dataset.text; send(a.dataset.text); els.input.value = ''; break;
    case 'open-chunk': openChunk(a.dataset.chunk, msgEl); break;
    case 'copy-answer': copy(msg?.content || ''); break;
    case 'copy-code': copy(a.closest('.code').querySelector('code').textContent); break;
    case 'copy-trace': { const [, m] = findMsg(state.selectedMsgId); copy(JSON.stringify(m?.trace, null, 2), 'Đã sao chép trace'); break; }
    case 'regenerate': if (msg) send(msg.request?.question || '', { regenerate: msg }); break;
    case 'cancel': state.inflight?.controller.abort(); break;
    case 'inspect': state.selectedMsgId = msg.id; renderChatPanel(); renderInspector(); openInspector(); break;
    case 'tab': state.tab = a.dataset.tab; renderInspector(); break;
    case 'toggle-sidebar': els.app.classList.toggle('sidebar-open'); break;
    case 'toggle-inspector': els.app.classList.toggle('inspector-open'); break;
    case 'close-drawers': closeDrawers(); break;
    case 'toggle-theme': {
      const t = document.documentElement.dataset.theme === 'light' ? 'dark' : 'light';
      document.documentElement.dataset.theme = t; settingsStore.setTheme(t); break;
    }
    default: return;
  }
});

// select an assistant message by clicking its body (not its buttons/links)
els.chat.addEventListener('click', (e) => {
  if (e.target.closest('button, a, details, summary')) return;
  const el = e.target.closest('.msg-assistant');
  if (el && el.dataset.msg !== state.selectedMsgId) { state.selectedMsgId = el.dataset.msg; renderChatPanel(); renderInspector(); }
});

els.config.addEventListener('change', (e) => {
  const k = e.target.dataset.setting;
  if (k) updateSetting(k, e.target.type === 'checkbox' ? e.target.checked : e.target.value);
});

els.sidebar.addEventListener('input', debounce((e) => {
  if (e.target.dataset.role === 'conv-search') {
    state.query = e.target.value;
    renderSidebarPanel();
    const s = els.sidebar.querySelector('[data-role="conv-search"]');
    s.focus(); s.setSelectionRange(s.value.length, s.value.length);
  }
}, 150));
els.sidebar.addEventListener('keydown', (e) => {
  if (e.target.dataset.role !== 'rename') return;
  if (e.key === 'Enter') finishRename(e.target.dataset.id, e.target.value);
  if (e.key === 'Escape') { state.editingId = null; renderSidebarPanel(); }
});
els.sidebar.addEventListener('focusout', (e) => {
  if (e.target.dataset.role === 'rename' && state.editingId) finishRename(e.target.dataset.id, e.target.value);
});

els.form.addEventListener('submit', (e) => {
  e.preventDefault();
  const text = els.input.value;
  if (!text.trim() || state.inflight) return;
  els.input.value = '';
  autosize();
  send(text);
});
els.input.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) { e.preventDefault(); els.form.requestSubmit(); }
});
function autosize() { els.input.style.height = 'auto'; els.input.style.height = Math.min(els.input.scrollHeight, 200) + 'px'; }
els.input.addEventListener('input', autosize);

setInterval(() => {
  if (!state.inflight) return;
  const el = els.chat.querySelector(`[data-msg="${state.inflight.msgId}"] [data-role="elapsed"]`);
  if (el) el.textContent = `${Math.round((Date.now() - state.inflight.started) / 1000)}s`;
}, 1000);

// ------------------------------------------------------------------ boot
async function boot() {
  const theme = settingsStore.theme();
  if (theme) document.documentElement.dataset.theme = theme;
  try {
    state.server = await api.config();
  } catch (e) {
    state.serverError = `Không tải được /api/config: ${e.message}`;
  }
  state.settings = sanitizeSettings(settingsStore.load(), state.server);
  state.conversations = await conversationStore.all();
  for (const c of state.conversations) {  // a reload during a request leaves a pending message: mark it honestly
    let changed = false;
    for (const m of c.messages) {
      if (m.status === 'pending') {
        Object.assign(m, { status: 'error', error_kind: 'interrupted', client_error: 'Trang đã tải lại trước khi backend trả lời; không có kết quả.' });
        changed = true;
      }
    }
    if (changed) await conversationStore.put(c);
  }
  pdf = new PdfViewer(els.pdf, { pages: state.server?.pdf?.pages || 1, onClose: () => els.input.focus() });
  selectConv(state.conversations[0]?.id || null);
  try {
    const h = await api.health();
    const ok = h.database === 'ok';
    els.health.className = `health ${ok ? 'ok' : 'bad'}`;
    els.health.title = ok ? `pgvector: ${h.vector_store_rows} chunk · PDF: ${h.pdf ? 'ok' : 'thiếu'}` : h.database;
    els.health.innerHTML = `<i></i>${ok ? `DB · ${h.vector_store_rows}` : 'DB lỗi'}`;
  } catch (e) {
    els.health.className = 'health bad';
    els.health.innerHTML = '<i></i>Backend offline';
    els.health.title = e.message;
  }
}

boot();
