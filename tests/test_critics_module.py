"""Tests for multimodal_gen.intelligence.critics — quality gate metrics."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from multimodal_gen.intelligence.critics import compute_vlc, compute_bkas, compute_adc


class TestVLC:
    def test_smooth_voice_leading_low_cost(self):
        """Stepwise voice leading should have VLC < 3.0."""
        voicings = [
            [60, 64, 67],  # C major
            [60, 64, 69],  # Am (common tones + step)
            [60, 65, 69],  # F major
            [59, 65, 67],  # G7 (partial)
        ]
        result = compute_vlc(voicings)
        assert result.value < 3.0
        assert result.passed is True

    def test_large_jumps_high_cost(self):
        """Octave jumps should produce high VLC."""
        voicings = [
            [48, 55, 60],
            [72, 76, 79],  # Jump up ~2 octaves
        ]
        result = compute_vlc(voicings)
        assert result.value > 5.0

    def test_single_voicing_trivial_pass(self):
        """A single voicing should trivially pass."""
        result = compute_vlc([[60, 64, 67]])
        assert result.passed is True
        assert result.value == 0.0

    def test_vlc_empty_list(self):
        """Empty voicing list should return a trivial pass."""
        result = compute_vlc([])
        assert result.passed is True
        assert result.value == 0.0

    def test_vlc_single_voicing_result(self):
        """Single voicing should return a CriticResult."""
        result = compute_vlc([[60, 64, 67]])
        assert result.name == "VLC"
        assert isinstance(result.value, float)

    def test_vlc_empty_voicing_skipped(self):
        """Empty voicings in list should be skipped, not crash."""
        result = compute_vlc([[], [60, 64, 67]])
        assert result.passed is True
        assert result.value == 0.0


class TestBKAS:
    def test_aligned_bass_kick(self):
        """Bass notes on kick hits should score > 0.7."""
        kick_ticks = [0, 480, 960, 1440]
        bass_notes = [{"tick": t} for t in [0, 480, 960, 1440]]
        result = compute_bkas(bass_notes, kick_ticks, tolerance_ticks=48)
        assert result.value > 0.9

    def test_misaligned_bass_kick(self):
        """Bass notes off-beat from kicks should score low."""
        kick_ticks = [0, 480, 960, 1440]
        bass_notes = [{"tick": t} for t in [240, 720, 1200]]
        result = compute_bkas(bass_notes, kick_ticks, tolerance_ticks=48)
        assert result.value < 0.5

    def test_bkas_empty_bass(self):
        """Empty bass notes with kicks should return CriticResult."""
        result = compute_bkas([], [0, 480], 48)
        assert isinstance(result, type(compute_bkas([], [], 48)))
        assert result.name == "BKAS"

    def test_bkas_empty_kicks(self):
        """Empty kicks should return trivial pass CriticResult."""
        result = compute_bkas([{"tick": 0}, {"tick": 480}], [], 48)
        assert result.passed is True
        assert result.value == 1.0


class TestADC:
    def test_correlated_density_tension(self):
        """Density that follows tension should score high."""
        tension = [0.2, 0.4, 0.6, 0.8, 1.0]
        density = [1.0, 2.0, 3.0, 4.0, 5.0]
        result = compute_adc(tension, density)
        assert result.value > 0.8

    def test_uncorrelated_low_score(self):
        """Flat density against rising tension should have low correlation."""
        tension = [0.2, 0.4, 0.6, 0.8, 1.0]
        density = [3.0, 3.0, 3.0, 3.0, 3.0]
        result = compute_adc(tension, density)
        assert result.value < 0.1
