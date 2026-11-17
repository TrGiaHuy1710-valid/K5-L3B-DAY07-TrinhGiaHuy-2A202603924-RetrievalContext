// Client for the real backend in src/api.py. No mock responses: every failure is thrown to the caller.
export class ApiError extends Error {
  constructor(message, status, kind = 'backend') {
    super(message);
    this.status = status;
    this.kind = kind;
  }
}

async function request(url, opts = {}) {
  let res;
  try {
    res = await fetch(url, opts);
  } catch (e) {
    if (e.name === 'AbortError') throw e;
    throw new ApiError('Không kết nối được backend (python -m src.api đã chạy chưa?)', 0, 'network');
  }
  const data = await res.json().catch(() => null);
  if (!res.ok) {
    const detail = data && data.detail ? (typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail)) : `HTTP ${res.status}`;
    throw new ApiError(detail, res.status, res.status === 400 || res.status === 422 ? 'request' : 'backend');
  }
  return data;
}

export const api = {
  health: () => request('/api/health'),
  config: () => request('/api/config'),
  chat: (body, signal) =>
    request('/api/chat', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body), signal }),
  locate: (page, ids) =>
    request(`/api/pdf/page/${page}/locate?` + ids.map((i) => 'chunk_id=' + encodeURIComponent(i)).join('&')),
  pageUrl: (n, scale) => `/api/pdf/page/${n}.png?scale=${scale}`,
  pdfUrl: (n) => `/api/pdf#page=${n}`,
};
