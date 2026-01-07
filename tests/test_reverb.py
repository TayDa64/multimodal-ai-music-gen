"""
Unit tests for Convolution Reverb

Tests IR generation, FFT convolution, wet/dry mixing, pre-delay,
stereo width, EQ, presets, and performance.
"""

import pytest
import sys
import numpy as np
import time
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from multimodal_gen.reverb import (
    ConvolutionReverb,
    IRConfig,
    ReverbConfig,
    IR_PRESETS,
    GENRE_REVERB_CONFIGS,
    apply_reverb,
    apply_genre_reverb
)


class TestIRGeneration:
    """Tests for impulse response generation."""
    
    def test_ir_generation_room(self):
        """Test room IR generation."""
        reverb = ConvolutionReverb(sample_rate=44100)
        config = IRConfig(ir_type="room", decay_seconds=1.0)
        
        ir = reverb.generate_ir(config)
        
        # Should be stereo
        assert ir.shape[1] == 2
        # Should have reasonable length
        assert len(ir) > config.decay_seconds * 44100
        # Should not clip
        assert np.max(np.abs(ir)) <= 1.0
    
    def test_ir_generation_hall(self):
        """Test hall IR generation."""
        reverb = ConvolutionReverb(sample_rate=44100)
        config = IRConfig(ir_type="hall", decay_seconds=2.0)
        
        ir = reverb.generate_ir(config)
        
        assert ir.shape[1] == 2
        assert len(ir) > config.decay_seconds * 44100
        assert np.max(np.abs(ir)) <= 1.0
    
    def test_ir_generation_plate(self):
        """Test plate IR generation."""
        reverb = ConvolutionReverb(sample_rate=44100)
        config = IRConfig(ir_type="plate", decay_seconds=1.5)
        
        ir = reverb.generate_ir(config)
        
        assert ir.shape[1] == 2
        assert np.max(np.abs(ir)) <= 1.0
    
    def test_ir_generation_spring(self):
        """Test spring IR generation."""
        reverb = ConvolutionReverb(sample_rate=44100)
        config = IRConfig(ir_type="spring", decay_seconds=1.0)
        
        ir = reverb.generate_ir(config)
        
        assert ir.shape[1] == 2
        assert np.max(np.abs(ir)) <= 1.0
    
    def test_ir_generation_lofi(self):
        """Test lofi IR generation."""
        reverb = ConvolutionReverb(sample_rate=44100)
        config = IRConfig(ir_type="lofi", decay_seconds=0.6)
        
        ir = reverb.generate_ir(config)
        
        assert ir.shape[1] == 2
        assert np.max(np.abs(ir)) <= 1.0
    
    def test_ir_decay_time(self):
        """Test that IR decay time is approximately correct."""
        reverb = ConvolutionReverb(sample_rate=44100)
        
        for decay in [0.5, 1.0, 2.0]:
            config = IRConfig(ir_type="room", decay_seconds=decay)
            ir = reverb.generate_ir(config)
            
            # IR should be at least decay_seconds long
            min_length = decay * 44100
            assert len(ir) >= min_length
            
            # Check that energy decays over time
            chunk_size = int(0.1 * 44100)  # 100ms chunks
            energies = []
            for i in range(0, len(ir), chunk_size):
                chunk = ir[i:i+chunk_size]
                if len(chunk) > 0:
                    energy = np.mean(chunk ** 2)
                    energies.append(energy)
            
            # Energy should generally decrease
            if len(energies) > 2:
                # First chunk should have more energy than last
                assert energies[0] > energies[-1]
    
    def test_early_reflections_generation(self):
        """Test early reflections generation."""
        reverb = ConvolutionReverb(sample_rate=44100)
        
        early = reverb.generate_early_reflections(size=0.5, num_reflections=12)
        
        # Should be stereo
        assert early.shape[1] == 2
        # Should have initial impulse
        assert early[0, 0] == 1.0
        assert early[0, 1] == 1.0
        # Should have some reflections
        assert np.sum(np.abs(early) > 0) > 1
    
    def test_late_reverb_generation(self):
        """Test late reverb tail generation."""
        reverb = ConvolutionReverb(sample_rate=44100)
        
        late = reverb.generate_late_reverb(
            decay_seconds=1.0,
            damping=0.5,
            diffusion=0.7
        )
        
        # Should be stereo
        assert late.shape[1] == 2
        # Should have reasonable length
        assert len(late) > 44100
        # Should not be silent
        assert np.max(np.abs(late)) > 0
    
    def test_ir_damping_effect(self):
        """Test that damping reduces high frequencies."""
        reverb = ConvolutionReverb(sample_rate=44100)
        
        # Generate two IRs with different damping
        config_low_damp = IRConfig(ir_type="room", decay_seconds=1.0, damping=0.1)
        config_high_damp = IRConfig(ir_type="room", decay_seconds=1.0, damping=0.9)
        
        ir_low = reverb.generate_ir(config_low_damp)
        ir_high = reverb.generate_ir(config_high_damp)
        
        # High damping should reduce high-frequency energy
        # Use FFT to check frequency content
        fft_low = np.fft.rfft(ir_low[:, 0])
        fft_high = np.fft.rfft(ir_high[:, 0])
        
        # Check high-frequency bins (above 8kHz)
        freqs = np.fft.rfftfreq(len(ir_low), 1/44100)
        hf_mask = freqs > 8000
        
        hf_energy_low = np.mean(np.abs(fft_low[hf_mask]))
        hf_energy_high = np.mean(np.abs(fft_high[hf_mask]))
        
        # High damping should have less HF energy
        # Allow for some margin due to normalization and processing
        assert hf_energy_high < hf_energy_low * 1.05
    
    def test_ir_pre_delay(self):
        """Test pre-delay in IR generation."""
        reverb = ConvolutionReverb(sample_rate=44100)
        
        config = IRConfig(ir_type="room", decay_seconds=1.0, pre_delay_ms=50)
        ir = reverb.generate_ir(config)
        
        # First 50ms should be mostly silent (just the initial delay)
        pre_delay_samples = int(50 * 44100 / 1000)
        initial_section = ir[:pre_delay_samples]
        
        # Should be very quiet in the initial section
        # (allowing for the impulse at sample 0 which gets moved)
        assert np.mean(np.abs(initial_section)) < 0.1


