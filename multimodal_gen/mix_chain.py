"""
Mix Chain Module

Defines audio effect chains for mixing and mastering.
Provides a structured way to apply series of effects to audio buffers.
"""

import numpy as np
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Union, Callable, Tuple
from enum import Enum
import math

from .utils import SAMPLE_RATE

# =============================================================================
# EFFECT TYPES
# =============================================================================

class EffectType(Enum):
    EQ_3BAND = "eq_3band"
    PARAMETRIC_EQ = "parametric_eq"  # Multi-band parametric EQ (RBJ cookbook)
    DYNAMIC_EQ = "dynamic_eq"  # Per-band compression/expansion
    COMPRESSOR = "compressor"
    REVERB = "reverb"
    DELAY = "delay"
    SATURATION = "saturation"
    HARMONIC_EXCITER = "harmonic_exciter"  # Multiband harmonic generation
    LIMITER = "limiter"
    TRUE_PEAK_LIMITER = "true_peak_limiter"  # ISP-aware limiter per ITU-R BS.1770-4
    TRANSIENT_SHAPER = "transient_shaper"  # Differential envelope transient shaping
    RESONANCE_SUPPRESSION = "resonance_suppression"  # Auto resonance detection/removal
    GAIN = "gain"
    PAN = "pan"
    STEREO_WIDTH = "stereo_width"

@dataclass
class EffectParams:
    """Base class for effect parameters."""
    enabled: bool = True
    mix: float = 1.0  # Wet/Dry mix (0.0 - 1.0)

@dataclass
class EQ3BandParams(EffectParams):
    low_gain_db: float = 0.0
    mid_gain_db: float = 0.0
    high_gain_db: float = 0.0
    low_freq: float = 200.0
    mid_freq: float = 1000.0
    high_freq: float = 5000.0


@dataclass
class ParametricEQBand:
    """Single band for parametric EQ."""
    filter_type: str = "peak"  # peak, low_shelf, high_shelf, lowpass, highpass, notch
    frequency: float = 1000.0
    gain_db: float = 0.0
    q: float = 1.0
    enabled: bool = True


@dataclass
class ParametricEQParams(EffectParams):
    """Multi-band parametric EQ using RBJ cookbook biquads."""
    bands: list = None  # List of ParametricEQBand or dicts
    output_gain_db: float = 0.0
    
    def __post_init__(self):
        if self.bands is None:
            # Default 4-band semi-parametric
            self.bands = [
                {'type': 'low_shelf', 'frequency': 100, 'gain_db': 0, 'q': 0.7},
                {'type': 'peak', 'frequency': 500, 'gain_db': 0, 'q': 1.0},
                {'type': 'peak', 'frequency': 2000, 'gain_db': 0, 'q': 1.0},
                {'type': 'high_shelf', 'frequency': 8000, 'gain_db': 0, 'q': 0.7},
            ]


@dataclass
class DynamicEQParams(EffectParams):
    """Dynamic EQ band - frequency-selective compression/expansion."""
    frequency: float = 3000.0      # Center frequency (Hz)
    q: float = 2.0                  # Bandwidth
    threshold_db: float = -20.0     # Activation threshold
    ratio: float = 4.0              # Compression ratio
    attack_ms: float = 10.0
    release_ms: float = 100.0
    max_gain_db: float = -12.0      # Max cut (negative) or boost (positive)
    mode: str = "compress"          # "compress" or "expand"


@dataclass
class HarmonicExciterParams(EffectParams):
    """Multiband harmonic exciter for warmth and presence."""
    even_harmonics: float = 0.3    # 0-1, amount of 2nd/4th harmonics
    odd_harmonics: float = 0.2     # 0-1, amount of 3rd/5th harmonics
    low_drive: float = 0.0         # Drive for <200 Hz
    mid_drive: float = 0.2         # Drive for 200-2000 Hz
    high_drive: float = 0.3        # Drive for 2-8 kHz
    air_drive: float = 0.4         # Drive for >8 kHz
    air_freq: float = 8000.0       # Air band cutoff


