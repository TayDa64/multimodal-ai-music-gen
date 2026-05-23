"""Active-environment FluidSynth/SoundFont proof helper.

This script is intentionally small and reproducible. It aims to provide
"active environment" proof that:

1) The local FluidSynth binary can be found (optionally by prepending a
   repo-local tools/ path when present).
2) `main.py --diagnose-audio` reports expected availability fields.
3) A strict, isolated smoke render uses FluidSynth with an explicit SoundFont.
4) The FluidSynth WAV still runs through the file-level mastering pipeline
   (recorded via `pipeline_stages.fluidsynth_file_mastering.*`).

Truthfulness/Scope notes:
- This is a proof harness, not a deployment installer.
- It does not claim full timbral parity, only that the expected renderer and
  mastering diagnostics ran in this environment.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Sequence


DEFAULT_PROMPT = (
    "1990's era rock song with crunchy electric guitar, live drums, bass guitar, "
    "verse chorus bridge, energetic band performance, 100 BPM in E minor"
)


@dataclass(frozen=True)
class ProofPaths:
    run_dir: Path
    diagnose_json: Path
    results_json: Path
    summary_json: Path


def _utc_now_compact() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def _find_repo_root() -> Path:
    # scripts/ is directly under the MUSE project root.
    return Path(__file__).resolve().parents[1]


def _find_local_fluidsynth_bin(repo_root: Path) -> Optional[Path]:
    """Best-effort search for a repo-local FluidSynth binary folder.

    We intentionally avoid hard-coded absolute paths. This prefers:
    - <workspace>/tools/fluidsynth*/bin/fluidsynth.exe (common in this repo)
    - <repo_root>/tools/... (fallback)
    """
    candidates: Sequence[Path] = (
        repo_root.parent / "tools",
        repo_root / "tools",
    )

    for base in candidates:
        if not base.exists():
            continue
        for bin_dir in base.glob("fluidsynth*/bin"):
            exe = bin_dir / "fluidsynth.exe"
            if exe.exists():
                return bin_dir
        # One level deeper (some zips extract as tools/fluidsynth-*/fluid*/bin)
        for bin_dir in base.glob("**/bin"):
            exe = bin_dir / "fluidsynth.exe"
            if exe.exists():
                return bin_dir
    return None


def _find_soundfont(repo_root: Path, explicit: Optional[str]) -> Optional[Path]:
    if explicit:
        p = Path(explicit)
        if not p.is_absolute():
            p = (repo_root / p).resolve()
        return p if p.exists() else None

    soundfonts_dir = repo_root / "assets" / "soundfonts"
    if not soundfonts_dir.exists():
        return None

    preferred = (
        "FluidR3Mono_GM.sf3",
        "FluidR3_GM.sf2",
        "GeneralUser_GS.sf2",
        "default.sf2",
    )
    for name in preferred:
        candidate = soundfonts_dir / name
        if candidate.exists():
            return candidate

    for ext in ("*.sf2", "*.sf3"):
        matches = sorted(soundfonts_dir.glob(ext))
        if matches:
            return matches[0]

    return None


def _run_json_command(
    cmd: Sequence[str],
    *,
    env: Dict[str, str],
    cwd: Path,
) -> Dict[str, Any]:
    proc = subprocess.run(
        list(cmd),
        env=env,
        cwd=str(cwd),
        capture_output=True,
        text=True,
    )

    if proc.returncode != 0:
        raise RuntimeError(
            "Command failed:\n"
            f"  cmd: {' '.join(cmd)}\n"
            f"  exit_code: {proc.returncode}\n"
            f"  stdout: {proc.stdout[-2000:]}\n"
            f"  stderr: {proc.stderr[-2000:]}\n"
        )

    stdout = (proc.stdout or "").strip()
    if not stdout:
        return {}

    # main.py's --json is intended to be clean, but in real shells a stray log
    # line can slip in. We tolerate this by extracting the last JSON object.
    try:
        return json.loads(stdout)
    except json.JSONDecodeError:
        parsed = _extract_last_json_object(stdout)
        if parsed is not None:
            return parsed
        raise RuntimeError(
            "Command did not produce valid JSON:\n"
            f"  cmd: {' '.join(cmd)}\n"
            f"  stdout (tail): {stdout[-2000:]}"
        )


def _extract_last_json_object(text: str) -> Optional[Dict[str, Any]]:
    """Best-effort extraction of a JSON object from noisy stdout."""
    if not text:
        return None

    # Try last line first.
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for candidate in reversed(lines[-30:]):
        if candidate.startswith("{") and candidate.endswith("}"):
            try:
                parsed = json.loads(candidate)
            except Exception:
                continue
            if isinstance(parsed, dict):
                return parsed

    # Fallback: scan for last '{' and attempt to parse substring.
    last_brace = text.rfind("{")
    if last_brace >= 0:
        snippet = text[last_brace:]
        try:
            parsed = json.loads(snippet)
        except Exception:
            return None
        return parsed if isinstance(parsed, dict) else None
    return None


def _run_command_capture(
    cmd: Sequence[str],
    *,
    env: Dict[str, str],
    cwd: Path,
) -> subprocess.CompletedProcess:
    return subprocess.run(
        list(cmd),
        env=env,
        cwd=str(cwd),
        capture_output=True,
        text=True,
    )


def _discover_latest_artifact(run_dir: Path, pattern: str) -> Optional[Path]:
    matches = sorted(run_dir.glob(pattern), key=lambda p: p.stat().st_mtime if p.exists() else 0.0)
    return matches[-1] if matches else None


def _extract_mastering_indicators(render_report: Dict[str, Any]) -> Dict[str, Any]:
    stages = render_report.get("pipeline_stages")
    if not isinstance(stages, dict):
        stages = {}
    prefix = "fluidsynth_file_mastering."

    def stage(key_suffix: str) -> Optional[str]:
        val = stages.get(prefix + key_suffix)
        return str(val) if val is not None else None

    return {
        "renderer_path": render_report.get("renderer_path"),
        "soundfont_path": render_report.get("soundfont_path"),
        "fluidsynth_success": (render_report.get("fluidsynth") or {}).get("success"),
        "mastering_status": stage("status"),
        "profile": stage("profile"),
        "tone_shaping": stage("tone_shaping"),
        "auto_gain_staging": stage("auto_gain_staging"),
        "true_peak_limiter": stage("true_peak_limiter"),
    }


def run_proof(args: argparse.Namespace) -> ProofPaths:
    repo_root = _find_repo_root()
    main_py = repo_root / "main.py"
    if not main_py.exists():
        raise FileNotFoundError(f"main.py not found at expected path: {main_py}")

    output_root = Path(args.output_root)
    if not output_root.is_absolute():
        output_root = (repo_root / output_root).resolve()
    run_dir = output_root / f"proof_{_utc_now_compact()}"
    run_dir.mkdir(parents=True, exist_ok=True)

    paths = ProofPaths(
        run_dir=run_dir,
        diagnose_json=run_dir / "diagnose_audio.json",
        results_json=run_dir / "generation_results.json",
        summary_json=run_dir / "proof_summary.json",
    )

    diagnose_stdout_path = run_dir / "diagnose_audio_stdout.txt"
    diagnose_stderr_path = run_dir / "diagnose_audio_stderr.txt"
    gen_stdout_path = run_dir / "generation_stdout.txt"
    gen_stderr_path = run_dir / "generation_stderr.txt"

    env = dict(os.environ)
    fluidsynth_bin = _find_local_fluidsynth_bin(repo_root)
    if fluidsynth_bin is not None:
        env["PATH"] = str(fluidsynth_bin) + os.pathsep + env.get("PATH", "")

    soundfont = _find_soundfont(repo_root, args.soundfont)
    if soundfont is None:
        raise FileNotFoundError(
            "No SoundFont found. Provide --soundfont or place one under assets/soundfonts/."
        )

    # 1) Diagnose proof
    diagnose_cmd = [
        sys.executable,
        str(main_py),
        "--diagnose-audio",
        "--soundfont",
        str(soundfont),
        "--no-banner",
    ]
    diagnose_proc = _run_command_capture(diagnose_cmd, env=env, cwd=repo_root)
    diagnose_stdout_path.write_text(diagnose_proc.stdout or "", encoding="utf-8")
    diagnose_stderr_path.write_text(diagnose_proc.stderr or "", encoding="utf-8")
    if diagnose_proc.returncode != 0:
        raise RuntimeError(
            "diagnose-audio failed:\n"
            f"  cmd: {' '.join(diagnose_cmd)}\n"
            f"  exit_code: {diagnose_proc.returncode}\n"
            f"  stderr (tail): {(diagnose_proc.stderr or '')[-2000:]}"
        )

    _diagnose_stdout = (diagnose_proc.stdout or "").strip()
    try:
        diagnose = json.loads(_diagnose_stdout) if _diagnose_stdout else {}
    except Exception:
        diagnose = _extract_last_json_object(_diagnose_stdout) or {}
    paths.diagnose_json.write_text(json.dumps(diagnose, indent=2), encoding="utf-8")

    # 2) Strict isolated smoke render
    prompt = args.prompt or DEFAULT_PROMPT
    gen_cmd = [
        sys.executable,
        str(main_py),
        prompt,
        "--output",
        str(run_dir),
        "--soundfont",
        str(soundfont),
        "--require-soundfont",
        "--require-audio",
        "--skip-default-instruments",
        "--skip-expansions",
        "--duration-bars",
        str(int(args.duration_bars)),
        "--seed",
        str(int(args.seed)),
        "--no-banner",
    ]
    gen_proc = _run_command_capture(gen_cmd, env=env, cwd=repo_root)
    gen_stdout_path.write_text(gen_proc.stdout or "", encoding="utf-8")
    gen_stderr_path.write_text(gen_proc.stderr or "", encoding="utf-8")
    if gen_proc.returncode != 0:
        raise RuntimeError(
            "generation command failed:\n"
            f"  cmd: {' '.join(gen_cmd)}\n"
            f"  exit_code: {gen_proc.returncode}\n"
            f"  stderr (tail): {(gen_proc.stderr or '')[-2000:]}"
        )

    # main.py does not produce stable machine-readable JSON in --json mode yet.
    # We discover artifacts from the output directory instead.
    render_report_path = _discover_latest_artifact(run_dir, "*_render_report.json")
    audio_path = _discover_latest_artifact(run_dir, "*.wav")
    midi_path = _discover_latest_artifact(run_dir, "*.mid")
    results = {
        "success": True,
        "render_report": str(render_report_path) if render_report_path else None,
        "audio": str(audio_path) if audio_path else None,
        "midi": str(midi_path) if midi_path else None,
    }
    paths.results_json.write_text(json.dumps(results, indent=2), encoding="utf-8")

    render_report: Dict[str, Any] = {}
    if render_report_path:
        try:
            render_report = json.loads(Path(render_report_path).read_text(encoding="utf-8"))
        except Exception:
            render_report = {}

    summary = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "python": sys.executable,
        "repo_root": str(repo_root),
        "fluidsynth_bin_prepended": str(fluidsynth_bin) if fluidsynth_bin else None,
        "soundfont": str(soundfont),
        "diagnose_audio": {
            "fluidsynth_available": (diagnose.get("fluidsynth") or {}).get("available"),
            "fluidsynth_version": (diagnose.get("fluidsynth") or {}).get("version"),
            "soundfont_discovered": (diagnose.get("soundfont") or {}).get("discovered"),
        },
        "generation": {
            "command": " ".join(gen_cmd),
            "output_dir": str(run_dir),
            "audio": results.get("audio"),
            "midi": results.get("midi"),
            "render_report": results.get("render_report"),
        },
        "renderer_mastering_indicators": _extract_mastering_indicators(render_report),
    }
    paths.summary_json.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    # Human-readable tail for terminal logs.
    print("\n=== FluidSynth environment proof summary ===")
    print(f"run_dir: {paths.run_dir}")
    print(f"summary_json: {paths.summary_json}")
    indicators = summary["renderer_mastering_indicators"]
    print(f"renderer_path: {indicators.get('renderer_path')}")
    print(f"fluidsynth_success: {indicators.get('fluidsynth_success')}")
    print(f"mastering_status: {indicators.get('mastering_status')}")
    print(f"profile: {indicators.get('profile')}")
    return paths


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--soundfont",
        type=str,
        default=None,
        help="SoundFont path (.sf2/.sf3). If relative, resolved against the MUSE repo root.",
    )
    parser.add_argument(
        "--output-root",
        type=str,
        default="output/_diagnostics/fluidsynth_env_proof",
        help="Root output folder for proof artifacts (default: output/_diagnostics/fluidsynth_env_proof)",
    )
    parser.add_argument("--prompt", type=str, default=DEFAULT_PROMPT)
    parser.add_argument("--duration-bars", type=int, default=4)
    parser.add_argument("--seed", type=int, default=49049)

    args = parser.parse_args()
    run_proof(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
