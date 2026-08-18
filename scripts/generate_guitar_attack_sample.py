"""Generate a self-owned guitar pick/pluck attack transient for the hybrid layer.

Deterministic (seeded) so the shipped asset is reproducible. The output is a
short broadband pick onset only -- an initial contact click, pick-scrape noise,
and a brief body "thock" -- with a fast decay to near-silence by <=60 ms and no
pitched/sustained content. Peak-normalized (not loudness-boosted); the renderer
applies its own velocity-scaled mix gain.

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
from multimodal_gen.assets_gen import bandpass_filter, highpass_filter, lowpass_filter

SAMPLE_RATE = 44100
SEED = 20260818
DURATION_S = 0.060  # 60 ms hard cap; useful energy sits in the first ~30 ms


def generate_guitar_pick_transient(sample_rate: int = SAMPLE_RATE, seed: int = SEED) -> np.ndarray:
    rng = np.random.default_rng(seed)
    n = int(DURATION_S * sample_rate)
    t = np.arange(n) / sample_rate

    # Initial contact click: very short bright impulse-like burst (~0.8 ms).
    click = rng.standard_normal(n)
    click = highpass_filter(click, 3000.0, sample_rate)
    click *= np.exp(-t / 0.0008)

    # Pick-scrape noise: bright band, the bulk of the transient (~15-25 ms).
    scrape = rng.standard_normal(n)
    scrape = bandpass_filter(scrape, 1200.0, 6500.0, sample_rate)
    scrape *= np.exp(-t / 0.010)

    # Body "thock": low-mid weight so the onset is not thin (~10 ms).
    thock = rng.standard_normal(n)
    thock = bandpass_filter(thock, 150.0, 500.0, sample_rate)
    thock *= np.exp(-t / 0.006)

    audio = 1.0 * click + 0.9 * scrape + 0.55 * thock

    # Overall fast decay + hard fade to zero by the end (no click at the tail).
    audio *= np.exp(-t / 0.014)
    fade = min(n, int(0.006 * sample_rate))
    if fade > 0:
        audio[-fade:] *= np.linspace(1.0, 0.0, fade)

    audio = lowpass_filter(audio, 9000.0, sample_rate)  # tame harsh aliasing
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
