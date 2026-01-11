import random

# Add parent directory to path for imports
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from multimodal_gen.ethio_melody import embellish_melody_qenet
from multimodal_gen.utils import ScaleType, get_scale_notes


def _pitch_classes(key: str, scale_type: ScaleType) -> set[int]:
    # Generate a wide set of notes to avoid octave edge cases.
    notes = get_scale_notes(key, scale_type, octave=1, num_octaves=8)
    return {n % 12 for n in notes}


def test_qenet_embellisher_keeps_notes_in_mode():
    rng = random.Random(1337)
    key = "C"
    scale = ScaleType.TIZITA_MAJOR

    # Simple skeleton melody.
    melody = [
        (120, 240, 72, 90),
        (480, 240, 74, 88),
        (840, 480, 76, 92),
        (1440, 240, 77, 84),
        (1680, 240, 79, 86),
    ]

    out = embellish_melody_qenet(
        melody,
        key=key,
        scale_type=scale,
        time_signature=(6, 8),
        section_bars=4,
        complexity=0.92,
        call_response=True,
        rng=rng,
    )

    pcs = _pitch_classes(key, scale)
    assert out, "Expected non-empty embellished melody"
    assert all(p % 12 in pcs for (_, _, p, _) in out), "All pitches must remain in the qenet mode"


def test_qenet_embellisher_high_complexity_adds_events():
    rng = random.Random(7)
    key = "D"
    scale = ScaleType.AMBASSEL

    melody = [
        (240, 480, 74, 90),
        (960, 480, 77, 88),
        (1680, 960, 81, 92),
    ]

    low = embellish_melody_qenet(
        melody,
        key=key,
        scale_type=scale,
        time_signature=(12, 8),
        section_bars=4,
        complexity=0.40,
        call_response=True,
        rng=rng,
    )

    rng = random.Random(7)
    high = embellish_melody_qenet(
        melody,
        key=key,
        scale_type=scale,
        time_signature=(12, 8),
        section_bars=4,
        complexity=0.95,
        call_response=True,
        rng=rng,
    )

    # Low complexity should mostly just snap to scale, not create more events.
    assert len(low) == len(melody)
    assert len(high) >= len(melody)
    assert len(high) > len(low)
