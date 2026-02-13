"""
Transition Generator — musical transitions between arrangement sections.

Creates fills, breakdowns, builds, cuts, and crashes to bridge section
boundaries so they don't cut abruptly from one to the next.

Pattern follows dynamics.py / section_variation.py: dataclasses, type hints,
genre presets, convenience function.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple
import random

TICKS_PER_BEAT = 480


# ---------------------------------------------------------------------------
# Enums & data classes
# ---------------------------------------------------------------------------

class TransitionType(Enum):
    """Kinds of transition between two sections."""
    FILL = "fill"            # Drum fill at section end
    BREAKDOWN = "breakdown"  # Strip to sparse elements before new section
    BUILD = "build"          # Energy ramp (snare roll / hihat increasing density)
    CUT = "cut"              # Hard stop (silence) before new section
    CRASH = "crash"          # Crash cymbal + brief silence on downbeat


@dataclass
class TransitionConfig:
    """Configuration for a section transition."""
    transition_type: TransitionType = TransitionType.FILL
    duration_beats: float = 2.0       # Length of transition in beats (half bar)
    intensity: float = 0.7            # 0.0 = subtle, 1.0 = dramatic
    seed: Optional[int] = None


@dataclass
class TransitionEvent:
    """A generated transition: list of MIDI note events."""
    transition_type: TransitionType
    events: List[Tuple[int, int, int, int]]  # (pitch, start_tick, duration_ticks, velocity)
    start_tick: int
    end_tick: int


# ---------------------------------------------------------------------------
# Genre-specific transition preferences
# ---------------------------------------------------------------------------

GENRE_TRANSITION_STYLES: Dict[str, Dict[str, TransitionType]] = {
    "trap": {
        "default": TransitionType.BUILD,
        "verse_to_chorus": TransitionType.CUT,
    },
    "boom_bap": {
        "default": TransitionType.FILL,
        "verse_to_chorus": TransitionType.CRASH,
    },
    "house": {
        "default": TransitionType.BUILD,
        "verse_to_chorus": TransitionType.BUILD,
    },
    "lofi": {
        "default": TransitionType.BREAKDOWN,
        "verse_to_chorus": TransitionType.FILL,
    },
    "jazz": {
        "default": TransitionType.FILL,
        "verse_to_chorus": TransitionType.FILL,
    },
    "ethiopian": {
        "default": TransitionType.FILL,
        "verse_to_chorus": TransitionType.BUILD,
    },
    "drill": {
        "default": TransitionType.CUT,
        "verse_to_chorus": TransitionType.BUILD,
    },
    "r&b": {
        "default": TransitionType.FILL,
        "verse_to_chorus": TransitionType.CRASH,
    },
    "ambient": {
        "default": TransitionType.BREAKDOWN,
        "verse_to_chorus": TransitionType.BREAKDOWN,
    },
}


# ---------------------------------------------------------------------------
# Generator
# ---------------------------------------------------------------------------

class TransitionGenerator:
    """Generates musical transitions between arrangement sections."""

    def __init__(self, seed: Optional[int] = None):
        self._rng = random.Random(seed)

    # -- selection ----------------------------------------------------------

    def select_transition_type(
        self,
        from_section,  # SongSection  (duck-typed to avoid hard import)
        to_section,
    ) -> TransitionType:
        """Choose appropriate transition based on energy delta."""
        energy_delta = (
            to_section.config.energy_level - from_section.config.energy_level
        )

        # Large energy increase → build
        if energy_delta > 0.3:
            return TransitionType.BUILD

        # Large energy decrease → breakdown or cut
        if energy_delta < -0.3:
            return self._rng.choice([TransitionType.BREAKDOWN, TransitionType.CUT])

        # Drop / chorus entry → crash
        to_type_value = (
            to_section.section_type.value
            if hasattr(to_section.section_type, "value")
            else str(to_section.section_type)
        )
        if to_type_value in ("drop", "chorus"):
            return TransitionType.CRASH

        # Default → fill
        return TransitionType.FILL

    # -- public API ---------------------------------------------------------

    def generate_transition(
        self,
        from_section,
        to_section,
        config: Optional[TransitionConfig] = None,
    ) -> TransitionEvent:
        """Generate transition events between two sections."""
        if config is None:
            tt = self.select_transition_type(from_section, to_section)
            config = TransitionConfig(transition_type=tt)

        duration_ticks = int(config.duration_beats * TICKS_PER_BEAT)
        end_tick = from_section.end_tick
        start_tick = max(from_section.start_tick, end_tick - duration_ticks)

        generators = {
            TransitionType.FILL: self._generate_fill,
            TransitionType.BREAKDOWN: self._generate_breakdown,
            TransitionType.BUILD: self._generate_build,
            TransitionType.CUT: self._generate_cut,
            TransitionType.CRASH: self._generate_crash,
        }

        gen_func = generators.get(config.transition_type, self._generate_fill)
        events = gen_func(start_tick, end_tick, config.intensity, to_section)

        return TransitionEvent(
            transition_type=config.transition_type,
            events=events,
            start_tick=start_tick,
            end_tick=end_tick,
        )

    def generate_all_transitions(
        self,
        sections: List,
        config: Optional[TransitionConfig] = None,
    ) -> List[TransitionEvent]:
        """Generate transitions for all section boundaries."""
        transitions: List[TransitionEvent] = []
        for i in range(len(sections) - 1):
            try:
                t = self.generate_transition(sections[i], sections[i + 1], config)
                transitions.append(t)
            except Exception:
                continue
        return transitions

    # -- private generators -------------------------------------------------

    def _generate_fill(
        self,
        start: int,
        end: int,
        intensity: float,
        to_section=None,
    ) -> List[Tuple[int, int, int, int]]:
        """Classic drum fill: toms descending, snare accent on last beat."""
        events: List[Tuple[int, int, int, int]] = []
        total = end - start
        if total <= 0:
            return events

        # Tom fill pattern: descending toms with increasing density
        tom_pitches = [50, 47, 45]  # hi tom, mid tom, low tom
        num_hits = max(3, int(6 * intensity))
        step = max(1, total // num_hits)

        for i in range(num_hits):
            tick = start + i * step
            if tick >= end:
                break
            tom_idx = min(
                i * len(tom_pitches) // num_hits, len(tom_pitches) - 1
            )
            velocity = int(80 + 30 * (i / max(1, num_hits - 1)) * intensity)
            velocity = min(127, velocity)
            events.append((tom_pitches[tom_idx], tick, step // 2, velocity))

        # Snare accent on last 8th note
        last_8th = end - TICKS_PER_BEAT // 2
        if last_8th >= start:
            events.append(
                (38, last_8th, TICKS_PER_BEAT // 2, min(127, int(100 + 27 * intensity)))
            )

        return events

    def _generate_build(
        self,
        start: int,
        end: int,
        intensity: float,
        to_section=None,
    ) -> List[Tuple[int, int, int, int]]:
        """Snare/hihat roll building in density toward section end."""
        events: List[Tuple[int, int, int, int]] = []
        total = end - start
        if total <= 0:
            return events

        # Start with 8th notes, accelerate to 16ths then 32nds
        subdivisions = [
            (0.0, 0.5, TICKS_PER_BEAT // 2),    # 8th notes first half
            (0.5, 0.75, TICKS_PER_BEAT // 4),    # 16th notes middle
            (0.75, 1.0, TICKS_PER_BEAT // 8),    # 32nd notes final quarter
        ]

        for frac_start, frac_end, subdiv in subdivisions:
            seg_start = start + int(total * frac_start)
            seg_end = start + int(total * frac_end)
            if subdiv <= 0:
                continue
            tick = seg_start
            while tick < seg_end:
                progress = (tick - start) / max(1, total)
                vel = int(60 + 60 * progress * intensity)
                vel = min(127, vel)
                # Alternate snare / hihat
                pitch = 38 if (tick // subdiv) % 2 == 0 else 42
                events.append((pitch, tick, subdiv // 2, vel))
                tick += subdiv

        return events

    def _generate_breakdown(
        self,
        start: int,
        end: int,
        intensity: float,
        to_section=None,
    ) -> List[Tuple[int, int, int, int]]:
        """Sparse breakdown: kick only, reducing density."""
        events: List[Tuple[int, int, int, int]] = []
        total = end - start
        if total <= 0:
            return events

        num_kicks = max(2, int(4 * (1 - intensity * 0.5)))
        step = total // max(1, num_kicks)
        for i in range(num_kicks):
            tick = start + i * step
            if tick >= end:
                break
            vel = int(90 - 20 * (i / max(1, num_kicks - 1)))
            events.append((36, tick, TICKS_PER_BEAT // 2, max(40, vel)))

        return events

    def _generate_cut(
        self,
        start: int,
        end: int,
        intensity: float,
        to_section=None,
    ) -> List[Tuple[int, int, int, int]]:
        """Hard cut: single snare hit then silence."""
        events: List[Tuple[int, int, int, int]] = []
        events.append(
            (38, start, TICKS_PER_BEAT // 4, min(127, int(110 * intensity)))
        )
        return events

    def _generate_crash(
        self,
        start: int,
        end: int,
        intensity: float,
        to_section=None,
    ) -> List[Tuple[int, int, int, int]]:
        """Crash cymbal on the transition point with optional kick."""
        events: List[Tuple[int, int, int, int]] = []
        crash_tick = end - TICKS_PER_BEAT  # One beat before section end
        if crash_tick < start:
            crash_tick = start
        # Crash
        events.append(
            (49, crash_tick, TICKS_PER_BEAT, min(127, int(100 + 27 * intensity)))
        )
        # Kick
        events.append(
            (36, crash_tick, TICKS_PER_BEAT // 2, min(127, int(90 + 30 * intensity)))
        )
        return events


# ---------------------------------------------------------------------------
# Convenience
# ---------------------------------------------------------------------------

def generate_transitions(
    sections,
    genre: str = "trap",
    seed: Optional[int] = None,
) -> List[TransitionEvent]:
    """Convenience: generate all transitions for an arrangement."""
    gen = TransitionGenerator(seed=seed)
    return gen.generate_all_transitions(sections)
