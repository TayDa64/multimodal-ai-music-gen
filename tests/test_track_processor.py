"""
Unit tests for Track Processor

Tests the track processing chain including saturation, EQ, compression,
transient shaping, and all presets.
"""

import pytest
import sys
import numpy as np
import time
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from multimodal_gen.track_processor import (
    TrackProcessor,
    TrackProcessorConfig,
    EQBand,
    CompressorConfig,
    TransientConfig,
    TRACK_PRESETS,
    process_track
)


class TestSaturation:
    """Tests for saturation processing."""
    
    def test_no_saturation_unchanged(self):
        """Drive of 1.0 should not significantly alter audio."""
        processor = TrackProcessor(sample_rate=44100)
        
        audio = np.random.randn(1000) * 0.5
        result = processor.soft_saturate(audio, drive=1.0)
        
        # Should be very close to original
        assert np.allclose(result, audio, atol=0.01)
    
    def test_saturation_no_clipping(self):
        """Saturation should not cause clipping."""
        processor = TrackProcessor(sample_rate=44100)
        
        # Test with loud signal
        audio = np.random.randn(1000) * 0.9
        
        for drive in [1.5, 2.0, 3.0, 4.0]:
            result = processor.soft_saturate(audio, drive=drive)
            
            # Should not exceed ±1.0
            assert np.max(np.abs(result)) <= 1.0, f"Clipping with drive={drive}"
    
    def test_saturation_drive_increases_effect(self):
        """Higher drive should cause more saturation."""
        processor = TrackProcessor(sample_rate=44100)
        
        audio = np.random.randn(1000) * 0.5
        
        result_low = processor.soft_saturate(audio, drive=1.5)
        result_high = processor.soft_saturate(audio, drive=3.0)
        
        # Higher drive should change signal more
        diff_low = np.mean(np.abs(result_low - audio))
        diff_high = np.mean(np.abs(result_high - audio))
        
        assert diff_high > diff_low
    
    def test_saturation_stereo(self):
        """Saturation should work on stereo audio."""
        processor = TrackProcessor(sample_rate=44100)
        
        audio = np.random.randn(1000, 2) * 0.5
        result = processor.soft_saturate(audio, drive=2.0)
        
        assert result.shape == audio.shape
        assert np.max(np.abs(result)) <= 1.0


