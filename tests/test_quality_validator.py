"""Tests for quality validation suite."""
import pytest
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from multimodal_gen.quality_validator import (
    QualityValidator, QualityLevel, MetricCategory,
    MetricResult, ValidationReport, quick_validate,
    GENRE_QUALITY_PROFILES
)


class TestQualityValidator:
    """Test QualityValidator initialization and validation."""
    
    def test_validator_initialization(self):
        """Test validator can be created."""
        validator = QualityValidator()
        assert validator is not None
        assert validator.strict_mode is False
        assert validator.genre_profiles is not None
    
    def test_validator_strict_mode(self):
        """Test validator with strict mode."""
        validator = QualityValidator(strict_mode=True)
        assert validator.strict_mode is True
    
    def test_validate_returns_report(self):
        """Test validate returns ValidationReport."""
        validator = QualityValidator()
        notes = [(0, 480, 60, 100), (480, 480, 62, 95)]
        report = validator.validate(notes)
        assert isinstance(report, ValidationReport)
        assert report.overall_score >= 0.0
        assert report.overall_score <= 1.0
        assert isinstance(report.overall_level, QualityLevel)
    
    def test_validate_empty_notes(self):
        """Test validation with no notes."""
        validator = QualityValidator()
        report = validator.validate([])
        assert report.passed is False
        assert report.overall_score == 0.0
        assert report.overall_level == QualityLevel.FAILING
    
    def test_validate_with_genre(self):
        """Test validation with different genres."""
        validator = QualityValidator()
        notes = [(i * 480, 240, 60 + i % 12, 80 + i * 2) for i in range(10)]
        
        for genre in ["pop", "jazz", "hip_hop", "edm", "rock"]:
            report = validator.validate(notes, genre=genre)
            assert isinstance(report, ValidationReport)
    
    def test_validate_has_all_metric_categories(self):
        """Test that validation includes all metric categories."""
        validator = QualityValidator()
        notes = [(i * 480, 240, 60 + i % 12, 80 + i * 2) for i in range(20)]
        report = validator.validate(notes)
        
        categories = {m.category for m in report.metrics}
        assert MetricCategory.MIDI_QUALITY in categories
        assert MetricCategory.HUMANIZATION in categories
        assert MetricCategory.MUSIC_THEORY in categories
        assert MetricCategory.GENRE_CONFORMANCE in categories

    def test_validate_includes_motif_coherence_metric(self):
        """Ensure the motif coherence heuristic is present."""
        validator = QualityValidator()
        notes = [(i * 240, 120, 60 + (i * 7) % 12, 70 + (i % 6) * 3) for i in range(24)]
        report = validator.validate(notes)
        metric_names = {m.name for m in report.metrics}
        assert "Motif Coherence" in metric_names
    
    def test_validate_produces_recommendations(self):
        """Test that validation produces recommendations."""
        validator = QualityValidator()
        notes = [(0, 480, 60, 80), (480, 480, 60, 80)]  # Very simple
        report = validator.validate(notes)
        assert isinstance(report.recommendations, list)


