"""
Track Processing Chain - CPU-efficient audio processing for individual tracks.

Provides saturation, EQ, compression, and transient shaping to make
rendered audio sound more professional and polished.
"""

from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional
import numpy as np


@dataclass
class EQBand:
    """Single EQ band configuration."""
    frequency: float        # Center/corner frequency in Hz
    gain_db: float = 0.0    # Gain in dB (-24 to +24)
    q: float = 1.0          # Q factor (0.1 to 10, only for parametric)
    band_type: str = "peak" # "peak", "low_shelf", "high_shelf", "lowpass", "highpass"


@dataclass
class CompressorConfig:
    """Compressor configuration."""
    threshold_db: float = -12.0    # Threshold in dB
    ratio: float = 4.0             # Compression ratio (1:1 to inf:1)
    attack_ms: float = 10.0        # Attack time in ms
    release_ms: float = 100.0      # Release time in ms
    makeup_db: float = 0.0         # Makeup gain in dB
    knee_db: float = 0.0           # Soft knee width in dB (0 = hard knee)


@dataclass
class TransientConfig:
    """Transient shaper configuration."""
    attack: float = 0.0     # Attack enhancement (-100 to +100)
    sustain: float = 0.0    # Sustain enhancement (-100 to +100)


@dataclass 
class TrackProcessorConfig:
    """Full track processing configuration."""
    saturation_drive: float = 1.0           # Saturation amount (1.0 = none, 3.0 = heavy)
    eq_bands: List[EQBand] = None           # EQ bands to apply
    compressor: CompressorConfig = None      # Compressor settings
    transient: TransientConfig = None        # Transient shaper settings
    output_gain_db: float = 0.0             # Final output gain