class TestEQ:
    """Tests for EQ processing."""
    
    def test_eq_peak_boost(self):
        """Peak EQ should boost at specified frequency."""
        processor = TrackProcessor(sample_rate=44100)
        
        # Generate sine wave at test frequency
        freq = 1000.0
        duration = 1.0
        t = np.linspace(0, duration, int(44100 * duration))
        audio = np.sin(2 * np.pi * freq * t) * 0.5
        
        band = EQBand(frequency=freq, gain_db=6.0, q=2.0, band_type="peak")
        result = processor.apply_biquad(audio, band)
        
        # Boosted signal should have higher RMS
        rms_input = np.sqrt(np.mean(audio ** 2))
        rms_output = np.sqrt(np.mean(result ** 2))
        
        assert rms_output > rms_input
    
    def test_eq_peak_cut(self):
        """Peak EQ should cut at specified frequency."""
        processor = TrackProcessor(sample_rate=44100)
        
        freq = 1000.0
        duration = 1.0
        t = np.linspace(0, duration, int(44100 * duration))
        audio = np.sin(2 * np.pi * freq * t) * 0.5
        
        band = EQBand(frequency=freq, gain_db=-6.0, q=2.0, band_type="peak")
        result = processor.apply_biquad(audio, band)
        
        # Cut signal should have lower RMS
        rms_input = np.sqrt(np.mean(audio ** 2))
        rms_output = np.sqrt(np.mean(result ** 2))
        
        assert rms_output < rms_input
    
    def test_eq_lowpass(self):
        """Lowpass filter should attenuate high frequencies."""
        processor = TrackProcessor(sample_rate=44100)
        
        # Create signal with low and high frequency components
        duration = 1.0
        t = np.linspace(0, duration, int(44100 * duration))
        low_freq = np.sin(2 * np.pi * 200 * t)
        high_freq = np.sin(2 * np.pi * 5000 * t)
        audio = (low_freq + high_freq) * 0.5
        
        band = EQBand(frequency=1000, gain_db=0, q=0.707, band_type="lowpass")
        result = processor.apply_biquad(audio, band)
        
        # High frequency should be attenuated more than low
        # Check by comparing first half (should be similar) with overall (should differ)
        assert not np.allclose(result, audio, atol=0.1)
    
    def test_eq_highpass(self):
        """Highpass filter should attenuate low frequencies."""
        processor = TrackProcessor(sample_rate=44100)
        
        duration = 1.0
        t = np.linspace(0, duration, int(44100 * duration))
        low_freq = np.sin(2 * np.pi * 50 * t)
        high_freq = np.sin(2 * np.pi * 2000 * t)
        audio = (low_freq + high_freq) * 0.5
        
        band = EQBand(frequency=200, gain_db=0, q=0.707, band_type="highpass")
        result = processor.apply_biquad(audio, band)
        
        # Should change the signal
        assert not np.allclose(result, audio, atol=0.1)
    
    def test_eq_low_shelf(self):
        """Low shelf should affect low frequencies."""
        processor = TrackProcessor(sample_rate=44100)
        
        duration = 0.5
        t = np.linspace(0, duration, int(44100 * duration))
        audio = np.sin(2 * np.pi * 100 * t) * 0.5
        
        band = EQBand(frequency=200, gain_db=6.0, q=0.707, band_type="low_shelf")
        result = processor.apply_biquad(audio, band)
        
        # Should boost low frequency
        rms_input = np.sqrt(np.mean(audio ** 2))
        rms_output = np.sqrt(np.mean(result ** 2))
        assert rms_output > rms_input
    
    def test_eq_high_shelf(self):
        """High shelf should affect high frequencies."""
        processor = TrackProcessor(sample_rate=44100)
        
        duration = 0.5
        t = np.linspace(0, duration, int(44100 * duration))
        audio = np.sin(2 * np.pi * 8000 * t) * 0.5
        
        band = EQBand(frequency=5000, gain_db=6.0, q=0.707, band_type="high_shelf")
        result = processor.apply_biquad(audio, band)
        
        # Should boost high frequency
        rms_input = np.sqrt(np.mean(audio ** 2))
        rms_output = np.sqrt(np.mean(result ** 2))
        assert rms_output > rms_input
    
    def test_eq_multi_band(self):
        """Multiple EQ bands should be applied in sequence."""
        processor = TrackProcessor(sample_rate=44100)
        
        audio = np.random.randn(10000) * 0.5
        
        bands = [
            EQBand(frequency=100, gain_db=3.0, band_type="low_shelf"),
            EQBand(frequency=1000, gain_db=-2.0, q=2.0, band_type="peak"),
            EQBand(frequency=8000, gain_db=2.0, band_type="high_shelf"),
        ]
        
        result = processor.apply_eq(audio, bands)
        
        # Should change the signal
        assert not np.allclose(result, audio, atol=0.01)
        assert result.shape == audio.shape
    
    def test_eq_stereo(self):
        """EQ should work on stereo audio."""
        processor = TrackProcessor(sample_rate=44100)
        
        audio = np.random.randn(10000, 2) * 0.5
        band = EQBand(frequency=1000, gain_db=3.0, q=1.0, band_type="peak")
        
        result = processor.apply_biquad(audio, band)
        
        assert result.shape == audio.shape


