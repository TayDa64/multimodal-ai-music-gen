"""Focused regressions for first-class guitar rendering/routing."""

import mido
import numpy as np
import soundfile as sf

from multimodal_gen.assets_gen import generate_guitar_tone
from multimodal_gen.audio_renderer import AudioRenderer, ProceduralRenderer, SynthNote
from multimodal_gen.synthesizers.neural_runtime import OptionalNeuralRuntime
from multimodal_gen.instrument_manager import (
    AnalyzedInstrument,
    InstrumentCategory,
    InstrumentLibrary,
    SonicProfile,
)
from multimodal_gen.prompt_parser import ParsedPrompt, PromptParser
from multimodal_gen.utils import ScaleType


ROCK_TONE_DIAGNOSTIC = "high_shelf=-10.0dB@4000Hz;low_shelf=-4.0dB@90Hz"
LYRICAL_CINEMATIC_TONE_DIAGNOSTIC = "high_shelf=-3.0dB@3500Hz"

LYRICAL_CINEMATIC_PIANO_PROMPT = (
    "cinematic orchestral score with lyrical piano, warm strings, flute, oboe, "
    "harp, and soft choir, emotional rising theme, 78 BPM in G major"
)


def _note(program: int, duration_samples: int = 2205) -> SynthNote:
    return SynthNote(
        pitch=64,
        start_sample=0,
        duration_samples=duration_samples,
        velocity=0.8,
        channel=2,
        program=program,
    )


def _bass_note(program: int, pitch: int = 40, duration_samples: int = 11025) -> SynthNote:
    return SynthNote(
        pitch=pitch,
        start_sample=0,
        duration_samples=duration_samples,
        velocity=0.82,
        channel=1,
        program=program,
    )


def _save_two_track_tempo_midi(path, *, tempo: int | None = None, start_tick: int = 7680, duration_ticks: int = 960):
    midi = mido.MidiFile(ticks_per_beat=480)

    meta_track = mido.MidiTrack()
    meta_track.append(mido.MetaMessage('track_name', name='Meta', time=0))
    if tempo is not None:
        meta_track.append(mido.MetaMessage('set_tempo', tempo=tempo, time=0))
    midi.tracks.append(meta_track)

    note_track = mido.MidiTrack()
    note_track.append(mido.MetaMessage('track_name', name='Lead', time=0))
    note_track.append(mido.Message('program_change', program=81, channel=0, time=0))
    note_track.append(mido.Message('note_on', note=64, velocity=100, channel=0, time=start_tick))
    note_track.append(mido.Message('note_off', note=64, velocity=0, channel=0, time=duration_ticks))
    midi.tracks.append(note_track)

    midi.save(path)
    return midi


def _save_single_track_program_midi(
    path,
    *,
    track_name: str,
    program: int | None,
    channel: int = 0,
    note: int = 64,
    velocity: int = 100,
    duration_ticks: int = 960,
):
    midi = mido.MidiFile(ticks_per_beat=480)

    meta_track = mido.MidiTrack()
    meta_track.append(mido.MetaMessage('track_name', name='Meta', time=0))
    meta_track.append(mido.MetaMessage('set_tempo', tempo=500000, time=0))
    midi.tracks.append(meta_track)

    note_track = mido.MidiTrack()
    note_track.append(mido.MetaMessage('track_name', name=track_name, time=0))
    if program is not None:
        note_track.append(mido.Message('program_change', program=program, channel=channel, time=0))
    note_track.append(mido.Message('note_on', note=note, velocity=velocity, channel=channel, time=0))
    note_track.append(mido.Message('note_off', note=note, velocity=0, channel=channel, time=duration_ticks))
    midi.tracks.append(note_track)

    midi.save(path)
    return midi


def test_procedural_render_uses_global_meta_track_tempo_for_note_timing(monkeypatch, tmp_path):
    midi_path = tmp_path / "meta_tempo_100bpm.mid"
    _save_two_track_tempo_midi(midi_path, tempo=600000)  # 100 BPM on track 0 only

    renderer = AudioRenderer(sample_rate=44100, use_fluidsynth=False, genre="rock")
    captured_notes = []

    def fake_render_notes(notes, total_samples, is_drums=False):
        captured_notes.extend(notes)
        return np.zeros(total_samples, dtype=np.float32)

    monkeypatch.setattr(renderer.procedural, "render_notes", fake_render_notes)
    monkeypatch.setattr("multimodal_gen.audio_renderer.save_wav", lambda *args, **kwargs: True)

    assert renderer._render_procedural(str(midi_path), str(tmp_path / "out.wav")) is True

    assert len(captured_notes) == 1
    note = captured_notes[0]
    assert note.start_sample == 423360
    assert note.duration_samples == 52920
    assert note.start_sample != 352800  # The old per-track 120 BPM fallback.


def test_procedural_render_defaults_to_120_bpm_without_any_tempo(monkeypatch, tmp_path):
    midi_path = tmp_path / "default_tempo.mid"
    _save_two_track_tempo_midi(midi_path, tempo=None)

    renderer = AudioRenderer(sample_rate=44100, use_fluidsynth=False, genre="rock")
    captured_notes = []

    def fake_render_notes(notes, total_samples, is_drums=False):
        captured_notes.extend(notes)
        return np.zeros(total_samples, dtype=np.float32)

    monkeypatch.setattr(renderer.procedural, "render_notes", fake_render_notes)
    monkeypatch.setattr("multimodal_gen.audio_renderer.save_wav", lambda *args, **kwargs: True)

    assert renderer._render_procedural(str(midi_path), str(tmp_path / "out.wav")) is True

    assert len(captured_notes) == 1
    note = captured_notes[0]
    assert note.start_sample == 352800
    assert note.duration_samples == 44100


