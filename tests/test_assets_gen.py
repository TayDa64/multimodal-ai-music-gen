import inspect
from pathlib import Path

import numpy as np

from multimodal_gen.assets_gen import (
    AssetsGenerator,
    SAMPLE_RATE,
    generate_begena_tone,
    generate_kebero_hit,
    generate_krar_tone,
    generate_masenqo_tone,
    generate_organ_tone,
    generate_washint_tone,
    get_static_wavetable_bank,
    render_static_wavetable_tone,
    generate_unison_lead_tone,
)


def _sample_names(kit):
    return {Path(path).name for path in kit.values()}


def _generate_seeded_krar(
    profile: str,
    seed: int = 0,
    *,
    frequency: float = 329.63,
    duration: float = 1.0,
    velocity: float = 0.85,
) -> np.ndarray:
    state = np.random.get_state()
    try:
        np.random.seed(seed)
        return generate_krar_tone(
            frequency,
            duration=duration,
            velocity=velocity,
            sample_rate=SAMPLE_RATE,
            profile=profile,
        )
    finally:
        np.random.set_state(state)


def _generate_seeded_masenqo(profile: str, seed: int = 0) -> np.ndarray:
    state = np.random.get_state()
    try:
        np.random.seed(seed)
        return generate_masenqo_tone(
            329.63,
            duration=1.0,
            velocity=0.85,
            sample_rate=SAMPLE_RATE,
            expressiveness=0.8,
            profile=profile,
        )
    finally:
        np.random.set_state(state)


def _generate_seeded_washint(
    profile: str,
    seed: int = 0,
    *,
    frequency: float = 659.25,
    duration: float = 1.0,
    velocity: float = 0.85,
    add_ornament: bool = False,
) -> np.ndarray:
    state = np.random.get_state()
    try:
        np.random.seed(seed)
        return generate_washint_tone(
            frequency,
            duration=duration,
            velocity=velocity,
            sample_rate=SAMPLE_RATE,
            add_ornament=add_ornament,
            profile=profile,
        )
    finally:
        np.random.set_state(state)


def _generate_seeded_begena(
    seed: int = 0,
    *,
    frequency: float = 110.0,
    duration: float = 1.5,
    velocity: float = 0.85,
    profile: str = 'paraliturgical_drone',
    buzzers_enabled: bool = True,
    buzzer_position: float = 0.35,
    string_quality: str = 'stable',
    sustain_bias: float = 0.8,
) -> np.ndarray:
    state = np.random.get_state()
    try:
        np.random.seed(seed)
        return generate_begena_tone(
            frequency,
            duration=duration,
            velocity=velocity,
            sample_rate=SAMPLE_RATE,
            profile=profile,
            buzzers_enabled=buzzers_enabled,
            buzzer_position=buzzer_position,
            string_quality=string_quality,
            sustain_bias=sustain_bias,
        )
    finally:
        np.random.set_state(state)


def _generate_seeded_kebero(
    profile: str,
    pitch: int,
    seed: int = 0,
    *,
    velocity: float = 0.9,
) -> np.ndarray:
    state = np.random.get_state()
    try:
        np.random.seed(seed)
        return generate_kebero_hit(
            pitch=pitch,
            velocity=velocity,
            sample_rate=SAMPLE_RATE,
            profile=profile,
        )
    finally:
        np.random.set_state(state)


def _band_energy_ratio(
    audio: np.ndarray,
    low_hz: float,
    high_hz: float,
    sample_rate: int = SAMPLE_RATE,
) -> float:
    clipped = np.asarray(audio, dtype=np.float64).reshape(-1)
    if clipped.size == 0 or not np.any(clipped):
        return 0.0
    spectrum = np.abs(np.fft.rfft(clipped)) ** 2
    total = float(np.sum(spectrum))
    if total <= 1e-12:
        return 0.0
    freqs = np.fft.rfftfreq(clipped.size, d=1.0 / sample_rate)
    band = (freqs >= low_hz) & (freqs <= high_hz)
    return float(np.sum(spectrum[band]) / total)


