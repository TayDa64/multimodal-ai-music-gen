"""
Task 129 self-proof: build real Ethiopian sample banks from copied MP3s,
print per-instrument extraction stats, save a few sample WAVs + a JSON summary.
"""
import json
from pathlib import Path
from collections import Counter

import numpy as np
import librosa
import soundfile as sf

from multimodal_gen import ethiopian_samples as es
from multimodal_gen.utils import SAMPLE_RATE

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = REPO_ROOT / "output" / "_diagnostics" / "task129_ethiopian_sample_bank_build_20260628"
INSTRUMENTS = ["krar", "masenqo", "begena"]


def source_durations(instrument):
    total = 0.0
    per = {}
    for fn in es.INSTRUMENT_SOURCES.get(instrument, []):
        p = es.DEFAULT_REFS_DIR / fn
        if p.exists():
            try:
                dur = float(librosa.get_duration(path=str(p)))
            except Exception:
                y, sr = librosa.load(str(p), sr=SAMPLE_RATE, mono=True)
                dur = len(y) / sr
            per[fn] = round(dur, 3)
            total += dur
    return round(total, 3), per


def count_segments(instrument):
    """Re-run segmentation to report raw segment count (pre-filter)."""
    total_segments = 0
    for fn in es.INSTRUMENT_SOURCES.get(instrument, []):
        p = es.DEFAULT_REFS_DIR / fn
        if not p.exists():
            continue
        y, sr = librosa.load(str(p), sr=SAMPLE_RATE, mono=True)
        segs = es._segment_boundaries(np, librosa, y.astype(np.float32), SAMPLE_RATE)
        total_segments += len(segs)
    return total_segments


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    summary = {"sample_rate": SAMPLE_RATE, "instruments": {}}

    for inst in INSTRUMENTS:
        total_dur, per_src = source_durations(inst)
        segments_found = count_segments(inst)
        samples = es.build_sample_bank(inst, force=True)

        roots = [s["root_note"] for s in samples]
        f0s = [s["f0_hz"] for s in samples]
        loops = sum(1 for s in samples
                    if s.get("loop_start_sample") is not None)
        dist = dict(sorted(Counter(roots).items())) if roots else {}

        info = {
            "source_duration_sec": total_dur,
            "per_source_duration_sec": per_src,
            "segments_found": segments_found,
            "kept_samples": len(samples),
            "root_note_min": min(roots) if roots else None,
            "root_note_max": max(roots) if roots else None,
            "root_note_distribution": dist,
            "f0_min_hz": round(min(f0s), 2) if f0s else None,
            "f0_max_hz": round(max(f0s), 2) if f0s else None,
            "sustain_loops_found": loops,
            "saved_wavs": [],
        }

        # Save 2-3 sample WAVs (highest confidence).
        top = sorted(samples, key=lambda s: -s["confidence"])[:3]
        for k, s in enumerate(top):
            wav_name = f"{inst}_sample{k+1}_root{s['root_note']:02d}.wav"
            wav_path = OUT_DIR / wav_name
            sf.write(str(wav_path), s["audio"], s["sample_rate"])
            info["saved_wavs"].append(wav_name)

        summary["instruments"][inst] = info

        print(f"\n=== {inst.upper()} ===")
        print(f"  source duration : {total_dur}s {per_src}")
        print(f"  segments found  : {segments_found}")
        print(f"  kept samples    : {len(samples)}")
        print(f"  root_note range : {info['root_note_min']}..{info['root_note_max']}")
        print(f"  distribution    : {dist}")
        print(f"  f0 range (Hz)   : {info['f0_min_hz']}..{info['f0_max_hz']}")
        print(f"  sustain loops   : {loops}")
        print(f"  saved WAVs      : {info['saved_wavs']}")

    summary_path = OUT_DIR / "build_summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    print(f"\nSummary written: {summary_path}")


if __name__ == "__main__":
    main()
