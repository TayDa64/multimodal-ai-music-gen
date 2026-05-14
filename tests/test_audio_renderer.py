"""Focused regressions for first-class guitar rendering/routing."""

import mido
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


def test_fluidsynth_file_level_mastering_integration(monkeypatch, tmp_path):
    """
    Integration test: FluidSynth success path applies file-level mastering.

    Monkeypatches render_midi_with_fluidsynth to write a simple WAV and return True,
    then verifies that the file-level mastering pipeline runs and is recorded.
    """
    import soundfile as sf

    # Create a simple loud WAV to be "rendered" by fake FluidSynth
    def fake_fluidsynth_render(midi_path, output_path, soundfont_path, sample_rate):
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

def test_check_fluidsynth_available_with_long_option(monkeypatch):
    """Test detection when modern --version works."""
    from multimodal_gen.audio_renderer import check_fluidsynth_available
    import subprocess

    call_count = [0]

    def fake_run(cmd, **kwargs):
        call_count[0] += 1
        result = subprocess.CompletedProcess(args=cmd, returncode=0, stdout="FluidSynth 2.4.7\n", stderr="")
        return result

    monkeypatch.setattr("subprocess.run", fake_run)

    available = check_fluidsynth_available()

    assert available is True
    assert call_count[0] == 1  # Should succeed on first try


def test_check_fluidsynth_available_fallback_to_short_option(monkeypatch):
    """Test fallback to -V when --version fails (Windows portable build)."""
    from multimodal_gen.audio_renderer import check_fluidsynth_available
    import subprocess

    call_count = [0]

    def fake_run(cmd, **kwargs):
        call_count[0] += 1
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

    monkeypatch.setattr("subprocess.run", fake_run)

    available = check_fluidsynth_available()

    assert available is True
    assert call_count[0] == 2  # Should try both options


def test_check_fluidsynth_not_found(monkeypatch):
    """Test when FluidSynth binary is not in PATH."""
    from multimodal_gen.audio_renderer import check_fluidsynth_available

    def fake_run(cmd, **kwargs):
        raise FileNotFoundError("fluidsynth not found")

    monkeypatch.setattr("subprocess.run", fake_run)

    available = check_fluidsynth_available()

    assert available is False


def test_get_fluidsynth_version_with_long_option(monkeypatch):
    """Test version retrieval when modern --version works."""
    from multimodal_gen.audio_renderer import get_fluidsynth_version
    import subprocess

    def fake_run(cmd, **kwargs):
        result = subprocess.CompletedProcess(args=cmd, returncode=0, stdout="FluidSynth 2.4.7\n", stderr="")
        return result

    monkeypatch.setattr("subprocess.run", fake_run)

    version = get_fluidsynth_version()

    assert version == "FluidSynth 2.4.7"


def test_get_fluidsynth_version_fallback_to_short_option(monkeypatch):
    """Test version retrieval with fallback to -V (Windows portable build)."""
    from multimodal_gen.audio_renderer import get_fluidsynth_version
    import subprocess

    def fake_run(cmd, **kwargs):
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

    monkeypatch.setattr("subprocess.run", fake_run)

    version = get_fluidsynth_version()

    assert version == "FluidSynth 2.4.7"


def test_get_fluidsynth_version_not_found(monkeypatch):
    """Test version retrieval when FluidSynth binary is not in PATH."""
    from multimodal_gen.audio_renderer import get_fluidsynth_version

    def fake_run(cmd, **kwargs):
        raise FileNotFoundError("fluidsynth not found")

    monkeypatch.setattr("subprocess.run", fake_run)

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
    midi_path = str(tmp_path / "song.mid")
    wav_path = str(tmp_path / "song.wav")
    sf_path = str(tmp_path / "FluidR3Mono_GM.sf3")

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        captured["kwargs"] = kwargs
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

    def fake_exists(path):
        return path == wav_path

    monkeypatch.setattr("subprocess.run", fake_run)
    monkeypatch.setattr(os.path, "exists", fake_exists)

    assert render_midi_with_fluidsynth(midi_path, wav_path, sf_path, sample_rate=48000) is True

    cmd = captured["cmd"]
    assert "-ni" not in cmd
    assert cmd[:7] == ["fluidsynth", "-n", "-i", "-F", wav_path, "-r", "48000"]
    assert cmd[-2:] == [sf_path, midi_path]
    assert captured["kwargs"]["timeout"] == 60