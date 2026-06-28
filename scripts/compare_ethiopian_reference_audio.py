#!/usr/bin/env python
"""Task 129 Ethiopian source-truth/reference-audio comparison harness.

This script is intentionally diagnostic: it generates isolated source probes from the
current Ethiopian instrument generators, extracts descriptor sets from generated and
available reference audio, and writes comparison artifacts. It is not a pass/fail
validator and must not be used to claim Ethiopian timbre is solved.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Mapping, NamedTuple, Optional, Sequence, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import librosa
import numpy as np
import soundfile as sf

from multimodal_gen.assets_gen import (
    SAMPLE_RATE,
    generate_begena_tone,
    generate_krar_tone,
    generate_masenqo_tone,
    generate_washint_tone,
)

INSTRUMENTS: Tuple[str, ...] = ("krar", "masenqo", "washint", "begena")

BEGENA_LOW_FUNDAMENTAL_RANGE_HZ: Tuple[float, float] = (50.0, 150.0)
BEGENA_REFERENCE_SCALE_DURATION_SECONDS = 24.63
BEGENA_REFERENCE_SCALE_ONSETS_SECONDS: Tuple[float, ...] = (
    2.206,
    3.971,
    5.352,
    6.455,
    8.220,
    9.671,
    11.029,
    12.179,
    12.899,
    14.153,
    14.640,
    15.534,
    16.742,
    18.530,
    20.515,
    21.780,
    22.163,
    23.174,
    23.824,
)
BEGENA_REFERENCE_SCALE_OBSERVED_F0_MEDIANS_HZ: Tuple[Optional[float], ...] = (
    58.16,
    61.11,
    77.65,
    81.47,
    101.88,
    58.21,
    40.10,
    44.43,
    58.22,
    101.85,
    101.80,
    82.18,
    77.68,
    61.00,
    58.24,
    57.03,
    61.68,
    56.87,
    None,  # Final high YIN estimate was unreliable and is not used literally.
)
BEGENA_REFERENCE_SCALE_FREQUENCIES_HZ: Tuple[float, ...] = (
    58.16,
    61.11,
    77.65,
    81.47,
    101.88,
    58.21,
    50.00,
    50.00,
    58.22,
    101.85,
    101.80,
    82.18,
    77.68,
    61.00,
    58.24,
    57.03,
    61.68,
    56.87,
    58.16,
)
BEGENA_REFERENCE_SCALE_TIMBRE_VARIATIONS: Tuple[Dict[str, Any], ...] = (
    {"string_quality": "stable", "buzzer_position": 0.34, "sustain_bias": 0.86, "velocity": 0.74},
    {"string_quality": "worn", "buzzer_position": 0.37, "sustain_bias": 0.90, "velocity": 0.76},
    {"string_quality": "lively", "buzzer_position": 0.39, "sustain_bias": 0.84, "velocity": 0.78},
    {"string_quality": "stable", "buzzer_position": 0.35, "sustain_bias": 0.88, "velocity": 0.75},
    {"string_quality": "worn", "buzzer_position": 0.42, "sustain_bias": 0.92, "velocity": 0.80},
    {"string_quality": "stable", "buzzer_position": 0.33, "sustain_bias": 0.87, "velocity": 0.74},
    {"string_quality": "worn", "buzzer_position": 0.31, "sustain_bias": 0.91, "velocity": 0.72},
    {"string_quality": "lively", "buzzer_position": 0.32, "sustain_bias": 0.85, "velocity": 0.73},
    {"string_quality": "stable", "buzzer_position": 0.36, "sustain_bias": 0.89, "velocity": 0.76},
    {"string_quality": "lively", "buzzer_position": 0.41, "sustain_bias": 0.84, "velocity": 0.79},
    {"string_quality": "worn", "buzzer_position": 0.43, "sustain_bias": 0.93, "velocity": 0.80},
    {"string_quality": "stable", "buzzer_position": 0.38, "sustain_bias": 0.88, "velocity": 0.77},
    {"string_quality": "lively", "buzzer_position": 0.37, "sustain_bias": 0.85, "velocity": 0.76},
    {"string_quality": "worn", "buzzer_position": 0.34, "sustain_bias": 0.90, "velocity": 0.74},
    {"string_quality": "stable", "buzzer_position": 0.35, "sustain_bias": 0.89, "velocity": 0.75},
    {"string_quality": "worn", "buzzer_position": 0.31, "sustain_bias": 0.91, "velocity": 0.73},
    {"string_quality": "lively", "buzzer_position": 0.38, "sustain_bias": 0.84, "velocity": 0.76},
    {"string_quality": "stable", "buzzer_position": 0.33, "sustain_bias": 0.88, "velocity": 0.74},
    {"string_quality": "worn", "buzzer_position": 0.36, "sustain_bias": 0.92, "velocity": 0.73},
)

BEGENA_REFERENCE_SCALE_SOURCE_NOTES: Tuple[str, ...] = (
    "Optional public-reference-shaped probe for the Wikimedia Commons BegenaScalePlucked.ogg scale reference; this is isolated source synthesis, not song generation.",
    "Onset and f0 values are bounded internal pre-analysis observations used to make descriptor comparisons fairer; they are not hard authenticity claims.",
    "Optional public-reference constraints preserved for this legacy Commons diagnostic: low fundamentals around 50-150 Hz, 10 strings / five pitch pairs, sparse monodic plucked scale-like behavior, leather-buzzer roughness, and long sustain.",
    "String quality, buzzer position, and sustain bias vary subtly note-to-note for the optional public-reference probe.",
)

BEGENA_REFERENCE_SCALE_WARNINGS: Tuple[str, ...] = (
    "Generated probe remains a diagnostic current-generator source probe; do not claim Begena timbre is solved from descriptor proximity.",
    "Observed sub-50 Hz medians were clamped into the optional public-reference low fundamental range.",
    "The final unreliable high f0 estimate was discarded rather than treated as a literal 180 Hz Begena pitch.",
)

PUBLIC_REFERENCE_MANIFEST: Dict[str, Dict[str, Any]] = {
    "begena": {
        "status": "available",
        "page": "https://commons.wikimedia.org/wiki/File:BegenaScalePlucked.ogg",
        "direct_url": "https://upload.wikimedia.org/wikipedia/commons/8/89/BegenaScalePlucked.ogg",
        "filename": "BegenaScalePlucked.ogg",
        "license": "CC BY-SA 3.0 / GFDL",
        "attribution": "Temambiru / Temesgen Hussein, per Wikimedia Commons file page",
        "reason": "Public Commons OGG reference is available for optional download.",
        "supports_user_ref": True,
    },
    "krar": {
        "status": "unavailable_by_default",
        "source_urls": [
            "https://commons.wikimedia.org/wiki/Category:Krar",
            "https://en.wikipedia.org/wiki/Krar",
        ],
        "reason": "No public downloadable WAV/OGG/MP3 reference found in current pass; use --user-ref krar=PATH to compare user-supplied audio.",
        "supports_user_ref": True,
    },
    "masenqo": {
        "status": "unavailable_by_default",
        "source_urls": [
            "https://commons.wikimedia.org/wiki/Category:Masenqo",
            "https://en.wikipedia.org/wiki/Masenqo",
        ],
        "reason": "No public downloadable WAV/OGG/MP3 reference found in current pass; use --user-ref masenqo=PATH to compare user-supplied audio.",
        "supports_user_ref": True,
    },
    "washint": {
        "status": "unavailable_by_default",
        "source_urls": [
            "https://commons.wikimedia.org/wiki/Category:Washint",
            "https://en.wikipedia.org/wiki/Washint",
        ],
        "reason": "No public downloadable WAV/OGG/MP3 reference found in current pass; use --user-ref washint=PATH to compare user-supplied audio.",
        "supports_user_ref": True,
    },
}

GENERATED_PROBE_SPECS: Dict[str, Dict[str, Any]] = {
    "krar": {
        "generator": "generate_krar_tone",
        "probe_shape": "single_note",
        "frequency_hz": 329.63,
        "duration_seconds": 1.20,
        "velocity": 0.82,
        "profile": "traditional_warm",
        "seed": 129001,
    },
    "masenqo": {
        "generator": "generate_masenqo_tone",
        "probe_shape": "single_note",
        "frequency_hz": 329.63,
        "duration_seconds": 1.20,
        "velocity": 0.82,
        "expressiveness": 0.80,
        "profile": "vocal_clean",
        "seed": 129002,
    },
    "washint": {
        "generator": "generate_washint_tone",
        "probe_shape": "single_note",
        "frequency_hz": 659.25,
        "duration_seconds": 1.20,
        "velocity": 0.80,
        "profile": "alto_breathy",
        "add_ornament": False,
        "seed": 129003,
    },
    "begena": {
        "generator": "generate_begena_tone",
        "probe_shape": "reference_scale_shape",
        "duration_seconds": BEGENA_REFERENCE_SCALE_DURATION_SECONDS,
        "onset_times_seconds": BEGENA_REFERENCE_SCALE_ONSETS_SECONDS,
        "observed_f0_medians_hz": BEGENA_REFERENCE_SCALE_OBSERVED_F0_MEDIANS_HZ,
        "frequencies_hz": BEGENA_REFERENCE_SCALE_FREQUENCIES_HZ,
        "frequency_range_hz": BEGENA_LOW_FUNDAMENTAL_RANGE_HZ,
        "note_variations": BEGENA_REFERENCE_SCALE_TIMBRE_VARIATIONS,
        "velocity": 0.76,
        "profile": "paraliturgical_drone",
        "buzzers_enabled": True,
        "buzzer_position": 0.35,
        "string_quality": "stable",
        "sustain_bias": 0.88,
        "source_truth_constraints": {
            "low_fundamental_range_hz": BEGENA_LOW_FUNDAMENTAL_RANGE_HZ,
            "string_layout": "10 strings / five pitch pairs",
            "texture": "sparse monodic plucked scale-like behavior",
            "buzzers_and_leather_roughness_default": True,
            "long_sustain_default": True,
            "isolated_source_synthesis": True,
        },
        "source_notes": BEGENA_REFERENCE_SCALE_SOURCE_NOTES,
        "warnings": BEGENA_REFERENCE_SCALE_WARNINGS,
        "seed": 129004,
    },
}

BAND_RANGES_HZ: Dict[str, Tuple[float, float]] = {
    "sub": (20.0, 60.0),
    "low": (60.0, 250.0),
    "low_mid": (250.0, 500.0),
    "mid": (500.0, 2000.0),
    "high_mid": (2000.0, 6000.0),
    "high": (6000.0, math.inf),
}

REFERENCE_SHAPE_F0_RANGES_HZ: Dict[str, Tuple[float, float]] = {
    "krar": (45.0, 360.0),
    "masenqo": (70.0, 650.0),
    "washint": (180.0, 1400.0),
    "begena": BEGENA_LOW_FUNDAMENTAL_RANGE_HZ,
}
REFERENCE_SHAPE_ANALYSIS_F0_RANGES_HZ: Dict[str, Tuple[float, float]] = {
    "krar": (35.0, 720.0),
    "masenqo": (50.0, 1000.0),
    "washint": (90.0, 1700.0),
    "begena": (35.0, 320.0),
}
REFERENCE_SHAPE_MAX_METADATA_ONSETS = 96
REFERENCE_SHAPE_MAX_GENERATION_EVENTS = 144
REFERENCE_SHAPE_MIN_ONSET_GAP_SECONDS = 0.045
REFERENCE_SHAPE_MAX_DURATION_SECONDS = 90.0
REFERENCE_SHAPE_NOTE_HEADROOM_GAIN: Dict[str, float] = {
    "krar": 0.70,
    "masenqo": 0.72,
    "washint": 0.72,
    "begena": 0.66,
}
REFERENCE_SHAPE_MAX_NOTE_PEAK: Dict[str, float] = {
    "krar": 0.82,
    "masenqo": 0.84,
    "washint": 0.84,
    "begena": 0.78,
}
REFERENCE_SHAPE_FADE_IN_SECONDS: Dict[str, float] = {
    "krar": 0.0035,
    "masenqo": 0.0060,
    "washint": 0.0070,
    "begena": 0.0045,
}
REFERENCE_SHAPE_FADE_OUT_SECONDS: Dict[str, Tuple[float, float]] = {
    "krar": (0.050, 0.120),
    "masenqo": (0.080, 0.180),
    "washint": (0.070, 0.140),
    "begena": (0.140, 0.360),
}
REFERENCE_SHAPE_MP3_FADE_OUT_SECONDS: Dict[str, Tuple[float, float]] = {
    # User MP3-shaped Begena probes should sustain, but not smear every event
    # into the long public/paper-reference hall-like tail used by the default
    # paraliturgical diagnostic shape.
    "begena": (0.095, 0.240),
}
REFERENCE_SHAPE_MP3_DURATION_BOUNDS: Dict[str, Tuple[float, float, float]] = {
    "begena": (0.180, 2.55, 0.46),
}
KRAR_FOCUS_DENSE_ONSET_THRESHOLD = 1.65
KRAR_FOCUS_LOW_F0_MEDIAN_HZ = 145.0
KRAR_FOCUS_STRONG_LOW_BAND_RATIO = 0.58
KRAR_FOCUS_SKIP_F0_HZ = 92.0
KRAR_FOCUS_ATTENUATE_F0_HZ = 116.0
KRAR_FOCUS_SUSTAINED_SECONDS = 0.36
KRAR_FOCUS_ATTENUATED_GAIN = 0.34


class ReferenceCandidate(NamedTuple):
    """A local audio file to compare against a generated probe."""

    instrument: str
    source_id: str
    path: Path
    kind: str
    metadata: Mapping[str, Any]


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def default_output_dir() -> Path:
    return Path("output") / "_diagnostics" / f"task129_reference_compare_{_timestamp()}"


def _resolve_path(path: Path | str, *, base_dir: Optional[Path] = None) -> Path:
    resolved = Path(path).expanduser()
    if resolved.is_absolute():
        return resolved
    return (base_dir or Path.cwd()).joinpath(resolved)


def normalize_instruments(values: Optional[Sequence[str]]) -> List[str]:
    if not values or "all" in values:
        return list(INSTRUMENTS)

    normalized: List[str] = []
    for value in values:
        instrument = str(value).strip().lower()
        if instrument not in INSTRUMENTS:
            raise ValueError(f"Unsupported instrument '{value}'. Expected one of: {', '.join(INSTRUMENTS)}")
        if instrument not in normalized:
            normalized.append(instrument)
    return normalized or list(INSTRUMENTS)


def parse_user_ref_arguments(values: Optional[Sequence[str]]) -> Dict[str, List[Path]]:
    refs: Dict[str, List[Path]] = {instrument: [] for instrument in INSTRUMENTS}
    for raw in values or []:
        if "=" not in raw:
            raise ValueError(f"--user-ref must be instrument=path, got: {raw!r}")
        instrument_raw, path_raw = raw.split("=", 1)
        instrument = instrument_raw.strip().lower()
        if instrument not in INSTRUMENTS:
            raise ValueError(f"Unsupported --user-ref instrument '{instrument_raw}'. Expected one of: {', '.join(INSTRUMENTS)}")
        if not path_raw.strip():
            raise ValueError(f"--user-ref for {instrument} has an empty path")
        refs[instrument].append(Path(path_raw.strip()))
    return {instrument: paths for instrument, paths in refs.items() if paths}


def _rms(audio: np.ndarray) -> float:
    arr = np.asarray(audio, dtype=np.float64).reshape(-1)
    if arr.size == 0:
        return 0.0
    return float(np.sqrt(np.mean(arr ** 2)))


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        candidate = float(value)
    except (TypeError, ValueError):
        return default
    if math.isfinite(candidate):
        return candidate
    return default


def _as_mono_float(audio: np.ndarray | Sequence[float]) -> np.ndarray:
    arr = np.asarray(audio, dtype=np.float64)
    if arr.ndim > 1:
        arr = np.mean(arr, axis=1)
    arr = np.ravel(arr)
    return np.nan_to_num(arr, nan=0.0, posinf=0.0, neginf=0.0)


def _feature_mean_std(feature: np.ndarray, prefix: str) -> Dict[str, float]:
    arr = np.asarray(feature, dtype=np.float64)
    if arr.size == 0:
        return {f"{prefix}_mean": 0.0, f"{prefix}_std": 0.0}
    return {
        f"{prefix}_mean": _safe_float(np.mean(arr)),
        f"{prefix}_std": _safe_float(np.std(arr)),
    }


def _analysis_fft_params(num_samples: int) -> Tuple[int, int]:
    if num_samples <= 0:
        return 64, 16
    n_fft = min(2048, max(64, 2 ** int(math.floor(math.log2(max(64, num_samples))))))
    hop_length = max(16, min(512, n_fft // 4))
    return int(n_fft), int(hop_length)


def _band_energy_ratios(audio: np.ndarray, sample_rate: int) -> Dict[str, float]:
    y = _as_mono_float(audio)
    if y.size == 0 or not np.any(y):
        return {name: 0.0 for name in BAND_RANGES_HZ}

    window = np.hanning(y.size) if y.size > 2 else np.ones_like(y)
    spectrum = np.abs(np.fft.rfft(y * window)) ** 2
    total = float(np.sum(spectrum))
    if total <= 1e-18:
        return {name: 0.0 for name in BAND_RANGES_HZ}

    freqs = np.fft.rfftfreq(y.size, d=1.0 / sample_rate)
    ratios: Dict[str, float] = {}
    nyquist = sample_rate / 2.0
    for name, (low_hz, high_hz) in BAND_RANGES_HZ.items():
        high = nyquist if math.isinf(high_hz) else min(high_hz, nyquist)
        band = (freqs >= low_hz) & (freqs < high)
        ratios[name] = _safe_float(np.sum(spectrum[band]) / total)
    return ratios


def _sustain_decay_metrics(audio: np.ndarray, sample_rate: int) -> Dict[str, float]:
    y = _as_mono_float(audio)
    if y.size == 0:
        return {
            "attack_time_to_peak": 0.0,
            "effective_duration_above_20db": 0.0,
            "tail_to_attack_rms": 0.0,
            "active_start_seconds": 0.0,
            "active_end_seconds": 0.0,
        }

    window = max(1, int(0.010 * sample_rate))
    if y.size >= window and window > 1:
        envelope = np.convolve(np.abs(y), np.ones(window, dtype=np.float64) / window, mode="same")
    else:
        envelope = np.abs(y)

    peak = float(np.max(envelope)) if envelope.size else 0.0
    if peak <= 1e-12:
        return {
            "attack_time_to_peak": 0.0,
            "effective_duration_above_20db": 0.0,
            "tail_to_attack_rms": 0.0,
            "active_start_seconds": 0.0,
            "active_end_seconds": 0.0,
        }

    peak_index = int(np.argmax(envelope))
    active = np.flatnonzero(envelope >= peak * 0.10)  # 20 dB below peak amplitude.
    if active.size:
        active_start = int(active[0])
        active_end = int(active[-1])
    else:  # Defensive fallback; the peak itself should normally be active.
        active_start = peak_index
        active_end = peak_index

    active_len = max(1, active_end - active_start + 1)
    effective_duration = float(active_len / sample_rate)

    attack_len = max(1, min(active_len, int(0.10 * sample_rate)))
    attack_end = min(y.size, active_start + attack_len)
    attack_rms = _rms(y[active_start:attack_end])

    tail_len = max(1, min(active_len, attack_len))
    tail_start = max(active_start, active_end - tail_len + 1)
    tail_end = min(y.size, active_end + 1)
    tail_rms = _rms(y[tail_start:tail_end])

    return {
        "attack_time_to_peak": _safe_float(max(0, peak_index - active_start) / sample_rate),
        "effective_duration_above_20db": _safe_float(effective_duration),
        "tail_to_attack_rms": _safe_float(tail_rms / max(attack_rms, 1e-12)),
        "active_start_seconds": _safe_float(active_start / sample_rate),
        "active_end_seconds": _safe_float((active_end + 1) / sample_rate),
    }


def adjacent_sample_jump_diagnostics(audio: np.ndarray | Sequence[float]) -> Dict[str, float]:
    """Return objective discontinuity/pop diagnostics for a mono signal.

    These are diagnostic-only descriptors. They do not judge authenticity, but
    they make abrupt click-like sample discontinuities visible in reports/tests.
    """

    y = _as_mono_float(audio)
    if y.size < 2:
        return {
            "max_adjacent_sample_jump": 0.0,
            "p95_adjacent_sample_jump": 0.0,
            "p99_adjacent_sample_jump": 0.0,
            "p999_adjacent_sample_jump": 0.0,
            "max_boundary_discontinuity": 0.0,
        }

    jumps = np.abs(np.diff(y))
    return {
        "max_adjacent_sample_jump": _safe_float(np.max(jumps)),
        "p95_adjacent_sample_jump": _safe_float(np.percentile(jumps, 95)),
        "p99_adjacent_sample_jump": _safe_float(np.percentile(jumps, 99)),
        "p999_adjacent_sample_jump": _safe_float(np.percentile(jumps, 99.9)),
        "max_boundary_discontinuity": _safe_float(max(abs(float(y[0])), abs(float(y[-1])))),
    }


def _estimate_f0_yin(audio: np.ndarray, sample_rate: int, n_fft: int, hop_length: int) -> Dict[str, Optional[float]]:
    y = _as_mono_float(audio)
    if y.size < max(64, int(0.050 * sample_rate)) or float(np.max(np.abs(y))) <= 1e-8:
        return {"f0_yin_median_hz": None, "f0_yin_voiced_fraction": 0.0}

    fmin = 30.0
    fmax = min(2000.0, sample_rate / 2.0 - 1.0)
    if fmax <= fmin:
        return {"f0_yin_median_hz": None, "f0_yin_voiced_fraction": 0.0}

    try:
        minimum_frame_for_fmin = int(math.ceil(2.2 * sample_rate / fmin))
        frame_length = min(max(256, n_fft, minimum_frame_for_fmin), max(256, y.size))
        if frame_length < minimum_frame_for_fmin:
            return {"f0_yin_median_hz": None, "f0_yin_voiced_fraction": 0.0}
        f0 = librosa.yin(y, fmin=fmin, fmax=fmax, sr=sample_rate, frame_length=frame_length, hop_length=hop_length)
        finite = np.asarray(f0[np.isfinite(f0)], dtype=np.float64)
        finite = finite[(finite >= fmin) & (finite <= fmax)]
        if finite.size == 0:
            return {"f0_yin_median_hz": None, "f0_yin_voiced_fraction": 0.0}
        return {
            "f0_yin_median_hz": _safe_float(np.median(finite)),
            "f0_yin_voiced_fraction": _safe_float(finite.size / max(1, np.asarray(f0).size)),
        }
    except Exception as exc:  # pragma: no cover - defensive fallback for backend edge cases.
        return {"f0_yin_median_hz": None, "f0_yin_voiced_fraction": 0.0, "f0_yin_error": str(exc)}


def extract_descriptors(audio: np.ndarray | Sequence[float], sample_rate: int) -> Dict[str, Any]:
    """Extract diagnostic audio descriptors from mono audio.

    The return shape is JSON-serializable and stable enough for tests/reports, but
    these descriptors are evidence inputs only, not pass/fail thresholds.
    """

    y = _as_mono_float(audio)
    original_duration = float(y.size / sample_rate) if sample_rate > 0 else 0.0
    work = y if y.size else np.zeros(1, dtype=np.float64)
    n_fft, hop_length = _analysis_fft_params(work.size)

    descriptors: Dict[str, Any] = {
        "duration": _safe_float(original_duration),
        "rms": _rms(work),
        "peak": _safe_float(np.max(np.abs(work)) if work.size else 0.0),
    }

    try:
        descriptors.update(_feature_mean_std(librosa.feature.spectral_centroid(y=work, sr=sample_rate, n_fft=n_fft, hop_length=hop_length), "spectral_centroid"))
        descriptors.update(_feature_mean_std(librosa.feature.spectral_rolloff(y=work, sr=sample_rate, n_fft=n_fft, hop_length=hop_length), "spectral_rolloff"))
        descriptors.update(_feature_mean_std(librosa.feature.spectral_bandwidth(y=work, sr=sample_rate, n_fft=n_fft, hop_length=hop_length), "spectral_bandwidth"))
        descriptors.update(_feature_mean_std(librosa.feature.spectral_flatness(y=work, n_fft=n_fft, hop_length=hop_length), "spectral_flatness"))
        zero_crossing = librosa.feature.zero_crossing_rate(work, frame_length=n_fft, hop_length=hop_length)
        descriptors["zero_crossing_mean"] = _safe_float(np.mean(zero_crossing))
    except Exception as exc:  # pragma: no cover - kept fail-open for unusual reference files.
        descriptors["spectral_feature_error"] = str(exc)
        for key in (
            "spectral_centroid",
            "spectral_rolloff",
            "spectral_bandwidth",
            "spectral_flatness",
        ):
            descriptors.update(_feature_mean_std(np.zeros(1), key))
        descriptors["zero_crossing_mean"] = 0.0

    try:
        mfcc = librosa.feature.mfcc(y=work, sr=sample_rate, n_mfcc=13, n_fft=n_fft, hop_length=hop_length)
        descriptors["mfcc_mean"] = [_safe_float(value) for value in np.mean(mfcc, axis=1)]
        descriptors["mfcc_std"] = [_safe_float(value) for value in np.std(mfcc, axis=1)]
    except Exception as exc:  # pragma: no cover - defensive fallback.
        descriptors["mfcc_error"] = str(exc)
        descriptors["mfcc_mean"] = [0.0] * 13
        descriptors["mfcc_std"] = [0.0] * 13

    try:
        onset_env = librosa.onset.onset_strength(y=work, sr=sample_rate, hop_length=hop_length)
        onset_times = librosa.onset.onset_detect(onset_envelope=onset_env, sr=sample_rate, hop_length=hop_length, units="time")
        descriptors["onset_strength_mean"] = _safe_float(np.mean(onset_env)) if onset_env.size else 0.0
        descriptors["onset_strength_std"] = _safe_float(np.std(onset_env)) if onset_env.size else 0.0
        descriptors["onset_strength_max"] = _safe_float(np.max(onset_env)) if onset_env.size else 0.0
        descriptors["onset_count"] = int(len(onset_times))
        descriptors["onset_density"] = _safe_float(len(onset_times) / max(original_duration, 1e-9))
    except Exception as exc:  # pragma: no cover - defensive fallback.
        descriptors["onset_error"] = str(exc)
        descriptors["onset_strength_mean"] = 0.0
        descriptors["onset_strength_std"] = 0.0
        descriptors["onset_strength_max"] = 0.0
        descriptors["onset_count"] = 0
        descriptors["onset_density"] = 0.0

    try:
        magnitude = np.abs(librosa.stft(work, n_fft=n_fft, hop_length=hop_length))
        if magnitude.shape[1] > 1:
            normalized = magnitude / (np.sum(magnitude, axis=0, keepdims=True) + 1e-12)
            spectral_flux = np.sqrt(np.sum(np.diff(normalized, axis=1) ** 2, axis=0))
        else:
            spectral_flux = np.zeros(1, dtype=np.float64)
        descriptors["spectral_flux_mean"] = _safe_float(np.mean(spectral_flux))
        descriptors["spectral_flux_std"] = _safe_float(np.std(spectral_flux))
    except Exception as exc:  # pragma: no cover - defensive fallback.
        descriptors["spectral_flux_error"] = str(exc)
        descriptors["spectral_flux_mean"] = 0.0
        descriptors["spectral_flux_std"] = 0.0

    try:
        harmonic, percussive = librosa.effects.hpss(work)
        harmonic_rms = _rms(harmonic)
        percussive_rms = _rms(percussive)
        descriptors["hpss_harmonic_rms"] = harmonic_rms
        descriptors["hpss_percussive_rms"] = percussive_rms
        descriptors["hpss_harmonic_percussive_ratio"] = _safe_float(harmonic_rms / max(percussive_rms, 1e-12))
    except Exception as exc:  # pragma: no cover - defensive fallback.
        descriptors["hpss_error"] = str(exc)
        descriptors["hpss_harmonic_rms"] = 0.0
        descriptors["hpss_percussive_rms"] = 0.0
        descriptors["hpss_harmonic_percussive_ratio"] = 0.0

    descriptors["band_energy_ratios"] = _band_energy_ratios(work, sample_rate)
    descriptors.update(_sustain_decay_metrics(work, sample_rate))
    descriptors.update(adjacent_sample_jump_diagnostics(work))
    descriptors.update(_estimate_f0_yin(work, sample_rate, n_fft, hop_length))
    return _clean_for_json(descriptors)


def _safe_percentiles(values: np.ndarray, percentiles: Sequence[float] = (10, 25, 50, 75, 90)) -> Dict[str, Optional[float]]:
    finite = np.asarray(values, dtype=np.float64)
    finite = finite[np.isfinite(finite)]
    if finite.size == 0:
        return {f"p{int(percentile)}": None for percentile in percentiles}
    return {
        f"p{int(percentile)}": _safe_float(np.percentile(finite, percentile))
        for percentile in percentiles
    }


def _deduplicate_onsets(onsets: Sequence[float], *, min_gap_seconds: float) -> List[float]:
    deduped: List[float] = []
    for onset in sorted(_safe_float(value) for value in onsets):
        if onset < 0.0:
            continue
        if not deduped or onset - deduped[-1] >= min_gap_seconds:
            deduped.append(onset)
        elif onset < deduped[-1]:  # pragma: no cover - sorted input makes this defensive only.
            deduped[-1] = onset
    return deduped


def _reference_shape_seed(instrument: str, reference_source_id: str) -> int:
    digest = hashlib.sha256(f"{instrument}:{reference_source_id}".encode("utf-8")).digest()
    return int.from_bytes(digest[:4], byteorder="big", signed=False)


def _fallback_shape_frequency(instrument: str) -> float:
    if instrument == "begena":
        return 72.0
    if instrument == "washint":
        return 659.25
    return 220.0


def _sanitize_reference_f0(instrument: str, value: Optional[float]) -> Optional[float]:
    if value is None:
        return None
    candidate = _safe_float(value, default=float("nan"))
    if not math.isfinite(candidate) or candidate <= 0.0:
        return None

    low_hz, high_hz = REFERENCE_SHAPE_F0_RANGES_HZ.get(instrument, (40.0, 1200.0))
    # Preserve register/pitch-class evidence where possible by folding octave errors
    # before final clipping.  This keeps low Krar/Begena probes low instead of
    # forcing every out-of-range estimate to the nearest boundary.
    while candidate > high_hz and candidate * 0.5 >= low_hz:
        candidate *= 0.5
    while candidate < low_hz and candidate * 2.0 <= high_hz:
        candidate *= 2.0
    return _safe_float(np.clip(candidate, low_hz, high_hz))


def _estimate_reference_f0_track(
    audio: np.ndarray,
    sample_rate: int,
    instrument: str,
    *,
    n_fft: int,
    hop_length: int,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, List[str]]:
    warnings: List[str] = []
    y = _as_mono_float(audio)
    if y.size < max(64, int(0.050 * sample_rate)) or float(np.max(np.abs(y))) <= 1e-8:
        warnings.append("reference audio too short or too quiet for reliable f0 extraction")
        return np.zeros(0, dtype=np.float64), np.zeros(0, dtype=np.float64), np.zeros(0, dtype=bool), warnings

    fmin, fmax = REFERENCE_SHAPE_ANALYSIS_F0_RANGES_HZ.get(instrument, (35.0, min(1600.0, sample_rate / 2.0 - 1.0)))
    fmax = min(float(fmax), sample_rate / 2.0 - 1.0)
    fmin = max(20.0, float(fmin))
    if fmax <= fmin:
        warnings.append("reference f0 extraction skipped because fmax <= fmin for this sample rate")
        return np.zeros(0, dtype=np.float64), np.zeros(0, dtype=np.float64), np.zeros(0, dtype=bool), warnings

    try:
        minimum_frame_for_fmin = int(math.ceil(2.2 * sample_rate / fmin))
        frame_length = min(max(256, n_fft, minimum_frame_for_fmin), max(256, y.size))
        if frame_length < minimum_frame_for_fmin:
            warnings.append("reference f0 extraction skipped because the reference is shorter than the minimum f0 frame")
            return np.zeros(0, dtype=np.float64), np.zeros(0, dtype=np.float64), np.zeros(0, dtype=bool), warnings

        f0 = librosa.yin(
            y,
            fmin=fmin,
            fmax=fmax,
            sr=sample_rate,
            frame_length=frame_length,
            hop_length=hop_length,
        )
        f0_values = np.asarray(f0, dtype=np.float64)
        frame_times = librosa.frames_to_time(np.arange(f0_values.size), sr=sample_rate, hop_length=hop_length)

        rms = librosa.feature.rms(y=y, frame_length=frame_length, hop_length=hop_length)[0]
        usable = min(f0_values.size, rms.size, frame_times.size)
        f0_values = f0_values[:usable]
        frame_times = np.asarray(frame_times[:usable], dtype=np.float64)
        rms = np.asarray(rms[:usable], dtype=np.float64)
        rms_peak = float(np.max(rms)) if rms.size else 0.0
        active_mask = rms >= max(1e-10, rms_peak * 0.08)
        finite_mask = np.isfinite(f0_values) & (f0_values >= fmin) & (f0_values <= fmax) & active_mask
        if not np.any(finite_mask):
            warnings.append("reference f0 extraction produced no active finite f0 frames")
        return frame_times, f0_values, finite_mask, warnings
    except Exception as exc:  # pragma: no cover - fail-open for unusual local audio.
        warnings.append(f"reference f0 extraction failed: {exc}")
        return np.zeros(0, dtype=np.float64), np.zeros(0, dtype=np.float64), np.zeros(0, dtype=bool), warnings


def extract_reference_schedule(
    audio: np.ndarray | Sequence[float],
    sample_rate: int,
    *,
    instrument: str,
    source_id: str = "reference",
) -> Dict[str, Any]:
    """Extract bounded reference performance-shape metadata from local audio.

    This is diagnostic metadata used to make generated-vs-reference probes fairer:
    it captures the reference duration, onset grid, and coarse f0 contour without
    asserting that the estimates are musicologically authoritative.
    """

    if instrument not in INSTRUMENTS:
        raise ValueError(f"Unsupported reference schedule instrument: {instrument}")

    y = _as_mono_float(audio)
    duration_seconds = _safe_float(y.size / sample_rate) if sample_rate > 0 else 0.0
    generation_duration_seconds = min(duration_seconds, REFERENCE_SHAPE_MAX_DURATION_SECONDS)
    analysis_samples = int(round(generation_duration_seconds * sample_rate)) if sample_rate > 0 else 0
    work = y[:analysis_samples] if analysis_samples > 0 else y
    if work.size == 0:
        work = np.zeros(1, dtype=np.float64)

    warnings: List[str] = []
    if duration_seconds > REFERENCE_SHAPE_MAX_DURATION_SECONDS:
        warnings.append(
            f"reference duration {duration_seconds:.3f}s exceeds the {REFERENCE_SHAPE_MAX_DURATION_SECONDS:.1f}s diagnostic cap; schedule generation is truncated"
        )

    n_fft, hop_length = _analysis_fft_params(work.size)
    onset_times: List[float] = []
    try:
        onset_env = librosa.onset.onset_strength(y=work, sr=sample_rate, hop_length=hop_length)
        detected = librosa.onset.onset_detect(
            onset_envelope=onset_env,
            sr=sample_rate,
            hop_length=hop_length,
            units="time",
        )
        onset_times.extend(float(value) for value in detected if 0.0 <= float(value) < generation_duration_seconds)
    except Exception as exc:  # pragma: no cover - defensive fallback for uncommon codecs.
        warnings.append(f"reference onset extraction failed: {exc}")

    active_metrics = _sustain_decay_metrics(work, sample_rate)
    active_start = _safe_float(active_metrics.get("active_start_seconds"), 0.0)
    active_end = _safe_float(active_metrics.get("active_end_seconds"), 0.0)
    if active_end > active_start and active_start < generation_duration_seconds:
        onset_times.append(max(0.0, active_start))
    if duration_seconds > 0.0:
        onset_times.append(0.0)

    onsets = _deduplicate_onsets(onset_times, min_gap_seconds=REFERENCE_SHAPE_MIN_ONSET_GAP_SECONDS)
    onsets = [onset for onset in onsets if onset < generation_duration_seconds]
    if not onsets and generation_duration_seconds > 0.0:
        onsets = [0.0]
        warnings.append("reference onset extraction produced no onsets; using a single onset at 0.0s")

    if len(onsets) > REFERENCE_SHAPE_MAX_METADATA_ONSETS:
        warnings.append(
            f"reference onset metadata truncated from {len(onsets)} to {REFERENCE_SHAPE_MAX_METADATA_ONSETS} entries"
        )
    if len(onsets) > REFERENCE_SHAPE_MAX_GENERATION_EVENTS:
        warnings.append(
            f"reference generation events truncated from {len(onsets)} to {REFERENCE_SHAPE_MAX_GENERATION_EVENTS} entries"
        )

    frame_times, f0_values, finite_f0_mask, f0_warnings = _estimate_reference_f0_track(
        work,
        sample_rate,
        instrument,
        n_fft=n_fft,
        hop_length=hop_length,
    )
    warnings.extend(f0_warnings)
    finite_f0 = f0_values[finite_f0_mask] if f0_values.size and finite_f0_mask.size else np.zeros(0, dtype=np.float64)
    global_f0_median: Optional[float] = _safe_float(np.median(finite_f0)) if finite_f0.size else None
    if finite_f0.size == 0:
        warnings.append("reference f0 metadata is diagnostic-only and unavailable for this file")

    generation_onsets = onsets[:REFERENCE_SHAPE_MAX_GENERATION_EVENTS]
    events: List[Dict[str, Any]] = []
    for index, onset in enumerate(generation_onsets):
        end = generation_onsets[index + 1] if index + 1 < len(generation_onsets) else generation_duration_seconds
        end = max(float(onset), float(end))
        segment_mask = np.zeros(0, dtype=bool)
        if frame_times.size and f0_values.size and finite_f0_mask.size:
            segment_mask = (frame_times >= onset) & (frame_times < max(end, onset + 0.040)) & finite_f0_mask
        segment_values = f0_values[segment_mask] if segment_mask.size else np.zeros(0, dtype=np.float64)
        segment_f0_median: Optional[float] = _safe_float(np.median(segment_values)) if segment_values.size else global_f0_median
        events.append(
            {
                "index": index,
                "onset_seconds": _safe_float(onset),
                "end_seconds": _safe_float(end),
                "duration_seconds": _safe_float(max(0.0, end - onset)),
                "f0_median_hz": segment_f0_median,
                "f0_source": "segment_yin" if segment_values.size else ("global_yin_fallback" if global_f0_median is not None else "unavailable"),
                "f0_frame_count": int(segment_values.size),
            }
        )

    return _clean_for_json(
        {
            "diagnostic_only": True,
            "instrument": instrument,
            "source_id": source_id,
            "duration_seconds": _safe_float(duration_seconds),
            "generation_duration_seconds": _safe_float(generation_duration_seconds),
            "onset_times_seconds": [_safe_float(value) for value in onsets[:REFERENCE_SHAPE_MAX_METADATA_ONSETS]],
            "onset_count": int(len(onsets)),
            "onset_metadata_count": int(min(len(onsets), REFERENCE_SHAPE_MAX_METADATA_ONSETS)),
            "onset_generation_count": int(len(generation_onsets)),
            "onset_density": _safe_float(len(onsets) / max(generation_duration_seconds, 1e-9)),
            "onsets_truncated_for_metadata": bool(len(onsets) > REFERENCE_SHAPE_MAX_METADATA_ONSETS),
            "generation_events_truncated": bool(len(onsets) > REFERENCE_SHAPE_MAX_GENERATION_EVENTS),
            "f0_median_hz": global_f0_median,
            "f0_percentiles_hz": _safe_percentiles(finite_f0),
            "f0_voiced_frame_count": int(finite_f0.size),
            "band_energy_ratios": _band_energy_ratios(work, sample_rate),
            "segment_f0_medians_hz": [event["f0_median_hz"] for event in events[:REFERENCE_SHAPE_MAX_METADATA_ONSETS]],
            "events": events[:REFERENCE_SHAPE_MAX_METADATA_ONSETS],
            "generation_events": events,
            "warnings": warnings,
        }
    )


def _bounded_reference_event_duration(
    instrument: str,
    onset_seconds: float,
    next_onset_seconds: Optional[float],
    total_duration_seconds: float,
    *,
    mp3_source_truth: bool = False,
) -> float:
    remaining = max(0.0, total_duration_seconds - onset_seconds)
    if remaining <= 0.0:
        return 0.0

    if next_onset_seconds is None:
        gap = remaining
    else:
        gap = max(0.0, next_onset_seconds - onset_seconds)
    if gap <= 1e-6:
        gap = remaining

    # Reference-shaped probes should preserve the instrument's natural sustain
    # instead of chopping each event to a fraction of the onset gap.  Plucked
    # instruments are allowed to decay into following onsets.  Bowed Masenqo is
    # explicitly monophonic: sustain is kept inside the current gesture with a
    # short fade to the next onset, not by additively layering a long tail under
    # the following note (which sounds like two players/instruments).
    bounds = {
        "krar": (0.090, 1.70, 0.38),
        "masenqo": (0.120, 1.90, 0.16),
        "washint": (0.100, 1.55, 0.12),
        "begena": (0.220, 3.80, 0.95),
    }
    if mp3_source_truth and instrument in REFERENCE_SHAPE_MP3_DURATION_BOUNDS:
        bounds = dict(bounds)
        bounds[instrument] = REFERENCE_SHAPE_MP3_DURATION_BOUNDS[instrument]
    min_seconds, max_seconds, tail_seconds = bounds.get(instrument, (0.100, 1.40, 0.18))
    if next_onset_seconds is None:
        desired = max(min_seconds, min(max_seconds, remaining))
    elif instrument == "masenqo":
        desired = min(max_seconds, gap)
    else:
        desired = max(min_seconds, min(max_seconds, gap + tail_seconds))
    return _safe_float(min(remaining, desired))


def _reference_schedule_overlap_diagnostics(
    notes: Sequence[Mapping[str, Any]],
    *,
    substantial_threshold_seconds: float = 0.010,
) -> Dict[str, Any]:
    overlaps: List[float] = []
    for note in notes:
        next_onset = note.get("next_onset_seconds")
        if next_onset is None:
            continue
        overlap = max(
            0.0,
            _safe_float(note.get("onset_seconds"), 0.0)
            + _safe_float(note.get("duration_seconds"), 0.0)
            - _safe_float(next_onset, 0.0),
        )
        overlaps.append(overlap)

    positive = [value for value in overlaps if value > 1e-6]
    substantial = [value for value in overlaps if value > substantial_threshold_seconds]
    return {
        "scheduled_overlap_count": len(positive),
        "substantial_overlap_count": len(substantial),
        "max_scheduled_overlap_seconds": _safe_float(max(overlaps) if overlaps else 0.0),
        "substantial_overlap_threshold_seconds": _safe_float(substantial_threshold_seconds),
    }


def _reference_shape_release_tail_seconds(
    instrument: str,
    note_duration_seconds: float,
    *,
    mp3_source_truth: bool = False,
) -> float:
    tail_bounds = REFERENCE_SHAPE_FADE_OUT_SECONDS
    if mp3_source_truth and instrument in REFERENCE_SHAPE_MP3_FADE_OUT_SECONDS:
        tail_bounds = {**REFERENCE_SHAPE_FADE_OUT_SECONDS, **REFERENCE_SHAPE_MP3_FADE_OUT_SECONDS}
    minimum, maximum = tail_bounds.get(instrument, (0.060, 0.140))
    note_duration = max(0.0, float(note_duration_seconds))
    if note_duration <= 0.0:
        return 0.0
    return _safe_float(min(maximum, max(minimum, note_duration * 0.22), note_duration * 0.60))


def _apply_reference_note_smoothing(
    note_audio: np.ndarray | Sequence[float],
    sample_rate: int,
    *,
    instrument: str,
    mp3_source_truth: bool = False,
) -> Tuple[np.ndarray, Dict[str, Any]]:
    """Apply short equal-power/cosine ramps to one rendered reference note."""

    y = _as_mono_float(note_audio).copy()
    if y.size == 0:
        return y, {
            "click_smoothing": True,
            "fade_in_seconds": 0.0,
            "release_tail_seconds": 0.0,
            "headroom_gain": REFERENCE_SHAPE_NOTE_HEADROOM_GAIN.get(instrument, 0.72),
        }

    fade_in_seconds = REFERENCE_SHAPE_FADE_IN_SECONDS.get(instrument, 0.005)
    release_tail_seconds = _reference_shape_release_tail_seconds(
        instrument,
        y.size / sample_rate,
        mp3_source_truth=mp3_source_truth,
    )
    fade_in_samples = min(y.size, max(1, int(round(fade_in_seconds * sample_rate))))
    fade_out_samples = min(y.size, max(1, int(round(release_tail_seconds * sample_rate))))

    if fade_in_samples > 1:
        phase = np.linspace(0.0, math.pi / 2.0, fade_in_samples, dtype=np.float64)
        y[:fade_in_samples] *= np.sin(phase)
    else:
        y[0] = 0.0

    if fade_out_samples > 1:
        phase = np.linspace(0.0, math.pi / 2.0, fade_out_samples, dtype=np.float64)
        y[-fade_out_samples:] *= np.cos(phase)
    else:
        y[-1] = 0.0

    headroom_gain = REFERENCE_SHAPE_NOTE_HEADROOM_GAIN.get(instrument, 0.72)
    max_note_peak = REFERENCE_SHAPE_MAX_NOTE_PEAK.get(instrument, 0.82)
    y *= headroom_gain
    peak = float(np.max(np.abs(y))) if y.size else 0.0
    if peak > max_note_peak:
        y = y / peak * max_note_peak

    return y, {
        "click_smoothing": True,
        "fade_in_seconds": _safe_float(fade_in_samples / sample_rate),
        "release_tail_seconds": _safe_float(fade_out_samples / sample_rate),
        "headroom_gain": _safe_float(headroom_gain),
        "max_note_peak": _safe_float(max_note_peak),
        "window": "equal_power_sine_in_cosine_out",
    }


def _reference_shaped_note_schedule(
    instrument: str,
    reference_schedule: Mapping[str, Any],
    *,
    mp3_source_truth: bool = False,
) -> List[Dict[str, Any]]:
    raw_events = list(reference_schedule.get("generation_events") or [])
    if not raw_events:
        raw_events = [
            {
                "index": 0,
                "onset_seconds": 0.0,
                "end_seconds": reference_schedule.get("generation_duration_seconds", reference_schedule.get("duration_seconds", 0.0)),
                "duration_seconds": reference_schedule.get("generation_duration_seconds", reference_schedule.get("duration_seconds", 0.0)),
                "f0_median_hz": reference_schedule.get("f0_median_hz"),
                "f0_source": "global_yin_fallback" if reference_schedule.get("f0_median_hz") is not None else "unavailable",
                "f0_frame_count": int(reference_schedule.get("f0_voiced_frame_count", 0) or 0),
            }
        ]

    total_duration = _safe_float(reference_schedule.get("generation_duration_seconds", reference_schedule.get("duration_seconds", 0.0)))
    default_frequency = _fallback_shape_frequency(instrument)
    previous_frequency = default_frequency
    notes: List[Dict[str, Any]] = []
    for index, event in enumerate(raw_events[:REFERENCE_SHAPE_MAX_GENERATION_EVENTS]):
        onset = _safe_float(event.get("onset_seconds"), 0.0)
        if onset >= total_duration:
            continue
        next_onset = None
        if index + 1 < len(raw_events):
            next_onset = _safe_float(raw_events[index + 1].get("onset_seconds"), total_duration)
        raw_f0 = event.get("f0_median_hz")
        sanitized_f0 = _sanitize_reference_f0(instrument, raw_f0 if raw_f0 is not None else None)
        if sanitized_f0 is None:
            sanitized_f0 = previous_frequency
        previous_frequency = sanitized_f0
        note_duration = _bounded_reference_event_duration(
            instrument,
            onset,
            next_onset,
            total_duration,
            mp3_source_truth=mp3_source_truth,
        )
        if note_duration <= 0.0:
            continue
        release_tail_seconds = _reference_shape_release_tail_seconds(
            instrument,
            note_duration,
            mp3_source_truth=mp3_source_truth,
        )
        notes.append(
            {
                "index": len(notes),
                "reference_event_index": int(event.get("index", index)),
                "onset_seconds": _safe_float(onset),
                "duration_seconds": _safe_float(note_duration),
                "next_onset_seconds": _safe_float(next_onset) if next_onset is not None else None,
                "nominal_gap_seconds": _safe_float(max(0.0, (next_onset if next_onset is not None else total_duration) - onset)),
                "composition_release_tail_seconds": release_tail_seconds,
                "overlaps_next_onset": bool(next_onset is not None and onset + note_duration > next_onset),
                "click_smoothing": True,
                "frequency_hz": _safe_float(sanitized_f0),
                "reference_f0_median_hz": raw_f0,
                "reference_f0_source": event.get("f0_source", "unavailable"),
                "reference_f0_frame_count": int(event.get("f0_frame_count", 0) or 0),
                "render_action": "pending",
            }
        )
    return notes


def _source_id_is_second_user_reference(reference_source_id: str) -> bool:
    # Source-id ordering is not a general audio classifier.  It is kept here as
    # a contained diagnostic fallback for the current Task 129 MP3 set where the
    # second Krar user reference is the amplified/mixed recording.
    return str(reference_source_id).strip().lower().endswith("_user_ref_2")


def _schedule_band_ratio(reference_schedule: Mapping[str, Any], band_name: str) -> float:
    ratios = reference_schedule.get("band_energy_ratios") or {}
    if isinstance(ratios, Mapping):
        return _safe_float(ratios.get(band_name), 0.0)
    return 0.0


def _reference_f0_median(reference_schedule: Mapping[str, Any]) -> Optional[float]:
    direct = reference_schedule.get("f0_median_hz")
    if direct is not None:
        candidate = _safe_float(direct, default=float("nan"))
        if math.isfinite(candidate) and candidate > 0.0:
            return candidate
    percentiles = reference_schedule.get("f0_percentiles_hz") or {}
    if isinstance(percentiles, Mapping):
        candidate = _safe_float(percentiles.get("p50"), default=float("nan"))
        if math.isfinite(candidate) and candidate > 0.0:
            return candidate
    return None


def _krar_focus_metadata(reference_schedule: Mapping[str, Any], reference_source_id: str) -> Dict[str, Any]:
    onset_density = _safe_float(reference_schedule.get("onset_density"), 0.0)
    onset_generation_count = int(reference_schedule.get("onset_generation_count", 0) or 0)
    f0_median = _reference_f0_median(reference_schedule)
    low_ratio = _schedule_band_ratio(reference_schedule, "low")
    low_mid_ratio = _schedule_band_ratio(reference_schedule, "low_mid")
    strong_low_band = low_ratio + low_mid_ratio >= KRAR_FOCUS_STRONG_LOW_BAND_RATIO
    dense_events = onset_density >= KRAR_FOCUS_DENSE_ONSET_THRESHOLD or onset_generation_count >= 18
    low_f0 = f0_median is not None and f0_median <= KRAR_FOCUS_LOW_F0_MEDIAN_HZ
    source_order_fallback = _source_id_is_second_user_reference(reference_source_id)
    enabled = bool((dense_events and low_f0 and strong_low_band) or source_order_fallback)
    reasons: List[str] = []
    if dense_events and low_f0 and strong_low_band:
        reasons.append("dense_low_f0_strong_low_band")
    if source_order_fallback:
        reasons.append("source_id_second_user_ref_task129_diagnostic_fallback")
    return {
        "instrument_focus": enabled,
        "instrument_focus_reasons": reasons,
        "instrument_focus_heuristics": {
            "onset_density": _safe_float(onset_density),
            "onset_generation_count": onset_generation_count,
            "f0_median_hz": _safe_float(f0_median) if f0_median is not None else None,
            "low_band_ratio": _safe_float(low_ratio),
            "low_mid_band_ratio": _safe_float(low_mid_ratio),
            "low_plus_low_mid_band_ratio": _safe_float(low_ratio + low_mid_ratio),
            "dense_events": bool(dense_events),
            "low_f0_median": bool(low_f0),
            "strong_low_band": bool(strong_low_band),
            "source_id_second_user_ref_fallback": bool(source_order_fallback),
        },
        "instrument_focus_skipped_events": 0,
        "instrument_focus_attenuated_events": 0,
        "instrument_focus_rendered_events": 0,
    }


def _krar_focus_action(note: Mapping[str, Any]) -> Tuple[str, float, str]:
    frequency_hz = _safe_float(note.get("frequency_hz"), 0.0)
    duration_seconds = _safe_float(note.get("duration_seconds"), 0.0)
    nominal_gap = _safe_float(note.get("nominal_gap_seconds"), duration_seconds)
    sustained = duration_seconds >= KRAR_FOCUS_SUSTAINED_SECONDS or nominal_gap >= KRAR_FOCUS_SUSTAINED_SECONDS
    if sustained and frequency_hz < KRAR_FOCUS_SKIP_F0_HZ:
        return "skipped_low_drone_like_event", 0.0, "sustained_event_below_krar_focus_skip_f0"
    if sustained and frequency_hz < KRAR_FOCUS_ATTENUATE_F0_HZ:
        return "attenuated_low_drone_like_event", KRAR_FOCUS_ATTENUATED_GAIN, "sustained_event_below_krar_focus_attenuate_f0"
    if frequency_hz < KRAR_FOCUS_SKIP_F0_HZ:
        return "attenuated_low_short_event", 0.50, "short_event_below_krar_focus_skip_f0"
    return "rendered", 1.0, "within_krar_focus_band"


def _mp3_profile_for_instrument(instrument: str, *, krar_instrument_focus: bool = False) -> str:
    if instrument == "begena":
        return "mp3_reference_bright"
    if instrument == "masenqo":
        return "mp3_reference_bow"
    if instrument == "krar" and krar_instrument_focus:
        return "azmari_bright"
    if instrument == "krar":
        return "traditional_warm"
    if instrument == "washint":
        return "alto_breathy"
    return "default"


def generate_reference_shaped_probe_audio(
    instrument: str,
    reference_schedule: Mapping[str, Any],
    *,
    reference_source_id: str,
    sample_rate: int = SAMPLE_RATE,
    mp3_source_truth: bool = False,
) -> Tuple[np.ndarray, Dict[str, Any]]:
    """Render one isolated source probe following a local reference schedule."""

    if instrument not in INSTRUMENTS:
        raise ValueError(f"Unsupported generated probe instrument: {instrument}")

    duration_seconds = _safe_float(reference_schedule.get("generation_duration_seconds", reference_schedule.get("duration_seconds", 0.0)))
    total_samples = max(1, int(round(max(0.0, duration_seconds) * sample_rate)))
    output = np.zeros(total_samples, dtype=np.float64)
    notes = _reference_shaped_note_schedule(
        instrument,
        reference_schedule,
        mp3_source_truth=mp3_source_truth,
    )
    krar_focus = _krar_focus_metadata(reference_schedule, reference_source_id) if instrument == "krar" and mp3_source_truth else {
        "instrument_focus": False,
        "instrument_focus_reasons": [],
        "instrument_focus_heuristics": {},
        "instrument_focus_skipped_events": 0,
        "instrument_focus_attenuated_events": 0,
        "instrument_focus_rendered_events": 0,
    }
    profiles_used: List[str] = []
    string_qualities_used: List[str] = []
    sustain_bias_values: List[float] = []

    state = np.random.get_state()
    np.random.seed(_reference_shape_seed(instrument, reference_source_id))
    try:
        for note in notes:
            onset_sample = int(round(float(note["onset_seconds"]) * sample_rate))
            if onset_sample >= total_samples:
                continue
            frequency_hz = float(note["frequency_hz"])
            note_duration = float(note["duration_seconds"])
            event_index = int(note["index"])
            if instrument == "krar":
                krar_profile = _mp3_profile_for_instrument(
                    instrument,
                    krar_instrument_focus=bool(krar_focus.get("instrument_focus")),
                ) if mp3_source_truth else "traditional_warm"
                note_gain = 1.0
                if krar_focus.get("instrument_focus"):
                    action, note_gain, reason = _krar_focus_action(note)
                    note["render_action"] = action
                    note["instrument_focus_gain"] = _safe_float(note_gain)
                    note["instrument_focus_reason"] = reason
                    if action.startswith("skipped"):
                        krar_focus["instrument_focus_skipped_events"] = int(krar_focus["instrument_focus_skipped_events"]) + 1
                        continue
                    if action.startswith("attenuated"):
                        krar_focus["instrument_focus_attenuated_events"] = int(krar_focus["instrument_focus_attenuated_events"]) + 1
                else:
                    note["render_action"] = "rendered"
                    note["instrument_focus_gain"] = 1.0
                krar_focus["instrument_focus_rendered_events"] = int(krar_focus["instrument_focus_rendered_events"]) + 1
                note["generator_profile"] = krar_profile
                if krar_profile not in profiles_used:
                    profiles_used.append(krar_profile)
                note_audio = generate_krar_tone(
                    frequency_hz,
                    duration=note_duration,
                    velocity=0.78 * float(note.get("instrument_focus_gain", 1.0)),
                    sample_rate=sample_rate,
                    profile=krar_profile,
                )
            elif instrument == "masenqo":
                masenqo_profile = _mp3_profile_for_instrument(instrument) if mp3_source_truth else "vocal_clean"
                note["generator_profile"] = masenqo_profile
                note["render_action"] = "rendered"
                if masenqo_profile not in profiles_used:
                    profiles_used.append(masenqo_profile)
                note_audio = generate_masenqo_tone(
                    frequency_hz,
                    duration=note_duration,
                    velocity=0.76,
                    sample_rate=sample_rate,
                    expressiveness=0.86 if mp3_source_truth else 0.78,
                    add_ornament=(event_index % 5 == 0 and note_duration >= 0.18),
                    profile=masenqo_profile,
                )
            elif instrument == "washint":
                washint_profile = "alto_breathy"
                note["generator_profile"] = washint_profile
                note["render_action"] = "rendered"
                if washint_profile not in profiles_used:
                    profiles_used.append(washint_profile)
                note_audio = generate_washint_tone(
                    frequency_hz,
                    duration=note_duration,
                    velocity=0.74,
                    sample_rate=sample_rate,
                    add_ornament=(event_index % 6 == 0 and note_duration >= 0.16),
                    profile=washint_profile,
                )
            elif instrument == "begena":
                begena_profile = _mp3_profile_for_instrument(instrument) if mp3_source_truth else "paraliturgical_drone"
                if mp3_source_truth:
                    string_quality = ("lively", "stable", "worn", "lively")[event_index % 4]
                    sustain_bias = float(np.clip(0.50 + 0.035 * (event_index % 4), 0.48, 0.64))
                    buzzer_position = float(np.clip(0.27 + 0.026 * ((event_index % 5) - 2), 0.20, 0.39))
                    velocity = 0.70
                else:
                    string_quality = ("stable", "worn", "lively")[event_index % 3]
                    sustain_bias = float(np.clip(0.70 + 0.04 * (event_index % 4), 0.64, 0.88))
                    buzzer_position = float(np.clip(0.32 + 0.035 * ((event_index % 5) - 2), 0.22, 0.48))
                    velocity = 0.74
                note["generator_profile"] = begena_profile
                note["string_quality"] = string_quality
                note["sustain_bias"] = _safe_float(sustain_bias)
                note["buzzer_position"] = _safe_float(buzzer_position)
                note["render_action"] = "rendered"
                if begena_profile not in profiles_used:
                    profiles_used.append(begena_profile)
                if string_quality not in string_qualities_used:
                    string_qualities_used.append(string_quality)
                sustain_bias_values.append(sustain_bias)
                note_audio = generate_begena_tone(
                    frequency_hz,
                    duration=note_duration,
                    velocity=velocity,
                    sample_rate=sample_rate,
                    profile=begena_profile,
                    buzzers_enabled=True,
                    buzzer_position=buzzer_position,
                    string_quality=string_quality,
                    sustain_bias=sustain_bias,
                )
            else:  # pragma: no cover - guarded above.
                raise ValueError(instrument)

            smoothed_note, smoothing_metadata = _apply_reference_note_smoothing(
                note_audio,
                sample_rate,
                instrument=instrument,
                mp3_source_truth=mp3_source_truth,
            )
            note.update(smoothing_metadata)
            note["composition_release_tail_seconds"] = smoothing_metadata["release_tail_seconds"]
            end_sample = min(total_samples, onset_sample + len(note_audio))
            if end_sample > onset_sample:
                output[onset_sample:end_sample] += smoothed_note[: end_sample - onset_sample]
    finally:
        np.random.set_state(state)

    peak = float(np.max(np.abs(output))) if output.size else 0.0
    normalized_final_output = False
    if peak > 0.98:
        output = output / peak * 0.98
        normalized_final_output = True

    rendered_notes = [note for note in notes if not str(note.get("render_action", "")).startswith("skipped")]
    f0_values = [float(note["frequency_hz"]) for note in rendered_notes]
    release_tail_values = [float(note.get("composition_release_tail_seconds", 0.0)) for note in rendered_notes]
    click_diagnostics = adjacent_sample_jump_diagnostics(output)
    overlap_diagnostics = _reference_schedule_overlap_diagnostics(notes)
    monophonic_source = instrument == "masenqo"
    overlap_policy = "monophonic_fade_to_next_onset" if monophonic_source else "sustain_tail_overlap"
    metadata: Dict[str, Any] = {
        "instrument": instrument,
        "sample_rate": sample_rate,
        "source": "current multimodal_gen.assets_gen generator",
        "probe_shape": "reference_performance_shape",
        "reference_source_id": reference_source_id,
        "full_song_generation": False,
        "diagnostic_only": True,
        "click_smoothing": True,
        "monophonic_source": bool(monophonic_source),
        "overlap_policy": overlap_policy,
        **overlap_diagnostics,
        "composition_release_tail_seconds": _safe_float(max(release_tail_values) if release_tail_values else 0.0),
        "mp3_source_truth": bool(mp3_source_truth),
        "generator_profiles_used": profiles_used,
        "mp3_profile_routing": {
            "enabled": bool(mp3_source_truth),
            "instrument_profile": profiles_used[0] if len(profiles_used) == 1 else profiles_used,
            "begena_string_qualities_used": string_qualities_used,
            "begena_sustain_bias_range": [
                _safe_float(min(sustain_bias_values)) if sustain_bias_values else None,
                _safe_float(max(sustain_bias_values)) if sustain_bias_values else None,
            ],
        },
        "instrument_focus": bool(krar_focus.get("instrument_focus")),
        "instrument_focus_reasons": krar_focus.get("instrument_focus_reasons", []),
        "instrument_focus_heuristics": krar_focus.get("instrument_focus_heuristics", {}),
        "instrument_focus_skipped_events": int(krar_focus.get("instrument_focus_skipped_events", 0) or 0),
        "instrument_focus_attenuated_events": int(krar_focus.get("instrument_focus_attenuated_events", 0) or 0),
        "instrument_focus_rendered_events": int(krar_focus.get("instrument_focus_rendered_events", len(rendered_notes)) or 0),
        "headroom_gain_per_note": _safe_float(REFERENCE_SHAPE_NOTE_HEADROOM_GAIN.get(instrument, 0.72)),
        "normalized_final_output": normalized_final_output,
        "pre_normalization_peak": _safe_float(peak),
        "click_diagnostics": click_diagnostics,
        "source_notes": [
            f"Reference-performance-shaped isolated source probe for {instrument}; no full-song generation is used.",
            "Reference onset/f0 metadata is diagnostic and bounded; it is used only to make probe comparisons less unfair than fixed single notes.",
            "Composition-level click smoothing and release tails are applied to avoid hard note-boundary cuts in the diagnostic probe.",
            "Masenqo reference-shaped probes are rendered as one bowed source with note ends constrained to the next onset, avoiding additive two-player overlap.",
        ],
        "warnings": list(reference_schedule.get("warnings", [])),
        "probe_schedule": {
            "shape": "reference_performance_shape",
            "duration_seconds": duration_seconds,
            "reference_source_id": reference_source_id,
            "click_smoothing": True,
            "monophonic_source": bool(monophonic_source),
            "overlap_policy": overlap_policy,
            **overlap_diagnostics,
            "composition_release_tail_seconds": _safe_float(max(release_tail_values) if release_tail_values else 0.0),
            "mp3_source_truth": bool(mp3_source_truth),
            "generator_profiles_used": profiles_used,
            "instrument_focus": bool(krar_focus.get("instrument_focus")),
            "instrument_focus_skipped_events": int(krar_focus.get("instrument_focus_skipped_events", 0) or 0),
            "instrument_focus_attenuated_events": int(krar_focus.get("instrument_focus_attenuated_events", 0) or 0),
            "instrument_focus_rendered_events": int(krar_focus.get("instrument_focus_rendered_events", len(rendered_notes)) or 0),
            "click_diagnostics": click_diagnostics,
            "onset_times_seconds": [float(note["onset_seconds"]) for note in notes],
            "frequencies_hz": f0_values,
            "all_reference_frequencies_hz": [float(note["frequency_hz"]) for note in notes],
            "frequency_range_hz": list(REFERENCE_SHAPE_F0_RANGES_HZ.get(instrument, (0.0, sample_rate / 2.0))),
            "notes": notes,
            "reference_schedule_summary": {
                "duration_seconds": reference_schedule.get("duration_seconds"),
                "generation_duration_seconds": reference_schedule.get("generation_duration_seconds"),
                "onset_count": reference_schedule.get("onset_count"),
                "onset_density": reference_schedule.get("onset_density"),
                "f0_median_hz": reference_schedule.get("f0_median_hz"),
                "f0_percentiles_hz": reference_schedule.get("f0_percentiles_hz"),
                "band_energy_ratios": reference_schedule.get("band_energy_ratios"),
                "diagnostic_only": True,
            },
        },
    }
    return _as_mono_float(output), _clean_for_json(metadata)


def _flatten_numeric(value: Any, prefix: str = "") -> Dict[str, float]:
    flattened: Dict[str, float] = {}
    if isinstance(value, Mapping):
        for key, nested in value.items():
            nested_prefix = f"{prefix}.{key}" if prefix else str(key)
            flattened.update(_flatten_numeric(nested, nested_prefix))
    elif isinstance(value, (list, tuple)):
        for index, nested in enumerate(value):
            nested_prefix = f"{prefix}.{index}" if prefix else str(index)
            flattened.update(_flatten_numeric(nested, nested_prefix))
    elif isinstance(value, (int, float, np.integer, np.floating)):
        numeric = float(value)
        if math.isfinite(numeric):
            flattened[prefix] = numeric
    return flattened


def compare_descriptors(generated: Mapping[str, Any], reference: Mapping[str, Any]) -> Dict[str, Any]:
    """Return diagnostic descriptor deltas between generated and reference audio."""

    generated_flat = _flatten_numeric(generated)
    reference_flat = _flatten_numeric(reference)
    shared_keys = sorted(set(generated_flat) & set(reference_flat))

    deltas: Dict[str, Dict[str, float]] = {}
    normalized_distances: List[float] = []
    for key in shared_keys:
        generated_value = generated_flat[key]
        reference_value = reference_flat[key]
        delta = generated_value - reference_value
        denom = abs(generated_value) + abs(reference_value) + 1e-12
        relative_delta = delta / max(abs(reference_value), 1e-12)
        normalized_delta = abs(delta) / denom
        normalized_distances.append(normalized_delta)
        deltas[key] = {
            "generated": _safe_float(generated_value),
            "reference": _safe_float(reference_value),
            "delta": _safe_float(delta),
            "relative_delta": _safe_float(relative_delta),
            "symmetric_normalized_abs_delta": _safe_float(normalized_delta),
        }

    return {
        "diagnostic_only": True,
        "descriptor_count": len(shared_keys),
        "descriptor_distance": _safe_float(np.mean(normalized_distances)) if normalized_distances else None,
        "descriptor_deltas": deltas,
    }


def _clean_for_json(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _clean_for_json(nested) for key, nested in value.items()}
    if isinstance(value, (list, tuple)):
        return [_clean_for_json(nested) for nested in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, np.ndarray):
        return _clean_for_json(value.tolist())
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        candidate = float(value)
        return candidate if math.isfinite(candidate) else None
    return value


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(_clean_for_json(payload), handle, indent=2, sort_keys=True)
        handle.write("\n")


def maybe_download_begena_reference(refs_dir: Path, *, download_public_refs: bool) -> Dict[str, Any]:
    manifest = PUBLIC_REFERENCE_MANIFEST["begena"]
    refs_dir.mkdir(parents=True, exist_ok=True)
    destination = refs_dir / str(manifest["filename"])
    status: Dict[str, Any] = {
        "instrument": "begena",
        "download_requested": bool(download_public_refs),
        "attempted": False,
        "status": "existing" if destination.exists() else "missing_download_not_requested",
        "path": str(destination),
        "page": manifest["page"],
        "direct_url": manifest["direct_url"],
        "license": manifest["license"],
        "attribution": manifest["attribution"],
    }

    if destination.exists() or not download_public_refs:
        return status

    status["attempted"] = True
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    try:
        request = urllib.request.Request(
            str(manifest["direct_url"]),
            headers={"User-Agent": "MUSE-Task129-ReferenceHarness/1.0"},
        )
        with urllib.request.urlopen(request, timeout=20) as response, temporary.open("wb") as handle:
            total = 0
            while True:
                chunk = response.read(1024 * 128)
                if not chunk:
                    break
                total += len(chunk)
                if total > 100 * 1024 * 1024:
                    raise RuntimeError("download exceeded 100 MB safety limit")
                handle.write(chunk)
        if temporary.stat().st_size <= 0:
            raise RuntimeError("download produced an empty file")
        temporary.replace(destination)
        status["status"] = "downloaded"
        status["bytes"] = destination.stat().st_size
    except (OSError, RuntimeError, urllib.error.URLError, urllib.error.HTTPError) as exc:
        try:
            if temporary.exists():
                temporary.unlink()
        except OSError:
            pass
        status["status"] = "skipped_unavailable"
        status["error"] = str(exc)
    return status


def build_reference_status(
    refs_dir: Path,
    instruments: Sequence[str],
    *,
    download_public_refs: bool = False,
    user_refs: Optional[Mapping[str, Sequence[Path | str]]] = None,
    match_user_ref_shape: bool = False,
    include_public_refs_with_user_refs: bool = False,
) -> Tuple[Dict[str, Any], List[ReferenceCandidate]]:
    selected = normalize_instruments(instruments)
    refs_dir = _resolve_path(refs_dir)
    refs_dir.mkdir(parents=True, exist_ok=True)
    user_refs = user_refs or {}

    status: Dict[str, Any] = {
        "schema_version": 1,
        "diagnostic_only": True,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "refs_dir": str(refs_dir),
        "download_public_refs": bool(download_public_refs),
        "match_user_ref_shape": bool(match_user_ref_shape),
        "include_public_refs_with_user_refs": bool(include_public_refs_with_user_refs),
        "user_mp3_references_are_source_truth": bool(
            match_user_ref_shape and any(user_refs.get(instrument) for instrument in selected)
        ),
        "user_reference_source_truth_instruments": [
            instrument for instrument in selected if match_user_ref_shape and bool(user_refs.get(instrument))
        ],
        "selected_instruments": list(selected),
        "public_reference_manifest": _clean_for_json(PUBLIC_REFERENCE_MANIFEST),
        "instruments": {},
    }
    candidates: List[ReferenceCandidate] = []

    begena_download_status: Optional[Dict[str, Any]] = None
    begena_has_user_refs = bool(user_refs.get("begena"))
    suppress_begena_public_for_user_truth = bool(
        "begena" in selected
        and match_user_ref_shape
        and begena_has_user_refs
        and not include_public_refs_with_user_refs
    )
    if "begena" in selected:
        begena_download_status = maybe_download_begena_reference(
            refs_dir,
            download_public_refs=download_public_refs and not suppress_begena_public_for_user_truth,
        )

    for instrument in selected:
        manifest = PUBLIC_REFERENCE_MANIFEST[instrument]
        entry: Dict[str, Any] = {
            "instrument": instrument,
            "manifest_status": manifest["status"],
            "manifest": _clean_for_json(manifest),
            "public_reference": None,
            "user_references": [],
            "user_refs_are_active_source_truth": bool(match_user_ref_shape and bool(user_refs.get(instrument))),
            "include_public_refs_with_user_refs": bool(include_public_refs_with_user_refs),
            "available_reference_count": 0,
            "effective_status": "unavailable_no_user_reference",
        }

        if instrument == "begena":
            assert begena_download_status is not None
            entry["public_reference"] = begena_download_status
            entry["public_reference_included"] = False
            if suppress_begena_public_for_user_truth:
                entry["public_reference_excluded_reason"] = (
                    "user references are the active source of truth for this --match-user-ref-shape run; "
                    "pass --include-public-refs-with-user-refs to include the Commons reference as an additional diagnostic comparator"
                )
            public_path = Path(str(begena_download_status["path"]))
            if public_path.exists() and not suppress_begena_public_for_user_truth:
                entry["public_reference_included"] = True
                candidates.append(
                    ReferenceCandidate(
                        instrument="begena",
                        source_id="begena_commons_BegenaScalePlucked",
                        path=public_path,
                        kind="public_commons",
                        metadata={
                            "page": manifest["page"],
                            "direct_url": manifest["direct_url"],
                            "license": manifest["license"],
                            "attribution": manifest["attribution"],
                        },
                    )
                )
            elif begena_download_status["status"] == "missing_download_not_requested":
                entry["effective_status"] = "public_available_not_local_download_not_requested"
            elif suppress_begena_public_for_user_truth:
                entry["effective_status"] = "user_reference_source_truth_public_reference_excluded"
            else:
                entry["effective_status"] = "public_available_but_local_unavailable"
        else:
            entry["public_reference"] = {
                "status": "unavailable_by_default",
                "source_urls": manifest.get("source_urls", []),
                "reason": manifest["reason"],
            }

        for index, raw_path in enumerate(user_refs.get(instrument, []), start=1):
            resolved = _resolve_path(raw_path)
            ref_entry = {
                "path": str(resolved),
                "exists": resolved.exists(),
                "source_id": f"{instrument}_user_ref_{index}",
                "kind": "user_supplied",
            }
            entry["user_references"].append(ref_entry)
            if resolved.exists():
                candidates.append(
                    ReferenceCandidate(
                        instrument=instrument,
                        source_id=f"{instrument}_user_ref_{index}",
                        path=resolved,
                        kind="user_supplied",
                        metadata={"provided_by": "--user-ref", "original_path": str(raw_path)},
                    )
                )

        available_count = sum(1 for candidate in candidates if candidate.instrument == instrument)
        entry["available_reference_count"] = available_count
        if available_count > 0:
            entry["effective_status"] = "available_local_reference"
        elif instrument != "begena":
            entry["effective_status"] = "unavailable_no_user_reference"

        status["instruments"][instrument] = entry

    return status, candidates


def _single_note_source_notes(instrument: str) -> List[str]:
    return [
        f"Single-note isolated source probe for {instrument}; this is not full-song generation.",
        "Descriptor comparison metadata records probe shape so duration/onset comparisons are interpreted with the correct scope.",
    ]


def _build_begena_reference_scale_schedule(spec: Mapping[str, Any]) -> List[Dict[str, Any]]:
    onsets = [float(value) for value in spec["onset_times_seconds"]]
    frequencies = [float(value) for value in spec["frequencies_hz"]]
    observed_f0 = list(spec.get("observed_f0_medians_hz", []))
    variations = [dict(value) for value in spec.get("note_variations", [])]
    low_hz, high_hz = (float(value) for value in spec.get("frequency_range_hz", BEGENA_LOW_FUNDAMENTAL_RANGE_HZ))

    if len(onsets) != len(frequencies):
        raise ValueError("Begena reference-scale onsets and frequencies must have the same length")
    if not variations:
        variations = [
            {
                "string_quality": spec.get("string_quality", "stable"),
                "buzzer_position": spec.get("buzzer_position", 0.35),
                "sustain_bias": spec.get("sustain_bias", 0.88),
                "velocity": spec.get("velocity", 0.76),
            }
        ]

    schedule: List[Dict[str, Any]] = []
    for index, (onset_seconds, frequency_hz) in enumerate(zip(onsets, frequencies)):
        variation = variations[index % len(variations)]
        schedule.append(
            {
                "index": index,
                "onset_seconds": _safe_float(onset_seconds),
                "frequency_hz": _safe_float(np.clip(frequency_hz, low_hz, high_hz)),
                "observed_f0_median_hz": observed_f0[index] if index < len(observed_f0) else None,
                "string_pair_index": index % 5,
                "string_layout_context": "10 strings / five pitch pairs",
                "string_quality": str(variation.get("string_quality", spec.get("string_quality", "stable"))),
                "buzzer_position": _safe_float(variation.get("buzzer_position", spec.get("buzzer_position", 0.35))),
                "sustain_bias": _safe_float(variation.get("sustain_bias", spec.get("sustain_bias", 0.88))),
                "velocity": _safe_float(variation.get("velocity", spec.get("velocity", 0.76))),
            }
        )
    return schedule


def _generate_begena_reference_scale_probe(spec: Mapping[str, Any], sample_rate: int) -> Tuple[np.ndarray, List[Dict[str, Any]]]:
    """Render the Commons-reference-shaped Begena scale as isolated source synthesis."""

    duration_seconds = float(spec["duration_seconds"])
    total_samples = max(1, int(round(duration_seconds * sample_rate)))
    output = np.zeros(total_samples, dtype=np.float64)
    schedule = _build_begena_reference_scale_schedule(spec)

    for index, note in enumerate(schedule):
        onset_seconds = float(note["onset_seconds"])
        onset_sample = int(round(onset_seconds * sample_rate))
        if onset_sample >= total_samples:
            continue

        next_onset = float(schedule[index + 1]["onset_seconds"]) if index + 1 < len(schedule) else duration_seconds
        inter_onset_seconds = max(0.0, next_onset - onset_seconds)
        remaining_seconds = max(0.0, duration_seconds - onset_seconds)
        desired_note_seconds = max(
            1.65,
            min(3.45, inter_onset_seconds + 1.35 + 0.45 * float(note["sustain_bias"])),
        )
        note_duration = min(remaining_seconds, desired_note_seconds)
        if note_duration <= 0:
            continue

        note_audio = generate_begena_tone(
            float(note["frequency_hz"]),
            duration=note_duration,
            velocity=float(note["velocity"]),
            sample_rate=sample_rate,
            profile=str(spec["profile"]),
            buzzers_enabled=bool(spec["buzzers_enabled"]),
            buzzer_position=float(note["buzzer_position"]),
            string_quality=str(note["string_quality"]),
            sustain_bias=float(note["sustain_bias"]),
        )
        end_sample = min(total_samples, onset_sample + len(note_audio))
        if end_sample > onset_sample:
            output[onset_sample:end_sample] += _as_mono_float(note_audio[: end_sample - onset_sample])

    peak = float(np.max(np.abs(output))) if output.size else 0.0
    if peak > 0.98:
        output = output / peak * 0.98
    return output, schedule


def generate_probe_audio(instrument: str, sample_rate: int = SAMPLE_RATE) -> Tuple[np.ndarray, Dict[str, Any]]:
    """Generate one isolated current-generator probe for an Ethiopian instrument."""

    if instrument not in GENERATED_PROBE_SPECS:
        raise ValueError(f"Unsupported generated probe instrument: {instrument}")

    spec = dict(GENERATED_PROBE_SPECS[instrument])
    probe_shape = str(spec.get("probe_shape", "single_note"))
    schedule: Optional[List[Dict[str, Any]]] = None
    state = np.random.get_state()
    np.random.seed(int(spec["seed"]))
    try:
        if instrument == "krar":
            audio = generate_krar_tone(
                float(spec["frequency_hz"]),
                duration=float(spec["duration_seconds"]),
                velocity=float(spec["velocity"]),
                sample_rate=sample_rate,
                profile=str(spec["profile"]),
            )
        elif instrument == "masenqo":
            audio = generate_masenqo_tone(
                float(spec["frequency_hz"]),
                duration=float(spec["duration_seconds"]),
                velocity=float(spec["velocity"]),
                sample_rate=sample_rate,
                expressiveness=float(spec["expressiveness"]),
                profile=str(spec["profile"]),
            )
        elif instrument == "washint":
            audio = generate_washint_tone(
                float(spec["frequency_hz"]),
                duration=float(spec["duration_seconds"]),
                velocity=float(spec["velocity"]),
                sample_rate=sample_rate,
                add_ornament=bool(spec["add_ornament"]),
                profile=str(spec["profile"]),
            )
        elif instrument == "begena":
            if probe_shape == "reference_scale_shape":
                audio, schedule = _generate_begena_reference_scale_probe(spec, sample_rate)
            else:
                audio = generate_begena_tone(
                    float(spec["frequency_hz"]),
                    duration=float(spec["duration_seconds"]),
                    velocity=float(spec["velocity"]),
                    sample_rate=sample_rate,
                    profile=str(spec["profile"]),
                    buzzers_enabled=bool(spec["buzzers_enabled"]),
                    buzzer_position=float(spec["buzzer_position"]),
                    string_quality=str(spec["string_quality"]),
                    sustain_bias=float(spec["sustain_bias"]),
                )
        else:  # pragma: no cover - guarded above.
            raise ValueError(instrument)
    finally:
        np.random.set_state(state)

    metadata = {
        "instrument": instrument,
        "sample_rate": sample_rate,
        "source": "current multimodal_gen.assets_gen generator",
        "probe_shape": probe_shape,
        "full_song_generation": False,
        "source_notes": list(spec.get("source_notes", _single_note_source_notes(instrument))),
        "warnings": list(spec.get("warnings", [])),
        "probe_spec": spec,
    }
    if schedule is not None:
        frequencies = [float(note["frequency_hz"]) for note in schedule]
        metadata["probe_schedule"] = {
            "shape": probe_shape,
            "duration_seconds": float(spec["duration_seconds"]),
            "onset_times_seconds": [float(note["onset_seconds"]) for note in schedule],
            "frequencies_hz": frequencies,
            "frequency_range_hz": [float(value) for value in spec.get("frequency_range_hz", BEGENA_LOW_FUNDAMENTAL_RANGE_HZ)],
            "notes": schedule,
            "observed_reference_preanalysis": {
                "duration_seconds_about": BEGENA_REFERENCE_SCALE_DURATION_SECONDS,
                "strong_onset_times_seconds": list(BEGENA_REFERENCE_SCALE_ONSETS_SECONDS),
                "observed_f0_medians_hz": list(BEGENA_REFERENCE_SCALE_OBSERVED_F0_MEDIANS_HZ),
                "sanitized_frequencies_hz": frequencies,
            },
            "source_truth_constraints": dict(spec.get("source_truth_constraints", {})),
        }
    return _as_mono_float(audio), metadata


def _safe_filename_token(value: str) -> str:
    token = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in str(value))
    token = token.strip("_")
    return token or "reference"


def write_generated_probe_wav(
    out_dir: Path,
    instrument: str,
    audio: np.ndarray,
    sample_rate: int,
    *,
    reference_source_id: Optional[str] = None,
) -> Path:
    generated_dir = out_dir / "generated_probes"
    generated_dir.mkdir(parents=True, exist_ok=True)
    if reference_source_id:
        path = generated_dir / f"{instrument}_{_safe_filename_token(reference_source_id)}_generated_probe.wav"
    else:
        path = generated_dir / f"{instrument}_generated_probe.wav"
    sf.write(path, _as_mono_float(audio), sample_rate)
    return path


def load_audio_file(path: Path) -> Tuple[np.ndarray, int]:
    try:
        data, sample_rate = sf.read(path, always_2d=False, dtype="float64")
        return _as_mono_float(data), int(sample_rate)
    except Exception:
        data, sample_rate = librosa.load(str(path), sr=None, mono=True)
        return _as_mono_float(data), int(sample_rate)


def build_summary_markdown(
    *,
    reference_status: Mapping[str, Any],
    descriptors: Mapping[str, Any],
    comparisons: Mapping[str, Any],
) -> str:
    lines: List[str] = []
    lines.append("# Task 129 Ethiopian Reference-Audio Comparison")
    lines.append("")
    lines.append("This is a **diagnostic source-truth harness**, not a pass/fail authenticity verdict and not proof that Ethiopian timbre is solved.")
    lines.append("Generated approval songs and analyzer-passed songs are not treated as primary timbre proof here.")
    if reference_status.get("user_mp3_references_are_source_truth"):
        active = ", ".join(str(value) for value in reference_status.get("user_reference_source_truth_instruments", []))
        lines.append(
            f"User-supplied MP3/local references are the active source of truth for this `--match-user-ref-shape` diagnostic run ({active})."
        )
        if not reference_status.get("include_public_refs_with_user_refs"):
            lines.append("Public/paper targets are not included alongside those user references unless `--include-public-refs-with-user-refs` is passed.")
    lines.append("")
    lines.append("## Public reference manifest")
    lines.append("")
    lines.append("- **Begena**: public reference available from Wikimedia Commons:")
    lines.append(f"  - Page: `{PUBLIC_REFERENCE_MANIFEST['begena']['page']}`")
    lines.append(f"  - Direct URL: `{PUBLIC_REFERENCE_MANIFEST['begena']['direct_url']}`")
    lines.append(f"  - License: `{PUBLIC_REFERENCE_MANIFEST['begena']['license']}`")
    lines.append(f"  - Attribution: {PUBLIC_REFERENCE_MANIFEST['begena']['attribution']}")
    lines.append("- **Krar / Masenqo / Washint**: unavailable by default in this harness: no public downloadable WAV/OGG/MP3 found in the current pass. Use `--user-ref instrument=path` to add user-supplied references.")
    lines.append("")
    lines.append("## Generated isolated probes")
    lines.append("")
    if reference_status.get("user_mp3_references_are_source_truth"):
        lines.append(
            "Default generated probes in this section are baseline descriptors only; user-reference-shaped probes are the active comparison targets in this run."
        )
        lines.append("")
    for instrument, generated in descriptors.get("generated", {}).items():
        path = generated.get("path") or "not written (use --write-generated-wavs / default CLI writes probes)"
        metadata = generated.get("metadata", {})
        spec = metadata.get("probe_spec", {})
        probe_shape = metadata.get("probe_shape", spec.get("probe_shape", "single_note"))
        if probe_shape == "reference_scale_shape":
            schedule = metadata.get("probe_schedule", {})
            frequencies = [float(value) for value in schedule.get("frequencies_hz", [])]
            frequency_text = "n/a"
            if frequencies:
                frequency_text = f"{min(frequencies):.2f}-{max(frequencies):.2f}"
            lines.append(
                f"- **{instrument}**: `{path}`; generator `{spec.get('generator')}`, shape `{probe_shape}`, "
                f"notes `{len(schedule.get('notes', []))}`, duration `{spec.get('duration_seconds')}` s, "
                f"sanitized frequency range `{frequency_text}` Hz, profile `{spec.get('profile', 'n/a')}`."
            )
        else:
            lines.append(
                f"- **{instrument}**: `{path}`; generator `{spec.get('generator')}`, shape `{probe_shape}`, "
                f"frequency `{spec.get('frequency_hz')}` Hz, duration `{spec.get('duration_seconds')}` s, "
                f"profile `{spec.get('profile', 'n/a')}`."
            )
        for warning in metadata.get("warnings", []):
            lines.append(f"  - Warning: {warning}")
    shaped_entries = descriptors.get("generated_reference_shaped", {})
    if shaped_entries and any(shaped_entries.get(instrument) for instrument in shaped_entries):
        lines.append("")
        lines.append("### User-reference-shaped generated probes")
        lines.append("")
        for instrument, entries in shaped_entries.items():
            for generated in entries:
                metadata = generated.get("metadata", {})
                schedule = metadata.get("probe_schedule", {})
                frequencies = [float(value) for value in schedule.get("frequencies_hz", [])]
                frequency_text = "n/a"
                if frequencies:
                    frequency_text = f"{min(frequencies):.2f}-{max(frequencies):.2f}"
                lines.append(
                    f"- **{instrument}** shaped to `{metadata.get('reference_source_id')}`: `{generated.get('path')}`; "
                    f"shape `{metadata.get('probe_shape')}`, notes `{len(schedule.get('notes', []))}`, "
                    f"duration `{schedule.get('duration_seconds')}` s, sanitized frequency range `{frequency_text}` Hz, "
                    f"click_smoothing `{metadata.get('click_smoothing')}`, "
                    f"release_tail_max `{metadata.get('composition_release_tail_seconds')}` s, "
                    f"max_adjacent_jump `{metadata.get('click_diagnostics', {}).get('max_adjacent_sample_jump')}`, "
                    f"full_song_generation `{metadata.get('full_song_generation')}`."
                )
    lines.append("")
    lines.append("## Reference availability")
    lines.append("")
    for instrument, entry in reference_status.get("instruments", {}).items():
        lines.append(f"- **{instrument}**: `{entry.get('effective_status')}` ({entry.get('available_reference_count', 0)} local reference file(s)).")
        if instrument in {"krar", "masenqo", "washint"} and entry.get("available_reference_count", 0) == 0:
            lines.append(f"  - Unavailable unless user supplies audio: {entry.get('manifest', {}).get('reason')}")
        if instrument == "begena":
            public_reference = entry.get("public_reference", {})
            lines.append(f"  - Begena public reference local status: `{public_reference.get('status')}` at `{public_reference.get('path')}`.")
            if entry.get("public_reference_excluded_reason"):
                lines.append(f"  - Public Begena excluded: {entry.get('public_reference_excluded_reason')}")
    lines.append("")
    lines.append("## Descriptor comparisons")
    lines.append("")
    for instrument in reference_status.get("selected_instruments", []):
        instrument_comparisons = comparisons.get("comparisons", {}).get(instrument, [])
        if not instrument_comparisons:
            lines.append(f"- **{instrument}**: no generated-vs-reference comparison run because no local reference file was available for this instrument.")
            continue
        for comparison in instrument_comparisons:
            distance = comparison.get("descriptor_distance")
            distance_text = "n/a" if distance is None else f"{float(distance):.6f}"
            lines.append(
                f"- **{instrument}** `{comparison.get('generated_probe_shape', 'single_note')}` vs `{comparison.get('reference_path')}`: "
                f"descriptor distance `{distance_text}` across `{comparison.get('descriptor_count')}` numeric descriptor fields (diagnostic only)."
            )
    lines.append("")
    lines.append("## Output files")
    lines.append("")
    lines.append("- `reference_status.json`: manifest, reference availability, download/user-ref status.")
    lines.append("- `descriptors.json`: generated/reference descriptor payloads.")
    lines.append("- `comparisons.json`: generated-vs-reference descriptor deltas when local references exist.")
    lines.append("- `summary.md`: this human-readable diagnostic summary.")
    lines.append("")
    lines.append("Do not use this report to claim that Ethiopian timbre is solved; it is the foundation for source-truth comparison and future bounded corrections.")
    lines.append("")
    return "\n".join(lines)


def run_comparison(
    *,
    refs_dir: Path | str = Path("assets") / "references" / "ethiopian",
    out_dir: Optional[Path | str] = None,
    instruments: Sequence[str] = INSTRUMENTS,
    download_public_refs: bool = False,
    user_refs: Optional[Mapping[str, Sequence[Path | str]]] = None,
    match_user_ref_shape: bool = False,
    include_public_refs_with_user_refs: bool = False,
    write_generated_wavs: bool = True,
    sample_rate: int = SAMPLE_RATE,
) -> Dict[str, Any]:
    """Run the bounded Task 129 comparison harness and write report artifacts."""

    selected = normalize_instruments(instruments)
    resolved_out = _resolve_path(out_dir or default_output_dir())
    resolved_refs = _resolve_path(refs_dir)
    resolved_out.mkdir(parents=True, exist_ok=True)

    reference_status, reference_candidates = build_reference_status(
        resolved_refs,
        selected,
        download_public_refs=download_public_refs,
        user_refs=user_refs,
        match_user_ref_shape=match_user_ref_shape,
        include_public_refs_with_user_refs=include_public_refs_with_user_refs,
    )

    descriptors: Dict[str, Any] = {
        "schema_version": 1,
        "diagnostic_only": True,
        "sample_rate_generated": sample_rate,
        "match_user_ref_shape": bool(match_user_ref_shape),
        "include_public_refs_with_user_refs": bool(include_public_refs_with_user_refs),
        "user_mp3_references_are_source_truth": bool(reference_status.get("user_mp3_references_are_source_truth")),
        "generated": {},
        "generated_reference_shaped": {instrument: [] for instrument in selected},
        "references": {instrument: [] for instrument in selected},
        "errors": [],
    }
    comparisons: Dict[str, Any] = {
        "schema_version": 1,
        "diagnostic_only": True,
        "note": "Descriptor comparisons are diagnostics only; they are not pass/fail authenticity thresholds.",
        "comparisons": {instrument: [] for instrument in selected},
        "unavailable_references": {},
    }

    for instrument in selected:
        audio, metadata = generate_probe_audio(instrument, sample_rate=sample_rate)
        generated_path: Optional[Path] = None
        if write_generated_wavs:
            generated_path = write_generated_probe_wav(resolved_out, instrument, audio, sample_rate)
        descriptors["generated"][instrument] = {
            "path": str(generated_path) if generated_path else None,
            "metadata": metadata,
            "descriptors": extract_descriptors(audio, sample_rate),
        }

    for candidate in reference_candidates:
        try:
            reference_audio, reference_sample_rate = load_audio_file(candidate.path)
            reference_descriptor = extract_descriptors(reference_audio, reference_sample_rate)
        except Exception as exc:
            descriptors["errors"].append(
                {
                    "instrument": candidate.instrument,
                    "source_id": candidate.source_id,
                    "path": str(candidate.path),
                    "error": str(exc),
                }
            )
            continue

        reference_payload = {
            "source_id": candidate.source_id,
            "kind": candidate.kind,
            "path": str(candidate.path),
            "sample_rate": reference_sample_rate,
            "metadata": dict(candidate.metadata),
            "descriptors": reference_descriptor,
        }
        reference_schedule: Optional[Dict[str, Any]] = None
        if match_user_ref_shape and candidate.kind == "user_supplied":
            reference_schedule = extract_reference_schedule(
                reference_audio,
                reference_sample_rate,
                instrument=candidate.instrument,
                source_id=candidate.source_id,
            )
            reference_payload["schedule_metadata"] = reference_schedule
        descriptors["references"].setdefault(candidate.instrument, []).append(reference_payload)

        generated_entry = descriptors["generated"][candidate.instrument]
        if reference_schedule is not None:
            shaped_audio, shaped_metadata = generate_reference_shaped_probe_audio(
                candidate.instrument,
                reference_schedule,
                reference_source_id=candidate.source_id,
                sample_rate=sample_rate,
                mp3_source_truth=True,
            )
            shaped_path: Optional[Path] = None
            if write_generated_wavs:
                shaped_path = write_generated_probe_wav(
                    resolved_out,
                    candidate.instrument,
                    shaped_audio,
                    sample_rate,
                    reference_source_id=candidate.source_id,
                )
            generated_entry = {
                "source_id": candidate.source_id,
                "path": str(shaped_path) if shaped_path else None,
                "metadata": shaped_metadata,
                "descriptors": extract_descriptors(shaped_audio, sample_rate),
            }
            descriptors["generated_reference_shaped"].setdefault(candidate.instrument, []).append(generated_entry)

        generated_descriptor = generated_entry["descriptors"]
        comparison = compare_descriptors(generated_descriptor, reference_descriptor)
        comparison.update(
            {
                "instrument": candidate.instrument,
                "generated_probe_shape": generated_entry.get("metadata", {}).get("probe_shape"),
                "generated_path": generated_entry.get("path"),
                "reference_source_id": candidate.source_id,
                "reference_kind": candidate.kind,
                "reference_path": str(candidate.path),
            }
        )
        comparisons["comparisons"].setdefault(candidate.instrument, []).append(comparison)

    for instrument in selected:
        if not comparisons["comparisons"].get(instrument):
            entry = reference_status["instruments"][instrument]
            comparisons["unavailable_references"][instrument] = {
                "effective_status": entry.get("effective_status"),
                "reason": entry.get("manifest", {}).get("reason"),
                "user_ref_supported": bool(entry.get("manifest", {}).get("supports_user_ref")),
            }

    summary = build_summary_markdown(
        reference_status=reference_status,
        descriptors=descriptors,
        comparisons=comparisons,
    )

    _write_json(resolved_out / "reference_status.json", reference_status)
    _write_json(resolved_out / "descriptors.json", descriptors)
    _write_json(resolved_out / "comparisons.json", comparisons)
    (resolved_out / "summary.md").write_text(summary, encoding="utf-8")

    return {
        "out_dir": str(resolved_out),
        "reference_status": reference_status,
        "descriptors": descriptors,
        "comparisons": comparisons,
        "summary_path": str(resolved_out / "summary.md"),
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Compare current Ethiopian generated probes against available reference audio (diagnostic only)."
    )
    parser.add_argument(
        "--refs-dir",
        default=str(Path("assets") / "references" / "ethiopian"),
        help="Directory for local Ethiopian reference audio (default: assets/references/ethiopian).",
    )
    parser.add_argument(
        "--out",
        default=None,
        help="Output directory (default: output/_diagnostics/task129_reference_compare_<timestamp>).",
    )
    parser.add_argument(
        "--instruments",
        nargs="*",
        choices=[*INSTRUMENTS, "all"],
        default=list(INSTRUMENTS),
        help="Instrument subset to process; use 'all' or omit for all four.",
    )
    parser.add_argument(
        "--download-public-refs",
        action="store_true",
        help="Download the public Begena OGG reference if missing. No internet is used unless this flag is passed.",
    )
    parser.add_argument(
        "--user-ref",
        action="append",
        default=[],
        metavar="instrument=path",
        help="Add/override a local reference file for an instrument. Repeatable for krar, masenqo, washint, or begena.",
    )
    parser.add_argument(
        "--match-user-ref-shape",
        action="store_true",
        default=False,
        help="For user-supplied refs, generate an additional per-reference isolated probe following that file's duration/onset/f0 schedule before comparison.",
    )
    parser.add_argument(
        "--include-public-refs-with-user-refs",
        action="store_true",
        default=False,
        help="When --match-user-ref-shape and --user-ref are used, also include available public references such as Commons Begena as extra diagnostics.",
    )
    parser.add_argument(
        "--write-generated-wavs",
        dest="write_generated_wavs",
        action="store_true",
        default=True,
        help="Write isolated generated probe WAVs (default: enabled for Task 129 diagnostics).",
    )
    parser.add_argument(
        "--no-write-generated-wavs",
        dest="write_generated_wavs",
        action="store_false",
        help="Skip writing generated probe WAVs while still extracting in-memory generated descriptors.",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    try:
        user_refs = parse_user_ref_arguments(args.user_ref)
        result = run_comparison(
            refs_dir=Path(args.refs_dir),
            out_dir=Path(args.out) if args.out else None,
            instruments=normalize_instruments(args.instruments),
            download_public_refs=bool(args.download_public_refs),
            user_refs=user_refs,
            match_user_ref_shape=bool(args.match_user_ref_shape),
            include_public_refs_with_user_refs=bool(args.include_public_refs_with_user_refs),
            write_generated_wavs=bool(args.write_generated_wavs),
        )
    except Exception as exc:
        parser.exit(2, f"error: {exc}\n")

    out_dir = result["out_dir"]
    print("Task 129 Ethiopian reference comparison complete (diagnostic only).")
    print(f"Output directory: {out_dir}")
    print(f"Summary: {result['summary_path']}")
    print("Missing Krar/Masenqo/Washint public references remain unavailable unless supplied via --user-ref.")
    if result["reference_status"].get("user_mp3_references_are_source_truth"):
        print("User-supplied references are the active source of truth for this diagnostic run.")
        if not result["reference_status"].get("include_public_refs_with_user_refs"):
            print("Public references were excluded alongside user refs unless explicitly included.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