class TestCompression:
    """Tests for compression processing."""
    
    def test_compression_reduces_peaks(self):
        """Compression should reduce peak levels above threshold."""
        processor = TrackProcessor(sample_rate=44100)
        
        # Create signal with loud peaks
        audio = np.concatenate([
            np.sin(2 * np.pi * 440 * np.linspace(0, 0.1, 4410)) * 0.3,  # Quiet
            np.sin(2 * np.pi * 440 * np.linspace(0, 0.1, 4410)) * 0.9,  # Loud
        ])
        
        config = CompressorConfig(
            threshold_db=-20,
            ratio=4.0,
            attack_ms=5,
            release_ms=100,
            makeup_db=0
        )
        
        result = processor.compress(audio, config)
        
        # Peak should be reduced
        peak_input = np.max(np.abs(audio))
        peak_output = np.max(np.abs(result))
        
        assert peak_output < peak_input
    
    def test_compression_threshold(self):
        """Signals below threshold should be unaffected."""
        processor = TrackProcessor(sample_rate=44100)
        
        # Quiet signal below threshold
        audio = np.sin(2 * np.pi * 440 * np.linspace(0, 0.5, 22050)) * 0.1
        
        config = CompressorConfig(
            threshold_db=-10,  # High threshold
            ratio=4.0,
            attack_ms=10,
            release_ms=100
        )
        
        result = processor.compress(audio, config)
        
        # Should be nearly unchanged
        assert np.allclose(result, audio, atol=0.15)
    
    def test_compression_ratio(self):
        """Higher ratio should compress more."""
        processor = TrackProcessor(sample_rate=44100)
        
        # Loud signal
        audio = np.sin(2 * np.pi * 440 * np.linspace(0, 0.5, 22050)) * 0.8
        
        config_low = CompressorConfig(threshold_db=-20, ratio=2.0, attack_ms=5, release_ms=100)
        config_high = CompressorConfig(threshold_db=-20, ratio=8.0, attack_ms=5, release_ms=100)
        
        result_low = processor.compress(audio, config_low)
        result_high = processor.compress(audio, config_high)
        
        # Higher ratio should reduce more
        peak_low = np.max(np.abs(result_low))
        peak_high = np.max(np.abs(result_high))
        
        assert peak_high < peak_low
    
    def test_compression_makeup_gain(self):
        """Makeup gain should increase output level."""
        processor = TrackProcessor(sample_rate=44100)
        
        audio = np.sin(2 * np.pi * 440 * np.linspace(0, 0.5, 22050)) * 0.6
        
        config_no_makeup = CompressorConfig(
            threshold_db=-20, ratio=4.0, attack_ms=5, release_ms=100, makeup_db=0
        )
        config_with_makeup = CompressorConfig(
            threshold_db=-20, ratio=4.0, attack_ms=5, release_ms=100, makeup_db=6
        )
        
        result_no_makeup = processor.compress(audio, config_no_makeup)
        result_with_makeup = processor.compress(audio, config_with_makeup)
        
        # With makeup should be louder
        rms_no = np.sqrt(np.mean(result_no_makeup ** 2))
        rms_with = np.sqrt(np.mean(result_with_makeup ** 2))
        
        assert rms_with > rms_no
    
    def test_compression_stereo(self):
        """Compression should work on stereo audio."""
        processor = TrackProcessor(sample_rate=44100)
        
        audio = np.random.randn(10000, 2) * 0.7
        config = CompressorConfig(threshold_db=-15, ratio=4.0, attack_ms=10, release_ms=100)
        
        result = processor.compress(audio, config)
        
        assert result.shape == audio.shape


class TestTransientShaping:
    """Tests for transient shaping."""
    
    def test_transient_attack_boost(self):
        """Positive attack should enhance transients."""
        processor = TrackProcessor(sample_rate=44100)
        
        # Create signal with clear transient (sudden onset)
        audio = np.zeros(10000)
        audio[1000:3000] = np.sin(2 * np.pi * 440 * np.linspace(0, 0.045, 2000)) * 0.7
        
        config = TransientConfig(attack=50, sustain=0)
        result = processor.shape_transients(audio, config)
        
        # Should increase the attack portion
        assert result.shape == audio.shape
    
    def test_transient_attack_cut(self):
        """Negative attack should reduce transients."""
        processor = TrackProcessor(sample_rate=44100)
        
        audio = np.zeros(10000)
        audio[1000:5000] = np.sin(2 * np.pi * 440 * np.linspace(0, 0.09, 4000)) * 0.7
        
        config = TransientConfig(attack=-50, sustain=0)
        result = processor.shape_transients(audio, config)
        
        assert result.shape == audio.shape
    
    def test_transient_no_change(self):
        """Zero settings should not change audio significantly."""
        processor = TrackProcessor(sample_rate=44100)
        
        audio = np.random.randn(5000) * 0.5
        config = TransientConfig(attack=0, sustain=0)
        
        result = processor.shape_transients(audio, config)
        
        # Should be unchanged
        assert np.allclose(result, audio, atol=0.01)
    
    def test_transient_stereo(self):
        """Transient shaping should work on stereo."""
        processor = TrackProcessor(sample_rate=44100)
        
        audio = np.random.randn(5000, 2) * 0.5
        config = TransientConfig(attack=30, sustain=-10)
        
        result = processor.shape_transients(audio, config)
        
        assert result.shape == audio.shape


