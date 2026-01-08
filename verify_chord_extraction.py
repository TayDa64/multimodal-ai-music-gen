#!/usr/bin/env python
"""
Manual verification script for chord extraction.

Generates synthetic audio with known chords and verifies extraction.
"""

import numpy as np
from multimodal_gen.chord_extractor import (
    ChordExtractor,
    extract_chords,
    chords_to_midi,
)


def generate_chord_audio(frequencies, duration, sample_rate=44100):
    """Generate audio for a chord given frequencies."""
    t = np.linspace(0, duration, int(sample_rate * duration))
    audio = np.zeros_like(t)
    
    for freq in frequencies:
        audio += np.sin(2 * np.pi * freq * t)
    
    # Normalize
    if audio.max() > 0:
        audio = audio / audio.max() * 0.8
    
    return audio


def test_c_major_progression():
    """Test C-F-G-C progression."""
    print("=" * 60)
    print("Test 1: C Major - F Major - G Major - C Major Progression")
    print("=" * 60)
    
    sample_rate = 44100
    chord_duration = 2.0
    
    # Frequencies for chords (Hz)
    # C major: C4, E4, G4
    c_major = [261.63, 329.63, 392.00]
    # F major: F4, A4, C5
    f_major = [349.23, 440.00, 523.25]
    # G major: G4, B4, D5
    g_major = [392.00, 493.88, 587.33]
    
    # Generate audio for each chord
    audio_parts = []
    audio_parts.append(generate_chord_audio(c_major, chord_duration, sample_rate))
    audio_parts.append(generate_chord_audio(f_major, chord_duration, sample_rate))
    audio_parts.append(generate_chord_audio(g_major, chord_duration, sample_rate))
    audio_parts.append(generate_chord_audio(c_major, chord_duration, sample_rate))
    
    # Concatenate
    audio = np.concatenate(audio_parts)
    
    # Extract chords
    extractor = ChordExtractor(sample_rate=sample_rate)
    progression = extractor.analyze(audio, min_chord_duration=0.5)
    
    print(f"\nDetected Key: {progression.key} {progression.mode}")
    print(f"Number of chords detected: {len(progression.chords)}")
    print("\nChord Progression:")
    for i, chord in enumerate(progression.chords):
        print(f"  {i+1}. {chord.chord:10s} "
              f"({chord.start_time:5.2f}s - {chord.end_time:5.2f}s) "
              f"confidence: {chord.confidence:.2f}")
    
    # Expected: Should detect 4 chords, key of C major
    print("\n✓ Test completed")
    return progression


def test_a_minor_progression():
    """Test A minor - D minor - E major - A minor progression."""
    print("\n" + "=" * 60)
    print("Test 2: A Minor - D Minor - E Major - A Minor Progression")
    print("=" * 60)
    
    sample_rate = 44100
    chord_duration = 2.0
    
    # Frequencies for chords
    # A minor: A4, C5, E5
    a_minor = [440.00, 523.25, 659.25]
    # D minor: D4, F4, A4
    d_minor = [293.66, 349.23, 440.00]
    # E major: E4, G#4, B4
    e_major = [329.63, 415.30, 493.88]
    
    # Generate audio
    audio_parts = []
    audio_parts.append(generate_chord_audio(a_minor, chord_duration, sample_rate))
    audio_parts.append(generate_chord_audio(d_minor, chord_duration, sample_rate))
    audio_parts.append(generate_chord_audio(e_major, chord_duration, sample_rate))
    audio_parts.append(generate_chord_audio(a_minor, chord_duration, sample_rate))
    
    audio = np.concatenate(audio_parts)
    
    # Extract chords
    progression = extract_chords(audio, sample_rate=sample_rate)
    
    print(f"\nDetected Key: {progression.key} {progression.mode}")
    print(f"Number of chords detected: {len(progression.chords)}")
    print("\nChord Progression:")
    for i, chord in enumerate(progression.chords):
        print(f"  {i+1}. {chord.chord:10s} "
              f"({chord.start_time:5.2f}s - {chord.end_time:5.2f}s) "
              f"confidence: {chord.confidence:.2f}")
    
    print("\n✓ Test completed")
    return progression


