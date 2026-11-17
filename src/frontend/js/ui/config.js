// RetrievalConfig + ProviderSelector. Options come from GET /api/config (real backend configuration).
// The settings hold only names/numbers; API keys stay on the server.
import { esc } from '../util.js';
import { icon } from '../icons.js';

const NUM = [
  ['top_k', 'Top-K', 'Số chunk mỗi lần search_book'],
  ['budget_chars', 'Context budget', 'Tổng ký tự sách gửi cho model'],
  ['max_new_per_search', 'Max mới / lần tìm', 'Số chunk mới tối đa mỗi lần tìm được thêm vào context'],
  ['max_book_searches', 'Max lần tìm', 'Số lần search_book tối đa'],
  ['max_steps', 'Max bước LLM', 'Số lần gọi LLM tối đa'],
];

export function renderConfig({ server, settings, open }) {
  if (!server) return `<div class="cfg-bar"><span class="muted">${icon('alert', 14)} Chưa tải được cấu hình backend.</span></div>`;
  const prov = server.providers.find((p) => p.id === settings.provider);
  const chapter = server.chapters.find((c) => c.chapter_no === settings.chapter_no);
  const retrieverLabel = server.retrievers.find((r) => r.id === settings.retriever)?.label || settings.retriever;
  const summary = `<button type="button" class="cfg-bar" data-action="toggle-config" aria-expanded="${open}" aria-controls="cfg-form">
      ${icon('settings', 14)}
      <span class="chip">${esc(retrieverLabel)}</span>
      <span class="chip">k=${settings.top_k} · ${settings.budget_chars} ký tự</span>
      ${chapter ? `<span class="chip">Ch.${esc(chapter.chapter_no)}</span>` : ''}
      <span class="chip ${prov && !prov.available ? 'chip-warn' : ''}">${esc(settings.provider)}/${esc(settings.model || prov?.models[0] || 'default')}</span>
      <span class="grow"></span>${icon(open ? 'down' : 'right', 14)}
    </button>`;
  if (!open) return summary;
  const num = ([k, label, help]) => {
    const [lo, hi] = server.limits[k];
    return `<label class="field" title="${esc(help)}"><span>${label}</span><input type="number" data-setting="${k}" min="${lo}" max="${hi}" value="${esc(settings[k])}"></label>`;
  };
  return `${summary}
    <div class="cfg-form" id="cfg-form">
      <div class="cfg-row">
        <label class="field"><span>Preset</span><select data-setting="preset">
          <option value="">custom</option>
          ${Object.keys(server.presets).map((p) => `<option value="${esc(p)}" ${settings.preset === p ? 'selected' : ''}>${esc(p)}</option>`).join('')}
        </select></label>
        <label class="field wide"><span>Retrieval strategy</span><select data-setting="retriever">
          ${server.retrievers.map((r) => `<option value="${esc(r.id)}" ${settings.retriever === r.id ? 'selected' : ''}>${esc(r.label)}</option>`).join('')}
        </select></label>
        <label class="field wide"><span>Lọc theo chương</span><select data-setting="chapter_no">
          <option value="">Toàn bộ sách</option>
          ${server.chapters.map((c) => `<option value="${esc(c.chapter_no)}" ${settings.chapter_no === c.chapter_no ? 'selected' : ''}>Ch.${esc(c.chapter_no)} · ${esc(c.title)} (tr.${c.first_page})</option>`).join('')}
        </select></label>
      </div>
      <div class="cfg-row">${NUM.map(num).join('')}
        <label class="field check"><input type="checkbox" data-setting="external_tools" ${settings.external_tools ? 'checked' : ''}><span>arXiv / GitHub tools</span></label>
      </div>
      <div class="cfg-row">
        <label class="field"><span>Provider</span><select data-setting="provider">
          ${server.providers.map((p) => `<option value="${esc(p.id)}" ${settings.provider === p.id ? 'selected' : ''} ${p.available ? '' : 'disabled'}>${esc(p.id)}${p.available ? '' : ' (chưa cấu hình)'}</option>`).join('')}
        </select></label>
        <label class="field wide"><span>Model</span><input list="model-list" data-setting="model" value="${esc(settings.model || '')}" placeholder="${esc(prov?.models[0] || '')}">
          <datalist id="model-list">${(prov?.models || []).map((m) => `<option value="${esc(m)}"></option>`).join('')}</datalist></label>
        <p class="field-note">${esc(prov?.note || '')}. Model để trống = mặc định của backend. Cấu hình áp dụng cho câu hỏi tiếp theo và được lưu trong trace từng câu trả lời.</p>
      </div>
    </div>`;
}
