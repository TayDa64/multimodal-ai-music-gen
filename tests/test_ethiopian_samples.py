"""
Deterministic unit tests for multimodal_gen.ethiopian_samples.

These tests DO NOT depend on the real MP3 source files. They build synthetic
signals so they run in CI without any reference audio present.
"""

import math
import os

import numpy as np
import pytest

from multimodal_gen import ethiopian_samples as es

librosa = pytest.importorskip("librosa")


SR = 22050  # use a lighter rate for fast pyin in tests


def _sine(freq, dur, sr=SR, amp=0.6):
    t = np.arange(int(dur * sr), dtype=np.float32) / sr
    # small attack/decay so onset detection has transients
    env = np.ones_like(t)
    a = int(0.01 * sr)
    if a > 0:
        env[:a] = np.linspace(0.0, 1.0, a)
        env[-a:] = np.linspace(1.0, 0.0, a)
    return (amp * env * np.sin(2 * math.pi * freq * t)).astype(np.float32)


def _multi_note_signal(freqs, note_dur=0.6, gap=0.2, sr=SR):
    silence = np.zeros(int(gap * sr), dtype=np.float32)
    parts = [silence]
    for f in freqs:
        parts.append(_sine(f, note_dur, sr=sr))
        parts.append(silence)
    return np.concatenate(parts).astype(np.float32)


# Four clear tones (A2, A3, E4, A4-ish) with silence gaps.
NOTE_FREQS = [110.0, 220.0, 330.0, 440.0]
REQUIRED_KEYS = {
    "audio", "root_note", "sample_rate", "f0_hz", "confidence",
    "instrument", "name", "loop_start_sample", "loop_end_sample",
}


def test_extract_note_samples_basic():
    sig = _multi_note_signal(NOTE_FREQS, sr=SR)
    samples = es.extract_note_samples(
        sig, SR, "krar", target_sample_rate=SR
    )
    assert isinstance(samples, list)
    assert len(samples) >= 1

    for s in samples:
        assert REQUIRED_KEYS.issubset(s.keys())
        audio = s["audio"]
        assert isinstance(audio, np.ndarray)
        assert audio.dtype == np.float32
        assert np.all(np.isfinite(audio))
        peak = float(np.max(np.abs(audio))) if len(audio) else 0.0
        assert peak <= 1.0 + 1e-6
        assert s["sample_rate"] == SR
        assert 0 <= s["root_note"] <= 127
        assert 0.0 <= s["confidence"] <= 1.0


def test_extract_root_notes_near_synthetic_pitches():
    sig = _multi_note_signal(NOTE_FREQS, sr=SR)
    samples = es.extract_note_samples(sig, SR, "krar", target_sample_rate=SR)
    assert samples, "expected at least one extracted sample"

    expected_midi = {round(float(librosa.hz_to_midi(f))) for f in NOTE_FREQS}
    got_midi = {s["root_note"] for s in samples}

    # At least one extracted root note should land within ~1 semitone of a tone.
    matched = any(
        any(abs(g - e) <= 1 for e in expected_midi) for g in got_midi
    )
    assert matched, f"root notes {got_midi} not near {expected_midi}"


def test_cache_round_trip(tmp_path):
    # Create a fake references dir with a synthetic wav as a "source".
    refs = tmp_path / "refs"
    cache = tmp_path / "cache"
    refs.mkdir(parents=True)

    sf = es._soundfile()
    if sf is None:
        pytest.skip("soundfile unavailable")

    inst = "krar"
    # Override INSTRUMENT_SOURCES for this instrument to a single synthetic file.
    src_name = "krar_acoustic.mp3"  # name only; we write a wav under that name's stem
    # librosa.load can read wav regardless of extension via soundfile; write WAV.
    wav_name = "synthetic_source.wav"
    sf.write(str(refs / wav_name), _multi_note_signal(NOTE_FREQS, sr=SR), SR)

    orig_sources = es.INSTRUMENT_SOURCES.get(inst)
    es.INSTRUMENT_SOURCES[inst] = [wav_name]
    try:
        first = es.build_sample_bank(
            inst, references_dir=refs, cache_dir=cache,
            target_sample_rate=SR, force=True,
        )
        assert len(first) >= 1

        npz_path, json_path = es._cache_paths(cache, inst)
        assert npz_path.exists()
        assert json_path.exists()

        # Rebuild without force: must load from cache (same count).
        second = es.build_sample_bank(
            inst, references_dir=refs, cache_dir=cache,
            target_sample_rate=SR, force=False,
        )
        assert len(second) == len(first)

        # Sanity: cached audio arrays match originals.
        assert np.allclose(first[0]["audio"], second[0]["audio"])
    finally:
        if orig_sources is not None:
            es.INSTRUMENT_SOURCES[inst] = orig_sources


def test_missing_source_returns_empty(tmp_path):
    refs = tmp_path / "empty_refs"
    cache = tmp_path / "empty_cache"
    refs.mkdir(parents=True)
    # No source files present -> [] without raising.
    result = es.build_sample_bank(
        "masenqo", references_dir=refs, cache_dir=cache,
        target_sample_rate=SR, force=True,
    )
    assert result == []


def test_unknown_instrument_returns_empty(tmp_path):
    result = es.build_sample_bank(
        "not_an_instrument", references_dir=tmp_path, cache_dir=tmp_path,
        force=True,
    )
    assert result == []


