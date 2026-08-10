"""Focused regressions for the upgraded mainstream instrument engines.

These assert the natural-realism behaviors added by the physical-modeling
upgrades (velocity->brightness, determinism, finiteness, bounds, zero-safety)
without pinning exact sample values, so they stay robust while guarding the
properties that matter for natural sound.
"""

import numpy as np

from multimodal_gen.assets_gen import (
    SAMPLE_RATE,
    generate_guitar_tone,
    generate_bass_tone,
    generate_piano_tone,
    generate_brass_tone,
)


def _hf_ratio(audio: np.ndarray, cutoff_hz: float = 2000.0, sample_rate: int = SAMPLE_RATE) -> float:
    audio = np.asarray(audio, dtype=np.float64)
    if audio.size == 0:
        return 0.0
    spectrum = np.abs(np.fft.rfft(audio))
    freqs = np.fft.rfftfreq(audio.size, d=1.0 / sample_rate)
    total = float(np.sum(spectrum))
    if total <= 0.0:
        return 0.0
    return float(np.sum(spectrum[freqs > cutoff_hz]) / total)


def _assert_render_invariants(audio: np.ndarray) -> None:
    assert audio.dtype == np.float32
    assert audio.size > 0
    assert np.all(np.isfinite(audio))
    assert np.max(np.abs(audio)) <= 1.0


# --- guitar (PR 2) ------------------------------------------------------------

def test_guitar_zero_duration_is_empty_and_finite():
    zero = generate_guitar_tone(220.0, 0.0, 0.8)
    assert zero.size == 0
    assert np.all(np.isfinite(zero))


def test_guitar_short_note_is_finite_and_bounded():
    audio = generate_guitar_tone(440.0, 0.05, 0.8)
    _assert_render_invariants(audio)


def test_guitar_is_deterministic():
    a = generate_guitar_tone(196.0, 0.4, 0.75, drive=0.5)
    b = generate_guitar_tone(196.0, 0.4, 0.75, drive=0.5)
    assert np.array_equal(a, b)


def test_guitar_velocity_increases_brightness():
    soft = generate_guitar_tone(196.0, 0.5, 0.25, drive=0.4)
    loud = generate_guitar_tone(196.0, 0.5, 0.95, drive=0.4)
    _assert_render_invariants(soft)
    _assert_render_invariants(loud)
    # Louder playing picks nearer the bridge and opens the filter -> brighter.
    assert _hf_ratio(loud) > _hf_ratio(soft)


def test_guitar_drive_adds_saturation():
    clean = generate_guitar_tone(147.0, 0.5, 0.8, drive=0.05)
    crunch = generate_guitar_tone(147.0, 0.5, 0.8, drive=0.95)
    _assert_render_invariants(clean)
    _assert_render_invariants(crunch)
    # Both normalize to the same peak, so heavier saturation shows up as a
    # denser, more compressed waveform (higher RMS / lower crest factor).
    clean_rms = float(np.sqrt(np.mean(clean.astype(np.float64) ** 2)))
    crunch_rms = float(np.sqrt(np.mean(crunch.astype(np.float64) ** 2)))
    assert crunch_rms > clean_rms
    assert not np.array_equal(clean, crunch)


def test_guitar_peak_scales_with_velocity():
    soft = generate_guitar_tone(220.0, 0.5, 0.3)
    loud = generate_guitar_tone(220.0, 0.5, 0.9)
    assert np.max(np.abs(loud)) > np.max(np.abs(soft))


# --- piano (PR 3) -------------------------------------------------------------

def test_piano_is_deterministic():
    a = generate_piano_tone(261.63, 0.6, 0.8)
    b = generate_piano_tone(261.63, 0.6, 0.8)
    assert np.array_equal(a, b)


def test_piano_is_finite_and_bounded():
    audio = generate_piano_tone(261.63, 0.6, 0.8)
    _assert_render_invariants(audio)


def test_piano_velocity_increases_brightness():
    soft = generate_piano_tone(261.63, 0.6, 0.25)
    loud = generate_piano_tone(261.63, 0.6, 0.95)
    _assert_render_invariants(soft)
    _assert_render_invariants(loud)
    # Harder strikes open the filter and hit the hammer harder -> brighter.
    assert _hf_ratio(loud) > _hf_ratio(soft)


# --- brass (PR 5) -------------------------------------------------------------

def test_brass_is_deterministic():
    a = generate_brass_tone(220.0, 0.5, 0.8)
    b = generate_brass_tone(220.0, 0.5, 0.8)
    assert np.array_equal(a, b)


def test_brass_zero_duration_is_empty():
    zero = generate_brass_tone(220.0, 0.0, 0.8)
    assert zero.size == 0


def test_brass_is_finite_and_bounded():
    audio = generate_brass_tone(220.0, 0.5, 0.8)
    _assert_render_invariants(audio)


