// PdfViewer: pages rendered from the ORIGINAL book_ML.pdf by the backend (PyMuPDF). Highlights use the exact
// character boxes returned by /locate; when a chunk cannot be matched, nothing is drawn and the excerpt is shown.
import { api } from '../api.js';
import { esc } from '../util.js';
import { icon } from '../icons.js';
import { deriveEvidence } from './evidence.js';

// zoom is relative to "fit width" of the stage; the backend raster scale follows it so text stays crisp
const SCALES = [0.75, 1, 1.25, 1.5, 2];
const raster = (zoom) => (zoom <= 1 ? 1.5 : 2.5);

export class PdfViewer {
  constructor(root, { pages, onClose }) {
    this.root = root;
    this.pages = pages || 1;
    this.onClose = onClose;
    this.state = { page: 1, scaleIdx: 1, focus: null, msg: null, locate: null, error: null, token: 0 };
    root.addEventListener('click', (e) => this.onClick(e));
    root.addEventListener('keydown', (e) => this.onKey(e));
    root.addEventListener('change', (e) => {
      if (e.target.matches('[data-role="page-input"]')) this.go(Number(e.target.value));
    });
  }

  get isOpen() { return !this.root.hidden; }

  open(page, { focus = null, msg = null } = {}) {
    this.state.page = Math.min(Math.max(1, page || 1), this.pages);
    this.state.focus = focus;
    this.state.msg = msg;
    this.root.hidden = false;
    this.load();
    this.root.querySelector('.pdf-toolbar button')?.focus({ preventScroll: true });
  }

  close() { this.root.hidden = true; this.onClose?.(); }

  go(page) {
    if (!Number.isFinite(page)) return;
    this.state.page = Math.min(Math.max(1, page), this.pages);
    this.state.focus = null;
    this.load();
  }

  chunkStatus() {
    // chunk id -> 'cited' | 'context' | 'retrieved' for the message the viewer was opened from
    const map = {};
    if (!this.state.msg) return map;
    for (const it of deriveEvidence(this.state.msg).items) map[it.id] = it.cited ? 'cited' : it.inContext ? 'context' : 'retrieved';
    return map;
  }