class TestMIDIQualityMetrics:
    """Test MIDI quality metric functions."""
    
    def test_note_density_calculation(self):
        """Test note density calculation."""
        validator = QualityValidator()
        # 10 notes over 4 beats = 2.5 notes/beat
        notes = [(i * 480, 240, 60, 80) for i in range(10)]
        result = validator.analyze_note_density(notes, 480, "pop")
        assert result.name == "Note Density"
        assert result.category == MetricCategory.MIDI_QUALITY
        assert result.value > 0
    
    def test_note_density_empty(self):
        """Test note density with no notes."""
        validator = QualityValidator()
        result = validator.analyze_note_density([], 480, "pop")
        assert result.quality_level == QualityLevel.FAILING
    
    def test_velocity_distribution(self):
        """Test velocity distribution analysis."""
        validator = QualityValidator()
        # Varied velocities
        notes = [(i * 480, 240, 60, 70 + i * 5) for i in range(10)]
        result = validator.analyze_velocity_distribution(notes)
        assert result.name == "Velocity Distribution"
        assert result.normalized_score > 0
    
    def test_velocity_distribution_uniform(self):
        """Test velocity distribution with uniform velocities."""
        validator = QualityValidator()
        # All same velocity
        notes = [(i * 480, 240, 60, 80) for i in range(10)]
        result = validator.analyze_velocity_distribution(notes)
        assert result.value == 0  # No variation
    
    def test_pitch_range_within_bounds(self):
        """Test pitch range within instrument bounds."""
        validator = QualityValidator()
        # Piano notes in good range
        notes = [(i * 480, 240, 48 + i, 80) for i in range(12)]
        result = validator.analyze_pitch_range(notes, "piano")
        assert result.normalized_score > 0
    
    def test_pitch_range_out_of_bounds(self):
        """Test pitch range outside instrument bounds."""
        validator = QualityValidator()
        # Notes too low for guitar
        notes = [(i * 480, 240, 20 + i, 80) for i in range(5)]
        result = validator.analyze_pitch_range(notes, "guitar")
        assert result.normalized_score < 1.0
    
    def test_duration_distribution(self):
        """Test duration distribution analysis."""
        validator = QualityValidator()
        # Varied durations
        notes = [(0, 240, 60, 80), (480, 480, 62, 80), (960, 120, 64, 80)]
        result = validator.analyze_duration_distribution(notes, 480)
        assert result.value > 1  # Multiple different durations
    
    def test_note_count_good(self):
        """Test note count with good amount."""
        validator = QualityValidator()
        notes = [(i * 240, 240, 60, 80) for i in range(20)]
        result = validator.analyze_note_count(notes)
        assert result.quality_level == QualityLevel.EXCELLENT
    
    def test_note_count_low(self):
        """Test note count with few notes."""
        validator = QualityValidator()
        notes = [(0, 240, 60, 80), (480, 240, 62, 80)]
        result = validator.analyze_note_count(notes)
        assert result.normalized_score < 1.0
    
    def test_note_overlap(self):
        """Test note overlap analysis."""
        validator = QualityValidator()
        # Some overlapping notes
        notes = [(0, 960, 60, 80), (480, 480, 64, 80), (960, 480, 67, 80)]
        result = validator.analyze_note_overlap(notes)
        assert result.name == "Note Overlap"
        assert result.category == MetricCategory.MIDI_QUALITY
    
    def test_note_overlap_monophonic(self):
        """Test note overlap with no overlaps."""
        validator = QualityValidator()
        # No overlapping notes
        notes = [(0, 240, 60, 80), (480, 240, 62, 80), (960, 240, 64, 80)]
        result = validator.analyze_note_overlap(notes)
        assert result.value == 0.0


class TestHumanizationMetrics:
    """Test humanization metric functions."""
    
    def test_timing_variance_robotic(self):
        """Perfectly quantized notes should flag as robotic."""
        validator = QualityValidator()
        # Perfect 16th notes
        notes = [(i * 120, 120, 60, 80) for i in range(10)]
        result = validator.analyze_timing_variance(notes, 480, "pop")
        # Should detect very low variance
        assert result.value < 0.1
    
    def test_timing_variance_humanized(self):
        """Notes with micro-timing should pass."""
        validator = QualityValidator()
        # Slightly off-grid timing
        notes = [(i * 120 + (i % 3) * 5, 120, 60, 80) for i in range(10)]
        result = validator.analyze_timing_variance(notes, 480, "pop")
        assert result.value > 0
    
    def test_velocity_variance(self):
        """Test velocity variance calculation."""
        validator = QualityValidator()
        # Good variation
        notes = [(i * 480, 240, 60, 70 + i * 3) for i in range(10)]
        result = validator.analyze_velocity_variance(notes)
        assert result.name == "Velocity Variance"
        assert result.value > 0
    
    def test_velocity_variance_static(self):
        """Test velocity variance with static velocities."""
        validator = QualityValidator()
        notes = [(i * 480, 240, 60, 80) for i in range(10)]
        result = validator.analyze_velocity_variance(notes)
        assert result.value == 0
    
    def test_repetition_detection(self):
        """Test pattern repetition detection."""
        validator = QualityValidator()
        # Some repeated patterns
        notes = [(0, 240, 60, 80), (240, 240, 62, 80), (480, 240, 64, 80), (720, 240, 65, 80),
                 (960, 240, 60, 80), (1200, 240, 62, 80), (1440, 240, 64, 80), (1680, 240, 65, 80)]
        result = validator.analyze_repetition(notes, 480)
        assert result.name == "Repetition"
        assert result.value >= 0
    
    def test_velocity_patterns(self):
        """Test velocity pattern analysis."""
        validator = QualityValidator()
        # Varied velocities
        notes = [(i * 240, 240, 60, 70 + (i % 4) * 10) for i in range(10)]
        result = validator.analyze_velocity_patterns(notes)
        assert result.normalized_score > 0
    
    def test_note_spacing(self):
        """Test note spacing analysis."""
        validator = QualityValidator()
        # Regular spacing
        notes = [(i * 480, 240, 60 + i % 5, 80) for i in range(10)]
        result = validator.analyze_note_spacing(notes, 480)
        assert result.name == "Note Spacing"
        assert result.value > 0


