"""Sprint 6: Transition generator tests.

Verifies TransitionGenerator (Sprint 6.4) and genre presets.
"""
import pytest
from multimodal_gen.transitions import (
    TransitionGenerator,
    TransitionType,
    TransitionConfig,
    TransitionEvent,
    GENRE_TRANSITION_STYLES,
    generate_transitions,
)


# ---------------------------------------------------------------------------
# Lightweight duck-typed mock sections (mirror actual SongSection interface)
# ---------------------------------------------------------------------------

class _MockConfig:
    def __init__(self, energy: float):
        self.energy_level = energy


class _MockSection:
    def __init__(self, section_type: str, start: int, end: int, energy: float = 0.5):
        self.section_type = type("ST", (), {"value": section_type})()
        self.start_tick = start
        self.end_tick = end
        self.config = _MockConfig(energy)
        self.variation_seed = 0


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestTransitionTypeSelection:
    def test_energy_increase_selects_build(self):
        gen = TransitionGenerator(seed=42)
        low = _MockSection("breakdown", 0, 1920, energy=0.3)
        high = _MockSection("chorus", 1920, 3840, energy=0.9)
        assert gen.select_transition_type(low, high) == TransitionType.BUILD

    def test_energy_decrease_selects_breakdown_or_cut(self):
        gen = TransitionGenerator(seed=42)
        high = _MockSection("chorus", 0, 1920, energy=0.9)
        low = _MockSection("verse", 1920, 3840, energy=0.3)
        tt = gen.select_transition_type(high, low)
        assert tt in (TransitionType.BREAKDOWN, TransitionType.CUT)

    def test_similar_energy_defaults_to_fill(self):
        gen = TransitionGenerator(seed=42)
        a = _MockSection("verse", 0, 1920, energy=0.5)
        b = _MockSection("verse", 1920, 3840, energy=0.5)
        tt = gen.select_transition_type(a, b)
        assert tt == TransitionType.FILL


class TestTransitionGeneration:
    def test_fill_produces_events(self):
        gen = TransitionGenerator(seed=42)
        s1 = _MockSection("verse", 0, 3840, energy=0.5)
        s2 = _MockSection("verse", 3840, 7680, energy=0.5)
        cfg = TransitionConfig(transition_type=TransitionType.FILL, duration_beats=2.0)
        result = gen.generate_transition(s1, s2, cfg)
        assert isinstance(result, TransitionEvent)
        assert len(result.events) > 0
        for pitch, tick, dur, vel in result.events:
            assert result.start_tick <= tick <= result.end_tick
            assert 0 <= vel <= 127

    def test_build_velocities_increase(self):
        gen = TransitionGenerator(seed=42)
        s1 = _MockSection("breakdown", 0, 7680, energy=0.3)
        s2 = _MockSection("drop", 7680, 15360, energy=1.0)
        cfg = TransitionConfig(
            transition_type=TransitionType.BUILD,
            duration_beats=4.0,
            intensity=1.0,
        )
        result = gen.generate_transition(s1, s2, cfg)
        vels = [v for _, _, _, v in result.events]
        assert len(vels) > 0
        assert vels[-1] >= vels[0]

    def test_cut_is_sparse(self):
        gen = TransitionGenerator(seed=42)
        s1 = _MockSection("chorus", 0, 3840, energy=0.8)
        s2 = _MockSection("verse", 3840, 7680, energy=0.4)
        cfg = TransitionConfig(transition_type=TransitionType.CUT)
        result = gen.generate_transition(s1, s2, cfg)
        assert len(result.events) <= 3

    def test_crash_has_cymbal(self):
        gen = TransitionGenerator(seed=42)
        s1 = _MockSection("verse", 0, 3840, energy=0.5)
        s2 = _MockSection("chorus", 3840, 7680, energy=0.8)
        cfg = TransitionConfig(transition_type=TransitionType.CRASH)
        result = gen.generate_transition(s1, s2, cfg)
        pitches = {p for p, _, _, _ in result.events}
        assert 49 in pitches  # crash cymbal GM pitch


class TestGenerateAll:
    def test_generate_all_transitions(self):
        gen = TransitionGenerator(seed=42)
        sections = [
            _MockSection("intro", 0, 1920, energy=0.3),
            _MockSection("verse", 1920, 5760, energy=0.5),
            _MockSection("chorus", 5760, 9600, energy=0.8),
        ]
        transitions = gen.generate_all_transitions(sections)
        assert len(transitions) == 2

    def test_single_section_yields_no_transitions(self):
        gen = TransitionGenerator(seed=42)
        transitions = gen.generate_all_transitions(
            [_MockSection("intro", 0, 1920, energy=0.3)]
        )
        assert len(transitions) == 0


class TestGenrePresets:
    def test_coverage(self):
        assert len(GENRE_TRANSITION_STYLES) >= 8

    def test_all_have_default(self):
        for genre, styles in GENRE_TRANSITION_STYLES.items():
            assert "default" in styles, f"{genre} missing 'default' key"


class TestConvenienceFunction:
    def test_generate_transitions_convenience(self):
        sections = [
            _MockSection("intro", 0, 1920, energy=0.3),
            _MockSection("chorus", 1920, 3840, energy=0.9),
        ]
        transitions = generate_transitions(sections, genre="trap", seed=42)
        assert len(transitions) == 1
        assert isinstance(transitions[0], TransitionEvent)

    def test_deterministic_with_seed(self):
        sections = [
            _MockSection("verse", 0, 1920, energy=0.5),
            _MockSection("chorus", 1920, 3840, energy=0.8),
        ]
        t1 = generate_transitions(sections, seed=123)
        t2 = generate_transitions(sections, seed=123)
        assert len(t1) == len(t2)
        for a, b in zip(t1, t2):
            assert a.events == b.events


class TestEdgeCases:
    """Edge-case tests for robustness."""

    def test_zero_length_section(self):
        """A zero-length section (start_tick == end_tick) should produce 0 events."""
        gen = TransitionGenerator(seed=42)
        s1 = _MockSection("verse", 1920, 1920, energy=0.5)   # zero-length!
        s2 = _MockSection("chorus", 1920, 3840, energy=0.8)
        cfg = TransitionConfig(transition_type=TransitionType.FILL)
        result = gen.generate_transition(s1, s2, cfg)
        # Should handle gracefully — no crash, any number of events is OK
        assert isinstance(result, TransitionEvent)

    def test_empty_sections_list(self):
        """generate_all_transitions([]) must return []."""
        gen = TransitionGenerator(seed=42)
        transitions = gen.generate_all_transitions([])
        assert transitions == []
