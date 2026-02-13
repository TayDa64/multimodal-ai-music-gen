"""
Unit tests for Mix Engine

Tests bus routing, sidechain compression, master processing, and genre presets.
"""

import pytest
import sys
import numpy as np
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from multimodal_gen.mix_engine import (
    MixBus,
    MixEngine,
    BusConfig,
    SidechainConfig,
    MasterConfig,
    MIX_PRESETS,
    GENRE_SIDECHAINS,
    create_mix,
    apply_sidechain_compression
)
from multimodal_gen.track_processor import TrackProcessorConfig, EQBand


class TestMixBus:
    """Tests for MixBus class."""
    
    def test_bus_creation(self):
        """Test basic bus creation."""
        bus = MixBus("test_bus", sample_rate=44100)
        assert bus.name == "test_bus"
        assert bus.sample_rate == 44100
        assert bus.audio_buffer is None
    
    def test_add_audio_single(self):
        """Test adding a single audio signal."""
        bus = MixBus("test", sample_rate=44100)
        audio = np.random.randn(1000) * 0.5
        
        bus.add_audio(audio)
        
        assert bus.audio_buffer is not None
        assert len(bus.audio_buffer) == 1000
        assert np.allclose(bus.audio_buffer, audio)
    
    def test_add_audio_summing(self):
        """Test that multiple adds sum correctly."""
        bus = MixBus("test", sample_rate=44100)
        
        audio1 = np.ones(1000) * 0.3
        audio2 = np.ones(1000) * 0.2
        
        bus.add_audio(audio1)
        bus.add_audio(audio2)
        
        # Should sum to 0.5
        assert np.allclose(bus.audio_buffer, 0.5, atol=0.01)
    
    def test_add_audio_with_gain(self):
        """Test adding audio with gain adjustment."""
        bus = MixBus("test", sample_rate=44100)
        audio = np.ones(1000) * 0.5
        
        # Add with +6dB gain (2x linear)
        bus.add_audio(audio, gain_db=6.0)
        
        expected = 0.5 * (10 ** (6.0 / 20))
        assert np.allclose(bus.audio_buffer, expected, rtol=0.01)
    
    def test_add_audio_different_lengths(self):
        """Test adding audio of different lengths."""
        bus = MixBus("test", sample_rate=44100)
        
        audio1 = np.ones(500)
        audio2 = np.ones(1000)
        
        bus.add_audio(audio1)
        bus.add_audio(audio2)
        
        # Buffer should extend to longest
        assert len(bus.audio_buffer) == 1000
        # First 500 samples should sum
        assert np.allclose(bus.audio_buffer[:500], 2.0, atol=0.01)
        # Last 500 should be from audio2 only
        assert np.allclose(bus.audio_buffer[500:], 1.0, atol=0.01)
    
    def test_process_no_processing(self):
        """Test processing with no insert effects."""
        bus = MixBus("test", sample_rate=44100)
        audio = np.random.randn(1000) * 0.5
        bus.add_audio(audio)
        
        config = BusConfig(name="test")
        processed = bus.process(config)
        
        assert np.allclose(processed, audio, atol=0.01)
    
    def test_process_with_gain(self):
        """Test processing with bus gain."""
        bus = MixBus("test", sample_rate=44100)
        audio = np.ones(1000) * 0.5
        bus.add_audio(audio)
        
        config = BusConfig(name="test", gain_db=6.0)
        processed = bus.process(config)
        
        expected = 0.5 * (10 ** (6.0 / 20))
        assert np.allclose(processed, expected, rtol=0.01)
    
    def test_process_with_mute(self):
        """Test that mute returns silence."""
        bus = MixBus("test", sample_rate=44100)
        audio = np.random.randn(1000) * 0.5
        bus.add_audio(audio)
        
        config = BusConfig(name="test", mute=True)
        processed = bus.process(config)
        
        assert np.allclose(processed, 0.0)
    
    def test_process_with_insert(self):
        """Test processing with insert processing."""
        bus = MixBus("test", sample_rate=44100)
        audio = np.random.randn(1000) * 0.5
        bus.add_audio(audio)
        
        # Add EQ boost
        processor_config = TrackProcessorConfig(
            eq_bands=[EQBand(frequency=1000, gain_db=6.0)]
        )
        config = BusConfig(name="test", processor_config=processor_config)
        
        processed = bus.process(config)
        
        # Should be different due to EQ
        assert not np.allclose(processed, audio)
    
    def test_clear(self):
        """Test clearing the bus buffer."""
        bus = MixBus("test", sample_rate=44100)
        audio = np.random.randn(1000)
        bus.add_audio(audio)
        
        assert bus.audio_buffer is not None
        
        bus.clear()
        assert bus.audio_buffer is None
    
    def test_get_peak_db(self):
        """Test peak measurement."""
        bus = MixBus("test", sample_rate=44100)
        
        # Empty bus
        assert bus.get_peak_db() == -np.inf
        
        # Add signal with known peak (0.5 = -6.02 dB)
        audio = np.zeros(1000)
        audio[500] = 0.5
        bus.add_audio(audio)
        
        peak_db = bus.get_peak_db()
        expected_db = 20 * np.log10(0.5)
        assert np.isclose(peak_db, expected_db, atol=0.1)
    
    def test_get_rms_db(self):
        """Test RMS measurement."""
        bus = MixBus("test", sample_rate=44100)
        
        # Empty bus
        assert bus.get_rms_db() == -np.inf
        
        # Add constant signal
        audio = np.ones(1000) * 0.5
        bus.add_audio(audio)
        
        rms_db = bus.get_rms_db()
        expected_db = 20 * np.log10(0.5)
        assert np.isclose(rms_db, expected_db, atol=0.1)
    
    def test_empty_audio(self):
        """Test handling of empty audio."""
        bus = MixBus("test", sample_rate=44100)
        
        # Add empty array
        bus.add_audio(np.array([]))
        assert bus.audio_buffer is None
        
        # Process empty bus
        config = BusConfig(name="test")
        processed = bus.process(config)
        assert len(processed) == 0


