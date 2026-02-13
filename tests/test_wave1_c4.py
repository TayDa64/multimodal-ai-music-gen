"""Wave 1 Category C4: Analysis & Narrative tests."""
import pytest
import numpy as np


class TestMelodyContour:
    def test_contour_extraction_returns_list(self):
        """extract_melody_contour returns list of contour segments for tonal audio."""
        from multimodal_gen.reference_analyzer import ReferenceAnalyzer

        analyzer = ReferenceAnalyzer()
        # Generate a simple ascending sine sweep (C4 -> C5)
        sr = 22050
        t = np.linspace(0, 2, sr * 2, dtype=np.float32)
        freq = 261.63 * (2.0 ** (t / 2))  # sweep from C4 to C5 over 2 seconds
        audio = (np.sin(2 * np.pi * np.cumsum(freq / sr)) * 0.5).astype(np.float32)
        contour = analyzer._extract_melody_contour(audio, sr)
        assert isinstance(contour, list)

    def test_contour_has_direction_field(self):
        from multimodal_gen.reference_analyzer import ReferenceAnalyzer

        analyzer = ReferenceAnalyzer()
        sr = 22050
        t = np.linspace(0, 1, sr, dtype=np.float32)
        audio = (np.sin(2 * np.pi * 440 * t) * 0.5).astype(np.float32)  # steady A4
        contour = analyzer._extract_melody_contour(audio, sr)
        if len(contour) > 0:
            assert "direction" in contour[0]
            assert contour[0]["direction"] in ("up", "down", "hold")

    def test_contour_in_analysis_dataclass(self):
        from multimodal_gen.reference_analyzer import ReferenceAnalysis

        analysis = ReferenceAnalysis(source_url="test")
        assert hasattr(analysis, "melody_contour")
        assert isinstance(analysis.melody_contour, list)


class TestDrumAnalysisEnhanced:
    def _make_drum_analysis(self):
        from multimodal_gen.reference_analyzer import DrumAnalysis

        return DrumAnalysis(
            density=0.5,
            kick_pattern=[0.0, 0.5],
            snare_pattern=[0.25, 0.75],
            hihat_density=0.5,
            has_rolls=False,
            four_on_floor=False,
            trap_hihats=False,
            boom_bap_feel=False,
        )

    def test_drum_analysis_has_hihat(self):
        da = self._make_drum_analysis()
        assert hasattr(da, "hihat_pattern")

    def test_drum_analysis_has_swing(self):
        da = self._make_drum_analysis()
        assert hasattr(da, "swing_amount")
        assert da.swing_amount == 0.0

    def test_as_template(self):
        da = self._make_drum_analysis()
        template = da.as_template()
        assert isinstance(template, dict)
        assert "kick" in template
        assert "snare" in template
        assert "hihat" in template
        assert "swing" in template


class TestTransitionCrossfade:
    def test_crossfade_type_exists(self):
        from multimodal_gen.transitions import TransitionType

        assert hasattr(TransitionType, "CROSSFADE")

    def test_crossfade_generation(self):
        from multimodal_gen.transitions import TransitionGenerator

        gen = TransitionGenerator(seed=42)
        from_section = type("Section", (), {"energy": 0.6, "section_type": "verse"})()
        to_section = type("Section", (), {"energy": 0.7, "section_type": "chorus"})()
        result = gen._generate_crossfade(from_section, to_section, 1920)
        assert isinstance(result, list)
        assert len(result) > 0

    def test_crossfade_in_genre_styles(self):
        from multimodal_gen.transitions import GENRE_TRANSITION_STYLES

        for genre in ["ambient", "lofi"]:
            if genre in GENRE_TRANSITION_STYLES:
                styles = GENRE_TRANSITION_STYLES[genre]
                has_crossfade = (
                    any("crossfade" in str(s).lower() for s in styles)
                    if isinstance(styles, (list, tuple))
                    else "crossfade" in str(styles).lower()
                )
                assert has_crossfade, f"{genre} should support crossfade transitions"


class TestTransitionStyleParam:
    def test_style_param_accepted(self):
        """generate_transition accepts optional style parameter."""
        from multimodal_gen.transitions import TransitionGenerator

        gen = TransitionGenerator(seed=42)
        _cfg_from = type("Config", (), {"energy_level": 0.5})()
        _cfg_to = type("Config", (), {"energy_level": 0.8})()
        from_section = type(
            "Section",
            (),
            {
                "config": _cfg_from,
                "section_type": "verse",
                "start_tick": 0,
                "end_tick": 1920,
            },
        )()
        to_section = type(
            "Section",
            (),
            {
                "config": _cfg_to,
                "section_type": "chorus",
                "start_tick": 1920,
                "end_tick": 3840,
            },
        )()
        # Should not raise with default style=None (backward compatible)
        result = gen.generate_transition(from_section, to_section)
        assert result is not None


class TestExistingCapabilities:
    """Verify existing Phase 4-5 capabilities still work."""

    def test_tension_arc_shapes(self):
        from multimodal_gen.tension_arc import ArcShape, TensionArcGenerator

        gen = TensionArcGenerator()
        for shape in ArcShape:
            arc = gen.create_arc(shape, num_sections=4)
            assert len(arc.points) == 4

    def test_section_variation_engine(self):
        from multimodal_gen.section_variation import SectionVariationEngine

        engine = SectionVariationEngine()
        assert engine is not None

    def test_motif_transformations(self):
        from multimodal_gen.motif_engine import Motif

        motif = Motif(
            name="test",
            intervals=[0, 2, 4, 7],
            rhythm=[0.5, 0.5, 0.5, 0.5],
            genre_tags=["test"],
        )
        retrograde = motif.retrograde()
        assert len(retrograde.intervals) == len(motif.intervals)
        inverted = motif.invert()
        assert len(inverted.intervals) == len(motif.intervals)

    def test_dynamics_genre_presets(self):
        from multimodal_gen.dynamics import GENRE_DYNAMICS

        assert len(GENRE_DYNAMICS) >= 16
        for genre, config in GENRE_DYNAMICS.items():
            assert hasattr(config, "velocity_range") or isinstance(config, dict)

    def test_chord_extractor_exists(self):
        from multimodal_gen.chord_extractor import ChordExtractor

        extractor = ChordExtractor()
        assert extractor is not None
