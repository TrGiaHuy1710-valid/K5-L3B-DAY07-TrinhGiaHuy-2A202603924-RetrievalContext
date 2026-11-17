// Minimal, safe Markdown: text is HTML-escaped first, then a few constructs are re-introduced.
// Citations written by the agent as [chunk-id] (or [id1, id2]) become clickable page chips.
import { esc, pageOf } from './util.js';
import { icon } from './icons.js';

const CITE = /\[((?:[\w.-]+\|p\d+\|\d+)(?:\s*[,;]\s*[\w.-]+\|p\d+\|\d+)*)\]/g;

function chip(id, kindOf) {
  const kind = kindOf ? kindOf(id) : 'cited'; // 'cited' (validated by backend) | 'invalid' (not in context)
  const page = pageOf(id);
  const title = kind === 'invalid' ? `${id} — không có trong context (backend đã loại)` : id;
  return `<button type="button" class="cite cite-${kind}" data-action="open-chunk" data-chunk="${esc(id)}" title="${esc(title)}">tr.${page ?? '?'}</button>`;
}

function inline(text, kindOf) {
  let s = esc(text);
  s = s.replace(/`([^`]+)`/g, '<code>$1</code>');
  // LaTeX is shown verbatim as code (no KaTeX: package CDNs are blocked here); pairs are matched left to right
  s = s.replace(/\\\((.+?)\\\)|\$([^$\n]{1,160}?)\$/g, (_, a, b) => `<code class="math">${a ?? b}</code>`);
  s = s.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
  s = s.replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>');
  s = s.replace(CITE, (_, ids) => ids.split(/\s*[,;]\s*/).map((id) => chip(id, kindOf)).join(''));
  return s;
}

function blocks(text, kindOf) {
  let html = '';
  let para = [];
  let list = null;
  const flushP = () => { if (para.length) { html += `<p>${inline(para.join(' '), kindOf)}</p>`; para = []; } };
  const flushL = () => {
    if (list) { html += `<${list.type}>${list.items.map((i) => `<li>${inline(i, kindOf)}</li>`).join('')}</${list.type}>`; list = null; }
  };
  for (const raw of text.split('\n')) {
    const l = raw.trimEnd();
    let m;
    if (!l.trim()) { flushP(); flushL(); continue; }
    if ((m = l.match(/^(#{1,4})\s+(.*)$/))) {
      flushP(); flushL();
      const lv = Math.min(m[1].length + 2, 6);
      html += `<h${lv}>${inline(m[2], kindOf)}</h${lv}>`;
      continue;
    }
    if ((m = l.match(/^\s*[-*•]\s+(.*)$/))) {
      flushP();
      if (!list || list.type !== 'ul') { flushL(); list = { type: 'ul', items: [] }; }
      list.items.push(m[1]);
      continue;
    }
    if ((m = l.match(/^\s*\d+[.)]\s+(.*)$/))) {
      flushP();
      if (!list || list.type !== 'ol') { flushL(); list = { type: 'ol', items: [] }; }
      list.items.push(m[1]);
      continue;
    }
    if (list && /^\s{2,}/.test(raw)) { list.items[list.items.length - 1] += ' ' + l.trim(); continue; }
    flushL();
    para.push(l.trim());
  }
  flushP(); flushL();
  return html;
}

function code(part) {
  const nl = part.indexOf('\n');
  const lang = nl >= 0 ? part.slice(0, nl).trim() : '';
  const body = (nl >= 0 ? part.slice(nl + 1) : part).replace(/\n$/, '');
  return `<div class="code"><div class="code-head"><span>${esc(lang || 'code')}</span>` +
    `<button type="button" class="icon-btn sm" data-action="copy-code" aria-label="Sao chép code">${icon('copy', 14)}</button></div>` +
    `<pre><code>${esc(body)}</code></pre></div>`;
}

export function renderMarkdown(src, kindOf) {
  return String(src || '').split('```').map((p, i) => (i % 2 ? code(p) : blocks(p, kindOf))).join('');
}