def test_midi_conversion():
    """Test converting chord progression to MIDI."""
    print("\n" + "=" * 60)
    print("Test 3: MIDI Conversion")
    print("=" * 60)
    
    # Create a simple progression
    sample_rate = 44100
    c_major = [261.63, 329.63, 392.00]
    g_major = [392.00, 493.88, 587.33]
    
    audio = np.concatenate([
        generate_chord_audio(c_major, 2.0, sample_rate),
        generate_chord_audio(g_major, 2.0, sample_rate),
    ])
    
    progression = extract_chords(audio, sample_rate=sample_rate)
    
    # Convert to MIDI
    midi_notes = chords_to_midi(progression, ticks_per_beat=480)
    
    print(f"\nGenerated {len(midi_notes)} MIDI notes")
    print("\nFirst 6 MIDI notes:")
    for i, (tick, duration, pitch, velocity) in enumerate(midi_notes[:6]):
        print(f"  {i+1}. Tick: {tick:6d}, Duration: {duration:6d}, "
              f"Pitch: {pitch:3d}, Velocity: {velocity:3d}")
    
    print("\n✓ Test completed")
    return midi_notes


def test_key_detection():
    """Test key detection with different keys."""
    print("\n" + "=" * 60)
    print("Test 4: Key Detection")
    print("=" * 60)
    
    sample_rate = 44100
    duration = 3.0
    
    test_cases = [
        ("C major", [261.63, 329.63, 392.00]),  # C, E, G
        ("G major", [392.00, 493.88, 587.33]),  # G, B, D
        ("D major", [293.66, 369.99, 440.00]),  # D, F#, A
        ("A minor", [440.00, 523.25, 659.25]),  # A, C, E
        ("E minor", [329.63, 392.00, 493.88]),  # E, G, B
    ]
    
    extractor = ChordExtractor(sample_rate=sample_rate)
    
    print("\nKey Detection Results:")
    for expected_key, frequencies in test_cases:
        audio = generate_chord_audio(frequencies, duration, sample_rate)
        progression = extractor.analyze(audio)
        
        detected = f"{progression.key} {progression.mode}"
        match = "✓" if expected_key.split()[0] == progression.key else "✗"
        print(f"  {match} Expected: {expected_key:15s} -> Detected: {detected}")
    
    print("\n✓ Test completed")


def test_chord_types():
    """Test detection of different chord types."""
    print("\n" + "=" * 60)
    print("Test 5: Different Chord Types")
    print("=" * 60)
    
    sample_rate = 44100
    duration = 2.0
    
    # Test different chord qualities
    test_chords = [
        ("C major", [261.63, 329.63, 392.00]),      # C, E, G
        ("C minor", [261.63, 311.13, 392.00]),      # C, Eb, G
        ("C diminished", [261.63, 311.13, 369.99]), # C, Eb, Gb
        ("C augmented", [261.63, 329.63, 415.30]),  # C, E, G#
    ]
    
    extractor = ChordExtractor(sample_rate=sample_rate)
    
    print("\nChord Type Detection:")
    for expected, frequencies in test_chords:
        audio = generate_chord_audio(frequencies, duration, sample_rate)
        progression = extractor.analyze(audio)
        
        if progression.chords:
            detected = progression.chords[0]
            print(f"  Expected: {expected:15s} -> Detected: {detected.chord:10s} "
                  f"(confidence: {detected.confidence:.2f})")
        else:
            print(f"  Expected: {expected:15s} -> No chord detected")
    
    print("\n✓ Test completed")


def main():
    """Run all verification tests."""
    print("Chord Extraction Verification")
    print("=" * 60)
    
    try:
        test_c_major_progression()
        test_a_minor_progression()
        test_midi_conversion()
        test_key_detection()
        test_chord_types()
        
        print("\n" + "=" * 60)
        print("All verification tests completed successfully! ✓")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n✗ Error during verification: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())
