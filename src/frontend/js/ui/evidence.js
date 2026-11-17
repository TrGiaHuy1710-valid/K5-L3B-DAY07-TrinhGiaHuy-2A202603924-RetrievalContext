// EvidenceInspector: retrieved vs context vs cited chunks of ONE assistant message, from its saved trace.
import { esc, pageOf } from '../util.js';
import { icon } from '../icons.js';

export function deriveEvidence(msg) {
  const t = msg.trace || {};
  const chunks = msg.chunks || {};
  const ctx = new Set(t.context_ids || []);
  const cited = new Set(t.citations || []);
  const map = new Map();
  let n = 0;
  for (const e of t.events || []) {
    if (e.event !== 'search') continue;
    n += 1;
    const added = new Set(e.added || []), dup = new Set(e.duplicate || []), skipped = new Set(e.skipped || []);
    for (const r of e.results || []) {
      const hit = {
        search: n, query: e.query, rank: r.rank, score: r.score, retriever: e.retriever,
        outcome: added.has(r.id) ? 'added' : dup.has(r.id) ? 'duplicate' : skipped.has(r.id) ? 'skipped (budget / max per search)' : '—',
      };
      if (map.has(r.id)) map.get(r.id).hits.push(hit);
      else map.set(r.id, { id: r.id, page: r.page, hits: [hit] });
    }
  }
  for (const id of [...ctx, ...cited]) if (!map.has(id)) map.set(id, { id, page: pageOf(id), hits: [] });
  const order = (it) => (it.cited ? 0 : it.inContext ? 1 : 2);
  const items = [...map.values()]
    .map((it) => ({ ...it, chunk: chunks[it.id], inContext: ctx.has(it.id), cited: cited.has(it.id) }))
    .sort((a, b) => order(a) - order(b) || (a.hits[0]?.search ?? 99) - (b.hits[0]?.search ?? 99) || (a.hits[0]?.rank ?? 99) - (b.hits[0]?.rank ?? 99));
  return { items, counts: { retrieved: map.size, context: ctx.size, cited: cited.size } };
}

function card(it) {
  const cls = it.cited ? 'ev-cited' : it.inContext ? 'ev-context' : 'ev-retrieved';
  const badges = [
    it.cited ? '<span class="badge b-cited">Cited</span>' : '',
    it.inContext ? '<span class="badge b-context">In context</span>' : '<span class="badge">Not in context</span>',
    '<span class="badge">Retrieved</span>',
  ].join('');
  const md = it.chunk?.metadata || {};
  const best = it.hits[0];
  const hits = it.hits.map((h) => `<tr><td>#${h.search}</td><td>${h.rank}</td><td>${h.score.toFixed(4)}</td><td>${esc(h.outcome)}</td><td class="q">${esc(h.query)}</td></tr>`).join('');
  const text = it.chunk ? it.chunk.text : '(nội dung chunk không có trong phản hồi backend)';
  return `<article class="ev ${cls}">
    <div class="ev-head">
      <div class="badges">${badges}</div>
      <button type="button" class="link-btn" data-action="open-chunk" data-chunk="${esc(it.id)}">${icon('file', 14)} tr.${it.page ?? '?'}</button>
    </div>
    <div class="ev-id mono">${esc(it.id)}</div>
    <div class="ev-meta">${esc(md.chapter_no ? `Ch.${md.chapter_no} · ${md.chapter || ''}` : md.chapter || '')}${md.section ? ` · ${esc(md.section)}` : ''}</div>
    ${best ? `<div class="ev-rank mono">search #${best.search} · rank ${best.rank} · score ${best.score.toFixed(4)} · ${esc(best.retriever || '')}</div>` : '<div class="ev-rank">không có trong kết quả tìm kiếm</div>'}
    <p class="ev-text">${esc(text)}</p>
    <details class="ev-more"><summary>Chi tiết</summary>
      <div class="ev-full">${esc(text)}</div>
      ${hits ? `<table class="tbl"><thead><tr><th>search</th><th>rank</th><th>score</th><th>context</th><th>query</th></tr></thead><tbody>${hits}</tbody></table>` : ''}
      <pre class="json">${esc(JSON.stringify({ source: it.chunk?.source, source_id: it.chunk?.source_id, page: it.page, metadata: md }, null, 2))}</pre>
    </details>
  </article>`;
}

export function renderEvidence(msg) {
  if (!msg) return '<div class="empty-sm">Chọn một câu trả lời để xem evidence.</div>';
  if (msg.status === 'pending') return '<div class="empty-sm">Đang chạy agent…</div>';
  const { items, counts } = deriveEvidence(msg);
  if (!items.length) {
    return `<div class="empty-sm">${msg.status === 'error' ? 'Lần chạy lỗi trước khi có kết quả tìm kiếm.' : 'Agent không gọi search_book cho câu này.'}</div>`;
  }
  return `<div class="ev-summary">
      <span><i class="dot d-retrieved"></i>${counts.retrieved} retrieved</span>
      <span><i class="dot d-context"></i>${counts.context} in context</span>
      <span><i class="dot d-cited"></i>${counts.cited} cited</span>
    </div>
    <p class="note">Cited = citation nằm trong context (backend đã kiểm tra ID). Việc đoạn văn có thực sự hỗ trợ câu trả lời cần người đọc xác nhận.</p>
    ${items.map(card).join('')}`;
}
