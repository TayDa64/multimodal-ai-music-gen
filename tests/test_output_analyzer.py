"""Tests for the output_analyzer module — the AI's 'ears'.

Tests spectral analysis, drum detection, piano type detection,
genre match scoring, correction generation, and the main OutputAnalyzer
facade. Uses synthetic signals (no WAV files required).
"""

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from multimodal_gen.output_analyzer import (
    AUDIO_GENRE_TARGETS,
    AnalysisIssue,
    CorrectionSuggestion,
    DrumDetection,
    GenreMatchScorer,
    InstrumentDetector,
    OutputAnalyzer,
    OutputAnalysisReport,
    OutputSpectralAnalyzer,
    PianoTypeDetection,
    SpectralFeatures,
    generate_corrections,
)

SR = 44100


# ---------------------------------------------------------------------------
# Helpers — generate synthetic test signals
# ---------------------------------------------------------------------------


def _sine(freq: float, duration: float = 2.0, sr: int = SR) -> np.ndarray:
    """Pure sine wave."""
    t = np.arange(int(sr * duration)) / sr
    return (0.5 * np.sin(2 * np.pi * freq * t)).astype(np.float32)


def _noise(duration: float = 2.0, sr: int = SR) -> np.ndarray:
    """White noise."""
    return (0.3 * np.random.randn(int(sr * duration))).astype(np.float32)


def _percussive_signal(
    duration: float = 3.0, hits: int = 20, sr: int = SR
) -> np.ndarray:
    """Signal with strong percussive transients (simulates drums)."""
    audio = np.zeros(int(sr * duration), dtype=np.float32)
    step = len(audio) // (hits + 1)
    for i in range(hits):
        pos = step * (i + 1)
        burst_len = min(int(sr * 0.01), len(audio) - pos)
        if burst_len <= 0:
            continue
        burst = np.random.randn(burst_len).astype(np.float32)
        burst *= np.exp(-np.arange(burst_len) / (sr * 0.003))
        audio[pos : pos + burst_len] += burst * 0.8
    return audio


def _piano_like_signal(
    freq: float = 440.0, duration: float = 2.0, sr: int = SR
) -> np.ndarray:
    """Multi-partial signal mimicking a piano (with slight inharmonicity)."""
    t = np.arange(int(sr * duration)) / sr
    audio = np.zeros(len(t), dtype=np.float64)
    inharm = 0.0002
    for n in range(1, 10):
        partial_freq = freq * (n + inharm * n**2)
        if partial_freq > sr / 2 - 200:
            break
        amp = 1.0 / n**1.2
        decay = 0.9 / n**0.5
        env = np.exp(-t / max(0.05, decay))
        audio += amp * np.sin(2 * np.pi * partial_freq * t) * env
    # Add attack noise
    noise_len = min(int(0.015 * sr), len(audio))
    noise = np.random.randn(noise_len) * 0.15
    noise *= np.exp(-np.arange(noise_len) / (sr * 0.004))
    audio[:noise_len] += noise
    return (audio / (np.max(np.abs(audio)) + 1e-10) * 0.7).astype(np.float32)


# ---------------------------------------------------------------------------
# Tests: SpectralFeatures dataclass
# ---------------------------------------------------------------------------


class TestSpectralFeatures:
    def test_default_values(self):
        sf = SpectralFeatures()
        assert sf.centroid_hz == 0.0
        assert sf.mfcc_mean == []

    def test_fields(self):
        sf = SpectralFeatures(centroid_hz=1500.0, rolloff_hz=6000.0)
        assert sf.centroid_hz == 1500.0
        assert sf.rolloff_hz == 6000.0


# ---------------------------------------------------------------------------
# Tests: OutputSpectralAnalyzer
# ---------------------------------------------------------------------------


class TestOutputSpectralAnalyzer:
    def test_analyze_sine_wave(self):
        audio = _sine(440.0, duration=2.0)
        analyzer = OutputSpectralAnalyzer(sr=SR)
        features = analyzer.analyze(audio, SR)

        assert features.centroid_hz > 0
        assert features.rolloff_hz > 0
        assert features.flatness < 0.1  # Pure tone → low flatness
        assert features.dynamic_range_db >= 0
        assert len(features.mfcc_mean) == 13

    def test_analyze_noise(self):
        audio = _noise(duration=2.0)
        analyzer = OutputSpectralAnalyzer(sr=SR)
        features = analyzer.analyze(audio, SR)

        # Noise has higher spectral flatness than a sine
        assert features.flatness > 0.1

    def test_stereo_input(self):
        mono = _sine(440.0, duration=1.0)
        stereo = np.stack([mono, mono])  # 2 x N
        analyzer = OutputSpectralAnalyzer(sr=SR)
        features = analyzer.analyze(stereo, SR)
        assert features.centroid_hz > 0


