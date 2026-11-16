# Retrieval benchmark — split `dev` (answerable questions only)

| Method | Hit@1 | Evidence Hit@3 | Hit@10 | MRR@10 | Ctx@800 | Ctx@2400 | median ms | cost | misses@3 |
|---|---|---|---|---|---|---|---|---|---|
| tfidf | 6/15 (40%) | 10/15 (67%) | 14/15 (93%) | 0.548 | 4/15 (27%) | 9/15 (60%) | 5.6 | 0.0 | d01, d06, d07, d13, d14 |
| bm25 | 8/15 (53%) | 10/15 (67%) | 15/15 (100%) | 0.656 | 2/15 (13%) | 10/15 (67%) | 5.5 | 0.0 | d01, d05, d12, d13, d14 |
| bm25_2gram | 10/15 (67%) | 13/15 (87%) | 15/15 (100%) | 0.786 | 5/15 (33%) | 13/15 (87%) | 5.5 | 0.0 | d12, d14 |
| dense | 11/15 (73%) | 14/15 (93%) | 14/15 (93%) | 0.811 | 6/15 (40%) | 13/15 (87%) | 61.5 | 0.0 | d11 |
| hybrid | 9/15 (60%) | 14/15 (93%) | 15/15 (100%) | 0.756 | 6/15 (40%) | 13/15 (87%) | 79.0 | 0.0 | d14 |
| hybrid_2gram | 10/15 (67%) | 14/15 (93%) | 15/15 (100%) | 0.802 | 6/15 (40%) | 13/15 (87%) | 82.3 | 0.0 | d14 |

Ctx@B = gold evidence present in the top-3 packed into B characters (starter `pack_context`).
Filter from the question applied: True. Same chunks.json / pgvector index for every method.