class TrackProcessor:
    """
    CPU-efficient audio processing chain for individual tracks.
    
    Processing order: Input → Saturation → EQ → Compression → Transient → Output Gain
    
    Usage:
        processor = TrackProcessor(sample_rate=44100)
        processed = processor.process(audio, config)
        
        # Or use presets
        processed = processor.process_with_preset(audio, "trap_808")
    """
    
    def __init__(self, sample_rate: int = 44100):
        self.sample_rate = sample_rate
    
    def process(
        self,
        audio: np.ndarray,
        config: TrackProcessorConfig
    ) -> np.ndarray:
        """
        Apply full processing chain to audio.
        
        Args:
            audio: Input audio (mono or stereo, float32 -1 to 1)
            config: Processing configuration
            
        Returns:
            Processed audio (same shape as input)
        """
        if len(audio) == 0:
            return audio
        
        # Copy to avoid modifying input
        processed = audio.copy()
        
        # 1. Saturation
        if config.saturation_drive > 1.0:
            processed = self.soft_saturate(processed, config.saturation_drive)
        
        # 2. EQ
        if config.eq_bands:
            processed = self.apply_eq(processed, config.eq_bands)
        
        # 3. Compression
        if config.compressor:
            processed = self.compress(processed, config.compressor)
        
        # 4. Transient shaping
        if config.transient:
            processed = self.shape_transients(processed, config.transient)
        
        # 5. Output gain
        if config.output_gain_db != 0.0:
            processed = self.apply_gain(processed, config.output_gain_db)
        
        # 6. Final safety limiter to prevent clipping
        # Soft clip any peaks above 0.99
        peak = np.max(np.abs(processed))
        if peak > 0.99:
            # Apply soft limiting
            processed = processed * (0.99 / peak)
        
        return processed
    
    def soft_saturate(
        self,
        audio: np.ndarray,
        drive: float = 2.0
    ) -> np.ndarray:
        """
        Apply warm saturation using tanh waveshaping.
        
        Args:
            audio: Input audio
            drive: Saturation amount (1.0 = subtle, 4.0 = heavy)
            
        Returns:
            Saturated audio (normalized to prevent clipping)
        """
        if drive <= 1.0:
            return audio
        
        # Apply tanh saturation
        # Scale input to get desired saturation curve
        saturated = np.tanh(audio * drive)
        
        # Compensate gain to maintain approximate level
        # Since tanh(x) asymptotes to ±1, we need to scale output
        # to prevent clipping while maintaining musical saturation
        compensation = 0.95 / np.tanh(drive)  # 0.95 to leave headroom
        saturated = saturated * compensation
        
        # Final safety clip to ensure no clipping
        saturated = np.clip(saturated, -0.99, 0.99)
        
        return saturated
    
    def apply_eq(
        self,
        audio: np.ndarray,
        bands: List[EQBand]
    ) -> np.ndarray:
        """
        Apply multi-band EQ using biquad filters.
        
        Args:
            audio: Input audio
            bands: List of EQ bands to apply
            
        Returns:
            EQ'd audio
        """
        processed = audio
        for band in bands:
            processed = self.apply_biquad(processed, band)
        return processed
    
    def apply_biquad(
        self,
        audio: np.ndarray,
        band: EQBand
    ) -> np.ndarray:
        """
        Apply single biquad filter.
        
        Implements standard biquad filter types:
        - Peak/parametric EQ
        - Low shelf
        - High shelf
        - Lowpass
        - Highpass
        """
        # Calculate biquad coefficients based on band type
        w0 = 2 * np.pi * band.frequency / self.sample_rate
        cos_w0 = np.cos(w0)
        sin_w0 = np.sin(w0)
        
        A = 10 ** (band.gain_db / 40)  # Square root of gain
        alpha = sin_w0 / (2 * band.q)
        
        # Initialize coefficients
        b0, b1, b2 = 1.0, 0.0, 0.0
        a0, a1, a2 = 1.0, 0.0, 0.0
        
        if band.band_type == "peak":
            # Peaking EQ
            b0 = 1 + alpha * A
            b1 = -2 * cos_w0
            b2 = 1 - alpha * A
            a0 = 1 + alpha / A
            a1 = -2 * cos_w0
            a2 = 1 - alpha / A
            
        elif band.band_type == "low_shelf":
            # Low shelf
            b0 = A * ((A + 1) - (A - 1) * cos_w0 + 2 * np.sqrt(A) * alpha)
            b1 = 2 * A * ((A - 1) - (A + 1) * cos_w0)
            b2 = A * ((A + 1) - (A - 1) * cos_w0 - 2 * np.sqrt(A) * alpha)
            a0 = (A + 1) + (A - 1) * cos_w0 + 2 * np.sqrt(A) * alpha
            a1 = -2 * ((A - 1) + (A + 1) * cos_w0)
            a2 = (A + 1) + (A - 1) * cos_w0 - 2 * np.sqrt(A) * alpha
            
        elif band.band_type == "high_shelf":
            # High shelf
            b0 = A * ((A + 1) + (A - 1) * cos_w0 + 2 * np.sqrt(A) * alpha)
            b1 = -2 * A * ((A - 1) + (A + 1) * cos_w0)
            b2 = A * ((A + 1) + (A - 1) * cos_w0 - 2 * np.sqrt(A) * alpha)
            a0 = (A + 1) - (A - 1) * cos_w0 + 2 * np.sqrt(A) * alpha
            a1 = 2 * ((A - 1) - (A + 1) * cos_w0)
            a2 = (A + 1) - (A - 1) * cos_w0 - 2 * np.sqrt(A) * alpha
            
        elif band.band_type == "lowpass":
            # Lowpass filter
            b0 = (1 - cos_w0) / 2
            b1 = 1 - cos_w0
            b2 = (1 - cos_w0) / 2
            a0 = 1 + alpha
            a1 = -2 * cos_w0
            a2 = 1 - alpha
            
        elif band.band_type == "highpass":
            # Highpass filter
            b0 = (1 + cos_w0) / 2
            b1 = -(1 + cos_w0)
            b2 = (1 + cos_w0) / 2
            a0 = 1 + alpha
            a1 = -2 * cos_w0
            a2 = 1 - alpha
        else:
            # Unknown type, return unprocessed
            return audio
        
        # Normalize coefficients
        b0 /= a0
        b1 /= a0
        b2 /= a0
        a1 /= a0
        a2 /= a0
        
        # Apply filter using direct form I
        return self._apply_biquad_filter(audio, b0, b1, b2, a1, a2)
    
    def _apply_biquad_filter(
        self,
        audio: np.ndarray,
        b0: float, b1: float, b2: float,
        a1: float, a2: float
    ) -> np.ndarray:
        """Apply biquad filter with given coefficients."""
        # Handle stereo
        if len(audio.shape) > 1:
            output = np.zeros_like(audio)
            for ch in range(audio.shape[1]):
                output[:, ch] = self._filter_mono(audio[:, ch], b0, b1, b2, a1, a2)
            return output
        else:
            return self._filter_mono(audio, b0, b1, b2, a1, a2)
    
    def _filter_mono(
        self,
        audio: np.ndarray,
        b0: float, b1: float, b2: float,
        a1: float, a2: float
    ) -> np.ndarray:
        """Apply biquad filter to mono audio."""
        output = np.zeros_like(audio)
        x1, x2 = 0.0, 0.0
        y1, y2 = 0.0, 0.0
        
        for i in range(len(audio)):
            x0 = audio[i]
            y0 = b0 * x0 + b1 * x1 + b2 * x2 - a1 * y1 - a2 * y2
            
            # Update states
            x2, x1 = x1, x0
            y2, y1 = y1, y0
            output[i] = y0
        
        return output
    
    def compress(
        self,
        audio: np.ndarray,
        config: CompressorConfig
    ) -> np.ndarray:
        """
        Apply dynamic range compression with envelope follower.
        
        Features:
        - Configurable attack/release
        - Soft knee option
        - Makeup gain
        - RMS or peak detection
        
        Args:
            audio: Input audio
            config: Compressor configuration
            
        Returns:
            Compressed audio
        """
        # Convert to mono for detection
        if len(audio.shape) > 1:
            detect = np.mean(np.abs(audio), axis=1)
        else:
            detect = np.abs(audio)
        
        # RMS detection (more musical than peak)
        window_size = int(0.01 * self.sample_rate)  # 10ms window
        if window_size > 0:
            # Simple moving average for RMS
            detect_squared = detect ** 2
            # Pad for convolution
            padded = np.pad(detect_squared, (window_size // 2, window_size // 2), mode='edge')
            rms = np.sqrt(np.convolve(padded, np.ones(window_size) / window_size, mode='valid'))
            detect = rms[:len(detect)]
        
        # Convert to dB
        detect_db = 20 * np.log10(detect + 1e-10)
        
        # Calculate gain reduction
        threshold = config.threshold_db
        ratio = config.ratio
        knee = config.knee_db
        
        gain_db = np.zeros_like(detect_db)
        
        for i in range(len(detect_db)):
            level = detect_db[i]
            
            if knee > 0:
                # Soft knee
                if level < (threshold - knee / 2):
                    # Below knee
                    gain_db[i] = 0
                elif level > (threshold + knee / 2):
                    # Above knee
                    excess = level - threshold
                    gain_db[i] = excess * (1 - 1 / ratio)
                else:
                    # In knee
                    excess = level - threshold + knee / 2
                    gain_db[i] = excess ** 2 / (2 * knee) * (1 - 1 / ratio)
            else:
                # Hard knee
                if level > threshold:
                    excess = level - threshold
                    gain_db[i] = excess * (1 - 1 / ratio)
        
        # Apply attack/release envelope
        attack_coeff = np.exp(-1.0 / (config.attack_ms * self.sample_rate / 1000.0))
        release_coeff = np.exp(-1.0 / (config.release_ms * self.sample_rate / 1000.0))
        
        smoothed_gain_db = np.zeros_like(gain_db)
        envelope = 0.0
        
        for i in range(len(gain_db)):
            target = gain_db[i]
            
            if target > envelope:
                # Attack (gain reduction increasing)
                coeff = attack_coeff
            else:
                # Release (gain reduction decreasing)
                coeff = release_coeff
            
            envelope = coeff * envelope + (1 - coeff) * target
            smoothed_gain_db[i] = envelope
        
        # Convert to linear gain
        gain_linear = 10 ** (-smoothed_gain_db / 20)
        
        # Apply makeup gain
        makeup_gain = 10 ** (config.makeup_db / 20)
        gain_linear *= makeup_gain
        
        # Apply to audio
        if len(audio.shape) > 1:
            return audio * gain_linear[:, np.newaxis]
        else:
            return audio * gain_linear
    
    def shape_transients(
        self,
        audio: np.ndarray,
        config: TransientConfig
    ) -> np.ndarray:
        """
        Shape transients for punch control.
        
        Args:
            audio: Input audio
            config: Transient configuration (-100 to +100 for attack/sustain)
            
        Returns:
            Transient-shaped audio
        """
        if config.attack == 0 and config.sustain == 0:
            return audio
        
        # Detect transients using envelope follower
        if len(audio.shape) > 1:
            mono = np.mean(np.abs(audio), axis=1)
        else:
            mono = np.abs(audio)
        
        # Fast and slow envelopes
        fast_attack = 0.001  # 1ms
        slow_attack = 0.050  # 50ms
        
        fast_coeff = np.exp(-1.0 / (fast_attack * self.sample_rate))
        slow_coeff = np.exp(-1.0 / (slow_attack * self.sample_rate))
        
        fast_env = np.zeros_like(mono)
        slow_env = np.zeros_like(mono)
        
        fast_state = 0.0
        slow_state = 0.0
        
        for i in range(len(mono)):
            # Fast envelope (tracks transients)
            fast_state = max(mono[i], fast_coeff * fast_state)
            fast_env[i] = fast_state
            
            # Slow envelope (tracks sustain)
            slow_state = max(mono[i], slow_coeff * slow_state)
            slow_env[i] = slow_state
        
        # Transient signal is difference between fast and slow
        transient = fast_env - slow_env
        transient = np.clip(transient, 0, None)
        
        # Sustain is the slow envelope
        sustain = slow_env
        
        # Apply enhancement
        attack_gain = 1.0 + (config.attack / 100.0)  # -100 to +100 -> 0 to 2
        sustain_gain = 1.0 + (config.sustain / 100.0)
        
        # Create gain curve
        transient_normalized = transient / (transient.max() + 1e-10)
        sustain_normalized = sustain / (sustain.max() + 1e-10)
        
        # Mix of transient and sustain gains
        gain = (transient_normalized * attack_gain + 
                sustain_normalized * sustain_gain) / 2
        
        # Smooth to avoid clicks
        gain = np.maximum(gain, 0.5)  # Don't reduce below 50%
        
        # Apply to audio
        if len(audio.shape) > 1:
            return audio * gain[:, np.newaxis]
        else:
            return audio * gain
    
    def apply_gain(
        self,
        audio: np.ndarray,
        gain_db: float
    ) -> np.ndarray:
        """Apply gain in dB."""
        linear_gain = 10 ** (gain_db / 20)
        return audio * linear_gain
    
    def process_with_preset(
        self,
        audio: np.ndarray,
        preset_name: str
    ) -> np.ndarray:
        """
        Process audio using a named preset.
        
        Args:
            audio: Input audio
            preset_name: Name of preset (e.g., "trap_808", "lofi_keys")
            
        Returns:
            Processed audio
        """
        config = self.get_preset(preset_name)
        if config is None:
            raise ValueError(f"Unknown preset: {preset_name}")
        return self.process(audio, config)
    
    def get_preset(self, name: str) -> TrackProcessorConfig:
        """Get a processing preset by name."""
        return TRACK_PRESETS.get(name)


# Track processing presets for different instrument types
TRACK_PRESETS: Dict[str, TrackProcessorConfig] = {
    # Bass presets
    "trap_808": TrackProcessorConfig(
        saturation_drive=3.0,
        eq_bands=[
            EQBand(frequency=60, gain_db=3.0, band_type="low_shelf"),
            EQBand(frequency=200, gain_db=-2.0, q=2.0, band_type="peak"),
        ],
        compressor=CompressorConfig(threshold_db=-12, ratio=4.0, attack_ms=5, release_ms=80),
        output_gain_db=0.0
    ),
    "boom_bap_bass": TrackProcessorConfig(
        saturation_drive=2.0,
        eq_bands=[
            EQBand(frequency=80, gain_db=2.0, band_type="low_shelf"),
            EQBand(frequency=800, gain_db=-3.0, q=1.5, band_type="peak"),
        ],
        compressor=CompressorConfig(threshold_db=-15, ratio=3.0, attack_ms=10, release_ms=100),
    ),
    
    # Drum presets
    "trap_hihat": TrackProcessorConfig(
        saturation_drive=1.2,
        eq_bands=[
            EQBand(frequency=400, gain_db=-4.0, band_type="highpass"),
            EQBand(frequency=10000, gain_db=2.0, band_type="high_shelf"),
        ],
        compressor=CompressorConfig(threshold_db=-18, ratio=2.0, attack_ms=1, release_ms=50),
    ),
    "boom_bap_drums": TrackProcessorConfig(
        saturation_drive=1.5,
        eq_bands=[
            EQBand(frequency=100, gain_db=2.0, band_type="low_shelf"),
            EQBand(frequency=3000, gain_db=2.0, q=2.0, band_type="peak"),
        ],
        compressor=CompressorConfig(threshold_db=-10, ratio=6.0, attack_ms=3, release_ms=80),
        transient=TransientConfig(attack=30, sustain=0),
    ),
    "punchy_kick": TrackProcessorConfig(
        saturation_drive=2.0,
        eq_bands=[
            EQBand(frequency=60, gain_db=3.0, band_type="peak", q=2.0),
            EQBand(frequency=3500, gain_db=4.0, band_type="peak", q=3.0),
        ],
        compressor=CompressorConfig(threshold_db=-8, ratio=4.0, attack_ms=2, release_ms=60),
        transient=TransientConfig(attack=40, sustain=-10),
    ),
    "snare_crack": TrackProcessorConfig(
        saturation_drive=1.8,
        eq_bands=[
            EQBand(frequency=200, gain_db=2.0, band_type="peak", q=2.0),
            EQBand(frequency=5000, gain_db=3.0, band_type="high_shelf"),
        ],
        compressor=CompressorConfig(threshold_db=-12, ratio=4.0, attack_ms=1, release_ms=100),
        transient=TransientConfig(attack=20, sustain=0),
    ),
    
    # Keys/Synth presets
    "lofi_keys": TrackProcessorConfig(
        saturation_drive=1.5,
        eq_bands=[
            EQBand(frequency=8000, gain_db=-4.0, band_type="high_shelf"),
            EQBand(frequency=300, gain_db=2.0, q=1.0, band_type="peak"),
        ],
        compressor=CompressorConfig(threshold_db=-15, ratio=2.0, attack_ms=20, release_ms=200),
    ),
    "bright_synth": TrackProcessorConfig(
        saturation_drive=1.3,
        eq_bands=[
            EQBand(frequency=2000, gain_db=2.0, q=1.5, band_type="peak"),
            EQBand(frequency=10000, gain_db=3.0, band_type="high_shelf"),
        ],
        compressor=CompressorConfig(threshold_db=-12, ratio=3.0, attack_ms=5, release_ms=100),
    ),
    "warm_pad": TrackProcessorConfig(
        saturation_drive=1.8,
        eq_bands=[
            EQBand(frequency=200, gain_db=2.0, band_type="low_shelf"),
            EQBand(frequency=6000, gain_db=-2.0, band_type="high_shelf"),
        ],
        compressor=CompressorConfig(threshold_db=-20, ratio=2.0, attack_ms=30, release_ms=300),
    ),
    
    # Vocal presets
    "vocal_presence": TrackProcessorConfig(
        saturation_drive=1.2,
        eq_bands=[
            EQBand(frequency=100, gain_db=0, band_type="highpass"),
            EQBand(frequency=3000, gain_db=3.0, q=2.0, band_type="peak"),
            EQBand(frequency=12000, gain_db=2.0, band_type="high_shelf"),
        ],
        compressor=CompressorConfig(threshold_db=-15, ratio=4.0, attack_ms=5, release_ms=80),
    ),
    
    # Additional presets to reach 10+
    "clean_bass": TrackProcessorConfig(
        saturation_drive=1.1,
        eq_bands=[
            EQBand(frequency=50, gain_db=2.0, band_type="low_shelf"),
            EQBand(frequency=150, gain_db=-1.0, q=1.0, band_type="peak"),
        ],
        compressor=CompressorConfig(threshold_db=-18, ratio=2.5, attack_ms=15, release_ms=120),
    ),
    "crisp_snare": TrackProcessorConfig(
        saturation_drive=1.4,
        eq_bands=[
            EQBand(frequency=180, gain_db=1.5, band_type="peak", q=1.5),
            EQBand(frequency=8000, gain_db=3.5, band_type="high_shelf"),
        ],
        compressor=CompressorConfig(threshold_db=-10, ratio=5.0, attack_ms=1, release_ms=70),
        transient=TransientConfig(attack=25, sustain=-5),
    ),
    "fat_kick": TrackProcessorConfig(
        saturation_drive=2.5,
        eq_bands=[
            EQBand(frequency=55, gain_db=4.0, band_type="peak", q=1.8),
            EQBand(frequency=2500, gain_db=2.5, band_type="peak", q=2.5),
        ],
        compressor=CompressorConfig(threshold_db=-9, ratio=5.0, attack_ms=3, release_ms=65),
        transient=TransientConfig(attack=35, sustain=-15),
    ),
}


# Convenience function
def process_track(
    audio: np.ndarray,
    preset: str,
    sample_rate: int = 44100
) -> np.ndarray:
    """
    Process audio using a named preset.
    
    Args:
        audio: Input audio array
        preset: Preset name (e.g., "trap_808", "lofi_keys")
        sample_rate: Sample rate in Hz
        
    Returns:
        Processed audio
    """
    processor = TrackProcessor(sample_rate)
    return processor.process_with_preset(audio, preset)
