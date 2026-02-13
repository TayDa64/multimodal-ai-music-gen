"""
Embedding Index & Semantic Search for MPC Beats Assets (Sprint 4, Tasks 4.1 + 4.2)

Provides 384-dim text embeddings via dual approach:
  1. ONNX-based (all-MiniLM-L6-v2) when onnxruntime + model files available
  2. TF-IDF fallback using numpy only (always available)

Key components:
  - EmbeddingService  — generates 384-dim L2-normalised text vectors
  - AssetEmbedding    — dataclass: id, type, name, description, vector, metadata
  - VectorIndex       — brute-force cosine-similarity index over AssetEmbeddings
  - SearchResult      — dataclass returned by search queries
  - search_assets()   — cross-modal semantic search with re-ranking
  - build_embedding_index() — build / incrementally update the index
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import numpy as np

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_EMBEDDING_DIM = 384
_DEFAULT_MODEL_NAME = "all-MiniLM-L6-v2"
_DEFAULT_MODEL_DIR = "data/models/all-MiniLM-L6-v2"

# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class AssetEmbedding:
    """A single indexed asset with its embedding vector."""

    id: str  # e.g. "progression:Godly", "preset:RhodesBallad"
    asset_type: str  # "progression", "arp", "preset", "effect"
    name: str
    description: str  # 50-100 word text description
    vector: np.ndarray  # 384-dim L2-normalised
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SearchResult:
    """Single result returned by search queries."""

    id: str
    name: str
    asset_type: str
    similarity: float  # 0.0–1.0 cosine similarity
    description: str
    metadata: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Cosine similarity (trivial for L2-normalised vectors)
# ---------------------------------------------------------------------------


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine similarity between two L2-normalised vectors (= dot product)."""
    return float(np.dot(a, b))


# ---------------------------------------------------------------------------
# TF-IDF Fallback Embedder
# ---------------------------------------------------------------------------


class _TFIDFEmbedder:
    """Lightweight TF-IDF-like embedder that produces 384-dim vectors using
    only numpy.  Vocabulary is built lazily from indexed text.

    The approach:
      1. Tokenise text → lowercased word tokens.
      2. Hash each token to a dimension in [0, 384) to build a
         term-frequency vector.
      3. Weight by IDF (log inverse document frequency) when a corpus
         vocabulary is available.
      4. L2-normalise to unit length.
    """

    def __init__(self, dimensions: int = _EMBEDDING_DIM) -> None:
        self.dimensions = dimensions
        # Corpus-level IDF weights (token → idf).  Populated by fit().
        self._idf: Dict[str, float] = {}
        self._fitted = False

    # -- public API --------------------------------------------------------

    def fit(self, documents: Sequence[str]) -> None:
        """Compute IDF weights from a corpus of documents."""
        n_docs = len(documents)
        if n_docs == 0:
            return

        doc_freq: Dict[str, int] = {}
        for doc in documents:
            tokens = set(self._tokenise(doc))
            for tok in tokens:
                doc_freq[tok] = doc_freq.get(tok, 0) + 1

        self._idf = {
            tok: math.log((1 + n_docs) / (1 + df)) + 1.0
            for tok, df in doc_freq.items()
        }
        self._fitted = True

    def embed(self, text: str) -> np.ndarray:
        """Return a 384-dim L2-normalised vector for *text*."""
        tokens = self._tokenise(text)
        vec = np.zeros(self.dimensions, dtype=np.float32)

        # Term-frequency accumulation
        tf: Dict[str, int] = {}
        for tok in tokens:
            tf[tok] = tf.get(tok, 0) + 1

        for tok, count in tf.items():
            dim = self._hash_to_dim(tok)
            idf = self._idf.get(tok, 1.0)
            vec[dim] += count * idf

        # L2 normalise
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec /= norm
        return vec

    def embed_batch(self, texts: List[str]) -> List[np.ndarray]:
        return [self.embed(t) for t in texts]

    # -- internals ---------------------------------------------------------

    @staticmethod
    def _tokenise(text: str) -> List[str]:
        """Simple whitespace + punctuation tokeniser."""
        text = text.lower()
        tokens = re.findall(r"[a-z0-9]+", text)
        return tokens

    def _hash_to_dim(self, token: str) -> int:
        """Deterministically map a token to a dimension index."""
        h = int(hashlib.md5(token.encode("utf-8")).hexdigest(), 16)
        return h % self.dimensions


