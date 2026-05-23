from pathlib import Path

import numpy as np

from multimodal_gen.assets_gen import (
    AssetsGenerator,
    SAMPLE_RATE,
    generate_organ_tone,
    get_static_wavetable_bank,
    render_static_wavetable_tone,
    generate_unison_lead_tone,
)


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


def test_generate_drum_kit_perc_request_writes_shaker_sample(tmp_path):
    generator = AssetsGenerator(str(tmp_path))

    kit = generator.generate_drum_kit(['perc'])

    assert list(kit) == ['shaker']
    assert _sample_names(kit) == {'shaker.wav'}
    assert (tmp_path / 'shaker.wav').exists()
    assert not (tmp_path / 'kick.wav').exists()


def test_generate_drum_kit_kebero_request_writes_hand_drum_samples(tmp_path):
    generator = AssetsGenerator(str(tmp_path))

    kit = generator.generate_drum_kit(['kebero'])

    assert list(kit) == ['kebero_bass', 'kebero_slap']
    assert _sample_names(kit) == {'kebero_bass.wav', 'kebero_slap.wav'}


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


def test_generate_unison_lead_tone_non_empty_and_finite():
    audio = generate_unison_lead_tone(440.0, duration=0.10, velocity=0.9, sample_rate=SAMPLE_RATE)

    assert isinstance(audio, np.ndarray)
    assert audio.size == int(0.10 * SAMPLE_RATE)
    assert np.all(np.isfinite(audio))
    peak = float(np.max(np.abs(audio))) if audio.size else 0.0
    assert peak <= 1.0 + 1e-6


def test_generate_unison_lead_tone_table_controls_change_output_while_remaining_bounded():
    square_like = generate_unison_lead_tone(
        440.0,
        duration=0.05,
        velocity=0.9,
        sample_rate=SAMPLE_RATE,
        table_position=0.88,
        table_motion=0.10,
    )
    saw_like = generate_unison_lead_tone(
        440.0,
        duration=0.05,
        velocity=0.9,
        sample_rate=SAMPLE_RATE,
        table_position=0.64,
        table_motion=0.70,
    )
    static_vs_moving = generate_unison_lead_tone(
        440.0,
        duration=0.05,
        velocity=0.9,
        sample_rate=SAMPLE_RATE,
        table_position=0.64,
        table_motion=0.0,
    )

    for audio in (square_like, saw_like, static_vs_moving):
        assert audio.size == int(0.05 * SAMPLE_RATE)
        assert np.all(np.isfinite(audio))
        assert float(np.max(np.abs(audio))) <= 1.0 + 1e-6

    assert not np.allclose(square_like, saw_like)
    assert not np.allclose(static_vs_moving, saw_like)


def test_static_wavetable_bank_exposes_multiple_single_cycle_tables():
    names, tables = get_static_wavetable_bank(512)

    assert names == ("sine", "triangle", "soft_saw", "hollow_square")
    assert tables.shape == (4, 512)
    assert np.all(np.isfinite(tables))
    assert np.max(np.abs(tables)) <= 1.0 + 1e-6


def test_render_static_wavetable_tone_morphing_is_finite_and_changes_shape():
    mellow = render_static_wavetable_tone(
        440.0,
        duration=0.05,
        sample_rate=SAMPLE_RATE,
        morph_position=0.0,
    )
    bright = render_static_wavetable_tone(
        440.0,
        duration=0.05,
        sample_rate=SAMPLE_RATE,
        morph_position=1.0,
        morph_span=0.25,
    )

    assert mellow.size == bright.size == int(0.05 * SAMPLE_RATE)
    assert np.all(np.isfinite(mellow))
    assert np.all(np.isfinite(bright))
    assert np.max(np.abs(bright)) <= 1.0 + 1e-6
    assert not np.allclose(mellow, bright)