@dataclass
class ResonanceSuppressionParams(EffectParams):
    """Automatic resonance detection and suppression."""
    sensitivity: float = 0.5       # 0-1, detection sensitivity
    frequency_range_low: float = 100.0
    frequency_range_high: float = 10000.0
    max_reduction_db: float = -12.0
    attack_ms: float = 5.0
    release_ms: float = 50.0
    max_bands: int = 8

@dataclass
class CompressorParams(EffectParams):
    threshold_db: float = -20.0
    ratio: float = 4.0
    attack_ms: float = 10.0
    release_ms: float = 100.0
    makeup_gain_db: float = 0.0
    knee_width_db: float = 6.0

@dataclass
class ReverbParams(EffectParams):
    room_size: float = 0.5  # 0.0 - 1.0
    damping: float = 0.5    # 0.0 - 1.0
    width: float = 1.0      # 0.0 - 1.0
    wet_level: float = 0.3  # 0.0 - 1.0 (independent of mix)

@dataclass
class DelayParams(EffectParams):
    time_ms: float = 250.0
    feedback: float = 0.3
    mix: float = 0.3

@dataclass
class SaturationParams(EffectParams):
    drive: float = 0.5  # 0.0 - 1.0
    type: str = "soft"  # "soft", "hard", "tube"

@dataclass
class StereoWidthParams(EffectParams):
    """Mid-Side stereo width control parameters."""
    width: float = 1.0      # 0.0 = mono, 1.0 = original, 2.0 = extra wide
    mid_gain_db: float = 0.0   # Mid channel gain
    side_gain_db: float = 0.0  # Side channel gain
    mono_below_hz: float = 0.0 # Make frequencies below this mono (bass focus)

# =============================================================================
# DSP IMPLEMENTATIONS
# =============================================================================

