import importlib.util
from pathlib import Path

import numpy as np
import soundfile as sf


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "compare_ethiopian_reference_audio.py"
SPEC = importlib.util.spec_from_file_location("compare_ethiopian_reference_audio", SCRIPT_PATH)
compare = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(compare)


def _synthetic_reference_audio(
    *,
    sample_rate: int = 22050,
    duration: float = 1.20,
    onsets=(0.0, 0.34, 0.72),
    frequencies=(220.0, 246.94, 196.0),
) -> np.ndarray:
    audio = np.zeros(int(round(duration * sample_rate)), dtype=np.float64)
    for onset, frequency in zip(onsets, frequencies):
        start = int(round(onset * sample_rate))
        stop = min(audio.size, start + int(round(0.30 * sample_rate)))
        if stop <= start:
            continue
        t = np.arange(stop - start, dtype=np.float64) / sample_rate
        envelope = np.exp(-t / 0.22) * np.clip(t / 0.018, 0.0, 1.0)
        audio[start:stop] += 0.42 * np.sin(2 * np.pi * frequency * t) * envelope
        audio[start:stop] += 0.05 * np.sin(2 * np.pi * frequency * 2.0 * t) * envelope
    return audio


def _synthetic_close_onset_reference_audio(sample_rate: int = 22050) -> np.ndarray:
    return _synthetic_reference_audio(
        sample_rate=sample_rate,
        duration=0.76,
        onsets=(0.0, 0.105, 0.215, 0.330),
        frequencies=(185.0, 220.0, 196.0, 246.94),
    )


def test_public_reference_manifest_statuses_and_metadata():
    manifest = compare.PUBLIC_REFERENCE_MANIFEST

    begena = manifest["begena"]
    assert begena["status"] == "available"
    assert begena["page"] == "https://commons.wikimedia.org/wiki/File:BegenaScalePlucked.ogg"
    assert begena["direct_url"] == "https://upload.wikimedia.org/wikipedia/commons/8/89/BegenaScalePlucked.ogg"
    assert begena["license"] == "CC BY-SA 3.0 / GFDL"
    assert "Temambiru" in begena["attribution"]
    assert "Temesgen Hussein" in begena["attribution"]

    for instrument in ("krar", "masenqo", "washint"):
        entry = manifest[instrument]
        assert entry["status"] == "unavailable_by_default"
        assert entry["supports_user_ref"] is True
        assert "No public downloadable WAV/OGG/MP3" in entry["reason"]
        assert entry["source_urls"]


def test_descriptor_extraction_on_constructed_audio_returns_finite_expected_keys():
    sample_rate = 22050
    t = np.arange(int(0.35 * sample_rate), dtype=np.float64) / sample_rate
    audio = 0.40 * np.sin(2 * np.pi * 220.0 * t) * np.exp(-t * 1.5)
    audio += 0.04 * np.sin(2 * np.pi * 660.0 * t)

    descriptors = compare.extract_descriptors(audio, sample_rate)

    expected_scalar_keys = [
        "duration",
        "rms",
        "peak",
        "spectral_centroid_mean",
        "spectral_centroid_std",
        "spectral_rolloff_mean",
        "spectral_rolloff_std",
        "spectral_bandwidth_mean",
        "spectral_bandwidth_std",
        "spectral_flatness_mean",
        "spectral_flatness_std",
        "zero_crossing_mean",
        "onset_strength_mean",
        "onset_strength_std",
        "onset_strength_max",
        "onset_density",
        "spectral_flux_mean",
        "spectral_flux_std",
        "hpss_harmonic_percussive_ratio",
        "attack_time_to_peak",
        "effective_duration_above_20db",
        "tail_to_attack_rms",
        "active_start_seconds",
        "active_end_seconds",
        "max_adjacent_sample_jump",
        "p95_adjacent_sample_jump",
        "p99_adjacent_sample_jump",
        "p999_adjacent_sample_jump",
        "max_boundary_discontinuity",
    ]
    for key in expected_scalar_keys:
        assert key in descriptors
        assert np.isfinite(float(descriptors[key]))

    assert descriptors["duration"] == len(audio) / sample_rate
    assert descriptors["peak"] > 0.0
    assert descriptors["rms"] > 0.0
    assert len(descriptors["mfcc_mean"]) == 13
    assert len(descriptors["mfcc_std"]) == 13
    assert all(np.isfinite(float(value)) for value in descriptors["mfcc_mean"])
    assert all(np.isfinite(float(value)) for value in descriptors["mfcc_std"])
    assert set(descriptors["band_energy_ratios"]) == {"sub", "low", "low_mid", "mid", "high_mid", "high"}
    assert all(np.isfinite(float(value)) for value in descriptors["band_energy_ratios"].values())
    assert "f0_yin_median_hz" in descriptors
    if descriptors["f0_yin_median_hz"] is not None:
        assert np.isfinite(float(descriptors["f0_yin_median_hz"]))


