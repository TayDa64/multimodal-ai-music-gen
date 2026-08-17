"""Focused regressions for the shared natural-instrument DSP foundation.

These cover the PR 1 helpers that back the mainstream physical-modeling
upgrades (guitar/bass/piano/brass): seeded determinism, velocity mapping,
filter envelopes (brighter attack than sustain), and dispersion. They assert
behavior, not exact sample values, so they stay robust while remaining strict
about the properties that matter for natural realism.
"""

import numpy as np
import pytest

from multimodal_gen.assets_gen import (
    SAMPLE_RATE,
    _dispersion_allpass,
    _seeded_rng,
    apply_envelope,
    apply_filter_envelope,
    apply_velocity_map,
    resolve_filter_envelope_params,
)


def _hf_ratio(audio: np.ndarray, cutoff_hz: float = 2500.0, sample_rate: int = SAMPLE_RATE) -> float:
    """Fraction of spectral magnitude above ``cutoff_hz`` (a brightness proxy)."""
    audio = np.asarray(audio, dtype=np.float64)
    if audio.size == 0:
        return 0.0
    spectrum = np.abs(np.fft.rfft(audio))
    freqs = np.fft.rfftfreq(audio.size, d=1.0 / sample_rate)
    total = float(np.sum(spectrum))
    if total <= 0.0:
        return 0.0
    return float(np.sum(spectrum[freqs > cutoff_hz]) / total)


# --- _seeded_rng --------------------------------------------------------------

def test_seeded_rng_is_deterministic_for_same_keys():
    a = _seeded_rng(440.0, 0.5).standard_normal(256)
    b = _seeded_rng(440.0, 0.5).standard_normal(256)
    assert np.array_equal(a, b)


def test_seeded_rng_differs_for_different_keys():
    a = _seeded_rng(440.0, 0.5).standard_normal(256)
    b = _seeded_rng(441.0, 0.5).standard_normal(256)
    assert not np.array_equal(a, b)


def test_seeded_rng_ignores_global_seed_state():
    np.random.seed(1)
    a = _seeded_rng(220.0, 1.0).standard_normal(128)
    np.random.seed(999999)
    b = _seeded_rng(220.0, 1.0).standard_normal(128)
    assert np.array_equal(a, b)


# --- apply_velocity_map -------------------------------------------------------

def test_velocity_map_scales_monotonically():
    soft = apply_velocity_map(0.2, cutoff_delta_hz=1000.0, transient_level=0.5, noise_level=0.3)
    loud = apply_velocity_map(0.9, cutoff_delta_hz=1000.0, transient_level=0.5, noise_level=0.3)
    for key in ("amp", "cutoff_delta_hz", "transient_level", "noise_level"):
        assert loud[key] > soft[key]


def test_velocity_map_clips_and_reads_object():
    class _VMap:
        amp = 1.0
        cutoff_delta_hz = 500.0
        transient_level = 0.4
        noise_level = 0.2

    result = apply_velocity_map(2.0, _VMap())  # velocity above 1.0 clips
    assert result["velocity"] == 1.0
    assert result["cutoff_delta_hz"] == pytest.approx(500.0)
    assert result["transient_level"] == pytest.approx(0.4)


def test_velocity_map_zero_velocity_is_silent_contribution():
    result = apply_velocity_map(0.0, cutoff_delta_hz=1000.0, transient_level=1.0, noise_level=1.0)
    assert result["amp"] == 0.0
    assert result["cutoff_delta_hz"] == 0.0
    assert result["transient_level"] == 0.0
    assert result["noise_level"] == 0.0


# --- apply_filter_envelope ----------------------------------------------------

def _bright_source(duration: float = 0.5) -> np.ndarray:
    n = int(duration * SAMPLE_RATE)
    t = np.arange(n) / SAMPLE_RATE
    # Harmonic-rich source so a moving low-pass has content to sculpt.
    return sum(np.sin(2 * np.pi * 220.0 * k * t) / k for k in range(1, 20)).astype(np.float64)