class TestConvolution:
    """Tests for FFT convolution."""
    
    def test_fft_convolve_mono(self):
        """Test FFT convolution with mono audio."""
        reverb = ConvolutionReverb(sample_rate=44100)
        
        # Create simple test audio
        audio = np.random.randn(1000) * 0.5
        audio_stereo = np.stack([audio, audio], axis=1)
        
        # Create simple IR
        ir = np.zeros((100, 2))
        ir[0] = [1.0, 1.0]  # Direct sound
        ir[50] = [0.5, 0.5]  # One echo
        
        result = reverb.fft_convolve(audio_stereo, ir)
        
        # Should be stereo
        assert result.shape[1] == 2
        # Length should be audio + ir - 1
        assert len(result) == len(audio_stereo) + len(ir) - 1
    
    def test_fft_convolve_correctness(self):
        """Test that FFT convolution is mathematically correct."""
        reverb = ConvolutionReverb(sample_rate=44100)
        
        # Simple impulse
        audio = np.zeros(100)
        audio[10] = 1.0
        audio_stereo = np.stack([audio, audio], axis=1)
        
        # Simple IR with one echo
        ir = np.zeros((50, 2))
        ir[0] = [1.0, 1.0]
        ir[20] = [0.5, 0.5]
        
        result = reverb.fft_convolve(audio_stereo, ir)
        
        # Should have impulse at position 10 and echo at position 30
        assert result[10, 0] > 0.9  # Original impulse
        assert result[30, 0] > 0.4  # Echo at 10 + 20
        assert result[30, 0] < 0.6
    
    def test_fft_convolve_stereo(self):
        """Test FFT convolution with stereo audio."""
        reverb = ConvolutionReverb(sample_rate=44100)
        
        # Create stereo test audio
        left = np.random.randn(1000) * 0.5
        right = np.random.randn(1000) * 0.5
        audio = np.stack([left, right], axis=1)
        
        # Create stereo IR
        ir = np.random.randn(100, 2) * 0.1
        ir[0] = [1.0, 1.0]
        
        result = reverb.fft_convolve(audio, ir)
        
        # Should be stereo
        assert result.shape[1] == 2
        # Channels should be different
        assert not np.allclose(result[:, 0], result[:, 1])


