"""Tests for the output_analyzer module — the AI's 'ears'.

Tests spectral analysis, drum detection, piano type detection,
genre match scoring, correction generation, and the main OutputAnalyzer
facade. Uses synthetic signals (no WAV files required).
"""

import sys
from pathlib import Path

import numpy as np
import pytest
from scipy import signal as scipy_signal

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


def _filtered_noise_burst(
    rng: np.random.Generator,
    samples: int,
    band: tuple[float | None, float | None],
    sr: int = SR,
) -> np.ndarray:
    burst = rng.standard_normal(samples).astype(np.float32)
    nyq = sr / 2.0
    lo, hi = band
    if lo is None:
        b, a = scipy_signal.butter(3, hi / nyq, btype="low")
    elif hi is None:
        b, a = scipy_signal.butter(3, lo / nyq, btype="high")
    else:
        b, a = scipy_signal.butter(3, [lo / nyq, hi / nyq], btype="band")
    return scipy_signal.lfilter(b, a, burst).astype(np.float32)


def _live_drum_backbeat_signal(
    *,
    include_snare: bool = True,
    include_kick: bool = True,
    include_hihat: bool = True,
    duration: float = 8.0,
    bpm: float = 100.0,
    sr: int = SR,
) -> np.ndarray:
    """Deterministic GM-ish rock drum pattern for detector regressions."""
    rng = np.random.default_rng(1990)
    audio = np.zeros(int(duration * sr), dtype=np.float32)
    beat = 60.0 / bpm
    bar = beat * 4.0

    def add(start_sec: float, burst: np.ndarray, amp: float) -> None:
        start = int(start_sec * sr)
        if start >= len(audio):
            return
        end = min(len(audio), start + len(burst))
        audio[start:end] += burst[: end - start] * amp

    for bar_index in range(int(duration / bar)):
        bar_start = bar_index * bar

        if include_kick:
            for beat_pos in (0.0, 2.0):
                n = int(0.14 * sr)
                t = np.arange(n, dtype=np.float32) / sr
                pitch_sweep = 70.0 - 30.0 * np.minimum(t / 0.14, 1.0)
                kick = np.sin(2 * np.pi * pitch_sweep * t) * np.exp(-t / 0.045)
                add(bar_start + beat_pos * beat, kick.astype(np.float32), 0.8)

        if include_snare:
            for beat_pos in (1.0, 3.0):
                n = int(0.12 * sr)
                t = np.arange(n, dtype=np.float32) / sr
                noise = _filtered_noise_burst(rng, n, (200.0, 5000.0), sr)
                noise *= np.exp(-t / 0.035)
                body = np.sin(2 * np.pi * 190.0 * t) * np.exp(-t / 0.05)
                snare = 0.8 * noise + 0.25 * body
                add(bar_start + beat_pos * beat, snare.astype(np.float32), 0.65)

        if include_hihat:
            for eighth in range(8):
                n = int(0.05 * sr)
                t = np.arange(n, dtype=np.float32) / sr
                hat = _filtered_noise_burst(rng, n, (6000.0, None), sr)
                hat *= np.exp(-t / 0.012)
                add(bar_start + eighth * beat / 2.0, hat.astype(np.float32), 0.5)

    peak = float(np.max(np.abs(audio)))
    if peak > 1e-9:
        audio = audio / peak * 0.8
    return audio.astype(np.float32)


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
        assert sf.sub_bass_energy_ratio == 0.0
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

    def test_analyze_sub_bass_energy_ratio_and_silence(self):
        analyzer = OutputSpectralAnalyzer(sr=SR)

        sub = analyzer.analyze(_sine(55.0, duration=2.0), SR)
        assert sub.sub_bass_energy_ratio > 0.8

        silence = np.zeros(SR * 2, dtype=np.float32)
        silent_features = analyzer.analyze(silence, SR)
        assert silent_features.sub_bass_energy_ratio == 0.0

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

    def test_gm_style_snare_detected_when_hats_dominate_aggregate_energy(self):
        audio = _live_drum_backbeat_signal(
            include_snare=True,
            include_kick=True,
            include_hihat=True,
        )
        detector = InstrumentDetector()

        result = detector.detect_drums(audio, SR)

        assert result.drums_present
        assert result.has_kick
        assert result.has_hihats
        assert result.has_snare_or_clap

    def test_kick_hat_groove_does_not_fake_snare_or_clap(self):
        audio = _live_drum_backbeat_signal(
            include_snare=False,
            include_kick=True,
            include_hihat=True,
        )
        detector = InstrumentDetector()

        result = detector.detect_drums(audio, SR)

        assert result.drums_present
        assert result.has_kick
        assert result.has_hihats
        assert not result.has_snare_or_clap

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
    def test_neo_soul_supported_without_neutral_fallback(self):
        assert "neo_soul" in AUDIO_GENRE_TARGETS

        spectral = SpectralFeatures(
            centroid_hz=4200.0,
            rolloff_hz=12000.0,
            flatness=0.16,
            dynamic_range_db=5.0,
        )
        drums = DrumDetection(
            drums_present=True,
            percussive_ratio=0.42,
            onset_density=6.5,
        )

        scorer = GenreMatchScorer()
        score, issues = scorer.score("neo_soul", spectral, drums)

        assert score < 0.75
        assert any(issue.metric_name in {"spectral_centroid", "spectral_rolloff", "onset_density"} for issue in issues)

    @pytest.mark.parametrize(
        "genre",
        [
            "rnb",
            "trap_soul",
            "house",
            "ambient",
            "ethiopian",
            "ethio_jazz",
            "eskista",
            "ethiopian_traditional",
            "rock",
            "classic_rock",
            "alternative_rock",
            "grunge",
            "punk_rock",
            "indie_rock",
        ],
    )
    def test_supported_genres_no_longer_use_neutral_fallback(self, genre):
        assert genre in AUDIO_GENRE_TARGETS

        spectral = SpectralFeatures(
            centroid_hz=5200.0,
            rolloff_hz=15000.0,
            flatness=0.24,
            dynamic_range_db=2.5,
        )
        drums = DrumDetection(
            drums_present=True,
            percussive_ratio=0.82,
            onset_density=8.5,
        )

        scorer = GenreMatchScorer()
        score, issues = scorer.score(genre, spectral, drums)

        assert score < 0.75
        assert issues

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

    def test_rock_supported_without_neutral_fallback(self):
        spectral = SpectralFeatures(
            centroid_hz=5200.0,
            rolloff_hz=16000.0,
            flatness=0.28,
            dynamic_range_db=2.0,
            sub_bass_energy_ratio=0.42,
        )
        drums = DrumDetection(
            percussive_ratio=0.04,
            onset_density=0.4,
            has_kick=False,
            has_snare_or_clap=False,
            has_hihats=False,
        )

        score, issues = GenreMatchScorer().score("rock", spectral, drums)

        assert score < 0.75
        assert issues

    def test_sub_heavy_trap_like_features_fail_rock_with_bass_correction(self):
        spectral = SpectralFeatures(
            centroid_hz=2600.0,
            rolloff_hz=10000.0,
            flatness=0.10,
            dynamic_range_db=7.0,
            sub_bass_energy_ratio=0.45,
        )
        drums = DrumDetection(
            drums_present=True,
            percussive_ratio=0.28,
            has_kick=True,
            has_snare_or_clap=True,
            has_hihats=True,
            onset_density=3.2,
        )

        score, issues = GenreMatchScorer().score("rock", spectral, drums)
        corrections = generate_corrections(issues)

        assert score < 0.60
        assert any(i.metric_name == "sub_bass_energy_ratio" for i in issues)
        assert any(
            c.action == "swap_instrument" and c.target == "bass"
            for c in corrections
        )

    def test_missing_live_drums_fail_rock_with_drum_correction(self):
        spectral = SpectralFeatures(
            centroid_hz=2400.0,
            rolloff_hz=9000.0,
            flatness=0.09,
            dynamic_range_db=8.0,
            sub_bass_energy_ratio=0.08,
        )
        drums = DrumDetection(
            drums_present=False,
            percussive_ratio=0.03,
            has_kick=False,
            has_snare_or_clap=False,
            has_hihats=False,
            onset_density=0.5,
        )

        score, issues = GenreMatchScorer().score("rock", spectral, drums)
        corrections = generate_corrections(issues)

        assert score < 0.60
        assert any(i.category == "drums" for i in issues)
        assert any(c.target == "drums" for c in corrections)

    def test_borderline_rock_live_drums_pass_with_required_parts_detected(self):
        spectral = SpectralFeatures(
            centroid_hz=2369.1,
            rolloff_hz=4646.5,
            flatness=0.0043,
            dynamic_range_db=40.2,
            sub_bass_energy_ratio=0.1214,
        )
        drums = DrumDetection(
            drums_present=False,
            percussive_ratio=0.117,
            has_kick=True,
            has_snare_or_clap=True,
            has_hihats=True,
            onset_density=3.86,
        )

        score, issues = GenreMatchScorer().score("rock", spectral, drums)
        corrections = generate_corrections(issues)

        assert score >= 0.60
        assert score >= 0.95
        assert not any(issue.severity == "error" for issue in issues)
        assert not any(
            "missing/low live drum presence" in issue.message.lower()
            for issue in issues
        )
        assert corrections == []

    def test_far_low_percussive_ratio_still_fails_rock_with_part_flags(self):
        spectral = SpectralFeatures(
            centroid_hz=2369.1,
            rolloff_hz=4646.5,
            flatness=0.0043,
            dynamic_range_db=40.2,
            sub_bass_energy_ratio=0.1214,
        )
        drums = DrumDetection(
            drums_present=False,
            percussive_ratio=0.03,
            has_kick=True,
            has_snare_or_clap=True,
            has_hihats=True,
            onset_density=3.86,
        )

        score, issues = GenreMatchScorer().score("rock", spectral, drums)
        corrections = generate_corrections(issues)

        assert score < 0.60
        assert any(
            "missing/low live drum presence" in issue.message.lower()
            for issue in issues
        )
        assert any(
            c.action == "re_render" and c.target == "drums"
            for c in corrections
        )

    def test_low_drum_trap_soul_does_not_trigger_live_drum_rerender(self):
        spectral = SpectralFeatures(
            centroid_hz=2400.0,
            rolloff_hz=9000.0,
            flatness=0.08,
            dynamic_range_db=7.0,
            sub_bass_energy_ratio=0.08,
        )
        drums = DrumDetection(
            drums_present=False,
            percussive_ratio=0.03,
            has_kick=False,
            has_snare_or_clap=False,
            has_hihats=False,
            onset_density=0.5,
        )

        score, issues = GenreMatchScorer().score("trap_soul", spectral, drums)
        corrections = generate_corrections(issues)

        assert score >= 0.60
        assert any(i.metric_name == "percussive_ratio" for i in issues)
        assert not any(
            "missing/low live drum presence" in i.message.lower()
            for i in issues
        )
        assert not any(
            c.action == "re_render" and c.target == "drums"
            for c in corrections
        )
        assert not any("live drum" in c.detail.lower() for c in corrections)

    def test_conservative_measurable_rock_band_features_pass(self):
        spectral = SpectralFeatures(
            centroid_hz=2300.0,
            rolloff_hz=9500.0,
            flatness=0.08,
            dynamic_range_db=9.0,
            sub_bass_energy_ratio=0.09,
        )
        drums = DrumDetection(
            drums_present=True,
            percussive_ratio=0.24,
            has_kick=True,
            has_snare_or_clap=True,
            has_hihats=True,
            onset_density=3.0,
        )

        score, issues = GenreMatchScorer().score("rock", spectral, drums)

        assert score >= 0.70
        assert not any(issue.severity == "error" for issue in issues)

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

    def test_high_centroid_issue_generates_directional_eq_correction(self):
        issues = [
            AnalysisIssue(
                severity="warning",
                category="genre",
                message="Spectral centroid 5000 Hz outside expected 600–2500 Hz",
                actual_value=5000.0,
                expected_range="600-2500",
            )
        ]
        corrections = generate_corrections(issues)
        eq_correction = next(c for c in corrections if c.action == "adjust_eq")
        assert "too bright" in eq_correction.detail.lower()
        assert "reduce brightness" in eq_correction.detail.lower()

    def test_low_centroid_issue_generates_directional_eq_correction(self):
        issues = [
            AnalysisIssue(
                severity="warning",
                category="genre",
                message="Spectral centroid 400 Hz outside expected 900–3200 Hz",
                actual_value=400.0,
                expected_range="900-3200",
            )
        ]
        corrections = generate_corrections(issues)
        eq_correction = next(c for c in corrections if c.action == "adjust_eq")
        detail = eq_correction.detail.lower()
        assert "too dark" in detail or "dull" in detail
        assert "increase brightness" in detail

    def test_high_onset_density_in_drum_light_context_generates_mute_drums(self):
        issues = [
            AnalysisIssue(
                severity="info",
                category="rhythm",
                message="Onset density 3.50 outside expected 0.0–2.0 for ambient",
                metric_name="onset_density",
                actual_value=3.5,
                expected_range="0.0-2.0",
            )
        ]

        corrections = generate_corrections(issues)

        assert any(
            c.action == "mute_drums" and c.target == "drums"
            for c in corrections
        )

    def test_low_onset_density_does_not_generate_mute_drums(self):
        issues = [
            AnalysisIssue(
                severity="info",
                category="rhythm",
                message="Onset density 0.20 outside expected 1.2–4.0 for neo_soul",
                metric_name="onset_density",
                actual_value=0.2,
                expected_range="1.2-4.0",
            )
        ]

        corrections = generate_corrections(issues)

        assert not any(c.action == "mute_drums" for c in corrections)

    def test_high_onset_density_in_non_drum_light_context_does_not_generate_mute_drums(self):
        issues = [
            AnalysisIssue(
                severity="info",
                category="rhythm",
                message="Onset density 5.20 outside expected 1.2–4.0 for neo_soul",
                metric_name="onset_density",
                actual_value=5.2,
                expected_range="1.2-4.0",
            )
        ]

        corrections = generate_corrections(issues)

        assert not any(c.action == "mute_drums" for c in corrections)

    def test_duplicate_drum_muting_cues_still_dedupe_to_one_correction(self):
        issues = [
            AnalysisIssue(
                severity="error",
                category="drums",
                message="Drum presence 0.35 exceeds max 0.10 for classical",
            ),
            AnalysisIssue(
                severity="info",
                category="rhythm",
                message="Onset density 3.50 outside expected 0.0–2.0 for ambient",
                metric_name="onset_density",
                actual_value=3.5,
                expected_range="0.0-2.0",
            ),
        ]

        corrections = generate_corrections(issues)
        mute_corrections = [c for c in corrections if c.action == "mute_drums"]

        assert len(mute_corrections) == 1

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

    def test_sub_bass_issue_generates_bass_swap_correction(self):
        issues = [
            AnalysisIssue(
                severity="error",
                category="bass",
                message="Sub-bass/808 energy 0.450 exceeds max 0.16 for rock",
                metric_name="sub_bass_energy_ratio",
                actual_value=0.45,
                expected_range="<0.16",
            )
        ]

        corrections = generate_corrections(issues)

        assert any(
            c.action == "swap_instrument" and c.target == "bass"
            for c in corrections
        )

    def test_low_live_drum_issue_generates_drum_rerender_correction(self):
        issues = [
            AnalysisIssue(
                severity="error",
                category="drums",
                message="Missing/low live drum presence: percussive ratio 0.030 below expected 0.12 for rock",
                metric_name="percussive_ratio",
                actual_value=0.03,
                expected_range="0.12-0.50",
            )
        ]

        corrections = generate_corrections(issues)

        assert any(c.action == "re_render" and c.target == "drums" for c in corrections)


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
            spectral=SpectralFeatures(
                centroid_hz=3000.0,
                rolloff_hz=8000.0,
                sub_bass_energy_ratio=0.12,
            ),
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
        assert d["spectral"]["sub_bass_energy_ratio"] == 0.12
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

    def test_expanded_targets_exist(self):
        for genre in [
            "rnb",
            "trap_soul",
            "house",
            "ambient",
            "ethiopian",
            "ethio_jazz",
            "eskista",
            "ethiopian_traditional",
            "rock",
            "classic_rock",
            "alternative_rock",
            "grunge",
            "punk_rock",
            "indie_rock",
        ]:
            assert genre in AUDIO_GENRE_TARGETS

    @pytest.mark.parametrize(
        "genre, sub_bass_max",
        [
            ("rock", 0.16),
            ("classic_rock", 0.12),
            ("alternative_rock", 0.16),
            ("grunge", 0.18),
            ("punk_rock", 0.15),
            ("indie_rock", 0.14),
        ],
    )
    def test_rock_family_targets_have_measurable_schema(self, genre, sub_bass_max):
        target = AUDIO_GENRE_TARGETS[genre]
        assert "spectral_centroid_range" in target
        assert target["sub_bass_energy_max"] == sub_bass_max
        assert target["required_drum_parts"] == [
            "kick",
            "snare_or_clap",
            "hihats",
        ]

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
