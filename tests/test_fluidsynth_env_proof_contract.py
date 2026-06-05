import argparse
import importlib.util
import json
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).parent.parent
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "fluidsynth_env_proof.py"


def _load_script_module():
    module_name = "fluidsynth_env_proof_under_test"
    sys.modules.pop(module_name, None)
    spec = importlib.util.spec_from_file_location(module_name, SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def test_load_fluidsynth_runtime_bootstraps_repo_root(monkeypatch):
    script = _load_script_module()
    repo_root = script._find_repo_root().resolve()

    filtered_sys_path = []
    for entry in sys.path:
        try:
            if Path(entry).resolve() == repo_root:
                continue
        except Exception:
            pass
        filtered_sys_path.append(entry)

    monkeypatch.setattr(sys, "path", filtered_sys_path)

    runtime_module = script._load_fluidsynth_runtime()

    assert Path(sys.path[0]).resolve() == repo_root
    assert runtime_module.__name__ == "multimodal_gen.fluidsynth_runtime"


def test_run_proof_uses_shared_resolver_without_path_prepend_and_records_json_contract(
    monkeypatch,
    tmp_path,
):
    script = _load_script_module()
    runtime_module = script._load_fluidsynth_runtime()

    resolved_executable = str((tmp_path / "fluidsynth.exe").resolve())
    soundfont = tmp_path / "proof.sf2"
    soundfont.write_bytes(b"sf2")

    probe_calls = []
    env_paths = []

    monkeypatch.setattr(runtime_module, "resolve_fluidsynth_executable", lambda: resolved_executable)

    def fake_probe(executable=None, *, timeout=3):
        probe_calls.append((executable, timeout))
        return executable, True, "FluidSynth 2.4.7"

    monkeypatch.setattr(runtime_module, "probe_fluidsynth", fake_probe)

    original_path = str(tmp_path / "system-bin")
    monkeypatch.setenv("PATH", original_path)

    def fake_run_command_capture(cmd, *, env, cwd):
        env_paths.append(env.get("PATH"))
        assert env.get("PATH") == original_path
        assert cwd == PROJECT_ROOT

        if "--diagnose-audio" in cmd:
            payload = {
                "fluidsynth": {
                    "available": True,
                    "executable": resolved_executable,
                    "version": "FluidSynth 2.4.7",
                },
                "soundfont": {
                    "discovered": str(soundfont),
                },
            }
            return subprocess.CompletedProcess(
                args=cmd,
                returncode=0,
                stdout=json.dumps(payload),
                stderr="",
            )

        assert "--json" in cmd
        output_dir = Path(cmd[cmd.index("--output") + 1])
        render_report_path = output_dir / "proof_render_report.json"
        render_report_path.write_text(
            json.dumps(
                {
                    "renderer_path": resolved_executable,
                    "soundfont_path": str(soundfont),
                    "fluidsynth": {"success": True},
                    "pipeline_stages": {
                        "fluidsynth_file_mastering.status": "applied",
                        "fluidsynth_file_mastering.profile": "rock:rock",
                        "fluidsynth_file_mastering.tone_shaping": "applied",
                        "fluidsynth_file_mastering.auto_gain_staging": "applied",
                        "fluidsynth_file_mastering.true_peak_limiter": "applied",
                    },
                }
            ),
            encoding="utf-8",
        )
        payload = {
            "success": True,
            "results": {
                "audio": str(output_dir / "proof.wav"),
                "midi": str(output_dir / "proof.mid"),
                "render_report": str(render_report_path),
            },
            "metadata": str(output_dir / "project_metadata.json"),
        }
        return subprocess.CompletedProcess(
            args=cmd,
            returncode=0,
            stdout=json.dumps(payload),
            stderr="progress on stderr",
        )

    monkeypatch.setattr(script, "_run_command_capture", fake_run_command_capture)

    args = argparse.Namespace(
        soundfont=str(soundfont),
        output_root=str(tmp_path / "proof-output"),
        prompt="rock proof harness contract",
        duration_bars=4,
        seed=20260605,
    )

    paths = script.run_proof(args)

    summary = json.loads(paths.summary_json.read_text(encoding="utf-8"))
    generation_payload = json.loads(paths.results_json.read_text(encoding="utf-8"))

    assert probe_calls == [(resolved_executable, 3)]
    assert env_paths == [original_path, original_path]
    assert summary["schema_version"] == 2
    assert summary["fluidsynth_executable"] == resolved_executable
    assert summary["fluidsynth_probe"] == {
        "executable": resolved_executable,
        "available": True,
        "version": "FluidSynth 2.4.7",
    }
    assert "fluidsynth_bin_prepended" not in summary
    assert summary["diagnose_audio"]["fluidsynth_executable"] == resolved_executable
    assert summary["generation"]["json_mode"] is True
    assert "--json" in summary["generation"]["command"]
    assert generation_payload["success"] is True
    assert generation_payload["results"]["render_report"].endswith("proof_render_report.json")
    assert json.loads((paths.run_dir / "generation_stdout.txt").read_text(encoding="utf-8"))["success"] is True