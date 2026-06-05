"""Focused main.py regressions for CLI duration wiring and render diagnostics persistence."""

import builtins
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import main as main_module
from multimodal_gen.instrument_patch import (
    build_track_scoped_instrument_patches,
    enrich_instrument_patches_with_resolved_samples,
)
from multimodal_gen.reference_matching import ReferenceProfile
from multimodal_gen.style_policy import MixPolicy


class DummyMidiFile:
    ticks_per_beat = 480
    tracks = []

    def save(self, path: str) -> None:
        Path(path).write_bytes(b"MThd")


class DummyMidiGenerator:
    def __init__(self, *args, **kwargs):
        pass

    def generate(self, *args, **kwargs):
        return DummyMidiFile()


class DummyArranger:
    def __init__(self, target_duration_seconds=None):
        self.target_duration_seconds = target_duration_seconds

    def create_arrangement(self, parsed):
        section = SimpleNamespace(
            section_type=SimpleNamespace(value="loop"),
            bars=getattr(parsed, "target_bars", 4) or 4,
            start_tick=0,
        )
        total_bars = section.bars
        return SimpleNamespace(
            sections=[section],
            total_bars=total_bars,
            total_ticks=total_bars * 4 * 480,
            bpm=parsed.bpm,
            time_signature=parsed.time_signature,
            tension_arc=None,
            chord_map={},
        )


class DummyAssetsGenerator:
    calls = []

    def __init__(self, *_args, **_kwargs):
        pass

    def generate_drum_kit(self, drum_elements=None):
        self.__class__.calls.append(list(drum_elements or []))
        return {}


class FailingGraphBuilder:
    def build_from_prompt(self, _parsed):
        raise RuntimeError("skip graph for focused test")


class DummyInstrumentResolutionService:
    def __init__(self, *args, **kwargs):
        pass


class VerboseDummyInstrumentResolutionService(DummyInstrumentResolutionService):
    def get_registry_stats(self):
        return {
            "total_instruments": 1,
            "expansion_programs_allocated": 1,
        }


class DummySessionGraph:
    def __init__(self):
        self.tracks = []
        self.sections = []
        self.groove_template = None
        self.midi_path = None
        self.audio_path = None

    def save_manifest(self, manifest_path):
        Path(manifest_path).write_text(json.dumps({"tracks": [], "sections": []}), encoding="utf-8")


class DummyGraphBuilder:
    def build_from_prompt(self, _parsed):
        return DummySessionGraph()

    def build_from_arrangement(self, session_graph, arrangement):
        session_graph.sections = arrangement.sections
        return session_graph


class QuietRenderer:
    def __init__(self, *args, **kwargs):
        pass

    def render_midi_file(self, midi_path, output_path, parsed):
        Path(output_path).write_bytes(b"RIFF")
        return True


class ParityRenderer:
    def __init__(self, *args, **kwargs):
        self._last_render_report = None
        self._parsed_instruments = list(kwargs.get("parsed_instruments") or [])
        self._resolved_sample_metadata = list(kwargs.get("resolved_sample_metadata") or [])

    def render_midi_file(self, midi_path, output_path, parsed):
        Path(output_path).write_bytes(b"RIFF")
        instrument_patches = enrich_instrument_patches_with_resolved_samples(
            build_track_scoped_instrument_patches(
                self._parsed_instruments,
                genre=parsed.genre,
            ),
            self._resolved_sample_metadata,
        )
        self._last_render_report = {
            "schema_version": 1,
            "renderer_path": "procedural",
            "midi_path": midi_path,
            "output_path": output_path,
            "prompt_meta": {
                "genre": parsed.genre,
                "bpm": parsed.bpm,
                "key": parsed.key,
            },
            "fluidsynth": {
                "available": False,
                "version": None,
                "enabled": False,
                "allowed": False,
                "attempted": False,
                "success": False,
                "skip_reason": "disabled",
            },
            "soundfont_path": None,
            "require_soundfont": False,
            "custom_audio": {
                "custom_drums_loaded": 0,
                "custom_melodic_loaded": {},
            },
            "instrument_library": {"loaded": False, "total_instruments": None, "categories": None, "sources": None},
            "expansions": {"loaded": False, "count": None, "expansions": None, "categories": None},
            "instrument_patches": [patch.to_dict() for patch in instrument_patches],
            "track_realization_statuses": [],
            "warnings": [],
            "production_preset": {
                "preset_values": None,
                "target_rms": None,
                "reverb_send": None,
            },
            "mix_policy": {
                "active": False,
                "saturation_type": None,
                "saturation_amount": None,
                "brightness_target": None,
                "warmth_target": None,
                "target_lufs": None,
                "master_ceiling_db": None,
                "stem_headroom_db": None,
                "drum_bus_fx": None,
                "bass_fx": None,
                "master_fx_chain": None,
            },
            "genre_normalized": (parsed.genre or "").lower().replace("-", "_").replace(" ", "_"),
            "pipeline_stages": {},
            "render_status": {
                "success": True,
                "current_stage": None,
                "failure": None,
            },
        }
        return True

    def get_last_render_report(self):
        return self._last_render_report

    def write_last_render_report(self, report_path):
        Path(report_path).write_text(json.dumps(self._last_render_report, indent=2), encoding="utf-8")
        return True