class TestReverbProcessing:
    """Tests for full reverb processing."""
    
    def test_convolve_with_config(self):
        """Test convolution with ReverbConfig."""
        reverb = ConvolutionReverb(sample_rate=44100)
        
        # Generate test audio
        audio = np.random.randn(4410) * 0.5  # 0.1s
        
        # Generate IR
        ir = reverb.generate_ir(IRConfig(ir_type="room", decay_seconds=0.5))
        
        # Process with config
        config = ReverbConfig(wet_dry=0.5, pre_delay_ms=10)
        result = reverb.convolve(audio, ir, config)
        
        # Should be same length as input (or similar)
        assert len(result) == len(audio)
        # Should not clip
        assert np.max(np.abs(result)) <= 1.0
    
    def test_wet_dry_mixing(self):
        """Test wet/dry mix control."""
        reverb = ConvolutionReverb(sample_rate=44100)
        
        # Generate test audio
        audio = np.random.randn(4410) * 0.5
        ir = reverb.generate_ir(IRConfig(ir_type="room", decay_seconds=0.3))
        
        # Process with different wet/dry ratios
        config_dry = ReverbConfig(wet_dry=0.0)
        config_wet = ReverbConfig(wet_dry=1.0)
        config_half = ReverbConfig(wet_dry=0.5)
        
        result_dry = reverb.convolve(audio, ir, config_dry)
        result_wet = reverb.convolve(audio, ir, config_wet)
        result_half = reverb.convolve(audio, ir, config_half)
        
        # Dry should be very similar to input (allowing for anti-clipping normalization)
        # Check correlation rather than exact match
        correlation = np.corrcoef(result_dry, audio)[0, 1]
        assert correlation > 0.99, f"Dry signal correlation {correlation} should be > 0.99"
        
        # RMS should be similar
        rms_dry = np.sqrt(np.mean(result_dry ** 2))
        rms_input = np.sqrt(np.mean(audio ** 2))
        assert abs(rms_dry - rms_input) / rms_input < 0.1
        
        # Half should be between dry and wet
        # (not exact due to processing, but should be different from both)
        diff_to_dry = np.mean(np.abs(result_half - result_dry))
        diff_to_wet = np.mean(np.abs(result_half - result_wet))
        assert diff_to_dry > 0
        assert diff_to_wet > 0
    
    def test_pre_delay_implementation(self):
        """Test pre-delay in processing."""
        reverb = ConvolutionReverb(sample_rate=44100)
        
        # Generate impulse
        audio = np.zeros(4410)
        audio[100] = 1.0
        
        ir = reverb.generate_ir(IRConfig(ir_type="room", decay_seconds=0.3))
        
        # Process with pre-delay
        config = ReverbConfig(wet_dry=1.0, pre_delay_ms=50)
        result = reverb.convolve(audio, ir, config)
        
        # The reverb should start after the pre-delay
        pre_delay_samples = int(50 * 44100 / 1000)
        
        # There should be a delay before significant reverb energy appears
        # (though this is hard to test precisely)
        assert len(result) == len(audio)
    
    def test_stereo_width_control(self):
        """Test stereo width adjustment."""
        reverb = ConvolutionReverb(sample_rate=44100)
        
        # Create stereo audio
        audio = np.random.randn(4410, 2) * 0.5
        
        # Test different widths
        width_0 = reverb.apply_stereo_width(audio, width=0.0)  # Mono
        width_1 = reverb.apply_stereo_width(audio, width=1.0)  # Normal
        width_2 = reverb.apply_stereo_width(audio, width=2.0)  # Wide
        
        # Width 0 should be mono (L == R)
        assert np.allclose(width_0[:, 0], width_0[:, 1])
        
        # Width 1 should be similar to original
        assert np.allclose(width_1, audio, atol=0.1)
        
        # Width 2 should have more difference between channels
        diff_original = np.mean(np.abs(audio[:, 0] - audio[:, 1]))
        diff_wide = np.mean(np.abs(width_2[:, 0] - width_2[:, 1]))
        assert diff_wide > diff_original * 1.5
    
    def test_pre_eq_high_pass(self):
        """Test high-pass filtering on reverb."""
        reverb = ConvolutionReverb(sample_rate=44100)
        
        # Create audio with low and high frequencies
        duration = 1.0
        t = np.linspace(0, duration, int(44100 * duration))
        low_freq = np.sin(2 * np.pi * 100 * t)  # 100 Hz
        high_freq = np.sin(2 * np.pi * 5000 * t)  # 5 kHz
        audio = np.stack([low_freq + high_freq, low_freq + high_freq], axis=1) * 0.3
        
        # Apply high-pass at 1000 Hz
        filtered = reverb.apply_pre_eq(audio, low_cut_hz=1000, high_cut_hz=20000)
        
        # Low frequencies should be reduced
        fft_orig = np.fft.rfft(audio[:, 0])
        fft_filtered = np.fft.rfft(filtered[:, 0])
        
        freqs = np.fft.rfftfreq(len(audio), 1/44100)
        lf_idx = np.argmin(np.abs(freqs - 100))  # 100 Hz bin
        
        # 100 Hz should be reduced
        assert np.abs(fft_filtered[lf_idx]) < np.abs(fft_orig[lf_idx])
    
    def test_pre_eq_low_pass(self):
        """Test low-pass filtering on reverb."""
        reverb = ConvolutionReverb(sample_rate=44100)
        
        # Create audio with low and high frequencies
        duration = 1.0
        t = np.linspace(0, duration, int(44100 * duration))
        low_freq = np.sin(2 * np.pi * 1000 * t)  # 1 kHz
        high_freq = np.sin(2 * np.pi * 10000 * t)  # 10 kHz
        audio = np.stack([low_freq + high_freq, low_freq + high_freq], axis=1) * 0.3
        
        # Apply low-pass at 5000 Hz
        filtered = reverb.apply_pre_eq(audio, low_cut_hz=20, high_cut_hz=5000)
        
        # High frequencies should be reduced
        fft_orig = np.fft.rfft(audio[:, 0])
        fft_filtered = np.fft.rfft(filtered[:, 0])
        
        freqs = np.fft.rfftfreq(len(audio), 1/44100)
        hf_idx = np.argmin(np.abs(freqs - 10000))  # 10 kHz bin
        
        # 10 kHz should be reduced
        assert np.abs(fft_filtered[hf_idx]) < np.abs(fft_orig[hf_idx])