def _spectral_flux_metric(
    audio: np.ndarray,
    sample_rate: int = SAMPLE_RATE,
    *,
    frame_size: int = 1024,
    hop_size: int = 256,
) -> float:
    clipped = np.asarray(audio, dtype=np.float64).reshape(-1)
    if clipped.size < frame_size:
        return 0.0
    frames = []
    window = np.hanning(frame_size)
    for start in range(0, clipped.size - frame_size + 1, hop_size):
        spectrum = np.abs(np.fft.rfft(clipped[start:start + frame_size] * window))
        total = float(np.sum(spectrum))
        frames.append(spectrum / max(total, 1e-12))
    if len(frames) < 2:
        return 0.0
    stacked = np.vstack(frames)
    return float(np.mean(np.sqrt(np.sum(np.diff(stacked, axis=0) ** 2, axis=1))))


def _spectral_flatness_metric(audio: np.ndarray, low_hz: float, high_hz: float, sample_rate: int = SAMPLE_RATE) -> float:
    clipped = np.asarray(audio, dtype=np.float64).reshape(-1)
    if clipped.size == 0 or not np.any(clipped):
        return 0.0
    spectrum = np.abs(np.fft.rfft(clipped * np.hanning(clipped.size))) ** 2
    freqs = np.fft.rfftfreq(clipped.size, d=1.0 / sample_rate)
    band = (freqs >= low_hz) & (freqs <= high_hz)
    values = spectrum[band]
    if values.size == 0:
        return 0.0
    values = values + 1e-18
    return float(np.exp(np.mean(np.log(values))) / np.mean(values))


def _kebero_bass_slap_contrast_metric(bass: np.ndarray, slap: np.ndarray) -> float:
    bass_low = _band_energy_ratio(bass, 40.0, 190.0)
    bass_presence = _band_energy_ratio(bass, 900.0, 2600.0)
    slap_low = _band_energy_ratio(slap, 40.0, 190.0)
    slap_presence = _band_energy_ratio(slap, 900.0, 2600.0)
    return (bass_low + slap_presence) - (bass_presence + slap_low)


def _effective_duration_seconds(audio: np.ndarray, sample_rate: int = SAMPLE_RATE) -> float:
    clipped = np.asarray(audio, dtype=np.float64).reshape(-1)
    if clipped.size == 0 or not np.any(clipped):
        return 0.0

    window = max(16, int(0.012 * sample_rate))
    smoothed = np.convolve(np.abs(clipped), np.ones(window) / window, mode='same')
    threshold = float(np.max(smoothed)) * 0.08
    active = np.flatnonzero(smoothed >= threshold)
    if active.size == 0:
        return 0.0
    return float((active[-1] + 1) / sample_rate)


def _tail_rms(audio: np.ndarray, start_ratio: float = 0.70) -> float:
    clipped = np.asarray(audio, dtype=np.float64).reshape(-1)
    if clipped.size == 0:
        return 0.0

    start = int(np.clip(start_ratio, 0.0, 0.99) * clipped.size)
    tail = clipped[start:]
    if tail.size == 0:
        return 0.0
    return float(np.sqrt(np.mean(tail ** 2)))


def _slice_audio(audio: np.ndarray, start_ratio: float, end_ratio: float) -> np.ndarray:
    clipped = np.asarray(audio, dtype=np.float64).reshape(-1)
    if clipped.size == 0:
        return np.zeros(0, dtype=np.float64)

    start = int(np.clip(start_ratio, 0.0, 1.0) * clipped.size)
    end = int(np.clip(end_ratio, 0.0, 1.0) * clipped.size)
    if end <= start:
        return np.zeros(0, dtype=np.float64)
    return clipped[start:end]


def _window_rms(audio: np.ndarray, start_ratio: float, end_ratio: float) -> float:
    window = _slice_audio(audio, start_ratio, end_ratio)
    if window.size == 0:
        return 0.0
    return float(np.sqrt(np.mean(window ** 2)))


def _windowed_band_metric(
    audio: np.ndarray,
    start_ratio: float,
    end_ratio: float,
    low_hz: float,
    high_hz: float,
) -> float:
    window = _slice_audio(audio, start_ratio, end_ratio)
    if window.size == 0:
        return 0.0
    return _window_rms(window, 0.0, 1.0) * _band_energy_ratio(window, low_hz, high_hz)


def _safe_ratio(numerator: float, denominator: float) -> float:
    return float(numerator / max(denominator, 1e-9))


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


