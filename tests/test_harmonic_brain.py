"""Tests for multimodal_gen.intelligence.harmonic_brain — voice leading & tension."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from multimodal_gen.intelligence.harmonic_brain import HarmonicBrain, VoicingConstraints


class TestVoiceLeading:
    def test_first_chord_returns_valid_voicing(self):
        """First chord (no previous) should return valid MIDI pitches."""
        brain = HarmonicBrain()
        voicing = brain.voice_lead(None, "Cm7", "C")
        assert len(voicing) >= 3
        assert all(0 <= p <= 127 for p in voicing)
        # Pitch classes must be a subset of Cm7 = {C, Eb, G, Bb} = {0, 3, 7, 10}
        pitch_classes = {p % 12 for p in voicing}
        assert pitch_classes <= {0, 3, 7, 10}

    def test_common_tone_retention(self):
        """Voice leading should retain common tones between chords."""
        brain = HarmonicBrain()
        v1 = brain.voice_lead(None, "C", "C")
        v2 = brain.voice_lead(v1, "Am", "C")
        # C and Am share pitch class C (0) and E (4)
        pcs1 = set(p % 12 for p in v1)
        pcs2 = set(p % 12 for p in v2)
        assert len(pcs1 & pcs2) >= 1

    def test_voice_leading_cost_decreases(self):
        """Voice-led progression should have low average movement."""
        brain = HarmonicBrain()
        symbols = ["Cm", "Fm", "AbMaj7", "G7"]
        voiced = brain.voice_lead_progression(symbols, "C")
        assert len(voiced) == 4
        total_movement = 0
        for i in range(1, len(voiced)):
            prev = voiced[i - 1].midi_notes
            curr = voiced[i].midi_notes
            for j in range(min(len(prev), len(curr))):
                total_movement += abs(prev[j] - curr[j])
        n_voices = min(len(voiced[0].midi_notes), 3)
        avg = total_movement / (max(n_voices, 1) * (len(voiced) - 1))
        assert avg < 5.0

    def test_generate_progression_returns_chord_symbols(self):
        """Generate progression should return valid chord symbol strings."""
        brain = HarmonicBrain()
        chords = brain.generate_progression("C", "minor", length=4)
        assert len(chords) == 4
        assert all(isinstance(c, str) for c in chords)
        # Each chord must start with a valid root note name
        for chord in chords:
            assert chord[0] in "ABCDEFG"

    def test_invalid_chord_raises(self):
        """Invalid chord symbol should raise ValueError."""
        brain = HarmonicBrain()
        with pytest.raises(ValueError):
            brain.voice_lead(None, "Xzz#99", "C")

    def test_empty_progression(self):
        """Empty chord list should return empty voiced list."""
        brain = HarmonicBrain()
        result = brain.voice_lead_progression([], "C")
        assert result == []


class TestComputeTension:
    def test_consonant_chord_low_tension(self):
        """C major triad in C should have low tension."""
        brain = HarmonicBrain()
        tension = brain.compute_tension([60, 64, 67], "C")
        assert 0.0 <= tension <= 0.5

    def test_dissonant_chord_higher_tension(self):
        """Diminished chord should have higher tension than major."""
        brain = HarmonicBrain()
        major = brain.compute_tension([60, 64, 67], "C")
        dim = brain.compute_tension([60, 63, 66], "C")
        assert dim > major
