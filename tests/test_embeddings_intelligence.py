"""Tests for multimodal_gen.intelligence.embeddings — TF-IDF & vector search."""

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from multimodal_gen.intelligence.embeddings import (
    AssetEmbedding,
    EmbeddingService,
    VectorIndex,
    _BUILTIN_DESCRIPTIONS,
    build_embedding_index,
    search_assets,
)


class TestEmbeddingService:
    def test_tfidf_embed_returns_vector(self):
        """TF-IDF fallback should produce a 384-dim vector."""
        svc = EmbeddingService()
        svc.fit_tfidf(["warm chords", "dark bass", "bright melody"])
        vec = svc.embed("warm chords")
        assert len(vec) == 384
        assert isinstance(vec, (list, np.ndarray))

    def test_embed_batch(self):
        svc = EmbeddingService()
        texts = ["chord progression", "bass line", "drum pattern"]
        svc.fit_tfidf(texts)
        vecs = svc.embed_batch(texts)
        assert len(vecs) == 3


class TestVectorIndex:
    def test_add_and_search(self):
        svc = EmbeddingService()
        svc.fit_tfidf(["warm jazz chords", "hard trap bass"])
        idx = VectorIndex()
        idx.add_entry(AssetEmbedding(
            id="test1", asset_type="progression", name="Jazz Chords",
            description="warm jazz chords", vector=svc.embed("warm jazz chords"),
            metadata={},
        ))
        idx.add_entry(AssetEmbedding(
            id="test2", asset_type="preset", name="Trap Bass",
            description="hard trap bass", vector=svc.embed("hard trap bass"),
            metadata={},
        ))
        results = idx.search(svc.embed("warm jazz"), top_k=1)
        assert len(results) >= 1
        assert results[0].name == "Jazz Chords"


class TestSearchAssets:
    def test_builtin_search(self):
        """Search with builtin descriptions should find results."""
        svc = EmbeddingService()
        idx = build_embedding_index(_BUILTIN_DESCRIPTIONS, svc)
        results = search_assets("dark moody chords", idx, svc, top_k=3)
        assert len(results) >= 1
        assert results[0].similarity > 0.1
