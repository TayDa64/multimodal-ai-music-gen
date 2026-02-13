"""Wave 3: Gap closure tests — CC injection, extract_drum_pattern, docs, orchestration."""
import json
import inspect
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Gap 1: MIDI CC Injection in dynamics.py
# ---------------------------------------------------------------------------

class TestCCIntensityPresets:
    """Verify CC_INTENSITY_PRESETS dict completeness."""

    def test_presets_importable(self):
        from multimodal_gen.dynamics import CC_INTENSITY_PRESETS
        assert isinstance(CC_INTENSITY_PRESETS, dict)

    def test_required_genres_present(self):
        from multimodal_gen.dynamics import CC_INTENSITY_PRESETS
        for genre in ("trap", "jazz", "lofi", "orchestral", "ethiopian", "default"):
            assert genre in CC_INTENSITY_PRESETS, f"Missing genre: {genre}"

    def test_preset_keys_contain_cc_numbers(self):
        from multimodal_gen.dynamics import CC_INTENSITY_PRESETS
        for genre, preset in CC_INTENSITY_PRESETS.items():
            assert "cc11" in preset, f"{genre} missing cc11"
            assert "cc1" in preset, f"{genre} missing cc1"
            assert "cc74" in preset, f"{genre} missing cc74"

    def test_preset_values_are_floats_in_range(self):
        from multimodal_gen.dynamics import CC_INTENSITY_PRESETS
        for genre, preset in CC_INTENSITY_PRESETS.items():
            for key, val in preset.items():
                assert isinstance(val, (int, float)), f"{genre}.{key} not numeric"
                assert 0.0 <= val <= 1.0, f"{genre}.{key}={val} out of 0..1"


class TestGeneratePhraseCCEvents:
    """Verify generate_phrase_cc_events function."""

    def test_importable(self):
        from multimodal_gen.dynamics import generate_phrase_cc_events
        assert callable(generate_phrase_cc_events)

    def test_signature(self):
        from multimodal_gen.dynamics import generate_phrase_cc_events
        sig = inspect.signature(generate_phrase_cc_events)
        assert "notes" in sig.parameters
        assert "boundaries" in sig.parameters
        assert "genre" in sig.parameters
        assert "ticks_per_beat" in sig.parameters

    def test_returns_list(self):
        from multimodal_gen.dynamics import generate_phrase_cc_events, detect_phrase_boundaries
        notes = [(i * 480, 60, 100, 480) for i in range(8)]
        boundaries = detect_phrase_boundaries(notes)
        events = generate_phrase_cc_events(notes, boundaries)
        assert isinstance(events, list)

    def test_events_are_tuples_of_three(self):
        from multimodal_gen.dynamics import generate_phrase_cc_events, detect_phrase_boundaries
        notes = [(i * 480, 60, 100, 480) for i in range(8)]
        boundaries = detect_phrase_boundaries(notes)
        events = generate_phrase_cc_events(notes, boundaries)
        for ev in events:
            assert len(ev) == 3, f"Expected 3-tuple, got {ev}"

    def test_cc_numbers_are_valid(self):
        from multimodal_gen.dynamics import generate_phrase_cc_events, detect_phrase_boundaries
        notes = [(i * 480, 60, 100, 480) for i in range(8)]
        boundaries = detect_phrase_boundaries(notes)
        events = generate_phrase_cc_events(notes, boundaries)
        valid_ccs = {1, 11, 74}
        for tick, cc, val in events:
            assert cc in valid_ccs, f"Unexpected CC number {cc}"
            assert 0 <= val <= 127, f"CC value {val} out of MIDI range"

    def test_empty_notes_returns_empty(self):
        from multimodal_gen.dynamics import generate_phrase_cc_events
        assert generate_phrase_cc_events([], [0]) == []

    def test_sustained_notes_get_cc1_vibrato(self):
        from multimodal_gen.dynamics import generate_phrase_cc_events, detect_phrase_boundaries
        # Single 4-beat note (1920 ticks) — well above 2-beat threshold
        notes = [(0, 1920, 60, 100)]
        boundaries = detect_phrase_boundaries(notes)
        events = generate_phrase_cc_events(notes, boundaries, genre="jazz")
        cc1_events = [e for e in events if e[1] == 1]
        assert len(cc1_events) > 0, "Sustained note should produce CC1 vibrato"

    def test_trap_minimal_cc(self):
        from multimodal_gen.dynamics import generate_phrase_cc_events, detect_phrase_boundaries
        notes = [(i * 480, 480, 60, 100) for i in range(4)]
        boundaries = detect_phrase_boundaries(notes)
        trap = generate_phrase_cc_events(notes, boundaries, genre="trap")
        jazz = generate_phrase_cc_events(notes, boundaries, genre="jazz")
        # Jazz should be at least as expressive as trap
        assert len(jazz) >= len(trap)

    def test_genre_affects_cc_values(self):
        from multimodal_gen.dynamics import generate_phrase_cc_events, detect_phrase_boundaries
        notes = [(i * 480, 480, 60, 100) for i in range(4)]
        boundaries = detect_phrase_boundaries(notes)
        trap = generate_phrase_cc_events(notes, boundaries, genre="trap")
        jazz = generate_phrase_cc_events(notes, boundaries, genre="jazz")
        # Compare average CC11 values — jazz should be higher
        trap_cc11 = [v for _, cc, v in trap if cc == 11]
        jazz_cc11 = [v for _, cc, v in jazz if cc == 11]
        if trap_cc11 and jazz_cc11:
            assert sum(jazz_cc11) / len(jazz_cc11) >= sum(trap_cc11) / len(trap_cc11)