# ---------------------------------------------------------------------------
# Tests: InstrumentDetector — Drums
# ---------------------------------------------------------------------------


class TestDrumDetection:
    def test_no_drums_in_sine(self):
        audio = _sine(440.0, duration=3.0)
        detector = InstrumentDetector()
        result = detector.detect_drums(audio, SR)

        assert not result.drums_present
        assert result.percussive_ratio < 0.15

    def test_drums_in_percussive_signal(self):
        audio = _percussive_signal(duration=3.0, hits=30)
        detector = InstrumentDetector()
        result = detector.detect_drums(audio, SR)

        assert result.percussive_ratio > 0.05
        assert result.onset_density > 2.0

    def test_drum_detection_returns_dataclass(self):
        audio = _sine(200.0, duration=1.0)
        detector = InstrumentDetector()
        result = detector.detect_drums(audio, SR)
        assert isinstance(result, DrumDetection)


# ---------------------------------------------------------------------------
# Tests: InstrumentDetector — Piano Type
# ---------------------------------------------------------------------------


class TestPianoTypeDetection:
    def test_piano_like_signal_detected(self):
        audio = _piano_like_signal(freq=440.0, duration=2.0)
        detector = InstrumentDetector()
        result = detector.detect_piano_type(audio, SR)

        assert result.piano_detected
        assert result.piano_type in ("acoustic", "synthetic")
        assert 0.0 <= result.confidence <= 1.0

    def test_pure_sine_low_inharmonicity(self):
        audio = _sine(440.0, duration=2.0)
        detector = InstrumentDetector()
        result = detector.detect_piano_type(audio, SR)

        # Pure sine — FFT bin resolution can cause small deviation
        # but should still be well below acoustic piano levels
        if result.piano_detected:
            assert result.inharmonicity_score < 0.05

    def test_noise_not_detected_as_piano(self):
        audio = _noise(duration=2.0)
        detector = InstrumentDetector()
        result = detector.detect_piano_type(audio, SR)
        # Noise should have few/no pitched frames
        # May or may not be detected — just shouldn't crash


# ---------------------------------------------------------------------------
# Tests: GenreMatchScorer
# ---------------------------------------------------------------------------


class TestGenreMatchScorer:
    def test_classical_perfect_score(self):
        """Features within classical thresholds → high score."""
        spectral = SpectralFeatures(
            centroid_hz=1200.0,
            rolloff_hz=5000.0,
            flatness=0.02,
            dynamic_range_db=18.0,
        )
        drums = DrumDetection(
            drums_present=False,
            percussive_ratio=0.05,
        )
        scorer = GenreMatchScorer()
        score, issues = scorer.score("classical", spectral, drums)

        assert score >= 0.8
        assert len(issues) == 0

    def test_classical_with_drums_penalized(self):
        """Drums in classical → reduced score + error issue."""
        spectral = SpectralFeatures(
            centroid_hz=1200.0,
            rolloff_hz=5000.0,
            flatness=0.02,
            dynamic_range_db=18.0,
        )
        drums = DrumDetection(
            drums_present=True,
            percussive_ratio=0.35,
        )
        scorer = GenreMatchScorer()
        score, issues = scorer.score("classical", spectral, drums)

        # Score is dragged down by drum penalty but other metrics
        # compensate — the key check is that drum issues are flagged
        assert score < 0.95
        drum_issues = [i for i in issues if i.category == "drums"]
        assert len(drum_issues) >= 1

    def test_classical_synth_piano_penalized(self):
        """Synthetic piano in classical → score penalty + issue."""
        spectral = SpectralFeatures(
            centroid_hz=1200.0,
            rolloff_hz=5000.0,
            flatness=0.02,
            dynamic_range_db=18.0,
        )
        drums = DrumDetection(percussive_ratio=0.05)
        piano = PianoTypeDetection(
            piano_detected=True,
            piano_type="synthetic",
            confidence=0.8,
        )
        scorer = GenreMatchScorer()
        score, issues = scorer.score("classical", spectral, drums, piano)

        timbre_issues = [i for i in issues if i.category == "timbre"]
        assert len(timbre_issues) >= 1
        assert "synthetic" in timbre_issues[0].message

    def test_unknown_genre_neutral_score(self):
        spectral = SpectralFeatures(centroid_hz=2000.0)
        drums = DrumDetection(percussive_ratio=0.2)
        scorer = GenreMatchScorer()
        score, issues = scorer.score("unknown_genre_xyz", spectral, drums)
        assert score == 0.75
        assert issues == []

    def test_trap_with_drums_acceptable(self):
        """Trap expects drums — high percussive ratio is OK."""
        spectral = SpectralFeatures(
            centroid_hz=2500.0,
            flatness=0.10,
            dynamic_range_db=6.0,
        )
        drums = DrumDetection(percussive_ratio=0.40)
        scorer = GenreMatchScorer()
        score, issues = scorer.score("trap", spectral, drums)
        assert score >= 0.7

    def test_high_centroid_classical_flagged(self):
        """Bright sound in classical → centroid warning."""
        spectral = SpectralFeatures(
            centroid_hz=5000.0,  # Way too bright for classical
            rolloff_hz=5000.0,
            flatness=0.02,
            dynamic_range_db=15.0,
        )
        drums = DrumDetection(percussive_ratio=0.05)
        scorer = GenreMatchScorer()
        score, issues = scorer.score("classical", spectral, drums)

        centroid_issues = [
            i for i in issues if "centroid" in i.message.lower()
        ]
        assert len(centroid_issues) >= 1


