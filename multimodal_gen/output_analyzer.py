"""
Output Analyzer Module — Gives the AI System "Ears"

Post-render audio analysis that compares the generated WAV against genre
expectations. Detects issues like:
  - Drums present in classical/acoustic genres
  - Synthetic vs acoustic piano timbre
  - Genre mismatch (spectral features outside expected range)
  - Dynamic range / loudness problems

Uses librosa (already installed) + scipy for all analysis. No external
dependencies beyond what the project already has.

Architecture:
  OutputSpectralAnalyzer  → Extract spectral features from rendered WAV
  InstrumentDetector      → Detect drums, piano type, harmonic/percussive ratio
  GenreMatchScorer        → Score features against AUDIO_GENRE_TARGETS
  OutputAnalysisReport    → Result dataclass with score, issues, corrections
"""

import logging
import numpy as np
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

try:
    import librosa

    HAS_LIBROSA = True
except ImportError:
    HAS_LIBROSA = False

try:
    from scipy import signal as scipy_signal

    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False

from .utils import SAMPLE_RATE


# =============================================================================
# AUDIO GENRE TARGETS — Expected rendered-output characteristics per genre
# =============================================================================

AUDIO_GENRE_TARGETS: Dict[str, Dict[str, Any]] = {
    "classical": {
        "spectral_centroid_range": (600, 2500),
        "spectral_rolloff_max": 8000,
        "spectral_flatness_max": 0.05,
        "onset_strength_max": 0.4,
        "harmonic_ratio_min": 0.70,
        "drum_presence_max": 0.10,
        "dynamic_range_min_db": 12,
        "expected_timbres": ["acoustic_piano", "strings"],
        "forbidden_timbres": ["synth_piano", "electronic_drums", "808"],
    },
    "cinematic": {
        "spectral_centroid_range": (700, 3000),
        "spectral_rolloff_max": 10000,
        "spectral_flatness_max": 0.08,
        "harmonic_ratio_min": 0.55,
        "drum_presence_max": 0.25,
        "dynamic_range_min_db": 10,
        "expected_timbres": ["piano", "strings", "brass"],
        "forbidden_timbres": ["808", "electronic_drums"],
    },
    "g_funk": {
        "spectral_centroid_range": (1000, 3500),
        "spectral_rolloff_max": 12000,
        "spectral_flatness_max": 0.15,
        "harmonic_ratio_min": 0.40,
        "drum_presence_range": (0.15, 0.60),
        "sub_bass_energy_min": 0.15,
        "dynamic_range_min_db": 6,
    },
    "trap": {
        "spectral_centroid_range": (1500, 4000),
        "spectral_flatness_max": 0.20,
        "harmonic_ratio_min": 0.30,
        "sub_bass_energy_min": 0.30,
        "drum_presence_range": (0.20, 0.70),
        "dynamic_range_min_db": 4,
    },
    "lofi": {
        "spectral_centroid_range": (500, 2500),
        "spectral_rolloff_max": 8000,
        "spectral_flatness_max": 0.10,
        "harmonic_ratio_min": 0.50,
        "drum_presence_range": (0.10, 0.40),
        "dynamic_range_min_db": 6,
    },
    "boom_bap": {
        "spectral_centroid_range": (800, 3000),
        "spectral_flatness_max": 0.12,
        "harmonic_ratio_min": 0.40,
        "drum_presence_range": (0.20, 0.55),
        "dynamic_range_min_db": 6,
    },
    "jazz": {
        "spectral_centroid_range": (600, 2800),
        "spectral_rolloff_max": 10000,
        "spectral_flatness_max": 0.06,
        "harmonic_ratio_min": 0.60,
        "drum_presence_range": (0.05, 0.30),
        "dynamic_range_min_db": 10,
    },
    "pop": {
        "spectral_centroid_range": (1000, 4000),
        "spectral_rolloff_max": 14000,
        "spectral_flatness_max": 0.15,
        "harmonic_ratio_min": 0.40,
        "drum_presence_range": (0.15, 0.50),
        "dynamic_range_min_db": 4,
    },
}


# =============================================================================
# DATA CLASSES
# =============================================================================


