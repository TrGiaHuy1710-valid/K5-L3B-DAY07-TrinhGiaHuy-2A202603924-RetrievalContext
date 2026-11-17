// Small shared helpers. Every string from the backend / model / document goes through esc() before innerHTML.
export function esc(v) {
  return String(v ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

export const uid = (p = '') => p + (crypto.randomUUID ? crypto.randomUUID() : Math.random().toString(36).slice(2)).replace(/-/g, '').slice(0, 12);
export const now = () => new Date().toISOString();

export function fmtMs(ms) {
  if (ms == null) return '–';
  return ms >= 1000 ? `${(ms / 1000).toFixed(1)} s` : `${Math.round(ms)} ms`;
}
export const fmtS = (s) => (s == null ? '–' : `${Number(s).toFixed(1)} s`);
export function fmtCost(c) {
  if (c == null) return 'n/a';
  return c < 0.01 ? `$${c.toFixed(5)}` : `$${c.toFixed(3)}`;
}
export function fmtTime(iso) {
  const d = new Date(iso);
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

// Conversation groups: Today, Yesterday, Previous 7 days, Older
export function dateGroup(iso) {
  const d = new Date(iso);
  const start = new Date(); start.setHours(0, 0, 0, 0);
  const day = 86400000;
  if (d >= start) return 'Hôm nay';
  if (d >= start - day) return 'Hôm qua';
  if (d >= start - 7 * day) return '7 ngày trước';
  return 'Cũ hơn';
}

export const pageOf = (chunkId) => {
  const m = /\|p(\d+)\|/.exec(chunkId || '');
  return m ? Number(m[1]) : null;
};

export function debounce(fn, ms = 200) {
  let t;
  return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); };
}