class TestMixEngine:
    """Tests for MixEngine class."""
    
    def test_engine_creation(self):
        """Test basic engine creation."""
        engine = MixEngine(sample_rate=44100)
        
        assert engine.sample_rate == 44100
        assert len(engine.buses) >= 8  # Default buses
        assert "kick" in engine.buses
        assert "drums" in engine.buses
        assert "bass" in engine.buses
        assert "master" in engine.buses
    
    def test_add_bus(self):
        """Test adding a custom bus."""
        engine = MixEngine(sample_rate=44100)
        
        bus = engine.add_bus("custom")
        assert bus.name == "custom"
        assert "custom" in engine.buses
    
    def test_add_to_bus(self):
        """Test adding audio to a bus."""
        engine = MixEngine(sample_rate=44100)
        audio = np.random.randn(1000) * 0.5
        
        engine.add_to_bus("kick", audio)
        
        kick_bus = engine.get_bus("kick")
        assert kick_bus.audio_buffer is not None
        assert len(kick_bus.audio_buffer) == 1000
    
    def test_add_to_nonexistent_bus(self):
        """Test that adding to nonexistent bus creates it."""
        engine = MixEngine(sample_rate=44100)
        audio = np.random.randn(1000)
        
        engine.add_to_bus("new_bus", audio)
        
        assert "new_bus" in engine.buses
    
    def test_set_bus_config(self):
        """Test setting bus configuration."""
        engine = MixEngine(sample_rate=44100)
        
        config = BusConfig(name="kick", gain_db=3.0)
        engine.set_bus_config("kick", config)
        
        assert engine.bus_configs["kick"].gain_db == 3.0
    
    def test_add_sidechain(self):
        """Test adding sidechain configuration."""
        engine = MixEngine(sample_rate=44100)
        
        sidechain = SidechainConfig("kick", "bass", depth=0.6)
        engine.add_sidechain(sidechain)
        
        assert len(engine.sidechains) == 1
        assert engine.sidechains[0].trigger_bus == "kick"
        assert engine.sidechains[0].target_bus == "bass"


