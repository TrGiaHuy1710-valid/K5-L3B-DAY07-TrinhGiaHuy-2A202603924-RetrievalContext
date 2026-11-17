# Auto proxies — test2 / mm_hybrid_v3 / gemini/gemini-3.5-flash-lite

| Group | N | context has gold | cites gold | abstain | errors | inspect calls |
|---|---|---|---|---|---|---|
| table | 6 | 6 | 4 | 0 | 0 | 5 |
| image | 5 | 5 | 4 | 0 | 0 | 4 |
| chart | 5 | 4 | 4 | 1 | 0 | 5 |
| multihop | 4 | 4 | 4 | 0 | 0 | 4 |
| text | 4 | 3 | 3 | 0 | 0 | 0 |
| unanswerable | 6 | - | - | 2 | 0 | 3 |

Latency {'median': 6.8, 'max': 68.29}, LLM tokens {'prompt': 476556, 'completion': 12831}, inspect_visual tokens 24414, cost None. Errors: none.
Pass/fail is decided by reading each answer against the original page (labels.json).
