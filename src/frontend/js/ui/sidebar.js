// ConversationSidebar: new / search / group by date / rename inline / delete.
import { esc, dateGroup } from '../util.js';
import { icon } from '../icons.js';

const GROUPS = ['Hôm nay', 'Hôm qua', '7 ngày trước', 'Cũ hơn'];

export function renderSidebar({ conversations, activeId, query, editingId, persistent }) {
  const q = (query || '').trim().toLowerCase();
  const list = conversations.filter((c) => !q || c.title.toLowerCase().includes(q) ||
    c.messages.some((m) => m.role === 'user' && m.content.toLowerCase().includes(q)));
  const groups = GROUPS.map((g) => [g, list.filter((c) => dateGroup(c.updated_at) === g)]).filter(([, items]) => items.length);
  const item = (c) => {
    if (c.id === editingId) {
      return `<li class="conv editing"><input class="rename" data-role="rename" data-id="${esc(c.id)}" value="${esc(c.title)}" aria-label="Tên cuộc trò chuyện" maxlength="120"></li>`;
    }
    return `<li class="conv${c.id === activeId ? ' active' : ''}">
      <button type="button" class="conv-btn" data-action="select-conv" data-id="${esc(c.id)}" ${c.id === activeId ? 'aria-current="true"' : ''}>
        <span class="conv-title">${esc(c.title)}</span></button>
      <span class="conv-actions">
        <button type="button" class="icon-btn sm" data-action="rename-conv" data-id="${esc(c.id)}" aria-label="Đổi tên">${icon('pencil', 14)}</button>
        <button type="button" class="icon-btn sm" data-action="delete-conv" data-id="${esc(c.id)}" aria-label="Xoá">${icon('trash', 14)}</button>
      </span></li>`;
  };
  return `
    <div class="side-head">
      <span class="brand">${icon('book', 16)} RAG Workbench</span>
      <button type="button" class="icon-btn only-mobile" data-action="close-drawers" aria-label="Đóng">${icon('x')}</button>
    </div>
    <button type="button" class="btn primary block" data-action="new-conv">${icon('plus')} Cuộc trò chuyện mới</button>
    <label class="search">${icon('search', 14)}<input type="search" data-role="conv-search" placeholder="Tìm lịch sử…" value="${esc(query || '')}" aria-label="Tìm trong lịch sử"></label>
    <nav class="conv-groups" aria-label="Lịch sử trò chuyện">
      ${groups.length ? groups.map(([g, items]) => `<h2 class="group">${g}</h2><ul class="conv-list">${items.map(item).join('')}</ul>`).join('')
        : `<p class="empty-sm">${q ? 'Không có kết quả.' : 'Chưa có cuộc trò chuyện.'}</p>`}
    </nav>
    <p class="side-foot">${persistent ? 'Lịch sử lưu trong IndexedDB của trình duyệt.' : `${icon('alert', 12)} IndexedDB không khả dụng: lịch sử chỉ giữ tới khi tải lại trang.`}</p>`;
}