class DSP:
    """Digital Signal Processing algorithms."""
    
    @staticmethod
    def apply_gain(audio: np.ndarray, gain_db: float) -> np.ndarray:
        """Apply gain in dB."""
        linear_gain = 10 ** (gain_db / 20)
        return audio * linear_gain

    @staticmethod
    def apply_pan(audio: np.ndarray, pan: float) -> np.ndarray:
        """Apply stereo panning (-1.0 to 1.0)."""
        # Ensure input is stereo
        if len(audio.shape) == 1:
            left = audio
            right = audio
        else:
            left = audio[:, 0]
            right = audio[:, 1]
            
        # Constant power panning
        pan_norm = (pan + 1) / 2  # 0 to 1
        left_gain = np.cos(pan_norm * np.pi / 2)
        right_gain = np.sin(pan_norm * np.pi / 2)
        
        return np.column_stack([left * left_gain, right * right_gain])

    @staticmethod
    def ms_encode(left: np.ndarray, right: np.ndarray) -> tuple:
        """Encode L/R to Mid/Side."""
        mid = (left + right) * 0.5
        side = (left - right) * 0.5
        return mid, side
    
    @staticmethod
    def ms_decode(mid: np.ndarray, side: np.ndarray) -> tuple:
        """Decode Mid/Side back to L/R."""
        left = mid + side
        right = mid - side
        return left, right
    
    @staticmethod
    def stereo_width(audio: np.ndarray, params: 'StereoWidthParams', sample_rate: int) -> np.ndarray:
        """Apply M/S stereo width processing."""
        # Ensure stereo
        if len(audio.shape) == 1:
            # Mono input - no width processing meaningful
            return np.column_stack([audio, audio])
        
        left = audio[:, 0]
        right = audio[:, 1]
        
        # Encode to M/S
        mid, side = DSP.ms_encode(left, right)
        
        # Apply mid/side gains
        mid_gain = 10 ** (params.mid_gain_db / 20)
        side_gain = 10 ** (params.side_gain_db / 20)
        
        mid = mid * mid_gain
        side = side * side_gain
        
        # Apply width (multiply side by width factor)
        # width=0: mono, width=1: original, width=2: double side
        side = side * params.width
        
        # Mono bass (optional low frequency mono)
        if params.mono_below_hz > 0:
            try:
                from scipy.signal import butter, lfilter
                # Design lowpass filter
                nyquist = sample_rate / 2
                cutoff_norm = min(params.mono_below_hz / nyquist, 0.99)
                b, a = butter(2, cutoff_norm, btype='low')
                
                # Extract bass from side and remove it (make it mono)
                bass_side = lfilter(b, a, side)
                side = side - bass_side  # Remove bass from side = bass becomes mono
            except ImportError:
                pass  # Skip if scipy not available
        
        # Decode back to L/R
        left_out, right_out = DSP.ms_decode(mid, side)
        
        return np.column_stack([left_out, right_out])

    @staticmethod
    def biquad_filter(audio: np.ndarray, b: List[float], a: List[float]) -> np.ndarray:
        """Apply biquad filter using scipy.signal.lfilter equivalent."""
        # Simple direct form I implementation if scipy not available
        # y[n] = b0*x[n] + b1*x[n-1] + b2*x[n-2] - a1*y[n-1] - a2*y[n-2]
        
        # For performance, we really should use scipy or numpy convolution
        # But for a pure python fallback (slow):
        try:
            from scipy.signal import lfilter
            # Handle stereo
            if len(audio.shape) > 1:
                out = np.zeros_like(audio)
                for i in range(audio.shape[1]):
                    out[:, i] = lfilter(b, a, audio[:, i])
                return out
            return lfilter(b, a, audio)
        except ImportError:
            # Very slow fallback, maybe warn user
            # For now, return audio unprocessed to avoid hanging
            print("Warning: scipy not found, skipping filter")
            return audio

    @staticmethod
    def eq_3band(audio: np.ndarray, params: EQ3BandParams, sample_rate: int) -> np.ndarray:
        """Apply 3-band EQ using biquad filters (RBJ cookbook)."""
        from .parametric_eq import apply_3band_eq
        
        return apply_3band_eq(
            audio,
            low_gain_db=params.low_gain_db,
            mid_gain_db=params.mid_gain_db,
            high_gain_db=params.high_gain_db,
            low_freq=params.low_freq,
            high_freq=params.high_freq,
            sample_rate=sample_rate
        )

    @staticmethod
    def parametric_eq(audio: np.ndarray, params: 'ParametricEQParams', sample_rate: int) -> np.ndarray:
        """
        Apply multi-band parametric EQ.
        
        Uses RBJ Audio EQ Cookbook biquad coefficients for professional-grade
        parametric equalization.
        """
        from .parametric_eq import apply_parametric_eq
        
        output = apply_parametric_eq(audio, params.bands, sample_rate)
        
        # Apply output gain
        if params.output_gain_db != 0.0:
            gain = 10 ** (params.output_gain_db / 20)
            output = output * gain
        
        # Mix control
        if params.mix < 1.0:
            output = audio * (1 - params.mix) + output * params.mix
        
        return output

    @staticmethod
    def dynamic_eq(audio: np.ndarray, params: 'DynamicEQParams', sample_rate: int) -> np.ndarray:
        """
        Apply dynamic EQ - frequency-selective compression.
        
        Combines parametric EQ with dynamics processing for surgical
        control of problem frequencies.
        """
        from .parametric_eq import DynamicEQBand, DynamicEQBandParams, DynamicMode
        
        dynamic_params = DynamicEQBandParams(
            enabled=params.enabled,
            frequency=params.frequency,
            q=params.q,
            threshold_db=params.threshold_db,
            ratio=params.ratio,
            attack_ms=params.attack_ms,
            release_ms=params.release_ms,
            max_gain_db=params.max_gain_db,
            mode=DynamicMode[params.mode.upper()]
        )
        
        band = DynamicEQBand(dynamic_params, sample_rate)
        output = band.process(audio)
        
        # Mix control
        if params.mix < 1.0:
            output = audio * (1 - params.mix) + output * params.mix
        
        return output

    @staticmethod
    def harmonic_exciter(audio: np.ndarray, params: 'HarmonicExciterParams', sample_rate: int) -> np.ndarray:
        """
        Apply harmonic exciter for warmth and presence.
        
        Generates harmonics using Chebyshev polynomials and multiband
        saturation for tube-like warmth and air enhancement.
        """
        from .parametric_eq import HarmonicExciter, ExciterParams as PEQExciterParams
        
        exciter_params = PEQExciterParams(
            enabled=params.enabled,
            mix=params.mix,
            even_harmonics=params.even_harmonics,
            odd_harmonics=params.odd_harmonics,
            low_drive=params.low_drive,
            mid_drive=params.mid_drive,
            high_drive=params.high_drive,
            air_drive=params.air_drive,
            air_freq=params.air_freq
        )
        
        exciter = HarmonicExciter(exciter_params, sample_rate)
        return exciter.process(audio)

    @staticmethod
    def resonance_suppression(audio: np.ndarray, params: 'ResonanceSuppressionParams', sample_rate: int) -> np.ndarray:
        """
        Apply automatic resonance detection and suppression.
        
        Analyzes spectrum for narrow peaks (resonances) and applies
        adaptive notch filters. Similar to Soothe2 style processing.
        """
        from .parametric_eq import ResonanceSuppressor, ResonanceSuppressionParams as PEQResParams
        
        res_params = PEQResParams(
            enabled=params.enabled,
            sensitivity=params.sensitivity,
            frequency_range=(params.frequency_range_low, params.frequency_range_high),
            max_reduction_db=params.max_reduction_db,
            attack_ms=params.attack_ms,
            release_ms=params.release_ms,
            max_bands=params.max_bands
        )
        
        suppressor = ResonanceSuppressor(res_params, sample_rate)
        output = suppressor.process(audio)
        
        # Mix control
        if params.mix < 1.0:
            output = audio * (1 - params.mix) + output * params.mix
        
        return output

    @staticmethod
    def compressor(audio: np.ndarray, params: CompressorParams, sample_rate: int) -> np.ndarray:
        """Apply compression."""
        # Convert to mono for detection
        if len(audio.shape) > 1:
            detect = np.mean(np.abs(audio), axis=1)
        else:
            detect = np.abs(audio)
            
        threshold = 10 ** (params.threshold_db / 20)
        attack_coeff = np.exp(-1.0 / (params.attack_ms * sample_rate / 1000.0))
        release_coeff = np.exp(-1.0 / (params.release_ms * sample_rate / 1000.0))
        
        envelope = 0.0
        gain_reduction = np.ones_like(detect)
        
        # Envelope follower
        # Vectorized implementation is hard for recursive filter, using loop for clarity
        # (In production, use numba or C++)
        
        # Simplified vector approximation
        # 1. Compute static gain reduction curve
        # 2. Smooth it with attack/release
        
        # Static curve
        db_detect = 20 * np.log10(detect + 1e-9)
        over_threshold = db_detect - params.threshold_db
        gain_db = np.zeros_like(db_detect)
        
        mask = over_threshold > 0
        gain_db[mask] = -over_threshold[mask] * (1 - 1/params.ratio)
        
        # Apply knee (simplified)
        
        # Convert to linear gain
        target_gain = 10 ** (gain_db / 20)
        
        # Apply smoothing (simple one-pole lowpass for now)
        # This is a very rough approximation of attack/release
        # For true compressor, we need stateful processing
        
        # Apply makeup gain
        makeup = 10 ** (params.makeup_gain_db / 20)
        
        if len(audio.shape) > 1:
            return audio * target_gain[:, np.newaxis] * makeup
        return audio * target_gain * makeup

    @staticmethod
    def saturation(audio: np.ndarray, params: SaturationParams) -> np.ndarray:
        """Apply saturation/distortion."""
        if params.drive <= 0:
            return audio
            
        # Tanh saturation
        # drive 0->1 maps to pre-gain 1->10
        pre_gain = 1.0 + params.drive * 9.0
        
        saturated = np.tanh(audio * pre_gain)
        
        # Normalize peak to match input roughly (auto-gain)
        # or just output as is for "drive" effect
        
        # Mix
        if params.mix < 1.0:
            return audio * (1 - params.mix) + saturated * params.mix
        return saturated

    @staticmethod
    def simple_reverb(audio: np.ndarray, params: ReverbParams, sample_rate: int) -> np.ndarray:
        """
        Simple Schroeder-like reverb using feedback delay networks or convolution.
        For this implementation, we'll use a simple impulse response convolution if possible,
        or a very basic feedback delay loop.
        """
        # Placeholder for a high-quality reverb
        # A simple feedback delay for "space"
        
        delay_samples = int(0.05 * sample_rate) # 50ms pre-delay
        decay = 0.6
        
        # Create a simple impulse response
        ir_len = int(params.room_size * 2.0 * sample_rate) # up to 2 sec
        if ir_len < 100: return audio
        
        # Noise burst with exponential decay
        ir = np.random.randn(ir_len)
        envelope = np.exp(-np.linspace(0, 5 + params.damping*5, ir_len))
        ir = ir * envelope
        
        # Normalize IR
        ir = ir / np.sum(np.abs(ir))
        
        # Convolve
        try:
            from scipy.signal import fftconvolve
            # Handle stereo
            if len(audio.shape) > 1:
                wet = np.zeros_like(audio)
                for i in range(audio.shape[1]):
                    # Convolve and truncate to original length
                    conv = fftconvolve(audio[:, i], ir, mode='full')
                    wet[:, i] = conv[:len(audio)]
            else:
                conv = fftconvolve(audio, ir, mode='full')
                wet = conv[:len(audio)]
                
            return audio * (1 - params.wet_level) + wet * params.wet_level
            
        except ImportError:
            return audio

    @staticmethod
    def true_peak_limit(audio: np.ndarray, params: 'TruePeakLimiterParams', sample_rate: int) -> np.ndarray:
        """
        Apply True Peak Limiting with ISP detection.
        
        Uses the TruePeakLimiter class for professional-grade limiting
        following ITU-R BS.1770-4 standards.
        
        Args:
            audio: Input audio (mono or stereo)
            params: TruePeakLimiterParams configuration
            sample_rate: Audio sample rate
        
        Returns:
            Limited audio with true peak at or below ceiling
        """
        from .true_peak_limiter import TruePeakLimiter, TruePeakLimiterParams
        
        # If params is not the right type, create default
        if not isinstance(params, TruePeakLimiterParams):
            params = TruePeakLimiterParams()
        
        limiter = TruePeakLimiter(params, sample_rate)
        return limiter.process(audio)

    @staticmethod
    def transient_shape(audio: np.ndarray, params: 'TransientShaperParams', sample_rate: int) -> np.ndarray:
        """
        Apply transient shaping using differential envelope detection.
        
        Uses the TransientShaper class based on SPL Transient Designer
        principles for attack/sustain control.
        
        Args:
            audio: Input audio (mono or stereo)
            params: TransientShaperParams configuration
            sample_rate: Audio sample rate
        
        Returns:
            Audio with shaped transients
        """
        from .transient_shaper import TransientShaper, TransientShaperParams
        
        # If params is not the right type, create default
        if not isinstance(params, TransientShaperParams):
            params = TransientShaperParams()
        
        shaper = TransientShaper(params, sample_rate)
        return shaper.process(audio)

