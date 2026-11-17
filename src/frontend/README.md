# RAG Workbench (frontend)

Minimal UI for the Day 7 agent: chat with `book_ML.pdf`, inspect evidence on the original PDF, and read the full agent trace.

## Run

```bash
# from the Day 7 repo root, conda env `robot`; Postgres (Day 6 docker) must be up
python -m src.api                 # -> http://127.0.0.1:8765 (if busy: next free port, printed at start)
python -m src.api --port 8800     # choose a port (error if that port is busy; no silent switch)
```

No build step and no `npm install`: plain HTML/CSS/ES modules served by the backend. (The npm registry and package CDNs are not reachable from the dev network, so React/PDF.js/KaTeX were not used.) Optional env: `PORT`, `HOST`, `BOOK_PDF`.

## Architecture

| Layer | File | Role |
|---|---|---|
| HTTP adapter | `src/api.py` | Thin FastAPI layer over the existing `BookAgent`, retrievers and `LLMClient`; caches the e5 model / BM25 index, serialises runs. No RAG logic. |
| ChatLayout | `js/main.js` | State, persistence, event wiring |
| LocalConversationStore | `js/store.js` | Conversations + full traces in IndexedDB; UI settings and theme in localStorage (no keys) |
| ConversationSidebar | `js/ui/sidebar.js` | New / search / group by date / rename / delete |
| ChatWindow, ChatMessage | `js/ui/chat.js`, `js/markdown.js` | Messages, safe Markdown, citation chips, sources, status, copy / regenerate / cancel |
| RetrievalConfig, ProviderSelector | `js/ui/config.js` | Options from `GET /api/config` |
| EvidenceInspector | `js/ui/evidence.js` | Retrieved vs in-context vs cited chunks |
| TraceInspector | `js/ui/trace.js` | Timeline rebuilt from the recorded trace events |
| PdfViewer, CitationHighlight | `js/ui/pdfviewer.js` | Page images + exact highlight boxes from the backend |

### API (all real, see `src/api.py`)

| Method | Path | Returns |
|---|---|---|
| GET | `/api/health` | chunk count, pgvector row count / DB error |
| GET | `/api/config` | retrievers, providers (availability only), presets, limits, chapters, PDF page count |
| POST | `/api/chat` | `{trace, chunks, error_kind}`; `trace` is exactly `BookAgent.run()` output |
| GET | `/api/pdf` | original PDF |
| GET | `/api/pdf/page/{n}.png?scale=` | page rendered by PyMuPDF |
| GET | `/api/pdf/page/{n}/locate?chunk_id=` | character boxes of each chunk on the page, or `found:false` + reason |

## Honesty rules implemented

- **No "Grounded" badge.** The backend only checks that cited chunk IDs are in the context; it does not judge support. Answers are labelled *“Có trích dẫn · chưa kiểm chứng”*; abstentions *Insufficient evidence*; failures *Error · kind* (provider / database / setup / agent / network / cancelled / interrupted).
- Citations the model wrote but the backend dropped (not in context) are shown struck-through in red.
- Highlights come from the PDF's own characters (the same extraction that produced the chunks): 881/881 chunks match exactly. If a match fails, nothing is drawn and the excerpt is shown.
- Trace fields that were not recorded are omitted, never filled in. Failed runs keep their trace; a page reload during a request marks the message *interrupted*.
- API keys never reach the browser; `/api/config` only says whether a key is configured.

## Known gaps (not faked)

- **No streaming**: the agent API is request/response; the UI shows a live elapsed timer and a cancel button (cancel stops waiting in the browser; the backend finishes that run).
- **Claude provider**: not in `src/llm.py`, so not offered. OpenAI is listed but disabled until `OPENAI_API_KEY` is set. Ollama needs the model pulled (`ollama pull qwen2.5:7b`) or `LLM_MODEL` set.
- **Evidence highlight = chunk span**, not a gold evidence sentence: at runtime there is no gold label.
- **Math** is shown as raw LaTeX in code style (no KaTeX offline).
- One request at a time (the backend serialises agent runs; the e5 model is shared).