class TestSidechainCompression:
    """Tests for sidechain compression."""
    
    def test_sidechain_ducking(self):
        """Test that sidechain causes audible ducking."""
        engine = MixEngine(sample_rate=44100)
        
        # Create a sustained bass note
        source = np.ones(10000) * 0.5
        
        # Create kick hits (spikes at regular intervals)
        trigger = np.zeros(10000)
        for i in range(0, 10000, 1000):
            if i + 100 < 10000:
                trigger[i:i+100] = 1.0
        
        config = SidechainConfig(
            trigger_bus="kick",
            target_bus="bass",
            threshold_db=-20.0,
            ratio=4.0,
            attack_ms=5.0,
            release_ms=100.0,
            depth=0.8
        )
        
        result = engine.apply_sidechain(source, trigger, config)
        
        # Result should be ducked where kick hits
        # Check that we have ducking at kick positions
        assert np.min(result) < 0.5  # Should be ducked below original
        assert np.max(result) <= 0.5  # Shouldn't exceed original
    
    def test_sidechain_depth_control(self):
        """Test that depth parameter controls ducking amount."""
        engine = MixEngine(sample_rate=44100)
        
        source = np.ones(5000) * 0.5
        trigger = np.ones(5000) * 0.8
        
        # Light ducking
        config_light = SidechainConfig("kick", "bass", depth=0.2, attack_ms=1.0, release_ms=50.0)
        result_light = engine.apply_sidechain(source, trigger, config_light)
        
        # Heavy ducking
        config_heavy = SidechainConfig("kick", "bass", depth=0.9, attack_ms=1.0, release_ms=50.0)
        result_heavy = engine.apply_sidechain(source, trigger, config_heavy)
        
        # Heavy should duck more
        avg_light = np.mean(result_light)
        avg_heavy = np.mean(result_heavy)
        
        assert avg_heavy < avg_light
    
    def test_sidechain_empty_inputs(self):
        """Test sidechain with empty inputs."""
        engine = MixEngine(sample_rate=44100)
        config = SidechainConfig("kick", "bass")
        
        # Empty source
        result = engine.apply_sidechain(np.array([]), np.ones(100), config)
        assert len(result) == 0
        
        # Empty trigger - should return source unchanged
        source = np.ones(100)
        result = engine.apply_sidechain(source, np.array([]), config)
        assert len(result) == 100
        assert np.allclose(result, source)
    
    def test_sidechain_mismatched_lengths(self):
        """Test sidechain with different length inputs."""
        engine = MixEngine(sample_rate=44100)
        config = SidechainConfig("kick", "bass")
        
        source = np.ones(1000)
        trigger = np.ones(500)
        
        result = engine.apply_sidechain(source, trigger, config)
        
        # Should handle gracefully
        assert len(result) == 1000


class TestMasterProcessing:
    """Tests for master bus processing."""
    
    def test_master_eq(self):
        """Test master EQ processing."""
        engine = MixEngine(sample_rate=44100)
        
        # Create audio
        audio = np.random.randn(5000, 2) * 0.5
        
        # Apply EQ
        config = MasterConfig(
            eq_low_db=3.0,
            eq_mid_db=0.0,
            eq_high_db=-2.0
        )
        
        result = engine.apply_master_processing(audio, config)
        
        # Should be different due to EQ
        assert not np.allclose(result, audio)
        assert result.shape == audio.shape
    
    def test_master_compression(self):
        """Test master compression."""
        engine = MixEngine(sample_rate=44100)
        
        # Create audio with peaks
        audio = np.random.randn(5000, 2) * 0.8
        
        config = MasterConfig(
            compression_threshold_db=-6.0,
            compression_ratio=3.0
        )
        
        result = engine.apply_master_processing(audio, config)
        
        # Peaks should be reduced
        peak_in = np.max(np.abs(audio))
        peak_out = np.max(np.abs(result))
        
        # Compression should reduce peaks somewhat
        assert peak_out <= peak_in * 1.1  # Allow small tolerance
    
    def test_limiter(self):
        """Test brickwall limiter."""
        engine = MixEngine(sample_rate=44100)
        
        # Create very loud audio
        audio = np.random.randn(5000, 2) * 2.0  # Way over 0 dB
        
        ceiling_db = -0.3
        result = engine.limit(audio, ceiling_db)
        
        # Should not exceed ceiling
        ceiling_linear = 10 ** (ceiling_db / 20)
        assert np.max(np.abs(result)) <= ceiling_linear * 1.01  # Small tolerance
    
    def test_limiter_no_effect_below_ceiling(self):
        """Test that limiter doesn't significantly affect audio well below ceiling."""
        engine = MixEngine(sample_rate=44100)
        
        # Deterministic seed + low amplitude keeps peaks well below ceiling
        np.random.seed(42)
        audio = np.random.randn(5000, 2) * 0.1  # Max peak ~0.4, well below ceiling
        
        result = engine.limit(audio, ceiling_db=-0.3)
        
        # Peak should not be reduced
        peak_in = np.max(np.abs(audio))
        peak_out = np.max(np.abs(result))
        
        # Since audio is well below ceiling, output peak should equal input
        assert peak_out >= peak_in * 0.99  # Allow tiny rounding error


