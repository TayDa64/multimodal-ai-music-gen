import numpy as np

from multimodal_gen.assets_gen import SAMPLE_RATE, generate_organ_tone


def test_generate_organ_tone_short_note_does_not_crash():
    audio = generate_organ_tone(440, duration=0.001, velocity=0.8)

    assert isinstance(audio, np.ndarray)
    assert len(audio) == int(0.001 * SAMPLE_RATE)
    assert not np.isnan(audio).any()


def test_generate_organ_tone_zero_duration_returns_empty_audio():
    audio = generate_organ_tone(440, duration=0.0, velocity=0.8)

    assert isinstance(audio, np.ndarray)
    assert len(audio) == 0


def test_generate_organ_tone_normal_duration_non_empty():
    audio = generate_organ_tone(440, duration=0.05, velocity=0.8)

    assert len(audio) == int(0.05 * SAMPLE_RATE)
    assert not np.isnan(audio).any()
    assert np.max(np.abs(audio)) > 0