class TestMusicTheoryMetrics:
    """Test music theory metric functions."""
    
    def test_scale_adherence_all_in_scale(self):
        """Test scale adherence with all notes in scale."""
        validator = QualityValidator()
        # C major scale notes
        notes = [(i * 480, 240, 60 + interval, 80) for i, interval in enumerate([0, 2, 4, 5, 7, 9, 11, 12])]
        result = validator.analyze_scale_adherence(notes, "C", "major")
        assert result.value == 1.0  # 100% in scale
        assert result.quality_level == QualityLevel.EXCELLENT
    
    def test_scale_adherence_chromatic(self):
        """Test scale adherence with chromatic notes."""
        validator = QualityValidator()
        # Mix of in and out of scale
        notes = [(i * 240, 240, 60 + i, 80) for i in range(12)]
        result = validator.analyze_scale_adherence(notes, "C", "major")
        assert result.value < 1.0  # Not all in scale
    
    def test_pitch_variety(self):
        """Test pitch variety analysis."""
        validator = QualityValidator()
        # Good variety
        notes = [(i * 240, 240, 60 + i % 8, 80) for i in range(20)]
        result = validator.analyze_pitch_variety(notes)
        assert result.normalized_score > 0
    
    def test_pitch_variety_limited(self):
        """Test pitch variety with limited pitches."""
        validator = QualityValidator()
        # Only 2 pitches
        notes = [(i * 240, 240, 60 if i % 2 == 0 else 62, 80) for i in range(10)]
        result = validator.analyze_pitch_variety(notes)
        assert result.value < 0.5
    
    def test_interval_distribution(self):
        """Test interval distribution analysis."""
        validator = QualityValidator()
        # Stepwise motion
        notes = [(i * 480, 240, 60 + i, 80) for i in range(8)]
        result = validator.analyze_interval_distribution(notes)
        assert result.name == "Interval Distribution"
    
    def test_melodic_contour(self):
        """Test melodic contour analysis."""
        validator = QualityValidator()
        # Up and down motion
        pitches = [60, 62, 64, 62, 60, 62, 64, 65]
        notes = [(i * 480, 240, pitches[i], 80) for i in range(len(pitches))]
        result = validator.analyze_melodic_contour(notes)
        assert result.normalized_score > 0


class TestGenreConformance:
    """Test genre conformance metrics."""
    
    def test_tempo_in_range(self):
        """Test tempo within genre range."""
        validator = QualityValidator()
        # Pop tempo in range (90-140)
        result = validator.analyze_tempo_conformance(120, "pop")
        assert result.quality_level == QualityLevel.EXCELLENT
        assert result.normalized_score == 1.0
    
    def test_tempo_out_of_range(self):
        """Test tempo outside genre range."""
        validator = QualityValidator()
        # Too slow for pop
        result = validator.analyze_tempo_conformance(60, "pop")
        assert result.normalized_score < 1.0
    
    def test_genre_velocity_profile_jazz(self):
        """Test velocity profile for jazz."""
        validator = QualityValidator()
        # Jazz needs good variation
        notes = [(i * 240, 240, 60, 70 + i * 5) for i in range(10)]
        result = validator.analyze_genre_velocity_profile(notes, "jazz")
        assert result.name == "Genre Velocity Profile"
    
    def test_genre_velocity_profile_edm(self):
        """Test velocity profile for EDM."""
        validator = QualityValidator()
        # EDM can have less variation
        notes = [(i * 240, 240, 60, 80 + i * 2) for i in range(10)]
        result = validator.analyze_genre_velocity_profile(notes, "edm")
        assert result.category == MetricCategory.GENRE_CONFORMANCE