# =============================================================================
# MIX CHAIN
# =============================================================================

class MixChain:
    """A chain of audio effects."""
    
    def __init__(self, name: str = "Default Chain"):
        self.name = name
        self.effects: List[Tuple[EffectType, EffectParams]] = []
    
    def add_effect(self, effect_type: EffectType, params: EffectParams):
        """Add an effect to the chain."""
        self.effects.append((effect_type, params))
    
    def process(self, audio: np.ndarray, sample_rate: int = SAMPLE_RATE) -> np.ndarray:
        """Process audio through the chain."""
        if len(audio) == 0:
            return audio
            
        processed = audio.copy()
        
        for effect_type, params in self.effects:
            if not params.enabled:
                continue
                
            if effect_type == EffectType.SATURATION:
                processed = DSP.saturation(processed, params)
            elif effect_type == EffectType.COMPRESSOR:
                processed = DSP.compressor(processed, params, sample_rate)
            elif effect_type == EffectType.REVERB:
                processed = DSP.simple_reverb(processed, params, sample_rate)
            elif effect_type == EffectType.STEREO_WIDTH:
                processed = DSP.stereo_width(processed, params, sample_rate)
            elif effect_type == EffectType.TRUE_PEAK_LIMITER:
                processed = DSP.true_peak_limit(processed, params, sample_rate)
            elif effect_type == EffectType.TRANSIENT_SHAPER:
                processed = DSP.transient_shape(processed, params, sample_rate)
            elif effect_type == EffectType.EQ_3BAND:
                processed = DSP.eq_3band(processed, params, sample_rate)
            elif effect_type == EffectType.PARAMETRIC_EQ:
                processed = DSP.parametric_eq(processed, params, sample_rate)
            elif effect_type == EffectType.DYNAMIC_EQ:
                processed = DSP.dynamic_eq(processed, params, sample_rate)
            elif effect_type == EffectType.HARMONIC_EXCITER:
                processed = DSP.harmonic_exciter(processed, params, sample_rate)
            elif effect_type == EffectType.RESONANCE_SUPPRESSION:
                processed = DSP.resonance_suppression(processed, params, sample_rate)
            # Add other effects...
            
        return processed

