#!/usr/bin/env python3
"""
Audio Diagnostic Script - Diagnose clipping and distortion issues in Ethiopian music generation.

This script:
1. Tests individual Ethiopian instrument synthesis
2. Checks for clipping in generated audio
3. Analyzes the mixing/rendering pipeline
4. Tests expansion system integration
"""

import os
import sys
from pathlib import Path
import numpy as np

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))

from multimodal_gen import (
    PromptParser,
    MidiGenerator,
    AudioRenderer,
    Arranger,
)
from multimodal_gen.assets_gen import (
    generate_krar_tone,
    generate_masenqo_tone,
    generate_washint_tone,
    generate_kebero_hit,
    normalize_audio,
)
from multimodal_gen.utils import SAMPLE_RATE


def print_header(title: str):
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}")


def analyze_audio(audio: np.ndarray, name: str):
    """Analyze audio for clipping and distortion."""
    peak = np.max(np.abs(audio))
    rms = np.sqrt(np.mean(audio ** 2))
    crest_factor = peak / rms if rms > 0 else 0
    
    # Check for clipping (samples at or very near ±1.0)
    clip_threshold = 0.99
    clipped_samples = np.sum(np.abs(audio) >= clip_threshold)
    clip_percentage = (clipped_samples / len(audio)) * 100
    
    # Check for DC offset
    dc_offset = np.mean(audio)
    
    # Check for asymmetry
    pos_max = np.max(audio)
    neg_min = np.min(audio)
    asymmetry = abs(pos_max + neg_min) / (pos_max - neg_min) if (pos_max - neg_min) > 0 else 0
    
    print(f"\n{name}:")
    print(f"  Peak:            {peak:.4f} ({20 * np.log10(peak + 1e-10):.1f} dB)")
    print(f"  RMS:             {rms:.4f} ({20 * np.log10(rms + 1e-10):.1f} dB)")
    print(f"  Crest Factor:    {crest_factor:.1f}")
    print(f"  DC Offset:       {dc_offset:.6f}")
    print(f"  Asymmetry:       {asymmetry:.4f}")
    print(f"  Clipped Samples: {clipped_samples} ({clip_percentage:.2f}%)")
    
    if clip_percentage > 0.1:
        print(f"  [!] WARNING: Significant clipping detected!")
    if abs(dc_offset) > 0.01:
        print(f"  [!] WARNING: DC offset detected!")
    if asymmetry > 0.2:
        print(f"  [!] WARNING: Asymmetric waveform detected!")
    
    return {
        'peak': peak,
        'rms': rms,
        'clipped': clipped_samples,
        'dc_offset': dc_offset,
    }


def test_individual_instruments():
    """Test each Ethiopian instrument synthesis in isolation."""
    print_header("INDIVIDUAL INSTRUMENT ANALYSIS")
    
    # Test at different frequencies and velocities
    test_cases = [
        ("C4", 261.63),
        ("A4", 440.0),
        ("C5", 523.25),
    ]
    
    results = {}
    
    for note, freq in test_cases:
        print(f"\n--- Testing at {note} ({freq:.1f} Hz) ---")
        
        # Krar
        krar = generate_krar_tone(freq, duration=1.0, velocity=0.8)
        results[f'krar_{note}'] = analyze_audio(krar, f"Krar ({note})")
        
        # Masenqo
        masenqo = generate_masenqo_tone(freq, duration=1.0, velocity=0.8)
        results[f'masenqo_{note}'] = analyze_audio(masenqo, f"Masenqo ({note})")
        
        # Washint
        washint = generate_washint_tone(freq, duration=1.0, velocity=0.8)
        results[f'washint_{note}'] = analyze_audio(washint, f"Washint ({note})")
    
    # Test kebero drum
    print("\n--- Testing Kebero Drum ---")
    kebero = generate_kebero_hit(60, velocity=0.9, sample_rate=SAMPLE_RATE)
    results['kebero'] = analyze_audio(kebero, "Kebero Hit")
    
    return results


def test_polyphonic_mixing():
    """Test what happens when multiple instruments play simultaneously."""
    print_header("POLYPHONIC MIXING ANALYSIS")
    
    freq = 440.0
    duration = 2.0
    
    # Generate individual tones
    krar = generate_krar_tone(freq, duration, velocity=0.7)
    masenqo = generate_masenqo_tone(freq * 1.5, duration, velocity=0.7)  # Perfect fifth
    washint = generate_washint_tone(freq * 2, duration, velocity=0.6)   # Octave
    
    # Ensure same length
    max_len = max(len(krar), len(masenqo), len(washint))
    krar = np.pad(krar, (0, max_len - len(krar)))
    masenqo = np.pad(masenqo, (0, max_len - len(masenqo)))
    washint = np.pad(washint, (0, max_len - len(washint)))
    
    # Simple sum (no mixing/normalization)
    raw_mix = krar + masenqo + washint
    analyze_audio(raw_mix, "Raw Sum (no normalization)")
    
    # Scaled sum (divide by number of sources)
    scaled_mix = (krar + masenqo + washint) / 3.0
    analyze_audio(scaled_mix, "Scaled Sum (divide by 3)")
    
    # Headroom-aware mix
    headroom_mix = (krar * 0.33 + masenqo * 0.33 + washint * 0.33)
    analyze_audio(headroom_mix, "Headroom Mix (0.33 each)")
    
    # Check the soft_clip from audio_renderer
    from multimodal_gen.audio_renderer import soft_clip
    soft_clipped = soft_clip(raw_mix, threshold=0.7, knee=0.3)
    analyze_audio(soft_clipped, "Soft Clipped Raw Mix")
    
    return raw_mix, scaled_mix