class TestStructureMetrics:
    """Test structure metrics."""
    
    def test_phrase_structure(self):
        """Test phrase structure detection."""
        validator = QualityValidator()
        # Two phrases with gap
        notes = [(i * 240, 240, 60, 80) for i in range(4)]
        notes += [(2400 + i * 240, 240, 62, 80) for i in range(4)]
        result = validator.analyze_phrase_structure(notes, 480)
        assert result.name == "Phrase Structure"
    
    def test_rhythmic_consistency(self):
        """Test rhythmic consistency."""
        validator = QualityValidator()
        # Consistent rhythm
        notes = [(i * 480, 240, 60 + i % 5, 80) for i in range(10)]
        result = validator.analyze_rhythmic_consistency(notes, 480)
        assert result.category == MetricCategory.STRUCTURE


class TestDynamicsMetrics:
    """Test dynamics metrics."""
    
    def test_dynamic_range_good(self):
        """Test good dynamic range."""
        validator = QualityValidator()
        # Good range: 50-100
        notes = [(i * 240, 240, 60, 50 + i * 5) for i in range(10)]
        result = validator.analyze_dynamic_range(notes)
        assert result.normalized_score > 0
    
    def test_dynamic_range_limited(self):
        """Test limited dynamic range."""
        validator = QualityValidator()
        # Narrow range: 75-85
        notes = [(i * 240, 240, 60, 75 + i) for i in range(10)]
        result = validator.analyze_dynamic_range(notes)
        assert result.value < 30
    
    def test_velocity_progression(self):
        """Test velocity progression (crescendo/decrescendo)."""
        validator = QualityValidator()
        # Crescendo
        notes = [(i * 240, 240, 60, 60 + i * 3) for i in range(10)]
        result = validator.analyze_velocity_progression(notes)
        assert result.name == "Velocity Progression"
    
    def test_accent_patterns(self):
        """Test accent pattern detection."""
        validator = QualityValidator()
        # Some accented notes
        velocities = [80, 90, 85, 100, 80, 85, 95, 80]
        notes = [(i * 240, 240, 60, velocities[i]) for i in range(len(velocities))]
        result = validator.analyze_accent_patterns(notes)
        assert result.category == MetricCategory.DYNAMICS


class TestRhythmMetrics:
    """Test rhythm metrics."""
    
    def test_rhythmic_complexity(self):
        """Test rhythmic complexity analysis."""
        validator = QualityValidator()
        # Mix of durations and timing
        notes = [(0, 240, 60, 80), (240, 120, 62, 80), (480, 480, 64, 80), (960, 240, 65, 80)]
        result = validator.analyze_rhythmic_complexity(notes, 480)
        assert result.name == "Rhythmic Complexity"
    
    def test_syncopation(self):
        """Test syncopation detection."""
        validator = QualityValidator()
        # Mix of on-beat and off-beat
        notes = [(0, 240, 60, 80), (300, 180, 62, 80), (480, 240, 64, 80), (780, 180, 65, 80)]
        result = validator.analyze_syncopation(notes, 480)
        assert result.category == MetricCategory.RHYTHM
    
    def test_note_duration_variety(self):
        """Test note duration variety."""
        validator = QualityValidator()
        # Varied durations
        notes = [(0, 240, 60, 80), (240, 480, 62, 80), (720, 120, 64, 80)]
        result = validator.analyze_note_duration_variety(notes, 480)
        assert result.normalized_score > 0


class TestValidationReport:
    """Test ValidationReport generation."""
    
    def test_overall_score_calculation(self):
        """Test overall score is calculated correctly."""
        validator = QualityValidator()
        notes = [(i * 240, 240, 60 + i % 12, 70 + i * 2) for i in range(20)]
        report = validator.validate(notes)
        assert 0.0 <= report.overall_score <= 1.0
    
    def test_category_scores_calculated(self):
        """Test category scores are calculated."""
        validator = QualityValidator()
        notes = [(i * 240, 240, 60 + i % 12, 70 + i * 2) for i in range(20)]
        report = validator.validate(notes)
        assert len(report.category_scores) > 0
        for cat, score in report.category_scores.items():
            assert isinstance(cat, MetricCategory)
            assert 0.0 <= score <= 1.0
    
    def test_recommendations_generated(self):
        """Test recommendations are generated."""
        validator = QualityValidator()
        # Poor quality notes
        notes = [(0, 480, 60, 80), (480, 480, 60, 80)]
        report = validator.validate(notes)
        assert len(report.recommendations) > 0
    
    def test_passed_flag_correct(self):
        """Test passed flag reflects quality."""
        validator = QualityValidator()
        # Good notes
        notes = [(i * 240, 240, 60 + i % 12, 70 + i * 3) for i in range(30)]
        report = validator.validate(notes)
        # Should generally pass with varied notes
        assert isinstance(report.passed, bool)
    
    def test_summary_generated(self):
        """Test summary is generated."""
        validator = QualityValidator()
        notes = [(i * 240, 240, 60 + i % 12, 70 + i * 2) for i in range(20)]
        report = validator.validate(notes)
        assert len(report.summary) > 0
        assert isinstance(report.summary, str)


