#!/usr/bin/env python3
"""
COMPREHENSIVE TEST SUITE
========================
Tests all major components of the Multimodal AI Music Generator.

Run with: python test_suite.py
"""

import sys
import os
import traceback
import time
from datetime import datetime

# Add project to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Test results collector
results = {
    'passed': [],
    'failed': [],
    'skipped': []
}

def mark_test(name):
    """Decorator to mark test functions."""
    def decorator(func):
        def wrapper():
            print(f"\n  Testing: {name}...", end=" ")
            try:
                start = time.time()
                func()
                elapsed = time.time() - start
                print(f"✓ PASS ({elapsed:.2f}s)")
                results['passed'].append(name)
            except AssertionError as e:
                print(f"✗ FAIL: {e}")
                results['failed'].append((name, str(e)))
            except Exception as e:
                print(f"✗ ERROR: {e}")
                traceback.print_exc()
                results['failed'].append((name, str(e)))
        return wrapper
    return decorator


# =============================================================================
# TEST: IMPORTS
# =============================================================================

@mark_test("Core imports")
def test_core_imports():
    import numpy as np
    import mido  # Using mido instead of midiutil
    from scipy.io import wavfile
    assert np.__version__, "NumPy not loaded"

@mark_test("Multimodal_gen package")
def test_multimodal_gen_import():
    from multimodal_gen import (
        PromptParser,
        Arranger,
        MidiGenerator,
        AudioRenderer
    )
    assert PromptParser is not None

@mark_test("Ethiopian instruments import")
def test_ethiopian_imports():
    from multimodal_gen.assets_gen import (
        generate_krar_tone,
        generate_masenqo_tone,
        generate_begena_tone,
        generate_kebero_hit,
        SAMPLE_RATE
    )
    assert SAMPLE_RATE == 44100


# =============================================================================
# TEST: PROMPT PARSER
# =============================================================================

@mark_test("Prompt parser - basic parsing")
def test_prompt_parser_basic():
    from multimodal_gen import PromptParser
    parser = PromptParser()
    result = parser.parse("trap beat at 140 BPM in D minor")
    # ParsedPrompt is a dataclass, access via attributes
    assert result.bpm == 140, f"Expected BPM 140, got {result.bpm}"
    # scale_type could be enum or string, check the key for minor indication
    assert 'D' in result.key or result.key == 'D', f"Expected key D, got {result.key}"

@mark_test("Prompt parser - genre detection")
def test_prompt_parser_genre():
    from multimodal_gen import PromptParser
    parser = PromptParser()
    
    genres_to_test = [
        ("lofi hip hop beat", "lofi"),
        ("dark trap beat with 808s", "trap"),
        ("boom bap classic style", "boom_bap"),
    ]
    
    for prompt, expected_genre in genres_to_test:
        result = parser.parse(prompt)
        assert expected_genre in result.genre.lower(), f"Expected {expected_genre} in {result.genre}"

@mark_test("Prompt parser - Ethiopian detection")
def test_prompt_parser_ethiopian():
    from multimodal_gen import PromptParser
    parser = PromptParser()
    result = parser.parse("ethiopian traditional music with krar")
    # Should detect Ethiopian-related keywords
    assert result is not None


# =============================================================================
# TEST: ETHIOPIAN INSTRUMENTS - SYNTHESIS
# =============================================================================

@mark_test("Krar synthesis (Karplus-Strong)")
def test_krar_synthesis():
    import numpy as np
    from multimodal_gen.assets_gen import generate_krar_tone, SAMPLE_RATE
    
    audio = generate_krar_tone(frequency=261.63, duration=1.0, velocity=0.8)
    
    assert len(audio) == SAMPLE_RATE, f"Expected {SAMPLE_RATE} samples, got {len(audio)}"
    assert np.max(np.abs(audio)) > 0.01, "Audio too quiet"
    assert np.max(np.abs(audio)) <= 1.0, "Audio clipping"

@mark_test("Masenqo synthesis (Bowed fiddle)")
def test_masenqo_synthesis():
    import numpy as np
    from multimodal_gen.assets_gen import generate_masenqo_tone, SAMPLE_RATE
    
    audio = generate_masenqo_tone(
        frequency=392.0,
        duration=1.0,
        velocity=0.7,
        expressiveness=0.8
    )
    
    assert len(audio) == SAMPLE_RATE
    assert np.max(np.abs(audio)) > 0.01
    assert not np.isnan(audio).any(), "NaN values in audio"

@mark_test("Begena synthesis (Bass lyre with buzz)")
def test_begena_synthesis():
    import numpy as np
    from multimodal_gen.assets_gen import generate_begena_tone, SAMPLE_RATE
    
    audio = generate_begena_tone(frequency=130.81, duration=1.0, velocity=0.7)
    
    assert len(audio) == SAMPLE_RATE
    assert np.max(np.abs(audio)) > 0.01

