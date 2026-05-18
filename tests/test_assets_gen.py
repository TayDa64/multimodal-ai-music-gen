from pathlib import Path

import numpy as np

from multimodal_gen.assets_gen import AssetsGenerator, SAMPLE_RATE, generate_organ_tone


def _sample_names(kit):
    return {Path(path).name for path in kit.values()}


def test_generate_drum_kit_no_arg_preserves_legacy_full_kit(tmp_path):
    generator = AssetsGenerator(str(tmp_path))

    kit = generator.generate_drum_kit()

    assert list(kit) == ['808', 'kick', 'snare', 'clap', 'hihat', 'hihat_open', 'rim']
    assert _sample_names(kit) == {
        '808_kick.wav',
        'kick.wav',
        'snare.wav',
        'clap.wav',
        'hihat_closed.wav',
        'hihat_open.wav',
        'rim.wav',
    }
    assert all(tmp_path.joinpath(name).exists() for name in _sample_names(kit))


def test_generate_drum_kit_rock_filter_excludes_808_and_clap(tmp_path):
    generator = AssetsGenerator(str(tmp_path))

    kit = generator.generate_drum_kit([
        'kick',
        'snare',
        'hihat',
        'hihat_open',
        'crash',
        'ride',
        'tom',
    ])

    assert list(kit) == ['kick', 'snare', 'hihat', 'hihat_open']
    assert _sample_names(kit) == {'kick.wav', 'snare.wav', 'hihat_closed.wav', 'hihat_open.wav'}
    assert not (tmp_path / '808_kick.wav').exists()
    assert not (tmp_path / 'clap.wav').exists()


def test_generate_drum_kit_trap_request_includes_808_and_clap(tmp_path):
    generator = AssetsGenerator(str(tmp_path))

    kit = generator.generate_drum_kit(['kick', '808', 'snare', 'clap', 'hihat_closed'])

    assert list(kit) == ['808', 'kick', 'snare', 'clap', 'hihat']
    assert '808_kick.wav' in _sample_names(kit)
    assert 'clap.wav' in _sample_names(kit)


def test_texture_instance_wrappers_write_legacy_file_names(tmp_path):
    generator = AssetsGenerator(str(tmp_path))

    vinyl_path = generator.generate_vinyl_crackle(duration=0.05)
    rain_path = generator.generate_rain_texture(duration=0.05)

    assert Path(vinyl_path).name == 'vinyl_crackle.wav'
    assert Path(rain_path).name == 'rain.wav'
    assert Path(vinyl_path).exists()
    assert Path(rain_path).exists()


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