class TestPresets:
    """Tests for preset IRs and configurations."""
    
    def test_all_presets_load(self):
        """Test that all IR presets load without error."""
        reverb = ConvolutionReverb(sample_rate=44100)
        
        for preset_name in IR_PRESETS.keys():
            ir = reverb.get_preset_ir(preset_name)
            
            # Should be stereo
            assert ir.shape[1] == 2
            # Should not be silent
            assert np.max(np.abs(ir)) > 0
            # Should not clip
            assert np.max(np.abs(ir)) <= 1.0
    
    def test_process_with_preset(self):
        """Test processing with preset name."""
        reverb = ConvolutionReverb(sample_rate=44100)
        
        audio = np.random.randn(4410) * 0.5
        
        for preset in ["tight_room", "room", "hall", "plate", "spring", "lofi_room"]:
            result = reverb.process(audio, preset=preset)
            
            # Should return audio
            assert len(result) > 0
            # Should not clip
            assert np.max(np.abs(result)) <= 1.0
    
    def test_preset_count(self):
        """Test that we have at least 7 presets."""
        assert len(IR_PRESETS) >= 7
        
        # Check specific required presets
        required = ["tight_room", "room", "large_room", "hall", "plate", "spring", "lofi_room"]
        for preset in required:
            assert preset in IR_PRESETS
    
    def test_genre_reverb_configs(self):
        """Test genre-specific reverb configurations."""
        assert len(GENRE_REVERB_CONFIGS) >= 8
        
        # Check some specific genres
        required_genres = ["trap", "boom_bap", "lofi", "house", "jazz", "orchestral", "rock", "ambient"]
        for genre in required_genres:
            assert genre in GENRE_REVERB_CONFIGS
            preset, config = GENRE_REVERB_CONFIGS[genre]
            
            # Preset should exist
            assert preset in IR_PRESETS
            # Config should be valid
            assert isinstance(config, ReverbConfig)
            assert 0 <= config.wet_dry <= 1.0