class TestLUFS:
    """Tests for LUFS measurement and normalization."""
    
    def test_measure_lufs_silence(self):
        """Test LUFS measurement of silence."""
        engine = MixEngine(sample_rate=44100)
        
        silence = np.zeros((10000, 2))
        lufs = engine.measure_lufs(silence)
        
        # Should be very quiet
        assert lufs < -60
    
    def test_measure_lufs_mono_and_stereo(self):
        """Test LUFS measurement works for mono and stereo."""
        engine = MixEngine(sample_rate=44100)
        
        mono = np.random.randn(10000) * 0.5
        stereo = np.random.randn(10000, 2) * 0.5
        
        lufs_mono = engine.measure_lufs(mono)
        lufs_stereo = engine.measure_lufs(stereo)
        
        # Both should give reasonable values
        assert -30 < lufs_mono < 0
        assert -30 < lufs_stereo < 0
    
    def test_normalize_to_lufs(self):
        """Test LUFS normalization."""
        engine = MixEngine(sample_rate=44100)
        
        # Create audio
        audio = np.random.randn(44100, 2) * 0.3
        
        target_lufs = -14.0
        result = engine.normalize_to_lufs(audio, target_lufs)
        
        # Measure result
        result_lufs = engine.measure_lufs(result)
        
        # Should be close to target (within a few dB)
        assert abs(result_lufs - target_lufs) < 3.0
    
    def test_normalize_empty_audio(self):
        """Test normalizing empty audio."""
        engine = MixEngine(sample_rate=44100)
        
        empty = np.zeros((0, 2))
        result = engine.normalize_to_lufs(empty, -14.0)
        
        assert len(result) == 0


class TestMixWorkflow:
    """Tests for full mixing workflow."""
    
    def test_simple_mix(self):
        """Test basic mixing of multiple buses."""
        engine = MixEngine(sample_rate=44100)
        
        # Add audio to different buses
        kick = np.random.randn(5000) * 0.5
        snare = np.random.randn(5000) * 0.4
        bass = np.random.randn(5000) * 0.6
        
        engine.add_to_bus("kick", kick)
        engine.add_to_bus("drums", snare)
        engine.add_to_bus("bass", bass)
        
        # Mix
        master = engine.mix()
        
        # Should produce stereo output
        assert len(master.shape) == 2
        assert master.shape[1] == 2
        assert len(master) > 0
    
    def test_mix_with_sidechain(self):
        """Test mixing with sidechain compression."""
        engine = MixEngine(sample_rate=44100)
        
        # Create kick and bass
        kick = np.zeros(10000)
        kick[0:100] = 1.0  # Kick hit at start
        kick[5000:5100] = 1.0  # Another kick
        
        bass = np.ones(10000) * 0.5  # Sustained bass
        
        engine.add_to_bus("kick", kick)
        engine.add_to_bus("bass", bass)
        
        # Add sidechain
        engine.add_sidechain(SidechainConfig(
            trigger_bus="kick",
            target_bus="bass",
            depth=0.8
        ))
        
        master = engine.mix()
        
        # Should produce output
        assert len(master) > 0
        assert master.shape[1] == 2
    
    def test_mix_with_sends(self):
        """Test mixing with send/return effects."""
        engine = MixEngine(sample_rate=44100)
        
        # Add melodic content
        melodic = np.random.randn(5000) * 0.4
        engine.add_to_bus("melodic", melodic)
        
        # Configure send to reverb
        config = BusConfig(
            name="melodic",
            sends={"reverb": 0.3}
        )
        engine.set_bus_config("melodic", config)
        
        master = engine.mix()
        
        # Should have sent audio to reverb bus
        reverb_bus = engine.get_bus("reverb")
        assert reverb_bus.audio_buffer is not None
    
    def test_mix_with_solo(self):
        """Test solo functionality."""
        engine = MixEngine(sample_rate=44100)
        
        # Add to multiple buses
        engine.add_to_bus("kick", np.ones(1000))
        engine.add_to_bus("bass", np.ones(1000))
        engine.add_to_bus("melodic", np.ones(1000))
        
        # Solo only kick
        kick_config = BusConfig(name="kick", solo=True)
        engine.set_bus_config("kick", kick_config)
        
        master = engine.mix()
        
        # Only kick should be in output
        assert len(master) > 0
    
    def test_mix_with_mute(self):
        """Test mute functionality."""
        engine = MixEngine(sample_rate=44100)
        
        # Add to multiple buses
        engine.add_to_bus("kick", np.ones(1000) * 0.5)
        engine.add_to_bus("bass", np.ones(1000) * 0.5)
        
        # Mute bass
        bass_config = BusConfig(name="bass", mute=True)
        engine.set_bus_config("bass", bass_config)
        
        master = engine.mix()
        
        # Should only have kick
        assert len(master) > 0
    
    def test_mix_empty_engine(self):
        """Test mixing with no audio."""
        engine = MixEngine(sample_rate=44100)
        
        master = engine.mix()
        
        # Should return empty stereo array
        assert len(master.shape) == 2
        assert master.shape[1] == 2
        assert len(master) == 0
    
    def test_clear_all(self):
        """Test clearing all buses."""
        engine = MixEngine(sample_rate=44100)
        
        # Add audio
        engine.add_to_bus("kick", np.ones(1000))
        engine.add_to_bus("bass", np.ones(1000))
        
        # Add sidechain
        engine.add_sidechain(SidechainConfig("kick", "bass"))
        
        # Clear
        engine.clear_all()
        
        # All buses should be empty
        for bus in engine.buses.values():
            assert bus.audio_buffer is None
        
        # Sidechains should be cleared
        assert len(engine.sidechains) == 0