# ---------------------------------------------------------------------------
# ONNX Embedder (optional)
# ---------------------------------------------------------------------------


class _ONNXEmbedder:
    """Embedding via the all-MiniLM-L6-v2 ONNX model.

    Requires:
      - ``onnxruntime`` Python package
      - Model files at *model_dir*:  ``model.onnx`` + ``vocab.txt``
    """

    def __init__(self, model_dir: str) -> None:
        import onnxruntime as ort  # type: ignore[import-untyped]

        model_path = os.path.join(model_dir, "model.onnx")
        vocab_path = os.path.join(model_dir, "vocab.txt")

        if not os.path.isfile(model_path):
            raise FileNotFoundError(f"ONNX model not found: {model_path}")
        if not os.path.isfile(vocab_path):
            raise FileNotFoundError(f"Vocab file not found: {vocab_path}")

        self._session = ort.InferenceSession(
            model_path,
            providers=["CPUExecutionProvider"],
        )

        # Load vocabulary for WordPiece tokenisation
        with open(vocab_path, "r", encoding="utf-8") as fh:
            self._vocab: Dict[str, int] = {
                line.strip(): idx for idx, line in enumerate(fh)
            }
        self._inv_vocab: Dict[int, str] = {v: k for k, v in self._vocab.items()}

        # Special token IDs
        self._cls_id = self._vocab.get("[CLS]", 101)
        self._sep_id = self._vocab.get("[SEP]", 102)
        self._unk_id = self._vocab.get("[UNK]", 100)
        self._pad_id = self._vocab.get("[PAD]", 0)
        self._max_len = 128

        logger.info("ONNX embedder loaded from %s", model_dir)

    # -- public API --------------------------------------------------------

    def embed(self, text: str) -> np.ndarray:
        """Return a 384-dim L2-normalised vector."""
        input_ids, attention_mask, token_type_ids = self._tokenise(text)
        outputs = self._session.run(
            None,
            {
                "input_ids": input_ids,
                "attention_mask": attention_mask,
                "token_type_ids": token_type_ids,
            },
        )
        # outputs[0] shape: (1, seq_len, 384) — mean-pool over seq dim
        token_embeddings = outputs[0]  # (1, seq_len, hidden)
        mask_expanded = attention_mask[..., np.newaxis].astype(np.float32)
        summed = np.sum(token_embeddings * mask_expanded, axis=1)
        counts = np.clip(mask_expanded.sum(axis=1), a_min=1e-9, a_max=None)
        mean_pooled = summed / counts  # (1, 384)
        vec = mean_pooled[0].astype(np.float32)

        # L2 normalise
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec /= norm
        return vec

    def embed_batch(self, texts: List[str]) -> List[np.ndarray]:
        return [self.embed(t) for t in texts]

    # -- WordPiece tokeniser (minimal) ------------------------------------

    def _tokenise(self, text: str):
        """Minimal WordPiece tokenisation compatible with BERT-style models."""
        text = text.lower().strip()
        words = re.findall(r"[a-z0-9]+|[^\sa-z0-9]", text)

        token_ids: List[int] = [self._cls_id]
        for word in words:
            sub_tokens = self._wordpiece(word)
            token_ids.extend(sub_tokens)
            if len(token_ids) >= self._max_len - 1:
                break
        token_ids.append(self._sep_id)

        # Pad / truncate
        seq_len = min(len(token_ids), self._max_len)
        token_ids = token_ids[:seq_len]
        attention = [1] * seq_len
        token_type = [0] * seq_len

        pad_len = self._max_len - seq_len
        token_ids += [self._pad_id] * pad_len
        attention += [0] * pad_len
        token_type += [0] * pad_len

        return (
            np.array([token_ids], dtype=np.int64),
            np.array([attention], dtype=np.int64),
            np.array([token_type], dtype=np.int64),
        )

    def _wordpiece(self, word: str) -> List[int]:
        """Break a word into WordPiece sub-tokens."""
        if word in self._vocab:
            return [self._vocab[word]]

        tokens: List[int] = []
        start = 0
        while start < len(word):
            end = len(word)
            found = False
            while start < end:
                substr = word[start:end]
                if start > 0:
                    substr = "##" + substr
                if substr in self._vocab:
                    tokens.append(self._vocab[substr])
                    found = True
                    break
                end -= 1
            if not found:
                tokens.append(self._unk_id)
                start += 1
            else:
                start = end
        return tokens