def test_reference_schedule_extraction_on_synthetic_audio_returns_finite_onset_and_f0_metadata():
    sample_rate = 22050
    audio = _synthetic_reference_audio(sample_rate=sample_rate)

    schedule = compare.extract_reference_schedule(
        audio,
        sample_rate,
        instrument="krar",
        source_id="synthetic_krar",
    )

    assert schedule["diagnostic_only"] is True
    assert 1.15 <= float(schedule["duration_seconds"]) <= 1.25
    assert schedule["onset_count"] >= 1
    assert schedule["onset_generation_count"] >= 1
    assert float(schedule["onset_density"]) > 0.0
    assert len(schedule["onset_times_seconds"]) <= compare.REFERENCE_SHAPE_MAX_METADATA_ONSETS
    assert schedule["f0_median_hz"] is not None
    assert np.isfinite(float(schedule["f0_median_hz"]))
    assert np.isfinite(float(schedule["f0_percentiles_hz"]["p50"]))
    assert any(value is not None and np.isfinite(float(value)) for value in schedule["segment_f0_medians_hz"])


def test_sustain_decay_metrics_use_active_region_with_leading_silence():
    sample_rate = 1000
    silence = np.zeros(int(0.40 * sample_rate), dtype=np.float64)
    active_t = np.arange(int(0.50 * sample_rate), dtype=np.float64) / sample_rate
    attack = np.clip(active_t / 0.06, 0.0, 1.0)
    decay = np.exp(-np.maximum(0.0, active_t - 0.06) / 0.22)
    active = 0.55 * np.sin(2 * np.pi * 80.0 * active_t) * attack * decay
    trailing_silence = np.zeros(int(0.30 * sample_rate), dtype=np.float64)
    audio = np.concatenate([silence, active, trailing_silence])

    metrics = compare._sustain_decay_metrics(audio, sample_rate)

    assert 0.38 <= metrics["active_start_seconds"] <= 0.43
    assert metrics["active_end_seconds"] < 0.92
    assert 0.035 <= metrics["attack_time_to_peak"] <= 0.085
    assert metrics["attack_time_to_peak"] < 0.12
    assert 0.0 < metrics["tail_to_attack_rms"] < 1.0
    assert np.isfinite(float(metrics["tail_to_attack_rms"]))


def test_comparison_report_handles_unavailable_refs_without_failing(tmp_path):
    out_dir = tmp_path / "report"
    refs_dir = tmp_path / "refs"

    result = compare.run_comparison(
        refs_dir=refs_dir,
        out_dir=out_dir,
        instruments=["krar", "masenqo", "washint"],
        download_public_refs=False,
        user_refs={},
        write_generated_wavs=False,
        sample_rate=22050,
    )

    assert Path(result["out_dir"]) == out_dir
    assert (out_dir / "reference_status.json").exists()
    assert (out_dir / "descriptors.json").exists()
    assert (out_dir / "comparisons.json").exists()
    assert (out_dir / "summary.md").exists()

    for instrument in ("krar", "masenqo", "washint"):
        entry = result["reference_status"]["instruments"][instrument]
        assert entry["effective_status"] == "unavailable_no_user_reference"
        assert entry["available_reference_count"] == 0
        assert result["comparisons"]["comparisons"][instrument] == []
        unavailable = result["comparisons"]["unavailable_references"][instrument]
        assert unavailable["effective_status"] == "unavailable_no_user_reference"
        assert unavailable["user_ref_supported"] is True
        generated = result["descriptors"]["generated"][instrument]
        assert generated["metadata"]["probe_shape"] == "single_note"
        assert generated["metadata"]["full_song_generation"] is False
        assert generated["path"] is None
        assert np.isfinite(float(generated["descriptors"]["rms"]))
        assert result["descriptors"]["generated_reference_shaped"][instrument] == []

    summary = (out_dir / "summary.md").read_text(encoding="utf-8")
    assert "diagnostic source-truth harness" in summary
    assert "Krar / Masenqo / Washint" in summary
    assert "Do not use this report to claim" in summary


