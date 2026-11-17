# Agent `base` on dev — openrouter/openai/gpt-4o-mini

| Metric | Value |
|---|---|
| Tool use (search_book) | 17/17 (100%) |
| Context Evidence Rate | 3/15 (20%) |
| Cites a gold chunk (auto proxy) | 3/15 (20%) |
| Answers with citation | 7/7 (100%) |
| [chunk-id] written in answer | 2/7 (29%) |
| Abstention (unanswerable) | 2/2 (100%) |
| False abstention (answerable) | 8/15 (53%) |
| Invalid citations dropped | 0 |
| Book searches / case | {1: 8, 2: 5, 3: 4} |
| LLM calls / case | {2: 8, 3: 5, 4: 3, 5: 1} |
| Avg context chars | 511.9 |
| Latency s (median / max) | {'median': 4.02, 'max': 16.82} |
| Tokens | {'prompt': 43101, 'completion': 1966} |
| Cost USD | 0.0074 |
| Provider errors | 0 |
| Context misses | d02, d03, d04, d06, d07, d08, d09, d10, d11, d12, d14, d15 |
| False abstain | d03, d04, d07, d09, d10, d11, d12, d14 |
| Answered unanswerable | - |

Automatic only. Answer grade and citation support must be read and labelled by a human (reviews.json).