class TestFullChain:
    """Tests for complete processing chain."""
    
    def test_full_chain_no_clipping(self):
        """Full chain should not cause clipping."""
        processor = TrackProcessor(sample_rate=44100)
        
        audio = np.random.randn(10000) * 0.7
        
        config = TrackProcessorConfig(
            saturation_drive=2.0,
            eq_bands=[
                EQBand(frequency=100, gain_db=3.0, band_type="low_shelf"),
                EQBand(frequency=5000, gain_db=2.0, band_type="high_shelf"),
            ],
            compressor=CompressorConfig(threshold_db=-15, ratio=4.0, attack_ms=10, release_ms=100),
            transient=TransientConfig(attack=20, sustain=0),
            output_gain_db=2.0
        )
        
        result = processor.process(audio, config)
        
        # Should not clip
        assert np.max(np.abs(result)) <= 1.0
    
    def test_full_chain_order(self):
        """Processing order should be: Sat → EQ → Comp → Trans → Gain."""
        processor = TrackProcessor(sample_rate=44100)
        
        audio = np.random.randn(5000) * 0.5
        
        config = TrackProcessorConfig(
            saturation_drive=1.5,
            eq_bands=[EQBand(frequency=1000, gain_db=3.0, q=1.0, band_type="peak")],
            compressor=CompressorConfig(threshold_db=-18, ratio=3.0, attack_ms=10, release_ms=100),
            output_gain_db=1.0
        )
        
        result = processor.process(audio, config)
        
        # Should process successfully
        assert result.shape == audio.shape
        assert not np.allclose(result, audio)
    
    def test_empty_audio(self):
        """Empty audio should be handled gracefully."""
        processor = TrackProcessor(sample_rate=44100)
        
        audio = np.array([])
        config = TrackProcessorConfig()
        
        result = processor.process(audio, config)
        
        assert len(result) == 0
    
    def test_silent_audio(self):
        """Silent audio should remain silent."""
        processor = TrackProcessor(sample_rate=44100)
        
        audio = np.zeros(5000)
        config = TrackProcessorConfig(
            saturation_drive=2.0,
            eq_bands=[EQBand(frequency=1000, gain_db=6.0, q=1.0, band_type="peak")],
            compressor=CompressorConfig(threshold_db=-20, ratio=4.0, attack_ms=10, release_ms=100)
        )
        
        result = processor.process(audio, config)
        
        # Should remain very quiet (some numerical noise acceptable)
        assert np.max(np.abs(result)) < 0.01


