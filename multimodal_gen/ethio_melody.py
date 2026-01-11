"""Ethiopian qenet / ethio-jazz melodic embellishment.

This module provides a lightweight, deterministic (seedable) post-process
for melody event lists. It is intentionally conservative:
- Only activates for higher "complexity" values.
- Keeps pitches inside the requested mode/scale.
- Adds Ethiopian-idiomatic ornaments (neighbor/grace, mordent) and simple
  call/response phrase shaping (2-bar phrases).

The goal is to increase perceived musicality without changing the core
composition pipeline or requiring audio rendering.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Optional, Sequence, Tuple

import random as _random

from .utils import (
    ScaleType,
    TICKS_PER_16TH,
    TICKS_PER_8TH,
    TICKS_PER_BEAT,
    bars_to_ticks,
    get_scale_notes,
    note_name_to_midi,
)


NoteTuple = Tuple[int, int, int, int]  # (tick, dur, pitch, vel)


def _clamp_int(value: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, int(value)))


def _pitch_classes_for_scale(key: str, scale_type: ScaleType) -> set[int]:
    root_midi = note_name_to_midi(key, 0)
    root_pc = root_midi % 12
    return {(root_pc + i) % 12 for i in scale_type.value}


def _nearest_in_scale(pitch: int, scale_notes: Sequence[int]) -> int:
    """Snap pitch to nearest absolute MIDI note present in scale_notes."""
    if not scale_notes:
        return pitch
    pitch = _clamp_int(pitch, 0, 127)
    best = scale_notes[0]
    best_dist = abs(best - pitch)
    for candidate in scale_notes[1:]:
        dist = abs(candidate - pitch)
        if dist < best_dist or (dist == best_dist and candidate < best):
            best = candidate
            best_dist = dist
    return best


def _build_scale_notes_around_register(key: str, scale_type: ScaleType) -> List[int]:
    # Generate a wide range so we can find nearby degrees for almost any melody register.
    # Octave=1 -> C1-ish region; 8 octaves covers MIDI range well.
    notes = get_scale_notes(key, scale_type, octave=1, num_octaves=8)
    notes = sorted(set(n for n in notes if 0 <= n <= 127))
    return notes


def _shift_degree(pitch: int, scale_notes: Sequence[int], degree_step: int) -> int:
    if not scale_notes:
        return pitch
    snapped = _nearest_in_scale(pitch, scale_notes)
    try:
        idx = scale_notes.index(snapped)
    except ValueError:
        # Fallback: approximate index by nearest.
        idx = min(range(len(scale_notes)), key=lambda i: abs(scale_notes[i] - snapped))
    target_idx = _clamp_int(idx + degree_step, 0, len(scale_notes) - 1)
    return scale_notes[target_idx]


def _choose_resting_pitch(pitch: int, key: str, scale_type: ScaleType, scale_notes: Sequence[int]) -> int:
    """Cadence helper: bias to tonic or fifth (when available)."""
    if not scale_notes:
        return pitch
    pcs = _pitch_classes_for_scale(key, scale_type)

    root_pc = note_name_to_midi(key, 0) % 12
    fifth_pc = (root_pc + 7) % 12

    candidates = []
    for n in scale_notes:
        if n % 12 == root_pc or (fifth_pc in pcs and n % 12 == fifth_pc):
            candidates.append(n)

    if not candidates:
        return _nearest_in_scale(pitch, scale_notes)

    # Prefer candidate in same register.
    best = candidates[0]
    best_dist = abs(best - pitch)
    for c in candidates[1:]:
        dist = abs(c - pitch)
        if dist < best_dist or (dist == best_dist and c < best):
            best, best_dist = c, dist
    return best


@dataclass(frozen=True)
class QenetEmbellishConfig:
    complexity_threshold: float = 0.70
    phrase_bars: int = 2


def embellish_melody_qenet(
    melody: Sequence[NoteTuple],
    *,
    key: str,
    scale_type: ScaleType,
    time_signature: tuple[int, int] = (4, 4),
    section_bars: int = 4,
    complexity: float = 0.5,
    call_response: bool = True,
    config: Optional[QenetEmbellishConfig] = None,
    rng: Optional[_random.Random] = None,
) -> List[NoteTuple]:
    """Return a new melody list embellished with qenet-style phrasing.

    This is a post-process: it does not generate a melody from scratch.

    Notes:
    - Pitches are snapped to the provided scale.
    - Ornaments are small neighbor motions *within the same scale*.
    - Simple call/response is applied by shaping odd phrases.
    """
    if not melody:
        return []

    cfg = config or QenetEmbellishConfig()
    r = rng or _random

    complexity = float(max(0.0, min(1.0, complexity)))

    # Always snap to scale for Ethiopian modes so ornaments don't introduce chromaticism.
    scale_notes = _build_scale_notes_around_register(key, scale_type)

    # Convert to list and sort for stable processing.
    base = sorted([(int(t), int(d), int(p), int(v)) for (t, d, p, v) in melody], key=lambda x: (x[0], x[2]))

    ticks_per_bar = int(bars_to_ticks(1, time_signature))
    phrase_len = max(ticks_per_bar, 1) * max(cfg.phrase_bars, 1)

    # Ornament probability ramps with complexity, but is gated.
    if complexity < cfg.complexity_threshold:
        # Still snap pitches (safe + mode-aware) but keep rhythm/content mostly intact.
        snapped = [(t, d, _nearest_in_scale(p, scale_notes), v) for (t, d, p, v) in base]
        return snapped

    prob = 0.10 + 0.35 * (complexity - cfg.complexity_threshold) / max(1e-6, (1.0 - cfg.complexity_threshold))
    prob = float(max(0.10, min(0.50, prob)))

    out: List[NoteTuple] = []

    for idx, (tick, dur, pitch, vel) in enumerate(base):
        snapped_pitch = _nearest_in_scale(pitch, scale_notes)

        phrase_idx = tick // phrase_len
        is_response = call_response and (phrase_idx % 2 == 1)

        local_prob = prob * (0.65 if is_response else 1.0)

        # Response phrases: slightly simplify + answer contour.
        if is_response and r.random() < 0.35:
            step = r.choice([-2, -1, 1, 2])
            snapped_pitch = _shift_degree(snapped_pitch, scale_notes, step)

        # Cadence: near end of phrase, bias to stable tones.
        phrase_end = (phrase_idx + 1) * phrase_len
        if (phrase_end - tick) <= TICKS_PER_8TH and r.random() < 0.55:
            snapped_pitch = _choose_resting_pitch(snapped_pitch, key, scale_type, scale_notes)

        out.append((tick, dur, snapped_pitch, vel))

        # --- Ornaments ---
        # Only insert ornaments when we have enough lead-in time.
        if tick < TICKS_PER_16TH:
            continue

        # Prefer neighbor/grace ornaments on sustained notes.
        if dur >= TICKS_PER_8TH and r.random() < local_prob:
            # Grace note: quick neighbor step into the target.
            neighbor_step = r.choice([-1, 1])
            grace_pitch = _shift_degree(snapped_pitch, scale_notes, neighbor_step)
            grace_tick = max(0, tick - (TICKS_PER_16TH // 2))
            grace_dur = max(1, TICKS_PER_16TH // 2)
            grace_vel = _clamp_int(int(vel * 0.60), 15, 110)
            out.append((grace_tick, grace_dur, grace_pitch, grace_vel))

        # Mordent-like flick for very long notes at high complexity.
        if dur >= TICKS_PER_BEAT and complexity >= 0.88 and r.random() < (0.18 + 0.12 * local_prob):
            step = r.choice([-1, 1])
            flick_pitch = _shift_degree(snapped_pitch, scale_notes, step)
            flick_tick = max(0, tick + (TICKS_PER_16TH // 2))
            flick_dur = max(1, TICKS_PER_16TH // 2)
            flick_vel = _clamp_int(int(vel * 0.55), 12, 100)
            out.append((flick_tick, flick_dur, flick_pitch, flick_vel))

    # Stable sort: ornaments might share ticks.
    out.sort(key=lambda x: (x[0], x[2], x[1]))

    # Safety: ensure every pitch is in-scale.
    pcs = _pitch_classes_for_scale(key, scale_type)
    cleaned: List[NoteTuple] = []
    for t, d, p, v in out:
        sp = _nearest_in_scale(p, scale_notes)
        if sp % 12 not in pcs:
            sp = _nearest_in_scale(sp, scale_notes)
        cleaned.append((int(t), int(d), int(sp), int(v)))

    return cleaned