def test_generate_krar_tone_profiles_remain_finite_and_bounded():
    warm = _generate_seeded_krar('traditional_warm', seed=7)
    bright = _generate_seeded_krar('azmari_bright', seed=7)

    assert warm.size == bright.size == int(1.0 * SAMPLE_RATE)
    for audio in (warm, bright):
        assert np.all(np.isfinite(audio))
        assert float(np.max(np.abs(audio))) <= 1.0 + 1e-6

    assert not np.allclose(warm, bright)


def test_generate_krar_tone_azmari_profile_has_stronger_attack_and_upper_mid_energy_than_warm_profile():
    warm = _generate_seeded_krar('traditional_warm', seed=11)
    bright = _generate_seeded_krar('azmari_bright', seed=11)

    warm_upper_mid = _band_energy_ratio(warm, 1800.0, 4500.0)
    bright_upper_mid = _band_energy_ratio(bright, 1800.0, 4500.0)
    warm_attack_upper_mid = _band_energy_ratio(warm[: int(0.05 * SAMPLE_RATE)], 1800.0, 4500.0)
    bright_attack_upper_mid = _band_energy_ratio(bright[: int(0.05 * SAMPLE_RATE)], 1800.0, 4500.0)

    assert bright_upper_mid > warm_upper_mid * 1.20
    assert bright_attack_upper_mid > warm_attack_upper_mid * 1.40


def test_generate_krar_tone_keeps_delayed_body_and_sympathetic_support_after_the_initial_pluck():
    warm = _generate_seeded_krar('traditional_warm', seed=73)
    bright = _generate_seeded_krar('azmari_bright', seed=73)

    warm_delayed_support = _windowed_band_metric(warm, 0.10, 0.55, 180.0, 1800.0)
    bright_delayed_support = _windowed_band_metric(bright, 0.10, 0.55, 180.0, 1800.0)
    warm_early_body = _windowed_band_metric(warm, 0.00, 0.05, 180.0, 1800.0)
    bright_early_body = _windowed_band_metric(bright, 0.00, 0.05, 180.0, 1800.0)
    warm_attack_brittle = _windowed_band_metric(warm, 0.00, 0.05, 2500.0, 7500.0)
    bright_attack_brittle = _windowed_band_metric(bright, 0.00, 0.05, 2500.0, 7500.0)

    assert warm_delayed_support > warm_attack_brittle * 0.85
    assert bright_delayed_support > bright_attack_brittle * 0.55
    assert warm_delayed_support > warm_early_body * 0.72
    assert bright_delayed_support > bright_early_body * 0.55


def test_generate_krar_tone_lower_register_has_body_contact_flux_without_brittle_highs():
    low = _generate_seeded_krar('traditional_warm', seed=129, frequency=82.41, duration=1.2, velocity=0.86)

    low_body = _band_energy_ratio(low, 55.0, 520.0)
    mid_body = _band_energy_ratio(low, 520.0, 1800.0)
    contact_presence = _band_energy_ratio(low[: int(0.11 * SAMPLE_RATE)], 850.0, 2600.0)
    brittle_highs = _band_energy_ratio(low, 4200.0, 9000.0)
    flux = _spectral_flux_metric(low)

    assert low_body > 0.18
    assert low_body + mid_body > brittle_highs * 55.0
    assert contact_presence > 0.0025
    assert 0.004 <= flux <= 0.24
    assert brittle_highs < 0.010


def test_generate_kebero_profiles_remain_finite_and_bounded():
    audio_examples = [
        _generate_seeded_kebero('eskista_dance', pitch=50, seed=23),
        _generate_seeded_kebero('traditional_ceremony', pitch=50, seed=23),
        _generate_seeded_kebero('ethio_jazz_hybrid', pitch=50, seed=23),
        _generate_seeded_kebero('eskista_dance', pitch=51, seed=29),
        _generate_seeded_kebero('traditional_ceremony', pitch=51, seed=29),
        _generate_seeded_kebero('ethio_jazz_hybrid', pitch=51, seed=29),
    ]

    assert all(audio.size == int(0.4 * SAMPLE_RATE) for audio in audio_examples)
    for audio in audio_examples:
        assert np.all(np.isfinite(audio))
        assert float(np.max(np.abs(audio))) <= 1.0 + 1e-6

    assert not np.allclose(audio_examples[0], audio_examples[1])
    assert not np.allclose(audio_examples[1], audio_examples[2])


