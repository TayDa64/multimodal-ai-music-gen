"""
Auto Producer (Deterministic, No-LLM)

Creates a valid Score Plan v1 from a natural language prompt.

This is a bridge until a Copilot "producer" agent is wired in. The contract is:
- Always return a schema-valid score_plan_v1.
- Encode enough structure (sections, tension curve, tracks, seed) to yield audible variation.
"""

from __future__ import annotations

import random
from typing import Any, Dict, List, Optional

from ..prompt_parser import PromptParser
from ..utils import ScaleType


def _mode_from_scale(scale: ScaleType) -> str:
    if scale == ScaleType.MAJOR:
        return "major"
    return "minor"


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, float(x)))


def auto_score_plan_v1(
    prompt: str,
    *,
    seed: Optional[int] = None,
    duration_bars: int = 16,
    genre_hint: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a Score Plan v1 (schema_version=score_plan_v1) from a prompt."""
    parser = PromptParser()
    parsed = parser.parse(prompt)

    bpm = int(parsed.bpm or 0) or 72
    key = (parsed.key or "C").strip()
    mode = _mode_from_scale(parsed.scale_type or ScaleType.MINOR)
    genre = (genre_hint or parsed.genre or "ambient").strip().lower()
    mood = (parsed.mood or "cinematic").strip().lower()

    # Seed drives both plan variation and the downstream generator (when copied into score_plan.seed).
    if seed is None:
        seed = random.randint(0, 2**31 - 1)
    rng = random.Random(int(seed))

    # Section templates - keep within schema enum.
    # Ambient/cinematic benefits from a slow build: intro -> verse/build -> chorus/peak -> outro.
    templates: List[List[Dict[str, Any]]] = [
        [
            {"name": "Intro", "type": "intro", "bars": 4, "energy": 0.25, "tension": 0.2},
            {"name": "Build", "type": "verse", "bars": 4, "energy": 0.45, "tension": 0.45},
            {"name": "Peak", "type": "chorus", "bars": 4, "energy": 0.7, "tension": 0.75},
            {"name": "Outro", "type": "outro", "bars": 4, "energy": 0.35, "tension": 0.3},
        ],
        [
            {"name": "Intro", "type": "intro", "bars": 4, "energy": 0.2, "tension": 0.15},
            {"name": "Verse", "type": "verse", "bars": 6, "energy": 0.5, "tension": 0.55},
            {"name": "Break", "type": "breakdown", "bars": 2, "energy": 0.35, "tension": 0.4},
            {"name": "Chorus", "type": "chorus", "bars": 4, "energy": 0.75, "tension": 0.8},
        ],
    ]

    sections = rng.choice(templates)

    # Adjust bars to duration_bars (best-effort).
    bars_total = sum(int(s["bars"]) for s in sections)
    if bars_total != duration_bars and duration_bars >= 4:
        # Stretch/shrink the longest non-intro/outro section.
        target = duration_bars - bars_total
        idx = max(range(len(sections)), key=lambda i: int(sections[i]["bars"]))
        sections[idx]["bars"] = max(1, int(sections[idx]["bars"]) + target)

    # Tension curve per bar.
    tension_curve: List[float] = []
    for s in sections:
        bars = int(s["bars"])
        start = float(s.get("tension", 0.5))
        end = float(s.get("tension", start))
        if bars <= 1:
            tension_curve.append(_clamp01(start))
        else:
            for i in range(bars):
                t = i / float(bars - 1)
                tension_curve.append(_clamp01(start + (end - start) * t))

    # Tracks: keep small but musical. Use parsed instrument nouns when present to avoid generic output.
    insts = [i.strip().lower() for i in (parsed.instruments or []) if isinstance(i, str) and i.strip()]
    drums = [d.strip().lower() for d in (parsed.drum_elements or []) if isinstance(d, str) and d.strip()]

    def pick(default: str, candidates: List[str]) -> str:
        if candidates:
            return rng.choice(candidates)
        return default

    pad_inst = pick("pad", [i for i in insts if "pad" in i] or insts)
    drone_inst = pick("drone", [i for i in insts if "drone" in i] or insts)
    keys_inst = pick("keys", [i for i in insts if "piano" in i or "keys" in i] or insts)
    bass_inst = pick("sub bass", [i for i in insts if "bass" in i] or insts)
    prompt_lower = prompt.lower()
    drum_keywords = ["drum", "kick", "snare", "hihat", "clap", "perc", "percussion"]
    has_drum_keyword = any(k in prompt_lower for k in drum_keywords)
    wants_drums = has_drum_keyword or (bool(drums) and genre not in ("ambient", "cinematic"))
    drums_inst = pick("drums", drums)

    tracks: List[Dict[str, Any]] = [
        {"role": "pad", "instrument": pad_inst, "density": 0.6, "octave": 4},
        {"role": "fx", "instrument": drone_inst, "density": 0.35, "octave": 3},
        {"role": "keys", "instrument": keys_inst, "density": 0.4, "octave": 4},
        {"role": "bass", "instrument": bass_inst, "density": 0.35, "octave": 2},
    ]
    if wants_drums:
        tracks.append({"role": "drums", "instrument": drums_inst, "density": 0.25})

    constraints: Dict[str, Any] = {
        "max_polyphony": 8 if genre == "ambient" else 12,
    }
    if not wants_drums and (genre == "ambient" or "cinematic" in prompt_lower):
        constraints["avoid_drums"] = ["drums", "kick", "snare", "hihat", "clap", "perc"]

    return {
        "schema_version": "score_plan_v1",
        "prompt": prompt,
        "bpm": float(bpm),
        "key": key,
        "mode": mode,
        "time_signature": [4, 4],
        "genre": genre,
        "mood": mood,
        "seed": int(seed),
        "duration_bars": int(duration_bars),
        "sections": sections,
        "tension_curve": tension_curve,
        "tracks": tracks,
        "constraints": constraints,
    }
