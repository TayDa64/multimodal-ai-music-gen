"""Tests for multimodal_gen.intelligence.preferences — user preference tracking."""

import random
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from multimodal_gen.intelligence.preferences import (
    PreferenceDimensions,
    PreferenceSignal,
    PreferenceTracker,
)


class TestPreferenceDimensions:
    def test_cold_start_defaults(self):
        """All dimensions should start at 0.5."""
        dims = PreferenceDimensions()
        assert dims.harmonic_complexity == 0.5
        assert dims.energy_level == 0.5

    def test_to_dict_roundtrip(self):
        dims = PreferenceDimensions(harmonic_complexity=0.8, energy_level=0.3)
        d = dims.to_dict()
        restored = PreferenceDimensions.from_dict(d)
        assert restored.harmonic_complexity == 0.8
        assert restored.energy_level == 0.3


class TestPreferenceTracker:
    def test_record_signal_ema_update(self, tmp_path):
        """Recording an 'increase' signal should raise the target dimension."""
        tracker = PreferenceTracker(preferences_path=str(tmp_path / "prefs.json"))
        before = tracker.preferences.dimensions.energy_level  # 0.5
        signal = PreferenceSignal(
            timestamp="2026-01-01T00:00:00",
            signal_type="accept",
            domain="mix",
            dimension="energy_level",
            direction="increase",
            confidence=1.0,
        )
        tracker.record_signal(signal)
        after = tracker.preferences.dimensions.energy_level
        assert after > before  # EMA moved toward 1.0

    def test_signal_count_increments(self, tmp_path):
        tracker = PreferenceTracker(preferences_path=str(tmp_path / "prefs.json"))
        assert tracker.preferences.signal_count == 0
        signal = PreferenceSignal(
            timestamp="2026-01-01T00:00:00",
            signal_type="accept",
            domain="harmony",
            dimension="harmonic_complexity",
            direction="increase",
            confidence=1.0,
        )
        tracker.record_signal(signal)
        assert tracker.preferences.signal_count == 1

    def test_persistence_roundtrip(self, tmp_path):
        path = str(tmp_path / "prefs.json")
        tracker = PreferenceTracker(preferences_path=path)
        tracker.record_generation_accept("jazz", 110.0, "Bb")
        tracker.save()

        tracker2 = PreferenceTracker(preferences_path=path)
        assert tracker2.preferences.signal_count >= 1
        assert "jazz" in tracker2.preferences.genre_affinities

    def test_corrupted_json_recovery(self, tmp_path):
        """Corrupted prefs file should fall back to cold-start defaults."""
        path = tmp_path / "prefs.json"
        path.write_text("{{{garbage not valid json!!!")
        tracker = PreferenceTracker(preferences_path=str(path))
        # Should recover with fresh defaults
        assert tracker.preferences.signal_count == 0
        assert tracker.preferences.dimensions.energy_level == 0.5

    def test_confidence_formula(self, tmp_path):
        tracker = PreferenceTracker(preferences_path=str(tmp_path / "prefs.json"))
        assert tracker.compute_confidence() == pytest.approx(0.3, abs=0.05)
        for _ in range(10):
            tracker.record_generation_accept("jazz", 100.0, "C")
        assert tracker.compute_confidence() > 0.5

    def test_exploration_decision_deterministic(self, tmp_path):
        random.seed(42)
        tracker = PreferenceTracker(preferences_path=str(tmp_path / "prefs.json"))
        results = [tracker.should_explore() for _ in range(100)]
        explore_rate = sum(results) / len(results)
        assert 0.15 <= explore_rate <= 0.45

    def test_reset_clears_state(self, tmp_path):
        tracker = PreferenceTracker(preferences_path=str(tmp_path / "prefs.json"))
        tracker.record_generation_accept("jazz", 100.0, "C")
        tracker.reset()
        assert tracker.preferences.signal_count == 0
        assert tracker.preferences.dimensions.energy_level == 0.5