# ---------------------------------------------------------------------------
# EmbeddingService (dual approach)
# ---------------------------------------------------------------------------


class EmbeddingService:
    """Generates 384-dim text embeddings.

    Uses all-MiniLM-L6-v2 (ONNX) when available, otherwise falls back
    to a TF-IDF hashing approach that uses only numpy.
    """

    def __init__(self, model_dir: str | None = None) -> None:
        self._onnx_embedder: Optional[_ONNXEmbedder] = None
        self._tfidf_embedder: Optional[_TFIDFEmbedder] = None

        # Try ONNX first
        if model_dir is None:
            model_dir = _DEFAULT_MODEL_DIR

        try:
            self._onnx_embedder = _ONNXEmbedder(model_dir)
            logger.info("EmbeddingService: using ONNX backend")
        except Exception as exc:
            logger.info("EmbeddingService: ONNX unavailable (%s), using TF-IDF fallback", exc)
            self._tfidf_embedder = _TFIDFEmbedder(_EMBEDDING_DIM)

    # -- public API --------------------------------------------------------

    def embed(self, text: str) -> np.ndarray:
        """Return a 384-dim L2-normalised vector for *text*."""
        if self._onnx_embedder is not None:
            return self._onnx_embedder.embed(text)
        assert self._tfidf_embedder is not None
        return self._tfidf_embedder.embed(text)

    def embed_batch(self, texts: List[str]) -> List[np.ndarray]:
        """Embed a list of texts."""
        if self._onnx_embedder is not None:
            return self._onnx_embedder.embed_batch(texts)
        assert self._tfidf_embedder is not None
        return self._tfidf_embedder.embed_batch(texts)

    def fit_tfidf(self, documents: Sequence[str]) -> None:
        """Fit the TF-IDF vocabulary (no-op when using ONNX)."""
        if self._tfidf_embedder is not None:
            self._tfidf_embedder.fit(documents)

    @property
    def is_onnx(self) -> bool:
        """Whether the service is using the ONNX model."""
        return self._onnx_embedder is not None

    @property
    def dimensions(self) -> int:
        """Embedding dimensionality (always 384)."""
        return _EMBEDDING_DIM


# ---------------------------------------------------------------------------
# VectorIndex
# ---------------------------------------------------------------------------


