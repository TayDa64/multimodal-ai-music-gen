"""Shared runtime helpers for locating and probing the FluidSynth executable."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Optional, Tuple


def _get_repo_root() -> Path:
    """Return the MUSE repository root."""
    return Path(__file__).resolve().parents[1]


def _normalize_candidate_path(candidate: Path) -> Optional[str]:
    try:
        if candidate.is_file():
            return str(candidate.resolve())
    except OSError:
        return None
    return None


def _resolve_explicit_override(raw_value: str) -> Optional[str]:
    value = (raw_value or "").strip().strip('"')
    if not value:
        return None

    candidate = Path(value).expanduser()
    repo_root = _get_repo_root()
    search_paths = [candidate]

    if not candidate.is_absolute():
        search_paths.extend([
            Path.cwd() / candidate,
            repo_root / candidate,
        ])

    for path_candidate in search_paths:
        resolved = _normalize_candidate_path(path_candidate)
        if resolved:
            return resolved

    which_match = shutil.which(value)
    if which_match:
        return str(Path(which_match).resolve())

    return None


def resolve_fluidsynth_executable() -> Optional[str]:
    """Resolve the FluidSynth executable to an absolute path, or None if unavailable.

    Search order:
    1) MUSE_FLUIDSYNTH_EXE override
    2) system PATH (fluidsynth / fluidsynth.exe)
    3) workspace-local tools fallback: ../tools/fluidsynth*/bin/fluidsynth.exe
    4) repo-local fallback: tools/**/bin/fluidsynth.exe
    """
    env_override = _resolve_explicit_override(os.environ.get("MUSE_FLUIDSYNTH_EXE", ""))
    if env_override:
        return env_override

    for command_name in ("fluidsynth", "fluidsynth.exe"):
        which_match = shutil.which(command_name)
        if which_match:
            return str(Path(which_match).resolve())

    repo_root = _get_repo_root()
    workspace_tools_root = repo_root.parent / "tools"
    if workspace_tools_root.exists():
        for candidate in sorted(workspace_tools_root.glob("fluidsynth*/bin/fluidsynth.exe")):
            resolved = _normalize_candidate_path(candidate)
            if resolved:
                return resolved

    repo_tools_root = repo_root / "tools"
    if repo_tools_root.exists():
        for candidate in sorted(repo_tools_root.glob("**/bin/fluidsynth.exe")):
            resolved = _normalize_candidate_path(candidate)
            if resolved:
                return resolved

    return None


def probe_fluidsynth(
    executable: Optional[str] = None,
    *,
    timeout: int = 3,
) -> Tuple[Optional[str], bool, Optional[str]]:
    """Probe the resolved FluidSynth executable and return (exe, available, version).

    Version probing preserves the existing runtime fallback order:
    first `--version`, then `-V` for Windows portable builds.
    """
    resolved_executable = executable or resolve_fluidsynth_executable()
    if not resolved_executable:
        return None, False, None

    for version_flag in ("--version", "-V"):
        try:
            result = subprocess.run(
                [resolved_executable, version_flag],
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except FileNotFoundError:
            return resolved_executable, False, None
        except Exception:
            return resolved_executable, False, None

        if result.returncode == 0:
            version_text = (result.stdout or result.stderr).strip() or None
            return resolved_executable, True, version_text

    return resolved_executable, False, None