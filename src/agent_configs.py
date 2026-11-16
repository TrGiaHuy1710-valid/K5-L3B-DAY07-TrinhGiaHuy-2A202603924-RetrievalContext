"""Named agent configurations. Each is benchmarked separately on dev (stage 4); add new ones here.

base          starter-like: dense top-3, 800-char total context (≈ one chunk), 3 book searches.
hybrid_b2400  best retrieval from stage 2 (hybrid RRF dense + BM25 syllable bigrams, Hit@10 15/15),
              5 candidates per search, at most 3 new chunks per search, 2400-char total context.
"""
from src.agent import AgentConfig

CONFIGS: dict[str, AgentConfig] = {
    "base": AgentConfig(name="base", retriever="dense", top_k=3, budget_chars=800, max_new_per_search=3,
                        max_book_searches=3, max_steps=6),
    "hybrid_b2400": AgentConfig(name="hybrid_b2400", retriever="hybrid_2gram", top_k=5, budget_chars=2400,
                                max_new_per_search=3, max_book_searches=3, max_steps=6),
}
