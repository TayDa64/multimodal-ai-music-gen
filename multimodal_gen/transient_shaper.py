"""
Transient Shaper Module

Professional-grade transient shaper using differential envelope algorithm
(SPL Transient Designer principles). Provides attack/sustain control for
drums, percussion, and any transient-rich material.

Key Features:
- Differential envelope detection (fast/slow envelopes)
- Lookahead buffer for catching initial attack
- Gain smoothing to prevent clicks
- Soft clipping for output protection
- DC blocking to prevent offset buildup

References:
- SPL Transient Designer principles
- Differential envelope detection (attack = fast - slow)

Author: Multimodal AI Music Generator
"""

import numpy as np
from dataclasses import dataclass
from typing import Optional, Tuple
from scipy import signal

from .mix_chain import EffectParams


# =============================================================================
# PARAMETERS
# =============================================================================

@dataclass
class TransientShaperParams(EffectParams):
    """
    Parameters for the Transient Shaper.
    
    Uses differential envelope detection to separate transient (attack)
    from sustain components, allowing independent control of each.
    
    Attributes:
        attack_amount: Attack boost/cut amount (-100 to +100).
                      Positive values add punch, negative softens attacks.
        sustain_amount: Sustain boost/cut amount (-100 to +100).
                       Positive values extend tails, negative shortens them.
        fast_attack_ms: Fast envelope attack time (0.1-5.0ms).
                       Controls how quickly the fast envelope follows transients.
        slow_attack_ms: Slow envelope attack time (5.0-100.0ms).
                       Controls the reference for sustain detection.
        lookahead_ms: Lookahead time (0-20ms).
                     Helps catch initial attack before it passes.
        sensitivity: Detection sensitivity multiplier (0.1-2.0).
                    Higher values trigger on smaller transients.
        output_gain_db: Output gain compensation in dB (-12 to +12).
        soft_clip: Enable soft clipping for output protection.
    """
    attack_amount: float = 0.0      # -100 to +100 (% boost/cut)
    sustain_amount: float = 0.0     # -100 to +100
    fast_attack_ms: float = 0.5     # 0.1-5.0 (catches transients)
    slow_attack_ms: float = 20.0    # 5.0-100.0 (follows sustain)
    lookahead_ms: float = 5.0       # 0-20 (helps catch initial attack)
    sensitivity: float = 1.0        # 0.1-2.0 (threshold multiplier)
    output_gain_db: float = 0.0     # Output gain compensation
    soft_clip: bool = True          # Enable soft clipping


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def ms_to_samples(ms: float, sample_rate: int) -> int:
    """Convert milliseconds to samples."""
    return max(1, int(ms * sample_rate / 1000.0))


def calculate_envelope_coeff(time_ms: float, sample_rate: int) -> float:
    """
    Calculate one-pole filter coefficient for envelope follower.
    
    Uses the standard formula: alpha = exp(-1 / (time_constant_samples))
    
    Args:
        time_ms: Time constant in milliseconds
        sample_rate: Sample rate in Hz
    
    Returns:
        Filter coefficient (0-1)
    """
    time_samples = time_ms * sample_rate / 1000.0
    if time_samples <= 0:
        return 0.0
    return np.exp(-1.0 / time_samples)


def soft_clip_tanh(x: np.ndarray, threshold: float = 0.9) -> np.ndarray:
    """
    Soft clip using tanh for values above threshold.
    
    Provides smooth limiting without harsh digital distortion.
    Linear below threshold, tanh saturation above.
    
    Args:
        x: Input signal
        threshold: Level where soft clipping begins (0-1)
    
    Returns:
        Soft-clipped signal
    """
    # Scale factor to make transition smooth
    scale = 1.0 / (1.0 - threshold)
    
    output = np.copy(x)
    
    # Positive values above threshold
    pos_mask = x > threshold
    if np.any(pos_mask):
        over = (x[pos_mask] - threshold) * scale
        output[pos_mask] = threshold + (1.0 - threshold) * np.tanh(over)
    
    # Negative values below -threshold
    neg_mask = x < -threshold
    if np.any(neg_mask):
        over = (-x[neg_mask] - threshold) * scale
        output[neg_mask] = -threshold - (1.0 - threshold) * np.tanh(over)
    
    return output