def _sub_bass_ratio(audio: np.ndarray, sample_rate: int = 44100) -> float:
    audio = np.asarray(audio, dtype=np.float64).reshape(-1)
    if audio.size == 0 or not np.any(audio):
        return 0.0
    power = np.abs(np.fft.rfft(audio)) ** 2
    total = float(np.sum(power))
    if total <= 1e-12:
        return 0.0
    freqs = np.fft.rfftfreq(audio.size, d=1.0 / sample_rate)
    return float(np.sum(power[freqs < 90.0]) / total)


def _sub_bass_power(audio: np.ndarray, sample_rate: int = 44100) -> float:
    audio = np.asarray(audio, dtype=np.float64).reshape(-1)
    if audio.size == 0 or not np.any(audio):
        return 0.0
    power = np.abs(np.fft.rfft(audio)) ** 2
    freqs = np.fft.rfftfreq(audio.size, d=1.0 / sample_rate)
    return float(np.sum(power[freqs < 90.0]))


def _high_band_ratio(audio: np.ndarray, sample_rate: int = 44100) -> float:
    audio = np.asarray(audio, dtype=np.float64).reshape(-1)
    if audio.size == 0 or not np.any(audio):
        return 0.0
    power = np.abs(np.fft.rfft(audio)) ** 2
    total = float(np.sum(power))
    if total <= 1e-12:
        return 0.0
    freqs = np.fft.rfftfreq(audio.size, d=1.0 / sample_rate)
    return float(np.sum(power[freqs > 5000.0]) / total)


def _library_with_dummy_guitar(sample_path: str = "dummy_guitar.wav") -> InstrumentLibrary:
    lib = InstrumentLibrary(instruments_dir=None, auto_load_audio=False)
    inst = AnalyzedInstrument(
        path=sample_path,
        name="Dummy Guitar",
        category=InstrumentCategory.GUITAR,
        profile=SonicProfile(
            sample_path=sample_path,
            sample_name="Dummy Guitar",
            category=InstrumentCategory.GUITAR.value,
            brightness=0.6,
            warmth=0.5,
            punch=0.7,
            richness=0.7,
        ),
        audio=np.linspace(-0.2, 0.2, 128, dtype=np.float32),
        sample_rate=44100,
    )
    lib.instruments[inst.path] = inst
    lib.by_category[InstrumentCategory.GUITAR].append(inst)
    return lib


def test_gm_guitar_programs_choose_guitar_cache_not_keys(monkeypatch):
    renderer = ProceduralRenderer(sample_rate=44100, genre="rock")
    guitar_variants = [{"audio": np.array([0.1]), "root_note": 60, "sample_rate": 44100}]
    keys_variants = [{"audio": np.array([0.9]), "root_note": 60, "sample_rate": 44100}]
    renderer._custom_melodic_cache = {"guitar": guitar_variants, "keys": keys_variants}
    seen = {}

    def fake_pitch_shift(sample_variants, target_pitch, duration, velocity):
        seen["sample_variants"] = sample_variants
        return np.array([0.123], dtype=np.float32)

    monkeypatch.setattr(renderer, "_pitch_shift_sample", fake_pitch_shift)

    out = renderer._synthesize_note(_note(program=30))

    assert seen["sample_variants"] is guitar_variants
    assert np.array_equal(out, np.array([0.123], dtype=np.float32))


def test_procedural_guitar_fallback_is_finite_and_zero_duration_safe():
    renderer = ProceduralRenderer(sample_rate=44100, genre="rock")

    rendered = renderer._synthesize_note(_note(program=30, duration_samples=2205))
    assert rendered.size > 0
    assert np.all(np.isfinite(rendered))
    assert np.max(np.abs(rendered)) <= 1.0

    direct = generate_guitar_tone(440.0, 0.05, 0.8)
    assert direct.size > 0
    assert np.all(np.isfinite(direct))

    zero = generate_guitar_tone(440.0, 0.0, 0.8)
    assert zero.size == 0
    assert np.all(np.isfinite(zero))


def test_custom_guitar_loading_and_render_report_include_guitar(tmp_path):
    guitar_sample = tmp_path / "dummy_guitar.wav"
    midi_path = tmp_path / "guitar_track.mid"
    _save_single_track_program_midi(midi_path, track_name="Guitar", program=29)

    parsed = ParsedPrompt(
        genre="rock",
        bpm=100,
        key="E",
        scale_type=ScaleType.MINOR,
        instruments=["guitar"],
        drum_elements=[],
    )
    renderer = AudioRenderer(
        sample_rate=44100,
        use_fluidsynth=False,
        soundfont_path=None,
        require_soundfont=False,
        instrument_library=_library_with_dummy_guitar(str(guitar_sample)),
        expansion_manager=None,
        genre=parsed.genre,
        mood=parsed.mood,
        use_bwf=False,
        parsed_instruments=parsed.instruments,
        resolved_sample_metadata=[
            {
                "category": "guitar",
                "name": "Dummy Guitar",
                "path": str(guitar_sample),
            }
        ],
    )

    assert renderer.procedural._custom_melodic_cache["guitar"]

    report = renderer._build_render_report(
        midi_path=str(midi_path),
        output_path="dummy.wav",
        parsed=parsed,
        renderer_path="procedural",
        fluidsynth_allowed=False,
        fluidsynth_attempted=False,
        fluidsynth_success=False,
        fluidsynth_skip_reason="disabled",
        warnings=[],
    )

    assert report["custom_audio"]["custom_melodic_loaded"]["guitar"] == 1
    assert [patch["patch_id"] for patch in report["instrument_patches"]] == [
        "core.guitar.track.v1"
    ]
    assert report["instrument_patches"][0]["patch_profile"]["family"] == "guitar"
    assert report["instrument_patches"][0]["sample_layers"][0]["path_hint"] == str(guitar_sample)
    assert report["track_realization_statuses"] == [
        {
            "track_index": 1,
            "track_name": "Guitar",
            "patch_id": "core.guitar.track.v1",
            "patch_family": "guitar",
            "preferred_realization": "sample_layer_hint",
            "actual_realization": "custom_sample",
            "uses_patch_sample_layer": True,
            "source_path": str(guitar_sample),
            "match_basis": "program_change",
            "notes": [],
        }
    ]


