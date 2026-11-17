# Auto proxies — dev / text_hybrid / gemini/gemini-3.5-flash-lite

| Group | N | context has gold | cites gold | abstain | errors | inspect calls |
|---|---|---|---|---|---|---|
| table | 3 | 3 | 2 | 0 | 0 | 0 |
| image | 3 | 3 | 3 | 0 | 0 | 0 |
| chart | 3 | 3 | 3 | 0 | 0 | 0 |
| multihop | 3 | 2 | 2 | 0 | 0 | 0 |
| text | 3 | 3 | 3 | 0 | 0 | 0 |
| unanswerable | 3 | - | - | 3 | 0 | 0 |

Latency {'median': 5.7, 'max': 24.6}, LLM tokens {'prompt': 162799, 'completion': 5072}, inspect_visual tokens 0, cost None. Errors: none.
Pass/fail is decided by reading each answer against the original page (labels.json).
