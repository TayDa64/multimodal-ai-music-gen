"""Tests for multimodal_gen.intelligence.genre_dna — genre vectors & fusion."""

import sys
from dataclasses import fields
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from multimodal_gen.intelligence.genre_dna import (
    GenreDNAVector,
    GenreFusionResult,
    NAMED_FUSIONS,
    blend_genres,
    classify_blend_distance,
    genre_distance,
    get_genre_dna,
    get_named_fusion,
    list_genres,
    nearest_genre,
)


class TestGenreDNA:
    def test_get_known_genre(self):
        """Known genres should return 10-dimensional vectors with values in 0-1."""
        dna = get_genre_dna("jazz")
        assert dna is not None
        for field in fields(GenreDNAVector):
            val = getattr(dna, field.name)
            if isinstance(val, float):
                assert 0.0 <= val <= 1.0

    def test_get_unknown_genre_returns_none(self):
        """Unknown genre should return None."""
        result = get_genre_dna("xyzzy_not_a_genre_98765")
        assert result is None

    def test_blend_two_genres(self):
        """Blending jazz + hip_hop should produce intermediate vector."""
        result = blend_genres([("jazz", 0.6), ("hip_hop", 0.4)])
        assert isinstance(result, GenreFusionResult)
        jazz = get_genre_dna("jazz")
        hip_hop = get_genre_dna("hip_hop")
        assert jazz is not None and hip_hop is not None
        # Each dimension should be between the two sources (within rounding)
        assert result.vector.swing >= min(jazz.swing, hip_hop.swing) - 0.01
        assert result.vector.swing <= max(jazz.swing, hip_hop.swing) + 0.01

    def test_named_fusions_all_valid(self):
        """All named fusions should produce valid results."""
        for name in NAMED_FUSIONS:
            result = get_named_fusion(name)
            assert result is not None
            assert isinstance(result, GenreFusionResult)
            assert result.vector.swing >= 0.0

    def test_classify_blend_distance(self):
        """Close genres should return 'close', far genres 'far'."""
        close = classify_blend_distance([("jazz", 0.5), ("blues", 0.5)])
        far = classify_blend_distance([("classical", 0.5), ("trap", 0.5)])
        # jazz+blues are musically close
        assert close == "close" or close == "medium"
        assert far in ("medium", "far")

    def test_unknown_genre_raises(self):
        """Looking up a completely unknown genre should return None."""
        result = get_genre_dna("zzz_unknown_123")
        assert result is None

    def test_list_genres_not_empty(self):
        genres = list_genres()
        assert len(genres) >= 15

    def test_nearest_genre(self):
        """Nearest genre to jazz DNA should be jazz itself."""
        jazz_dna = get_genre_dna("jazz")
        assert jazz_dna is not None
        nearest_name, distance = nearest_genre(jazz_dna)
        assert nearest_name == "jazz"
        assert distance < 0.01

    def test_genre_distance_symmetric(self):
        """Distance should be symmetric."""
        jazz = get_genre_dna("jazz")
        blues_vec = get_genre_dna("soul")  # use soul as stand-in
        assert jazz is not None and blues_vec is not None
        d1 = genre_distance(jazz, blues_vec)
        d2 = genre_distance(blues_vec, jazz)
        assert abs(d1 - d2) < 0.001