@dataclass
class SpectralFeatures:
    """Spectral features extracted from the rendered output."""

    centroid_hz: float = 0.0
    rolloff_hz: float = 0.0
    bandwidth_hz: float = 0.0
    flatness: float = 0.0
    zero_crossing_rate: float = 0.0
    mfcc_mean: List[float] = field(default_factory=list)
    mfcc_variance: float = 0.0
    spectral_contrast: List[float] = field(default_factory=list)
    rms_mean: float = 0.0
    rms_max: float = 0.0
    dynamic_range_db: float = 0.0


@dataclass
class DrumDetection:
    """Results from drum detection in the output."""

    drums_present: bool = False
    percussive_ratio: float = 0.0
    has_kick: bool = False
    has_snare_or_clap: bool = False
    has_hihats: bool = False
    onset_density: float = 0.0


@dataclass
class PianoTypeDetection:
    """Results from piano type detection."""

    piano_detected: bool = False
    piano_type: str = "unknown"  # "acoustic", "synthetic", "unknown"
    confidence: float = 0.0
    inharmonicity_score: float = 0.0
    attack_noisiness: float = 0.0
    mfcc_temporal_variance: float = 0.0


@dataclass
class AnalysisIssue:
    """A single issue detected in the output."""

    severity: str = "warning"  # "info", "warning", "error"
    category: str = ""  # "drums", "timbre", "genre", "dynamics"
    message: str = ""
    metric_name: str = ""
    actual_value: float = 0.0
    expected_range: str = ""


@dataclass
class CorrectionSuggestion:
    """A suggested correction for a detected issue."""

    action: str = ""  # "mute_drums", "swap_instrument", "adjust_eq", "re_render"
    target: str = ""  # "drums", "piano", "bass", etc.
    detail: str = ""  # Human-readable description
    priority: int = 0  # 0=highest


