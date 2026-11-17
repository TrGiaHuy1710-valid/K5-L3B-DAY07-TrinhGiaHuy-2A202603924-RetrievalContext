// TraceInspector: the agent lifecycle rebuilt ONLY from fields the backend recorded (src/agent.py trace schema).
// Missing fields are omitted, never invented.
import { esc, fmtMs, fmtS, fmtCost } from '../util.js';
import { icon } from '../icons.js';

function val(v) {
  if (v === undefined) return null;
  if (v === null) return '<span class="muted">null</span>';
  if (Array.isArray(v) && !v.length) return '<span class="muted">[]</span>';
  if (typeof v === 'object') return `<pre class="json">${esc(JSON.stringify(v, null, 2))}</pre>`;
  return `<span class="mono">${esc(v)}</span>`;
}

function fields(obj) {
  const rows = Object.entries(obj).map(([k, v]) => [k, val(v)]).filter(([, h]) => h !== null);
  return `<dl class="kv">${rows.map(([k, h]) => `<dt>${esc(k)}</dt><dd>${h}</dd>`).join('')}</dl>`;
}

function resultsTable(e) {
  const added = new Set(e.added || []), dup = new Set(e.duplicate || []);
  const rows = (e.results || []).map((r) => {
    const tag = added.has(r.id) ? '<span class="badge b-context">added</span>' : dup.has(r.id) ? '<span class="badge">dup</span>' : '<span class="badge">skipped</span>';
    return `<tr><td>${r.rank}</td><td><button type="button" class="link-btn mono" data-action="open-chunk" data-chunk="${esc(r.id)}">${esc(r.id.split('|').slice(1).join('|'))}</button></td><td>${r.page}</td><td>${r.score.toFixed(4)}</td><td>${tag}</td></tr>`;
  }).join('');
  return rows ? `<table class="tbl"><thead><tr><th>rank</th><th>chunk</th><th>page</th><th>score</th><th>context</th></tr></thead><tbody>${rows}</tbody></table>` : '<p class="muted">0 kết quả</p>';
}

function steps(t) {
  const out = [{ icon: 'user', title: 'Nhận câu hỏi', status: 'ok', body: fields({ question: t.question, filters: t.filter ?? 'none', query_id: t.query_id }) }];
  if (t.stage === 'setup') out.push({ icon: 'alert', title: 'Khởi tạo retriever / provider thất bại', status: 'error', body: fields({ error_message: t.error }) });
  let n = 0;
  for (const e of t.events || []) {
    if (e.event === 'llm') {
      out.push({
        icon: 'cpu', title: `Controller (LLM) · bước ${e.step + 1}`,
        sub: e.tool_calls?.length ? `chọn ${e.tool_calls.join(', ')}` : 'không gọi tool', status: 'ok', meta: fmtS(e.latency_s),
        body: fields({ provider: t.provider, model: t.model, tool_calls: e.tool_calls, prompt_tokens: e.prompt_tokens,
          completion_tokens: e.completion_tokens, cost_usd: e.cost_usd ?? 'not reported by provider', latency_s: e.latency_s,
          retries: e.retries, assistant_text: e.text || undefined }),
      });
    } else if (e.event === 'search') {
      n += 1;
      out.push({
        icon: 'search', title: `Tool · search_book #${n}`, sub: `“${e.query}”`, status: 'ok', meta: fmtMs(e.elapsed_ms),
        body: fields({ tool_name: e.tool, tool_arguments: { query: e.query }, retrieval_method: e.retriever, filters: e.filter ?? 'none',
          top_k: e.top_k, execution_time_ms: e.elapsed_ms, returned_chunks: (e.results || []).length,
          added_to_context: e.added, duplicate: e.duplicate, skipped: e.skipped, context_chars_after: e.context_chars }) + resultsTable(e),
      });
    } else if (e.event === 'external_search') {
      out.push({
        icon: 'external', title: `Tool · ${e.tool}`, sub: `“${e.query}”`, status: e.error ? 'error' : 'ok', meta: fmtMs(e.elapsed_ms),
        body: fields({ tool_name: e.tool, tool_arguments: { query: e.query }, execution_time_ms: e.elapsed_ms, status: e.error ? 'error' : 'ok',
          error_message: e.error ? `${e.error}: ${e.error_message || ''}` : undefined, urls: e.urls }),
      });
    } else if (e.event === 'search_limit' || e.event === 'external_limit') {
      out.push({ icon: 'alert', title: `${e.tool}: hết lượt gọi`, status: 'warn', body: fields({ query: e.query }) });
    } else if (e.event === 'tool_error') {
      out.push({ icon: 'alert', title: `Lỗi tool ${e.tool}`, status: 'error', body: fields({ error_message: e.error }) });
    }
  }
  if (t.stage !== 'setup' && (t.n_book_searches > 0 || (t.context_ids || []).length)) {
    out.push({
      icon: 'book', title: 'Context cuối gửi cho model', sub: `${(t.context_ids || []).length} chunk · ${t.context_chars} ký tự`, status: 'ok',
      body: fields({ budget_chars: t.config?.budget_chars, context_chars: t.context_chars, context_ids: t.context_ids }) +
        (t.context ? `<details class="sub"><summary>Nội dung context</summary><pre class="json">${esc(t.context)}</pre></details>` : ''),
    });
  }
  const v = t.validation || {};
  const final = { answered: ['flag', 'Câu trả lời cuối (final_answer)', 'ok'], abstain: ['flag', 'Từ chối: thiếu bằng chứng', 'warn'], error: ['alert', 'Lỗi', 'error'] }[t.status] || ['flag', t.status, 'warn'];
  out.push({
    icon: final[0], title: final[1], status: final[2],
    body: fields({ status: t.status, model_status: v.model_status, citations: t.citations, invalid_citations: v.invalid_citations,
      dropped_external_refs: v.dropped_refs, citations_written_in_answer: v.citations_in_text, reason: v.reason,
      external_refs: t.external_refs?.length ? t.external_refs : undefined, error_message: t.error }),
  });
  return out;
}

