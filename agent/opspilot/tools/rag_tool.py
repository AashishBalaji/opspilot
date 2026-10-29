"""
Grounds a diagnosis in the target repo's own source, instead of asking
the LLM to guess from the failure message alone.

Design choice worth stating plainly: retrieval here is TF-IDF +
cosine similarity (scikit-learn), not a dense embedding model. A
production RAG system would likely use embeddings; TF-IDF is the
honest choice for THIS project because it's fully offline and
deterministic -- no embedding-model download, no external API call,
no non-determinism in CI -- while still being a real, explainable, and
widely-used retrieval baseline (hybrid search systems in production
often keep a lexical retriever like BM25/TF-IDF specifically for this
reason: it doesn't depend on a model being available or warm). It's a
genuine engineering trade-off, not a placeholder.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# Code/doc file types worth indexing; deliberately excludes binaries,
# lockfiles, and build output.
_INDEXABLE_EXTENSIONS = {
    ".py", ".ts", ".tsx", ".js", ".jsx", ".md", ".sql", ".yml", ".yaml",
    ".json", ".sh", ".tf", ".txt",
}
_SKIP_DIRS = {"node_modules", ".git", "dist", "build", "__pycache__", ".venv", "venv"}


@dataclass(frozen=True)
class RetrievedChunk:
    path: str
    text: str
    score: float


class RepoIndex:
    """A TF-IDF index over every indexable file under a repo root, chunked by file (not sub-file)."""

    def __init__(self, repo_root: str):
        self.repo_root = repo_root
        self._paths: list[str] = []
        self._texts: list[str] = []
        self._vectorizer: TfidfVectorizer | None = None
        self._matrix = None
        self._build()

    def _build(self) -> None:
        for dirpath, dirnames, filenames in os.walk(self.repo_root):
            dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]
            for filename in filenames:
                ext = os.path.splitext(filename)[1]
                if ext not in _INDEXABLE_EXTENSIONS:
                    continue
                full_path = os.path.join(dirpath, filename)
                try:
                    with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                except OSError:
                    continue
                if not content.strip():
                    continue
                self._paths.append(os.path.relpath(full_path, self.repo_root))
                self._texts.append(content)

        if not self._texts:
            return
        self._vectorizer = TfidfVectorizer(max_features=20_000, stop_words="english")
        self._matrix = self._vectorizer.fit_transform(self._texts)

    def query(self, text: str, top_k: int = 3) -> list[RetrievedChunk]:
        if self._vectorizer is None or self._matrix is None:
            return []
        query_vec = self._vectorizer.transform([text])
        scores = cosine_similarity(query_vec, self._matrix)[0]
        ranked = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
        results = []
        for i in ranked[:top_k]:
            if scores[i] <= 0:
                continue
            results.append(RetrievedChunk(path=self._paths[i], text=self._texts[i][:2000], score=float(scores[i])))
        return results