def test_load_ethiopian_sample_bank_shape(tmp_path):
    out = es.load_ethiopian_sample_bank(
        ["masenqo", "begena"], references_dir=tmp_path, cache_dir=tmp_path,
        force=True,
    )
    assert set(out.keys()) == {"masenqo", "begena"}
    assert out["masenqo"] == []
    assert out["begena"] == []


# ---------------------------------------------------------------------------
# render_note_from_bank: sustain-aware sample rendering
# ---------------------------------------------------------------------------
RENDER_SR = 22050


def _looped_sample(root_note=60, dur=0.30, sr=RENDER_SR, amp=0.6, freq=220.0):
    """A short tonal sample with a sustain loop region in the stable middle."""
    n = int(dur * sr)
    t = np.arange(n, dtype=np.float32) / sr
    audio = (amp * np.sin(2 * math.pi * freq * t)).astype(np.float32)
    # Tiny attack/release so the natural envelope is preserved.
    a = max(1, int(0.01 * sr))
    audio[:a] *= np.linspace(0.0, 1.0, a, dtype=np.float32)
    audio[-a:] *= np.linspace(1.0, 0.0, a, dtype=np.float32)
    loop_start = int(0.10 * sr)
    loop_end = int(0.22 * sr)
    return {
        "audio": audio,
        "root_note": int(root_note),
        "sample_rate": sr,
        "f0_hz": float(freq),
        "confidence": 0.9,
        "instrument": "krar",
        "name": f"krar_root{root_note}",
        "loop_start_sample": loop_start,
        "loop_end_sample": loop_end,
    }


def _max_interior_silence_run(audio, sr, threshold=1e-5, edge_seconds=0.06):
    """Longest run (samples) of near-zero values away from the head/tail edges."""
    edge = int(edge_seconds * sr)
    interior = audio[edge: len(audio) - edge] if len(audio) > 2 * edge else audio
    silent = np.abs(interior) < threshold
    best = run = 0
    for s in silent:
        run = run + 1 if s else 0
        best = max(best, run)
    return best


def test_render_note_from_bank_short_note_is_finite_and_correct_length():
    bank = [_looped_sample(root_note=60)]
    duration = 0.20  # <= 0.30s sample length
    out = es.render_note_from_bank(bank, 60, duration, 0.8, RENDER_SR)
    expected = int(duration * RENDER_SR)
    assert isinstance(out, np.ndarray)
    assert out.dtype == np.float32
    assert abs(len(out) - expected) <= 1
    assert np.all(np.isfinite(out))
    assert float(np.max(np.abs(out))) <= 1.0 + 1e-6


def test_render_note_from_bank_long_sustained_note_loops_without_internal_silence():
    bank = [_looped_sample(root_note=60)]
    duration = 1.50  # >> 0.30s sample length -> requires sustain looping
    out = es.render_note_from_bank(bank, 60, duration, 0.8, RENDER_SR)
    expected = int(duration * RENDER_SR)
    assert abs(len(out) - expected) <= 1
    assert np.all(np.isfinite(out))
    assert float(np.max(np.abs(out))) <= 1.0 + 1e-6
    # A loop exists: the sustained body must not collapse into dead silence.
    max_silence = _max_interior_silence_run(out, RENDER_SR)
    assert max_silence < int(0.02 * RENDER_SR), (
        f"unexpected interior silence run of {max_silence} samples"
    )


def test_render_note_from_bank_nearest_root_selection_picks_expected_sample():
    # Two distinct-amplitude constant-ish samples at well-separated roots.
    low = _looped_sample(root_note=60, amp=0.40)
    high = _looped_sample(root_note=72, amp=0.85)
    bank = [low, high]

    # Target 61 is nearest root 60 (low amp ~0.40 after velocity 1.0).
    out_low = es.render_note_from_bank(bank, 61, 0.18, 1.0, RENDER_SR, seed=0)
    # Target 70 is nearest root 72 (high amp ~0.85 after velocity 1.0).
    out_high = es.render_note_from_bank(bank, 70, 0.18, 1.0, RENDER_SR, seed=0)

    peak_low = float(np.max(np.abs(out_low)))
    peak_high = float(np.max(np.abs(out_high)))
    assert peak_low < peak_high
    assert peak_low < 0.6  # closer to the 0.40 sample
    assert peak_high > 0.6  # closer to the 0.85 sample


def test_render_note_from_bank_empty_bank_returns_zeros():
    out = es.render_note_from_bank([], 60, 0.25, 0.8, RENDER_SR)
    expected = int(0.25 * RENDER_SR)
    assert isinstance(out, np.ndarray)
    assert abs(len(out) - expected) <= 1
    assert not np.any(out)


def test_render_note_from_bank_round_robin_is_deterministic_with_seed():
    a = _looped_sample(root_note=60, amp=0.5, freq=200.0)
    b = _looped_sample(root_note=60, amp=0.5, freq=400.0)
    bank = [a, b]
    first = es.render_note_from_bank(bank, 60, 0.18, 0.9, RENDER_SR, seed=1)
    second = es.render_note_from_bank(bank, 60, 0.18, 0.9, RENDER_SR, seed=1)
    assert np.allclose(first, second)