def test_render_report_track_realization_statuses_separate_patch_hint_from_rock_bass_runtime(tmp_path):
    bass_sample = tmp_path / "bass_hint.wav"
    midi_path = tmp_path / "bass_track.mid"
    _save_single_track_program_midi(midi_path, track_name="Bass", program=34, note=40)

    parsed = ParsedPrompt(
        genre="rock",
        bpm=100,
        key="E",
        scale_type=ScaleType.MINOR,
        instruments=["bass"],
        drum_elements=[],
    )
    renderer = AudioRenderer(
        sample_rate=44100,
        use_fluidsynth=False,
        soundfont_path=None,
        require_soundfont=False,
        instrument_library=None,
        expansion_manager=None,
        genre=parsed.genre,
        mood=parsed.mood,
        use_bwf=False,
        parsed_instruments=parsed.instruments,
        resolved_sample_metadata=[
            {
                "category": "bass",
                "name": "Bass Hint",
                "path": str(bass_sample),
            }
        ],
    )

    report = renderer._build_render_report(
        midi_path=str(midi_path),
        output_path="dummy.wav",
        parsed=parsed,
        renderer_path="procedural",
        fluidsynth_allowed=False,
        fluidsynth_attempted=False,
        fluidsynth_success=False,
        fluidsynth_skip_reason="disabled",
        warnings=[],
    )

    status = report["track_realization_statuses"][0]
    assert status["track_name"] == "Bass"
    assert status["patch_id"] == "core.bass.track.v1"
    assert status["patch_family"] == "bass"
    assert status["preferred_realization"] == "sample_layer_hint"
    assert status["actual_realization"] == "procedural_fallback"
    assert status["uses_patch_sample_layer"] is False
    assert status["source_path"] is None
    assert status["match_basis"] == "program_change"
    assert any("Rock-family bass programs are forced" in note for note in status["notes"])


def test_render_report_track_realization_statuses_report_fluidsynth_whole_file_truth(tmp_path):
    midi_path = tmp_path / "lead_track.mid"
    _save_single_track_program_midi(midi_path, track_name="Lead", program=81)

    parsed = ParsedPrompt(
        genre="pop",
        bpm=120,
        key="C",
        scale_type=ScaleType.MINOR,
        instruments=["synth"],
        drum_elements=[],
    )
    renderer = AudioRenderer(
        sample_rate=44100,
        use_fluidsynth=False,
        soundfont_path="C:/soundfonts/test.sf3",
        require_soundfont=False,
        instrument_library=None,
        expansion_manager=None,
        genre=parsed.genre,
        mood=parsed.mood,
        use_bwf=False,
        parsed_instruments=parsed.instruments,
    )

    report = renderer._build_render_report(
        midi_path=str(midi_path),
        output_path="dummy.wav",
        parsed=parsed,
        renderer_path="fluidsynth",
        fluidsynth_allowed=True,
        fluidsynth_attempted=True,
        fluidsynth_success=True,
        fluidsynth_skip_reason=None,
        warnings=[],
    )

    status = report["track_realization_statuses"][0]
    assert status["track_name"] == "Lead"
    assert status["actual_realization"] == "fluidsynth_soundfont"
    assert status["uses_patch_sample_layer"] is False
    assert status["source_path"] == "C:/soundfonts/test.sf3"
    assert any("whole-file SoundFont rendering" in note for note in status["notes"])


def test_procedural_drum_note_mapping_keeps_side_stick_and_clap_off_kick_path():
    renderer = ProceduralRenderer(sample_rate=44100, genre="trap")
    renderer._drum_cache["kick"] = np.array([1.0], dtype=np.float32)
    renderer._drum_cache["snare"] = np.array([2.0], dtype=np.float32)
    renderer._drum_cache["clap"] = np.array([3.0], dtype=np.float32)

    side_stick = renderer._get_drum_sample(37)
    clap = renderer._get_drum_sample(39)

    np.testing.assert_array_equal(side_stick, np.array([2.0], dtype=np.float32))
    np.testing.assert_array_equal(clap, np.array([3.0], dtype=np.float32))
    assert not np.array_equal(side_stick, renderer._drum_cache["kick"])
    assert not np.array_equal(clap, renderer._drum_cache["kick"])


def test_render_report_track_realization_statuses_match_krar_patch_by_canonical_identity(tmp_path):
    midi_path = tmp_path / "krar_track.mid"
    _save_single_track_program_midi(midi_path, track_name="Krar", program=110, note=60)

    parsed = ParsedPrompt(
        genre="ethio_jazz",
        bpm=120,
        key="C",
        scale_type=ScaleType.MINOR,
        instruments=["krar"],
        drum_elements=[],
    )
    renderer = AudioRenderer(
        sample_rate=44100,
        use_fluidsynth=False,
        soundfont_path=None,
        require_soundfont=False,
        instrument_library=None,
        expansion_manager=None,
        genre=parsed.genre,
        mood=parsed.mood,
        use_bwf=False,
        parsed_instruments=parsed.instruments,
    )

    report = renderer._build_render_report(
        midi_path=str(midi_path),
        output_path="dummy.wav",
        parsed=parsed,
        renderer_path="procedural",
        fluidsynth_allowed=False,
        fluidsynth_attempted=False,
        fluidsynth_success=False,
        fluidsynth_skip_reason="disabled",
        warnings=[],
    )

    assert [patch["patch_id"] for patch in report["instrument_patches"]] == [
        "ethiopian.krar.track.v1"
    ]
    assert report["track_realization_statuses"] == [
        {
            "track_index": 1,
            "track_name": "Krar",
            "patch_id": "ethiopian.krar.track.v1",
            "patch_family": "ethiopian_string",
            "preferred_realization": "fallback_only",
            "actual_realization": "procedural_fallback",
            "uses_patch_sample_layer": False,
            "source_path": None,
            "match_basis": "program_change",
            "notes": [],
        }
    ]