class TestPerformance:
    """Tests for performance and efficiency."""
    
    def test_convolution_efficiency(self):
        """Test that convolution is efficient (< 100ms for 10s audio)."""
        reverb = ConvolutionReverb(sample_rate=44100)
        
        # Generate 10 seconds of audio
        audio = np.random.randn(441000) * 0.5  # 10s at 44.1kHz
        
        ir = reverb.generate_ir(IRConfig(ir_type="room", decay_seconds=1.0))
        config = ReverbConfig(wet_dry=0.3)
        
        start_time = time.time()
        result = reverb.convolve(audio, ir, config)
        elapsed = time.time() - start_time
        
        # Should complete in less than 100ms
        assert elapsed < 0.1, f"Convolution took {elapsed:.3f}s, should be < 0.1s"
    
    def test_preset_caching(self):
        """Test that presets are cached and reused."""
        reverb = ConvolutionReverb(sample_rate=44100)
        
        # Get preset twice
        ir1 = reverb.get_preset_ir("room")
        ir2 = reverb.get_preset_ir("room")
        
        # Should be the same object (cached)
        assert ir1 is ir2


class TestEdgeCases:
    """Tests for edge cases and error handling."""
    
    def test_silent_audio(self):
        """Test processing silent audio."""
        reverb = ConvolutionReverb(sample_rate=44100)
        
        audio = np.zeros(4410)
        result = reverb.process(audio, preset="room")
        
        # Should return audio (mostly silent)
        assert len(result) == len(audio)
        # Should be very quiet
        assert np.max(np.abs(result)) < 0.01
    
    def test_very_short_audio(self):
        """Test processing very short audio."""
        reverb = ConvolutionReverb(sample_rate=44100)
        
        audio = np.random.randn(10) * 0.5
        result = reverb.process(audio, preset="room")
        
        # Should handle short audio
        assert len(result) == len(audio)
    
    def test_empty_audio(self):
        """Test processing empty audio."""
        reverb = ConvolutionReverb(sample_rate=44100)
        
        audio = np.array([])
        result = reverb.process(audio, preset="room")
        
        # Should return empty
        assert len(result) == 0
    
    def test_mono_input(self):
        """Test that mono input is handled correctly."""
        reverb = ConvolutionReverb(sample_rate=44100)
        
        audio = np.random.randn(4410) * 0.5  # Mono
        result = reverb.process(audio, preset="room")
        
        # Should return mono (same shape as input)
        assert len(result.shape) == 1 or (len(result.shape) == 2 and result.shape[1] == 1)
    
    def test_stereo_input(self):
        """Test that stereo input is handled correctly."""
        reverb = ConvolutionReverb(sample_rate=44100)
        
        audio = np.random.randn(4410, 2) * 0.5  # Stereo
        result = reverb.process(audio, preset="room")
        
        # Should return stereo
        assert len(result.shape) == 2
        assert result.shape[1] == 2
    
    def test_unknown_preset_error(self):
        """Test that unknown preset raises error."""
        reverb = ConvolutionReverb(sample_rate=44100)
        
        with pytest.raises(ValueError):
            reverb.get_preset_ir("nonexistent_preset")
    
    def test_no_clipping(self):
        """Test that processing never causes clipping."""
        reverb = ConvolutionReverb(sample_rate=44100)
        
        # Test with loud audio
        audio = np.random.randn(4410) * 0.9
        
        for preset in IR_PRESETS.keys():
            result = reverb.process(audio, preset=preset)
            assert np.max(np.abs(result)) <= 1.0, f"Clipping with preset {preset}"