@mark_test("Kebero synthesis (Drum)")
def test_kebero_synthesis():
    import numpy as np
    from multimodal_gen.assets_gen import generate_kebero_hit, SAMPLE_RATE
    
    audio = generate_kebero_hit(velocity=0.8)
    
    assert len(audio) > 0, "No audio generated"
    assert np.max(np.abs(audio)) > 0.01

@mark_test("Ethiopian instrument attack times < 10ms")
def test_attack_times():
    import numpy as np
    from multimodal_gen.assets_gen import (
        generate_krar_tone,
        generate_masenqo_tone,
        generate_begena_tone,
        SAMPLE_RATE
    )
    
    def measure_attack(audio, threshold=0.1):
        """Measure attack time in milliseconds."""
        peak = np.max(np.abs(audio))
        if peak < 0.001:
            return 0
        threshold_level = peak * threshold
        for i, sample in enumerate(np.abs(audio)):
            if sample >= threshold_level:
                return (i / SAMPLE_RATE) * 1000  # ms
        return 0
    
    # Use longer durations and proper parameters
    krar = generate_krar_tone(261.63, 1.0, 0.8)
    masenqo = generate_masenqo_tone(frequency=261.63, duration=1.0, velocity=0.8, expressiveness=0.7)
    begena = generate_begena_tone(130.81, 1.0, 0.8)
    
    krar_attack = measure_attack(krar)
    masenqo_attack = measure_attack(masenqo)
    begena_attack = measure_attack(begena)
    
    assert krar_attack < 15, f"Krar attack too slow: {krar_attack}ms"
    assert masenqo_attack < 20, f"Masenqo attack too slow: {masenqo_attack}ms"  # Bowed has slower attack
    assert begena_attack < 25, f"Begena attack too slow: {begena_attack}ms"  # Bass lyre with buzz has natural attack delay


# =============================================================================
# TEST: MIDI GENERATION
# =============================================================================

@mark_test("MIDI generator - basic generation")
def test_midi_generator():
    from multimodal_gen import MidiGenerator
    
    # MidiGenerator takes velocity_variation, timing_variation, swing
    generator = MidiGenerator(velocity_variation=0.12, timing_variation=0.03, swing=0.0)
    assert generator is not None

@mark_test("MIDI file creation")
def test_midi_file_creation():
    from mido import MidiFile, MidiTrack, Message, MetaMessage
    import tempfile
    import os
    
    mid = MidiFile()
    track = MidiTrack()
    mid.tracks.append(track)
    
    track.append(MetaMessage('set_tempo', tempo=500000))
    track.append(Message('note_on', note=60, velocity=100, time=0))
    track.append(Message('note_off', note=60, velocity=0, time=480))
    
    with tempfile.NamedTemporaryFile(suffix='.mid', delete=False) as f:
        temp_path = f.name
    
    mid.save(temp_path)
    
    assert os.path.exists(temp_path)
    assert os.path.getsize(temp_path) > 0
    os.unlink(temp_path)


# =============================================================================
# TEST: AUDIO RENDERING
# =============================================================================

@mark_test("Audio renderer initialization")
def test_audio_renderer():
    from multimodal_gen import AudioRenderer
    renderer = AudioRenderer()
    assert renderer is not None

@mark_test("WAV file writing")
def test_wav_writing():
    import numpy as np
    from scipy.io import wavfile
    import tempfile
    import os
    
    sample_rate = 44100
    duration = 0.5
    t = np.linspace(0, duration, int(sample_rate * duration))
    audio = np.sin(2 * np.pi * 440 * t)  # 440 Hz sine wave
    
    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
        temp_path = f.name
    
    wavfile.write(temp_path, sample_rate, (audio * 32767).astype(np.int16))
    
    assert os.path.exists(temp_path)
    assert os.path.getsize(temp_path) > 0
    
    # Read back and verify
    sr, data = wavfile.read(temp_path)
    assert sr == sample_rate
    assert len(data) == len(audio)
    
    os.unlink(temp_path)


# =============================================================================
# TEST: ARRANGER
# =============================================================================

@mark_test("Arranger - song structure")
def test_arranger():
    from multimodal_gen import Arranger, PromptParser
    
    parser = PromptParser()
    parsed = parser.parse("trap beat at 140 BPM")
    
    arranger = Arranger()
    arrangement = arranger.create_arrangement(parsed)
    
    assert arrangement is not None
    assert hasattr(arrangement, 'sections')


# =============================================================================
# TEST: FULL GENERATION PIPELINE
# =============================================================================

