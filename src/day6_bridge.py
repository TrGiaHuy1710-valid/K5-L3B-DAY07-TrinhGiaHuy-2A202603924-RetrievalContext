"""Bridge to the Day 6 lab: reuse its e5 embedder and the pgvector table `book_chunks`.

Day 6 and Day 7 are separate repos, so the Day 6 `starter/` folder is put on sys.path.
Override the location with env DAY6_STARTER. Run Python with the conda env `robot`.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

DAY7 = Path(__file__).resolve().parent.parent
DAY6_STARTER = Path(os.getenv("DAY6_STARTER") or DAY7.parent / "K5-L3B-DAY06-TrinhGiaHuy-2A202603924-DataIngestion" / "starter")  # empty = unset


def _load_day6():
    """Load Day 6's `src` package under the name `day6src` (both repos have a package called `src`)."""
    import importlib
    import importlib.util
    if "day6src" in sys.modules:
        return sys.modules["day6src"]
    pkg_dir = DAY6_STARTER / "src"
    if not (pkg_dir / "book_store.py").exists():
        raise FileNotFoundError(f"Day 6 starter not found at {DAY6_STARTER}; set DAY6_STARTER")
    spec = importlib.util.spec_from_file_location("day6src", pkg_dir / "__init__.py", submodule_search_locations=[str(pkg_dir)])
    module = importlib.util.module_from_spec(spec)
    sys.modules["day6src"] = module
    spec.loader.exec_module(module)
    return module


def connect():
    """Return (embedder, store). Raises on any connection/model problem; never falls back to a mock."""
    import importlib
    _load_day6()
    BookStore = importlib.import_module("day6src.book_store").BookStore
    make_embedder = importlib.import_module("day6src.embeddings").make_embedder
    database_url_from_env = importlib.import_module("day6src.store").database_url_from_env
    embedder = make_embedder()
    store = BookStore(database_url_from_env(), embedder.dimensions, embedder.model_name)
    return embedder, store
