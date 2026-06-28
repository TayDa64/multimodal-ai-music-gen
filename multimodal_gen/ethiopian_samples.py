"""
Ethiopian instrument sample bank (real note extraction).

This module extracts individual *note samples* from real instrument MP3
recordings (krar, masenqo, begena) so that a later renderer step can play
back the user's actual recordings instead of purely procedural synthesis.

Design goals
------------
- **Import-safe**: numpy / librosa / soundfile are imported lazily and guarded.
  Importing this module never hard-fails even if those libraries are missing.
- **Self-contained**: no dependency on the renderer or generator pipeline.
- **Renderer-compatible**: each extracted sample dict carries the keys the
  existing renderer sample path already understands (``audio``, ``root_note``,
  ``sample_rate``) plus extra metadata for later sustain looping.

This step does NOT wire anything into the renderer; it only builds and caches
the sample banks.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

# ---------------------------------------------------------------------------
# SAMPLE_RATE (import-safe)
# ---------------------------------------------------------------------------
try:
    from .utils import SAMPLE_RATE  # type: ignore
except Exception:  # pragma: no cover - fallback when run standalone
    try:
        from multimodal_gen.utils import SAMPLE_RATE  # type: ignore
    except Exception:
        SAMPLE_RATE = 44100


# ---------------------------------------------------------------------------
# Paths / constants
# ---------------------------------------------------------------------------
_THIS_DIR = Path(__file__).resolve().parent          # .../multimodal_gen
_REPO_ROOT = _THIS_DIR.parent                         # repo root

DEFAULT_REFS_DIR = _REPO_ROOT / "assets" / "references" / "ethiopian" / "source_mp3"
DEFAULT_CACHE_DIR = _REPO_ROOT / "assets" / "references" / "ethiopian" / "_sample_cache"

# Instrument -> normalized source filenames (located under references_dir).
INSTRUMENT_SOURCES: Dict[str, List[str]] = {
    "krar": ["krar_acoustic.mp3", "krar_amplified.mp3"],
    "masenqo": ["masenqo.mp3"],
    "begena": ["begena.mp3"],
}

# Instrument-appropriate f0 search ranges (Hz): (fmin, fmax).
INSTRUMENT_F0_RANGES: Dict[str, Tuple[float, float]] = {
    "krar": (70.0, 700.0),
    "masenqo": (80.0, 700.0),
    "begena": (45.0, 200.0),
}

# Extraction tuning.
MIN_SAMPLE_SEC = 0.12          # discard segments shorter than this
MAX_SAMPLE_SEC = 2.5           # cap each sample length (preserve natural decay)
MIN_CONFIDENCE = 0.45          # minimum voiced-confidence to keep a segment
PEAK_NORM = 0.9                # normalize peak to ~0.9
FADE_MS = 4.0                  # tiny anti-click fade in/out
TRIM_TOP_DB = 40.0             # silence trim threshold
MAX_PER_PITCH = 6              # max samples kept per MIDI pitch
MAX_PER_INSTRUMENT = 120       # overall cap per instrument

_CACHE_VERSION = 1


# ---------------------------------------------------------------------------
# Lazy / guarded imports
# ---------------------------------------------------------------------------
def _np():
    try:
        import numpy as np  # type: ignore
        return np
    except Exception:
        return None


def _librosa():
    try:
        import librosa  # type: ignore
        return librosa
    except Exception:
        return None


def _soundfile():
    try:
        import soundfile  # type: ignore
        return soundfile
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------
def _to_mono(np, audio) -> Any:
    """Return a contiguous float32 mono view of ``audio``."""
    a = np.asarray(audio, dtype=np.float32)
    if a.ndim > 1:
        # average channels (assume shape (n, ch) or (ch, n))
        if a.shape[0] < a.shape[-1]:
            a = a.mean(axis=0)
        else:
            a = a.mean(axis=1)
    return np.ascontiguousarray(a, dtype=np.float32)


def _apply_fades(np, audio, sr: int, fade_ms: float = FADE_MS) -> Any:
    """Apply a tiny linear fade in/out to avoid clicks."""
    n = len(audio)
    fade_len = int(max(1, round((fade_ms / 1000.0) * sr)))
    fade_len = min(fade_len, n // 2)
    if fade_len <= 0:
        return audio
    out = audio.copy()
    fade_in = np.linspace(0.0, 1.0, fade_len, dtype=np.float32)
    fade_out = np.linspace(1.0, 0.0, fade_len, dtype=np.float32)
    out[:fade_len] *= fade_in
    out[-fade_len:] *= fade_out
    return out


def _normalize_peak(np, audio, peak: float = PEAK_NORM) -> Any:
    m = float(np.max(np.abs(audio))) if len(audio) else 0.0
    if m > 1e-9:
        return (audio * (peak / m)).astype(np.float32)
    return audio.astype(np.float32)


def _estimate_f0(np, librosa, segment, sr: int, fmin: float, fmax: float
                 ) -> Tuple[Optional[float], float]:
    """
    Estimate fundamental frequency (Hz) and a voiced-confidence in [0, 1]
    using pyin (preferred) with a yin fallback. Uses the stable middle of the
    segment to avoid onset transients / release noise.
    """
    if len(segment) < int(0.03 * sr):
        return None, 0.0

    # Confine estimation to the stable middle of the segment.
    n = len(segment)
    lo = n // 4
    hi = max(lo + 1, (3 * n) // 4)
    mid = segment[lo:hi]
    if len(mid) < int(0.02 * sr):
        mid = segment

    f0_hz: Optional[float] = None
    confidence = 0.0
    try:
        f0, voiced_flag, voiced_prob = librosa.pyin(
            mid, fmin=float(fmin), fmax=float(fmax), sr=sr
        )
        voiced = np.isfinite(f0)
        if voiced_prob is not None:
            voiced = voiced & (np.asarray(voiced_prob) >= 0.3)
        if np.any(voiced):
            f0_hz = float(np.nanmedian(f0[voiced]))
            if voiced_prob is not None:
                confidence = float(np.nanmean(np.asarray(voiced_prob)[voiced]))
            else:
                confidence = float(np.mean(voiced))
    except Exception:
        f0_hz = None
        confidence = 0.0

    if f0_hz is None or not np.isfinite(f0_hz):
        # Fallback: yin (returns f0 for every frame).
        try:
            yf = librosa.yin(mid, fmin=float(fmin), fmax=float(fmax), sr=sr)
            yf = np.asarray(yf, dtype=np.float64)
            yf = yf[np.isfinite(yf)]
            if len(yf):
                f0_hz = float(np.median(yf))
                # confidence proxy: pitch stability (low relative spread = high conf)
                med = np.median(yf)
                if med > 1e-6:
                    spread = float(np.median(np.abs(yf - med)) / med)
                    confidence = float(max(0.0, min(1.0, 1.0 - spread * 4.0)))
        except Exception:
            return None, 0.0

    if f0_hz is None or not np.isfinite(f0_hz) or f0_hz <= 0:
        return None, 0.0
    return f0_hz, float(max(0.0, min(1.0, confidence)))


def _noise_metric(np, librosa, segment, sr: int) -> float:
    """
    Lower is cleaner. Uses mean spectral flatness as a tonal/noise proxy
    (flat spectrum -> noisy; peaky spectrum -> tonal).
    """
    try:
        flat = librosa.feature.spectral_flatness(y=segment)
        return float(np.mean(flat))
    except Exception:
        return 1.0


def _detect_loop_region(np, audio, sr: int) -> Tuple[Optional[int], Optional[int]]:
    """
    Detect a stable-amplitude middle window suitable for sustain looping.
    Returns (loop_start_sample, loop_end_sample) or (None, None).
    """
    n = len(audio)
    if n < int(0.25 * sr):
        return None, None
    # RMS envelope on short frames.
    frame = max(256, int(0.02 * sr))
    hop = max(128, frame // 2)
    if n < frame * 4:
        return None, None
    # Compute frame RMS.
    n_frames = 1 + (n - frame) // hop
    if n_frames < 6:
        return None, None
    rms = np.empty(n_frames, dtype=np.float64)
    for i in range(n_frames):
        s = i * hop
        seg = audio[s:s + frame]
        rms[i] = float(np.sqrt(np.mean(seg * seg) + 1e-12))

    peak = float(np.max(rms))
    if peak <= 1e-9:
        return None, None
    norm = rms / peak

    # Search the middle for a stable plateau (low local variation, decent level).
    lo_f = n_frames // 4
    hi_f = max(lo_f + 1, (3 * n_frames) // 4)
    best = None
    win = max(3, (hi_f - lo_f) // 3)
    for start in range(lo_f, hi_f - win):
        seg = norm[start:start + win]
        level = float(np.mean(seg))
        var = float(np.std(seg))
        if level >= 0.35 and var <= 0.08:
            score = level - var
            if best is None or score > best[0]:
                best = (score, start, start + win)
    if best is None:
        return None, None
    _, sf_idx, ef_idx = best
    start_sample = int(sf_idx * hop)
    end_sample = int(min(n - 1, (ef_idx * hop) + frame))
    if end_sample - start_sample < int(0.05 * sr):
        return None, None
    return start_sample, end_sample


def _segment_boundaries(np, librosa, audio, sr: int) -> List[Tuple[int, int]]:
    """Use onset detection (with backtrack) to produce (start, end) segments."""
    try:
        onset_frames = librosa.onset.onset_detect(
            y=audio, sr=sr, backtrack=True, units="frames"
        )
        onset_samples = list(librosa.frames_to_samples(onset_frames))
    except Exception:
        onset_samples = []

    n = len(audio)
    bounds = sorted(set([0] + [int(s) for s in onset_samples if 0 < s < n] + [n]))
    segments: List[Tuple[int, int]] = []
    for i in range(len(bounds) - 1):
        a, b = bounds[i], bounds[i + 1]
        if b - a > int(0.02 * sr):
            segments.append((a, b))
    if not segments and n > 0:
        segments = [(0, n)]
    return segments


# ---------------------------------------------------------------------------
# Public: note extraction
# ---------------------------------------------------------------------------
def extract_note_samples(
    audio,
    sample_rate: int,
    instrument: str,
    *,
    target_sample_rate: int = SAMPLE_RATE,
) -> List[Dict]:
    """
    Extract individual note samples from a mono audio signal.

    Returns a list of dicts with keys compatible with the renderer's sample
    path plus extras:
        audio, root_note, sample_rate, f0_hz, confidence, instrument, name,
        loop_start_sample, loop_end_sample
    """
    np = _np()
    librosa = _librosa()
    if np is None or librosa is None:
        return []

    inst = (instrument or "").lower().strip()
    fmin, fmax = INSTRUMENT_F0_RANGES.get(inst, (60.0, 700.0))

    audio = _to_mono(np, audio)
    if len(audio) == 0:
        return []

    # Resample to the target rate up front so all downstream samples match.
    if int(sample_rate) != int(target_sample_rate):
        try:
            audio = librosa.resample(
                audio, orig_sr=int(sample_rate), target_sr=int(target_sample_rate)
            ).astype(np.float32)
        except Exception:
            return []
    sr = int(target_sample_rate)

    segments = _segment_boundaries(np, librosa, audio, sr)

    min_len = int(MIN_SAMPLE_SEC * sr)
    max_len = int(MAX_SAMPLE_SEC * sr)

    candidates: List[Dict] = []
    for idx, (a, b) in enumerate(segments):
        seg = audio[a:b]
        if len(seg) < min_len:
            continue

        # Trim leading/trailing silence.
        try:
            trimmed, _ = librosa.effects.trim(seg, top_db=TRIM_TOP_DB)
            if len(trimmed) >= min_len:
                seg = trimmed
        except Exception:
            pass

        if len(seg) < min_len:
            continue

        # Estimate pitch on the (possibly long) segment.
        f0_hz, confidence = _estimate_f0(np, librosa, seg, sr, fmin, fmax)
        if f0_hz is None or confidence < MIN_CONFIDENCE:
            continue

        # Cap length but preserve natural decay (truncate + fade later).
        if len(seg) > max_len:
            seg = seg[:max_len]

        seg = np.ascontiguousarray(seg, dtype=np.float32)
        seg = _apply_fades(np, seg, sr)
        seg = _normalize_peak(np, seg, PEAK_NORM)

        if not np.all(np.isfinite(seg)):
            continue

        try:
            root_note = int(round(float(librosa.hz_to_midi(f0_hz))))
        except Exception:
            continue
        root_note = max(0, min(127, root_note))

        loop_start, loop_end = _detect_loop_region(np, seg, sr)
        noise = _noise_metric(np, librosa, seg, sr)

        candidates.append({
            "audio": seg,
            "root_note": root_note,
            "sample_rate": sr,
            "f0_hz": float(f0_hz),
            "confidence": float(confidence),
            "instrument": inst,
            "name": f"{inst}_seg{idx:03d}_root{root_note}",
            "loop_start_sample": loop_start,
            "loop_end_sample": loop_end,
            "_noise": float(noise),
        })

    return _apply_caps(candidates)


def _apply_caps(candidates: List[Dict]) -> List[Dict]:
    """Bound samples per pitch and overall; prefer high-confidence, low-noise."""
    if not candidates:
        return []
    # Group by root_note, keep best MAX_PER_PITCH (high conf, low noise).
    by_pitch: Dict[int, List[Dict]] = {}
    for c in candidates:
        by_pitch.setdefault(c["root_note"], []).append(c)

    kept: List[Dict] = []
    for pitch, group in by_pitch.items():
        group.sort(key=lambda d: (-d["confidence"], d.get("_noise", 1.0)))
        kept.extend(group[:MAX_PER_PITCH])

    # Overall cap, prefer best globally.
    kept.sort(key=lambda d: (-d["confidence"], d.get("_noise", 1.0)))
    kept = kept[:MAX_PER_INSTRUMENT]

    # Strip private metric key.
    for c in kept:
        c.pop("_noise", None)
    return kept


# ---------------------------------------------------------------------------
# Caching
# ---------------------------------------------------------------------------
def _source_signature(references_dir: Path, filenames: List[str]) -> List[List[Any]]:
    """Signature of the source files: [name, size, mtime_ns] for existing ones."""
    sig: List[List[Any]] = []
    for fn in filenames:
        p = Path(references_dir) / fn
        if p.exists():
            st = p.stat()
            sig.append([fn, int(st.st_size), int(st.st_mtime_ns)])
        else:
            sig.append([fn, 0, 0])
    return sig


def _cache_paths(cache_dir: Path, instrument: str) -> Tuple[Path, Path]:
    base = Path(cache_dir) / instrument
    return base.with_suffix(".npz"), base.with_suffix(".json")


def _save_cache(cache_dir: Path, instrument: str, samples: List[Dict],
                signature: List[List[Any]], target_sample_rate: int) -> None:
    np = _np()
    if np is None:
        return
    Path(cache_dir).mkdir(parents=True, exist_ok=True)
    npz_path, json_path = _cache_paths(cache_dir, instrument)

    arrays = {f"audio_{i}": s["audio"] for i, s in enumerate(samples)}
    np.savez_compressed(npz_path, **arrays)

    meta = {
        "cache_version": _CACHE_VERSION,
        "instrument": instrument,
        "target_sample_rate": int(target_sample_rate),
        "signature": signature,
        "count": len(samples),
        "samples": [
            {
                "root_note": int(s["root_note"]),
                "sample_rate": int(s["sample_rate"]),
                "f0_hz": float(s["f0_hz"]),
                "confidence": float(s["confidence"]),
                "instrument": str(s["instrument"]),
                "name": str(s["name"]),
                "loop_start_sample": s.get("loop_start_sample"),
                "loop_end_sample": s.get("loop_end_sample"),
            }
            for s in samples
        ],
    }
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)


def _load_cache(cache_dir: Path, instrument: str,
                signature: List[List[Any]]) -> Optional[List[Dict]]:
    np = _np()
    if np is None:
        return None
    npz_path, json_path = _cache_paths(cache_dir, instrument)
    if not npz_path.exists() or not json_path.exists():
        return None
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            meta = json.load(f)
    except Exception:
        return None

    if meta.get("cache_version") != _CACHE_VERSION:
        return None
    if meta.get("signature") != signature:
        return None

    try:
        npz = np.load(npz_path, allow_pickle=False)
    except Exception:
        return None

    samples: List[Dict] = []
    for i, sm in enumerate(meta.get("samples", [])):
        key = f"audio_{i}"
        if key not in npz:
            return None
        audio = np.asarray(npz[key], dtype=np.float32)
        samples.append({
            "audio": audio,
            "root_note": int(sm["root_note"]),
            "sample_rate": int(sm["sample_rate"]),
            "f0_hz": float(sm["f0_hz"]),
            "confidence": float(sm["confidence"]),
            "instrument": str(sm["instrument"]),
            "name": str(sm["name"]),
            "loop_start_sample": sm.get("loop_start_sample"),
            "loop_end_sample": sm.get("loop_end_sample"),
        })
    return samples


# ---------------------------------------------------------------------------
# Public: bank building
# ---------------------------------------------------------------------------
def build_sample_bank(
    instrument: str,
    *,
    references_dir: os.PathLike | str = DEFAULT_REFS_DIR,
    cache_dir: os.PathLike | str = DEFAULT_CACHE_DIR,
    target_sample_rate: int = SAMPLE_RATE,
    force: bool = False,
) -> List[Dict]:
    """
    Build (or load from cache) the extracted note sample bank for an instrument.

    Returns [] gracefully if librosa/soundfile are unavailable or no sources
    are found.
    """
    np = _np()
    librosa = _librosa()
    if np is None or librosa is None:
        return []

    inst = (instrument or "").lower().strip()
    filenames = INSTRUMENT_SOURCES.get(inst, [])
    if not filenames:
        return []

    references_dir = Path(references_dir)
    cache_dir = Path(cache_dir)

    existing = [fn for fn in filenames if (references_dir / fn).exists()]
    if not existing:
        return []

    signature = _source_signature(references_dir, filenames)

    if not force:
        cached = _load_cache(cache_dir, inst, signature)
        if cached is not None:
            return cached

    all_samples: List[Dict] = []
    for fn in existing:
        path = references_dir / fn
        try:
            audio, sr = librosa.load(str(path), sr=target_sample_rate, mono=True)
        except Exception:
            continue
        samples = extract_note_samples(
            audio, sr, inst, target_sample_rate=target_sample_rate
        )
        all_samples.extend(samples)

    all_samples = _apply_caps(all_samples)

    try:
        _save_cache(cache_dir, inst, all_samples, signature, target_sample_rate)
    except Exception:
        pass

    return all_samples


def load_ethiopian_sample_bank(
    instruments: List[str],
    *,
    references_dir: os.PathLike | str = DEFAULT_REFS_DIR,
    cache_dir: os.PathLike | str = DEFAULT_CACHE_DIR,
    target_sample_rate: int = SAMPLE_RATE,
    force: bool = False,
) -> Dict[str, List[Dict]]:
    """Build/load sample banks for several instruments at once."""
    out: Dict[str, List[Dict]] = {}
    for inst in instruments:
        out[(inst or "").lower().strip()] = build_sample_bank(
            inst,
            references_dir=references_dir,
            cache_dir=cache_dir,
            target_sample_rate=target_sample_rate,
            force=force,
        )
    return out


# ---------------------------------------------------------------------------
# Public: sustain-aware sample rendering (single source of truth)
# ---------------------------------------------------------------------------
# Deterministic round-robin state for tie-breaking between equally-near samples.
_RENDER_ROUND_ROBIN: Dict[Tuple[Any, ...], int] = {}


def _resample_audio(np, audio, orig_sr: int, target_sr: int) -> Any:
    """Resample ``audio`` from ``orig_sr`` to ``target_sr`` (librosa or linear)."""
    a = np.asarray(audio, dtype=np.float32)
    if int(orig_sr) == int(target_sr) or len(a) == 0:
        return a
    librosa = _librosa()
    if librosa is not None:
        try:
            return librosa.resample(
                a, orig_sr=int(orig_sr), target_sr=int(target_sr)
            ).astype(np.float32)
        except Exception:
            pass
    # Linear-interpolation fallback (keeps the module import-safe).
    ratio = float(target_sr) / float(max(1, int(orig_sr)))
    new_len = max(1, int(round(len(a) * ratio)))
    xp = np.arange(len(a), dtype=np.float64)
    x = np.linspace(0.0, len(a) - 1, new_len)
    return np.interp(x, xp, a.astype(np.float64)).astype(np.float32)


def _equal_power_fades(np, n: int) -> Tuple[Any, Any]:
    """Return (fade_in, fade_out) equal-power ramps of length ``n``."""
    theta = np.linspace(0.0, np.pi / 2.0, int(n), dtype=np.float32)
    return np.sin(theta), np.cos(theta)


def _sustain_loop_fill(np, audio, target_len: int, loop_start, loop_end, sr: int) -> Any:
    """
    Fill ``audio`` to ``target_len`` samples by looping a sustain region with
    short equal-power crossfades, preserving the natural attack and appending a
    natural release tail. Assumes ``target_len > len(audio)``.

    NEVER leaves a zero-gap silence inside the sustained body when a loop region
    (explicit or derived) exists. Falls back to a minimal zero-pad only when the
    sample is too short to derive any usable loop region.
    """
    n = len(audio)
    ls = le = -1
    try:
        if loop_start is not None and loop_end is not None:
            ls = int(loop_start)
            le = int(loop_end)
    except (TypeError, ValueError):
        ls = le = -1

    min_loop = max(1, int(0.03 * sr))
    valid = (0 <= ls < le <= n) and (le - ls) >= min_loop
    if not valid:
        # Derive a fallback sustain loop from the tail so a sustained note never
        # collapses into dead silence when explicit markers are absent.
        if n >= int(0.20 * sr):
            ls = int(n * 0.45)
            le = n
            valid = (le - ls) >= min_loop
    if not valid:
        out = np.zeros(int(target_len), dtype=np.float32)
        m = min(n, int(target_len))
        out[:m] = audio[:m]
        return out

    loop = np.ascontiguousarray(audio[ls:le], dtype=np.float32)
    release = np.ascontiguousarray(audio[le:], dtype=np.float32)
    loop_len = len(loop)
    xf = int(min(loop_len // 2, max(1, round(0.018 * sr))))
    fade_in, fade_out = _equal_power_fades(np, xf) if xf > 1 else (None, None)

    body_target = max(le, int(target_len) - len(release))
    out = np.ascontiguousarray(audio[:le], dtype=np.float32).copy()  # attack + first loop pass

    guard = 0
    while len(out) < body_target and guard < 200000:
        guard += 1
        if xf > 1 and len(out) >= xf:
            tail = out[-xf:]
            head = loop[:xf]
            mixed = (tail * fade_out + head * fade_in).astype(np.float32)
            out = np.concatenate([out[:-xf], mixed, loop[xf:]])
        else:
            out = np.concatenate([out, loop])

    # Append the natural release tail with an equal-power crossfade.
    if len(release) > 0:
        if xf > 1 and len(out) >= xf:
            tail = out[-xf:]
            head = release[:xf]
            mixed = (tail * fade_out + head * fade_in).astype(np.float32)
            out = np.concatenate([out[:-xf], mixed, release[xf:]])
        else:
            out = np.concatenate([out, release])

    if len(out) >= target_len:
        out = np.ascontiguousarray(out[:int(target_len)], dtype=np.float32)
    else:
        pad = np.zeros(int(target_len) - len(out), dtype=np.float32)
        out = np.concatenate([np.asarray(out, dtype=np.float32), pad])
    return out.astype(np.float32)


def render_note_from_bank(
    bank: List[Dict],
    target_midi: int,
    duration: float,
    velocity: float,
    sample_rate: int,
    *,
    seed: Optional[int] = None,
) -> Any:
    """
    Render a single note from an extracted sample ``bank`` (one instrument).

    The note is produced by picking the sample whose ``root_note`` is nearest
    ``target_midi`` (deterministic round-robin among ties), pitch-shifting it by
    resampling, and either looping its sustain region (with equal-power
    crossfades) to fill long notes or truncating/padding short ones. The result
    is finite ``float32`` with peak <= 1.0 and length ``int(duration*sr)``.

    Returns ``zeros(int(duration*sr))`` when the bank is empty. Import-safe: if
    numpy is unavailable an empty list is returned.
    """
    np = _np()
    sr = int(sample_rate)
    target_len = max(0, int(round(float(duration) * sr)))
    if np is None:
        return []
    if not bank:
        return np.zeros(target_len, dtype=np.float32)

    # --- Nearest-root selection with deterministic round-robin on ties --------
    roots = [int(s.get("root_note", 60)) for s in bank]
    target = int(round(float(target_midi)))
    dists = [abs(r - target) for r in roots]
    min_d = min(dists)
    candidates = [i for i, d in enumerate(dists) if d == min_d]
    if len(candidates) == 1:
        pick = candidates[0]
    elif seed is not None:
        pick = candidates[int(seed) % len(candidates)]
    else:
        key = (tuple(candidates), min_d)
        counter = _RENDER_ROUND_ROBIN.get(key, 0)
        pick = candidates[counter % len(candidates)]
        _RENDER_ROUND_ROBIN[key] = counter + 1
    variant = bank[pick]

    audio = np.asarray(variant.get("audio"), dtype=np.float32)
    if audio.ndim > 1:
        audio = _to_mono(np, audio)
    audio = np.ascontiguousarray(audio, dtype=np.float32).copy()
    if len(audio) == 0 or target_len == 0:
        return np.zeros(target_len, dtype=np.float32)

    orig_len0 = len(audio)
    loop_start = variant.get("loop_start_sample")
    loop_end = variant.get("loop_end_sample")
    root_note = int(variant.get("root_note", 60))

    # Match the stored sample to the renderer rate before pitch shifting.
    src_sr = int(variant.get("sample_rate", sr) or sr)
    if src_sr != sr:
        audio = _resample_audio(np, audio, src_sr, sr)

    # --- Pitch shift by resampling (resample DOWN to pitch UP) ----------------
    semitones = target - root_note
    shift_ratio = 2.0 ** (semitones / 12.0)
    if abs(shift_ratio - 1.0) > 1e-3:
        shifted_sr = max(1, int(round(sr / shift_ratio)))
        audio = _resample_audio(np, audio, shifted_sr, sr)

    # Scale loop markers to the final (resampled) audio length.
    final_len = len(audio)
    ls = le = None
    if loop_start is not None and loop_end is not None and orig_len0 > 0:
        scale = final_len / float(orig_len0)
        ls = int(round(int(loop_start) * scale))
        le = int(round(int(loop_end) * scale))

    # --- Fit to the requested duration ----------------------------------------
    if final_len >= target_len:
        out = np.ascontiguousarray(audio[:target_len], dtype=np.float32).copy()
        fade = min(int(0.05 * sr), len(out) // 4)
        if fade > 0:
            out[-fade:] *= np.linspace(1.0, 0.0, fade, dtype=np.float32)
    else:
        out = _sustain_loop_fill(np, audio, target_len, ls, le, sr)

    # Anti-click fade in/out + velocity scaling.
    out = _apply_fades(np, out, sr)
    out = out * float(np.clip(velocity, 0.0, 1.0))
    out = np.nan_to_num(out, nan=0.0, posinf=0.0, neginf=0.0).astype(np.float32)

    peak = float(np.max(np.abs(out))) if out.size else 0.0
    if peak > 1.0:
        out = (out / peak).astype(np.float32)
    return out