def test_ethiopian_prompt_guardrail_skips_generic_melodic_cache():
    renderer = ProceduralRenderer(
        sample_rate=44100,
        instrument_library=_library_with_dummy_guitar(),
        genre="ethiopian",
        parsed_instruments=["krar", "guitar"],
    )

    assert renderer._has_ethiopian_instruments is True
    assert renderer._custom_melodic_cache == {}


def test_rock_family_synth_bass_program_is_guarded_away_from_808(monkeypatch):
    renderer = ProceduralRenderer(sample_rate=44100, genre="rock")

    def fail_808(*args, **kwargs):
        raise AssertionError("rock bass must not render through generate_808_kick")

    monkeypatch.setattr("multimodal_gen.audio_renderer.generate_808_kick", fail_808)

    rendered = renderer._synthesize_note(_bass_note(program=38))

    assert rendered.size > 0
    assert np.all(np.isfinite(rendered))
    assert np.max(np.abs(rendered)) <= 1.0


def test_rock_electric_bass_bypasses_custom_bass_cache(monkeypatch):
    renderer = ProceduralRenderer(sample_rate=44100, genre="grunge")
    renderer._custom_melodic_cache = {
        "bass": [{"audio": np.array([0.9]), "root_note": 40, "sample_rate": 44100}]
    }

    def fail_pitch_shift(*args, **kwargs):
        raise AssertionError("rock bass must not use arbitrary custom bass samples")

    monkeypatch.setattr(renderer, "_pitch_shift_sample", fail_pitch_shift)

    rendered = renderer._synthesize_note(_bass_note(program=34))

    assert rendered.size > 0
    assert np.all(np.isfinite(rendered))
    assert np.max(np.abs(rendered)) <= 1.0


def test_non_rock_synth_bass_program_keeps_existing_808_path(monkeypatch):
    renderer = ProceduralRenderer(sample_rate=44100, genre="trap")
    sentinel = np.array([0.25, -0.25], dtype=np.float32)

    def fake_808(*args, **kwargs):
        return sentinel

    monkeypatch.setattr("multimodal_gen.audio_renderer.generate_808_kick", fake_808)

    rendered = renderer._synthesize_note(_bass_note(program=38))

    assert rendered is sentinel


def test_bass_track_name_infers_electric_bass_only_for_rock_family():
    rock_renderer = AudioRenderer(sample_rate=44100, use_fluidsynth=False, genre="alternative_rock")
    trap_renderer = AudioRenderer(sample_rate=44100, use_fluidsynth=False, genre="trap")

    assert rock_renderer._infer_program_from_track_name("Bass") == 34
    assert trap_renderer._infer_program_from_track_name("Bass") == 38


def test_rock_procedural_electric_bass_sequence_limits_sub_bass_energy():
    renderer = ProceduralRenderer(sample_rate=44100, genre="rock")
    notes = [
        renderer._synthesize_note(_bass_note(program=34, pitch=pitch, duration_samples=11025))
        for pitch in [40, 47, 52, 54] * 2
    ]
    audio = np.concatenate(notes)

    assert np.all(np.isfinite(audio))
    assert np.max(np.abs(audio)) <= 1.0
    assert _sub_bass_ratio(audio, 44100) < 0.16


def test_rock_fluidsynth_tone_shaping_tames_bright_soundfont_balance():
    renderer = AudioRenderer(sample_rate=44100, use_fluidsynth=False, genre="rock")
    duration = 1.0
    t = np.linspace(0, duration, int(44100 * duration), endpoint=False, dtype=np.float32)
    bright_mono = (
        0.35 * np.sin(2 * np.pi * 55.0 * t)
        + 0.22 * np.sin(2 * np.pi * 440.0 * t)
        + 0.18 * np.sin(2 * np.pi * 8000.0 * t)
    ).astype(np.float32)
    bright_stereo = np.stack([bright_mono, bright_mono], axis=-1)

    shaped = renderer._apply_rock_fluidsynth_tone_shaping(
        bright_stereo, 44100, "fluidsynth_file_mastering"
    )

    assert shaped.shape == bright_stereo.shape
    assert np.all(np.isfinite(shaped))
    assert _high_band_ratio(shaped[:, 0], 44100) < _high_band_ratio(bright_mono, 44100) * 0.45
    assert _sub_bass_power(shaped[:, 0], 44100) < _sub_bass_power(bright_mono, 44100)
    assert renderer._pipeline_stages["fluidsynth_file_mastering.tone_shaping"] == ROCK_TONE_DIAGNOSTIC
    assert renderer._pipeline_stages["fluidsynth_file_mastering.rock_tone_shaping"] == ROCK_TONE_DIAGNOSTIC
    assert renderer._pipeline_stages["fluidsynth_file_mastering.profile"] == "rock:rock"


def test_trap_fluidsynth_profile_does_not_apply_rock_tone_shaping():
    renderer = AudioRenderer(sample_rate=44100, use_fluidsynth=False, genre="trap")
    audio = np.full((256, 2), 0.125, dtype=np.float32)

    shaped = renderer._apply_rock_fluidsynth_tone_shaping(
        audio, 44100, "fluidsynth_file_mastering"
    )

    np.testing.assert_array_equal(shaped, audio)
    assert "fluidsynth_file_mastering.rock_tone_shaping" not in renderer._pipeline_stages
    assert "fluidsynth_file_mastering.tone_shaping" not in renderer._pipeline_stages
    assert renderer._pipeline_stages["fluidsynth_file_mastering.profile"] == (
        "trap_modern_beat:modern_beat"
    )


