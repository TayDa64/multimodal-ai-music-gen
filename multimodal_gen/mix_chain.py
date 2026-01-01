"""
Mix Chain Module

Defines audio effect chains for mixing and mastering.
Provides a structured way to apply series of effects to audio buffers.
"""

import numpy as np
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Union, Callable
from enum import Enum
import math

from .utils import SAMPLE_RATE

# =============================================================================
# EFFECT TYPES
# =============================================================================

class EffectType(Enum):
    EQ_3BAND = "eq_3band"
    COMPRESSOR = "compressor"
    REVERB = "reverb"
    DELAY = "delay"
    SATURATION = "saturation"
    LIMITER = "limiter"
    GAIN = "gain"
    PAN = "pan"

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
        """Apply 3-band EQ."""
        # This would ideally use biquad filters for low shelf, peaking, high shelf
        # For this prototype, we'll use a simplified FFT approach or skip if complex
        # Let's implement a simple gain scaling for now as placeholder
        # Real implementation requires filter design
        return audio # Placeholder

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
