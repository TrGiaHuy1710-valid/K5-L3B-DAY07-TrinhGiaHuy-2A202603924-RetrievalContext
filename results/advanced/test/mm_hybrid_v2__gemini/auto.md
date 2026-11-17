# Auto proxies — test / mm_hybrid_v2 / gemini/gemini-3.5-flash-lite

| Group | N | context has gold | cites gold | abstain | errors | inspect calls |
|---|---|---|---|---|---|---|
| table | 6 | 6 | 3 | 0 | 0 | 5 |
| image | 5 | 5 | 5 | 0 | 0 | 3 |
| chart | 5 | 5 | 5 | 0 | 0 | 5 |
| multihop | 4 | 4 | 4 | 0 | 0 | 1 |
| text | 4 | 4 | 4 | 0 | 0 | 0 |
| unanswerable | 6 | - | - | 3 | 0 | 2 |

Latency {'median': 5.4, 'max': 59.14}, LLM tokens {'prompt': 346418, 'completion': 11240}, inspect_visual tokens 21734, cost None. Errors: none.
Pass/fail is decided by reading each answer against the original page (labels.json).