class VectorIndex:
    """In-memory brute-force cosine similarity index over AssetEmbeddings.

    At ~600 entries × 384 dims × 4 bytes ≈ 900 KB — trivially small for
    brute-force search.
    """

    def __init__(
        self,
        model: str = _DEFAULT_MODEL_NAME,
        dimensions: int = _EMBEDDING_DIM,
    ) -> None:
        self.model = model
        self._dimensions = dimensions
        self._entries: Dict[str, AssetEmbedding] = {}

    # -- mutators ----------------------------------------------------------

    def add_entry(self, entry: AssetEmbedding) -> None:
        """Add or overwrite an embedding entry."""
        self._entries[entry.id] = entry

    def add_entries(self, entries: List[AssetEmbedding]) -> None:
        """Add multiple entries at once."""
        for entry in entries:
            self._entries[entry.id] = entry

    def remove_entry(self, id: str) -> bool:
        """Remove an entry by id.  Returns True if it existed."""
        return self._entries.pop(id, None) is not None

    # -- queries -----------------------------------------------------------

    def get_entry(self, id: str) -> Optional[AssetEmbedding]:
        """Retrieve a single entry by id, or None."""
        return self._entries.get(id)

    def search(
        self,
        query_vector: np.ndarray,
        top_k: int = 10,
        type_filter: Optional[List[str]] = None,
        min_similarity: float = 0.0,
    ) -> List[SearchResult]:
        """Brute-force cosine search.

        Args:
            query_vector: 384-dim L2-normalised query.
            top_k: Maximum results to return.
            type_filter: If given, only include these asset types.
            min_similarity: Floor threshold (0.0–1.0).

        Returns:
            List of SearchResult ordered by descending similarity.
        """
        if not self._entries:
            return []

        candidates = self._entries.values()
        if type_filter:
            filter_set = set(type_filter)
            candidates = [e for e in candidates if e.asset_type in filter_set]

        scored: List[tuple[float, AssetEmbedding]] = []
        for entry in candidates:
            sim = cosine_similarity(query_vector, entry.vector)
            if sim >= min_similarity:
                scored.append((sim, entry))

        # Sort descending by similarity
        scored.sort(key=lambda x: x[0], reverse=True)

        results: List[SearchResult] = []
        for sim, entry in scored[:top_k]:
            results.append(
                SearchResult(
                    id=entry.id,
                    name=entry.name,
                    asset_type=entry.asset_type,
                    similarity=round(sim, 6),
                    description=entry.description,
                    metadata=entry.metadata,
                )
            )
        return results

    @property
    def size(self) -> int:
        """Number of entries in the index."""
        return len(self._entries)

    # -- serialisation -----------------------------------------------------

    def serialize(self) -> dict:
        """Serialise the full index to a JSON-safe dict."""
        entries_data = []
        for entry in self._entries.values():
            entries_data.append({
                "id": entry.id,
                "asset_type": entry.asset_type,
                "name": entry.name,
                "description": entry.description,
                "vector": entry.vector.tolist(),
                "metadata": entry.metadata,
            })
        return {
            "model": self.model,
            "dimensions": self._dimensions,
            "entries": entries_data,
        }

    @classmethod
    def deserialize(cls, data: dict) -> "VectorIndex":
        """Reconstruct a VectorIndex from a serialised dict."""
        index = cls(
            model=data.get("model", _DEFAULT_MODEL_NAME),
            dimensions=data.get("dimensions", _EMBEDDING_DIM),
        )
        for item in data.get("entries", []):
            entry = AssetEmbedding(
                id=item["id"],
                asset_type=item["asset_type"],
                name=item["name"],
                description=item["description"],
                vector=np.array(item["vector"], dtype=np.float32),
                metadata=item.get("metadata", {}),
            )
            index.add_entry(entry)
        return index

    def save(self, path: str) -> None:
        """Persist the index to a JSON file."""
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8") as fh:
            json.dump(self.serialize(), fh, ensure_ascii=False)
        logger.info("VectorIndex saved to %s (%d entries)", path, self.size)

    @classmethod
    def load(cls, path: str) -> "VectorIndex":
        """Load a VectorIndex from a JSON file."""
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        index = cls.deserialize(data)
        logger.info("VectorIndex loaded from %s (%d entries)", path, index.size)
        return index


# ---------------------------------------------------------------------------
# Semantic Search (Task 4.2)
# ---------------------------------------------------------------------------