def dc_blocker(audio: np.ndarray, cutoff_hz: float = 20.0, sample_rate: int = 44100) -> np.ndarray:
    """
    Remove DC offset using a high-pass filter.
    
    Args:
        audio: Input audio
        cutoff_hz: High-pass cutoff frequency
        sample_rate: Sample rate
    
    Returns:
        Audio with DC removed
    """
    nyquist = sample_rate / 2
    normalized_cutoff = cutoff_hz / nyquist
    
    # Ensure cutoff is within valid range
    normalized_cutoff = np.clip(normalized_cutoff, 0.0001, 0.99)
    
    # Design 2nd order Butterworth high-pass
    b, a = signal.butter(2, normalized_cutoff, btype='high')
    
    # Apply filter
    if len(audio.shape) > 1:
        output = np.zeros_like(audio)
        for ch in range(audio.shape[1]):
            output[:, ch] = signal.lfilter(b, a, audio[:, ch])
        return output
    else:
        return signal.lfilter(b, a, audio)


# =============================================================================
# TRANSIENT SHAPER CLASS
# =============================================================================

class TransientShaper:
    """
    Professional Transient Shaper using differential envelope detection.
    
    Based on the SPL Transient Designer algorithm which uses the difference
    between fast and slow envelope followers to detect transients.
    
    Algorithm:
    1. Calculate fast envelope (0.5-5ms attack) - tracks transients
    2. Calculate slow envelope (20-100ms attack) - tracks sustain
    3. Transient signal = fast_envelope - slow_envelope
    4. Apply gain based on transient/sustain detection
    5. Smooth gain to prevent clicks
    6. Optional soft clipping for output protection
    
    Usage:
        >>> params = TransientShaperParams(attack_amount=50, sustain_amount=-20)
        >>> shaper = TransientShaper(params, sample_rate=44100)
        >>> processed = shaper.process(drums_audio)
    """
    
    def __init__(self, params: TransientShaperParams, sample_rate: int = 44100):
        """
        Initialize the Transient Shaper.
        
        Args:
            params: TransientShaperParams configuration
            sample_rate: Audio sample rate in Hz
        """
        self.params = params
        self.sample_rate = sample_rate
        
        # Calculate envelope follower coefficients
        self.fast_attack_coeff = calculate_envelope_coeff(params.fast_attack_ms, sample_rate)
        self.slow_attack_coeff = calculate_envelope_coeff(params.slow_attack_ms, sample_rate)
        
        # Release is typically faster than attack for snappy response
        fast_release_ms = params.fast_attack_ms * 5  # 5x attack time
        slow_release_ms = params.slow_attack_ms * 2  # 2x attack time
        self.fast_release_coeff = calculate_envelope_coeff(fast_release_ms, sample_rate)
        self.slow_release_coeff = calculate_envelope_coeff(slow_release_ms, sample_rate)
        
        # Lookahead in samples
        self.lookahead_samples = ms_to_samples(params.lookahead_ms, sample_rate)
        
        # Gain smoothing (2ms to prevent clicks)
        self.gain_smooth_coeff = calculate_envelope_coeff(2.0, sample_rate)
        
        # Output gain
        self.output_gain = 10 ** (params.output_gain_db / 20.0)
        
        # Detection threshold based on sensitivity
        # Lower sensitivity = higher threshold = only loud transients detected
        self.threshold = 0.01 / params.sensitivity
        
        # Clamp parameter ranges
        self.attack_amount = np.clip(params.attack_amount, -100, 100) / 100.0
        self.sustain_amount = np.clip(params.sustain_amount, -100, 100) / 100.0
    
    def process(self, audio: np.ndarray) -> np.ndarray:
        """
        Process audio through the transient shaper.
        
        Handles both mono and stereo input. For stereo, channels are
        processed independently to preserve stereo transient information.
        
        Args:
            audio: Input audio array. Shape: (samples,) for mono or
                  (samples, 2) for stereo.
        
        Returns:
            Processed audio with shaped transients.
        """
        if len(audio) == 0:
            return audio
        
        # Skip processing if no shaping requested
        if self.attack_amount == 0 and self.sustain_amount == 0:
            return audio * self.output_gain
        
        # Handle stereo vs mono
        is_stereo = len(audio.shape) > 1 and audio.shape[1] == 2
        
        if is_stereo:
            # Process each channel independently
            left = self._process_mono(audio[:, 0])
            right = self._process_mono(audio[:, 1])
            output = np.column_stack([left, right])
        else:
            output = self._process_mono(audio)
        
        # Apply DC blocking if gain changes might introduce DC
        if abs(self.attack_amount) > 0.3 or abs(self.sustain_amount) > 0.3:
            output = dc_blocker(output, 20.0, self.sample_rate)
        
        return output
    
    def _process_mono(self, audio: np.ndarray) -> np.ndarray:
        """Process mono audio through the transient shaper."""
        n_samples = len(audio)
        
        # Apply lookahead by padding input
        if self.lookahead_samples > 0:
            # Pad with zeros at the end so we can look ahead
            padded = np.concatenate([audio, np.zeros(self.lookahead_samples)])
        else:
            padded = audio
        
        # Calculate envelope signals
        fast_env = self._envelope_follower(
            padded, 
            self.fast_attack_coeff, 
            self.fast_release_coeff
        )
        slow_env = self._envelope_follower(
            padded, 
            self.slow_attack_coeff, 
            self.slow_release_coeff
        )
        
        # Shift envelopes for lookahead (look ahead in the envelope, not the audio)
        if self.lookahead_samples > 0:
            fast_env = fast_env[self.lookahead_samples:self.lookahead_samples + n_samples]
            slow_env = slow_env[self.lookahead_samples:self.lookahead_samples + n_samples]
        else:
            fast_env = fast_env[:n_samples]
            slow_env = slow_env[:n_samples]
        
        # Calculate gain envelope
        gain = self._calculate_gain_envelope(fast_env, slow_env)
        
        # Smooth the gain to prevent clicks
        gain = self._smooth_gain(gain)
        
        # Apply gain to original audio (no lookahead delay on audio itself)
        processed = audio * gain
        
        # Apply output gain
        processed = processed * self.output_gain
        
        # Apply soft clipping if enabled
        if self.params.soft_clip:
            processed = soft_clip_tanh(processed, 0.95)
        
        return processed
    
    def _envelope_follower(
        self, 
        audio: np.ndarray, 
        attack_coeff: float, 
        release_coeff: float
    ) -> np.ndarray:
        """
        Follow the envelope of the audio signal.
        
        Uses separate attack and release coefficients for asymmetric response.
        Attack: how fast envelope rises to follow transients
        Release: how fast envelope decays after peak
        
        Args:
            audio: Input audio
            attack_coeff: Attack coefficient (0-1, higher = slower)
            release_coeff: Release coefficient (0-1, higher = slower)
        
        Returns:
            Envelope signal (positive values)
        """
        n_samples = len(audio)
        envelope = np.zeros(n_samples)
        
        # Rectify input
        rectified = np.abs(audio)
        
        state = 0.0
        
        for i in range(n_samples):
            input_val = rectified[i]
            
            if input_val > state:
                # Attack phase: envelope rising
                state = attack_coeff * state + (1.0 - attack_coeff) * input_val
            else:
                # Release phase: envelope falling
                state = release_coeff * state + (1.0 - release_coeff) * input_val
            
            envelope[i] = state
        
        return envelope
    
    def _calculate_gain_envelope(
        self, 
        fast_env: np.ndarray, 
        slow_env: np.ndarray
    ) -> np.ndarray:
        """
        Calculate the gain envelope based on transient/sustain detection.
        
        Transient = difference between fast and slow envelopes
        When transient is high, we're in the attack phase
        When transient is low but slow_env is high, we're in sustain
        
        Args:
            fast_env: Fast envelope (tracks transients)
            slow_env: Slow envelope (tracks sustain)
        
        Returns:
            Gain envelope to apply to audio
        """
        # Calculate transient signal (difference)
        transient = fast_env - slow_env
        
        # Transient is positive during attacks, near zero during sustain
        # Clip to only positive values (attack phase)
        transient_positive = np.maximum(transient, 0.0)
        
        # Normalize transient detection relative to envelope level
        # This makes detection level-independent
        max_env = np.maximum(fast_env, self.threshold)
        transient_normalized = transient_positive / max_env
        
        # Sustain detection (when slow envelope is active but transient is low)
        sustain_normalized = np.clip(slow_env / (slow_env.max() + 1e-10), 0, 1)
        
        # Calculate attack gain
        # transient_normalized is ~1 during transients, ~0 during sustain
        # attack_amount > 0: boost attacks
        # attack_amount < 0: cut attacks
        attack_gain_factor = transient_normalized * self.attack_amount
        
        # Calculate sustain gain
        # Higher during sustained portions
        # Reduce transient contribution to sustain
        sustain_contribution = sustain_normalized * (1.0 - transient_normalized * 0.5)
        sustain_gain_factor = sustain_contribution * self.sustain_amount
        
        # Combine gains
        # Base gain is 1.0, modified by attack and sustain factors
        gain = 1.0 + attack_gain_factor + sustain_gain_factor
        
        # Ensure gain doesn't go negative (minimum 0.1 = -20dB)
        gain = np.maximum(gain, 0.1)
        
        # Limit maximum gain to prevent excessive boost (+12dB)
        gain = np.minimum(gain, 4.0)
        
        return gain
    
    def _smooth_gain(self, gain: np.ndarray) -> np.ndarray:
        """
        Smooth the gain envelope to prevent clicks.
        
        Uses a one-pole lowpass filter with rate limiting
        to ensure smooth transitions.
        
        Args:
            gain: Raw gain envelope
        
        Returns:
            Smoothed gain envelope
        """
        n_samples = len(gain)
        smoothed = np.zeros(n_samples)
        
        state = gain[0] if n_samples > 0 else 1.0
        
        # Maximum gain change per sample (rate limiting)
        # Allows change of 1.0 over ~2ms
        max_delta = 1.0 / (2.0 * self.sample_rate / 1000.0)
        
        for i in range(n_samples):
            target = gain[i]
            
            # Apply smoothing filter
            state = self.gain_smooth_coeff * state + (1.0 - self.gain_smooth_coeff) * target
            
            # Rate limiting (additional artifact prevention)
            if i > 0:
                delta = state - smoothed[i - 1]
                if abs(delta) > max_delta:
                    state = smoothed[i - 1] + np.sign(delta) * max_delta
            
            smoothed[i] = state
        
        return smoothed
    
    def get_analysis(self, audio: np.ndarray) -> dict:
        """
        Analyze audio and return transient/sustain characteristics.
        
        Useful for understanding how the shaper will affect the audio.
        
        Args:
            audio: Input audio
        
        Returns:
            Dict with analysis information
        """
        # Get mono for analysis
        if len(audio.shape) > 1:
            mono = np.mean(audio, axis=1)
        else:
            mono = audio
        
        # Calculate envelopes
        fast_env = self._envelope_follower(
            mono, 
            self.fast_attack_coeff, 
            self.fast_release_coeff
        )
        slow_env = self._envelope_follower(
            mono, 
            self.slow_attack_coeff, 
            self.slow_release_coeff
        )
        
        # Transient detection
        transient = np.maximum(fast_env - slow_env, 0)
        
        # Find peaks in transient signal (approximate transient count)
        transient_threshold = np.max(transient) * 0.3
        above_threshold = transient > transient_threshold
        transient_regions = np.diff(above_threshold.astype(int))
        transient_count = np.sum(transient_regions == 1)
        
        return {
            'peak_level_db': 20 * np.log10(np.max(np.abs(mono)) + 1e-10),
            'rms_level_db': 20 * np.log10(np.sqrt(np.mean(mono ** 2)) + 1e-10),
            'transient_count': int(transient_count),
            'max_transient_strength': float(np.max(transient)),
            'avg_sustain_level': float(np.mean(slow_env)),
            'dynamic_range_db': float(20 * np.log10(np.max(fast_env) / (np.mean(slow_env) + 1e-10)))
        }