def test_lyrical_cinematic_contextual_profile_records_narrow_tonal_diagnostic():
    renderer = AudioRenderer(sample_rate=44100, use_fluidsynth=False, genre="cinematic")
    parsed = PromptParser().parse(LYRICAL_CINEMATIC_PIANO_PROMPT)
    duration = 1.0
    t = np.linspace(0, duration, int(44100 * duration), endpoint=False, dtype=np.float32)
    bright_mono = (
        0.22 * np.sin(2 * np.pi * 220.0 * t)
        + 0.20 * np.sin(2 * np.pi * 440.0 * t)
        + 0.18 * np.sin(2 * np.pi * 7200.0 * t)
    ).astype(np.float32)
    bright_stereo = np.stack([bright_mono, bright_mono], axis=-1)

    shaped = renderer._apply_fluidsynth_profile_tone_shaping(
        bright_stereo,
        44100,
        "fluidsynth_file_mastering",
        profile=renderer._resolve_fluidsynth_profile(parsed),
    )

    assert shaped.shape == bright_stereo.shape
    assert np.all(np.isfinite(shaped))
    assert _high_band_ratio(shaped[:, 0], 44100) < _high_band_ratio(bright_mono, 44100) * 0.9
    assert renderer._pipeline_stages["fluidsynth_file_mastering.profile"] == (
        "classical_lyrical_piano:classical"
    )
    assert renderer._pipeline_stages["fluidsynth_file_mastering.tone_shaping"] == (
        LYRICAL_CINEMATIC_TONE_DIAGNOSTIC
    )


def test_non_lyrical_cinematic_context_keeps_base_profile_without_tone_shaping():
    renderer = AudioRenderer(sample_rate=44100, use_fluidsynth=False, genre="cinematic")
    parsed = PromptParser().parse(
        "dark cinematic orchestral film score with sweeping strings, brass, french horn, choir, harp, and timpani, 72 BPM in D minor"
    )
    audio = np.full((256, 2), 0.125, dtype=np.float32)

    shaped = renderer._apply_fluidsynth_profile_tone_shaping(
        audio,
        44100,
        "fluidsynth_file_mastering",
        profile=renderer._resolve_fluidsynth_profile(parsed),
    )

    np.testing.assert_array_equal(shaped, audio)
    assert renderer._pipeline_stages["fluidsynth_file_mastering.profile"] == "classical:classical"
    assert "fluidsynth_file_mastering.tone_shaping" not in renderer._pipeline_stages


def test_edm_lead_programs_80_87_dispatch_to_bounded_unison_wavetable_path_with_distinct_bounded_presets(monkeypatch):
    renderer = ProceduralRenderer(sample_rate=44100, genre="edm")
    sentinel = np.array([0.4, -0.4], dtype=np.float32)
    calls = []

    def fake_unison(*args, **kwargs):
        calls.append({"args": args, "kwargs": kwargs})
        return sentinel

    def fail_standard_lead(*args, **kwargs):
        raise AssertionError("EDM fallback should dispatch to the bounded unison wavetable path")

    monkeypatch.setattr("multimodal_gen.audio_renderer.generate_unison_lead_tone", fake_unison)
    monkeypatch.setattr("multimodal_gen.audio_renderer.generate_lead_tone", fail_standard_lead)

    for program in range(80, 88):
        rendered = renderer._synthesize_note(_note(program=program))
        assert rendered is sentinel

    assert len(calls) == 8

    presets = []
    allowed_keys = {"voices", "detune_cents", "table_position", "table_motion"}
    for program, call in zip(range(80, 88), calls):
        kwargs = call["kwargs"]
        assert set(kwargs) == allowed_keys
        assert 1 <= kwargs["voices"] <= 11
        assert 0.0 <= kwargs["detune_cents"] <= 40.0
        assert 0.0 <= kwargs["table_position"] <= 1.0
        assert 0.0 <= kwargs["table_motion"] <= 1.0
        presets.append(
            (
                program,
                kwargs["voices"],
                kwargs["detune_cents"],
                kwargs["table_position"],
                kwargs["table_motion"],
            )
        )

    assert len({preset[1:] for preset in presets}) == 8
    assert presets[0][3] > presets[1][3]
    assert presets[0][4] < presets[1][4]


def test_non_edm_lead_programs_80_87_keep_existing_standard_lead_dispatch(monkeypatch):
    renderer = ProceduralRenderer(sample_rate=44100, genre="trap")
    sentinel = np.array([0.2, -0.2], dtype=np.float32)
    standard_calls = []

    def fail_unison(*args, **kwargs):
        raise AssertionError("Trap lead fallback should not dispatch to the bounded wavetable path")

    def fake_standard_lead(*args, **kwargs):
        standard_calls.append({"args": args, "kwargs": kwargs})
        return sentinel

    monkeypatch.setattr("multimodal_gen.audio_renderer.generate_unison_lead_tone", fail_unison)
    monkeypatch.setattr("multimodal_gen.audio_renderer.generate_lead_tone", fake_standard_lead)

    for program in range(80, 88):
        rendered = renderer._synthesize_note(_note(program=program))
        assert rendered is sentinel

    assert len(standard_calls) == 8


def test_neural_backend_opt_in_missing_model_fails_open_to_procedural(monkeypatch, tmp_path):
    midi_path = tmp_path / "neural_fallback.mid"
    _save_single_track_program_midi(midi_path, track_name="Lead", program=81)

    renderer = AudioRenderer(
        sample_rate=44100,
        use_fluidsynth=False,
        genre="pop",
        use_bwf=False,
        enable_neural_render=True,
        neural_backend=OptionalNeuralRuntime(enabled=True, model_path=None),
    )

    def fake_render_procedural(*_args, **_kwargs):
        sf.write(str(tmp_path / "out.wav"), np.zeros((128, 2), dtype=np.float32), 44100)
        return True

    monkeypatch.setattr(renderer, "_render_procedural", fake_render_procedural)
    monkeypatch.setattr(renderer, "_run_output_analysis", lambda *_args, **_kwargs: None)

    output_path = tmp_path / "out.wav"
    assert renderer.render_midi_file(str(midi_path), str(output_path)) is True

    report = renderer.get_last_render_report()
    assert report is not None
    assert report["renderer_path"] == "procedural"
    assert report["neural"]["enabled"] is True
    assert report["neural"]["success"] is False
    assert report["neural"]["skip_reason"] == "missing_model_path"