  async load() {
    const token = ++this.state.token;
    const status = this.chunkStatus();
    const ids = Object.keys(status).filter((id) => (this.state.msg?.chunks?.[id]?.page ?? null) === this.state.page);
    if (this.state.focus && !ids.includes(this.state.focus)) ids.push(this.state.focus);
    this.state.locate = null;
    this.state.error = null;
    this.state.ids = ids;
    this.render();
    if (!ids.length) return;
    try {
      const res = await api.locate(this.state.page, ids);
      if (token !== this.state.token) return;
      this.state.locate = res;
    } catch (e) {
      if (token !== this.state.token) return;
      this.state.error = `Không định vị được evidence: ${e.message}`;
    }
    this.render();
    const f = this.root.querySelector('.hl.focus');
    f?.scrollIntoView({ block: 'center', behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth' });
  }

  render() {
    const { page, scaleIdx, focus, locate, error, ids = [] } = this.state;
    const scale = SCALES[scaleIdx];
    const status = this.chunkStatus();
    const chunks = this.state.msg?.chunks || {};
    let layer = '';
    let list = '';
    if (locate) {
      const W = locate.width, H = locate.height;
      for (const m of locate.matches) {
        const st = status[m.chunk_id] || 'retrieved';
        if (m.found) {
          layer += m.rects.map(([x0, y0, x1, y1]) => `<div class="hl hl-${st}${m.chunk_id === focus ? ' focus' : ''}" style="left:${(x0 / W) * 100}%;top:${(y0 / H) * 100}%;width:${((x1 - x0) / W) * 100}%;height:${((y1 - y0) / H) * 100}%" title="${esc(m.chunk_id)}"></div>`).join('');
        }
        const text = chunks[m.chunk_id]?.text || '';
        list += `<li class="loc loc-${st}${m.chunk_id === focus ? ' focus' : ''}">
          <div class="loc-head"><span class="badge b-${st === 'retrieved' ? 'plain' : st}">${st}</span><span class="mono">${esc(m.chunk_id.split('|').slice(1).join('|'))}</span>
          ${m.found ? `<span class="ok">${icon('check', 12)} ${esc(m.method)}</span>` : `<span class="warn">${icon('alert', 12)} ${esc(m.reason)}</span>`}</div>
          ${m.found ? '' : `<p class="excerpt">${esc(text.slice(0, 400))}</p>`}
        </li>`;
      }
    }
    this.root.innerHTML = `
      <div class="pdf-toolbar" role="toolbar" aria-label="Điều khiển PDF">
        <button type="button" class="icon-btn" data-action="pdf-close" aria-label="Đóng PDF">${icon('x')}</button>
        <span class="pdf-title">${icon('book', 14)} book_ML.pdf</span>
        <div class="grow"></div>
        <button type="button" class="icon-btn" data-action="pdf-prev" aria-label="Trang trước" ${page <= 1 ? 'disabled' : ''}>${icon('left')}</button>
        <label class="page-ctl">Trang <input data-role="page-input" type="number" min="1" max="${this.pages}" value="${page}" aria-label="Số trang"> / ${this.pages}</label>
        <button type="button" class="icon-btn" data-action="pdf-next" aria-label="Trang sau" ${page >= this.pages ? 'disabled' : ''}>${icon('right')}</button>
        <span class="sep"></span>
        <button type="button" class="icon-btn" data-action="pdf-zoom-out" aria-label="Thu nhỏ" ${scaleIdx === 0 ? 'disabled' : ''}>${icon('zoomOut')}</button>
        <span class="mono zoom">${Math.round(scale * 100)}%</span>
        <button type="button" class="icon-btn" data-action="pdf-zoom-in" aria-label="Phóng to" ${scaleIdx === SCALES.length - 1 ? 'disabled' : ''}>${icon('zoomIn')}</button>
        <a class="icon-btn" href="${api.pdfUrl(page)}" target="_blank" rel="noopener" aria-label="Mở PDF gốc ở tab mới">${icon('external')}</a>
      </div>
      <div class="pdf-body">
        <div class="pdf-stage">
          <div class="pdf-page" style="width:${scale * 100}%">
            <img src="${api.pageUrl(page, raster(scale))}" alt="Trang ${page} của book_ML.pdf" data-role="page-img">
            <div class="hl-layer">${layer}</div>
          </div>
        </div>
        <aside class="pdf-side" aria-label="Chunk trên trang này">
          <h3>Chunk trên trang ${page}</h3>
          ${error ? `<p class="warn">${esc(error)}</p>` : ''}
          ${ids.length ? (locate ? `<ul class="loc-list">${list}</ul>` : '<p class="muted">Đang định vị…</p>') : '<p class="muted">Câu trả lời đang chọn không có chunk nào trên trang này.</p>'}
          <p class="note"><i class="dot d-cited"></i>cited <i class="dot d-context"></i>context <i class="dot d-retrieved"></i>retrieved. Vị trí lấy từ ký tự của PDF gốc; không khớp thì không tô.</p>
        </aside>
      </div>`;
    const img = this.root.querySelector('[data-role="page-img"]');
    img.addEventListener('error', () => {
      img.replaceWith(Object.assign(document.createElement('div'), { className: 'pdf-err', textContent: `Không tải được trang ${page} của PDF (lỗi tải PDF từ backend).` }));
    }, { once: true });
  }

  onClick(e) {
    const a = e.target.closest('[data-action]');
    if (!a || !this.root.contains(a)) return;
    const s = this.state;
    switch (a.dataset.action) {
      case 'pdf-close': this.close(); break;
      case 'pdf-prev': this.go(s.page - 1); break;
      case 'pdf-next': this.go(s.page + 1); break;
      case 'pdf-zoom-in': s.scaleIdx = Math.min(SCALES.length - 1, s.scaleIdx + 1); this.render(); break;
      case 'pdf-zoom-out': s.scaleIdx = Math.max(0, s.scaleIdx - 1); this.render(); break;
      default: return;
    }
  }

  onKey(e) {
    if (e.target.matches('input')) return;
    if (e.key === 'Escape') this.close();
    else if (e.key === 'ArrowLeft') this.go(this.state.page - 1);
    else if (e.key === 'ArrowRight') this.go(this.state.page + 1);
  }
}