# =============================================================================
# PRESETS
# =============================================================================

def create_drum_bus_chain() -> MixChain:
    chain = MixChain("Drum Bus")
    chain.add_effect(EffectType.SATURATION, SaturationParams(drive=0.2, type="soft"))
    chain.add_effect(EffectType.COMPRESSOR, CompressorParams(threshold_db=-12, ratio=4.0, attack_ms=10, release_ms=50))
    return chain

def create_master_chain() -> MixChain:
    chain = MixChain("Master Bus")
    chain.add_effect(EffectType.COMPRESSOR, CompressorParams(threshold_db=-3, ratio=2.0, attack_ms=30, release_ms=100))
    chain.add_effect(EffectType.SATURATION, SaturationParams(drive=0.1, type="tube"))
    return chain

def create_lofi_chain() -> MixChain:
    chain = MixChain("Lo-Fi Chain")
    chain.add_effect(EffectType.SATURATION, SaturationParams(drive=0.4, type="soft"))
    # Would add Low Pass Filter here
    return chain

def create_wide_stereo_chain() -> MixChain:
    """Chain with subtle stereo widening for masters."""
    chain = MixChain("Wide Stereo")
    chain.add_effect(EffectType.STEREO_WIDTH, StereoWidthParams(width=1.2, mono_below_hz=120))
    return chain