def search_assets(
    query: str,
    index: VectorIndex,
    embedding_service: EmbeddingService,
    top_k: int = 10,
    type_filter: Optional[List[str]] = None,
    genre: Optional[str] = None,
    min_similarity: float = 0.0,
    context_boost: Optional[Dict[str, Any]] = None,
) -> List[SearchResult]:
    """Cross-modal semantic search.

    Embeds the query, searches the index, and optionally re-ranks by
    genre affinity or song-state context.

    Args:
        query: Natural-language search string.
        index: Populated VectorIndex.
        embedding_service: EmbeddingService instance.
        top_k: Max results.
        type_filter: Restrict to these asset types.
        genre: If given, boost results whose metadata.genre matches.
        min_similarity: Floor threshold.
        context_boost: Optional dict with ``genre_bias`` (float 0-1) and/or
            ``song_state`` (dict with current key/tempo/energy).

    Returns:
        Ordered list of SearchResult.
    """
    query_vec = embedding_service.embed(query)
    results = index.search(
        query_vec,
        top_k=top_k * 3 if (genre or context_boost) else top_k,
        type_filter=type_filter,
        min_similarity=min_similarity,
    )

    # -- Genre re-ranking --------------------------------------------------
    if genre:
        genre_bias = 0.15
        if context_boost and "genre_bias" in context_boost:
            genre_bias = float(context_boost["genre_bias"])

        genre_lower = genre.lower()
        reranked: List[SearchResult] = []
        for r in results:
            meta_genre = str(r.metadata.get("genre", "")).lower()
            boost = genre_bias if meta_genre == genre_lower else 0.0
            reranked.append(
                SearchResult(
                    id=r.id,
                    name=r.name,
                    asset_type=r.asset_type,
                    similarity=round(min(r.similarity + boost, 1.0), 6),
                    description=r.description,
                    metadata=r.metadata,
                )
            )
        reranked.sort(key=lambda x: x.similarity, reverse=True)
        results = reranked

    # -- Context boost (song-state aware) ----------------------------------
    if context_boost and "song_state" in context_boost:
        song_state = context_boost["song_state"]
        target_key = str(song_state.get("key", "")).lower()
        if target_key:
            for r in results:
                entry_key = str(r.metadata.get("key", "")).lower()
                if entry_key == target_key:
                    r.similarity = round(min(r.similarity + 0.05, 1.0), 6)
            results.sort(key=lambda x: x.similarity, reverse=True)

    return results[:top_k]


# ---------------------------------------------------------------------------
# Index Builder
# ---------------------------------------------------------------------------


def build_embedding_index(
    descriptions: List[Dict[str, Any]],
    embedding_service: EmbeddingService,
    existing_index: Optional[VectorIndex] = None,
) -> VectorIndex:
    """Build or incrementally update the embedding index.

    Each item in *descriptions* must have keys:
      ``id``, ``type``, ``name``, ``description``, and optionally ``metadata``.

    When *existing_index* is supplied, new entries are merged into it
    (overwriting entries with the same id).

    Returns:
        Populated VectorIndex.
    """
    index = existing_index or VectorIndex()

    if not descriptions:
        return index

    # Fit TF-IDF vocabulary when using fallback
    all_texts = [d["description"] for d in descriptions if d.get("description")]
    embedding_service.fit_tfidf(all_texts)

    # Embed all descriptions
    texts = [d.get("description", d.get("name", "")) for d in descriptions]
    vectors = embedding_service.embed_batch(texts)

    for desc, vec in zip(descriptions, vectors):
        entry = AssetEmbedding(
            id=desc["id"],
            asset_type=desc.get("type", "unknown"),
            name=desc.get("name", ""),
            description=desc.get("description", ""),
            vector=vec,
            metadata=desc.get("metadata", {}),
        )
        index.add_entry(entry)

    logger.info(
        "build_embedding_index: indexed %d entries (total %d)",
        len(descriptions),
        index.size,
    )
    return index