def test_renderer_path_becomes_neural_only_after_real_neural_render(monkeypatch, tmp_path):
    midi_path = tmp_path / "neural_success.mid"
    _save_single_track_program_midi(midi_path, track_name="Lead", program=81)

    model_path = tmp_path / "dummy_model.ckpt"
    model_path.write_text("stub", encoding="utf-8")

    def fake_neural_render(_midi_path, output_path, **_kwargs):
        tone = np.zeros((256, 2), dtype=np.float32)
        tone[:, 0] = 0.1
        tone[:, 1] = -0.1
        sf.write(output_path, tone, 44100)
        return True

    renderer = AudioRenderer(
        sample_rate=44100,
        use_fluidsynth=False,
        genre="pop",
        use_bwf=False,
        enable_neural_render=True,
        neural_backend=OptionalNeuralRuntime(
            enabled=True,
            model_path=str(model_path),
            required_dependencies=(),
            render_callback=fake_neural_render,
        ),
    )

    def fail_procedural(*_args, **_kwargs):
        raise AssertionError("Procedural fallback should not run after a real neural render success")

    monkeypatch.setattr(renderer, "_render_procedural", fail_procedural)
    monkeypatch.setattr(renderer, "_run_output_analysis", lambda *_args, **_kwargs: None)

    output_path = tmp_path / "neural.wav"
    assert renderer.render_midi_file(str(midi_path), str(output_path)) is True

    report = renderer.get_last_render_report()
    assert report is not None
    assert report["renderer_path"] == "neural"
    assert report["neural"]["attempted"] is True
    assert report["neural"]["success"] is True
    assert report["neural"]["skip_reason"] is None


def test_fluidsynth_file_level_mastering_integration(monkeypatch, tmp_path):
    """
    Integration test: FluidSynth success path applies file-level mastering.

    Monkeypatches render_midi_with_fluidsynth to write a simple WAV and return True,
    then verifies that the file-level mastering pipeline runs and is recorded.
    """
    import soundfile as sf

    # Create a simple loud WAV to be "rendered" by fake FluidSynth
    def fake_fluidsynth_render(midi_path, output_path, soundfont_path, sample_rate, **_kwargs):
        """Fake FluidSynth that writes a loud stereo WAV."""
        # Generate loud stereo audio (0.9 peak to test limiting)
        duration = 0.5
        samples = int(duration * sample_rate)
        t = np.linspace(0, duration, samples, dtype=np.float32)
        tone = 0.9 * np.sin(2 * np.pi * 440 * t)
        stereo = np.stack([tone, tone], axis=-1)
        sf.write(output_path, stereo, sample_rate, subtype='PCM_16')
        return True

    monkeypatch.setattr("multimodal_gen.audio_renderer.render_midi_with_fluidsynth", fake_fluidsynth_render)

    # Create renderer with FluidSynth enabled
    # Note: Must set these after construction because __init__ modifies use_fluidsynth based on availability
    renderer = AudioRenderer(sample_rate=44100, use_fluidsynth=False, genre="rock")
    renderer.fluidsynth_available = True
    renderer.use_fluidsynth = True
    renderer.soundfont_path = "fake.sf2"  # Non-empty to allow FluidSynth

    # Create fake MIDI file
    midi_path = tmp_path / "test.mid"
    midi_path.write_bytes(b"MThd" + b"\x00" * 20)  # Minimal fake MIDI header

    output_path = tmp_path / "output.wav"

    # Render
    parsed = ParsedPrompt(
        raw_prompt="rock song",
        bpm=120,
        key="C",
        scale_type=ScaleType.MAJOR,
        genre="rock",
        mood="energetic",
        target_bars=4,
        textures=[]
    )
    success = renderer.render_midi_file(str(midi_path), str(output_path), parsed)

    # Assertions
    assert success is True
    assert output_path.exists()

    # Check render report
    report = renderer._last_render_report
    assert report is not None
    assert report.get("renderer_path") == "fluidsynth"
    assert report.get("fluidsynth", {}).get("success") is True

    # Check pipeline_stages contains FluidSynth file mastering stages
    stages = report.get("pipeline_stages", {})
    assert "fluidsynth_file_mastering.status" in stages
    assert stages["fluidsynth_file_mastering.status"] == "applied"

    # Guard: profile diagnostic should always be recorded for file-level mastering.
    assert "fluidsynth_file_mastering.profile" in stages
    assert isinstance(stages["fluidsynth_file_mastering.profile"], str)

    # Should have at least auto_gain_staging and true_peak_limiter stages recorded
    # (or their error/fallback variants if modules unavailable)
    has_ags = any("auto_gain_staging" in k for k in stages)
    has_tpl = any("true_peak_limiter" in k for k in stages)
    assert has_ags, "Should record auto_gain_staging (or fallback normalization)"
    assert has_tpl, "Should record true_peak_limiter (or fallback limit)"

    # Verify output is finite and limited
    audio, sr = sf.read(str(output_path))
    assert np.all(np.isfinite(audio))
    peak = np.max(np.abs(audio))
    assert peak <= 1.0, f"Peak {peak} should be limited to <= 1.0"


def test_apply_file_level_mastering_unit(tmp_path):
    """
    Unit test for _apply_file_level_mastering() directly.

    Creates a loud WAV, calls the method, asserts output is limited and stages recorded.
    """
    import soundfile as sf

    renderer = AudioRenderer(sample_rate=44100, use_fluidsynth=False, genre="rock")

    # Create loud stereo WAV
    duration = 0.3
    samples = int(duration * 44100)
    t = np.linspace(0, duration, samples, dtype=np.float32)
    loud_tone = 1.5 * np.sin(2 * np.pi * 440 * t)  # Peak > 1.0
    stereo = np.stack([loud_tone, loud_tone], axis=-1)

    test_wav = tmp_path / "loud.wav"
    sf.write(str(test_wav), stereo, 44100, subtype='PCM_16')

    # Apply mastering
    result = renderer._apply_file_level_mastering(str(test_wav), parsed=None, stage_prefix="test_master")

    # Should succeed
    assert result is True

    # Check pipeline stages
    assert "test_master.status" in renderer._pipeline_stages
    assert renderer._pipeline_stages["test_master.status"] == "applied"

    # Verify output exists and is limited
    assert test_wav.exists()
    audio, sr = sf.read(str(test_wav))
    assert np.all(np.isfinite(audio))
    peak = np.max(np.abs(audio))
    assert peak <= 1.01, f"Mastered peak {peak} should be limited close to 1.0"

    # Should have at least one mastering stage beyond status
    stage_keys = [k for k in renderer._pipeline_stages.keys() if k.startswith("test_master.")]
    assert len(stage_keys) >= 2, f"Should have multiple stages recorded, got: {stage_keys}"