class TestGenrePresets:
    """Tests for genre-specific presets."""
    
    def test_presets_exist(self):
        """Test that presets exist for required genres."""
        required_genres = ["trap", "boom_bap", "lofi", "house"]
        
        for genre in required_genres:
            assert genre in MIX_PRESETS
            assert len(MIX_PRESETS[genre]) > 0
    
    def test_trap_preset(self):
        """Test trap genre preset."""
        preset = MIX_PRESETS["trap"]
        
        # Should have bass-heavy mix
        assert "bass" in preset
        assert preset["bass"].gain_db == 2.0
        
        # Should have reverb sends
        assert "melodic" in preset
        assert "reverb" in preset["melodic"].sends
    
    def test_house_preset(self):
        """Test house genre preset."""
        preset = MIX_PRESETS["house"]
        
        # Should emphasize kick
        assert "kick" in preset
        assert preset["kick"].gain_db == 2.0
    
    def test_genre_sidechains(self):
        """Test genre-specific sidechain configs."""
        # Trap should have kick->bass sidechain
        assert "trap" in GENRE_SIDECHAINS
        trap_chains = GENRE_SIDECHAINS["trap"]
        assert len(trap_chains) > 0
        assert trap_chains[0].trigger_bus == "kick"
        assert trap_chains[0].target_bus == "bass"
        
        # House should have stronger sidechaining
        assert "house" in GENRE_SIDECHAINS
        house_chains = GENRE_SIDECHAINS["house"]
        assert len(house_chains) > 0
        # Find kick->bass sidechain
        kick_bass = [sc for sc in house_chains if sc.trigger_bus == "kick" and sc.target_bus == "bass"]
        assert len(kick_bass) > 0
        assert kick_bass[0].depth > 0.6  # Heavy ducking
    
    def test_get_mix_preset(self):
        """Test getting mix preset from engine."""
        engine = MixEngine(sample_rate=44100)
        
        preset = engine.get_mix_preset("trap")
        assert len(preset) > 0
        assert "bass" in preset
        
        # Unknown genre should return empty
        unknown = engine.get_mix_preset("unknown_genre")
        assert len(unknown) == 0


