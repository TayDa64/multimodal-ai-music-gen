"""
File Analysis - Lightweight analysis for audio/MIDI files

Implements the Python side of TODOtasks Milestone 2 (/analyze) with an
offline-first, dependency-optional approach.

Design goals:
- Best-effort analysis with graceful degradation when optional deps are missing
- Deterministic, JSON-serializable output for JUCE UI consumption
- No impact on existing generation pipeline (additive feature)
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Tuple
import json
import math
import os
import time

import numpy as np

try:
    import soundfile as sf
    HAS_SOUNDFILE = True
except ImportError:
    HAS_SOUNDFILE = False

try:
    import mido
    HAS_MIDO = True
except ImportError:
    HAS_MIDO = False

try:
    import librosa
    HAS_LIBROSA = True
except ImportError:
    HAS_LIBROSA = False


ProgressCb = Callable[[str, float, str], None]


@dataclass
class AnalysisResult:
    request_id: str
    file_path: str
    file_type: str  # "audio" | "midi" | "unknown"

    bpm_estimate: float = 0.0
    bpm_confidence: float = 0.0
    key_estimate: str = ""
    mode_estimate: str = ""  # "major" | "minor" | ""
    time_signature: str = "4/4"

    loudness_rms_db: float = float("nan")
    peak_db: float = float("nan")
    duration_seconds: float = 0.0
    spectral_centroid_hz: float = float("nan")

    detected_genre: str = ""
    prompt_suggestion: str = ""

    warnings: list[str] = field(default_factory=list)
    extra: Dict[str, Any] = field(default_factory=dict)

    schema_version: int = 1

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        # JSON can't represent NaN; replace with None for portability
        for k in ("loudness_rms_db", "peak_db", "spectral_centroid_hz"):
            if isinstance(d.get(k), float) and (math.isnan(d[k]) or math.isinf(d[k])):
                d[k] = None
        return d


def _dbfs(x: float) -> float:
    if x <= 1e-12:
        return -120.0
    return 20.0 * math.log10(float(x))


def _spectral_centroid(audio: np.ndarray, sr: int) -> float:
    if audio.size == 0:
        return float("nan")
    if audio.ndim > 1:
        audio = np.mean(audio, axis=1)
    # window small slice for speed
    if audio.size > sr * 20:
        audio = audio[: sr * 20]
    audio = audio.astype(np.float64, copy=False)
    audio = audio - np.mean(audio)
    mag = np.abs(np.fft.rfft(audio))
    if mag.size == 0:
        return float("nan")
    freqs = np.fft.rfftfreq(audio.size, 1.0 / sr)
    denom = np.sum(mag)
    if denom <= 1e-12:
        return float("nan")
    return float(np.sum(freqs * mag) / denom)


def _estimate_key_from_midi_notes(note_numbers: list[int]) -> Tuple[str, str, float]:
    # Minimal Krumhansl-Schmuckler style approach with pitch-class histogram.
    if not note_numbers:
        return "", "", 0.0

    pitch_classes = [n % 12 for n in note_numbers if 0 <= n <= 127]
    if not pitch_classes:
        return "", "", 0.0

    hist = np.bincount(pitch_classes, minlength=12).astype(np.float64)
    hist /= max(1.0, float(hist.sum()))

    # Krumhansl profiles (normalized)
    major = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
    minor = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])
    major /= major.sum()
    minor /= minor.sum()

    def best_match(profile: np.ndarray) -> Tuple[int, float]:
        scores = []
        for root in range(12):
            rotated = np.roll(profile, root)
            scores.append(float(np.dot(hist, rotated)))
        best_root = int(np.argmax(scores))
        return best_root, float(scores[best_root])

    major_root, major_score = best_match(major)
    minor_root, minor_score = best_match(minor)

    note_names = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
    if minor_score > major_score:
        return note_names[minor_root], "minor", minor_score
    return note_names[major_root], "major", major_score


def _read_audio(path: Path) -> Tuple[np.ndarray, int, list[str]]:
    warnings: list[str] = []
    if HAS_SOUNDFILE:
        audio, sr = sf.read(str(path), always_2d=False)
        return audio, int(sr), warnings

    # Fallback supports WAV only
    if path.suffix.lower() != ".wav":
        raise RuntimeError("soundfile not installed; only .wav analysis is supported")

    import wave

    with wave.open(str(path), "rb") as wf:
        sr = wf.getframerate()
        n = wf.getnframes()
        sampwidth = wf.getsampwidth()
        channels = wf.getnchannels()
        frames = wf.readframes(n)

    if sampwidth == 2:
        data = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
    elif sampwidth == 4:
        data = np.frombuffer(frames, dtype=np.int32).astype(np.float32) / 2147483648.0
    else:
        warnings.append(f"Unsupported WAV sample width: {sampwidth} bytes")
        data = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0

    if channels > 1:
        data = data.reshape(-1, channels)
    return data, int(sr), warnings


def _cache_key(path: Path, options: Dict[str, Any]) -> str:
    stat = path.stat()
    payload = {
        "path": str(path.resolve()),
        "mtime": int(stat.st_mtime),
        "size": int(stat.st_size),
        "options": options,
    }
    import hashlib
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()


def load_cached_result(cache_dir: Path, path: Path, options: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    cache_dir.mkdir(parents=True, exist_ok=True)
    key = _cache_key(path, options)
    cache_path = cache_dir / f"{key}.json"
    if not cache_path.exists():
        return None
    try:
        return json.loads(cache_path.read_text(encoding="utf-8"))
    except Exception:
        return None


def save_cached_result(cache_dir: Path, path: Path, options: Dict[str, Any], result: Dict[str, Any]) -> None:
    cache_dir.mkdir(parents=True, exist_ok=True)
    key = _cache_key(path, options)
    cache_path = cache_dir / f"{key}.json"
    cache_path.write_text(json.dumps(result, indent=2), encoding="utf-8")


def analyze_path(
    file_path: str,
    request_id: str,
    options: Optional[Dict[str, Any]] = None,
    progress: Optional[ProgressCb] = None,
) -> AnalysisResult:
    options = options or {}
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(str(path))

    cache_root = Path(options.get("cache_dir") or (Path(__file__).parent.parent / "output"))
    cache_dir = cache_root / ".analysis_cache"

    cached = load_cached_result(cache_dir, path, options)
    if cached is not None:
        return AnalysisResult(**cached)

    def report(step: str, pct: float, msg: str):
        if progress:
            progress(step, pct, msg)

    report("analyze_loading", 0.05, "Loading file...")

    suffix = path.suffix.lower()
    is_midi = suffix in (".mid", ".midi")
    is_audio = suffix in (".wav", ".aif", ".aiff", ".flac", ".mp3", ".ogg", ".m4a")

    result = AnalysisResult(
        request_id=request_id,
        file_path=str(path),
        file_type="midi" if is_midi else ("audio" if is_audio else "unknown"),
        schema_version=1,
    )

    if is_midi:
        if not HAS_MIDO:
            result.warnings.append("mido not installed; MIDI analysis unavailable")
            save_cached_result(cache_dir, path, options, result.to_dict())
            return result

        report("analyze_midi", 0.25, "Analyzing MIDI...")
        midi = mido.MidiFile(str(path))
        result.duration_seconds = float(getattr(midi, "length", 0.0) or 0.0)

        # tempo estimate from first set_tempo meta
        tempo_us = None
        note_numbers: list[int] = []
        for track in midi.tracks:
            for msg in track:
                if msg.type == "set_tempo" and tempo_us is None:
                    tempo_us = msg.tempo
                if msg.type == "note_on" and getattr(msg, "velocity", 0) > 0:
                    note_numbers.append(int(msg.note))

        if tempo_us:
            result.bpm_estimate = float(60_000_000.0 / tempo_us)
            result.bpm_confidence = 0.9

        key, mode, conf = _estimate_key_from_midi_notes(note_numbers)
        result.key_estimate = key
        result.mode_estimate = mode
        result.extra["key_confidence"] = conf

        # prompt suggestion
        parts = []
        if result.bpm_estimate > 0:
            parts.append(f"{result.bpm_estimate:.0f} BPM")
        if result.key_estimate and result.mode_estimate:
            parts.append(f"in {result.key_estimate} {result.mode_estimate}")
        hint = " ".join(parts).strip()
        result.prompt_suggestion = f"Generate a track {hint}".strip()

        save_cached_result(cache_dir, path, options, result.to_dict())
        report("analyze_complete", 1.0, "Analysis complete")
        return result

    if is_audio:
        report("analyze_audio", 0.25, "Analyzing audio...")
        audio, sr, warn = _read_audio(path)
        result.warnings.extend(warn)

        # duration
        if isinstance(audio, np.ndarray):
            n = audio.shape[0] if audio.ndim == 1 else audio.shape[0]
            result.duration_seconds = float(n) / float(sr)

        # loudness/peak
        mono = audio if audio.ndim == 1 else np.mean(audio, axis=1)
        mono = mono.astype(np.float64, copy=False)
        rms = float(np.sqrt(np.mean(mono**2))) if mono.size else 0.0
        peak = float(np.max(np.abs(mono))) if mono.size else 0.0
        result.loudness_rms_db = _dbfs(rms)
        result.peak_db = _dbfs(peak)
        result.spectral_centroid_hz = _spectral_centroid(mono, sr)

        # optional bpm/key estimation
        report("analyze_tempo_key", 0.65, "Estimating tempo/key...")
        if HAS_LIBROSA:
            try:
                y = mono.astype(np.float32, copy=False)
                # librosa expects float32 mono
                tempo = librosa.beat.tempo(y=y, sr=sr, aggregate=np.median)
                if isinstance(tempo, np.ndarray):
                    tempo = float(tempo[0]) if tempo.size else 0.0
                result.bpm_estimate = float(tempo or 0.0)
                result.bpm_confidence = 0.6 if result.bpm_estimate > 0 else 0.0

                chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
                chroma_mean = np.mean(chroma, axis=1)
                if float(np.sum(chroma_mean)) > 0:
                    chroma_mean /= float(np.sum(chroma_mean))
                # reuse MIDI key estimator by mapping chroma weights to pseudo-notes
                pseudo_notes = []
                for pc, w in enumerate(chroma_mean):
                    pseudo_notes += [pc + 60] * int(max(0, round(float(w) * 200)))
                key, mode, conf = _estimate_key_from_midi_notes(pseudo_notes)
                result.key_estimate = key
                result.mode_estimate = mode
                result.extra["key_confidence"] = conf
            except Exception as e:
                result.warnings.append(f"librosa analysis failed: {e}")
        else:
            result.warnings.append("librosa not installed; BPM/key estimation skipped")

        # prompt suggestion
        parts = []
        if result.bpm_estimate > 0:
            parts.append(f"{result.bpm_estimate:.0f} BPM")
        if result.key_estimate and result.mode_estimate:
            parts.append(f"in {result.key_estimate} {result.mode_estimate}")
        hint = " ".join(parts).strip()
        if hint:
            result.prompt_suggestion = f"Make a track {hint} with a similar groove and tonal balance"
        else:
            result.prompt_suggestion = "Make a track inspired by this reference (tempo, groove, and tone)"

        save_cached_result(cache_dir, path, options, result.to_dict())
        report("analyze_complete", 1.0, "Analysis complete")
        return result

    result.warnings.append(f"Unsupported file type: {path.suffix}")
    save_cached_result(cache_dir, path, options, result.to_dict())
    report("analyze_complete", 1.0, "Analysis complete")
    return result