@dataclass
class OutputAnalysisReport:
    """Complete analysis report for a rendered audio file."""

    audio_path: str = ""
    target_genre: str = ""
    genre_match_score: float = 0.0
    spectral: Optional[SpectralFeatures] = None
    drums: Optional[DrumDetection] = None
    piano: Optional[PianoTypeDetection] = None
    issues: List[AnalysisIssue] = field(default_factory=list)
    corrections: List[CorrectionSuggestion] = field(default_factory=list)
    passed: bool = False
    analysis_error: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for render report / JSON-RPC."""
        result: Dict[str, Any] = {
            "audio_path": self.audio_path,
            "target_genre": self.target_genre,
            "genre_match_score": round(self.genre_match_score, 3),
            "passed": self.passed,
        }
        if self.spectral:
            result["spectral"] = {
                "centroid_hz": round(self.spectral.centroid_hz, 1),
                "rolloff_hz": round(self.spectral.rolloff_hz, 1),
                "bandwidth_hz": round(self.spectral.bandwidth_hz, 1),
                "flatness": round(self.spectral.flatness, 4),
                "dynamic_range_db": round(self.spectral.dynamic_range_db, 1),
                "mfcc_variance": round(self.spectral.mfcc_variance, 2),
            }
        if self.drums:
            result["drums"] = {
                "drums_present": self.drums.drums_present,
                "percussive_ratio": round(self.drums.percussive_ratio, 3),
                "has_kick": self.drums.has_kick,
                "has_snare_or_clap": self.drums.has_snare_or_clap,
                "has_hihats": self.drums.has_hihats,
                "onset_density": round(self.drums.onset_density, 2),
            }
        if self.piano:
            result["piano"] = {
                "piano_detected": self.piano.piano_detected,
                "piano_type": self.piano.piano_type,
                "confidence": round(self.piano.confidence, 3),
                "inharmonicity_score": round(self.piano.inharmonicity_score, 4),
                "attack_noisiness": round(self.piano.attack_noisiness, 4),
                "mfcc_temporal_variance": round(
                    self.piano.mfcc_temporal_variance, 2
                ),
            }
        if self.issues:
            result["issues"] = [
                {
                    "severity": i.severity,
                    "category": i.category,
                    "message": i.message,
                }
                for i in self.issues
            ]
        if self.corrections:
            result["corrections"] = [
                {
                    "action": c.action,
                    "target": c.target,
                    "detail": c.detail,
                    "priority": c.priority,
                }
                for c in self.corrections
            ]
        if self.analysis_error:
            result["analysis_error"] = self.analysis_error
        return result


# =============================================================================
# SPECTRAL ANALYZER
# =============================================================================


class OutputSpectralAnalyzer:
    """Extract spectral features from a rendered WAV file."""

    def __init__(self, sr: int = SAMPLE_RATE):
        self.sr = sr

    def analyze(self, audio: np.ndarray, sr: int) -> SpectralFeatures:
        """Analyze audio array and return spectral features."""
        if not HAS_LIBROSA:
            logger.warning("librosa not available — spectral analysis skipped")
            return SpectralFeatures()

        features = SpectralFeatures()

        # Ensure mono
        if len(audio.shape) > 1:
            audio = np.mean(audio, axis=1)

        # Spectral centroid (perceived brightness)
        centroid = librosa.feature.spectral_centroid(y=audio, sr=sr)
        features.centroid_hz = float(np.mean(centroid))

        # Spectral rolloff (high-freq cutoff)
        rolloff = librosa.feature.spectral_rolloff(y=audio, sr=sr)
        features.rolloff_hz = float(np.mean(rolloff))

        # Spectral bandwidth
        bw = librosa.feature.spectral_bandwidth(y=audio, sr=sr)
        features.bandwidth_hz = float(np.mean(bw))

        # Spectral flatness (noise vs tonal: 0=tonal, 1=noise)
        flatness = librosa.feature.spectral_flatness(y=audio)
        features.flatness = float(np.mean(flatness))

        # Zero crossing rate (percussiveness indicator)
        zcr = librosa.feature.zero_crossing_rate(y=audio)
        features.zero_crossing_rate = float(np.mean(zcr))

        # MFCCs for timbral fingerprint
        mfccs = librosa.feature.mfcc(y=audio, sr=sr, n_mfcc=13)
        features.mfcc_mean = np.mean(mfccs, axis=1).tolist()
        features.mfcc_variance = float(np.mean(np.var(mfccs, axis=1)))

        # Spectral contrast (peak-valley ratio per octave band)
        contrast = librosa.feature.spectral_contrast(y=audio, sr=sr)
        features.spectral_contrast = np.mean(contrast, axis=1).tolist()

        # RMS energy and dynamic range
        rms = librosa.feature.rms(y=audio)[0]
        features.rms_mean = float(np.mean(rms))
        features.rms_max = float(np.max(rms))
        rms_nonzero = rms[rms > 1e-10]
        if len(rms_nonzero) > 0:
            features.dynamic_range_db = float(
                20.0 * np.log10(np.max(rms_nonzero) / np.min(rms_nonzero))
            )

        return features


# =============================================================================
# INSTRUMENT DETECTOR
# =============================================================================


class InstrumentDetector:
    """Detect presence and type of instruments in rendered audio."""

    def detect_drums(self, audio: np.ndarray, sr: int) -> DrumDetection:
        """Detect drums using harmonic-percussive source separation."""
        if not HAS_LIBROSA:
            return DrumDetection()

        result = DrumDetection()

        # Mono
        if len(audio.shape) > 1:
            audio = np.mean(audio, axis=1)

        # HPSS — separate harmonic and percussive components
        harmonic, percussive = librosa.effects.hpss(audio)

        total_energy = float(np.sum(audio**2)) + 1e-10
        perc_energy = float(np.sum(percussive**2))
        result.percussive_ratio = perc_energy / total_energy
        result.drums_present = result.percussive_ratio > 0.12

        # Onset density (onsets per second)
        onset_env = librosa.onset.onset_strength(y=audio, sr=sr)
        onsets = librosa.onset.onset_detect(
            y=audio, sr=sr, onset_envelope=onset_env
        )
        duration_sec = len(audio) / sr
        result.onset_density = len(onsets) / max(duration_sec, 0.1)

        if not HAS_SCIPY:
            return result

        # Kick detection — low-frequency transients (< 200 Hz)
        nyq = sr / 2.0
        if nyq > 200:
            b, a = scipy_signal.butter(
                4, 200 / nyq, btype="low", output="ba"
            )
            low_pass = scipy_signal.filtfilt(b, a, audio)
            low_onsets = librosa.onset.onset_detect(y=low_pass, sr=sr)
            result.has_kick = len(low_onsets) > 2

        # Hi-hat detection — high-frequency transients (> 5000 Hz)
        if nyq > 5000:
            b, a = scipy_signal.butter(
                4, 5000 / nyq, btype="high", output="ba"
            )
            high_pass = scipy_signal.filtfilt(b, a, percussive)
            high_onsets = librosa.onset.onset_detect(y=high_pass, sr=sr)
            high_onset_density = len(high_onsets) / max(duration_sec, 0.1)
            result.has_hihats = high_onset_density > 3.0

        # Snare/clap — mid-frequency percussive energy (200–5000 Hz)
        if nyq > 5000:
            b, a = scipy_signal.butter(
                4, [200 / nyq, 5000 / nyq], btype="band", output="ba"
            )
            mid_band = scipy_signal.filtfilt(b, a, percussive)
            mid_energy = float(np.sum(mid_band**2))
            result.has_snare_or_clap = (
                mid_energy / (perc_energy + 1e-10) > 0.3
            )

        return result

    def detect_piano_type(
        self, audio: np.ndarray, sr: int
    ) -> PianoTypeDetection:
        """Detect whether piano sounds acoustic or synthetic.

        Acoustic pianos have:
          - Inharmonic partials (strings are stiff → partials drift sharp)
          - Noisy attack transient (hammer + felt + string)
          - Timbre that evolves over time (MFCC variance is high)

        Synthetic pianos have:
          - Perfectly harmonic partials
          - Clean, uniform attack
          - Static timbre (MFCC variance is low)
        """
        if not HAS_LIBROSA:
            return PianoTypeDetection()

        result = PianoTypeDetection()

        # Mono
        if len(audio.shape) > 1:
            audio = np.mean(audio, axis=1)

        # --- 1. Inharmonicity analysis ---
        # Use YIN pitch estimation to find fundamental
        f0 = librosa.yin(
            audio, fmin=50, fmax=2000, sr=sr, frame_length=4096
        )
        voiced = f0[f0 > 0]
        if len(voiced) < 5:
            # Not enough pitched content to analyze piano
            result.piano_detected = False
            return result

        result.piano_detected = True
        fundamental = float(np.median(voiced))

        # Measure inharmonicity: deviation of partials from integer multiples
        n_fft = 4096
        spectrum = np.abs(librosa.stft(audio, n_fft=n_fft))
        avg_spectrum = np.mean(spectrum, axis=1)
        freqs = librosa.fft_frequencies(sr=sr, n_fft=n_fft)

        inharmonicity_scores: List[float] = []
        for n in range(2, min(8, int((sr / 2) / fundamental))):
            expected = fundamental * n
            # Search within ±3% of expected frequency
            search_lo = expected * 0.97
            search_hi = expected * 1.03
            mask = (freqs >= search_lo) & (freqs <= search_hi)
            if not np.any(mask):
                continue
            masked_spectrum = avg_spectrum.copy()
            masked_spectrum[~mask] = 0
            peak_idx = np.argmax(masked_spectrum)
            if masked_spectrum[peak_idx] < 1e-8:
                continue
            actual = freqs[peak_idx]
            deviation = abs(actual - expected) / expected
            inharmonicity_scores.append(deviation)

        if inharmonicity_scores:
            result.inharmonicity_score = float(np.mean(inharmonicity_scores))

        # --- 2. Attack transient noisiness ---
        onsets_frames = librosa.onset.onset_detect(
            y=audio, sr=sr, units="samples"
        )
        if len(onsets_frames) > 0:
            onset_sample = int(onsets_frames[0])
            attack_end = min(len(audio), onset_sample + int(sr * 0.030))
            attack_region = audio[onset_sample:attack_end]
            if len(attack_region) > 64:
                attack_flatness = librosa.feature.spectral_flatness(
                    y=attack_region
                )
                result.attack_noisiness = float(np.mean(attack_flatness))

        # --- 3. MFCC temporal variance (timbre evolution) ---
        mfccs = librosa.feature.mfcc(y=audio, sr=sr, n_mfcc=13)
        result.mfcc_temporal_variance = float(np.mean(np.var(mfccs, axis=1)))

        # --- 4. Composite classification ---
        # Acoustic evidence scoring
        acoustic_score = 0.0

        # Inharmonicity: acoustic > 0.003, synth < 0.002
        if result.inharmonicity_score > 0.004:
            acoustic_score += 0.35
        elif result.inharmonicity_score > 0.002:
            acoustic_score += 0.15

        # Attack noise: acoustic > 0.08, synth < 0.05
        if result.attack_noisiness > 0.10:
            acoustic_score += 0.25
        elif result.attack_noisiness > 0.06:
            acoustic_score += 0.10

        # MFCC variance: acoustic > 15, synth < 8
        if result.mfcc_temporal_variance > 15.0:
            acoustic_score += 0.25
        elif result.mfcc_temporal_variance > 10.0:
            acoustic_score += 0.10

        # Spectral contrast variation (body resonance indicator)
        contrast = librosa.feature.spectral_contrast(y=audio, sr=sr)
        contrast_var = float(np.mean(np.var(contrast, axis=1)))
        if contrast_var > 50.0:
            acoustic_score += 0.15
        elif contrast_var > 20.0:
            acoustic_score += 0.05

        if acoustic_score >= 0.50:
            result.piano_type = "acoustic"
            result.confidence = min(1.0, acoustic_score)
        else:
            result.piano_type = "synthetic"
            result.confidence = min(1.0, 1.0 - acoustic_score)

        return result


# =============================================================================
# GENRE MATCH SCORER
# =============================================================================


class GenreMatchScorer:
    """Score how well rendered audio matches genre expectations."""

    def __init__(self, targets: Optional[Dict[str, Dict]] = None):
        self.targets = targets or AUDIO_GENRE_TARGETS

    def score(
        self,
        genre: str,
        spectral: SpectralFeatures,
        drums: DrumDetection,
        piano: Optional[PianoTypeDetection] = None,
    ) -> Tuple[float, List[AnalysisIssue]]:
        """Return (score, issues) where score is 0.0–1.0."""
        genre_key = genre.lower().replace("-", "_").replace(" ", "_")
        target = self.targets.get(genre_key)
        if target is None:
            # Unknown genre — pass with neutral score
            return 0.75, []

        scores: List[float] = []
        issues: List[AnalysisIssue] = []

        # --- Spectral centroid ---
        centroid_range = target.get("spectral_centroid_range")
        if centroid_range:
            lo, hi = centroid_range
            if lo <= spectral.centroid_hz <= hi:
                scores.append(1.0)
            else:
                dist = min(
                    abs(spectral.centroid_hz - lo),
                    abs(spectral.centroid_hz - hi),
                )
                s = max(0.0, 1.0 - dist / 2000.0)
                scores.append(s)
                issues.append(
                    AnalysisIssue(
                        severity="warning",
                        category="genre",
                        message=(
                            f"Spectral centroid {spectral.centroid_hz:.0f} Hz "
                            f"outside expected {lo}–{hi} Hz"
                        ),
                        metric_name="spectral_centroid",
                        actual_value=spectral.centroid_hz,
                        expected_range=f"{lo}-{hi}",
                    )
                )

        # --- Spectral rolloff ---
        rolloff_max = target.get("spectral_rolloff_max")
        if rolloff_max is not None:
            if spectral.rolloff_hz <= rolloff_max:
                scores.append(1.0)
            else:
                s = max(
                    0.0,
                    1.0 - (spectral.rolloff_hz - rolloff_max) / 5000.0,
                )
                scores.append(s)
                issues.append(
                    AnalysisIssue(
                        severity="warning",
                        category="genre",
                        message=(
                            f"Spectral rolloff {spectral.rolloff_hz:.0f} Hz "
                            f"exceeds max {rolloff_max} Hz"
                        ),
                        metric_name="spectral_rolloff",
                        actual_value=spectral.rolloff_hz,
                        expected_range=f"<{rolloff_max}",
                    )
                )

        # --- Spectral flatness ---
        flatness_max = target.get("spectral_flatness_max")
        if flatness_max is not None:
            if spectral.flatness <= flatness_max:
                scores.append(1.0)
            else:
                s = max(
                    0.0,
                    1.0 - (spectral.flatness - flatness_max) / 0.2,
                )
                scores.append(s)
                issues.append(
                    AnalysisIssue(
                        severity="info",
                        category="genre",
                        message=(
                            f"Spectral flatness {spectral.flatness:.4f} "
                            f"above threshold {flatness_max}"
                        ),
                        metric_name="spectral_flatness",
                        actual_value=spectral.flatness,
                        expected_range=f"<{flatness_max}",
                    )
                )

        # --- Drum presence ---
        drum_max = target.get("drum_presence_max")
        drum_range = target.get("drum_presence_range")
        if drum_max is not None:
            if drums.percussive_ratio <= drum_max:
                scores.append(1.0)
            else:
                scores.append(0.2)
                issues.append(
                    AnalysisIssue(
                        severity="error",
                        category="drums",
                        message=(
                            f"Drum presence {drums.percussive_ratio:.3f} "
                            f"exceeds max {drum_max} for {genre}"
                        ),
                        metric_name="percussive_ratio",
                        actual_value=drums.percussive_ratio,
                        expected_range=f"<{drum_max}",
                    )
                )
        elif drum_range:
            lo, hi = drum_range
            if lo <= drums.percussive_ratio <= hi:
                scores.append(1.0)
            else:
                dist = min(
                    abs(drums.percussive_ratio - lo),
                    abs(drums.percussive_ratio - hi),
                )
                scores.append(max(0.0, 1.0 - dist / 0.3))

        # --- Dynamic range ---
        dr_min = target.get("dynamic_range_min_db")
        if dr_min is not None:
            if spectral.dynamic_range_db >= dr_min:
                scores.append(1.0)
            else:
                s = spectral.dynamic_range_db / max(dr_min, 1.0)
                scores.append(max(0.0, s))
                if spectral.dynamic_range_db < dr_min * 0.7:
                    issues.append(
                        AnalysisIssue(
                            severity="warning",
                            category="dynamics",
                            message=(
                                f"Dynamic range {spectral.dynamic_range_db:.1f} dB "
                                f"below minimum {dr_min} dB for {genre}"
                            ),
                            metric_name="dynamic_range_db",
                            actual_value=spectral.dynamic_range_db,
                            expected_range=f">{dr_min}",
                        )
                    )

        # --- Harmonic ratio ---
        # We compute this from percussive ratio: harmonic ≈ 1 - percussive
        h_ratio_min = target.get("harmonic_ratio_min")
        if h_ratio_min is not None:
            harmonic_ratio = 1.0 - drums.percussive_ratio
            if harmonic_ratio >= h_ratio_min:
                scores.append(1.0)
            else:
                scores.append(harmonic_ratio / h_ratio_min)

        # --- Piano timbre check (for genres that expect acoustic piano) ---
        forbidden = target.get("forbidden_timbres", [])
        expected = target.get("expected_timbres", [])
        if piano and piano.piano_detected:
            if piano.piano_type == "synthetic" and "synth_piano" in forbidden:
                scores.append(0.3)
                issues.append(
                    AnalysisIssue(
                        severity="error",
                        category="timbre",
                        message=(
                            f"Piano sounds synthetic (confidence "
                            f"{piano.confidence:.2f}) but {genre} "
                            f"expects acoustic piano"
                        ),
                        metric_name="piano_type",
                        actual_value=piano.confidence,
                        expected_range="acoustic",
                    )
                )
            elif piano.piano_type == "acoustic" and "acoustic_piano" in expected:
                scores.append(1.0)

        if not scores:
            return 0.75, issues

        return float(np.mean(scores)), issues


# =============================================================================
# CORRECTION ENGINE
# =============================================================================


def generate_corrections(
    issues: List[AnalysisIssue],
) -> List[CorrectionSuggestion]:
    """Map analysis issues to actionable corrections."""
    corrections: List[CorrectionSuggestion] = []

    for issue in issues:
        if issue.category == "drums" and "exceeds" in issue.message:
            corrections.append(
                CorrectionSuggestion(
                    action="mute_drums",
                    target="drums",
                    detail="Drums detected in a genre that expects minimal drums. "
                    "Mute drum tracks and re-render.",
                    priority=0,
                )
            )

        elif issue.category == "timbre" and "synthetic" in issue.message:
            corrections.append(
                CorrectionSuggestion(
                    action="swap_instrument",
                    target="piano",
                    detail="Piano timbre detected as synthetic. Try a different "
                    "piano sample or apply warmth/resonance processing.",
                    priority=1,
                )
            )

        elif issue.category == "genre" and "centroid" in issue.message.lower():
            if issue.actual_value > 0 and "outside" in issue.message:
                corrections.append(
                    CorrectionSuggestion(
                        action="adjust_eq",
                        target="master",
                        detail=f"Spectral centroid at {issue.actual_value:.0f} Hz "
                        f"is outside genre range. Apply corrective EQ.",
                        priority=2,
                    )
                )

        elif issue.category == "dynamics":
            corrections.append(
                CorrectionSuggestion(
                    action="adjust_dynamics",
                    target="master",
                    detail="Dynamic range too narrow. Reduce compression "
                    "or increase velocity variation.",
                    priority=2,
                )
            )

    # Remove duplicate actions
    seen = set()
    unique: List[CorrectionSuggestion] = []
    for c in corrections:
        key = (c.action, c.target)
        if key not in seen:
            seen.add(key)
            unique.append(c)

    unique.sort(key=lambda c: c.priority)
    return unique


# =============================================================================
# MAIN ANALYZER FACADE
# =============================================================================


class OutputAnalyzer:
    """Analyze a rendered WAV and produce an OutputAnalysisReport.

    Usage::

        analyzer = OutputAnalyzer()
        report = analyzer.analyze("output/song.wav", target_genre="classical")
        if not report.passed:
            for issue in report.issues:
                print(issue.message)
    """

    PASS_THRESHOLD = 0.60  # Conservative — avoids false positive re-renders

    def __init__(
        self,
        sr: int = SAMPLE_RATE,
        pass_threshold: float = 0.60,
    ):
        self.sr = sr
        self.pass_threshold = pass_threshold
        self._spectral_analyzer = OutputSpectralAnalyzer(sr=sr)
        self._instrument_detector = InstrumentDetector()
        self._scorer = GenreMatchScorer()

    def analyze(
        self,
        audio_path: str,
        target_genre: str = "pop",
    ) -> OutputAnalysisReport:
        """Analyze a rendered WAV file against genre expectations.

        Args:
            audio_path: Path to the rendered WAV file.
            target_genre: The intended genre.

        Returns:
            OutputAnalysisReport with score, issues, and corrections.
        """
        report = OutputAnalysisReport(
            audio_path=audio_path,
            target_genre=target_genre,
        )

        if not HAS_LIBROSA:
            report.analysis_error = "librosa not installed — cannot analyze"
            report.passed = True  # Don't block rendering
            return report

        # Load audio
        try:
            audio, sr = librosa.load(audio_path, sr=self.sr, mono=False)
        except Exception as e:
            report.analysis_error = f"Failed to load audio: {e}"
            report.passed = True
            return report

        # Convert to mono for analysis (keep original for HPSS)
        if len(audio.shape) > 1:
            audio_mono = np.mean(audio, axis=0)
        else:
            audio_mono = audio

        if len(audio_mono) < sr:
            report.analysis_error = "Audio too short for meaningful analysis"
            report.passed = True
            return report

        # --- Extract features ---
        logger.info("Analyzing output: %s (genre=%s)", audio_path, target_genre)

        report.spectral = self._spectral_analyzer.analyze(audio_mono, sr)
        report.drums = self._instrument_detector.detect_drums(audio_mono, sr)
        report.piano = self._instrument_detector.detect_piano_type(
            audio_mono, sr
        )

        # --- Score against genre targets ---
        score, issues = self._scorer.score(
            target_genre, report.spectral, report.drums, report.piano
        )
        report.genre_match_score = score
        report.issues = issues

        # --- Generate corrections ---
        report.corrections = generate_corrections(issues)

        # --- Pass/fail ---
        report.passed = score >= self.pass_threshold

        logger.info(
            "Output analysis complete: score=%.3f passed=%s issues=%d",
            score,
            report.passed,
            len(issues),
        )
        if report.issues:
            for issue in report.issues:
                logger.info(
                    "  [%s] %s: %s", issue.severity, issue.category, issue.message
                )

        return report

    def analyze_audio_array(
        self,
        audio: np.ndarray,
        sr: int,
        target_genre: str = "pop",
    ) -> OutputAnalysisReport:
        """Analyze an in-memory audio array (skips file I/O).

        Useful for analyzing audio before it's saved to disk, or for
        testing with synthetic signals.
        """
        report = OutputAnalysisReport(
            audio_path="<in-memory>",
            target_genre=target_genre,
        )

        if not HAS_LIBROSA:
            report.analysis_error = "librosa not installed"
            report.passed = True
            return report

        if len(audio.shape) > 1:
            audio_mono = np.mean(audio, axis=0)
        else:
            audio_mono = audio

        if len(audio_mono) < sr:
            report.analysis_error = "Audio too short"
            report.passed = True
            return report

        report.spectral = self._spectral_analyzer.analyze(audio_mono, sr)
        report.drums = self._instrument_detector.detect_drums(audio_mono, sr)
        report.piano = self._instrument_detector.detect_piano_type(
            audio_mono, sr
        )

        score, issues = self._scorer.score(
            target_genre, report.spectral, report.drums, report.piano
        )
        report.genre_match_score = score
        report.issues = issues
        report.corrections = generate_corrections(issues)
        report.passed = score >= self.pass_threshold

        return report