export function renderTrace(msg) {
  if (!msg) return '<div class="empty-sm">Chọn một câu trả lời để xem trace.</div>';
  if (msg.status === 'pending') return '<div class="empty-sm">Đang chạy agent… trace sẽ có khi backend trả kết quả (backend không stream).</div>';
  const t = msg.trace;
  if (!t) {
    return `<div class="trace-error">${icon('alert')} <div><strong>Không có trace</strong><p>${esc(msg.client_error || 'Yêu cầu không tới được agent.')}</p></div></div>`;
  }
  const c = t.config || {};
  const head = `<div class="trace-head">
    ${fields({ provider: t.provider, model: t.model, retriever: c.retriever, preset: c.name,
      config: { top_k: c.top_k, budget_chars: c.budget_chars, max_new_per_search: c.max_new_per_search, max_book_searches: c.max_book_searches, max_steps: c.max_steps, external_tools: c.external_tools },
      latency: fmtS(t.latency_s), llm_calls: t.n_llm_calls, book_searches: t.n_book_searches, external_calls: t.n_external_calls,
      tokens: `${t.prompt_tokens} in / ${t.completion_tokens} out`, cost: fmtCost(t.cost_usd) })}
  </div>`;
  const items = steps(t).map((s, i) => `<li class="step st-${s.status}">
      <details ${s.status === 'error' ? 'open' : ''}>
        <summary><span class="step-ic">${icon(s.icon, 14)}</span><span class="step-t">${i + 1}. ${esc(s.title)}</span>${s.sub ? `<span class="step-sub">${esc(s.sub)}</span>` : ''}${s.meta ? `<span class="step-meta mono">${esc(s.meta)}</span>` : ''}</summary>
        <div class="step-body">${s.body}</div>
      </details></li>`).join('');
  return `${head}<ol class="timeline">${items}</ol>
    <details class="raw"><summary>Raw trace JSON</summary>
      <button type="button" class="btn sm" data-action="copy-trace">${icon('copy', 14)} Sao chép</button>
      <pre class="json">${esc(JSON.stringify(t, null, 2))}</pre></details>`;
}
