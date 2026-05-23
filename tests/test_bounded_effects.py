import numpy as np

from multimodal_gen.audio_renderer import ProceduralRenderer, SynthNote
from multimodal_gen.mix_chain import DSP, WowFlutterParams


def test_wow_flutter_effect_preserves_shape_and_finiteness():
    sr = 44100
    duration = 0.25
    n = int(sr * duration)
    t = np.arange(n, dtype=np.float32) / sr
    audio = 0.3 * np.sin(2.0 * np.pi * 440.0 * t)

    params = WowFlutterParams(wow_rate_hz=0.4, wow_depth_ms=3.0, flutter_rate_hz=6.0, flutter_depth_ms=0.4, mix=1.0)
    processed = DSP.wow_flutter(audio, params, sr)

    assert isinstance(processed, np.ndarray)
    assert processed.shape == audio.shape
    assert np.all(np.isfinite(processed))


def test_rock_guitar_physical_model_path_is_finite_and_bounded():
    sr = 44100
    renderer = ProceduralRenderer(sample_rate=sr, genre="rock")

    note = SynthNote(
        pitch=64,
        start_sample=0,
        duration_samples=int(0.15 * sr),
        velocity=0.85,
        channel=2,
        program=30,  # distortion guitar
    )

    audio = renderer._synthesize_note(note)
    assert isinstance(audio, np.ndarray)
    assert audio.size == note.duration_samples
    assert np.all(np.isfinite(audio))
    assert float(np.max(np.abs(audio))) <= 1.0 + 1e-6


def test_orchestral_program_uses_expansion_cache_when_available():
    sr = 44100
    renderer = ProceduralRenderer(sample_rate=sr, genre="cinematic")

    # Simulate one cached expansion sample for strings.
    renderer._expansion_sample_cache["strings"] = np.ones(int(0.20 * sr), dtype=np.float32) * 0.1

    audio = renderer._get_expansion_sample_for_program(
        program=40,  # GM strings range
        freq=440.0,
        duration=0.20,
        velocity=0.8,
    )

    assert isinstance(audio, np.ndarray)
    assert audio.size == int(0.20 * sr)
    assert np.all(np.isfinite(audio))