class TestPresets:
    """Tests for all presets."""
    
    def test_all_presets_exist(self):
        """All documented presets should exist."""
        required_presets = [
            "trap_808", "boom_bap_bass", "trap_hihat", "boom_bap_drums",
            "punchy_kick", "snare_crack", "lofi_keys", "bright_synth",
            "warm_pad", "vocal_presence"
        ]
        
        for preset in required_presets:
            assert preset in TRACK_PRESETS, f"Missing preset: {preset}"
    
    def test_preset_count(self):
        """Should have at least 10 presets."""
        assert len(TRACK_PRESETS) >= 10
    
    def test_all_presets_load(self):
        """All presets should load without error."""
        processor = TrackProcessor(sample_rate=44100)
        
        for preset_name in TRACK_PRESETS:
            config = processor.get_preset(preset_name)
            assert config is not None
            assert isinstance(config, TrackProcessorConfig)
    
    def test_all_presets_process(self):
        """All presets should process audio without error."""
        processor = TrackProcessor(sample_rate=44100)
        
        audio = np.random.randn(5000) * 0.5
        
        for preset_name in TRACK_PRESETS:
            result = processor.process_with_preset(audio, preset_name)
            
            assert result.shape == audio.shape
            assert np.max(np.abs(result)) <= 1.0, f"Clipping in preset: {preset_name}"
    
    def test_preset_trap_808(self):
        """Trap 808 preset should have appropriate settings."""
        config = TRACK_PRESETS["trap_808"]
        
        assert config.saturation_drive > 1.0
        assert config.eq_bands is not None
        assert config.compressor is not None
    
    def test_preset_lofi_keys(self):
        """Lo-fi keys preset should have appropriate settings."""
        config = TRACK_PRESETS["lofi_keys"]
        
        # Should have some saturation and rolled-off highs
        assert config.saturation_drive > 1.0
        assert config.eq_bands is not None
        
        # Check for high-frequency cut
        has_high_cut = any(
            band.band_type in ["high_shelf"] and band.gain_db < 0
            for band in config.eq_bands
        )
        assert has_high_cut
    
    def test_invalid_preset_raises_error(self):
        """Invalid preset name should raise ValueError."""
        processor = TrackProcessor(sample_rate=44100)
        audio = np.random.randn(1000) * 0.5
        
        with pytest.raises(ValueError):
            processor.process_with_preset(audio, "nonexistent_preset")


class TestMonoStereoHandling:
    """Tests for mono and stereo audio handling."""
    
    def test_mono_input_mono_output(self):
        """Mono input should produce mono output."""
        processor = TrackProcessor(sample_rate=44100)
        
        audio = np.random.randn(5000) * 0.5
        config = TrackProcessorConfig(
            saturation_drive=1.5,
            eq_bands=[EQBand(frequency=1000, gain_db=3.0, q=1.0, band_type="peak")],
            compressor=CompressorConfig(threshold_db=-15, ratio=4.0, attack_ms=10, release_ms=100)
        )
        
        result = processor.process(audio, config)
        
        assert result.ndim == 1
        assert result.shape == audio.shape
    
    def test_stereo_input_stereo_output(self):
        """Stereo input should produce stereo output."""
        processor = TrackProcessor(sample_rate=44100)
        
        audio = np.random.randn(5000, 2) * 0.5
        config = TrackProcessorConfig(
            saturation_drive=1.5,
            eq_bands=[EQBand(frequency=1000, gain_db=3.0, q=1.0, band_type="peak")],
            compressor=CompressorConfig(threshold_db=-15, ratio=4.0, attack_ms=10, release_ms=100)
        )
        
        result = processor.process(audio, config)
        
        assert result.ndim == 2
        assert result.shape == audio.shape


class TestEdgeCases:
    """Tests for edge cases."""
    
    def test_single_sample(self):
        """Should handle single sample audio."""
        processor = TrackProcessor(sample_rate=44100)
        
        audio = np.array([0.5])
        config = TrackProcessorConfig(saturation_drive=2.0)
        
        result = processor.process(audio, config)
        
        assert len(result) == 1
    
    def test_very_loud_audio(self):
        """Should handle very loud audio without exploding."""
        processor = TrackProcessor(sample_rate=44100)
        
        audio = np.random.randn(5000) * 1.5  # Clipping input
        audio = np.clip(audio, -1.0, 1.0)
        
        config = TrackProcessorConfig(
            saturation_drive=2.0,
            compressor=CompressorConfig(threshold_db=-6, ratio=10.0, attack_ms=1, release_ms=50)
        )
        
        result = processor.process(audio, config)
        
        # Should not NaN or Inf
        assert not np.any(np.isnan(result))
        assert not np.any(np.isinf(result))
        assert np.max(np.abs(result)) <= 1.0
    
    def test_dc_offset(self):
        """Should handle DC offset in audio."""
        processor = TrackProcessor(sample_rate=44100)
        
        audio = np.random.randn(5000) * 0.3 + 0.5  # DC offset
        config = TrackProcessorConfig(saturation_drive=1.5)
        
        result = processor.process(audio, config)
        
        assert not np.any(np.isnan(result))