def test_generate_kebero_eskista_profile_has_stronger_bass_slap_contrast_than_traditional_profile():
    eskista_bass = _generate_seeded_kebero('eskista_dance', pitch=50, seed=31)
    eskista_slap = _generate_seeded_kebero('eskista_dance', pitch=51, seed=31)
    traditional_bass = _generate_seeded_kebero('traditional_ceremony', pitch=50, seed=31)
    traditional_slap = _generate_seeded_kebero('traditional_ceremony', pitch=51, seed=31)
    hybrid_bass = _generate_seeded_kebero('ethio_jazz_hybrid', pitch=50, seed=31)
    hybrid_slap = _generate_seeded_kebero('ethio_jazz_hybrid', pitch=51, seed=31)

    eskista_contrast = _kebero_bass_slap_contrast_metric(eskista_bass, eskista_slap)
    traditional_contrast = _kebero_bass_slap_contrast_metric(traditional_bass, traditional_slap)
    hybrid_contrast = _kebero_bass_slap_contrast_metric(hybrid_bass, hybrid_slap)

    assert eskista_contrast > traditional_contrast + 0.08
    assert traditional_contrast < hybrid_contrast < eskista_contrast


def test_generate_masenqo_tone_profiles_remain_finite_and_bounded():
    clean = _generate_seeded_masenqo('vocal_clean', seed=13)
    grit = _generate_seeded_masenqo('azmari_grit', seed=13)
    mp3_bow = _generate_seeded_masenqo('mp3_reference_bow', seed=13)

    assert clean.size == grit.size == mp3_bow.size == int(1.0 * SAMPLE_RATE)
    for audio in (clean, grit, mp3_bow):
        assert np.all(np.isfinite(audio))
        assert float(np.max(np.abs(audio))) <= 1.0 + 1e-6

    assert not np.allclose(clean, grit)
    assert not np.allclose(clean, mp3_bow)


def test_generate_masenqo_tone_mp3_reference_bow_has_more_rosin_noise_than_vocal_clean_with_body_control():
    clean = _generate_seeded_masenqo('vocal_clean', seed=12901)
    mp3_bow = _generate_seeded_masenqo('mp3_reference_bow', seed=12901)

    clean_high_mid = _band_energy_ratio(clean, 2000.0, 6000.0)
    mp3_high_mid = _band_energy_ratio(mp3_bow, 2000.0, 6000.0)
    clean_high = _band_energy_ratio(clean, 6000.0, 10000.0)
    mp3_high = _band_energy_ratio(mp3_bow, 6000.0, 10000.0)
    clean_flatness = _spectral_flatness_metric(clean, 1800.0, 9000.0)
    mp3_flatness = _spectral_flatness_metric(mp3_bow, 1800.0, 9000.0)
    mp3_body = _band_energy_ratio(mp3_bow, 220.0, 1800.0)

    assert mp3_high_mid > clean_high_mid * 1.85
    assert mp3_high > max(clean_high * 2.4, 0.000010)
    assert mp3_flatness > clean_flatness * 1.35
    assert mp3_body > mp3_high_mid * 2.5
    assert mp3_high < 0.045


def test_generate_masenqo_tone_azmari_grit_has_more_presence_and_noise_band_than_vocal_clean():
    clean = _generate_seeded_masenqo('vocal_clean', seed=19)
    grit = _generate_seeded_masenqo('azmari_grit', seed=19)

    clean_presence = _band_energy_ratio(clean, 1800.0, 4200.0)
    grit_presence = _band_energy_ratio(grit, 1800.0, 4200.0)
    clean_attack_presence = _band_energy_ratio(clean[: int(0.06 * SAMPLE_RATE)], 2200.0, 5200.0)
    grit_attack_presence = _band_energy_ratio(grit[: int(0.06 * SAMPLE_RATE)], 2200.0, 5200.0)
    clean_noise_band = _band_energy_ratio(clean, 4200.0, 9000.0)
    grit_noise_band = _band_energy_ratio(grit, 4200.0, 9000.0)

    assert grit_presence > clean_presence * 1.05
    assert grit_attack_presence > clean_attack_presence * 1.18
    assert grit_noise_band > clean_noise_band * 1.20