class ExplodingRenderer:
    def __init__(self, *args, **kwargs):
        self._last_render_report = None

    def render_midi_file(self, midi_path, output_path, parsed):
        self._last_render_report = {
            "schema_version": 1,
            "renderer_path": "none",
            "midi_path": midi_path,
            "output_path": output_path,
            "prompt_meta": {
                "genre": parsed.genre,
                "bpm": parsed.bpm,
                "key": parsed.key,
            },
            "fluidsynth": {
                "available": False,
                "version": None,
                "enabled": False,
                "allowed": False,
                "attempted": False,
                "success": False,
                "skip_reason": "disabled",
            },
            "soundfont_path": None,
            "require_soundfont": False,
            "custom_audio": {
                "custom_drums_loaded": 0,
                "custom_melodic_loaded": {},
            },
            "instrument_library": {"loaded": False, "total_instruments": None, "categories": None, "sources": None},
            "expansions": {"loaded": False, "count": None, "expansions": None, "categories": None},
            "warnings": ["Render exception: RuntimeError: synthetic step 5 failure"],
            "production_preset": {
                "preset_values": None,
                "target_rms": None,
                "reverb_send": None,
            },
            "mix_policy": {
                "active": False,
                "saturation_type": None,
                "saturation_amount": None,
                "brightness_target": None,
                "warmth_target": None,
                "target_lufs": None,
                "master_ceiling_db": None,
                "stem_headroom_db": None,
                "drum_bus_fx": None,
                "bass_fx": None,
                "master_fx_chain": None,
            },
            "genre_normalized": (parsed.genre or "").lower().replace("-", "_").replace(" ", "_"),
            "pipeline_stages": {},
            "render_status": {
                "success": False,
                "current_stage": "procedural_render",
                "failure": {
                    "reason": "render_exception",
                    "stage": "procedural_render",
                    "exception_type": "RuntimeError",
                    "exception_message": "synthetic step 5 failure",
                    "traceback": "Traceback (most recent call last):\nRuntimeError: synthetic step 5 failure\n",
                },
            },
        }
        raise RuntimeError("synthetic step 5 failure")

    def get_last_render_report(self):
        return self._last_render_report

    def write_last_render_report(self, report_path):
        Path(report_path).write_text(json.dumps(self._last_render_report, indent=2), encoding="utf-8")
        return True


def test_cli_duration_bars_reaches_run_generation(monkeypatch, tmp_path):
    captured = {}

    def fake_run_generation(*, duration_bars=None, **kwargs):
        captured["duration_bars"] = duration_bars
        return {
            "midi": None,
            "audio": None,
            "mpc": None,
            "stems": [],
            "samples": [],
            "takes": {},
            "comps": {},
            "seed": 123,
            "synthesis_params": {},
            "project_metadata": str(tmp_path / "project_metadata.json"),
        }

    monkeypatch.setattr(main_module, "run_generation", fake_run_generation)
    monkeypatch.setattr(sys, "argv", [
        "main.py",
        "smoke prompt",
        "--duration-bars",
        "8",
        "--output",
        str(tmp_path),
        "--no-banner",
    ])

    exit_code = main_module.main()

    assert exit_code == 0
    assert captured["duration_bars"] == 8


def test_cli_fluidsynth_isolation_flags_reach_run_generation(monkeypatch, tmp_path):
    captured = {}

    def fake_run_generation(**kwargs):
        captured.update(kwargs)
        return {
            "midi": None,
            "audio": str(tmp_path / "dummy.wav"),
            "mpc": None,
            "stems": [],
            "samples": [],
            "takes": {},
            "comps": {},
            "seed": 123,
            "synthesis_params": {},
            "project_metadata": str(tmp_path / "project_metadata.json"),
        }

    monkeypatch.setattr(main_module, "run_generation", fake_run_generation)
    monkeypatch.setattr(sys, "argv", [
        "main.py",
        "smoke prompt",
        "--output",
        str(tmp_path),
        "--no-banner",
        "--skip-default-instruments",
        "--skip-expansions",
        "--require-soundfont",
        "--soundfont",
        "assets/soundfonts/test.sf3",
    ])

    exit_code = main_module.main()

    assert exit_code == 0
    assert captured["skip_default_instruments"] is True
    assert captured["skip_expansions"] is True
    assert captured["require_soundfont"] is True
    assert captured["soundfont_path"] == "assets/soundfonts/test.sf3"


def test_cli_diagnose_audio_reports_resolved_fluidsynth_executable(monkeypatch, tmp_path, capsys):
    sandbox_main = tmp_path / "sandbox" / "main.py"
    sandbox_main.parent.mkdir(parents=True, exist_ok=True)

    fake_exe = str((tmp_path / "portable" / "fluidsynth.exe").resolve())
    fake_soundfont = str((sandbox_main.parent / "assets" / "soundfonts" / "FluidR3Mono_GM.sf3").resolve())

    import multimodal_gen.audio_renderer as audio_renderer_module
    import multimodal_gen.fluidsynth_runtime as fluidsynth_runtime_module

    monkeypatch.setattr(main_module, "__file__", str(sandbox_main))
    monkeypatch.setattr(audio_renderer_module, "check_fluidsynth_available", lambda executable=None: executable == fake_exe)
    monkeypatch.setattr(audio_renderer_module, "get_fluidsynth_version", lambda executable=None: "FluidSynth 2.4.7")
    monkeypatch.setattr(audio_renderer_module, "find_soundfont", lambda: fake_soundfont)
    monkeypatch.setattr(fluidsynth_runtime_module, "resolve_fluidsynth_executable", lambda: fake_exe)
    monkeypatch.setattr(sys, "argv", [
        "main.py",
        "--diagnose-audio",
        "--no-banner",
    ])

    exit_code = main_module.main()

    output = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert output["fluidsynth"]["available"] is True
    assert output["fluidsynth"]["executable"] == fake_exe
    assert output["fluidsynth"]["version"] == "FluidSynth 2.4.7"
    assert output["soundfont"]["discovered"] == fake_soundfont
    assert json.dumps(output)