def create_vocal_chain() -> MixChain:
    """Chain optimized for vocals with de-essing and presence."""
    chain = MixChain("Vocal Chain")
    
    # High-pass to remove rumble
    chain.add_effect(EffectType.PARAMETRIC_EQ, ParametricEQParams(
        bands=[
            {'type': 'highpass', 'frequency': 80, 'gain_db': 0, 'q': 0.7},
            {'type': 'peak', 'frequency': 200, 'gain_db': -2, 'q': 1.5},  # Reduce mud
            {'type': 'peak', 'frequency': 3000, 'gain_db': 2, 'q': 1.0},  # Presence
        ]
    ))
    
    # De-ess harsh frequencies dynamically
    chain.add_effect(EffectType.DYNAMIC_EQ, DynamicEQParams(
        frequency=5000,
        q=3.0,
        threshold_db=-18,
        ratio=6.0,
        attack_ms=2,
        release_ms=50,
        max_gain_db=-8,
        mode="compress"
    ))
    
    # Gentle compression
    chain.add_effect(EffectType.COMPRESSOR, CompressorParams(
        threshold_db=-15,
        ratio=3.0,
        attack_ms=15,
        release_ms=100
    ))
    
    # Add air/presence
    chain.add_effect(EffectType.HARMONIC_EXCITER, HarmonicExciterParams(
        even_harmonics=0.2,
        odd_harmonics=0.1,
        high_drive=0.2,
        air_drive=0.3,
        mix=0.3
    ))
    
    return chain