def test_generate_masenqo_tone_vocal_clean_keeps_bounded_bow_friction_floor_below_grit():
    clean = _generate_seeded_masenqo('vocal_clean', seed=129)
    grit = _generate_seeded_masenqo('azmari_grit', seed=129)

    clean_high_mid = _band_energy_ratio(clean, 2200.0, 5200.0)
    grit_high_mid = _band_energy_ratio(grit, 2200.0, 5200.0)
    clean_noise = _band_energy_ratio(clean, 4200.0, 9000.0)
    grit_noise = _band_energy_ratio(grit, 4200.0, 9000.0)
    clean_flatness = _spectral_flatness_metric(clean, 1800.0, 5600.0)
    grit_flatness = _spectral_flatness_metric(grit, 1800.0, 5600.0)

    assert clean_high_mid > 0.00045
    assert 0.000001 < clean_flatness < 0.15
    assert grit_high_mid > clean_high_mid * 1.08
    assert grit_noise > clean_noise * 1.18
    assert grit_flatness >= clean_flatness * 0.85


def test_generate_masenqo_tone_transitions_from_attack_scrape_to_sustained_vocal_body_balance():
    clean = _generate_seeded_masenqo('vocal_clean', seed=79)
    grit = _generate_seeded_masenqo('azmari_grit', seed=79)

    clean_attack_scrape = _windowed_band_metric(clean, 0.00, 0.08, 2200.0, 5200.0)
    clean_attack_vocal = _windowed_band_metric(clean, 0.00, 0.08, 320.0, 1800.0)
    clean_sustain_scrape = _windowed_band_metric(clean, 0.18, 0.60, 2200.0, 5200.0)
    clean_sustain_vocal = _windowed_band_metric(clean, 0.18, 0.60, 320.0, 1800.0)

    grit_attack_scrape = _windowed_band_metric(grit, 0.00, 0.08, 2200.0, 5200.0)
    grit_attack_vocal = _windowed_band_metric(grit, 0.00, 0.08, 320.0, 1800.0)
    grit_sustain_scrape = _windowed_band_metric(grit, 0.18, 0.60, 2200.0, 5200.0)
    grit_sustain_vocal = _windowed_band_metric(grit, 0.18, 0.60, 320.0, 1800.0)

    clean_attack_scrape_balance = _safe_ratio(clean_attack_scrape, clean_attack_vocal)
    clean_sustain_scrape_balance = _safe_ratio(clean_sustain_scrape, clean_sustain_vocal)
    grit_attack_scrape_balance = _safe_ratio(grit_attack_scrape, grit_attack_vocal)
    grit_sustain_scrape_balance = _safe_ratio(grit_sustain_scrape, grit_sustain_vocal)

    assert abs(clean_attack_scrape - clean_sustain_scrape) > clean_sustain_scrape * 0.10
    assert abs(clean_attack_vocal - clean_sustain_vocal) > clean_sustain_vocal * 0.10
    assert abs(grit_attack_scrape - grit_sustain_scrape) > grit_sustain_scrape * 0.10
    assert abs(grit_attack_vocal - grit_sustain_vocal) > grit_sustain_vocal * 0.10
    assert abs(clean_attack_scrape_balance - clean_sustain_scrape_balance) > clean_sustain_scrape_balance * 0.08
    assert abs(grit_attack_scrape_balance - grit_sustain_scrape_balance) > grit_sustain_scrape_balance * 0.08


def test_generate_washint_tone_profiles_remain_finite_and_bounded():
    alto = _generate_seeded_washint('alto_breathy', seed=23)
    call = _generate_seeded_washint('dance_call', seed=23)

    assert alto.size == call.size == int(1.0 * SAMPLE_RATE)
    for audio in (alto, call):
        assert np.all(np.isfinite(audio))
        assert float(np.max(np.abs(audio))) <= 1.0 + 1e-6

    assert not np.allclose(alto, call)


def test_generate_washint_tone_dance_call_has_stronger_attack_and_upper_presence_than_alto_breathy():
    alto = _generate_seeded_washint('alto_breathy', seed=29)
    call = _generate_seeded_washint('dance_call', seed=29)

    alto_upper = _band_energy_ratio(alto, 2600.0, 6200.0)
    call_upper = _band_energy_ratio(call, 2600.0, 6200.0)
    alto_attack = _band_energy_ratio(alto[: int(0.05 * SAMPLE_RATE)], 2500.0, 7200.0)
    call_attack = _band_energy_ratio(call[: int(0.05 * SAMPLE_RATE)], 2500.0, 7200.0)

    assert call_upper > alto_upper * 1.10
    assert call_attack > alto_attack * 1.15


