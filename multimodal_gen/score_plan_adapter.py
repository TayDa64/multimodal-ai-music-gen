"""
Score Plan Adapter

Bridges Copilot-authored Score Plans to the existing deterministic pipeline
without changing core generation behavior.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .prompt_parser import PromptParser, ParsedPrompt
from .utils import bars_to_ticks, ScaleType
from .arranger import SectionType, SectionConfig, SECTION_CONFIGS, SongSection
from .agents.context import PerformanceScore


SCORE_PLAN_SCHEMA_PATH = Path(__file__).parent.parent / "docs" / "muse-specs" / "schemas" / "score_plan.v1.schema.json"


class ScorePlanError(ValueError):
    """Raised when a score plan is invalid or cannot be adapted."""


def validate_score_plan(plan: Dict[str, Any], schema_path: Optional[Path] = None) -> None:
    """Validate a score plan against the JSON schema when available."""
    if not isinstance(plan, dict):
        raise ScorePlanError("Score plan must be a dict")

    schema_file = schema_path or SCORE_PLAN_SCHEMA_PATH
    try:
        import json
        import jsonschema  # type: ignore

        schema = json.loads(schema_file.read_text(encoding="utf-8"))
        jsonschema.validate(plan, schema)
        return
    except ImportError:
        # Minimal validation when jsonschema is unavailable.
        required = ("schema_version", "prompt", "bpm", "key", "mode", "sections", "tracks")
        missing = [k for k in required if k not in plan]
        if missing:
            raise ScorePlanError(f"Score plan missing required fields: {', '.join(missing)}")
    except FileNotFoundError as e:
        raise ScorePlanError(f"Score plan schema not found: {e}") from e
    except Exception as e:
        raise ScorePlanError(f"Score plan validation failed: {e}") from e


def score_plan_to_parsed_prompt(plan: Dict[str, Any], parser: Optional[PromptParser] = None) -> ParsedPrompt:
    """Apply score plan overrides onto a ParsedPrompt."""
    validate_score_plan(plan)
    parser = parser or PromptParser()
    parsed = parser.parse(str(plan.get("prompt", "")))

    parsed.bpm = int(plan.get("bpm", parsed.bpm or 120))

    key = str(plan.get("key", parsed.key or "C")).strip()
    mode = str(plan.get("mode", "minor")).strip().lower()
    parsed.key = key
    parsed.scale_type = ScaleType.MINOR if mode != "major" else ScaleType.MAJOR

    if plan.get("time_signature"):
        try:
            ts = plan["time_signature"]
            parsed.time_signature = (int(ts[0]), int(ts[1]))
        except Exception:
            pass

    if plan.get("genre"):
        parsed.genre = str(plan["genre"])

    if plan.get("mood"):
        parsed.mood = str(plan["mood"])

    # Instruments/drums from tracks
    instruments: List[str] = []
    drums: List[str] = []
    for track in plan.get("tracks", []):
        role = str(track.get("role", "")).strip().lower()
        instrument = str(track.get("instrument", "")).strip().lower()
        if not instrument:
            continue
        if role == "drums":
            if instrument not in drums:
                drums.append(instrument)
        else:
            if instrument not in instruments:
                instruments.append(instrument)

    if instruments:
        parsed.instruments = instruments
    if drums:
        parsed.drum_elements = drums

    constraints = plan.get("constraints") or {}
    if isinstance(constraints, dict):
        avoid_insts = constraints.get("avoid_instruments") or []
        avoid_drums = constraints.get("avoid_drums") or []
        if avoid_insts:
            parsed.excluded_instruments = [str(i) for i in avoid_insts]
        if avoid_drums:
            parsed.excluded_drums = [str(d) for d in avoid_drums]

    return parsed


def _section_type_from_str(section_type: str) -> SectionType:
    key = section_type.strip().upper()
    try:
        return SectionType[key]
    except Exception:
        return SectionType.VERSE


def build_sections_from_plan(
    plan: Dict[str, Any],
    time_signature: Tuple[int, int] = (4, 4),
) -> List[SongSection]:
    """Build SongSection list from a score plan."""
    sections: List[SongSection] = []
    current_tick = 0

    for entry in plan.get("sections", []):
        section_type_str = str(entry.get("type", "verse"))
        section_type = _section_type_from_str(section_type_str)
        bars = int(entry.get("bars", 4))
        ticks = bars_to_ticks(bars, time_signature)

        base_config: SectionConfig = SECTION_CONFIGS.get(section_type, SectionConfig())
        config = SectionConfig(**base_config.__dict__)

        section = SongSection(
            section_type=section_type,
            start_tick=current_tick,
            end_tick=current_tick + ticks,
            bars=bars,
            config=config,
        )
        sections.append(section)
        current_tick += ticks

    return sections


def score_plan_to_performance_score(plan: Dict[str, Any]) -> PerformanceScore:
    """Create a PerformanceScore from a score plan."""
    validate_score_plan(plan)

    bpm = float(plan.get("bpm", 120))
    key = str(plan.get("key", "C")).strip()
    time_signature = (4, 4)
    if plan.get("time_signature"):
        try:
            ts = plan["time_signature"]
            time_signature = (int(ts[0]), int(ts[1]))
        except Exception:
            time_signature = (4, 4)

    sections = build_sections_from_plan(plan, time_signature=time_signature)

    score = PerformanceScore()
    score.sections = sections
    score.tempo_map = {0: bpm}
    score.key_map = {0: key}
    score.genre = str(plan.get("genre", "")).strip().lower()
    score.mood = str(plan.get("mood", "neutral")).strip().lower()

    # Chord map from bar-indexed entries
    for item in plan.get("chord_map", []) or []:
        try:
            bar = int(item.get("bar", 1))
            chord = str(item.get("chord", "")).strip()
            if chord:
                tick = bars_to_ticks(max(0, bar - 1), time_signature)
                score.chord_map[tick] = chord
        except Exception:
            continue

    # Cue points from bar-indexed entries
    for item in plan.get("cue_points", []) or []:
        try:
            bar = int(item.get("bar", 1))
            cue_type = str(item.get("type", "")).strip()
            if cue_type:
                tick = bars_to_ticks(max(0, bar - 1), time_signature)
                cue = {"type": cue_type, "tick": tick}
                if "intensity" in item:
                    cue["intensity"] = float(item["intensity"])
                score.cue_points.append(cue)
        except Exception:
            continue

    # Tension curve (optional)
    if plan.get("tension_curve"):
        try:
            score.tension_curve = [float(v) for v in plan["tension_curve"]]
        except Exception:
            pass

    return score


def extract_seed(plan: Dict[str, Any]) -> Optional[int]:
    """Extract optional seed from a score plan."""
    seed = plan.get("seed")
    try:
        return int(seed) if seed is not None else None
    except Exception:
        return None

