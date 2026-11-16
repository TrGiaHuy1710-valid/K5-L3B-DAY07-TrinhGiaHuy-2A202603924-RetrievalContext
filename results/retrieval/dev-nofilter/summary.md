# Retrieval benchmark — split `dev` (answerable questions only)

| Method | Hit@1 | Evidence Hit@3 | Hit@10 | MRR@10 | Ctx@800 | Ctx@2400 | median ms | cost | misses@3 |
|---|---|---|---|---|---|---|---|---|---|
| tfidf | 6/15 (40%) | 10/15 (67%) | 13/15 (87%) | 0.54 | 4/15 (27%) | 9/15 (60%) | 6.8 | 0.0 | d01, d06, d07, d13, d14 |
| bm25 | 8/15 (53%) | 10/15 (67%) | 15/15 (100%) | 0.656 | 2/15 (13%) | 10/15 (67%) | 4.9 | 0.0 | d01, d05, d12, d13, d14 |
| bm25_2gram | 10/15 (67%) | 13/15 (87%) | 15/15 (100%) | 0.785 | 5/15 (33%) | 13/15 (87%) | 5.3 | 0.0 | d12, d14 |
| dense | 11/15 (73%) | 14/15 (93%) | 14/15 (93%) | 0.811 | 6/15 (40%) | 13/15 (87%) | 71.9 | 0.0 | d11 |
| hybrid | 9/15 (60%) | 14/15 (93%) | 15/15 (100%) | 0.756 | 6/15 (40%) | 13/15 (87%) | 84.6 | 0.0 | d14 |
| hybrid_2gram | 10/15 (67%) | 14/15 (93%) | 15/15 (100%) | 0.8 | 6/15 (40%) | 13/15 (87%) | 65.1 | 0.0 | d14 |

Ctx@B = gold evidence present in the top-3 packed into B characters (starter `pack_context`).
Filter from the question applied: False. Same chunks.json / pgvector index for every method.
