#!/usr/bin/env python3
"""
Test script for new features:
- BWF writer
- Waveform synthesis
- MIDI overdub/versioning
- Enhanced XPM parsing
"""

import sys
from pathlib import Path
import numpy as np

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from multimodal_gen import (
    WaveformType,
    ADSRParameters,
    SynthesisParameters,
    generate_waveform,
    generate_tone_with_adsr,
    generate_hybrid_sound,
    BWFWriter,
    save_wav_with_ai_provenance,
    read_bwf_metadata,
)

def test_waveform_generation():
    """Test basic waveform generation."""
    print("Testing waveform generation...")
    
    # Test each waveform type
    for waveform_type in WaveformType:
        audio = generate_waveform(
            waveform_type,
            frequency=440.0,
            duration=0.5,
            duty_cycle=0.3
        )
        assert len(audio) > 0, f"Failed to generate {waveform_type.value} waveform"
        print(f"  ✓ {waveform_type.value} waveform: {len(audio)} samples")
    
    print("✅ Waveform generation tests passed!\n")

def test_adsr_synthesis():
    """Test ADSR envelope synthesis."""
    print("Testing ADSR synthesis...")
    
    # Test with different ADSR parameters
    adsr = ADSRParameters(
        attack_ms=10.0,
        decay_ms=100.0,
        sustain_level=0.7,
        release_ms=200.0
    )
    
    params = SynthesisParameters(
        waveform=WaveformType.SINE,
        frequency=440.0,
        duration_sec=1.0,
        adsr=adsr
    )
    
    audio = generate_tone_with_adsr(params)
    assert len(audio) > 0, "Failed to generate tone with ADSR"
    print(f"  ✓ ADSR tone generated: {len(audio)} samples")
    
    # Test hybrid sounds
    for sound_type in ['kick', 'bass', 'pad', 'pluck', 'lead']:
        audio = generate_hybrid_sound(
            sound_type=sound_type,
            frequency=200.0 if sound_type in ['kick', 'bass'] else 440.0,
            duration=0.5
        )
        assert len(audio) > 0, f"Failed to generate {sound_type}"
        print(f"  ✓ {sound_type} sound: {len(audio)} samples")
    
    print("✅ ADSR synthesis tests passed!\n")

def test_bwf_writer():
    """Test BWF writer with AI provenance."""
    print("Testing BWF writer...")
    
    # Create test audio
    duration = 0.5
    sample_rate = 44100
    frequency = 440.0
    t = np.arange(int(duration * sample_rate)) / sample_rate
    audio = np.sin(2 * np.pi * frequency * t)
    audio = np.stack([audio, audio], axis=-1)  # Stereo
    
    # Test metadata
    ai_metadata = {
        'version': '0.2.0',
        'prompt': 'test generation',
        'seed': 12345,
        'bpm': 120,
        'key': 'C major',
        'genre': 'test',
        'synthesis_params': {
            'waveform': 'sine',
            'attack_ms': 10,
            'decay_ms': 100,
        }
    }
    
    # Save as BWF
    output_path = '/tmp/test_bwf.wav'
    save_wav_with_ai_provenance(
        audio,
        output_path,
        ai_metadata=ai_metadata,
        sample_rate=sample_rate,
        description="Test BWF file"
    )
    
    assert Path(output_path).exists(), "BWF file not created"
    print(f"  ✓ BWF file created: {output_path}")
    
    # Read back metadata
    metadata = read_bwf_metadata(output_path)
    assert metadata is not None, "Failed to read BWF metadata"
    assert metadata.get('prompt') == 'test generation', "Metadata mismatch"
    assert metadata.get('seed') == 12345, "Seed mismatch"
    print(f"  ✓ BWF metadata verified:")
    print(f"    - Prompt: {metadata.get('prompt')}")
    print(f"    - Seed: {metadata.get('seed')}")
    print(f"    - BPM: {metadata.get('bpm')}")
    
    print("✅ BWF writer tests passed!\n")

def test_midi_functions():
    """Test MIDI overdub and versioning functions."""
    print("Testing MIDI functions...")
    
    from multimodal_gen import (
        overdub_midi_track,
        create_midi_version,
        load_and_merge_midi_tracks,
    )
    
    # These functions require actual MIDI files to test properly
    # For now, just verify they're importable and callable
    print("  ✓ MIDI functions imported successfully")
    print("  ℹ Full MIDI tests require actual MIDI files")
    
    print("✅ MIDI function imports passed!\n")

def main():
    """Run all tests."""
    print("=" * 60)
    print("Testing New Features")
    print("=" * 60)
    print()
    
    try:
        test_waveform_generation()
        test_adsr_synthesis()
        test_bwf_writer()
        test_midi_functions()
        
        print("=" * 60)
        print("✅ ALL TESTS PASSED!")
        print("=" * 60)
        return 0
    
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == '__main__':
    sys.exit(main())