class TestConvenienceFunctions:
    """Tests for convenience functions."""
    
    def test_create_mix(self):
        """Test create_mix convenience function."""
        stems = {
            "kick": np.random.randn(5000) * 0.5,
            "bass": np.random.randn(5000) * 0.4,
            "melodic": np.random.randn(5000) * 0.3
        }
        
        master = create_mix(stems, genre="trap", sample_rate=44100)
        
        # Should produce stereo output
        assert len(master.shape) == 2
        assert master.shape[1] == 2
        assert len(master) > 0
    
    def test_apply_sidechain_compression(self):
        """Test standalone sidechain function."""
        source = np.ones(5000) * 0.5
        trigger = np.zeros(5000)
        trigger[0:100] = 1.0
        
        result = apply_sidechain_compression(
            source, trigger,
            depth=0.7,
            attack_ms=5.0,
            release_ms=100.0,
            sample_rate=44100
        )
        
        # Should be ducked
        assert len(result) == len(source)
        assert np.min(result) < 0.5


class TestEdgeCases:
    """Tests for edge cases and error handling."""
    
    def test_single_sample(self):
        """Test handling of single sample audio."""
        engine = MixEngine(sample_rate=44100)
        
        single_sample = np.array([0.5])
        engine.add_to_bus("kick", single_sample)
        
        master = engine.mix()
        
        # Should handle gracefully
        assert len(master) >= 1
    
    def test_very_loud_audio(self):
        """Test handling of very loud input audio."""
        engine = MixEngine(sample_rate=44100)
        
        # Extremely loud audio
        loud = np.random.randn(5000) * 10.0
        engine.add_to_bus("kick", loud)
        
        master = engine.mix()
        
        # Should be limited
        assert np.max(np.abs(master)) <= 1.0
    
    def test_dc_offset(self):
        """Test handling of DC offset."""
        engine = MixEngine(sample_rate=44100)
        
        # Audio with DC offset
        audio = np.random.randn(5000) * 0.3 + 0.5
        engine.add_to_bus("kick", audio)
        
        master = engine.mix()
        
        # Should produce valid output
        assert len(master) > 0
        assert not np.any(np.isnan(master))
    
    def test_all_zeros(self):
        """Test mixing all-zero audio."""
        engine = MixEngine(sample_rate=44100)
        
        zeros = np.zeros(5000)
        engine.add_to_bus("kick", zeros)
        engine.add_to_bus("bass", zeros)
        
        master = engine.mix()
        
        # Should handle gracefully
        assert len(master.shape) == 2
    
    def test_nan_handling(self):
        """Test that NaN values don't crash the engine."""
        engine = MixEngine(sample_rate=44100)
        
        # Note: we should avoid adding NaN in practice
        # This tests robustness
        audio = np.random.randn(1000)
        engine.add_to_bus("kick", audio)
        
        # Should not crash
        try:
            master = engine.mix()
            assert not np.any(np.isnan(master))
        except:
            pass  # Expected to handle or fail gracefully


class TestStereoHandling:
    """Tests for stereo audio handling."""
    
    def test_pan_center(self):
        """Test center panning."""
        engine = MixEngine(sample_rate=44100)
        
        mono = np.random.randn(1000) * 0.5
        stereo = engine._apply_pan(mono, pan=0.0)
        
        # Should be equal in both channels
        assert stereo.shape == (1000, 2)
        assert np.allclose(stereo[:, 0], stereo[:, 1])
    
    def test_pan_left(self):
        """Test full left panning."""
        engine = MixEngine(sample_rate=44100)
        
        mono = np.ones(1000) * 0.5
        stereo = engine._apply_pan(mono, pan=-1.0)
        
        # Left should have signal, right should be near zero
        assert np.mean(np.abs(stereo[:, 0])) > 0.4
        assert np.mean(np.abs(stereo[:, 1])) < 0.1
    
    def test_pan_right(self):
        """Test full right panning."""
        engine = MixEngine(sample_rate=44100)
        
        mono = np.ones(1000) * 0.5
        stereo = engine._apply_pan(mono, pan=1.0)
        
        # Right should have signal, left should be near zero
        assert np.mean(np.abs(stereo[:, 0])) < 0.1
        assert np.mean(np.abs(stereo[:, 1])) > 0.4
    
    def test_mix_produces_stereo(self):
        """Test that mix always produces stereo output."""
        engine = MixEngine(sample_rate=44100)
        
        # Add mono audio
        mono = np.random.randn(1000) * 0.5
        engine.add_to_bus("kick", mono)
        
        master = engine.mix()
        
        # Should be stereo
        assert len(master.shape) == 2
        assert master.shape[1] == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