def test_run_generation_persists_render_diagnostics_on_step5_exception(monkeypatch, tmp_path):
    output_dir = tmp_path / "out"
    output_dir.mkdir()

    sandbox_main = tmp_path / "sandbox" / "main.py"
    sandbox_main.parent.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(main_module, "__file__", str(sandbox_main))
    monkeypatch.setattr(main_module, "print_step", lambda *args, **kwargs: None)
    monkeypatch.setattr(main_module, "print_info", lambda *args, **kwargs: None)
    monkeypatch.setattr(main_module, "print_warning", lambda *args, **kwargs: None)
    monkeypatch.setattr(main_module, "print_success", lambda *args, **kwargs: None)
    monkeypatch.setattr(main_module, "print_parsed_prompt", lambda *args, **kwargs: None)
    monkeypatch.setattr(main_module, "validate_generation", lambda *args, **kwargs: SimpleNamespace(valid=True, violations=[]))
    monkeypatch.setattr(main_module, "Arranger", DummyArranger)
    monkeypatch.setattr(main_module, "SessionGraphBuilder", FailingGraphBuilder)
    monkeypatch.setattr(main_module, "MidiGenerator", DummyMidiGenerator)
    monkeypatch.setattr(main_module, "AssetsGenerator", DummyAssetsGenerator)
    monkeypatch.setattr(main_module, "AudioRenderer", ExplodingRenderer)
    monkeypatch.setattr(main_module, "generate_project_name", lambda _parsed: "test_project")
    monkeypatch.setattr(main_module, "set_instrument_service", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(main_module, "_run_quality_gate", lambda *args, **kwargs: None)
    monkeypatch.setattr(main_module, "HAS_STYLE_POLICY", False)
    monkeypatch.setattr(main_module, "compile_policy", None)
    monkeypatch.setattr(main_module, "HAS_AGENT_SYSTEM", False)
    monkeypatch.setattr(main_module, "_HAS_QUALITY_VALIDATOR", False)
    monkeypatch.setattr(main_module, "_HAS_FILE_ANALYSIS", False)
    monkeypatch.setattr(main_module, "_HAS_STEM_SEPARATION", False)

    import multimodal_gen.instrument_resolution as instrument_resolution_module

    monkeypatch.setattr(
        instrument_resolution_module,
        "InstrumentResolutionService",
        DummyInstrumentResolutionService,
    )

    results = main_module.run_generation(
        prompt="neo soul smoke test 88 bpm in D minor",
        output_dir=output_dir,
        verbose=False,
        use_bwf=False,
    )

    render_report = output_dir / "test_project_render_report.json"
    render_error = output_dir / "test_project_render_error.txt"

    assert results["audio"] is None
    assert results["render_report"] == str(render_report)
    assert results["render_error"] == str(render_error)
    assert render_report.exists()
    assert render_error.exists()

    report_data = json.loads(render_report.read_text(encoding="utf-8"))
    failure = report_data["render_status"]["failure"]
    assert failure["reason"] == "render_exception"
    assert failure["stage"] == "procedural_render"
    assert failure["exception_type"] == "RuntimeError"

    error_text = render_error.read_text(encoding="utf-8")
    assert "synthetic step 5 failure" in error_text
    assert "RuntimeError" in error_text
    assert "traceback:" in error_text


def test_run_generation_skip_isolation_avoids_default_instruments_and_expansions(monkeypatch, tmp_path):
    output_dir = tmp_path / "out"
    output_dir.mkdir()

    sandbox_main = tmp_path / "sandbox" / "main.py"
    sandbox_main.parent.mkdir(parents=True, exist_ok=True)
    default_instruments = sandbox_main.parent / "instruments"
    default_instruments.mkdir()
    (default_instruments / "placeholder.wav").write_bytes(b"RIFF")
    expansions_dir = sandbox_main.parent.parent / "expansions"
    expansions_dir.mkdir()

    cleared_services = []

    monkeypatch.setattr(main_module, "__file__", str(sandbox_main))
    monkeypatch.setattr(main_module, "print_step", lambda *args, **kwargs: None)
    monkeypatch.setattr(main_module, "print_info", lambda *args, **kwargs: None)
    monkeypatch.setattr(main_module, "print_warning", lambda *args, **kwargs: None)
    monkeypatch.setattr(main_module, "print_success", lambda *args, **kwargs: None)
    monkeypatch.setattr(main_module, "print_parsed_prompt", lambda *args, **kwargs: None)
    monkeypatch.setattr(main_module, "validate_generation", lambda *args, **kwargs: SimpleNamespace(valid=True, violations=[]))
    monkeypatch.setattr(main_module, "Arranger", DummyArranger)
    monkeypatch.setattr(main_module, "SessionGraphBuilder", FailingGraphBuilder)
    monkeypatch.setattr(main_module, "MidiGenerator", DummyMidiGenerator)
    monkeypatch.setattr(main_module, "AssetsGenerator", DummyAssetsGenerator)
    monkeypatch.setattr(main_module, "AudioRenderer", ExplodingRenderer)
    monkeypatch.setattr(main_module, "generate_project_name", lambda _parsed: "test_project")
    monkeypatch.setattr(main_module, "set_instrument_service", lambda service: cleared_services.append(service))
    monkeypatch.setattr(main_module, "_run_quality_gate", lambda *args, **kwargs: None)
    monkeypatch.setattr(main_module, "HAS_STYLE_POLICY", False)
    monkeypatch.setattr(main_module, "compile_policy", None)
    monkeypatch.setattr(main_module, "HAS_AGENT_SYSTEM", False)
    monkeypatch.setattr(main_module, "_HAS_QUALITY_VALIDATOR", False)
    monkeypatch.setattr(main_module, "_HAS_FILE_ANALYSIS", False)
    monkeypatch.setattr(main_module, "_HAS_STEM_SEPARATION", False)

    import multimodal_gen as multimodal_gen_module
    import multimodal_gen.instrument_resolution as instrument_resolution_module

    class ForbiddenExpansionManager:
        def __init__(self, *args, **kwargs):
            raise AssertionError("expansions should not load in isolation")

    class ForbiddenInstrumentLibrary:
        def __init__(self, *args, **kwargs):
            raise AssertionError("default instruments should not auto-load in isolation")

    class ForbiddenInstrumentResolutionService:
        def __init__(self, *args, **kwargs):
            raise AssertionError("instrument service should not auto-register expansions in isolation")

    def forbidden_load_multiple_libraries(*args, **kwargs):
        raise AssertionError("default instruments should not auto-load in isolation")

    monkeypatch.setattr(multimodal_gen_module, "ExpansionManager", ForbiddenExpansionManager, raising=False)
    monkeypatch.setattr(multimodal_gen_module, "InstrumentLibrary", ForbiddenInstrumentLibrary, raising=False)
    monkeypatch.setattr(multimodal_gen_module, "load_multiple_libraries", forbidden_load_multiple_libraries, raising=False)
    monkeypatch.setattr(
        instrument_resolution_module,
        "InstrumentResolutionService",
        ForbiddenInstrumentResolutionService,
    )

    results = main_module.run_generation(
        prompt="neo soul smoke test 88 bpm in D minor",
        output_dir=output_dir,
        verbose=False,
        use_bwf=False,
        skip_default_instruments=True,
        skip_expansions=True,
    )

    assert cleared_services == [None]
    assert results["audio"] is None
    assert results["render_report"] == str(output_dir / "test_project_render_report.json")


def test_run_generation_passes_parsed_drums_to_assets_and_metadata_excludes_absent_samples(monkeypatch, tmp_path):
    output_dir = tmp_path / "out"
    output_dir.mkdir()

    sandbox_main = tmp_path / "sandbox" / "main.py"
    sandbox_main.parent.mkdir(parents=True, exist_ok=True)

    class CapturingAssetsGenerator(DummyAssetsGenerator):
        calls = []

        def __init__(self, output_dir, *_args, **_kwargs):
            self.output_dir = Path(output_dir)
            self.output_dir.mkdir(parents=True, exist_ok=True)

        def generate_drum_kit(self, drum_elements=None):
            elements = list(drum_elements or [])
            self.__class__.calls.append(elements)
            samples = {}
            for key, filename in {
                "808": "808_kick.wav",
                "kick": "kick.wav",
                "snare": "snare.wav",
                "clap": "clap.wav",
                "hihat": "hihat_closed.wav",
                "hihat_open": "hihat_open.wav",
                "rim": "rim.wav",
            }.items():
                if key not in elements:
                    continue
                path = self.output_dir / filename
                path.write_bytes(b"RIFF")
                samples[key] = str(path)
            return samples

    monkeypatch.setattr(main_module, "__file__", str(sandbox_main))
    monkeypatch.setattr(main_module, "print_step", lambda *args, **kwargs: None)
    monkeypatch.setattr(main_module, "print_info", lambda *args, **kwargs: None)
    monkeypatch.setattr(main_module, "print_warning", lambda *args, **kwargs: None)
    monkeypatch.setattr(main_module, "print_success", lambda *args, **kwargs: None)
    monkeypatch.setattr(main_module, "print_parsed_prompt", lambda *args, **kwargs: None)
    monkeypatch.setattr(main_module, "validate_generation", lambda *args, **kwargs: SimpleNamespace(valid=True, violations=[]))
    monkeypatch.setattr(main_module, "Arranger", DummyArranger)
    monkeypatch.setattr(main_module, "SessionGraphBuilder", FailingGraphBuilder)
    monkeypatch.setattr(main_module, "MidiGenerator", DummyMidiGenerator)
    monkeypatch.setattr(main_module, "AssetsGenerator", CapturingAssetsGenerator)
    monkeypatch.setattr(main_module, "AudioRenderer", ExplodingRenderer)
    monkeypatch.setattr(main_module, "generate_project_name", lambda _parsed: "test_project")
    monkeypatch.setattr(main_module, "set_instrument_service", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(main_module, "_run_quality_gate", lambda *args, **kwargs: None)
    monkeypatch.setattr(main_module, "HAS_STYLE_POLICY", False)
    monkeypatch.setattr(main_module, "compile_policy", None)
    monkeypatch.setattr(main_module, "HAS_AGENT_SYSTEM", False)
    monkeypatch.setattr(main_module, "_HAS_QUALITY_VALIDATOR", False)
    monkeypatch.setattr(main_module, "_HAS_FILE_ANALYSIS", False)
    monkeypatch.setattr(main_module, "_HAS_STEM_SEPARATION", False)

    import multimodal_gen.instrument_resolution as instrument_resolution_module

    monkeypatch.setattr(
        instrument_resolution_module,
        "InstrumentResolutionService",
        DummyInstrumentResolutionService,
    )

    results = main_module.run_generation(
        prompt="classic rock Hammond organ with live drums at 100 BPM in E minor",
        output_dir=output_dir,
        verbose=False,
        use_bwf=False,
    )

    assert CapturingAssetsGenerator.calls == [["kick", "snare", "hihat", "hihat_open", "crash", "ride", "tom"]]
    sample_names = {Path(path).name for path in results["samples"]}
    assert sample_names == {"kick.wav", "snare.wav", "hihat_closed.wav", "hihat_open.wav"}
    assert "808_kick.wav" not in sample_names
    assert "clap.wav" not in sample_names

    metadata = json.loads(Path(results["project_metadata"]).read_text(encoding="utf-8"))
    metadata_sample_names = {
        Path(path).name
        for path in metadata["current"]["outputs"]["samples"]
    }
    assert metadata["current"]["parsed"]["genre"] == "classic_rock"
    assert "808" not in metadata["current"]["parsed"]["drum_elements"]
    assert "clap" not in metadata["current"]["parsed"]["drum_elements"]
    assert metadata_sample_names == sample_names
    assert "808_kick.wav" not in metadata_sample_names
    assert "clap.wav" not in metadata_sample_names


def test_run_generation_warns_honestly_when_adjective_smart_metadata_is_unavailable(monkeypatch, tmp_path):
    output_dir = tmp_path / "out"
    output_dir.mkdir()

    sandbox_main = tmp_path / "sandbox" / "main.py"
    sandbox_main.parent.mkdir(parents=True, exist_ok=True)
    expansions_dir = sandbox_main.parent.parent / "expansions"
    expansions_dir.mkdir()

    warnings = []
    expected_warning = (
        "Adjective-aware smart instrument metadata is unavailable in this build; "
        "continuing with the supported live instrument resolver flow."
    )

    class DummyPromptParser:
        def parse(self, prompt):
            return main_module.ParsedPrompt(
                genre="classic_rock",
                instruments=["guitar"],
                drum_elements=["kick", "snare", "hihat"],
                sonic_adjectives=["warm", "vintage"],
                raw_prompt=prompt,
            )

    class TruthyExpansionManager:
        def scan_expansions(self, _path):
            return 1

    original_import = builtins.__import__

    def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "multimodal_gen.instrument_index":
            raise AssertionError("dead instrument_index import attempted")
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    monkeypatch.setattr(main_module, "__file__", str(sandbox_main))
    monkeypatch.setattr(main_module, "PromptParser", DummyPromptParser)
    monkeypatch.setattr(main_module, "print_step", lambda *args, **kwargs: None)
    monkeypatch.setattr(main_module, "print_info", lambda *args, **kwargs: None)
    monkeypatch.setattr(main_module, "print_warning", lambda message: warnings.append(message))
    monkeypatch.setattr(main_module, "print_success", lambda *args, **kwargs: None)
    monkeypatch.setattr(main_module, "print_parsed_prompt", lambda *args, **kwargs: None)
    monkeypatch.setattr(main_module, "validate_generation", lambda *args, **kwargs: SimpleNamespace(valid=True, violations=[]))
    monkeypatch.setattr(main_module, "Arranger", DummyArranger)
    monkeypatch.setattr(main_module, "SessionGraphBuilder", DummyGraphBuilder)
    monkeypatch.setattr(main_module, "MidiGenerator", DummyMidiGenerator)
    monkeypatch.setattr(main_module, "AssetsGenerator", DummyAssetsGenerator)
    monkeypatch.setattr(main_module, "AudioRenderer", QuietRenderer)
    monkeypatch.setattr(main_module, "generate_project_name", lambda _parsed: "test_project")
    monkeypatch.setattr(main_module, "set_instrument_service", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(main_module, "_run_quality_gate", lambda *args, **kwargs: None)
    monkeypatch.setattr(main_module, "HAS_STYLE_POLICY", False)
    monkeypatch.setattr(main_module, "compile_policy", None)
    monkeypatch.setattr(main_module, "HAS_AGENT_SYSTEM", False)
    monkeypatch.setattr(main_module, "_HAS_QUALITY_VALIDATOR", False)
    monkeypatch.setattr(main_module, "_HAS_FILE_ANALYSIS", False)
    monkeypatch.setattr(main_module, "_HAS_STEM_SEPARATION", False)

    import multimodal_gen as multimodal_gen_module
    import multimodal_gen.instrument_resolution as instrument_resolution_module

    monkeypatch.setattr(multimodal_gen_module, "ExpansionManager", TruthyExpansionManager, raising=False)
    monkeypatch.setattr(
        instrument_resolution_module,
        "InstrumentResolutionService",
        VerboseDummyInstrumentResolutionService,
    )

    results = main_module.run_generation(
        prompt="warm vintage classic rock guitar with live drums",
        output_dir=output_dir,
        verbose=True,
        use_bwf=False,
        skip_default_instruments=True,
    )

    assert warnings == [expected_warning]
    assert "smart_instruments" not in results

    metadata = json.loads(Path(results["project_metadata"]).read_text(encoding="utf-8"))
    assert "smart_instruments" not in metadata["current"]["outputs"]


def test_run_generation_persists_instrument_patches_when_renderer_is_monkeypatched(monkeypatch, tmp_path):
    output_dir = tmp_path / "out"
    output_dir.mkdir()

    sandbox_main = tmp_path / "sandbox" / "main.py"
    sandbox_main.parent.mkdir(parents=True, exist_ok=True)

    class DummyPromptParser:
        def parse(self, prompt):
            return main_module.ParsedPrompt(
                genre="ethio_jazz",
                bpm=110,
                key="A",
                scale_type=main_module.ParsedPrompt.scale_type,
                instruments=["krar"],
                drum_elements=["kick"],
                raw_prompt=prompt,
            )

    monkeypatch.setattr(main_module, "__file__", str(sandbox_main))
    monkeypatch.setattr(main_module, "PromptParser", DummyPromptParser)
    monkeypatch.setattr(main_module, "print_step", lambda *args, **kwargs: None)
    monkeypatch.setattr(main_module, "print_info", lambda *args, **kwargs: None)
    monkeypatch.setattr(main_module, "print_warning", lambda *args, **kwargs: None)
    monkeypatch.setattr(main_module, "print_success", lambda *args, **kwargs: None)
    monkeypatch.setattr(main_module, "print_parsed_prompt", lambda *args, **kwargs: None)
    monkeypatch.setattr(main_module, "validate_generation", lambda *args, **kwargs: SimpleNamespace(valid=True, violations=[]))
    monkeypatch.setattr(main_module, "Arranger", DummyArranger)
    monkeypatch.setattr(main_module, "SessionGraphBuilder", DummyGraphBuilder)
    monkeypatch.setattr(main_module, "MidiGenerator", DummyMidiGenerator)
    monkeypatch.setattr(main_module, "AssetsGenerator", DummyAssetsGenerator)
    monkeypatch.setattr(main_module, "AudioRenderer", QuietRenderer)
    monkeypatch.setattr(main_module, "generate_project_name", lambda _parsed: "test_project")
    monkeypatch.setattr(main_module, "set_instrument_service", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(main_module, "_run_quality_gate", lambda *args, **kwargs: None)
    monkeypatch.setattr(main_module, "HAS_STYLE_POLICY", False)
    monkeypatch.setattr(main_module, "compile_policy", None)
    monkeypatch.setattr(main_module, "HAS_AGENT_SYSTEM", False)
    monkeypatch.setattr(main_module, "_HAS_QUALITY_VALIDATOR", False)
    monkeypatch.setattr(main_module, "_HAS_FILE_ANALYSIS", False)
    monkeypatch.setattr(main_module, "_HAS_STEM_SEPARATION", False)

    results = main_module.run_generation(
        prompt="krar melody smoke test",
        output_dir=output_dir,
        verbose=False,
        use_bwf=False,
        skip_default_instruments=True,
        skip_expansions=True,
    )

    assert [patch["patch_id"] for patch in results["instrument_patches"]] == [
        "ethiopian.krar.track.v1"
    ]

    metadata = json.loads(Path(results["project_metadata"]).read_text(encoding="utf-8"))
    assert [patch["patch_id"] for patch in metadata["current"]["outputs"]["instrument_patches"]] == [
        "ethiopian.krar.track.v1"
    ]


def test_run_generation_enriches_instrument_patches_after_resolved_samples_are_known(monkeypatch, tmp_path):
    output_dir = tmp_path / "out"
    output_dir.mkdir()

    sandbox_main = tmp_path / "sandbox" / "main.py"
    sandbox_main.parent.mkdir(parents=True, exist_ok=True)

    instruments_dir = tmp_path / "instrument_pool"
    instruments_dir.mkdir()
    guitar_sample = instruments_dir / "crunch_guitar.wav"
    guitar_sample.write_bytes(b"RIFF")

    class DummyPromptParser:
        def parse(self, prompt):
            return main_module.ParsedPrompt(
                genre="rock",
                bpm=100,
                key="E",
                scale_type=main_module.ParsedPrompt.scale_type,
                instruments=["guitar"],
                drum_elements=[],
                raw_prompt=prompt,
            )

    class DummyInstrumentLibrary:
        def __init__(self, *args, **kwargs):
            pass

        def discover_and_analyze(self):
            return 1

        def list_categories(self):
            return {"guitar": 1}

    class DummyInstrumentMatcher:
        def __init__(self, _library):
            pass

        def get_recommendations(self, genre, mood=None):
            instrument = SimpleNamespace(
                name="Crunch Guitar",
                path=str(guitar_sample),
                source="test_source",
            )
            return {"guitar": [(instrument, 0.97)]}

    monkeypatch.setattr(main_module, "__file__", str(sandbox_main))
    monkeypatch.setattr(main_module, "PromptParser", DummyPromptParser)
    monkeypatch.setattr(main_module, "print_step", lambda *args, **kwargs: None)
    monkeypatch.setattr(main_module, "print_info", lambda *args, **kwargs: None)
    monkeypatch.setattr(main_module, "print_warning", lambda *args, **kwargs: None)
    monkeypatch.setattr(main_module, "print_success", lambda *args, **kwargs: None)
    monkeypatch.setattr(main_module, "print_parsed_prompt", lambda *args, **kwargs: None)
    monkeypatch.setattr(main_module, "validate_generation", lambda *args, **kwargs: SimpleNamespace(valid=True, violations=[]))
    monkeypatch.setattr(main_module, "Arranger", DummyArranger)
    monkeypatch.setattr(main_module, "SessionGraphBuilder", DummyGraphBuilder)
    monkeypatch.setattr(main_module, "MidiGenerator", DummyMidiGenerator)
    monkeypatch.setattr(main_module, "AssetsGenerator", DummyAssetsGenerator)
    monkeypatch.setattr(main_module, "AudioRenderer", QuietRenderer)
    monkeypatch.setattr(main_module, "generate_project_name", lambda _parsed: "test_project")
    monkeypatch.setattr(main_module, "set_instrument_service", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(main_module, "_run_quality_gate", lambda *args, **kwargs: None)
    monkeypatch.setattr(main_module, "HAS_STYLE_POLICY", False)
    monkeypatch.setattr(main_module, "compile_policy", None)
    monkeypatch.setattr(main_module, "HAS_AGENT_SYSTEM", False)
    monkeypatch.setattr(main_module, "_HAS_QUALITY_VALIDATOR", False)
    monkeypatch.setattr(main_module, "_HAS_FILE_ANALYSIS", False)
    monkeypatch.setattr(main_module, "_HAS_STEM_SEPARATION", False)

    import multimodal_gen as multimodal_gen_module

    monkeypatch.setattr(multimodal_gen_module, "InstrumentLibrary", DummyInstrumentLibrary, raising=False)
    monkeypatch.setattr(multimodal_gen_module, "InstrumentMatcher", DummyInstrumentMatcher, raising=False)

    results = main_module.run_generation(
        prompt="rock guitar sample hint smoke test",
        output_dir=output_dir,
        verbose=False,
        use_bwf=False,
        instruments_paths=[str(instruments_dir)],
        skip_default_instruments=True,
        skip_expansions=True,
    )

    assert results["instruments_used"] == [
        {
            "category": "guitar",
            "name": "Crunch Guitar",
            "score": 0.97,
            "path": str(guitar_sample),
            "source": "test_source",
        }
    ]
    assert [patch["patch_id"] for patch in results["instrument_patches"]] == [
        "core.guitar.track.v1"
    ]
    assert len(results["instrument_patches"][0]["sample_layers"]) == 1
    assert results["instrument_patches"][0]["sample_layers"][0]["path_hint"] == str(guitar_sample)

    metadata = json.loads(Path(results["project_metadata"]).read_text(encoding="utf-8"))
    metadata_patch = metadata["current"]["outputs"]["instrument_patches"][0]
    assert len(metadata_patch["sample_layers"]) == 1
    assert metadata_patch["sample_layers"][0]["path_hint"] == str(guitar_sample)


def test_run_generation_render_report_matches_main_enriched_instrument_patch_view(monkeypatch, tmp_path):
    output_dir = tmp_path / "out"
    output_dir.mkdir()

    sandbox_main = tmp_path / "sandbox" / "main.py"
    sandbox_main.parent.mkdir(parents=True, exist_ok=True)

    instruments_dir = tmp_path / "instrument_pool"
    instruments_dir.mkdir()
    guitar_sample = instruments_dir / "crunch_guitar.wav"
    guitar_sample.write_bytes(b"RIFF")

    class DummyPromptParser:
        def parse(self, prompt):
            return main_module.ParsedPrompt(
                genre="rock",
                bpm=100,
                key="E",
                scale_type=main_module.ParsedPrompt.scale_type,
                instruments=["guitar"],
                drum_elements=[],
                raw_prompt=prompt,
            )

    class DummyInstrumentLibrary:
        def __init__(self, *args, **kwargs):
            pass

        def discover_and_analyze(self):
            return 1

        def list_categories(self):
            return {"guitar": 1}

    class DummyInstrumentMatcher:
        def __init__(self, _library):
            pass

        def get_recommendations(self, genre, mood=None):
            instrument = SimpleNamespace(
                name="Crunch Guitar",
                path=str(guitar_sample),
                source="test_source",
            )
            return {"guitar": [(instrument, 0.97)]}

    monkeypatch.setattr(main_module, "__file__", str(sandbox_main))
    monkeypatch.setattr(main_module, "PromptParser", DummyPromptParser)
    monkeypatch.setattr(main_module, "print_step", lambda *args, **kwargs: None)
    monkeypatch.setattr(main_module, "print_info", lambda *args, **kwargs: None)
    monkeypatch.setattr(main_module, "print_warning", lambda *args, **kwargs: None)
    monkeypatch.setattr(main_module, "print_success", lambda *args, **kwargs: None)
    monkeypatch.setattr(main_module, "print_parsed_prompt", lambda *args, **kwargs: None)
    monkeypatch.setattr(main_module, "validate_generation", lambda *args, **kwargs: SimpleNamespace(valid=True, violations=[]))
    monkeypatch.setattr(main_module, "Arranger", DummyArranger)
    monkeypatch.setattr(main_module, "SessionGraphBuilder", DummyGraphBuilder)
    monkeypatch.setattr(main_module, "MidiGenerator", DummyMidiGenerator)
    monkeypatch.setattr(main_module, "AssetsGenerator", DummyAssetsGenerator)
    monkeypatch.setattr(main_module, "AudioRenderer", ParityRenderer)
    monkeypatch.setattr(main_module, "generate_project_name", lambda _parsed: "test_project")
    monkeypatch.setattr(main_module, "set_instrument_service", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(main_module, "_run_quality_gate", lambda *args, **kwargs: None)
    monkeypatch.setattr(main_module, "HAS_STYLE_POLICY", False)
    monkeypatch.setattr(main_module, "compile_policy", None)
    monkeypatch.setattr(main_module, "HAS_AGENT_SYSTEM", False)
    monkeypatch.setattr(main_module, "_HAS_QUALITY_VALIDATOR", False)
    monkeypatch.setattr(main_module, "_HAS_FILE_ANALYSIS", False)
    monkeypatch.setattr(main_module, "_HAS_STEM_SEPARATION", False)

    import multimodal_gen as multimodal_gen_module

    monkeypatch.setattr(multimodal_gen_module, "InstrumentLibrary", DummyInstrumentLibrary, raising=False)
    monkeypatch.setattr(multimodal_gen_module, "InstrumentMatcher", DummyInstrumentMatcher, raising=False)

    results = main_module.run_generation(
        prompt="rock guitar render report parity smoke test",
        output_dir=output_dir,
        verbose=False,
        use_bwf=False,
        instruments_paths=[str(instruments_dir)],
        skip_default_instruments=True,
        skip_expansions=True,
    )

    render_report_path = Path(results["render_report"])
    assert render_report_path.exists()

    render_report = json.loads(render_report_path.read_text(encoding="utf-8"))
    assert render_report["instrument_patches"] == results["instrument_patches"]
    assert render_report["instrument_patches"][0]["sample_layers"][0]["path_hint"] == str(guitar_sample)
    assert isinstance(render_report["track_realization_statuses"], list)


def _missing_audio_results(tmp_path):
    render_report = tmp_path / "failed_render_report.json"
    render_report.write_text(
        json.dumps({"render_status": {"success": False, "failure": {"reason": "render_exception"}}}),
        encoding="utf-8",
    )
    return {
        "midi": str(tmp_path / "smoke.mid"),
        "audio": None,
        "mpc": None,
        "stems": [],
        "samples": [],
        "takes": {},
        "comps": {},
        "seed": 123,
        "synthesis_params": {},
        "render_report": str(render_report),
        "project_metadata": str(tmp_path / "project_metadata.json"),
    }


def _write_refine_metadata(tmp_path, *, seed=123):
    metadata_path = tmp_path / "project_metadata.json"
    metadata_path.write_text(
        json.dumps(
            {
                "original_seed": seed,
                "current": {
                    "prompt": "neo soul smoke test 88 bpm in D minor",
                    "parsed": {
                        "bpm": 88,
                        "key": "D",
                        "genre": "neo_soul",
                    },
                },
            }
        ),
        encoding="utf-8",
    )
    return metadata_path


def test_cli_require_audio_returns_code_2_and_json_failure(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(main_module, "run_generation", lambda **_kwargs: _missing_audio_results(tmp_path))
    monkeypatch.setattr(sys, "argv", [
        "main.py",
        "neo soul smoke test 88 bpm in D minor",
        "--output",
        str(tmp_path),
        "--no-banner",
        "--json",
        "--require-audio",
    ])

    exit_code = main_module.main()

    output = json.loads(capsys.readouterr().out)
    assert exit_code == 2
    assert output["success"] is False
    assert output["results"]["audio"] is None


def test_cli_missing_audio_default_remains_success(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(main_module, "run_generation", lambda **_kwargs: _missing_audio_results(tmp_path))
    monkeypatch.setattr(sys, "argv", [
        "main.py",
        "neo soul smoke test 88 bpm in D minor",
        "--output",
        str(tmp_path),
        "--no-banner",
        "--json",
    ])

    exit_code = main_module.main()

    output = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert output["success"] is True
    assert output["results"]["audio"] is None


def test_cli_json_routes_progress_logs_to_stderr_on_success(monkeypatch, tmp_path, capsys):
    progress_token = "progress: rendered step 4/6"

    def fake_run_generation(**_kwargs):
        print(progress_token)
        return {
            "midi": str(tmp_path / "smoke.mid"),
            "audio": str(tmp_path / "smoke.wav"),
            "mpc": None,
            "stems": [],
            "samples": [],
            "takes": {},
            "comps": {},
            "seed": 123,
            "synthesis_params": {},
            "project_metadata": str(tmp_path / "project_metadata.json"),
        }

    monkeypatch.setattr(main_module, "run_generation", fake_run_generation)
    monkeypatch.setattr(sys, "argv", [
        "main.py",
        "neo soul smoke test 88 bpm in D minor",
        "--output",
        str(tmp_path),
        "--no-banner",
        "--json",
    ])

    exit_code = main_module.main()

    captured = capsys.readouterr()
    output = json.loads(captured.out)
    assert exit_code == 0
    assert output["success"] is True
    assert progress_token not in captured.out
    assert progress_token in captured.err


def test_cli_json_routes_progress_logs_to_stderr_on_error(monkeypatch, tmp_path, capsys):
    progress_token = "progress: rendered step 4/6"

    def fake_run_generation(**_kwargs):
        print(progress_token)
        raise RuntimeError("boom during render")

    monkeypatch.setattr(main_module, "run_generation", fake_run_generation)
    monkeypatch.setattr(sys, "argv", [
        "main.py",
        "neo soul smoke test 88 bpm in D minor",
        "--output",
        str(tmp_path),
        "--no-banner",
        "--json",
    ])

    exit_code = main_module.main()

    captured = capsys.readouterr()
    output = json.loads(captured.out)
    assert exit_code == 1
    assert output["success"] is False
    assert output["error"] == "boom during render"
    assert progress_token not in captured.out
    assert progress_token in captured.err


def test_cli_refine_json_routes_progress_logs_to_stderr_on_success(monkeypatch, tmp_path, capsys):
    metadata_path = _write_refine_metadata(tmp_path)
    progress_token = "progress: refined step 4/6"

    def fake_run_generation(**_kwargs):
        print(progress_token)
        return {
            "midi": str(tmp_path / "refined.mid"),
            "audio": str(tmp_path / "refined.wav"),
            "mpc": None,
            "stems": [],
            "samples": [],
            "takes": {},
            "comps": {},
            "seed": 123,
            "synthesis_params": {},
            "project_metadata": str(metadata_path),
        }

    monkeypatch.setattr(main_module, "run_generation", fake_run_generation)
    monkeypatch.setattr(sys, "argv", [
        "main.py",
        "make the snare punchier",
        "--refine",
        str(metadata_path),
        "--output",
        str(tmp_path),
        "--no-banner",
        "--json",
    ])

    main_module.main()

    captured = capsys.readouterr()
    output = json.loads(captured.out)
    assert output["success"] is True
    assert output["results"]["audio"] == str(tmp_path / "refined.wav")
    assert output["metadata"] == str(metadata_path)
    assert progress_token not in captured.out
    assert progress_token in captured.err
    assert "Refining generation with original seed: 123" in captured.err
    assert "Refinement prompt: make the snare punchier" in captured.err


def test_cli_refine_json_routes_progress_logs_to_stderr_on_error(monkeypatch, tmp_path, capsys):
    metadata_path = _write_refine_metadata(tmp_path)
    progress_token = "progress: refined step 4/6"

    def fake_run_generation(**_kwargs):
        print(progress_token)
        raise RuntimeError("boom during refine")

    monkeypatch.setattr(main_module, "run_generation", fake_run_generation)
    monkeypatch.setattr(sys, "argv", [
        "main.py",
        "make the snare punchier",
        "--refine",
        str(metadata_path),
        "--output",
        str(tmp_path),
        "--no-banner",
        "--json",
    ])

    try:
        main_module.main()
        raise AssertionError("Expected refine failure to exit")
    except SystemExit as exc:
        assert exc.code == 1

    captured = capsys.readouterr()
    output = json.loads(captured.out)
    assert output["success"] is False
    assert output["error"] == "boom during refine"
    assert progress_token not in captured.out
    assert progress_token in captured.err
    assert "Refining generation with original seed: 123" in captured.err
    assert "Refinement failed:" not in captured.err


def test_cli_json_omits_private_bridge_objects_without_mutating_live_results(monkeypatch, tmp_path, capsys):
    mix_policy = MixPolicy(saturation_type="tube")
    reference_profile = ReferenceProfile(name="ref")
    live_results = {
        "midi": str(tmp_path / "smoke.mid"),
        "audio": str(tmp_path / "smoke.wav"),
        "mpc": None,
        "stems": [],
        "samples": [],
        "takes": {},
        "comps": {},
        "seed": 123,
        "synthesis_params": {},
        "project_metadata": str(tmp_path / "project_metadata.json"),
        "_mix_policy_obj": mix_policy,
        "_reference_profile_obj": reference_profile,
        "_preset_values": {"humanize_amount": 0.7},
    }

    monkeypatch.setattr(main_module, "run_generation", lambda **_kwargs: live_results)
    monkeypatch.setattr(sys, "argv", [
        "main.py",
        "neo soul smoke test 88 bpm in D minor",
        "--output",
        str(tmp_path),
        "--no-banner",
        "--json",
    ])

    exit_code = main_module.main()

    output = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert output["success"] is True
    assert "_mix_policy_obj" not in output["results"]
    assert "_reference_profile_obj" not in output["results"]
    assert "_preset_values" not in output["results"]
    assert live_results["_mix_policy_obj"] is mix_policy
    assert live_results["_reference_profile_obj"] is reference_profile
    assert live_results["_preset_values"] == {"humanize_amount": 0.7}


def test_save_project_metadata_omits_private_bridge_objects_without_stringifying_them(tmp_path):
    output_dir = tmp_path / "out"
    output_dir.mkdir()

    mix_policy = MixPolicy(saturation_type="tube")
    reference_profile = ReferenceProfile(name="ref")
    results = {
        "midi": str(output_dir / "smoke.mid"),
        "audio": None,
        "mpc": None,
        "stems": [],
        "samples": [],
        "takes": {},
        "comps": {},
        "seed": 123,
        "synthesis_params": {},
        "_mix_policy_obj": mix_policy,
        "_reference_profile_obj": reference_profile,
        "_preset_values": {"humanize_amount": 0.7},
    }
    parsed = main_module.ParsedPrompt(
        raw_prompt="neo soul smoke test 88 bpm in D minor",
        genre="neo_soul",
        instruments=["piano"],
        drum_elements=["kick"],
    )

    metadata_path = main_module.save_project_metadata(
        output_dir=output_dir,
        prompt=parsed.raw_prompt,
        results=results,
        parsed=parsed,
        seed=123,
        synthesis_params=results["synthesis_params"],
    )

    metadata_text = metadata_path.read_text(encoding="utf-8")
    metadata = json.loads(metadata_text)
    outputs = metadata["current"]["outputs"]

    assert "_mix_policy_obj" not in outputs
    assert "_reference_profile_obj" not in outputs
    assert "_preset_values" not in outputs
    assert "MixPolicy(" not in metadata_text
    assert "ReferenceProfile(" not in metadata_text
    assert results["_mix_policy_obj"] is mix_policy
    assert results["_reference_profile_obj"] is reference_profile
    assert results["_preset_values"] == {"humanize_amount": 0.7}