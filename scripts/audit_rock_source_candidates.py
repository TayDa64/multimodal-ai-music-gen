"""Audit local guitar/bass source candidates for exact-rock upgrades.

This diagnostic is intentionally conservative: it reports source candidates and
their provenance, but it does not change renderer behavior and does not treat
local samples or expansion content as eligible without explicit approval proof.
"""

from __future__ import annotations

import argparse
import json
import os
import re
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple


SCHEMA_VERSION = 1

SOUNDFONT_EXTENSIONS = {".sf2", ".sf3", ".sfz"}
AUDIO_EXTENSIONS = {".wav", ".aif", ".aiff", ".mp3", ".flac"}
EXPANSION_EXTENSIONS = AUDIO_EXTENSIONS | {".xpm"}


def _normalized_path(path: Path) -> str:
    return str(path).replace(os.sep, "/")


def _relative_path(path: Path, repo_root: Path) -> str:
    try:
        rel = os.path.relpath(path, repo_root)
    except ValueError:
        return _normalized_path(path.resolve())
    return rel.replace(os.sep, "/")


def _format_for(path: Path) -> str:
    return path.suffix.lower().lstrip(".")


def _candidate_name(path: Path) -> str:
    return path.name.lower().replace("_", " ").replace("-", " ")


def _is_gm_baseline_soundfont(path: Path) -> bool:
    name = _candidate_name(path)
    return (
        "fluidr3" in name
        or "general midi" in name
        or re.search(r"(^|\W)gm($|\W)", name) is not None
    )


def _matches_guitar_or_bass(path: Path) -> bool:
    name = path.stem.lower()
    return "guitar" in name or "gtr" in name or "bass" in name


def _infer_guitar_bass_family(path: Path) -> str:
    name = path.stem.lower()
    if "bass" in name:
        return "bass"
    if "guitar" in name or "gtr" in name:
        return "guitar"
    return "unknown"