def test_brass_velocity_increases_brightness():
    soft = generate_brass_tone(220.0, 0.5, 0.25)
    loud = generate_brass_tone(220.0, 0.5, 0.95)
    _assert_render_invariants(soft)
    _assert_render_invariants(loud)
    # The signature brass cue: louder playing blooms far more upper harmonics.
    assert _hf_ratio(loud) > _hf_ratio(soft)


# --- bass (PR 4) --------------------------------------------------------------

def test_bass_is_deterministic():
    a = generate_bass_tone(55.0, 0.5, 0.8)
    b = generate_bass_tone(55.0, 0.5, 0.8)
    assert np.array_equal(a, b)


def test_bass_zero_duration_is_empty():
    zero = generate_bass_tone(55.0, 0.0, 0.8)
    assert zero.size == 0


def test_bass_is_finite_and_bounded():
    audio = generate_bass_tone(55.0, 0.5, 0.8)
    _assert_render_invariants(audio)


def _band_power(audio: np.ndarray, low_hz: float, high_hz: float, sample_rate: int = SAMPLE_RATE) -> float:
    audio = np.asarray(audio, dtype=np.float64)
    if audio.size == 0:
        return 0.0
    power = np.abs(np.fft.rfft(audio)) ** 2
    freqs = np.fft.rfftfreq(audio.size, d=1.0 / sample_rate)
    mask = (freqs >= low_hz) & (freqs < high_hz)
    return float(np.sum(power[mask]))


def test_bass_has_strong_low_end():
    audio = generate_bass_tone(55.0, 0.5, 0.85)
    _assert_render_invariants(audio)
    # A bass note should concentrate its energy in the low band.
    low = _band_power(audio, 0.0, 300.0)
    high = _band_power(audio, 300.0, SAMPLE_RATE / 2.0)
    assert low > high


def test_bass_velocity_increases_brightness():
    soft = generate_bass_tone(55.0, 0.5, 0.25)
    loud = generate_bass_tone(55.0, 0.5, 0.95)
    assert _hf_ratio(loud, cutoff_hz=800.0) > _hf_ratio(soft, cutoff_hz=800.0)


# --- InstrumentPatch -> DSP consumption (loop closure) ------------------------

_ENGINE_FAMILY = [
    (generate_guitar_tone, "guitar", dict(frequency=196.0, duration=0.4, velocity=0.75, drive=0.5)),
    (generate_piano_tone, "keys", dict(frequency=261.63, duration=0.6, velocity=0.8)),
    (generate_bass_tone, "bass", dict(frequency=55.0, duration=0.5, velocity=0.8)),
    (generate_brass_tone, "brass", dict(frequency=220.0, duration=0.5, velocity=0.8)),
]


def _registry_voice(family: str):
    from multimodal_gen.instrument_patch import get_instrument_patch

    patch = get_instrument_patch(family)
    assert patch is not None and patch.synthesis_voice is not None
    return patch.synthesis_voice


def test_registry_voice_is_behavior_preserving():
    # The registry filter-envelope / velocity-map values equal the engine
    # defaults, so consuming the model must reproduce the default sound exactly.
    for fn, family, kw in _ENGINE_FAMILY:
        default = fn(**kw)
        via_patch = fn(**kw, voice=_registry_voice(family))
        assert np.array_equal(default, via_patch), family


def test_custom_voice_changes_realization():
    # A patch with a different filter envelope / velocity map must change the
    # rendered output, proving the engines actually consume the model.
    from multimodal_gen.instrument_patch import SynthesisVoice, EnvelopeSpec, VelocityMap

    neutral = SynthesisVoice(
        filter_envelope=EnvelopeSpec(attack_ms=0.0, decay_ms=10.0, sustain_level=0.0, release_ms=10.0, amount=0.0),
        velocity_map=VelocityMap(amp=1.0, cutoff_delta_hz=0.0, transient_level=0.0, noise_level=0.0),
    )
    for fn, family, kw in _ENGINE_FAMILY:
        default = fn(**kw)
        altered = fn(**kw, voice=neutral)
        _assert_render_invariants(altered)
        assert not np.array_equal(default, altered), family


def test_registry_patches_expose_filter_envelope_for_upgraded_families():
    for family in ("guitar", "keys", "bass", "brass"):
        voice = _registry_voice(family)
        assert voice.filter_envelope is not None, family
        assert voice.filter_envelope.amount > 0.0, family


# --- short-note robustness across engines -------------------------------------

def test_upgraded_engines_short_notes_are_valid_float32():
    for fn, _family, kw in _ENGINE_FAMILY:
        short = dict(kw)
        short["duration"] = 0.002  # ~88 samples at 44.1k
        audio = fn(**short)
        _assert_render_invariants(audio)
