// LocalConversationStore: conversations (with full traces) in IndexedDB; light UI settings in localStorage.
// Nothing secret is stored: the backend never sends keys, and the settings hold only provider/model names.
const DB = 'rag-workbench';
const STORE = 'conversations';
const SETTINGS_KEY = 'rag-wb-settings';
const THEME_KEY = 'rag-wb-theme';

let dbPromise = null;
let memory = null; // fallback when IndexedDB is unavailable (private mode): history then lives only in memory

function openDb() {
  if (!dbPromise) {
    dbPromise = new Promise((resolve, reject) => {
      if (!('indexedDB' in window)) return reject(new Error('IndexedDB unavailable'));
      const req = indexedDB.open(DB, 1);
      req.onupgradeneeded = () => req.result.createObjectStore(STORE, { keyPath: 'id' });
      req.onsuccess = () => resolve(req.result);
      req.onerror = () => reject(req.error);
    });
  }
  return dbPromise;
}

function tx(mode, fn) {
  return openDb().then((db) => new Promise((resolve, reject) => {
    const t = db.transaction(STORE, mode);
    const r = fn(t.objectStore(STORE));
    t.oncomplete = () => resolve(r && r.result);
    t.onerror = () => reject(t.error);
  }));
}

export const conversationStore = {
  persistent: true,
  async all() {
    try {
      const rows = await tx('readonly', (s) => s.getAll());
      return (rows || []).sort((a, b) => b.updated_at.localeCompare(a.updated_at));
    } catch {
      this.persistent = false;
      memory = memory || new Map();
      return [...memory.values()];
    }
  },
  async put(conv) {
    const copy = JSON.parse(JSON.stringify(conv)); // structured, detached snapshot
    if (!this.persistent) { memory.set(copy.id, copy); return; }
    await tx('readwrite', (s) => s.put(copy));
  },
  async remove(id) {
    if (!this.persistent) { memory.delete(id); return; }
    await tx('readwrite', (s) => s.delete(id));
  },
};

export const settingsStore = {
  load() {
    try { return JSON.parse(localStorage.getItem(SETTINGS_KEY)) || null; } catch { return null; }
  },
  save(s) {
    try { localStorage.setItem(SETTINGS_KEY, JSON.stringify(s)); } catch { /* storage blocked: settings stay in memory */ }
  },
  theme() {
    try { return localStorage.getItem(THEME_KEY); } catch { return null; }
  },
  setTheme(t) {
    try { localStorage.setItem(THEME_KEY, t); } catch { /* ignore */ }
  },
};
