# Agent `base` on test — openrouter/openai/gpt-4o-mini

| Metric | Value |
|---|---|
| Tool use (search_book) | 7/7 (100%) |
| Context Evidence Rate | 1/5 (20%) |
| Cites a gold chunk (auto proxy) | 1/5 (20%) |
| Answers with citation | 3/3 (100%) |
| [chunk-id] written in answer | 1/3 (33%) |
| Abstention (unanswerable) | 2/2 (100%) |
| False abstention (answerable) | 2/5 (40%) |
| Invalid citations dropped | 0 |
| Book searches / case | {1: 3, 2: 2, 3: 2} |
| LLM calls / case | {2: 2, 3: 3, 4: 2} |
| Avg context chars | 448.4 |
| Latency s (median / max) | {'median': 6.13, 'max': 27.74} |
| Tokens | {'prompt': 18884, 'completion': 940} |
| Cost USD | 0.00323 |
| Provider errors | 0 |
| Context misses | t01, t02, t03, t04 |
| False abstain | t02, t04 |
| Answered unanswerable | - |

Automatic only. Answer grade and citation support must be read and labelled by a human (reviews.json).