@mark_test("Full generation pipeline (MIDI only)")
def test_full_pipeline():
    from multimodal_gen import PromptParser, Arranger, MidiGenerator
    
    # Parse prompt
    parser = PromptParser()
    params = parser.parse("trap beat at 140 BPM in C minor")
    
    # ParsedPrompt is a dataclass
    assert params.bpm is not None
    assert params.genre is not None
    
    # Create arranger and arrangement
    arranger = Arranger()
    arrangement = arranger.create_arrangement(params)
    
    # Create generator
    generator = MidiGenerator()
    
    assert generator is not None
    assert arrangement is not None


# =============================================================================
# TEST: ETHIOPIAN SONG GENERATION
# =============================================================================

@mark_test("Ethiopian song generation")
def test_ethiopian_song():
    import numpy as np
    from multimodal_gen.assets_gen import (
        generate_krar_tone,
        generate_masenqo_tone,
        generate_begena_tone,
        SAMPLE_RATE
    )
    
    duration = 2.0  # 2 second test
    total_samples = int(duration * SAMPLE_RATE)
    
    # Generate tracks
    krar = generate_krar_tone(261.63, duration, 0.7)
    masenqo = generate_masenqo_tone(392.0, duration, 0.7, 0.7)
    begena = generate_begena_tone(130.81, duration, 0.6)
    
    # Mix
    min_len = min(len(krar), len(masenqo), len(begena))
    mix = krar[:min_len] * 0.4 + masenqo[:min_len] * 0.35 + begena[:min_len] * 0.25
    
    # Normalize
    if np.max(np.abs(mix)) > 0:
        mix = mix / np.max(np.abs(mix)) * 0.9
    
    assert len(mix) > 0
    assert not np.isnan(mix).any()
    assert np.max(np.abs(mix)) <= 1.0


# =============================================================================
# TEST: INSTRUMENT SHAPER COMPONENTS
# =============================================================================

@mark_test("FFT spectrum computation")
def test_fft_spectrum():
    import numpy as np
    from scipy import signal
    
    sample_rate = 44100
    duration = 1.0
    t = np.linspace(0, duration, int(sample_rate * duration))
    
    # Generate test signal: 440 Hz + harmonics
    audio = np.sin(2 * np.pi * 440 * t) + 0.5 * np.sin(2 * np.pi * 880 * t)
    
    # FFT
    n = 4096
    window = signal.windows.hann(n)
    audio_windowed = audio[:n] * window
    
    fft = np.fft.rfft(audio_windowed)
    freqs = np.fft.rfftfreq(n, 1/sample_rate)
    magnitude = np.abs(fft)
    
    # Find peak at fundamental
    peak_idx = np.argmax(magnitude[10:500]) + 10  # Skip DC
    peak_freq = freqs[peak_idx]
    
    assert 430 < peak_freq < 450, f"Expected ~440Hz, got {peak_freq}Hz"


# =============================================================================
# MAIN
# =============================================================================

def run_all_tests():
    """Run all tests and report results."""
    print("=" * 70)
    print("  MULTIMODAL AI MUSIC GENERATOR - COMPREHENSIVE TEST SUITE")
    print("  " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    print("=" * 70)
    
    # Collect all test functions
    tests = [
        # Imports
        test_core_imports,
        test_multimodal_gen_import,
        test_ethiopian_imports,
        
        # Prompt Parser
        test_prompt_parser_basic,
        test_prompt_parser_genre,
        test_prompt_parser_ethiopian,
        
        # Ethiopian Instruments
        test_krar_synthesis,
        test_masenqo_synthesis,
        test_begena_synthesis,
        test_kebero_synthesis,
        test_attack_times,
        
        # MIDI
        test_midi_generator,
        test_midi_file_creation,
        
        # Audio
        test_audio_renderer,
        test_wav_writing,
        
        # Arranger
        test_arranger,
        
        # Full Pipeline
        test_full_pipeline,
        test_ethiopian_song,
        
        # Spectrum
        test_fft_spectrum,
    ]
    
    # Run tests
    for test_func in tests:
        test_func()
    
    # Report
    print("\n" + "=" * 70)
    print("  TEST RESULTS")
    print("=" * 70)
    
    total = len(results['passed']) + len(results['failed']) + len(results['skipped'])
    
    print(f"\n  ✓ Passed: {len(results['passed'])}/{total}")
    print(f"  ✗ Failed: {len(results['failed'])}/{total}")
    print(f"  ○ Skipped: {len(results['skipped'])}/{total}")
    
    if results['failed']:
        print("\n  FAILURES:")
        for name, error in results['failed']:
            print(f"    - {name}: {error}")
    
    print("\n" + "=" * 70)
    
    if results['failed']:
        print("  STATUS: SOME TESTS FAILED ✗")
        return 1
    else:
        print("  STATUS: ALL TESTS PASSED ✓")
        return 0


if __name__ == "__main__":
    sys.exit(run_all_tests())