def _safe_json_load(path: Path) -> Dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _coerce_string_list(value: Any) -> List[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    if value is None:
        return []
    return [str(value)]


def _license_text(metadata: Mapping[str, Any]) -> str:
    for key in ("license", "licence", "license_name", "license_type"):
        value = metadata.get(key)
        if value:
            return str(value)
    return ""


def _is_personal_use_license(license_text: str) -> bool:
    normalized = license_text.lower().replace("-", " ")
    return "personal use" in normalized or (
        "commercial" in normalized and "personal" in normalized
    )


def _approval_manifest_exists(candidate: Path, expansion_root: Optional[Path] = None) -> bool:
    """Return True only for explicit local approval manifests.

    The audit remains conservative by requiring an obvious manifest name with an
    affirmative exact-rock approval flag. This currently acts as a diagnostic
    gate; the renderer does not consume this result.
    """

    roots = [candidate.parent]
    if expansion_root is not None:
        roots.append(expansion_root)

    manifest_names = (
        "rock_source_approval_manifest.json",
        "exact_rock_source_approval_manifest.json",
        "source_candidate_approval_manifest.json",
    )
    for root in roots:
        for name in manifest_names:
            manifest = root / name
            if not manifest.exists():
                continue
            data = _safe_json_load(manifest)
            if data.get("eligible_for_exact_rock_upgrade") is True:
                return True
            if data.get("exact_rock_upgrade_approved") is True:
                return True
    return False


def _soundfont_candidate(path: Path, repo_root: Path) -> Dict[str, Any]:
    if _is_gm_baseline_soundfont(path):
        source_quality = "gm_soundfont_baseline"
        family = "general_midi"
        license_status = "baseline_general_midi"
        reason = (
            "General MIDI SoundFont baseline asset; not a dedicated guitar/bass "
            "source upgrade."
        )
    else:
        source_quality = "soundfont_unverified"
        family = _infer_guitar_bass_family(path)
        license_status = "unknown_or_unverified"
        reason = (
            "SoundFont/SFZ candidate has no explicit exact-rock approval manifest "
            "with license, curation, and clean guitar/bass source proof."
        )

    return {
        "path": _relative_path(path, repo_root),
        "format": _format_for(path),
        "family": family,
        "source_quality": source_quality,
        "license_status": license_status,
        "eligible_for_exact_rock_upgrade": False,
        "reason": reason,
        "source_scope": "soundfont",
    }


def _local_instrument_candidate(path: Path, repo_root: Path) -> Dict[str, Any]:
    return {
        "path": _relative_path(path, repo_root),
        "format": _format_for(path),
        "family": _infer_guitar_bass_family(path),
        "source_quality": "local_user_sample_unverified",
        "license_status": "unknown_local_user_sample",
        "eligible_for_exact_rock_upgrade": False,
        "reason": (
            "Local guitar/bass sample is unverified; explicit license, curation, "
            "and clean multisample proof are required before exact-rock upgrade "
            "eligibility."
        ),
        "source_scope": "local_instruments",
    }


def _expansion_candidate(
    path: Path,
    repo_root: Path,
    expansion_root: Optional[Path],
    metadata: Mapping[str, Any],
) -> Dict[str, Any]:
    license_text = _license_text(metadata)
    approval_manifest_exists = _approval_manifest_exists(path, expansion_root)
    eligible = False

    if license_text and _is_personal_use_license(license_text):
        source_quality = "expansion_personal_use"
        license_status = "personal_use_restricted"
        reason = (
            "Expansion license is personal-use restricted; not eligible for an "
            "exact-rock guitar/bass source upgrade."
        )
    elif approval_manifest_exists:
        source_quality = "expansion_approval_manifest_present"
        license_status = "approval_manifest_present"
        eligible = True
        reason = (
            "Expansion candidate has an explicit approval manifest; downstream "
            "verification must still validate source quality before renderer use."
        )
    else:
        source_quality = "expansion_sample_unverified"
        license_status = "unknown_or_unverified"
        reason = (
            "Expansion guitar/bass source is unverified; no exact-rock approval "
            "manifest with license, curation, and clean multisample proof was found."
        )

    candidate = {
        "path": _relative_path(path, repo_root),
        "format": _format_for(path),
        "family": _infer_guitar_bass_family(path),
        "source_quality": source_quality,
        "license_status": license_status,
        "eligible_for_exact_rock_upgrade": eligible,
        "reason": reason,
        "source_scope": "expansion",
        "expansion_name": str(metadata.get("name") or expansion_root.name if expansion_root else ""),
        "expansion_license": license_text,
        "target_genres": _coerce_string_list(metadata.get("target_genres")),
    }
    return candidate


def _iter_files(root: Path, extensions: Iterable[str]) -> Iterable[Path]:
    if not root.exists():
        return []
    wanted = {ext.lower() for ext in extensions}
    return sorted(
        (
            path
            for path in root.rglob("*")
            if path.is_file() and path.suffix.lower() in wanted
        ),
        key=lambda path: _normalized_path(path.resolve()).lower(),
    )


def _find_expansion_manifests(expansions_root: Path) -> Dict[Path, Dict[str, Any]]:
    manifests: Dict[Path, Dict[str, Any]] = {}
    if not expansions_root.exists():
        return manifests
    for manifest in sorted(
        expansions_root.rglob("expansion.json"),
        key=lambda path: _normalized_path(path.resolve()).lower(),
    ):
        manifests[manifest.parent.resolve()] = _safe_json_load(manifest)
    return manifests


def _nearest_expansion_metadata(
    path: Path,
    manifests: Mapping[Path, Dict[str, Any]],
) -> Tuple[Optional[Path], Dict[str, Any]]:
    resolved = path.resolve()
    best_root: Optional[Path] = None
    best_metadata: Dict[str, Any] = {}
    for root, metadata in manifests.items():
        try:
            resolved.relative_to(root)
        except ValueError:
            continue
        if best_root is None or len(root.parts) > len(best_root.parts):
            best_root = root
            best_metadata = dict(metadata)
    return best_root, best_metadata


def _expansion_roots(repo_root: Path) -> List[Path]:
    roots = [repo_root.parent / "expansions", repo_root / "expansions"]
    seen = set()
    unique_roots = []
    for root in roots:
        resolved = root.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        unique_roots.append(root)
    return unique_roots


def _summary(candidates: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    by_source_scope = Counter(str(c.get("source_scope", "unknown")) for c in candidates)
    by_source_quality = Counter(str(c.get("source_quality", "unknown")) for c in candidates)
    by_family = Counter(str(c.get("family", "unknown")) for c in candidates)
    eligible_count = sum(
        1 for candidate in candidates if candidate.get("eligible_for_exact_rock_upgrade") is True
    )

    return {
        "total_candidates": len(candidates),
        "eligible_exact_rock_upgrade_candidates": eligible_count,
        "ineligible_candidates": len(candidates) - eligible_count,
        "by_source_scope": dict(sorted(by_source_scope.items())),
        "by_source_quality": dict(sorted(by_source_quality.items())),
        "by_family": dict(sorted(by_family.items())),
    }


def audit_rock_source_candidates(repo_root: Optional[Path | str] = None) -> Dict[str, Any]:
    """Return a deterministic JSON-serializable source-candidate audit."""

    root = Path(repo_root) if repo_root is not None else Path.cwd()
    root = root.resolve()

    candidates: List[Dict[str, Any]] = []

    soundfont_root = root / "assets" / "soundfonts"
    for path in _iter_files(soundfont_root, SOUNDFONT_EXTENSIONS):
        candidates.append(_soundfont_candidate(path, root))

    instruments_root = root / "instruments"
    for path in _iter_files(instruments_root, AUDIO_EXTENSIONS):
        if _matches_guitar_or_bass(path):
            candidates.append(_local_instrument_candidate(path, root))

    for expansions_root in _expansion_roots(root):
        manifests = _find_expansion_manifests(expansions_root)
        for path in _iter_files(expansions_root, EXPANSION_EXTENSIONS):
            if not _matches_guitar_or_bass(path):
                continue
            expansion_root, metadata = _nearest_expansion_metadata(path, manifests)
            candidates.append(_expansion_candidate(path, root, expansion_root, metadata))

    candidates.sort(
        key=lambda candidate: (
            str(candidate.get("path", "")).lower(),
            str(candidate.get("format", "")).lower(),
            str(candidate.get("source_scope", "")).lower(),
        )
    )

    return {
        "schema_version": SCHEMA_VERSION,
        "repo_root": _normalized_path(root),
        "summary": _summary(candidates),
        "candidates": candidates,
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Audit local guitar/bass source candidates for exact-rock upgrades."
    )
    parser.add_argument(
        "--repo-root",
        default=None,
        help="Repository root to scan. Defaults to the current working directory.",
    )
    parser.add_argument(
        "--out",
        default=None,
        help="Optional path to write the audit JSON. JSON is always printed to stdout.",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_arg_parser().parse_args(argv)
    report = audit_rock_source_candidates(args.repo_root)
    payload = json.dumps(report, indent=2, sort_keys=True)

    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(payload + "\n", encoding="utf-8")

    print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())