def test_generate_washint_tone_dance_call_stays_separated_in_high_register_with_midi_style_velocity_input():
    alto = _generate_seeded_washint(
        'alto_breathy',
        seed=119002,
        frequency=880.0,
        duration=1.4,
        velocity=96.0,
    )
    call = _generate_seeded_washint(
        'dance_call',
        seed=119002,
        frequency=880.0,
        duration=1.4,
        velocity=96.0,
    )

    alto_upper = _band_energy_ratio(alto, 2600.0, 6200.0)
    call_upper = _band_energy_ratio(call, 2600.0, 6200.0)
    alto_attack = _band_energy_ratio(alto[: int(0.05 * SAMPLE_RATE)], 2500.0, 7200.0)
    call_attack = _band_energy_ratio(call[: int(0.05 * SAMPLE_RATE)], 2500.0, 7200.0)

    assert call_upper > alto_upper * 1.20
    assert call_attack > alto_attack * 1.20


def test_generate_washint_tone_has_clearer_onset_air_jet_than_sustained_tube_column_balance():
    alto = _generate_seeded_washint('alto_breathy', seed=83)
    call = _generate_seeded_washint('dance_call', seed=83)

    alto_onset_air = _windowed_band_metric(alto, 0.00, 0.08, 3000.0, 8200.0)
    alto_onset_tube = _windowed_band_metric(alto, 0.00, 0.08, 350.0, 2200.0)
    alto_sustain_air = _windowed_band_metric(alto, 0.18, 0.65, 3000.0, 8200.0)
    alto_sustain_tube = _windowed_band_metric(alto, 0.18, 0.65, 350.0, 2200.0)

    call_onset_air = _windowed_band_metric(call, 0.00, 0.08, 3000.0, 8200.0)
    call_onset_tube = _windowed_band_metric(call, 0.00, 0.08, 350.0, 2200.0)
    call_sustain_air = _windowed_band_metric(call, 0.18, 0.65, 3000.0, 8200.0)
    call_sustain_tube = _windowed_band_metric(call, 0.18, 0.65, 350.0, 2200.0)

    assert _safe_ratio(alto_onset_air, alto_onset_tube) > _safe_ratio(alto_sustain_air, alto_sustain_tube) * 1.15
    assert _safe_ratio(call_onset_air, call_onset_tube) > _safe_ratio(call_sustain_air, call_sustain_tube) * 1.15


def test_generate_washint_tone_high_register_shifts_sustained_tube_focus_upward():
    mid = _generate_seeded_washint('alto_breathy', seed=97, frequency=523.25, duration=1.2)
    high = _generate_seeded_washint('alto_breathy', seed=97, frequency=880.0, duration=1.2)

    mid_upper_tube = _windowed_band_metric(mid, 0.20, 0.70, 1800.0, 4200.0)
    mid_low_tube = _windowed_band_metric(mid, 0.20, 0.70, 320.0, 1600.0)
    high_upper_tube = _windowed_band_metric(high, 0.20, 0.70, 1800.0, 4200.0)
    high_low_tube = _windowed_band_metric(high, 0.20, 0.70, 320.0, 1600.0)

    assert _safe_ratio(high_upper_tube, high_low_tube) > _safe_ratio(mid_upper_tube, mid_low_tube) * 1.08


def test_generate_washint_tone_add_ornament_concentrates_change_at_the_entry():
    plain = _generate_seeded_washint('dance_call', seed=211, add_ornament=False)
    ornamented = _generate_seeded_washint('dance_call', seed=211, add_ornament=True)

    onset_delta = _window_rms(ornamented - plain, 0.00, 0.10)
    sustain_delta = _window_rms(ornamented - plain, 0.24, 0.60)

    assert onset_delta > sustain_delta * 1.8


