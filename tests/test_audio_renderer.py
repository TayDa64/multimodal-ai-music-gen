"""Focused regressions for first-class guitar rendering/routing."""

import numpy as np

from multimodal_gen.assets_gen import generate_guitar_tone
from multimodal_gen.audio_renderer import AudioRenderer, ProceduralRenderer, SynthNote
from multimodal_gen.instrument_manager import (
    AnalyzedInstrument,
    InstrumentCategory,
    InstrumentLibrary,
    SonicProfile,
)
from multimodal_gen.prompt_parser import ParsedPrompt
from multimodal_gen.utils import ScaleType


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


def _library_with_dummy_guitar() -> InstrumentLibrary:
    lib = InstrumentLibrary(instruments_dir=None, auto_load_audio=False)
    inst = AnalyzedInstrument(
        path="dummy_guitar.wav",
        name="Dummy Guitar",
        category=InstrumentCategory.GUITAR,
        profile=SonicProfile(
            sample_path="dummy_guitar.wav",
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


def test_custom_guitar_loading_and_render_report_include_guitar():
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
        instrument_library=_library_with_dummy_guitar(),
        expansion_manager=None,
        genre=parsed.genre,
        mood=parsed.mood,
        use_bwf=False,
        parsed_instruments=parsed.instruments,
    )

    assert renderer.procedural._custom_melodic_cache["guitar"]

    report = renderer._build_render_report(
        midi_path="dummy.mid",
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