# ============================================================================
# FluidSynth Detection Tests (Windows portable fallback)
# ============================================================================

def test_resolve_fluidsynth_executable_prefers_env_override(monkeypatch, tmp_path):
    import multimodal_gen.fluidsynth_runtime as runtime_module

    repo_root = tmp_path / "MUSE"
    repo_root.mkdir()

    env_exe = tmp_path / "override" / "fluidsynth.exe"
    env_exe.parent.mkdir(parents=True)
    env_exe.write_bytes(b"exe")

    path_exe = tmp_path / "path" / "fluidsynth.exe"
    path_exe.parent.mkdir(parents=True)
    path_exe.write_bytes(b"exe")

    workspace_exe = tmp_path / "tools" / "fluidsynth-2.4.7-win10-x64" / "bin" / "fluidsynth.exe"
    workspace_exe.parent.mkdir(parents=True)
    workspace_exe.write_bytes(b"exe")

    monkeypatch.setattr(runtime_module, "_get_repo_root", lambda: repo_root)
    monkeypatch.setenv("MUSE_FLUIDSYNTH_EXE", str(env_exe))
    monkeypatch.setattr(runtime_module.shutil, "which", lambda _name: str(path_exe))

    assert runtime_module.resolve_fluidsynth_executable() == str(env_exe.resolve())


def test_resolve_fluidsynth_executable_prefers_path_over_workspace_tools(monkeypatch, tmp_path):
    import multimodal_gen.fluidsynth_runtime as runtime_module

    repo_root = tmp_path / "MUSE"
    repo_root.mkdir()

    path_exe = tmp_path / "path" / "fluidsynth.exe"
    path_exe.parent.mkdir(parents=True)
    path_exe.write_bytes(b"exe")

    workspace_exe = tmp_path / "tools" / "fluidsynth-2.4.7-win10-x64" / "bin" / "fluidsynth.exe"
    workspace_exe.parent.mkdir(parents=True)
    workspace_exe.write_bytes(b"exe")

    monkeypatch.setattr(runtime_module, "_get_repo_root", lambda: repo_root)
    monkeypatch.delenv("MUSE_FLUIDSYNTH_EXE", raising=False)
    monkeypatch.setattr(runtime_module.shutil, "which", lambda _name: str(path_exe))

    assert runtime_module.resolve_fluidsynth_executable() == str(path_exe.resolve())


def test_resolve_fluidsynth_executable_finds_workspace_tools_when_path_absent(monkeypatch, tmp_path):
    import multimodal_gen.fluidsynth_runtime as runtime_module

    repo_root = tmp_path / "MUSE"
    repo_root.mkdir()

    workspace_exe = tmp_path / "tools" / "fluidsynth-2.4.7-win10-x64" / "bin" / "fluidsynth.exe"
    workspace_exe.parent.mkdir(parents=True)
    workspace_exe.write_bytes(b"exe")

    monkeypatch.setattr(runtime_module, "_get_repo_root", lambda: repo_root)
    monkeypatch.delenv("MUSE_FLUIDSYNTH_EXE", raising=False)
    monkeypatch.setattr(runtime_module.shutil, "which", lambda _name: None)

    assert runtime_module.resolve_fluidsynth_executable() == str(workspace_exe.resolve())


def test_check_fluidsynth_available_with_long_option(monkeypatch):
    """Test detection when modern --version works."""
    from multimodal_gen.audio_renderer import check_fluidsynth_available
    import subprocess

    resolved_exe = "C:/portable/fluidsynth.exe"
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="FluidSynth 2.4.7\n", stderr="")

    monkeypatch.setattr("multimodal_gen.audio_renderer.resolve_fluidsynth_executable", lambda: resolved_exe)
    monkeypatch.setattr("subprocess.run", fake_run)

    available = check_fluidsynth_available()

    assert available is True
    assert calls == [[resolved_exe, "--version"]]


def test_check_fluidsynth_available_fallback_to_short_option(monkeypatch):
    """Test fallback to -V when --version fails (Windows portable build)."""
    from multimodal_gen.audio_renderer import check_fluidsynth_available
    import subprocess

    resolved_exe = "C:/portable/fluidsynth.exe"
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        if '--version' in cmd:
            # Windows portable build rejects long options
            result = subprocess.CompletedProcess(
                args=cmd,
                returncode=1,
                stdout="",
                stderr="This version was compiled without getopt support. Unknown switch.\n"
            )
        elif '-V' in cmd:
            # Short option works
            result = subprocess.CompletedProcess(args=cmd, returncode=0, stdout="FluidSynth 2.4.7\n", stderr="")
        else:
            result = subprocess.CompletedProcess(args=cmd, returncode=1, stdout="", stderr="")
        return result

    monkeypatch.setattr("multimodal_gen.audio_renderer.resolve_fluidsynth_executable", lambda: resolved_exe)
    monkeypatch.setattr("subprocess.run", fake_run)

    available = check_fluidsynth_available()

    assert available is True
    assert calls == [[resolved_exe, '--version'], [resolved_exe, '-V']]


