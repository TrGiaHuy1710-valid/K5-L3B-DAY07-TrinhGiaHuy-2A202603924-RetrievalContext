// ChatWindow + ChatMessage. The status chip never claims "grounded": the backend only validates that citation IDs
// are in the retrieved context; semantic support is not judged, so answered messages are labelled as unverified.
import { esc, fmtS, fmtCost, fmtTime, pageOf } from '../util.js';
import { icon } from '../icons.js';
import { renderMarkdown } from '../markdown.js';
import { deriveEvidence } from './evidence.js';

const ERROR_KIND = {
  provider: 'LLM provider', database: 'Database', setup: 'Khởi tạo', agent: 'Agent / retrieval', network: 'Mất kết nối backend',
  request: 'Yêu cầu không hợp lệ', backend: 'Backend', cancelled: 'Đã huỷ', interrupted: 'Bị gián đoạn',
};

export function statusInfo(msg) {
  switch (msg.status) {
    case 'pending': return { cls: 'st-pending', label: 'Đang chạy', title: 'Agent đang tìm kiếm và trả lời' };
    case 'answered': return { cls: 'st-cited', label: 'Có trích dẫn · chưa kiểm chứng', title: 'Citation nằm trong context đã truy xuất (backend kiểm tra ID). Backend không chấm mức độ grounded; hãy đọc evidence.' };
    case 'abstain': return { cls: 'st-insufficient', label: 'Insufficient evidence', title: 'Agent từ chối vì sách không đủ bằng chứng (hoặc citation không hợp lệ)' };
    default: return { cls: 'st-error', label: `Error · ${ERROR_KIND[msg.error_kind] || 'không rõ'}`, title: msg.trace?.error || msg.client_error || '' };
  }
}

function meta(msg) {
  const t = msg.trace;
  const req = msg.request || {};
  const cfg = t?.config || req.config || {};
  const parts = [];
  if (t) {
    const { counts } = deriveEvidence(msg);
    parts.push(`${counts.context} chunk trong context`, `${counts.retrieved} retrieved`, `${(t.n_book_searches || 0) + (t.n_external_calls || 0)} tool call`);
  }
  parts.push(cfg.retriever || '–');
  parts.push(`${t?.provider || req.provider || 'default'}/${t?.model || req.model || 'default'}`);
  if (t) parts.push(fmtS(t.latency_s), fmtCost(t.cost_usd));
  return parts.map((p) => `<span>${esc(p)}</span>`).join('<span class="sep-dot">·</span>');
}

function sources(msg) {
  const t = msg.trace;
  if (!t) return '';
  const cited = (t.citations || []).map((id) => {
    const c = msg.chunks?.[id];
    const md = c?.metadata || {};
    return `<li><button type="button" class="src" data-action="open-chunk" data-chunk="${esc(id)}">
      <span class="src-page">${icon('file', 13)} book_ML.pdf · tr.${pageOf(id) ?? '?'}</span>
      <span class="src-meta">${esc(md.chapter_no ? `Ch.${md.chapter_no} ${md.chapter || ''}` : '')}</span>
      <span class="src-id mono">${esc(id.split('|').slice(1).join('|'))}</span></button></li>`;
  }).join('');
  const ext = (t.external_refs || []).map((r) =>
    `<li><a class="src" href="${esc(r.url)}" target="_blank" rel="noopener noreferrer"><span class="src-page">${icon('external', 13)} ${esc(r.title || r.url)}</span><span class="src-id mono">${esc(r.url)}</span></a></li>`).join('');
  if (!cited && !ext) return '';
  return `<div class="sources">${cited ? `<h4>Nguồn trong sách</h4><ul>${cited}</ul>` : ''}${ext ? `<h4>Tham khảo ngoài sách (không phải bằng chứng)</h4><ul>${ext}</ul>` : ''}</div>`;
}

function assistant(msg, selected, inflight) {
  const st = statusInfo(msg);
  const valid = new Set(msg.trace?.citations || []);
  const kindOf = (id) => (valid.has(id) ? 'cited' : 'invalid');
  let body;
  if (msg.status === 'pending') {
    const secs = inflight && inflight.msgId === msg.id ? Math.round((Date.now() - inflight.started) / 1000) : 0;
    body = `<div class="pending"><span class="spinner" aria-hidden="true"></span> Agent đang tìm trong sách và gọi LLM… <span class="mono" data-role="elapsed">${secs}s</span>
      <button type="button" class="btn sm ghost" data-action="cancel">Huỷ</button></div>`;
  } else if (msg.status === 'error') {
    body = `<div class="err-box">${icon('alert')}<div><strong>${esc(st.label)}</strong><p class="mono">${esc(msg.trace?.error || msg.client_error || 'Lỗi không rõ')}</p>
      <p class="muted">Trace của lần chạy lỗi vẫn được lưu; xem tab Trace.</p></div></div>`;
  } else {
    body = `<div class="md">${renderMarkdown(msg.content, kindOf)}</div>${sources(msg)}`;
  }
  const canRetry = msg.status !== 'pending' && !inflight;
  return `<article class="msg msg-assistant${selected ? ' selected' : ''}" data-msg="${esc(msg.id)}" aria-label="Câu trả lời">
    <div class="msg-head">
      <span class="status ${st.cls}" title="${esc(st.title)}"><i></i>${esc(st.label)}</span>
      <span class="time">${fmtTime(msg.created_at)}</span>
    </div>
    ${body}
    <div class="msg-meta">${meta(msg)}</div>
    <div class="msg-actions">
      ${msg.status !== 'pending' && msg.content ? `<button type="button" class="btn sm ghost" data-action="copy-answer">${icon('copy', 14)} Sao chép</button>` : ''}
      ${canRetry ? `<button type="button" class="btn sm ghost" data-action="regenerate">${icon('refresh', 14)} ${msg.status === 'error' ? 'Thử lại' : 'Tạo lại'}</button>` : ''}
      <button type="button" class="btn sm ghost" data-action="inspect">${icon('panel', 14)} Evidence & trace</button>
    </div>
  </article>`;
}

function user(msg) {
  return `<article class="msg msg-user" data-msg="${esc(msg.id)}" aria-label="Câu hỏi"><div class="bubble">${esc(msg.content)}</div></article>`;
}

const EXAMPLES = [
  'Gradient descent hoạt động như thế nào?',
  'So sánh hồi quy logistic và hồi quy softmax theo sách.',
  'Giải thích thuật toán K-means và gợi ý repo GitHub cài đặt từ đầu.',
];

export function renderChat({ conv, selectedId, inflight }) {
  if (!conv || !conv.messages.length) {
    return `<div class="empty">
      <div class="empty-ic">${icon('book', 22)}</div>
      <h1>Hỏi về sách “Machine Learning cơ bản”</h1>
      <p>Agent tìm trong <span class="mono">book_ML.pdf</span>, trả lời kèm trích dẫn trang và có thể tìm bài báo / repo liên quan.</p>
      <div class="examples">${EXAMPLES.map((e) => `<button type="button" class="example" data-action="example" data-text="${esc(e)}">${esc(e)}</button>`).join('')}</div>
    </div>`;
  }
  return `<div class="thread">${conv.messages.map((m) => (m.role === 'user' ? user(m) : assistant(m, m.id === selectedId, inflight))).join('')}</div>`;
}