def test_full_generation():
    """Test the full generation pipeline with an Ethiopian prompt."""
    print_header("FULL GENERATION PIPELINE TEST")
    
    prompt = "eskista at 145 BPM in A minor"
    
    print(f"Prompt: \"{prompt}\"")
    
    # Parse
    parser = PromptParser()
    parsed = parser.parse(prompt)
    
    print(f"\nParsed:")
    print(f"  Genre: {parsed.genre}")
    print(f"  BPM: {parsed.bpm}")
    print(f"  Key: {parsed.key}")
    print(f"  Instruments: {parsed.instruments}")
    
    # Create arrangement
    arranger = Arranger()
    arrangement = arranger.create_arrangement(parsed)
    
    print(f"\nArrangement:")
    print(f"  Total bars: {arrangement.total_bars}")
    print(f"  Sections: {len(arrangement.sections)}")
    
    # Generate MIDI
    midi_gen = MidiGenerator()
    midi_file = midi_gen.generate(arrangement, parsed)
    
    print(f"\nMIDI Generated:")
    print(f"  Tracks: {len(midi_file.tracks)}")
    for i, track in enumerate(midi_file.tracks):
        name = "unknown"
        for msg in track:
            if msg.type == 'track_name':
                name = msg.name
                break
        note_count = sum(1 for msg in track if msg.type == 'note_on')
        print(f"    Track {i}: {name} ({note_count} notes)")
    
    # Save temporary MIDI for testing
    import tempfile
    with tempfile.NamedTemporaryFile(suffix='.mid', delete=False) as f:
        midi_path = f.name
    midi_file.save(midi_path)
    
    # Render audio (procedural)
    print(f"\nRendering audio...")
    renderer = AudioRenderer(use_fluidsynth=False)
    
    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
        audio_path = f.name
    
    success = renderer.render_midi_file(midi_path, audio_path, parsed)
    
    if success:
        # Load and analyze the rendered audio
        import soundfile as sf
        audio, sr = sf.read(audio_path)
        
        if len(audio.shape) > 1:
            # Stereo - analyze both channels
            analyze_audio(audio[:, 0], "Rendered Audio (Left)")
            analyze_audio(audio[:, 1], "Rendered Audio (Right)")
            analyze_audio(np.mean(audio, axis=1), "Rendered Audio (Mono Mix)")
        else:
            analyze_audio(audio, "Rendered Audio")
        
        print(f"\nAudio saved to: {audio_path}")
    else:
        print("  [!] Audio rendering failed!")
    
    # Cleanup
    os.unlink(midi_path)
    
    return audio_path if success else None


def check_expansion_integration():
    """Check if ExpansionManager is integrated into the pipeline."""
    print_header("EXPANSION SYSTEM INTEGRATION CHECK")
    
    try:
        from multimodal_gen import ExpansionManager
        print("[OK] ExpansionManager imported successfully")
    except ImportError as e:
        print(f"[X] ExpansionManager import failed: {e}")
        return
    
    # Check if main.py uses ExpansionManager
    main_py = Path(__file__).parent / "main.py"
    if main_py.exists():
        content = main_py.read_text(encoding='utf-8')
        if "ExpansionManager" in content:
            print("[OK] ExpansionManager referenced in main.py")
        else:
            print("[X] ExpansionManager NOT used in main.py - this is the integration gap!")
    
    # Check if audio_renderer.py uses ExpansionManager
    renderer_py = Path(__file__).parent / "multimodal_gen" / "audio_renderer.py"
    if renderer_py.exists():
        content = renderer_py.read_text(encoding='utf-8')
        if "ExpansionManager" in content or "expansion" in content.lower():
            print("[OK] Expansion system referenced in audio_renderer.py")
        else:
            print("[X] Expansion system NOT integrated in audio_renderer.py - samples not being used!")
    
    # Check available expansions
    expansions_dir = Path(__file__).parent.parent / "expansions"
    if expansions_dir.exists():
        manager = ExpansionManager()
        count = manager.scan_expansions(str(expansions_dir))
        print(f"[OK] Found {count} expansion pack(s) in {expansions_dir}")
        
        # Test resolution for Ethiopian instruments
        print("\nTesting Ethiopian instrument resolution:")
        ethiopian_instruments = ['krar', 'masenqo', 'washint', 'kebero']
        for inst in ethiopian_instruments:
            result = manager.resolve_instrument(inst, genre='eskista')
            if result:
                print(f"  {inst} -> {result.resolved_name} ({result.match_type.name}, {result.confidence:.0%})")
            else:
                print(f"  {inst} -> NO RESOLUTION (using procedural synthesis)")
    else:
        print(f"[X] Expansions directory not found: {expansions_dir}")


def main():
    """Run all diagnostics."""
    print_header("AUDIO DIAGNOSTIC TOOL")
    print("Diagnosing clipping and distortion issues in Ethiopian music generation")
    
    # 1. Test individual instruments
    test_individual_instruments()
    
    # 2. Test polyphonic mixing
    test_polyphonic_mixing()
    
    # 3. Check expansion integration
    check_expansion_integration()
    
    # 4. Test full generation
    audio_path = test_full_generation()
    
    print_header("SUMMARY")
    print("""
Key findings to investigate:
1. Individual instrument synthesis - check for clipping
2. Polyphonic mixing - check gain staging  
3. Expansion integration - ExpansionManager not wired to render pipeline
4. Full generation - check final audio for distortion

Recommended fixes:
- Wire ExpansionManager into AudioRenderer to use real samples
- Add gain staging in mix_stereo_tracks()
- Reduce individual instrument output levels
- Add per-track limiter before final mix
""")
    
    if audio_path:
        print(f"\nTest audio saved to: {audio_path}")
        print("Open in a DAW to visually inspect waveform for clipping.")


if __name__ == '__main__':
    main()