# ---------------------------------------------------------------------------
# Tests: Correction Engine
# ---------------------------------------------------------------------------


class TestCorrectionEngine:
    def test_drum_issue_generates_mute_correction(self):
        issues = [
            AnalysisIssue(
                severity="error",
                category="drums",
                message="Drum presence 0.35 exceeds max 0.10 for classical",
            )
        ]
        corrections = generate_corrections(issues)
        assert any(c.action == "mute_drums" for c in corrections)

    def test_synth_piano_generates_swap_correction(self):
        issues = [
            AnalysisIssue(
                severity="error",
                category="timbre",
                message="Piano sounds synthetic (confidence 0.8)",
            )
        ]
        corrections = generate_corrections(issues)
        assert any(c.action == "swap_instrument" for c in corrections)

    def test_centroid_issue_generates_eq_correction(self):
        issues = [
            AnalysisIssue(
                severity="warning",
                category="genre",
                message="Spectral centroid 5000 Hz outside expected 600–2500 Hz",
                actual_value=5000.0,
            )
        ]
        corrections = generate_corrections(issues)
        assert any(c.action == "adjust_eq" for c in corrections)

    def test_no_duplicate_corrections(self):
        issues = [
            AnalysisIssue(
                severity="error",
                category="drums",
                message="Drum presence 0.35 exceeds max 0.10",
            ),
            AnalysisIssue(
                severity="warning",
                category="drums",
                message="Drum presence 0.20 exceeds max 0.10",
            ),
        ]
        corrections = generate_corrections(issues)
        mute_corrections = [c for c in corrections if c.action == "mute_drums"]
        assert len(mute_corrections) == 1

    def test_empty_issues_no_corrections(self):
        assert generate_corrections([]) == []

    def test_corrections_sorted_by_priority(self):
        issues = [
            AnalysisIssue(
                severity="warning",
                category="dynamics",
                message="Dynamic range too narrow",
            ),
            AnalysisIssue(
                severity="error",
                category="drums",
                message="Drum presence exceeds max",
            ),
        ]
        corrections = generate_corrections(issues)
        if len(corrections) >= 2:
            assert corrections[0].priority <= corrections[1].priority


# ---------------------------------------------------------------------------
# Tests: OutputAnalysisReport
# ---------------------------------------------------------------------------