# ---------------------------------------------------------------------------
# Built-in Descriptions Catalog (~30 representative MPC Beats assets)
# ---------------------------------------------------------------------------

_BUILTIN_DESCRIPTIONS: List[Dict[str, Any]] = [
    # ── Progressions ──────────────────────────────────────────────────────
    {
        "id": "progression:Godly",
        "type": "progression",
        "name": "Godly",
        "description": (
            "Gospel-influenced worship chord progression with rich extended "
            "voicings, major key, uplifting spiritual feel, building tension "
            "through suspension resolutions"
        ),
        "metadata": {"genre": "gospel", "key": "C", "scale": "major"},
    },
    {
        "id": "progression:Slow Praise",
        "type": "progression",
        "name": "Slow Praise",
        "description": (
            "Slow, devotional worship progression with warm sustained chords, "
            "gentle movement, meditative and peaceful atmosphere suitable for "
            "intimate worship settings"
        ),
        "metadata": {"genre": "gospel", "key": "Eb", "scale": "major"},
    },
    {
        "id": "progression:After Dark",
        "type": "progression",
        "name": "After Dark",
        "description": (
            "Dark moody R&B progression with minor key tension, late-night "
            "atmospheric feeling, smooth jazz-influenced extended chords with "
            "chromatic movement"
        ),
        "metadata": {"genre": "rnb", "key": "Am", "scale": "minor"},
    },
    {
        "id": "progression:Velvet",
        "type": "progression",
        "name": "Velvet",
        "description": (
            "Silky neo-soul progression with lush 9th and 13th chords, warm "
            "Rhodes-like harmonic palette, smooth voice leading and gentle "
            "rhythmic feel"
        ),
        "metadata": {"genre": "neo_soul", "key": "Db", "scale": "major"},
    },
    {
        "id": "progression:Late Registration",
        "type": "progression",
        "name": "Late Registration",
        "description": (
            "Soulful hip-hop progression with sampled soul chord stabs, "
            "Kanye-era orchestral grandeur, pitched vocal chops and warm "
            "analog texture"
        ),
        "metadata": {"genre": "hip_hop", "key": "Bb", "scale": "minor"},
    },
    {
        "id": "progression:Midnight Drive",
        "type": "progression",
        "name": "Midnight Drive",
        "description": (
            "Lo-fi chill hop progression with mellow jazzy chords, dusty "
            "vinyl warmth, tape-saturated piano over soft boom-bap drums"
        ),
        "metadata": {"genre": "lo_fi", "key": "F", "scale": "major"},
    },
    {
        "id": "progression:Trap Lord",
        "type": "progression",
        "name": "Trap Lord",
        "description": (
            "Dark aggressive trap progression with ominous minor key stabs, "
            "808 sub-bass harmonics, sparse haunting melody with heavy reverb "
            "and distortion"
        ),
        "metadata": {"genre": "trap", "key": "Cm", "scale": "minor"},
    },
    {
        "id": "progression:Sunset Strip",
        "type": "progression",
        "name": "Sunset Strip",
        "description": (
            "Bright funk-pop progression with tight rhythmic comping, "
            "major seventh chords, upbeat feel with muted guitar strum "
            "patterns and slap bass roots"
        ),
        "metadata": {"genre": "funk", "key": "E", "scale": "major"},
    },
    {
        "id": "progression:Blue Note",
        "type": "progression",
        "name": "Blue Note",
        "description": (
            "Classic jazz ballad progression with ii-V-I turnarounds, "
            "tritone substitutions, walking bass compatible, smoky late-night "
            "club atmosphere"
        ),
        "metadata": {"genre": "jazz", "key": "Bb", "scale": "major"},
    },
    {
        "id": "progression:Fire & Ice",
        "type": "progression",
        "name": "Fire & Ice",
        "description": (
            "House music progression with four-on-the-floor energy, uplifting "
            "major key filter sweeps, euphoric build-and-drop structure with "
            "pulsating synth pads"
        ),
        "metadata": {"genre": "house", "key": "G", "scale": "major"},
    },
    {
        "id": "progression:Saharan Wind",
        "type": "progression",
        "name": "Saharan Wind",
        "description": (
            "Ethio-jazz influenced progression with modal interchange, "
            "pentatonic melodies over minor chords, hypnotic circular "
            "harmonic movement inspired by Ethiopian scales"
        ),
        "metadata": {"genre": "ethio_jazz", "key": "D", "scale": "minor"},
    },
    {
        "id": "progression:Campfire",
        "type": "progression",
        "name": "Campfire",
        "description": (
            "Simple acoustic folk progression with open-string voicings, "
            "fingerpick-friendly shapes, heartfelt and warm singalong "
            "quality with gentle dynamics"
        ),
        "metadata": {"genre": "acoustic", "key": "G", "scale": "major"},
    },
    {
        "id": "progression:Neon Lights",
        "type": "progression",
        "name": "Neon Lights",
        "description": (
            "Synthwave retro-futuristic progression with arpeggiated analog "
            "pads, bright detuned saw chords, 80s nostalgia with modern "
            "production sheen"
        ),
        "metadata": {"genre": "synthwave", "key": "A", "scale": "minor"},
    },
    {
        "id": "progression:Island Breeze",
        "type": "progression",
        "name": "Island Breeze",
        "description": (
            "Reggae-influenced progression with off-beat chord skank rhythm, "
            "laid-back summer vibes, major key warmth with subtle dub delays"
        ),
        "metadata": {"genre": "reggae", "key": "C", "scale": "major"},
    },
    # ── Presets ────────────────────────────────────────────────────────────
    {
        "id": "preset:RhodesBallad",
        "type": "preset",
        "name": "Rhodes Ballad",
        "description": (
            "Warm Fender Rhodes electric piano with gentle tremolo, soft "
            "velocity curves, rich harmonic overtones ideal for slow ballads "
            "and neo-soul comping"
        ),
        "metadata": {"genre": "neo_soul", "category": "keys"},
    },
    {
        "id": "preset:AnalogPad",
        "type": "preset",
        "name": "Analog Pad",
        "description": (
            "Thick detuned analog synthesiser pad with slow attack, lush "
            "stereo chorus, warm low-pass filter sweep perfect for ambient "
            "textures and cinematic beds"
        ),
        "metadata": {"genre": "ambient", "category": "synth"},
    },
    {
        "id": "preset:808SubBass",
        "type": "preset",
        "name": "808 Sub Bass",
        "description": (
            "Deep 808 sub-bass with long sustain decay, sine wave fundamental "
            "with controlled distortion harmonics, essential for trap and "
            "hip-hop production"
        ),
        "metadata": {"genre": "trap", "category": "bass"},
    },
    {
        "id": "preset:AcousticGuitarFinger",
        "type": "preset",
        "name": "Acoustic Guitar Finger",
        "description": (
            "Natural steel-string acoustic guitar with fingerpicking "
            "articulation, warm body resonance, realistic fret noise and "
            "string release suitable for folk and singer-songwriter"
        ),
        "metadata": {"genre": "acoustic", "category": "guitar"},
    },
    {
        "id": "preset:VintageOrgan",
        "type": "preset",
        "name": "Vintage Organ",
        "description": (
            "Hammond B3-style drawbar organ with Leslie rotary speaker "
            "simulation, percussive click attack, gospel and jazz inspired "
            "warm overdriven tone"
        ),
        "metadata": {"genre": "gospel", "category": "keys"},
    },
    {
        "id": "preset:PluckSynth",
        "type": "preset",
        "name": "Pluck Synth",
        "description": (
            "Short snappy plucked synthesiser with fast decay envelope, "
            "bright resonant filter, suitable for arpeggiated house and "
            "EDM melodic hooks"
        ),
        "metadata": {"genre": "house", "category": "synth"},
    },
    # ── Effects ────────────────────────────────────────────────────────────
    {
        "id": "effect:TapeDelay",
        "type": "effect",
        "name": "Tape Delay",
        "description": (
            "Warm analog tape delay effect with wow and flutter modulation, "
            "high-frequency roll-off on repeats, dub reggae-style rhythmic "
            "echoes with feedback control"
        ),
        "metadata": {"category": "delay"},
    },
    {
        "id": "effect:HallReverb",
        "type": "effect",
        "name": "Hall Reverb",
        "description": (
            "Spacious concert hall reverb with long diffuse tail, smooth "
            "early reflections, adds depth and grandeur to vocals and "
            "orchestral instruments"
        ),
        "metadata": {"category": "reverb"},
    },
    {
        "id": "effect:VinylSaturation",
        "type": "effect",
        "name": "Vinyl Saturation",
        "description": (
            "Lo-fi vinyl crackle and warmth processor with subtle harmonic "
            "saturation, high-frequency roll-off, adds nostalgic dusty "
            "character to any source"
        ),
        "metadata": {"category": "saturation"},
    },
    {
        "id": "effect:SideChainPump",
        "type": "effect",
        "name": "Sidechain Pump",
        "description": (
            "Rhythmic sidechain compressor effect synced to kick drum, "
            "creates pumping ducking effect essential for EDM, house, and "
            "electronic dance music production"
        ),
        "metadata": {"category": "dynamics"},
    },
    # ── Arp Patterns ──────────────────────────────────────────────────────
    {
        "id": "arp:RisingTriad",
        "type": "arp",
        "name": "Rising Triad",
        "description": (
            "Ascending triad arpeggio pattern with even eighth-note rhythm, "
            "root-third-fifth sequence, bright upward energy suitable for "
            "trance and EDM builds"
        ),
        "metadata": {"direction": "up", "subdivision": "8th"},
    },
    {
        "id": "arp:FunkyChicken",
        "type": "arp",
        "name": "Funky Chicken",
        "description": (
            "Syncopated funk arpeggio with 16th-note ghost notes and "
            "accented off-beats, clavinet-style rhythmic picking, tight "
            "staccato articulation for groove-heavy tracks"
        ),
        "metadata": {"direction": "alternate", "subdivision": "16th"},
    },
    {
        "id": "arp:DreamSequence",
        "type": "arp",
        "name": "Dream Sequence",
        "description": (
            "Slow ambient arpeggio with wide interval leaps, sustained "
            "notes with reverb tails overlapping, ethereal pad-like quality "
            "for downtempo and chillout"
        ),
        "metadata": {"direction": "random", "subdivision": "quarter"},
    },
    {
        "id": "arp:TrapRoll",
        "type": "arp",
        "name": "Trap Roll",
        "description": (
            "Rapid hi-hat roll pattern with 32nd-note bursts and velocity "
            "ramps, classic trap build-up technique, switches between open "
            "and closed hat articulations"
        ),
        "metadata": {"direction": "up", "subdivision": "32nd"},
    },
    {
        "id": "arp:BossaNova",
        "type": "arp",
        "name": "Bossa Nova",
        "description": (
            "Classic bossa nova guitar picking pattern with syncopated "
            "thumb-and-finger independence, gentle Brazilian rhythm, "
            "alternating bass notes with upper chord tones"
        ),
        "metadata": {"direction": "alternate", "subdivision": "8th"},
    },
    {
        "id": "arp:GospelRun",
        "type": "arp",
        "name": "Gospel Run",
        "description": (
            "Fast gospel piano run pattern with chromatic approach tones, "
            "ascending and descending scalar fills, dynamic velocity "
            "crescendo building to a climactic chord resolution"
        ),
        "metadata": {"direction": "alternate", "subdivision": "16th"},
    },
]

# Convenience count
BUILTIN_DESCRIPTION_COUNT = len(_BUILTIN_DESCRIPTIONS)