def test_check_fluidsynth_not_found(monkeypatch):
    """Test when FluidSynth binary is not in PATH."""
    from multimodal_gen.audio_renderer import check_fluidsynth_available

    monkeypatch.setattr("multimodal_gen.audio_renderer.resolve_fluidsynth_executable", lambda: None)
    monkeypatch.setattr("subprocess.run", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("subprocess.run should not be called")))

    available = check_fluidsynth_available()

    assert available is False


def test_get_fluidsynth_version_with_long_option(monkeypatch):
    """Test version retrieval when modern --version works."""
    from multimodal_gen.audio_renderer import get_fluidsynth_version
    import subprocess

    resolved_exe = "C:/portable/fluidsynth.exe"
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="FluidSynth 2.4.7\n", stderr="")

    monkeypatch.setattr("multimodal_gen.audio_renderer.resolve_fluidsynth_executable", lambda: resolved_exe)
    monkeypatch.setattr("subprocess.run", fake_run)

    version = get_fluidsynth_version()

    assert version == "FluidSynth 2.4.7"
    assert calls == [[resolved_exe, "--version"]]


def test_get_fluidsynth_version_fallback_to_short_option(monkeypatch):
    """Test version retrieval with fallback to -V (Windows portable build)."""
    from multimodal_gen.audio_renderer import get_fluidsynth_version
    import subprocess

    resolved_exe = "C:/portable/fluidsynth.exe"
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        if '--version' in cmd:
            result = subprocess.CompletedProcess(
                args=cmd,
                returncode=1,
                stdout="",
                stderr="This version was compiled without getopt support.\n"
            )
        elif '-V' in cmd:
            result = subprocess.CompletedProcess(args=cmd, returncode=0, stdout="FluidSynth 2.4.7\n", stderr="")
        else:
            result = subprocess.CompletedProcess(args=cmd, returncode=1, stdout="", stderr="")
        return result

    monkeypatch.setattr("multimodal_gen.audio_renderer.resolve_fluidsynth_executable", lambda: resolved_exe)
    monkeypatch.setattr("subprocess.run", fake_run)

    version = get_fluidsynth_version()

    assert version == "FluidSynth 2.4.7"
    assert calls == [[resolved_exe, '--version'], [resolved_exe, '-V']]


def test_get_fluidsynth_version_not_found(monkeypatch):
    """Test version retrieval when FluidSynth binary is not in PATH."""
    from multimodal_gen.audio_renderer import get_fluidsynth_version

    monkeypatch.setattr("multimodal_gen.audio_renderer.resolve_fluidsynth_executable", lambda: None)
    monkeypatch.setattr("subprocess.run", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("subprocess.run should not be called")))

    version = get_fluidsynth_version()

    assert version is None


def test_find_soundfont_discovers_sf3_before_sf2(monkeypatch):
    """Test that find_soundfont discovers .sf3 files with priority over .sf2."""
    from multimodal_gen.audio_renderer import find_soundfont
    import os

    def fake_exists(path):
        # Simulate FluidR3Mono_GM.sf3 exists in assets/soundfonts/
        if path.endswith('FluidR3Mono_GM.sf3'):
            return True
        return False

    monkeypatch.setattr(os.path, 'exists', fake_exists)

    result = find_soundfont()

    assert result is not None
    assert result.endswith('FluidR3Mono_GM.sf3')
    assert 'assets' in result or 'soundfonts' in result


def test_find_soundfont_discovers_ms_basic_sf3(monkeypatch):
    """Test that find_soundfont discovers MS Basic.sf3."""
    from multimodal_gen.audio_renderer import find_soundfont
    import os

    def fake_exists(path):
        if path.endswith('MS Basic.sf3'):
            return True
        return False

    monkeypatch.setattr(os.path, 'exists', fake_exists)

    result = find_soundfont()

    assert result is not None
    assert result.endswith('MS Basic.sf3')


def test_find_soundfont_falls_back_to_sf2(monkeypatch):
    """Test that find_soundfont still discovers .sf2 files when .sf3 not available."""
    from multimodal_gen.audio_renderer import find_soundfont
    import os

    def fake_exists(path):
        # No .sf3 files exist, but FluidR3_GM.sf2 does
        if path.endswith('FluidR3_GM.sf2'):
            return True
        return False

    monkeypatch.setattr(os.path, 'exists', fake_exists)

    result = find_soundfont()

    assert result is not None
    assert result.endswith('FluidR3_GM.sf2')


def test_find_soundfont_returns_none_when_no_soundfont(monkeypatch):
    """Test that find_soundfont returns None when no soundfont exists."""
    from multimodal_gen.audio_renderer import find_soundfont
    import os

    def fake_exists(path):
        return False

    monkeypatch.setattr(os.path, 'exists', fake_exists)

    result = find_soundfont()

    assert result is None


def test_render_midi_with_fluidsynth_uses_options_before_files(monkeypatch, tmp_path):
    """Windows portable FluidSynth requires options before SoundFont/MIDI files."""
    from multimodal_gen.audio_renderer import render_midi_with_fluidsynth
    import os
    import subprocess

    captured = {}
    resolved_exe = str((tmp_path / "portable" / "fluidsynth.exe").resolve())
    midi_path = str(tmp_path / "song.mid")
    wav_path = str(tmp_path / "song.wav")
    sf_path = str(tmp_path / "FluidR3Mono_GM.sf3")

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        captured["kwargs"] = kwargs
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

    def fake_exists(path):
        return path == wav_path

    monkeypatch.setattr("multimodal_gen.audio_renderer.resolve_fluidsynth_executable", lambda: resolved_exe)
    monkeypatch.setattr("subprocess.run", fake_run)
    monkeypatch.setattr(os.path, "exists", fake_exists)

    assert render_midi_with_fluidsynth(midi_path, wav_path, sf_path, sample_rate=48000) is True

    cmd = captured["cmd"]
    assert "-ni" not in cmd
    assert cmd[:7] == [resolved_exe, "-n", "-i", "-F", wav_path, "-r", "48000"]
    assert cmd[-2:] == [sf_path, midi_path]
    assert captured["kwargs"]["timeout"] == 60