def test_default_krar_and_masenqo_generated_probes_remain_single_note():
    for instrument in ("krar", "masenqo"):
        audio, metadata = compare.generate_probe_audio(instrument, sample_rate=22050)
        assert audio.size == int(round(1.20 * 22050))
        assert metadata["probe_shape"] == "single_note"
        assert metadata["full_song_generation"] is False
        assert "reference_source_id" not in metadata


def test_match_user_ref_shape_generates_per_reference_entries_and_pairs_comparisons(tmp_path):
    sample_rate = 22050
    refs_dir = tmp_path / "refs"
    out_dir = tmp_path / "report"
    refs_dir.mkdir()

    krar_ref = refs_dir / "synthetic_krar.wav"
    masenqo_ref = refs_dir / "synthetic_masenqo.wav"
    begena_ref = refs_dir / "synthetic_begena.wav"
    sf.write(krar_ref, _synthetic_reference_audio(sample_rate=sample_rate, frequencies=(180.0, 220.0, 165.0)), sample_rate)
    sf.write(masenqo_ref, _synthetic_reference_audio(sample_rate=sample_rate, frequencies=(260.0, 293.66, 246.94)), sample_rate)
    sf.write(begena_ref, _synthetic_reference_audio(sample_rate=sample_rate, frequencies=(73.42, 82.41, 65.41)), sample_rate)

    result = compare.run_comparison(
        refs_dir=refs_dir,
        out_dir=out_dir,
        instruments=["krar", "masenqo", "begena"],
        download_public_refs=False,
        user_refs={"krar": [krar_ref], "masenqo": [masenqo_ref], "begena": [begena_ref]},
        match_user_ref_shape=True,
        write_generated_wavs=True,
        sample_rate=sample_rate,
    )

    for instrument in ("krar", "masenqo", "begena"):
        default_generated = result["descriptors"]["generated"][instrument]
        expected_default_shape = "reference_scale_shape" if instrument == "begena" else "single_note"
        assert default_generated["metadata"]["probe_shape"] == expected_default_shape

        shaped_entries = result["descriptors"]["generated_reference_shaped"][instrument]
        assert len(shaped_entries) == 1
        shaped = shaped_entries[0]
        source_id = f"{instrument}_user_ref_1"
        assert shaped["source_id"] == source_id
        assert shaped["metadata"]["probe_shape"] == "reference_performance_shape"
        assert shaped["metadata"]["reference_source_id"] == source_id
        assert shaped["metadata"]["full_song_generation"] is False
        assert shaped["metadata"]["click_smoothing"] is True
        assert shaped["metadata"]["mp3_source_truth"] is True
        assert float(shaped["metadata"]["composition_release_tail_seconds"]) > 0.0
        assert shaped["metadata"]["click_diagnostics"]["max_adjacent_sample_jump"] < 0.45
        assert source_id in Path(shaped["path"]).name
        assert Path(shaped["path"]).exists()
        assert abs(float(shaped["descriptors"]["duration"]) - 1.20) <= 0.03

        references = result["descriptors"]["references"][instrument]
        assert references[0]["schedule_metadata"]["source_id"] == source_id
        assert references[0]["schedule_metadata"]["diagnostic_only"] is True

        comparisons = result["comparisons"]["comparisons"][instrument]
        assert len(comparisons) == 1
        assert comparisons[0]["reference_source_id"] == source_id
        assert comparisons[0]["generated_probe_shape"] == "reference_performance_shape"
        assert comparisons[0]["generated_path"] == shaped["path"]