def test_generate_ethiopian_melodic_fallbacks_keep_body_energy_well_above_brittle_highs():
    cases = [
        ('krar_traditional_warm', _generate_seeded_krar('traditional_warm', seed=41)),
        ('krar_azmari_bright', _generate_seeded_krar('azmari_bright', seed=41)),
        ('masenqo_vocal_clean', _generate_seeded_masenqo('vocal_clean', seed=43)),
        ('masenqo_azmari_grit', _generate_seeded_masenqo('azmari_grit', seed=43)),
        ('washint_alto_breathy', _generate_seeded_washint('alto_breathy', seed=47)),
        ('washint_dance_call', _generate_seeded_washint('dance_call', seed=47)),
    ]

    for label, audio in cases:
        body_band = _band_energy_ratio(audio, 220.0, 1800.0)
        brittle_highs = _band_energy_ratio(audio, 3500.0, 9000.0)
        assert body_band > brittle_highs * 20.0, label


def test_generate_begena_tone_variants_remain_finite_and_bounded():
    stable = _generate_seeded_begena(seed=53)
    worn = _generate_seeded_begena(seed=53, string_quality='worn', buzzer_position=0.48)
    dry = _generate_seeded_begena(seed=53, buzzers_enabled=False, sustain_bias=0.55)
    mp3_bright = _generate_seeded_begena(
        seed=53,
        profile='mp3_reference_bright',
        string_quality='lively',
        buzzer_position=0.27,
        sustain_bias=0.55,
    )

    assert stable.size == worn.size == dry.size == mp3_bright.size == int(1.5 * SAMPLE_RATE)
    for audio in (stable, worn, dry, mp3_bright):
        assert np.all(np.isfinite(audio))
        assert float(np.max(np.abs(audio))) <= 1.0 + 1e-6


def test_generate_begena_tone_mp3_reference_bright_adds_clarity_without_exploding_highs():
    drone = _generate_seeded_begena(seed=12902, profile='paraliturgical_drone', sustain_bias=0.84)
    bright = _generate_seeded_begena(
        seed=12902,
        profile='mp3_reference_bright',
        string_quality='lively',
        buzzer_position=0.27,
        sustain_bias=0.55,
    )

    drone_low_mid = _band_energy_ratio(drone, 250.0, 500.0)
    bright_low_mid = _band_energy_ratio(bright, 250.0, 500.0)
    drone_mid = _band_energy_ratio(drone, 500.0, 2000.0)
    bright_mid = _band_energy_ratio(bright, 500.0, 2000.0)
    drone_high_mid = _band_energy_ratio(drone, 2000.0, 6000.0)
    bright_high_mid = _band_energy_ratio(bright, 2000.0, 6000.0)
    drone_high = _band_energy_ratio(drone, 6000.0, 10000.0)
    bright_high = _band_energy_ratio(bright, 6000.0, 10000.0)

    drone_clarity = drone_mid + drone_high_mid + drone_high
    bright_clarity = bright_mid + bright_high_mid + bright_high

    assert bright_mid > drone_mid * 2.0
    assert bright_high_mid > max(drone_high_mid * 2.0, 0.00020)
    assert bright_high > max(drone_high * 1.5, 0.000001)
    assert bright_clarity > drone_clarity * 2.0
    assert _safe_ratio(bright_low_mid, bright_clarity) < _safe_ratio(drone_low_mid, drone_clarity) * 0.75
    assert bright_high_mid < 0.080
    assert bright_high < 0.018


def test_generate_begena_tone_buzzers_on_vs_off_produces_meaningful_structured_difference():
    with_buzz = _generate_seeded_begena(seed=59, buzzers_enabled=True, buzzer_position=0.42)
    without_buzz = _generate_seeded_begena(seed=59, buzzers_enabled=False, buzzer_position=0.42)

    difference = float(np.mean(np.abs(with_buzz - without_buzz)))
    buzz_delta = with_buzz - without_buzz
    low_mid_roughness = _band_energy_ratio(buzz_delta, 180.0, 560.0)
    broad_low_mid_roughness = _band_energy_ratio(buzz_delta, 180.0, 700.0)
    high_mid_roughness = _band_energy_ratio(buzz_delta, 1200.0, 6000.0)

    assert difference > 0.01
    assert low_mid_roughness > high_mid_roughness * 25.0
    assert broad_low_mid_roughness > high_mid_roughness * 25.0
    assert high_mid_roughness < 0.010


def test_generate_begena_tone_higher_sustain_bias_increases_held_tail_energy():
    shorter = _generate_seeded_begena(seed=61, duration=1.8, sustain_bias=0.25)
    longer = _generate_seeded_begena(seed=61, duration=1.8, sustain_bias=0.95)

    assert _tail_rms(longer, 0.72) > _tail_rms(shorter, 0.72) * 1.01