# =============================================================================
# PRESET FUNCTIONS
# =============================================================================

def drum_punch() -> TransientShaperParams:
    """
    Preset for adding punch to drums and percussion.
    
    Emphasizes the attack while slightly reducing sustain
    for a tight, punchy drum sound.
    
    Returns:
        TransientShaperParams configured for drum punch
    """
    return TransientShaperParams(
        attack_amount=50.0,      # +50% attack boost
        sustain_amount=-10.0,   # Slight sustain reduction
        fast_attack_ms=0.5,     # Fast attack detection
        slow_attack_ms=25.0,    # Medium sustain reference
        lookahead_ms=3.0,       # Small lookahead
        sensitivity=1.2,        # Slightly higher sensitivity
        soft_clip=True
    )


def drum_snap() -> TransientShaperParams:
    """
    Preset for maximum attack emphasis (snare crack, etc).
    
    Aggressive attack boost with sustain cut for
    very transient-focused sound.
    
    Returns:
        TransientShaperParams configured for snappy drums
    """
    return TransientShaperParams(
        attack_amount=80.0,      # Strong attack boost
        sustain_amount=-30.0,   # Notable sustain cut
        fast_attack_ms=0.3,     # Very fast attack
        slow_attack_ms=30.0,
        lookahead_ms=5.0,       # Good lookahead
        sensitivity=1.5,        # High sensitivity
        soft_clip=True
    )