def test_filter_envelope_attack_is_brighter_than_sustain():
    src = _bright_source(0.6)
    out = apply_filter_envelope(
        src,
        base_cutoff_hz=400.0,
        attack_ms=3.0,
        decay_ms=200.0,
        sustain_level=0.1,
        release_ms=100.0,
        amount_hz=6000.0,
    )
    # Skip the filter's cold-start ramp so the comparison reflects the cutoff
    # contour, not the onset transient's low-frequency bias.
    settle = int(0.004 * SAMPLE_RATE)
    window = int(0.02 * SAMPLE_RATE)
    attack_hf = _hf_ratio(out[settle:settle + window])
    sustain_hf = _hf_ratio(out[len(out) // 2:len(out) // 2 + window])
    assert attack_hf > sustain_hf


def test_filter_envelope_zero_amount_matches_static_lowpass():
    from multimodal_gen.assets_gen import lowpass_filter

    src = _bright_source(0.2)
    moving = apply_filter_envelope(src, base_cutoff_hz=1500.0, amount_hz=0.0)
    static = lowpass_filter(src, 1500.0, SAMPLE_RATE)
    assert np.allclose(moving, static, atol=1e-9)


def test_filter_envelope_preserves_length_and_is_finite():
    src = _bright_source(0.1)
    out = apply_filter_envelope(src, base_cutoff_hz=1000.0, amount_hz=2000.0)
    assert out.shape[0] == src.shape[0]
    assert np.all(np.isfinite(out))


def test_filter_envelope_handles_empty_input():
    out = apply_filter_envelope(np.zeros(0), base_cutoff_hz=1000.0, amount_hz=2000.0)
    assert out.shape[0] == 0


def test_filter_envelope_short_notes_are_finite_and_click_safe():
    # Very short notes (1..64 samples) must stay finite, length-preserving, and
    # bounded (no cold-start blow-up) even with a large modulation amount.
    src_full = _bright_source(0.5)
    for n in (1, 2, 3, 8, 32, 64):
        out = apply_filter_envelope(
            src_full[:n],
            base_cutoff_hz=600.0,
            attack_ms=5.0,
            decay_ms=40.0,
            sustain_level=0.2,
            release_ms=40.0,
            amount_hz=6000.0,
        )
        assert out.shape[0] == n
        assert np.all(np.isfinite(out))
        assert np.max(np.abs(out)) <= np.max(np.abs(src_full[:n])) + 1e-6


def test_filter_envelope_extreme_params_stay_finite():
    src = _bright_source(0.05)
    # Base above Nyquist, negative amount, tiny release: must not raise or NaN.
    out = apply_filter_envelope(
        src,
        base_cutoff_hz=1_000_000.0,
        attack_ms=0.0,
        decay_ms=0.0,
        sustain_level=2.0,
        release_ms=0.0,
        amount_hz=-9000.0,
    )
    assert out.shape[0] == src.shape[0]
    assert np.all(np.isfinite(out))


# --- resolve_filter_envelope_params -------------------------------------------

def test_resolve_filter_envelope_uses_defaults_when_no_voice():
    params = resolve_filter_envelope_params(
        None, attack_ms=2.0, decay_ms=140.0, sustain_level=0.5, release_ms=120.0, amount_hz=2200.0
    )
    assert params == {
        "attack_ms": 2.0,
        "decay_ms": 140.0,
        "sustain_level": 0.5,
        "release_ms": 120.0,
        "amount_hz": 2200.0,
    }


def test_resolve_filter_envelope_reads_voice_filter_envelope():
    from multimodal_gen.instrument_patch import SynthesisVoice, EnvelopeSpec

    voice = SynthesisVoice(
        filter_envelope=EnvelopeSpec(attack_ms=9.0, decay_ms=99.0, sustain_level=0.1, release_ms=33.0, amount=1234.0)
    )
    params = resolve_filter_envelope_params(
        voice, attack_ms=2.0, decay_ms=140.0, sustain_level=0.5, release_ms=120.0, amount_hz=2200.0
    )
    assert params["attack_ms"] == 9.0
    assert params["decay_ms"] == 99.0
    assert params["sustain_level"] == 0.1
    assert params["release_ms"] == 33.0
    assert params["amount_hz"] == 1234.0  # EnvelopeSpec.amount maps to amount_hz


def test_resolve_filter_envelope_defaults_when_voice_has_no_filter_envelope():
    from multimodal_gen.instrument_patch import SynthesisVoice

    voice = SynthesisVoice()  # filter_envelope is None by default
    params = resolve_filter_envelope_params(
        voice, attack_ms=2.0, decay_ms=140.0, sustain_level=0.5, release_ms=120.0, amount_hz=2200.0
    )
    assert params["amount_hz"] == 2200.0


# --- apply_envelope short-note release -----------------------------------------

def test_apply_envelope_short_note_fades_to_zero():
    # A note far shorter than attack+decay must still fade to near zero at the
    # end (no mid-amplitude truncation click).
    n = 2000
    audio = np.ones(n)
    out = apply_envelope(audio, attack_samples=200, decay_samples=4000,
                         sustain_level=0.5, release_samples=5000, sustain_samples=0)
    assert out.shape[0] == n
    assert np.all(np.isfinite(out))
    assert abs(out[-1]) < 0.02
    assert float(np.mean(np.abs(out[-30:]))) < 0.05


def test_apply_envelope_normal_note_preserves_sustain_and_fades():
    n = 20000
    a, d, r = 200, 800, 1000
    audio = np.ones(n)
    out = apply_envelope(audio, a, d, sustain_level=0.5,
                         release_samples=r, sustain_samples=n - a - d - r)
    # Sustain region is not compressed: it sits at sustain_level.
    assert out[a + d + 100] == pytest.approx(0.5, abs=1e-6)
    # And the note still fades to zero at the end.
    assert abs(out[-1]) < 1e-6


def test_apply_envelope_extreme_short_notes_finite_bounded():
    for n in (1, 2, 3, 8, 16):
        out = apply_envelope(np.ones(n), attack_samples=200, decay_samples=4000,
                             sustain_level=0.5, release_samples=5000, sustain_samples=0)
        assert out.shape[0] == n
        assert np.all(np.isfinite(out))
        assert np.max(np.abs(out)) <= 1.0 + 1e-9


def test_apply_envelope_empty_input():
    out = apply_envelope(np.zeros(0), 100, 100, 0.5, 100, 0)
    assert out.shape[0] == 0


# --- _dispersion_allpass ------------------------------------------------------

def test_dispersion_preserves_length_and_is_finite():
    src = _bright_source(0.1)
    out = _dispersion_allpass(src, coefficient=0.5, stages=3)
    assert out.shape[0] == src.shape[0]
    assert np.all(np.isfinite(out))


def test_dispersion_is_deterministic():
    src = _bright_source(0.05)
    a = _dispersion_allpass(src, coefficient=0.4, stages=2)
    b = _dispersion_allpass(src, coefficient=0.4, stages=2)
    assert np.array_equal(a, b)


def test_dispersion_zero_stages_is_passthrough():
    src = _bright_source(0.05)
    out = _dispersion_allpass(src, coefficient=0.4, stages=0)
    assert np.allclose(out, src)


def test_dispersion_shifts_phase_without_destroying_energy():
    src = _bright_source(0.1)
    out = _dispersion_allpass(src, coefficient=0.6, stages=2)
    # Allpass sections preserve overall energy while altering phase/dispersion.
    assert np.sum(out ** 2) == pytest.approx(np.sum(src ** 2), rel=0.05)
    assert not np.allclose(out, src)