def test_generate_begena_tone_keeps_low_frequency_dominance_across_string_qualities():
    stable = _generate_seeded_begena(seed=67, string_quality='stable')
    lively = _generate_seeded_begena(seed=67, string_quality='lively', buzzer_position=0.28)
    worn = _generate_seeded_begena(seed=67, string_quality='worn', buzzer_position=0.50)

    for label, audio in (
        ('stable', stable),
        ('lively', lively),
        ('worn', worn),
    ):
        low_band = _band_energy_ratio(audio, 40.0, 220.0)
        upper_band = _band_energy_ratio(audio, 900.0, 2600.0)
        assert low_band > upper_band * 1.8, label


def test_generate_begena_tone_reference_proxy_keeps_body_below_520hz_dominant():
    cases = [
        ('default', _generate_seeded_begena(seed=73)),
        ('stable', _generate_seeded_begena(seed=73, string_quality='stable')),
        ('worn', _generate_seeded_begena(seed=73, string_quality='worn', buzzer_position=0.50)),
        ('lively', _generate_seeded_begena(seed=73, string_quality='lively', buzzer_position=0.28)),
    ]

    for label, audio in cases:
        low_to_low_mid_body = _band_energy_ratio(audio, 40.0, 520.0)
        skin_box_body = _band_energy_ratio(audio, 250.0, 500.0)
        midrange_buzz = _band_energy_ratio(audio, 520.0, 2600.0)
        assert low_to_low_mid_body > 0.88, label
        assert skin_box_body > 0.34, label
        assert midrange_buzz < 0.065, label
        assert low_to_low_mid_body > midrange_buzz * 12.0, label


def test_generate_begena_tone_buzzer_presence_is_low_mid_not_broadband_high_mid():
    with_buzz = _generate_seeded_begena(seed=79, buzzers_enabled=True, buzzer_position=0.46)
    without_buzz = _generate_seeded_begena(seed=79, buzzers_enabled=False, buzzer_position=0.46)
    buzz_delta = with_buzz - without_buzz

    assert float(np.mean(np.abs(buzz_delta))) > 0.01

    low_mid_roughness = _band_energy_ratio(buzz_delta, 180.0, 560.0)
    broad_low_mid_roughness = _band_energy_ratio(buzz_delta, 180.0, 700.0)
    high_mid_roughness = _band_energy_ratio(buzz_delta, 1200.0, 6000.0)
    assert low_mid_roughness > high_mid_roughness * 25.0
    assert broad_low_mid_roughness > high_mid_roughness * 25.0
    assert high_mid_roughness < 0.010


def test_generate_begena_tone_string_quality_changes_timbre_without_breaking_identity():
    stable = _generate_seeded_begena(seed=71, string_quality='stable')
    lively = _generate_seeded_begena(seed=71, string_quality='lively', buzzer_position=0.24)

    assert not np.allclose(stable, lively)
    assert float(np.mean(np.abs(stable - lively))) > 0.005

    stable_low = _band_energy_ratio(stable, 40.0, 220.0)
    lively_low = _band_energy_ratio(lively, 40.0, 220.0)
    stable_upper = _band_energy_ratio(stable, 900.0, 2600.0)
    lively_upper = _band_energy_ratio(lively, 900.0, 2600.0)

    assert stable_low > stable_upper * 1.8
    assert lively_low > lively_upper * 1.8


def test_krar_masenqo_begena_public_synthesis_signatures_remain_unchanged():
    assert list(inspect.signature(generate_krar_tone).parameters) == [
        'frequency',
        'duration',
        'velocity',
        'sample_rate',
        'tuning',
        'add_ornament',
        'profile',
    ]
    assert list(inspect.signature(generate_masenqo_tone).parameters) == [
        'frequency',
        'duration',
        'velocity',
        'sample_rate',
        'expressiveness',
        'add_ornament',
        'profile',
    ]
    assert list(inspect.signature(generate_begena_tone).parameters) == [
        'frequency',
        'duration',
        'velocity',
        'sample_rate',
        'profile',
        'buzzers_enabled',
        'buzzer_position',
        'string_quality',
        'sustain_bias',
    ]


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
