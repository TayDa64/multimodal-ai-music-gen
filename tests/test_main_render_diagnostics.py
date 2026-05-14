"""Focused main.py regressions for CLI duration wiring and render diagnostics persistence."""

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import main as main_module


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
    def __init__(self, *_args, **_kwargs):
        pass

    def generate_drum_kit(self):
        return {}


class FailingGraphBuilder:
    def build_from_prompt(self, _parsed):
        raise RuntimeError("skip graph for focused test")


class DummyInstrumentResolutionService:
    def __init__(self, *args, **kwargs):
        pass


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