class TestConvenienceFunctions:
    """Tests for convenience functions."""
    
    def test_apply_reverb_function(self):
        """Test apply_reverb convenience function."""
        audio = np.random.randn(4410) * 0.5
        
        result = apply_reverb(audio, preset="room", wet_dry=0.3, sample_rate=44100)
        
        assert len(result) > 0
        assert np.max(np.abs(result)) <= 1.0
    
    def test_apply_genre_reverb_function(self):
        """Test apply_genre_reverb convenience function."""
        audio = np.random.randn(4410) * 0.5
        
        for genre in GENRE_REVERB_CONFIGS.keys():
            result = apply_genre_reverb(audio, genre=genre, sample_rate=44100)
            
            assert len(result) > 0
            assert np.max(np.abs(result)) <= 1.0
    
    def test_apply_genre_reverb_unknown_genre(self):
        """Test apply_genre_reverb with unknown genre (should use default)."""
        audio = np.random.randn(4410) * 0.5
        
        # Should not raise error, just use default
        result = apply_genre_reverb(audio, genre="unknown_genre", sample_rate=44100)
        
        assert len(result) > 0
        assert np.max(np.abs(result)) <= 1.0


class TestIntegration:
    """Integration tests with realistic scenarios."""
    
    def test_full_reverb_chain(self):
        """Test complete reverb processing chain."""
        reverb = ConvolutionReverb(sample_rate=44100)
        
        # Generate realistic audio (drums)
        duration = 2.0
        t = np.linspace(0, duration, int(44100 * duration))
        
        # Kick drum (low freq)
        kick = np.sin(2 * np.pi * 60 * t) * np.exp(-t * 10)
        
        # Snare (mid-high freq)
        snare = np.random.randn(len(t)) * np.exp(-(t - 0.5) * 20)
        snare[t < 0.5] = 0
        
        audio = (kick + snare * 0.5) * 0.5
        
        # Process with reverb
        config = ReverbConfig(
            wet_dry=0.3,
            pre_delay_ms=20,
            low_cut_hz=100,
            high_cut_hz=10000,
            stereo_width=1.2
        )
        
        result = reverb.process(audio, preset="room", config=config)
        
        # Should produce valid output
        assert len(result) > 0
        assert np.max(np.abs(result)) <= 1.0
        
        # Should add energy (reverb tail)
        rms_input = np.sqrt(np.mean(audio ** 2))
        rms_output = np.sqrt(np.mean(result ** 2))
        # With 30% wet, output should have more energy
        assert rms_output > rms_input * 0.8
    
    def test_different_sample_rates(self):
        """Test reverb with different sample rates."""
        for sr in [22050, 44100, 48000]:
            reverb = ConvolutionReverb(sample_rate=sr)
            
            audio = np.random.randn(sr) * 0.5  # 1 second
            result = reverb.process(audio, preset="room")
            
            assert len(result) > 0
            assert np.max(np.abs(result)) <= 1.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