# ---------------------------------------------------------------------------
# Gap 2: extract_drum_pattern
# ---------------------------------------------------------------------------

class TestExtractDrumPattern:
    """Verify the public convenience wrapper."""

    def test_function_exists(self):
        from multimodal_gen.reference_analyzer import extract_drum_pattern
        assert callable(extract_drum_pattern)

    def test_signature(self):
        from multimodal_gen.reference_analyzer import extract_drum_pattern
        sig = inspect.signature(extract_drum_pattern)
        assert "audio_path" in sig.parameters
        assert "quantize_grid" in sig.parameters

    def test_missing_file_raises(self):
        from multimodal_gen.reference_analyzer import extract_drum_pattern
        with pytest.raises((FileNotFoundError, ImportError)):
            extract_drum_pattern("nonexistent_file_wave3_test.wav")


# ---------------------------------------------------------------------------
# Gap 3: MASTERCLASS_GUIDE.md documentation
# ---------------------------------------------------------------------------

class TestDocumentation:
    """Verify docs/MASTERCLASS_GUIDE.md content."""

    def test_file_exists(self):
        guide = Path(__file__).parent.parent / "docs" / "MASTERCLASS_GUIDE.md"
        assert guide.exists(), "docs/MASTERCLASS_GUIDE.md should exist"

    def test_has_required_sections(self):
        guide = Path(__file__).parent.parent / "docs" / "MASTERCLASS_GUIDE.md"
        content = guide.read_text(encoding="utf-8")
        for section in ("Overview", "Quick Start", "Motif", "Groove", "Genre",
                        "Reference Analysis", "Audio Processing", "Arrangement",
                        "Preset", "Quality"):
            assert section in content, f"Missing section: {section}"

    def test_mentions_key_modules(self):
        guide = Path(__file__).parent.parent / "docs" / "MASTERCLASS_GUIDE.md"
        content = guide.read_text(encoding="utf-8")
        for module in ("dynamics.py", "motif_engine.py", "reference_analyzer.py",
                        "reverb.py", "tension_arc.py"):
            assert module in content, f"Missing module reference: {module}"


# ---------------------------------------------------------------------------
# Gap 4: orchestration.json update
# ---------------------------------------------------------------------------

class TestOrchestratorState:
    """Verify orchestration.json updates."""

    def test_builder_4_completed(self):
        orch_path = Path(__file__).parent.parent / ".github" / "state" / "orchestration.json"
        data = json.loads(orch_path.read_text(encoding="utf-8"))
        b4 = data.get("architecture_refactoring", {}).get("builder_4_instrument_plugin_system", {})
        assert b4.get("status") == "completed"

    def test_wave_3_section_exists(self):
        orch_path = Path(__file__).parent.parent / ".github" / "state" / "orchestration.json"
        data = json.loads(orch_path.read_text(encoding="utf-8"))
        assert "wave_3" in data, "wave_3 section missing from orchestration.json"
        assert data["wave_3"]["status"] == "COMPLETE"


# ---------------------------------------------------------------------------
# Regression: existing functionality unbroken
# ---------------------------------------------------------------------------

class TestExistingRegression:
    """Verify nothing broke."""

    def test_dynamics_engine_still_works(self):
        from multimodal_gen.dynamics import DynamicsEngine, DynamicsConfig
        engine = DynamicsEngine()
        notes = [(i * 480, 240, 60, 80) for i in range(8)]
        config = DynamicsConfig()
        result = engine.apply(notes, config)
        assert len(result) == len(notes)

    def test_detect_phrase_boundaries_still_works(self):
        from multimodal_gen.dynamics import detect_phrase_boundaries
        notes = [(0, 480, 60, 80), (960, 480, 62, 80), (3000, 480, 64, 80)]
        bounds = detect_phrase_boundaries(notes)
        assert 0 in bounds
        assert isinstance(bounds, list)

    def test_apply_dynamics_convenience(self):
        from multimodal_gen.dynamics import apply_dynamics
        notes = [(i * 480, 240, 60, 80) for i in range(4)]
        result = apply_dynamics(notes, genre="trap")
        assert len(result) == 4

    def test_genre_dynamics_presets_intact(self):
        from multimodal_gen.dynamics import GENRE_DYNAMICS
        assert len(GENRE_DYNAMICS) >= 17

    def test_reference_analyzer_imports(self):
        from multimodal_gen.reference_analyzer import ReferenceAnalyzer, analyze_reference
        assert callable(analyze_reference)