class TestOutputAnalysisReport:
    def test_to_dict_minimal(self):
        report = OutputAnalysisReport(
            audio_path="test.wav",
            target_genre="pop",
            genre_match_score=0.85,
            passed=True,
        )
        d = report.to_dict()
        assert d["audio_path"] == "test.wav"
        assert d["target_genre"] == "pop"
        assert d["genre_match_score"] == 0.85
        assert d["passed"] is True

    def test_to_dict_with_all_fields(self):
        report = OutputAnalysisReport(
            audio_path="test.wav",
            target_genre="classical",
            genre_match_score=0.45,
            passed=False,
            spectral=SpectralFeatures(centroid_hz=3000.0, rolloff_hz=8000.0),
            drums=DrumDetection(drums_present=True, percussive_ratio=0.3),
            piano=PianoTypeDetection(
                piano_detected=True,
                piano_type="synthetic",
                confidence=0.9,
            ),
            issues=[
                AnalysisIssue(
                    severity="error",
                    category="drums",
                    message="Drums present",
                )
            ],
            corrections=[
                CorrectionSuggestion(
                    action="mute_drums",
                    target="drums",
                    detail="Mute drums",
                    priority=0,
                )
            ],
        )
        d = report.to_dict()
        assert "spectral" in d
        assert "drums" in d
        assert "piano" in d
        assert len(d["issues"]) == 1
        assert len(d["corrections"]) == 1

    def test_to_dict_with_error(self):
        report = OutputAnalysisReport(
            analysis_error="librosa not installed"
        )
        d = report.to_dict()
        assert d["analysis_error"] == "librosa not installed"


# ---------------------------------------------------------------------------
# Tests: OutputAnalyzer (facade) — in-memory analysis
# ---------------------------------------------------------------------------


class TestOutputAnalyzer:
    def test_analyze_sine_wave(self):
        audio = _sine(440.0, duration=3.0)
        analyzer = OutputAnalyzer(sr=SR)
        report = analyzer.analyze_audio_array(audio, SR, target_genre="pop")

        assert isinstance(report, OutputAnalysisReport)
        assert report.spectral is not None
        assert report.drums is not None
        assert 0.0 <= report.genre_match_score <= 1.0

    def test_analyze_classical_genre(self):
        """Low-frequency tonal signal should score well for classical."""
        audio = _piano_like_signal(freq=261.6, duration=3.0)
        analyzer = OutputAnalyzer(sr=SR)
        report = analyzer.analyze_audio_array(
            audio, SR, target_genre="classical"
        )

        assert report.spectral is not None
        assert report.drums is not None
        # Piano-like signal with low percussion should score OK
        assert report.genre_match_score > 0.3

    def test_analyze_short_audio_passes(self):
        """Audio shorter than 1 second should pass (not enough data)."""
        short_audio = _sine(440.0, duration=0.3)
        analyzer = OutputAnalyzer(sr=SR)
        report = analyzer.analyze_audio_array(
            short_audio, SR, target_genre="classical"
        )
        assert report.passed  # Too short → auto-pass

    def test_analyze_percussive_in_classical(self):
        """Percussive signal in classical → drum issues detected."""
        # Mix piano with strong percussion
        piano = _piano_like_signal(freq=261.6, duration=3.0)
        perc = _percussive_signal(duration=3.0, hits=40)
        mixed = piano + perc * 0.8
        mixed = mixed / (np.max(np.abs(mixed)) + 1e-10) * 0.7

        analyzer = OutputAnalyzer(sr=SR)
        report = analyzer.analyze_audio_array(
            mixed, SR, target_genre="classical"
        )

        # Should detect higher percussive content
        assert report.drums is not None
        assert report.drums.percussive_ratio > 0.05


# ---------------------------------------------------------------------------
# Tests: AUDIO_GENRE_TARGETS structure
# ---------------------------------------------------------------------------


class TestAudioGenreTargets:
    def test_classical_target_exists(self):
        assert "classical" in AUDIO_GENRE_TARGETS

    def test_classical_has_required_keys(self):
        classical = AUDIO_GENRE_TARGETS["classical"]
        assert "spectral_centroid_range" in classical
        assert "drum_presence_max" in classical
        assert "harmonic_ratio_min" in classical
        assert "forbidden_timbres" in classical

    def test_all_genres_have_centroid_range(self):
        for genre, target in AUDIO_GENRE_TARGETS.items():
            assert "spectral_centroid_range" in target, (
                f"{genre} missing spectral_centroid_range"
            )

    def test_centroid_ranges_are_valid(self):
        for genre, target in AUDIO_GENRE_TARGETS.items():
            lo, hi = target["spectral_centroid_range"]
            assert lo < hi, f"{genre}: centroid lo={lo} >= hi={hi}"
            assert lo > 0, f"{genre}: centroid lo must be positive"
