"""
MIDI Critic Feature Extraction

Extracts lightweight, deterministic features from a MIDI file so we can run
the "critics" quality gate without requiring upstream pipeline internals.

This powers JSON-RPC `run_critics_midi`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


@dataclass
class CriticFeatures:
    voicings: List[List[int]]
    bass_notes: List[Dict[str, int]]
    kick_ticks: List[int]
    tension_curve: List[float]
    note_density_per_beat: List[float]
    ticks_per_beat: int


def _iter_note_events(midi_path: str) -> Tuple[int, List[Tuple[int, int, int, int, int, str]]]:
    """Return (ticks_per_beat, notes) where notes are tuples:

    (start_tick, duration_ticks, pitch, velocity, channel, track_name)
    """
    import mido

    midi = mido.MidiFile(midi_path)
    ticks_per_beat = int(getattr(midi, "ticks_per_beat", 480) or 480)

    notes: List[Tuple[int, int, int, int, int, str]] = []

    for track in midi.tracks:
        abs_tick = 0
        track_name = getattr(track, "name", "") or ""
        active: Dict[Tuple[int, int], Tuple[int, int]] = {}  # (channel,pitch) -> (start_tick, velocity)

        for msg in track:
            abs_tick += int(getattr(msg, "time", 0) or 0)

            if not hasattr(msg, "type"):
                continue

            if msg.type == "note_on" and int(getattr(msg, "velocity", 0) or 0) > 0:
                ch = int(getattr(msg, "channel", 0) or 0)
                pitch = int(getattr(msg, "note", 0) or 0)
                vel = int(getattr(msg, "velocity", 0) or 0)
                active[(ch, pitch)] = (abs_tick, vel)
            elif msg.type in ("note_off", "note_on"):
                # note_on with velocity 0 is treated as note_off
                if msg.type == "note_on" and int(getattr(msg, "velocity", 0) or 0) != 0:
                    continue
                ch = int(getattr(msg, "channel", 0) or 0)
                pitch = int(getattr(msg, "note", 0) or 0)
                key = (ch, pitch)
                if key in active:
                    start_tick, vel = active.pop(key)
                    duration = max(0, abs_tick - start_tick)
                    notes.append((start_tick, duration, pitch, vel, ch, track_name))

        # If the file ends with hanging notes, close them at end-of-track tick.
        for (ch, pitch), (start_tick, vel) in list(active.items()):
            duration = max(0, abs_tick - start_tick)
            notes.append((start_tick, duration, int(pitch), int(vel), int(ch), track_name))

    return ticks_per_beat, notes


def extract_critic_features_from_midi(
    midi_path: str,
    *,
    time_signature: Tuple[int, int] = (4, 4),
    tension_curve: Optional[List[float]] = None,
) -> CriticFeatures:
    """Extract critic inputs from a MIDI file."""
    ticks_per_beat, notes = _iter_note_events(midi_path)

    # Kick on MIDI channel 10 (0-based channel 9), pitch 36 (GM kick).
    kick_ticks = sorted(
        int(t)
        for (t, _dur, pitch, vel, ch, _name) in notes
        if ch == 9 and pitch == 36 and vel > 0
    )

    # Bass notes: non-drum notes below middle C (MIDI < 60).
    bass_notes = [
        {"tick": int(t), "pitch": int(pitch)}
        for (t, _dur, pitch, _vel, ch, _name) in notes
        if ch != 9 and int(pitch) < 60
    ]

    # Voicings: group simultaneous chord-register notes.
    from collections import defaultdict

    tick_groups: Dict[int, List[int]] = defaultdict(list)
    for (t, _dur, pitch, vel, ch, _name) in notes:
        if ch == 9 or vel <= 0:
            continue
        p = int(pitch)
        if 48 <= p <= 96:
            tick_groups[int(t)].append(p)

    voicings = [
        sorted(v)
        for t, v in sorted(tick_groups.items(), key=lambda kv: kv[0])
        if len(v) >= 2
    ]

    # Density per bar (4/4 assumed unless specified).
    numerator, denominator = time_signature
    beats_per_bar = float(numerator) * (4.0 / float(denominator))
    ticks_per_bar = int(round(ticks_per_beat * beats_per_bar))
    if ticks_per_bar <= 0:
        ticks_per_bar = ticks_per_beat * 4

    max_tick = 0
    for (t, dur, _pitch, _vel, _ch, _name) in notes:
        max_tick = max(max_tick, int(t) + int(dur))
    total_bars = max(1, (max_tick // ticks_per_bar) + 1)

    bar_counts = [0] * total_bars
    for (t, _dur, _pitch, vel, ch, _name) in notes:
        if ch == 9 or vel <= 0:
            continue
        bar = int(t) // ticks_per_bar
        if 0 <= bar < total_bars:
            bar_counts[bar] += 1

    note_density_per_beat = [float(c) for c in bar_counts]

    if tension_curve is None:
        # Default tension ramp: encourages arrangements with build-ups.
        if total_bars == 1:
            tension_curve = [0.5]
        else:
            tension_curve = [
                round(0.2 + (0.7 * (i / float(total_bars - 1))), 4) for i in range(total_bars)
            ]

    return CriticFeatures(
        voicings=voicings,
        bass_notes=bass_notes,
        kick_ticks=kick_ticks,
        tension_curve=list(tension_curve),
        note_density_per_beat=note_density_per_beat,
        ticks_per_beat=ticks_per_beat,
    )

