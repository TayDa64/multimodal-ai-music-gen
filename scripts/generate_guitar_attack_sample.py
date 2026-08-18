"""Generate a self-owned guitar pick/pluck attack transient for the hybrid layer.

Derived from the guitar physical-modeling engine (`generate_guitar_tone`, whose
Karplus-Strong core + pick transient are internally seeded and deterministic) so
the onset inherits real pick/string character instead of a generic noise recipe.
The rendered note's onset is windowed to <=60 ms and fast-faded so only the
attack remains -- no sustained pitched note. Peak-normalized (not loudness
boosted); the renderer applies its own velocity-scaled mix gain.

Run:
    python scripts/generate_guitar_attack_sample.py
Writes:
    assets/attack_samples/guitar/guitar_pick_transient_v1.wav
"""

from pathlib import Path
import sys

import numpy as np
import soundfile as sf

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from multimodal_gen.assets_gen import generate_guitar_tone

SAMPLE_RATE = 44100
# Deterministic render args (generate_guitar_tone seeds its RNG from these).
PITCH_HZ = 196.0   # G3, a mid guitar pitch
RENDER_S = 0.15    # render long enough for a fully formed onset, then window
VELOCITY = 0.9
DRIVE = 0.5
WINDOW_S = 0.060   # 60 ms hard cap
FADE_TAU_S = 0.014  # fast onset-only decay so no sustained note remains


def generate_guitar_pick_transient(sample_rate: int = SAMPLE_RATE) -> np.ndarray:
    # Render a note from the physical model, then keep only its onset.
    note = generate_guitar_tone(PITCH_HZ, RENDER_S, VELOCITY, sample_rate, drive=DRIVE)
    n = int(WINDOW_S * sample_rate)
    audio = np.asarray(note[:n], dtype=np.float64)
    if audio.size == 0:
        return audio.astype(np.float32)

    t = np.arange(audio.size) / sample_rate
    audio *= np.exp(-t / FADE_TAU_S)  # attack-only: fade out the sustain

    fade = min(audio.size, int(0.006 * sample_rate))
    if fade > 0:
        audio[-fade:] *= np.linspace(1.0, 0.0, fade)

    audio = np.nan_to_num(audio, nan=0.0, posinf=0.0, neginf=0.0)
    peak = float(np.max(np.abs(audio))) if audio.size else 0.0
    if peak > 1e-9:
        audio = audio / peak
    return audio.astype(np.float32)


def main() -> None:
    out_dir = Path(__file__).resolve().parent.parent / "assets" / "attack_samples" / "guitar"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "guitar_pick_transient_v1.wav"
    audio = generate_guitar_pick_transient()
    sf.write(str(out_path), audio, SAMPLE_RATE, subtype="FLOAT")
    print(f"wrote {out_path} ({audio.size} samples, {audio.size / SAMPLE_RATE * 1000:.1f} ms)")


if __name__ == "__main__":
    main()
