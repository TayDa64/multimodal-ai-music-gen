"""
Bus Processing & Mix Engine - Professional mixing with bus routing and master processing.

Provides bus-based mixing with sidechain compression, send/return effects,
and master limiting for streaming-ready output (-14 LUFS target).
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import numpy as np
from multimodal_gen.track_processor import TrackProcessor, TrackProcessorConfig


@dataclass
class BusConfig:
    """Configuration for an audio bus."""
    name: str
    processor_config: Optional[TrackProcessorConfig] = None  # Insert processing
    sends: Dict[str, float] = field(default_factory=dict)    # Bus name -> send level (0-1)
    gain_db: float = 0.0                                      # Bus output gain
    pan: float = 0.0                                          # -1 (left) to 1 (right)
    mute: bool = False
    solo: bool = False


@dataclass
class SidechainConfig:
    """Sidechain compression configuration."""
    trigger_bus: str           # Bus that triggers compression (e.g., "kick")
    target_bus: str            # Bus being compressed (e.g., "bass")
    threshold_db: float = -20.0
    ratio: float = 4.0
    attack_ms: float = 5.0
    release_ms: float = 100.0
    depth: float = 0.5         # How much ducking (0-1)


@dataclass
class MasterConfig:
    """Master bus configuration."""
    eq_low_db: float = 0.0      # Low shelf at 100Hz
    eq_mid_db: float = 0.0      # Peak at 1kHz
    eq_high_db: float = 0.0     # High shelf at 8kHz
    compression_threshold_db: float = -6.0
    compression_ratio: float = 2.0
    limiter_ceiling_db: float = -0.3   # True peak limit
    target_lufs: float = -14.0          # Streaming target
    use_true_peak_limiter: bool = False  # Use ISP-aware limiter
    true_peak_ceiling_dbtp: float = -1.0  # -1 dBTP for streaming compliance


class MixBus:
    """
    Audio bus with insert processing and send/return capability.
    
    Usage:
        bus = MixBus("drums", sample_rate=44100)
        bus.add_audio(kick_audio)
        bus.add_audio(snare_audio)
        output = bus.process(config)
    """
    
    def __init__(self, name: str, sample_rate: int = 44100):
        self.name = name
        self.sample_rate = sample_rate
        self.processor = TrackProcessor(sample_rate)
        self.audio_buffer: Optional[np.ndarray] = None
    
    def add_audio(self, audio: np.ndarray, gain_db: float = 0.0) -> None:
        """Add audio to the bus (summing)."""
        if len(audio) == 0:
            return
        
        # Apply gain
        gain_linear = 10 ** (gain_db / 20)
        audio_scaled = audio * gain_linear
        
        # Sum into buffer
        if self.audio_buffer is None:
            self.audio_buffer = audio_scaled.copy()
        else:
            # Extend buffer if needed
            if len(audio_scaled) > len(self.audio_buffer):
                self.audio_buffer = np.pad(
                    self.audio_buffer, 
                    (0, len(audio_scaled) - len(self.audio_buffer)),
                    mode='constant'
                )
            
            # Add audio
            self.audio_buffer[:len(audio_scaled)] += audio_scaled
    
    def process(self, config: BusConfig) -> np.ndarray:
        """Process bus through inserts and return output."""
        if self.audio_buffer is None or len(self.audio_buffer) == 0:
            return np.array([])
        
        processed = self.audio_buffer.copy()
        
        # Apply insert processing if configured
        if config.processor_config is not None:
            processed = self.processor.process(processed, config.processor_config)
        
        # Apply bus gain
        if config.gain_db != 0.0:
            gain_linear = 10 ** (config.gain_db / 20)
            processed = processed * gain_linear
        
        # Handle mute/solo
        if config.mute:
            return np.zeros_like(processed)
        
        return processed
    
    def clear(self) -> None:
        """Clear the audio buffer."""
        self.audio_buffer = None
    
    def get_peak_db(self) -> float:
        """Get peak level in dB."""
        if self.audio_buffer is None or len(self.audio_buffer) == 0:
            return -np.inf
        
        peak = np.max(np.abs(self.audio_buffer))
        if peak > 0:
            return 20 * np.log10(peak)
        return -np.inf
    
    def get_rms_db(self) -> float:
        """Get RMS level in dB."""
        if self.audio_buffer is None or len(self.audio_buffer) == 0:
            return -np.inf
        
        rms = np.sqrt(np.mean(self.audio_buffer ** 2))
        if rms > 0:
            return 20 * np.log10(rms)
        return -np.inf


class MixEngine:
    """
    Full mixing engine with buses, sends, sidechains, and master processing.
    
    Default bus structure:
    - kick: Individual kick drum
    - drums: All drums summed
    - bass: Bass instruments
    - melodic: Synths, keys, melodic elements
    - fx: Sound effects, risers
    - reverb: Return bus for reverb send
    - delay: Return bus for delay send
    - master: Final output
    
    Usage:
        engine = MixEngine(sample_rate=44100)
        engine.add_to_bus("kick", kick_audio)
        engine.add_to_bus("drums", snare_audio)
        engine.add_to_bus("bass", bass_audio)
        
        # Configure sidechain
        engine.add_sidechain(SidechainConfig(
            trigger_bus="kick",
            target_bus="bass",
            depth=0.6
        ))
        
        # Mix and get master output
        master = engine.mix(master_config)
    """
    
    def __init__(self, sample_rate: int = 44100, buffer_length: int = None):
        self.sample_rate = sample_rate
        self.buffer_length = buffer_length
        self.buses: Dict[str, MixBus] = {}
        self.sidechains: List[SidechainConfig] = []
        self.bus_configs: Dict[str, BusConfig] = {}
        self._init_default_buses()
    
    def _init_default_buses(self) -> None:
        """Initialize default bus structure."""
        default_bus_names = [
            "kick", "drums", "bass", "melodic", 
            "fx", "reverb", "delay", "master"
        ]
        
        for bus_name in default_bus_names:
            self.buses[bus_name] = MixBus(bus_name, self.sample_rate)
            self.bus_configs[bus_name] = BusConfig(name=bus_name)
    
    def add_bus(self, name: str, config: Optional[BusConfig] = None) -> MixBus:
        """Add a new bus to the mixer."""
        bus = MixBus(name, self.sample_rate)
        self.buses[name] = bus
        self.bus_configs[name] = config if config else BusConfig(name=name)
        return bus
    
    def add_to_bus(self, bus_name: str, audio: np.ndarray, gain_db: float = 0.0) -> None:
        """Add audio to a bus."""
        if bus_name not in self.buses:
            self.add_bus(bus_name)
        
        self.buses[bus_name].add_audio(audio, gain_db)
    
    def set_bus_config(self, bus_name: str, config: BusConfig) -> None:
        """Set processing configuration for a bus."""
        if bus_name not in self.bus_configs:
            self.bus_configs[bus_name] = config
        else:
            self.bus_configs[bus_name] = config
    
    def add_sidechain(self, config: SidechainConfig) -> None:
        """Add a sidechain compression routing."""
        self.sidechains.append(config)
    
    def apply_sidechain(
        self,
        source: np.ndarray,
        trigger: np.ndarray,
        config: SidechainConfig
    ) -> np.ndarray:
        """
        Apply sidechain compression.
        
        The source audio is ducked based on the trigger audio level.
        Classic use: kick triggers bass ducking for "pumping" effect.
        
        Args:
            source: Audio to be compressed
            trigger: Audio that triggers compression
            config: Sidechain settings
            
        Returns:
            Sidechained audio
        """
        if len(source) == 0:
            return source
        
        if len(trigger) == 0:
            return source
        
        # Ensure trigger is at least as long as source
        if len(trigger) < len(source):
            trigger = np.pad(trigger, (0, len(source) - len(trigger)), mode='constant')
        else:
            trigger = trigger[:len(source)]
        
        # Calculate envelope from trigger
        attack_samples = int(config.attack_ms * self.sample_rate / 1000)
        release_samples = int(config.release_ms * self.sample_rate / 1000)
        
        # Get trigger envelope (peak detection)
        trigger_abs = np.abs(trigger)
        envelope = np.zeros_like(trigger_abs)
        
        envelope_state = 0.0
        attack_coeff = np.exp(-1.0 / max(attack_samples, 1))
        release_coeff = np.exp(-1.0 / max(release_samples, 1))
        
        for i in range(len(trigger_abs)):
            if trigger_abs[i] > envelope_state:
                # Attack
                coeff = attack_coeff
            else:
                # Release
                coeff = release_coeff
            
            envelope_state = coeff * envelope_state + (1 - coeff) * trigger_abs[i]
            envelope[i] = envelope_state
        
        # Convert to dB
        envelope_db = np.where(envelope > 0, 20 * np.log10(envelope + 1e-10), -100)
        
        # Calculate gain reduction
        threshold = config.threshold_db
        ratio = config.ratio
        
        gain_reduction_db = np.zeros_like(envelope_db)
        above_threshold = envelope_db > threshold
        
        if np.any(above_threshold):
            excess = envelope_db[above_threshold] - threshold
            gain_reduction_db[above_threshold] = -excess * (1 - 1 / ratio) * config.depth
        
        # Convert to linear gain
        gain_linear = 10 ** (gain_reduction_db / 20)
        
        # Apply to source
        return source * gain_linear
    
    def process_sends(self, bus_name: str, audio: np.ndarray) -> None:
        """Process send routing from a bus to return buses."""
        config = self.bus_configs.get(bus_name)
        if not config or not config.sends:
            return
        
        for target_bus, send_level in config.sends.items():
            if target_bus in self.buses and send_level > 0:
                # Send audio to target bus at specified level
                send_db = 20 * np.log10(send_level) if send_level > 0 else -100
                self.add_to_bus(target_bus, audio, send_db)
    
    def mix(self, master_config: Optional[MasterConfig] = None) -> np.ndarray:
        """
        Process all buses and return master output.
        
        Processing order:
        1. Process individual track buses (kick, snare, etc.)
        2. Sum to group buses (drums, melodic, etc.)
        3. Apply sidechains
        4. Process sends to return buses (reverb, delay)
        5. Sum to master
        6. Apply master processing
        7. Limit to target LUFS
        
        Returns:
            Stereo master output, limited and LUFS-normalized
        """
        if master_config is None:
            master_config = MasterConfig()
        
        # Process all buses (except master)
        processed_buses: Dict[str, np.ndarray] = {}
        
        for bus_name, bus in self.buses.items():
            if bus_name == "master":
                continue
            
            config = self.bus_configs.get(bus_name, BusConfig(name=bus_name))
            
            # Skip if solo is active on other buses
            solo_active = any(c.solo for c in self.bus_configs.values())
            if solo_active and not config.solo:
                processed_buses[bus_name] = np.array([])
                continue
            
            processed = bus.process(config)
            processed_buses[bus_name] = processed
            
            # Process sends
            if len(processed) > 0:
                self.process_sends(bus_name, processed)
        
        # Apply sidechains
        for sidechain_config in self.sidechains:
            trigger_audio = processed_buses.get(sidechain_config.trigger_bus)
            target_audio = processed_buses.get(sidechain_config.target_bus)
            
            if trigger_audio is not None and target_audio is not None:
                if len(trigger_audio) > 0 and len(target_audio) > 0:
                    processed_buses[sidechain_config.target_bus] = self.apply_sidechain(
                        target_audio, trigger_audio, sidechain_config
                    )
        
        # Sum to master
        master_audio = np.array([])
        max_length = max((len(audio) for audio in processed_buses.values() if len(audio) > 0), default=0)
        
        if max_length > 0:
            master_audio = np.zeros(max_length)
            
            for bus_name, audio in processed_buses.items():
                if len(audio) > 0:
                    # Apply pan before summing to master
                    config = self.bus_configs.get(bus_name, BusConfig(name=bus_name))
                    audio_stereo = self._apply_pan(audio, config.pan)
                    
                    # Sum to master
                    if len(audio_stereo.shape) == 1:
                        master_audio[:len(audio_stereo)] += audio_stereo
                    else:
                        # Already stereo - take one channel for now
                        master_audio[:len(audio_stereo)] += audio_stereo[:, 0] if len(audio_stereo.shape) > 1 else audio_stereo
        
        if len(master_audio) == 0:
            return np.zeros((0, 2))
        
        # Convert to stereo if mono
        if len(master_audio.shape) == 1:
            master_audio = np.stack([master_audio, master_audio], axis=1)
        
        # Apply master processing
        master_audio = self.apply_master_processing(master_audio, master_config)
        
        # Normalize to target LUFS
        master_audio = self.normalize_to_lufs(master_audio, master_config.target_lufs)
        
        return master_audio
    
    def _apply_pan(self, audio: np.ndarray, pan: float) -> np.ndarray:
        """Apply panning to audio. Returns stereo."""
        # Constant power panning
        pan_norm = (pan + 1) / 2  # Convert -1..1 to 0..1
        left_gain = np.cos(pan_norm * np.pi / 2)
        right_gain = np.sin(pan_norm * np.pi / 2)
        
        left = audio * left_gain
        right = audio * right_gain
        
        return np.stack([left, right], axis=1)
    
    def apply_master_processing(
        self,
        audio: np.ndarray,
        config: MasterConfig
    ) -> np.ndarray:
        """Apply master bus processing (EQ, compression, limiting)."""
        if len(audio) == 0:
            return audio
        
        # Import EQ and compressor from track processor
        from multimodal_gen.track_processor import EQBand, CompressorConfig
        
        processor = TrackProcessor(self.sample_rate)
        
        # Process each channel separately
        is_stereo = len(audio.shape) > 1 and audio.shape[1] == 2
        
        if is_stereo:
            left = audio[:, 0]
            right = audio[:, 1]
        else:
            left = audio
            right = audio
        
        # Apply EQ if any bands are non-zero
        eq_bands = []
        if config.eq_low_db != 0.0:
            eq_bands.append(EQBand(frequency=100, gain_db=config.eq_low_db, band_type="low_shelf"))
        if config.eq_mid_db != 0.0:
            eq_bands.append(EQBand(frequency=1000, gain_db=config.eq_mid_db, q=2.0, band_type="peak"))
        if config.eq_high_db != 0.0:
            eq_bands.append(EQBand(frequency=8000, gain_db=config.eq_high_db, band_type="high_shelf"))
        
        if eq_bands:
            left = processor.apply_eq(left, eq_bands)
            right = processor.apply_eq(right, eq_bands)
        
        # Apply compression
        comp_config = CompressorConfig(
            threshold_db=config.compression_threshold_db,
            ratio=config.compression_ratio,
            attack_ms=10.0,
            release_ms=100.0,
            makeup_db=0.0
        )
        
        left = processor.compress(left, comp_config)
        right = processor.compress(right, comp_config)
        
        # Combine channels
        if is_stereo:
            processed = np.stack([left, right], axis=1)
        else:
            processed = left
        
        # Apply limiter - use True Peak Limiter if configured for streaming compliance
        if config.use_true_peak_limiter:
            processed = self.true_peak_limit(processed, config.true_peak_ceiling_dbtp)
        else:
            processed = self.limit(processed, config.limiter_ceiling_db)
        
        return processed
    
    def true_peak_limit(
        self,
        audio: np.ndarray,
        ceiling_dbtp: float = -1.0
    ) -> np.ndarray:
        """
        Apply True Peak Limiting with ISP detection.
        
        Uses the TruePeakLimiter class for professional-grade limiting
        following ITU-R BS.1770-4 standards. Recommended for streaming
        platform compliance (Spotify, Apple Music, YouTube).
        
        Args:
            audio: Input audio (stereo or mono)
            ceiling_dbtp: True peak ceiling in dBTP (default: -1.0)
        
        Returns:
            Limited audio with true peak at or below ceiling
        """
        from multimodal_gen.true_peak_limiter import TruePeakLimiter, TruePeakLimiterParams
        
        params = TruePeakLimiterParams(ceiling_dbtp=ceiling_dbtp)
        limiter = TruePeakLimiter(params, self.sample_rate)
        return limiter.process(audio)
    
    def check_true_peak_compliance(self, audio: np.ndarray) -> dict:
        """
        Check if audio meets streaming platform true peak requirements.
        
        Args:
            audio: Audio to check
        
        Returns:
            Dict with compliance status for various platforms
        """
        from multimodal_gen.true_peak_limiter import check_true_peak_compliance
        return check_true_peak_compliance(audio, ceiling_dbtp=-1.0)
    
    def limit(
        self,
        audio: np.ndarray,
        ceiling_db: float = -0.3
    ) -> np.ndarray:
        """Apply brickwall limiter."""
        ceiling_linear = 10 ** (ceiling_db / 20)
        
        # Simple but effective brickwall limiter
        is_stereo = len(audio.shape) > 1 and audio.shape[1] == 2
        
        if is_stereo:
            # Get max peak across both channels for each sample
            peak = np.max(np.abs(audio), axis=1)
        else:
            peak = np.abs(audio)
        
        # Calculate gain reduction needed
        gain = np.ones_like(peak)
        above_ceiling = peak > ceiling_linear
        
        if np.any(above_ceiling):
            gain[above_ceiling] = ceiling_linear / peak[above_ceiling]
        
        # Apply lookahead and smooth gain changes to avoid distortion
        # Use minimum gain in a small window (lookahead)
        lookahead_samples = 5
        smoothed_gain = np.copy(gain)
        
        for i in range(len(gain)):
            # Look ahead
            end_idx = min(i + lookahead_samples, len(gain))
            smoothed_gain[i] = np.min(gain[i:end_idx])
        
        # Apply simple smoothing to avoid clicks
        for i in range(1, len(smoothed_gain)):
            # Smooth release (attack should be fast)
            if smoothed_gain[i] > smoothed_gain[i-1]:
                smoothed_gain[i] = 0.95 * smoothed_gain[i-1] + 0.05 * smoothed_gain[i]
        
        # Apply gain reduction
        if is_stereo:
            result = audio * smoothed_gain[:, np.newaxis]
        else:
            result = audio * smoothed_gain
        
        # Final safety clip to ensure we never exceed ceiling
        result = np.clip(result, -ceiling_linear, ceiling_linear)
        
        return result
    
    def measure_lufs(self, audio: np.ndarray) -> float:
        """Measure integrated LUFS of audio."""
        if len(audio) == 0:
            return -70.0
        
        # Simplified LUFS measurement (K-weighted)
        # True LUFS requires ITU-R BS.1770 filters
        
        is_stereo = len(audio.shape) > 1 and audio.shape[1] == 2
        
        if is_stereo:
            # Average channels
            mono = np.mean(audio, axis=1)
        else:
            mono = audio
        
        # Apply high-pass filter (simplified K-weighting)
        # In a real implementation, we'd use proper ITU-R BS.1770 filters
        from scipy import signal
        
        # High-pass at 80Hz
        sos = signal.butter(2, 80, btype='high', fs=self.sample_rate, output='sos')
        filtered = signal.sosfilt(sos, mono)
        
        # Calculate mean square
        ms = np.mean(filtered ** 2)
        
        if ms > 0:
            return -0.691 + 10 * np.log10(ms)
        return -70.0
    
    def normalize_to_lufs(
        self,
        audio: np.ndarray,
        target_lufs: float = -14.0
    ) -> np.ndarray:
        """Normalize audio to target LUFS."""
        if len(audio) == 0:
            return audio
        
        current_lufs = self.measure_lufs(audio)
        
        if current_lufs > -70.0:
            gain_db = target_lufs - current_lufs
            gain_linear = 10 ** (gain_db / 20)
            return audio * gain_linear
        
        return audio
    
    def get_bus(self, name: str) -> Optional[MixBus]:
        """Get a bus by name."""
        return self.buses.get(name)
    
    def clear_all(self) -> None:
        """Clear all bus buffers."""
        for bus in self.buses.values():
            bus.clear()
        self.sidechains.clear()
    
    def get_mix_preset(self, genre: str) -> Dict[str, BusConfig]:
        """Get genre-specific mix preset."""
        return MIX_PRESETS.get(genre, {})


# Genre-specific mix presets
MIX_PRESETS: Dict[str, Dict[str, BusConfig]] = {
    "trap": {
        "kick": BusConfig("kick", sends={"reverb": 0.1}),
        "drums": BusConfig("drums", gain_db=1.0),
        "bass": BusConfig("bass", gain_db=2.0),  # Bass-heavy
        "melodic": BusConfig("melodic", sends={"reverb": 0.3, "delay": 0.2}),
    },
    "boom_bap": {
        "drums": BusConfig("drums", gain_db=2.0),  # Drums forward
        "bass": BusConfig("bass", gain_db=0.0),
        "melodic": BusConfig("melodic", sends={"reverb": 0.2}),
    },
    "lofi": {
        "drums": BusConfig("drums", gain_db=-1.0),  # Softer drums
        "melodic": BusConfig("melodic", gain_db=1.0, sends={"reverb": 0.4}),
    },
    "house": {
        "kick": BusConfig("kick", gain_db=2.0),  # Four-on-floor kick
        "bass": BusConfig("bass"),  # Sidechain will duck this
        "melodic": BusConfig("melodic", sends={"reverb": 0.3}),
    },
}

# Default sidechain configurations per genre
GENRE_SIDECHAINS: Dict[str, List[SidechainConfig]] = {
    "trap": [
        SidechainConfig("kick", "bass", depth=0.4, release_ms=80),
    ],
    "house": [
        SidechainConfig("kick", "bass", depth=0.7, release_ms=150),
        SidechainConfig("kick", "melodic", depth=0.3, release_ms=100),
    ],
    "edm": [
        SidechainConfig("kick", "bass", depth=0.8, release_ms=200),
        SidechainConfig("kick", "melodic", depth=0.5, release_ms=150),
    ],
}


# Convenience functions
def create_mix(
    stems: Dict[str, np.ndarray],
    genre: str = "trap",
    sample_rate: int = 44100
) -> np.ndarray:
    """
    Create a mixed master from stems using genre preset.
    
    Args:
        stems: Dict mapping bus names to audio arrays
        genre: Genre for mix preset
        sample_rate: Sample rate
        
    Returns:
        Mixed and mastered stereo audio
    """
    engine = MixEngine(sample_rate=sample_rate)
    
    # Add stems to appropriate buses
    for bus_name, audio in stems.items():
        engine.add_to_bus(bus_name, audio)
    
    # Apply genre preset
    preset = engine.get_mix_preset(genre)
    for bus_name, config in preset.items():
        engine.set_bus_config(bus_name, config)
    
    # Apply genre sidechains
    sidechains = GENRE_SIDECHAINS.get(genre, [])
    for sidechain in sidechains:
        engine.add_sidechain(sidechain)
    
    # Mix
    return engine.mix()


def apply_sidechain_compression(
    source: np.ndarray,
    trigger: np.ndarray,
    depth: float = 0.5,
    attack_ms: float = 5.0,
    release_ms: float = 100.0,
    sample_rate: int = 44100
) -> np.ndarray:
    """
    Standalone sidechain compression function.
    
    Args:
        source: Audio to duck
        trigger: Audio that triggers ducking
        depth: Amount of ducking (0-1)
        attack_ms: Attack time
        release_ms: Release time
        sample_rate: Sample rate
        
    Returns:
        Sidechained audio
    """
    engine = MixEngine(sample_rate=sample_rate)
    config = SidechainConfig(
        trigger_bus="trigger",
        target_bus="target",
        threshold_db=-20.0,
        ratio=4.0,
        attack_ms=attack_ms,
        release_ms=release_ms,
        depth=depth
    )
    
    return engine.apply_sidechain(source, trigger, config)