def drum_sustain() -> TransientShaperParams:
    """
    Preset for extending drum sustain/room sound.
    
    Reduces attack and boosts sustain for a roomier,
    more ambient drum sound.
    
    Returns:
        TransientShaperParams configured for sustained drums
    """
    return TransientShaperParams(
        attack_amount=-20.0,    # Slight attack reduction
        sustain_amount=50.0,    # Sustain boost
        fast_attack_ms=1.0,
        slow_attack_ms=50.0,    # Longer sustain reference
        lookahead_ms=2.0,
        sensitivity=0.8,
        soft_clip=True
    )


def vocal_presence() -> TransientShaperParams:
    """
    Preset for adding presence to vocals.
    
    Subtle attack enhancement for consonant clarity
    without affecting the body of the voice.
    
    Returns:
        TransientShaperParams configured for vocal presence
    """
    return TransientShaperParams(
        attack_amount=25.0,      # Subtle attack boost
        sustain_amount=10.0,    # Slight sustain lift
        fast_attack_ms=2.0,     # Slower attack for vocal transients
        slow_attack_ms=40.0,
        lookahead_ms=5.0,
        sensitivity=0.7,        # Lower sensitivity for vocals
        soft_clip=True
    )


def bass_tighten() -> TransientShaperParams:
    """
    Preset for tightening bass guitar/synth bass.
    
    Adds attack definition and reduces sustain
    for a tighter, more controlled bass sound.
    
    Returns:
        TransientShaperParams configured for tight bass
    """
    return TransientShaperParams(
        attack_amount=30.0,
        sustain_amount=-25.0,
        fast_attack_ms=1.5,
        slow_attack_ms=35.0,
        lookahead_ms=4.0,
        sensitivity=1.0,
        soft_clip=True
    )


