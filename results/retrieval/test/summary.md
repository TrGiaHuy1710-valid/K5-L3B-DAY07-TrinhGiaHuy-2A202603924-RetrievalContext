# Retrieval benchmark — split `test` (answerable questions only)

| Method | Hit@1 | Evidence Hit@3 | Hit@10 | MRR@10 | Ctx@800 | Ctx@2400 | median ms | cost | misses@3 |
|---|---|---|---|---|---|---|---|---|---|
| tfidf | 2/5 (40%) | 2/5 (40%) | 2/5 (40%) | 0.4 | 1/5 (20%) | 2/5 (40%) | 8.0 | 0.0 | t01, t02, t04 |
| bm25 | 2/5 (40%) | 4/5 (80%) | 5/5 (100%) | 0.595 | 2/5 (40%) | 4/5 (80%) | 6.8 | 0.0 | t02 |
| bm25_2gram | 4/5 (80%) | 5/5 (100%) | 5/5 (100%) | 0.867 | 2/5 (40%) | 4/5 (80%) | 7.2 | 0.0 | - |
| dense | 3/5 (60%) | 4/5 (80%) | 4/5 (80%) | 0.7 | 2/5 (40%) | 4/5 (80%) | 66.1 | 0.0 | t02 |
| hybrid | 3/5 (60%) | 4/5 (80%) | 4/5 (80%) | 0.7 | 2/5 (40%) | 4/5 (80%) | 76.2 | 0.0 | t02 |
| hybrid_2gram | 4/5 (80%) | 4/5 (80%) | 4/5 (80%) | 0.8 | 2/5 (40%) | 4/5 (80%) | 63.9 | 0.0 | t02 |

Ctx@B = gold evidence present in the top-3 packed into B characters (starter `pack_context`).
Filter from the question applied: True. Same chunks.json / pgvector index for every method.