def test_reference_shaped_composition_includes_release_tails_overlap_and_click_metadata():
    sample_rate = 22050
    reference_schedule = {
        "diagnostic_only": True,
        "instrument": "krar",
        "source_id": "synthetic_close_krar",
        "duration_seconds": 0.72,
        "generation_duration_seconds": 0.72,
        "warnings": [],
        "generation_events": [
            {"index": 0, "onset_seconds": 0.00, "f0_median_hz": 185.0, "f0_source": "test", "f0_frame_count": 1},
            {"index": 1, "onset_seconds": 0.11, "f0_median_hz": 220.0, "f0_source": "test", "f0_frame_count": 1},
            {"index": 2, "onset_seconds": 0.23, "f0_median_hz": 196.0, "f0_source": "test", "f0_frame_count": 1},
        ],
    }

    audio, metadata = compare.generate_reference_shaped_probe_audio(
        "krar",
        reference_schedule,
        reference_source_id="synthetic_close_krar",
        sample_rate=sample_rate,
        mp3_source_truth=True,
    )

    assert audio.size == int(round(0.72 * sample_rate))
    assert metadata["click_smoothing"] is True
    assert metadata["mp3_source_truth"] is True
    assert metadata["normalized_final_output"] is False
    assert float(metadata["composition_release_tail_seconds"]) >= 0.05

    schedule = metadata["probe_schedule"]
    assert schedule["click_smoothing"] is True
    assert schedule["mp3_source_truth"] is True
    assert float(schedule["composition_release_tail_seconds"]) >= 0.05
    assert any(note["overlaps_next_onset"] for note in schedule["notes"][:-1])
    assert all(note["click_smoothing"] is True for note in schedule["notes"])
    assert all(float(note["composition_release_tail_seconds"]) > 0.0 for note in schedule["notes"])
    assert float(np.max(np.abs(audio))) <= 0.98


def test_masenqo_reference_shaped_probe_is_monophonic_for_close_onsets():
    sample_rate = 22050
    reference_schedule = {
        "diagnostic_only": True,
        "instrument": "masenqo",
        "source_id": "synthetic_close_masenqo",
        "duration_seconds": 0.74,
        "generation_duration_seconds": 0.74,
        "warnings": [],
        "generation_events": [
            {"index": 0, "onset_seconds": 0.00, "f0_median_hz": 246.94, "f0_source": "test", "f0_frame_count": 2},
            {"index": 1, "onset_seconds": 0.095, "f0_median_hz": 293.66, "f0_source": "test", "f0_frame_count": 2},
            {"index": 2, "onset_seconds": 0.205, "f0_median_hz": 261.63, "f0_source": "test", "f0_frame_count": 2},
            {"index": 3, "onset_seconds": 0.330, "f0_median_hz": 329.63, "f0_source": "test", "f0_frame_count": 2},
        ],
    }

    audio, metadata = compare.generate_reference_shaped_probe_audio(
        "masenqo",
        reference_schedule,
        reference_source_id="synthetic_close_masenqo",
        sample_rate=sample_rate,
        mp3_source_truth=True,
    )

    schedule = metadata["probe_schedule"]
    notes = schedule["notes"]

    assert audio.size == int(round(0.74 * sample_rate))
    assert metadata["monophonic_source"] is True
    assert metadata["overlap_policy"] == "monophonic_fade_to_next_onset"
    assert metadata["scheduled_overlap_count"] == 0
    assert metadata["substantial_overlap_count"] == 0
    assert metadata["max_scheduled_overlap_seconds"] <= 0.001
    assert schedule["monophonic_source"] is True
    assert schedule["overlap_policy"] == metadata["overlap_policy"]
    assert schedule["substantial_overlap_count"] == 0
    assert all(note["overlaps_next_onset"] is False for note in notes[:-1])
    assert all(
        float(note["duration_seconds"]) <= float(note["nominal_gap_seconds"]) + 1e-6
        for note in notes[:-1]
    )
    assert metadata["click_diagnostics"]["max_adjacent_sample_jump"] < 0.45
    assert metadata["click_diagnostics"]["p999_adjacent_sample_jump"] < 0.18
    assert float(np.max(np.abs(audio))) <= 0.98