def acoustic_guitar() -> TransientShaperParams:
    """
    Preset for acoustic guitar pick attack.
    
    Enhances the pick attack while maintaining
    natural sustain characteristics.
    
    Returns:
        TransientShaperParams configured for acoustic guitar
    """
    return TransientShaperParams(
        attack_amount=35.0,
        sustain_amount=5.0,
        fast_attack_ms=0.8,
        slow_attack_ms=30.0,
        lookahead_ms=3.0,
        sensitivity=1.1,
        soft_clip=True
    )


def smooth_attack() -> TransientShaperParams:
    """
    Preset for softening harsh attacks.
    
    Reduces attack transients for a smoother,
    more gentle sound.
    
    Returns:
        TransientShaperParams configured for smooth attacks
    """
    return TransientShaperParams(
        attack_amount=-40.0,    # Attack reduction
        sustain_amount=15.0,   # Compensate with sustain
        fast_attack_ms=0.5,
        slow_attack_ms=20.0,
        lookahead_ms=5.0,
        sensitivity=1.0,
        soft_clip=True
    )


def piano_presence() -> TransientShaperParams:
    """
    Preset for piano hammer attack clarity.
    
    Subtle enhancement of the hammer strike
    for more defined piano notes.
    
    Returns:
        TransientShaperParams configured for piano
    """
    return TransientShaperParams(
        attack_amount=20.0,
        sustain_amount=0.0,
        fast_attack_ms=1.0,
        slow_attack_ms=45.0,
        lookahead_ms=4.0,
        sensitivity=0.9,
        soft_clip=True
    )


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def shape_transients(
    audio: np.ndarray,
    attack_amount: float = 0.0,
    sustain_amount: float = 0.0,
    sample_rate: int = 44100
) -> np.ndarray:
    """
    Convenience function for quick transient shaping.
    
    Args:
        audio: Input audio array
        attack_amount: Attack boost/cut (-100 to +100)
        sustain_amount: Sustain boost/cut (-100 to +100)
        sample_rate: Audio sample rate
    
    Returns:
        Processed audio
    
    Example:
        >>> punchy_drums = shape_transients(drums, attack_amount=50, sustain_amount=-10)
    """
    params = TransientShaperParams(
        attack_amount=attack_amount,
        sustain_amount=sustain_amount
    )
    shaper = TransientShaper(params, sample_rate)
    return shaper.process(audio)