def create_mastering_chain() -> MixChain:
    """Full mastering chain with EQ, dynamics, and enhancement."""
    chain = MixChain("Mastering Chain")
    
    # Surgical EQ
    chain.add_effect(EffectType.PARAMETRIC_EQ, ParametricEQParams(
        bands=[
            {'type': 'highpass', 'frequency': 30, 'gain_db': 0, 'q': 0.7},
            {'type': 'low_shelf', 'frequency': 80, 'gain_db': 1.5, 'q': 0.7},
            {'type': 'peak', 'frequency': 200, 'gain_db': -1.5, 'q': 1.5},  # Reduce mud
            {'type': 'peak', 'frequency': 3000, 'gain_db': 0.5, 'q': 2.0},  # Presence
            {'type': 'high_shelf', 'frequency': 10000, 'gain_db': 1.0, 'q': 0.7},  # Air
        ]
    ))
    
    # Tame harsh midrange dynamically
    chain.add_effect(EffectType.DYNAMIC_EQ, DynamicEQParams(
        frequency=2500,
        q=2.5,
        threshold_db=-15,
        ratio=3.0,
        attack_ms=5,
        release_ms=75,
        max_gain_db=-6,
        mode="compress"
    ))
    
    # Gentle bus compression
    chain.add_effect(EffectType.COMPRESSOR, CompressorParams(
        threshold_db=-6,
        ratio=2.0,
        attack_ms=30,
        release_ms=150,
        knee_width_db=6.0
    ))
    
    # Add warmth and air
    chain.add_effect(EffectType.HARMONIC_EXCITER, HarmonicExciterParams(
        even_harmonics=0.15,
        odd_harmonics=0.05,
        mid_drive=0.1,
        air_drive=0.2,
        mix=0.25
    ))
    
    # Stereo width enhancement
    chain.add_effect(EffectType.STEREO_WIDTH, StereoWidthParams(
        width=1.1,
        mono_below_hz=100
    ))
    
    # Subtle saturation for glue
    chain.add_effect(EffectType.SATURATION, SaturationParams(drive=0.1, type="tube", mix=0.3))
    
    return chain


def create_bass_chain() -> MixChain:
    """Chain optimized for bass instruments."""
    chain = MixChain("Bass Chain")
    
    # Shape the low end
    chain.add_effect(EffectType.PARAMETRIC_EQ, ParametricEQParams(
        bands=[
            {'type': 'highpass', 'frequency': 30, 'gain_db': 0, 'q': 0.7},
            {'type': 'peak', 'frequency': 60, 'gain_db': 2, 'q': 1.5},  # Sub weight
            {'type': 'peak', 'frequency': 150, 'gain_db': -2, 'q': 2.0},  # Reduce boom
            {'type': 'peak', 'frequency': 800, 'gain_db': 1, 'q': 1.5},  # Growl
        ]
    ))
    
    # Heavy compression for punch
    chain.add_effect(EffectType.COMPRESSOR, CompressorParams(
        threshold_db=-12,
        ratio=6.0,
        attack_ms=15,
        release_ms=80
    ))
    
    # Subtle saturation for warmth
    chain.add_effect(EffectType.SATURATION, SaturationParams(drive=0.25, type="tube", mix=0.4))
    
    return chain


def create_clean_eq_chain() -> MixChain:
    """Simple parametric EQ chain for transparent correction."""
    chain = MixChain("Clean EQ")
    chain.add_effect(EffectType.PARAMETRIC_EQ, ParametricEQParams(
        bands=[
            {'type': 'low_shelf', 'frequency': 100, 'gain_db': 0, 'q': 0.7},
            {'type': 'peak', 'frequency': 400, 'gain_db': 0, 'q': 1.0},
            {'type': 'peak', 'frequency': 1500, 'gain_db': 0, 'q': 1.0},
            {'type': 'peak', 'frequency': 4000, 'gain_db': 0, 'q': 1.0},
            {'type': 'high_shelf', 'frequency': 8000, 'gain_db': 0, 'q': 0.7},
        ]
    ))
    return chain