class TestQuickValidate:
    """Test quick_validate convenience function."""
    
    def test_quick_validate_returns_tuple(self):
        """Test quick_validate returns correct tuple."""
        notes = [(i * 240, 240, 60 + i % 12, 70 + i * 2) for i in range(20)]
        passed, score, issues = quick_validate(notes)
        assert isinstance(passed, bool)
        assert isinstance(score, float)
        assert isinstance(issues, list)
    
    def test_quick_validate_score_range(self):
        """Test score is in valid range."""
        notes = [(i * 240, 240, 60 + i % 12, 70 + i * 2) for i in range(20)]
        passed, score, issues = quick_validate(notes)
        assert 0.0 <= score <= 1.0
    
    def test_quick_validate_with_genre(self):
        """Test quick_validate with different genres."""
        notes = [(i * 240, 240, 60 + i % 12, 70 + i * 2) for i in range(20)]
        for genre in ["pop", "jazz", "hip_hop"]:
            passed, score, issues = quick_validate(notes, genre=genre)
            assert isinstance(score, float)


class TestGenreProfiles:
    """Test genre profiles are correctly defined."""
    
    def test_genre_profiles_exist(self):
        """Test all expected genre profiles exist."""
        assert "hip_hop" in GENRE_QUALITY_PROFILES
        assert "jazz" in GENRE_QUALITY_PROFILES
        assert "pop" in GENRE_QUALITY_PROFILES
        assert "edm" in GENRE_QUALITY_PROFILES
        assert "rock" in GENRE_QUALITY_PROFILES
    
    def test_genre_profile_structure(self):
        """Test genre profiles have required fields."""
        for genre, profile in GENRE_QUALITY_PROFILES.items():
            assert "tempo_range" in profile
            assert "velocity_variance_min" in profile
            assert isinstance(profile["tempo_range"], tuple)
            assert len(profile["tempo_range"]) == 2


class TestEdgeCases:
    """Test edge cases and error handling."""
    
    def test_single_note(self):
        """Test validation with single note."""
        validator = QualityValidator()
        notes = [(0, 480, 60, 80)]
        report = validator.validate(notes)
        assert isinstance(report, ValidationReport)
    
    def test_very_long_sequence(self):
        """Test validation with many notes."""
        validator = QualityValidator()
        notes = [(i * 120, 120, 60 + i % 12, 70 + i % 30) for i in range(100)]
        report = validator.validate(notes)
        assert report.overall_score > 0
    
    def test_extreme_velocities(self):
        """Test with extreme velocity values."""
        validator = QualityValidator()
        notes = [(0, 480, 60, 1), (480, 480, 62, 127)]
        report = validator.validate(notes)
        assert isinstance(report, ValidationReport)
    
    def test_extreme_pitches(self):
        """Test with extreme pitch values."""
        validator = QualityValidator()
        notes = [(0, 480, 21, 80), (480, 480, 108, 80)]
        report = validator.validate(notes)
        assert isinstance(report, ValidationReport)
    
    def test_unknown_genre(self):
        """Test with unknown genre falls back to pop."""
        validator = QualityValidator()
        notes = [(i * 240, 240, 60 + i % 12, 80) for i in range(10)]
        report = validator.validate(notes, genre="unknown_genre")
        assert isinstance(report, ValidationReport)
    
    def test_unknown_scale(self):
        """Test with unknown scale falls back to major."""
        validator = QualityValidator()
        notes = [(i * 240, 240, 60 + i % 12, 80) for i in range(10)]
        report = validator.validate(notes, scale="unknown_scale")
        assert isinstance(report, ValidationReport)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