def test_mp3_source_begena_shaped_probe_uses_mp3_profile_and_shorter_tail():
    sample_rate = 22050
    reference_schedule = {
        "diagnostic_only": True,
        "instrument": "begena",
        "source_id": "begena_user_ref_1",
        "duration_seconds": 1.36,
        "generation_duration_seconds": 1.36,
        "onset_density": 1.47,
        "f0_median_hz": 78.0,
        "band_energy_ratios": {"low": 0.42, "low_mid": 0.30, "mid": 0.16, "high_mid": 0.02, "high": 0.01},
        "warnings": [],
        "generation_events": [
            {"index": 0, "onset_seconds": 0.00, "f0_median_hz": 73.4, "f0_source": "test", "f0_frame_count": 3},
            {"index": 1, "onset_seconds": 0.52, "f0_median_hz": 82.4, "f0_source": "test", "f0_frame_count": 3},
        ],
    }

    audio, metadata = compare.generate_reference_shaped_probe_audio(
        "begena",
        reference_schedule,
        reference_source_id="begena_user_ref_1",
        sample_rate=sample_rate,
        mp3_source_truth=True,
    )

    assert audio.size == int(round(1.36 * sample_rate))
    assert metadata["mp3_source_truth"] is True
    assert metadata["click_smoothing"] is True
    assert metadata["generator_profiles_used"] == ["mp3_reference_bright"]
    assert metadata["mp3_profile_routing"]["instrument_profile"] == "mp3_reference_bright"
    assert float(metadata["composition_release_tail_seconds"]) <= 0.2401
    assert float(metadata["composition_release_tail_seconds"]) < 0.36
    assert metadata["mp3_profile_routing"]["begena_sustain_bias_range"][1] <= 0.64
    assert all(note["generator_profile"] == "mp3_reference_bright" for note in metadata["probe_schedule"]["notes"])
    assert all(note["click_smoothing"] is True for note in metadata["probe_schedule"]["notes"])


def test_krar_mp3_mixed_reference_instrument_focus_skips_or_attenuates_low_drone_events():
    sample_rate = 22050
    reference_schedule = {
        "diagnostic_only": True,
        "instrument": "krar",
        "source_id": "krar_user_ref_2",
        "duration_seconds": 1.82,
        "generation_duration_seconds": 1.82,
        "onset_density": 2.20,
        "onset_generation_count": 4,
        "f0_median_hz": 129.0,
        "band_energy_ratios": {"low": 0.40, "low_mid": 0.28, "mid": 0.22, "high_mid": 0.06, "high": 0.01},
        "warnings": [],
        "generation_events": [
            {"index": 0, "onset_seconds": 0.00, "f0_median_hz": 58.0, "f0_source": "test", "f0_frame_count": 3},
            {"index": 1, "onset_seconds": 0.50, "f0_median_hz": 102.0, "f0_source": "test", "f0_frame_count": 3},
            {"index": 2, "onset_seconds": 1.00, "f0_median_hz": 196.0, "f0_source": "test", "f0_frame_count": 3},
            {"index": 3, "onset_seconds": 1.34, "f0_median_hz": 220.0, "f0_source": "test", "f0_frame_count": 3},
        ],
    }

    audio, metadata = compare.generate_reference_shaped_probe_audio(
        "krar",
        reference_schedule,
        reference_source_id="krar_user_ref_2",
        sample_rate=sample_rate,
        mp3_source_truth=True,
    )

    assert audio.size == int(round(1.82 * sample_rate))
    assert metadata["instrument_focus"] is True
    assert metadata["generator_profiles_used"] == ["azmari_bright"]
    assert metadata["instrument_focus_skipped_events"] >= 1
    assert metadata["instrument_focus_attenuated_events"] >= 1
    assert metadata["instrument_focus_rendered_events"] >= 2
    assert "source_id_second_user_ref_task129_diagnostic_fallback" in metadata["instrument_focus_reasons"]
    actions = [note["render_action"] for note in metadata["probe_schedule"]["notes"]]
    assert "skipped_low_drone_like_event" in actions
    assert "attenuated_low_drone_like_event" in actions
    assert metadata["probe_schedule"]["instrument_focus_skipped_events"] == metadata["instrument_focus_skipped_events"]


def test_generated_reference_shaped_probe_has_bounded_jump_for_close_onset_reference_wav(tmp_path):
    sample_rate = 22050
    refs_dir = tmp_path / "refs"
    out_dir = tmp_path / "report"
    refs_dir.mkdir()
    krar_ref = refs_dir / "synthetic_close_krar.wav"
    sf.write(krar_ref, _synthetic_close_onset_reference_audio(sample_rate=sample_rate), sample_rate)

    result = compare.run_comparison(
        refs_dir=refs_dir,
        out_dir=out_dir,
        instruments=["krar"],
        download_public_refs=False,
        user_refs={"krar": [krar_ref]},
        match_user_ref_shape=True,
        write_generated_wavs=True,
        sample_rate=sample_rate,
    )

    shaped = result["descriptors"]["generated_reference_shaped"]["krar"][0]
    descriptors = shaped["descriptors"]
    click_diagnostics = shaped["metadata"]["click_diagnostics"]

    assert Path(shaped["path"]).exists()
    assert descriptors["max_adjacent_sample_jump"] < 0.45
    assert descriptors["p999_adjacent_sample_jump"] < 0.18
    assert descriptors["max_boundary_discontinuity"] < 0.02
    assert click_diagnostics["max_adjacent_sample_jump"] == descriptors["max_adjacent_sample_jump"]