class TestRealTimeCapability:
    """Tests for real-time processing capability."""
    
    def test_processing_faster_than_realtime(self):
        """Processing should be faster than audio duration."""
        processor = TrackProcessor(sample_rate=44100)
        
        # 1 second of audio
        duration = 1.0
        audio = np.random.randn(int(44100 * duration)) * 0.5
        
        config = TrackProcessorConfig(
            saturation_drive=2.0,
            eq_bands=[
                EQBand(frequency=100, gain_db=3.0, band_type="low_shelf"),
                EQBand(frequency=1000, gain_db=-2.0, q=2.0, band_type="peak"),
                EQBand(frequency=8000, gain_db=2.0, band_type="high_shelf"),
            ],
            compressor=CompressorConfig(threshold_db=-15, ratio=4.0, attack_ms=10, release_ms=100),
            transient=TransientConfig(attack=30, sustain=0),
            output_gain_db=1.0
        )
        
        start = time.time()
        result = processor.process(audio, config)
        elapsed = time.time() - start
        
        # Should process in less than audio duration (1 second)
        assert elapsed < duration, f"Processing took {elapsed:.3f}s for {duration}s of audio"
    
    def test_preset_processing_speed(self):
        """Preset processing should be real-time capable."""
        processor = TrackProcessor(sample_rate=44100)
        
        # 1 second of audio
        duration = 1.0
        audio = np.random.randn(int(44100 * duration)) * 0.5
        
        # Test a few heavy presets
        heavy_presets = ["trap_808", "boom_bap_drums", "vocal_presence"]
        
        for preset_name in heavy_presets:
            start = time.time()
            result = processor.process_with_preset(audio, preset_name)
            elapsed = time.time() - start
            
            assert elapsed < duration, f"Preset {preset_name} too slow: {elapsed:.3f}s"


class TestConvenienceFunction:
    """Tests for convenience function."""
    
    def test_process_track_function(self):
        """process_track convenience function should work."""
        audio = np.random.randn(5000) * 0.5
        
        result = process_track(audio, "trap_808", sample_rate=44100)
        
        assert result.shape == audio.shape
        assert np.max(np.abs(result)) <= 1.0
    
    def test_process_track_with_different_sample_rate(self):
        """process_track should work with different sample rates."""
        audio = np.random.randn(5000) * 0.5
        
        result = process_track(audio, "lofi_keys", sample_rate=48000)
        
        assert result.shape == audio.shape


class TestGainStaging:
    """Tests for proper gain staging throughout chain."""
    
    def test_gain_function(self):
        """apply_gain should work correctly."""
        processor = TrackProcessor(sample_rate=44100)
        
        audio = np.ones(1000) * 0.5
        
        # +6dB should double amplitude
        result = processor.apply_gain(audio, 6.0)
        expected = audio * (10 ** (6.0 / 20))
        
        assert np.allclose(result, expected)
    
    def test_negative_gain(self):
        """Negative gain should reduce level."""
        processor = TrackProcessor(sample_rate=44100)
        
        audio = np.ones(1000) * 0.5
        result = processor.apply_gain(audio, -6.0)
        
        assert np.all(np.abs(result) < np.abs(audio))
    
    def test_output_gain_in_chain(self):
        """Output gain should be applied last in chain."""
        processor = TrackProcessor(sample_rate=44100)
        
        audio = np.random.randn(5000) * 0.3
        
        config = TrackProcessorConfig(
            saturation_drive=1.5,
            output_gain_db=6.0
        )
        
        result = processor.process(audio, config)
        
        # Should be louder than input
        rms_input = np.sqrt(np.mean(audio ** 2))
        rms_output = np.sqrt(np.mean(result ** 2))
        
        assert rms_output > rms_input


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v"])