def apply_preset(
    audio: np.ndarray,
    preset_name: str,
    sample_rate: int = 44100
) -> np.ndarray:
    """
    Apply a named transient shaping preset.
    
    Args:
        audio: Input audio array
        preset_name: Name of preset ('drum_punch', 'drum_snap', 'drum_sustain',
                    'vocal_presence', 'bass_tighten', 'acoustic_guitar',
                    'smooth_attack', 'piano_presence')
        sample_rate: Audio sample rate
    
    Returns:
        Processed audio
    
    Example:
        >>> punchy_drums = apply_preset(drums, 'drum_punch')
    """
    presets = {
        'drum_punch': drum_punch,
        'drum_snap': drum_snap,
        'drum_sustain': drum_sustain,
        'vocal_presence': vocal_presence,
        'bass_tighten': bass_tighten,
        'acoustic_guitar': acoustic_guitar,
        'smooth_attack': smooth_attack,
        'piano_presence': piano_presence
    }
    
    if preset_name not in presets:
        available = ', '.join(presets.keys())
        raise ValueError(f"Unknown preset: {preset_name}. Available: {available}")
    
    params = presets[preset_name]()
    shaper = TransientShaper(params, sample_rate)
    return shaper.process(audio)


# =============================================================================
# PRESETS DICTIONARY (for integration with track_processor)
# =============================================================================

TRANSIENT_PRESETS = {
    'drum_punch': drum_punch(),
    'drum_snap': drum_snap(),
    'drum_sustain': drum_sustain(),
    'vocal_presence': vocal_presence(),
    'bass_tighten': bass_tighten(),
    'acoustic_guitar': acoustic_guitar(),
    'smooth_attack': smooth_attack(),
    'piano_presence': piano_presence()
}