def test_begena_public_reference_still_included_without_user_refs(tmp_path):
    refs_dir = tmp_path / "refs"
    refs_dir.mkdir()
    public_path = refs_dir / compare.PUBLIC_REFERENCE_MANIFEST["begena"]["filename"]
    public_path.write_bytes(b"placeholder; candidate selection only")

    status, candidates = compare.build_reference_status(
        refs_dir,
        ["begena"],
        download_public_refs=False,
        user_refs={},
        match_user_ref_shape=True,
    )

    begena_status = status["instruments"]["begena"]
    assert begena_status["public_reference"]["status"] == "existing"
    assert begena_status["public_reference_included"] is True
    assert begena_status["effective_status"] == "available_local_reference"
    assert [candidate.kind for candidate in candidates] == ["public_commons"]


def test_user_ref_shape_run_excludes_public_begena_unless_explicitly_included(tmp_path):
    refs_dir = tmp_path / "refs"
    refs_dir.mkdir()
    public_path = refs_dir / compare.PUBLIC_REFERENCE_MANIFEST["begena"]["filename"]
    public_path.write_bytes(b"placeholder; candidate selection only")
    user_ref = refs_dir / "synthetic_begena_user_ref.wav"
    user_ref.write_bytes(b"placeholder; candidate selection only")

    status, candidates = compare.build_reference_status(
        refs_dir,
        ["begena"],
        download_public_refs=False,
        user_refs={"begena": [user_ref]},
        match_user_ref_shape=True,
    )

    begena_status = status["instruments"]["begena"]
    assert status["user_mp3_references_are_source_truth"] is True
    assert begena_status["user_refs_are_active_source_truth"] is True
    assert begena_status["public_reference_included"] is False
    assert "user references are the active source of truth" in begena_status["public_reference_excluded_reason"]
    assert [candidate.kind for candidate in candidates] == ["user_supplied"]

    included_status, included_candidates = compare.build_reference_status(
        refs_dir,
        ["begena"],
        download_public_refs=False,
        user_refs={"begena": [user_ref]},
        match_user_ref_shape=True,
        include_public_refs_with_user_refs=True,
    )

    included_begena = included_status["instruments"]["begena"]
    assert included_begena["public_reference_included"] is True
    assert [candidate.kind for candidate in included_candidates] == ["public_commons", "user_supplied"]


def test_begena_generated_probe_is_reference_scale_shape_with_bounded_frequencies():
    sample_rate = 22050

    audio, metadata = compare.generate_probe_audio("begena", sample_rate=sample_rate)

    duration = len(audio) / sample_rate
    assert duration > 20.0
    assert 24.0 <= duration <= 25.0
    assert metadata["probe_shape"] == "reference_scale_shape"
    assert metadata["full_song_generation"] is False
    assert metadata["source_notes"]
    assert metadata["warnings"]

    schedule = metadata["probe_schedule"]
    assert schedule["shape"] == "reference_scale_shape"
    assert len(schedule["notes"]) == len(compare.BEGENA_REFERENCE_SCALE_ONSETS_SECONDS)
    assert len(schedule["frequencies_hz"]) == len(schedule["notes"])

    frequencies = [float(value) for value in schedule["frequencies_hz"]]
    assert all(50.0 <= frequency <= 150.0 for frequency in frequencies)
    assert max(frequencies) > min(frequencies)
    assert schedule["source_truth_constraints"]["isolated_source_synthesis"] is True
    assert "10 strings / five pitch pairs" in schedule["source_truth_constraints"]["string_layout"]

    qualities = {note["string_quality"] for note in schedule["notes"]}
    buzzer_positions = [float(note["buzzer_position"]) for note in schedule["notes"]]
    sustain_biases = [float(note["sustain_bias"]) for note in schedule["notes"]]
    assert len(qualities) > 1
    assert max(buzzer_positions) > min(buzzer_positions)
    assert max(sustain_biases) > min(sustain_biases)
    assert np.isfinite(float(np.max(np.abs(audio))))
