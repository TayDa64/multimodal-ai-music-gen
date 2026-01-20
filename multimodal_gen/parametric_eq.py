"""
Parametric EQ and Dynamic EQ Module

Implements professional-grade parametric equalization based on the
Robert Bristow-Johnson Audio EQ Cookbook, plus dynamic EQ, resonance
suppression, and harmonic exciter algorithms.

References:
- W3C Audio EQ Cookbook: https://www.w3.org/TR/audio-eq-cookbook/
- EarLevel Engineering: https://www.earlevel.com/main/
"""

import numpy as np
from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Union
from enum import Enum
from scipy.signal import lfilter, butter, sosfilt

try:
    from scipy.fft import rfft, rfftfreq
    from scipy.signal import find_peaks
    HAS_SCIPY_FFT = True
except ImportError:
    HAS_SCIPY_FFT = False

from .utils import SAMPLE_RATE


# =============================================================================
# FILTER TYPES
# =============================================================================

class FilterType(Enum):
    """Types of biquad filters available."""
    LOWPASS = "lowpass"
    HIGHPASS = "highpass"
    BANDPASS = "bandpass"
    NOTCH = "notch"
    PEAK = "peak"
    LOW_SHELF = "low_shelf"
    HIGH_SHELF = "high_shelf"
    ALLPASS = "allpass"


class DynamicMode(Enum):
    """Dynamic EQ modes."""
    COMPRESS = "compress"  # Reduce gain when signal exceeds threshold
    EXPAND = "expand"      # Boost gain when signal below threshold


# =============================================================================
# PARAMETER CLASSES
# =============================================================================

@dataclass
class EQBandParams:
    """Parameters for a single EQ band."""
    filter_type: FilterType = FilterType.PEAK
    frequency: float = 1000.0  # Hz
    gain_db: float = 0.0       # dB (for peak/shelf only)
    q: float = 1.0             # Q factor (higher = narrower)
    enabled: bool = True


@dataclass
class ParametricEQParams:
    """Parameters for multi-band parametric EQ."""
    enabled: bool = True
    mix: float = 1.0
    bands: List[EQBandParams] = field(default_factory=list)
    output_gain_db: float = 0.0
    
    def __post_init__(self):
        if not self.bands:
            # Default 4-band semi-parametric setup
            self.bands = [
                EQBandParams(FilterType.LOW_SHELF, 100.0, 0.0, 0.7),
                EQBandParams(FilterType.PEAK, 500.0, 0.0, 1.0),
                EQBandParams(FilterType.PEAK, 2000.0, 0.0, 1.0),
                EQBandParams(FilterType.HIGH_SHELF, 8000.0, 0.0, 0.7),
            ]


@dataclass
class DynamicEQBandParams:
    """Parameters for a dynamic EQ band."""
    enabled: bool = True
    frequency: float = 3000.0      # Center frequency (Hz)
    q: float = 2.0                  # Bandwidth
    threshold_db: float = -20.0     # Activation threshold
    ratio: float = 4.0              # Compression/expansion ratio
    attack_ms: float = 10.0         # Attack time
    release_ms: float = 100.0       # Release time
    max_gain_db: float = -12.0      # Maximum gain change (negative for cut)
    mode: DynamicMode = DynamicMode.COMPRESS
    knee_db: float = 6.0            # Soft knee width


@dataclass
class ExciterParams:
    """Parameters for harmonic exciter."""
    enabled: bool = True
    mix: float = 0.5
    even_harmonics: float = 0.3    # 0-1, amount of 2nd/4th harmonics
    odd_harmonics: float = 0.2     # 0-1, amount of 3rd/5th harmonics
    low_drive: float = 0.0         # Drive for <200 Hz
    mid_drive: float = 0.2         # Drive for 200-2000 Hz
    high_drive: float = 0.3        # Drive for 2-8 kHz
    air_drive: float = 0.4         # Drive for >8 kHz
    air_freq: float = 8000.0       # Air band cutoff


@dataclass
class ResonanceSuppressionParams:
    """Parameters for automatic resonance suppression."""
    enabled: bool = True
    sensitivity: float = 0.5       # 0-1, detection sensitivity
    frequency_range: Tuple[float, float] = (100.0, 10000.0)
    min_q: float = 5.0             # Minimum Q to consider resonant
    max_reduction_db: float = -12.0
    attack_ms: float = 5.0
    release_ms: float = 50.0
    fft_size: int = 4096
    max_bands: int = 8             # Maximum simultaneous notches


# =============================================================================
# BIQUAD COEFFICIENT CALCULATION
# =============================================================================

def calculate_biquad_coefficients(
    filter_type: FilterType,
    frequency: float,
    sample_rate: float,
    gain_db: float = 0.0,
    q: float = 1.0
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Calculate biquad filter coefficients using RBJ Audio EQ Cookbook.
    
    Based on W3C Audio EQ Cookbook:
    https://www.w3.org/TR/audio-eq-cookbook/
    
    Args:
        filter_type: Type of filter
        frequency: Center/corner frequency in Hz
        sample_rate: Sample rate in Hz
        gain_db: Gain in dB (for peak and shelf filters)
        q: Q factor (bandwidth)
        
    Returns:
        b, a: Numerator and denominator coefficients [b0, b1, b2], [1, a1, a2]
    """
    # Clamp frequency to valid range
    nyquist = sample_rate / 2
    frequency = np.clip(frequency, 1.0, nyquist * 0.99)
    
    # Intermediate variables
    A = 10 ** (gain_db / 40)  # For peaking and shelving
    w0 = 2 * np.pi * frequency / sample_rate
    cos_w0 = np.cos(w0)
    sin_w0 = np.sin(w0)
    alpha = sin_w0 / (2 * max(q, 0.001))  # Prevent division by zero
    
    if filter_type == FilterType.LOWPASS:
        b0 = (1 - cos_w0) / 2
        b1 = 1 - cos_w0
        b2 = (1 - cos_w0) / 2
        a0 = 1 + alpha
        a1 = -2 * cos_w0
        a2 = 1 - alpha
        
    elif filter_type == FilterType.HIGHPASS:
        b0 = (1 + cos_w0) / 2
        b1 = -(1 + cos_w0)
        b2 = (1 + cos_w0) / 2
        a0 = 1 + alpha
        a1 = -2 * cos_w0
        a2 = 1 - alpha
        
    elif filter_type == FilterType.BANDPASS:
        b0 = alpha
        b1 = 0
        b2 = -alpha
        a0 = 1 + alpha
        a1 = -2 * cos_w0
        a2 = 1 - alpha
        
    elif filter_type == FilterType.NOTCH:
        b0 = 1
        b1 = -2 * cos_w0
        b2 = 1
        a0 = 1 + alpha
        a1 = -2 * cos_w0
        a2 = 1 - alpha
        
    elif filter_type == FilterType.PEAK:
        b0 = 1 + alpha * A
        b1 = -2 * cos_w0
        b2 = 1 - alpha * A
        a0 = 1 + alpha / A
        a1 = -2 * cos_w0
        a2 = 1 - alpha / A
        
    elif filter_type == FilterType.LOW_SHELF:
        sqrt_A = np.sqrt(A)
        sqrt_2A_alpha = 2 * sqrt_A * alpha
        
        b0 = A * ((A + 1) - (A - 1) * cos_w0 + sqrt_2A_alpha)
        b1 = 2 * A * ((A - 1) - (A + 1) * cos_w0)
        b2 = A * ((A + 1) - (A - 1) * cos_w0 - sqrt_2A_alpha)
        a0 = (A + 1) + (A - 1) * cos_w0 + sqrt_2A_alpha
        a1 = -2 * ((A - 1) + (A + 1) * cos_w0)
        a2 = (A + 1) + (A - 1) * cos_w0 - sqrt_2A_alpha
        
    elif filter_type == FilterType.HIGH_SHELF:
        sqrt_A = np.sqrt(A)
        sqrt_2A_alpha = 2 * sqrt_A * alpha
        
        b0 = A * ((A + 1) + (A - 1) * cos_w0 + sqrt_2A_alpha)
        b1 = -2 * A * ((A - 1) + (A + 1) * cos_w0)
        b2 = A * ((A + 1) + (A - 1) * cos_w0 - sqrt_2A_alpha)
        a0 = (A + 1) - (A - 1) * cos_w0 + sqrt_2A_alpha
        a1 = 2 * ((A - 1) - (A + 1) * cos_w0)
        a2 = (A + 1) - (A - 1) * cos_w0 - sqrt_2A_alpha
        
    elif filter_type == FilterType.ALLPASS:
        b0 = 1 - alpha
        b1 = -2 * cos_w0
        b2 = 1 + alpha
        a0 = 1 + alpha
        a1 = -2 * cos_w0
        a2 = 1 - alpha
    
    else:
        raise ValueError(f"Unknown filter type: {filter_type}")
    
    # Normalize by a0
    b = np.array([b0/a0, b1/a0, b2/a0])
    a = np.array([1.0, a1/a0, a2/a0])
    
    return b, a


# =============================================================================
# BIQUAD FILTER CLASS
# =============================================================================

class BiquadFilter:
    """
    Single biquad filter with state.
    
    Uses Transposed Direct Form II for better numerical stability.
    """
    
    def __init__(self):
        self.b = np.array([1.0, 0.0, 0.0])
        self.a = np.array([1.0, 0.0, 0.0])
        self.z1 = 0.0
        self.z2 = 0.0
    
    def set_coefficients(self, b: np.ndarray, a: np.ndarray):
        """Set filter coefficients."""
        self.b = b
        self.a = a
    
    def reset(self):
        """Reset filter state."""
        self.z1 = 0.0
        self.z2 = 0.0
    
    def process_sample(self, x: float) -> float:
        """
        Process single sample using Transposed Direct Form II.
        
        More numerically stable than Direct Form I for floating point.
        """
        y = self.b[0] * x + self.z1
        self.z1 = self.b[1] * x - self.a[1] * y + self.z2
        self.z2 = self.b[2] * x - self.a[2] * y
        return y
    
    def process_block(self, audio: np.ndarray) -> np.ndarray:
        """Process block of samples (sample-by-sample for state preservation)."""
        output = np.zeros_like(audio)
        for i in range(len(audio)):
            output[i] = self.process_sample(audio[i])
        return output


# =============================================================================
# PARAMETRIC EQ
# =============================================================================

class ParametricEQ:
    """
    Multi-band parametric equalizer.
    
    Each band is a biquad filter with configurable type, frequency, gain, and Q.
    Uses vectorized processing via scipy.signal.lfilter for performance.
    """
    
    def __init__(self, params: ParametricEQParams, sample_rate: float = SAMPLE_RATE):
        self.params = params
        self.sample_rate = sample_rate
        self._coefficients: List[Tuple[np.ndarray, np.ndarray]] = []
        self._update_coefficients()
    
    def _update_coefficients(self):
        """Recalculate all band coefficients."""
        self._coefficients = []
        for band in self.params.bands:
            if band.enabled and band.gain_db != 0.0:
                b, a = calculate_biquad_coefficients(
                    band.filter_type,
                    band.frequency,
                    self.sample_rate,
                    band.gain_db,
                    band.q
                )
                self._coefficients.append((b, a))
    
    def set_band(self, index: int, 
                 filter_type: Optional[FilterType] = None,
                 frequency: Optional[float] = None,
                 gain_db: Optional[float] = None,
                 q: Optional[float] = None,
                 enabled: Optional[bool] = None):
        """Update a single band's parameters."""
        if index >= len(self.params.bands):
            raise IndexError(f"Band index {index} out of range")
        
        band = self.params.bands[index]
        
        if filter_type is not None:
            band.filter_type = filter_type
        if frequency is not None:
            band.frequency = frequency
        if gain_db is not None:
            band.gain_db = gain_db
        if q is not None:
            band.q = q
        if enabled is not None:
            band.enabled = enabled
        
        self._update_coefficients()
    
    def process(self, audio: np.ndarray) -> np.ndarray:
        """
        Process audio through all enabled EQ bands.
        
        Args:
            audio: Mono or stereo audio array
            
        Returns:
            Processed audio
        """
        if not self.params.enabled or len(audio) == 0:
            return audio
        
        output = audio.copy()
        
        # Apply each band
        for b, a in self._coefficients:
            if len(output.shape) > 1:
                for ch in range(output.shape[1]):
                    output[:, ch] = lfilter(b, a, output[:, ch])
            else:
                output = lfilter(b, a, output)
        
        # Apply output gain
        if self.params.output_gain_db != 0.0:
            gain = 10 ** (self.params.output_gain_db / 20)
            output = output * gain
        
        # Mix control
        if self.params.mix < 1.0:
            output = audio * (1 - self.params.mix) + output * self.params.mix
        
        return output


# =============================================================================
# ENVELOPE FOLLOWER
# =============================================================================

class EnvelopeFollower:
    """
    Attack/release envelope follower.
    
    Used for dynamics processing (compression, dynamic EQ, etc.)
    """
    
    def __init__(self, attack_ms: float, release_ms: float, sample_rate: float):
        self.sample_rate = sample_rate
        self.envelope = 0.0
        self.set_times(attack_ms, release_ms)
    
    def set_times(self, attack_ms: float, release_ms: float):
        """Update attack and release times."""
        # Using the standard formula: coef = 1 - exp(-2.2 / (time_ms * sr / 1000))
        self.attack_coef = 1 - np.exp(-2.2 / (attack_ms * self.sample_rate / 1000))
        self.release_coef = 1 - np.exp(-2.2 / (release_ms * self.sample_rate / 1000))
    
    def reset(self):
        """Reset envelope state."""
        self.envelope = 0.0
    
    def process_sample(self, x: float) -> float:
        """Process single sample through envelope follower."""
        input_level = abs(x)
        
        if input_level > self.envelope:
            # Attack
            self.envelope = (self.attack_coef * input_level + 
                           (1 - self.attack_coef) * self.envelope)
        else:
            # Release
            self.envelope = (self.release_coef * input_level + 
                           (1 - self.release_coef) * self.envelope)
        
        return self.envelope
    
    def process_block(self, audio: np.ndarray) -> np.ndarray:
        """Process block of samples, returning envelope."""
        envelope = np.zeros(len(audio))
        for i in range(len(audio)):
            envelope[i] = self.process_sample(audio[i])
        return envelope


# =============================================================================
# DYNAMIC EQ
# =============================================================================

class DynamicEQBand:
    """
    Single dynamic EQ band.
    
    Combines parametric EQ with dynamics processing for frequency-selective
    compression or expansion.
    """
    
    def __init__(self, params: DynamicEQBandParams, sample_rate: float):
        self.params = params
        self.sample_rate = sample_rate
        
        # Sidechain bandpass filter
        self.sc_filter_l = BiquadFilter()
        self.sc_filter_r = BiquadFilter()
        b, a = calculate_biquad_coefficients(
            FilterType.BANDPASS,
            params.frequency,
            sample_rate,
            q=params.q
        )
        self.sc_filter_l.set_coefficients(b, a)
        self.sc_filter_r.set_coefficients(b, a)
        
        # Envelope followers
        self.env_l = EnvelopeFollower(params.attack_ms, params.release_ms, sample_rate)
        self.env_r = EnvelopeFollower(params.attack_ms, params.release_ms, sample_rate)
        
        # Threshold in linear
        self.threshold_linear = 10 ** (params.threshold_db / 20)
        
        # Current EQ filters (gain modulated)
        self.eq_filter_l = BiquadFilter()
        self.eq_filter_r = BiquadFilter()
    
    def _compute_gain_db(self, envelope_linear: float) -> float:
        """Compute gain reduction/boost based on envelope."""
        if envelope_linear < 1e-10:
            return 0.0
        
        env_db = 20 * np.log10(envelope_linear)
        over_db = env_db - self.params.threshold_db
        
        # Soft knee
        knee_half = self.params.knee_db / 2
        
        if self.params.mode == DynamicMode.COMPRESS:
            if over_db <= -knee_half:
                return 0.0
            elif over_db >= knee_half:
                reduction = -over_db * (1 - 1/self.params.ratio)
                return max(reduction, self.params.max_gain_db)
            else:
                # In knee region
                knee_factor = (over_db + knee_half) / self.params.knee_db
                reduction = -over_db * (1 - 1/self.params.ratio) * knee_factor
                return max(reduction, self.params.max_gain_db)
        else:  # EXPAND
            if over_db >= knee_half:
                return 0.0
            elif over_db <= -knee_half:
                boost = abs(over_db) * (1 - 1/self.params.ratio)
                return min(boost, -self.params.max_gain_db)  # max_gain_db is negative
            else:
                knee_factor = (knee_half - over_db) / self.params.knee_db
                boost = abs(over_db) * (1 - 1/self.params.ratio) * knee_factor
                return min(boost, -self.params.max_gain_db)
    
    def process(self, audio: np.ndarray) -> np.ndarray:
        """
        Process audio with dynamic EQ.
        
        Args:
            audio: Input audio (mono or stereo)
            
        Returns:
            Processed audio
        """
        if not self.params.enabled:
            return audio
        
        is_mono = len(audio.shape) == 1
        if is_mono:
            audio = audio.reshape(-1, 1)
        
        output = np.zeros_like(audio)
        
        for i in range(len(audio)):
            # Sidechain: filter and detect envelope per channel
            sc_l = self.sc_filter_l.process_sample(audio[i, 0])
            env_l = self.env_l.process_sample(sc_l)
            
            if audio.shape[1] > 1:
                sc_r = self.sc_filter_r.process_sample(audio[i, 1])
                env_r = self.env_r.process_sample(sc_r)
                env_avg = (env_l + env_r) / 2
            else:
                env_avg = env_l
            
            # Compute gain
            gain_db = self._compute_gain_db(env_avg)
            
            # Update EQ coefficients with current gain
            b, a = calculate_biquad_coefficients(
                FilterType.PEAK,
                self.params.frequency,
                self.sample_rate,
                gain_db,
                self.params.q
            )
            self.eq_filter_l.set_coefficients(b, a)
            self.eq_filter_r.set_coefficients(b, a)
            
            # Apply EQ
            output[i, 0] = self.eq_filter_l.process_sample(audio[i, 0])
            if audio.shape[1] > 1:
                output[i, 1] = self.eq_filter_r.process_sample(audio[i, 1])
        
        return output.flatten() if is_mono else output


# =============================================================================
# HARMONIC EXCITER
# =============================================================================

def chebyshev_harmonic(x: np.ndarray, n: int) -> np.ndarray:
    """
    Generate nth harmonic using Chebyshev polynomial.
    
    T_n(cos(θ)) = cos(nθ), so T_n applied to a sine wave generates
    the nth harmonic.
    
    Args:
        x: Input signal (normalized to -1 to 1)
        n: Harmonic number (2=octave, 3=octave+fifth, etc.)
    """
    if n == 1:
        return x
    elif n == 2:
        return 2 * x**2 - 1
    elif n == 3:
        return 4 * x**3 - 3 * x
    elif n == 4:
        return 8 * x**4 - 8 * x**2 + 1
    elif n == 5:
        return 16 * x**5 - 20 * x**3 + 5 * x
    else:
        # Recursive: T_n = 2x*T_{n-1} - T_{n-2}
        t_prev2 = np.ones_like(x)
        t_prev1 = x.copy()
        for _ in range(2, n + 1):
            t_curr = 2 * x * t_prev1 - t_prev2
            t_prev2 = t_prev1
            t_prev1 = t_curr
        return t_prev1


def soft_saturate(x: np.ndarray, drive: float = 1.0) -> np.ndarray:
    """
    Soft saturation using tanh.
    Generates mostly odd harmonics (3rd, 5th, 7th...).
    """
    if drive <= 0:
        return x
    return np.tanh(x * drive)


def tube_saturate(x: np.ndarray, drive: float = 1.0, asymmetry: float = 0.2) -> np.ndarray:
    """
    Asymmetric saturation for tube-like even harmonics.
    
    Args:
        x: Input signal (normalized -1 to 1)
        drive: Saturation amount (1.0 = moderate)
        asymmetry: 0 = symmetric (odd only), higher = more even harmonics
    """
    if drive <= 0:
        return x
    
    # Different drive for positive and negative halves
    pos_drive = drive * (1 + asymmetry)
    neg_drive = drive * (1 - asymmetry)
    
    return np.where(x >= 0, 
                    np.tanh(x * pos_drive),
                    np.tanh(x * neg_drive))


class HarmonicExciter:
    """
    Multiband harmonic exciter/enhancer.
    
    Generates harmonics in different frequency bands for "warmth",
    "presence", and "air" enhancement.
    """
    
    def __init__(self, params: ExciterParams, sample_rate: float):
        self.params = params
        self.sample_rate = sample_rate
    
    def process(self, audio: np.ndarray) -> np.ndarray:
        """
        Apply harmonic excitation.
        
        Args:
            audio: Input audio (mono or stereo)
            
        Returns:
            Excited audio with added harmonics
        """
        if not self.params.enabled:
            return audio
        
        # Handle mono/stereo
        is_mono = len(audio.shape) == 1
        if is_mono:
            channels = [audio]
        else:
            channels = [audio[:, i] for i in range(audio.shape[1])]
        
        processed = []
        
        for channel in channels:
            # Band-split
            sos_low = butter(4, 200, 'low', fs=self.sample_rate, output='sos')
            sos_mid = butter(4, [200, 2000], 'band', fs=self.sample_rate, output='sos')
            sos_high = butter(4, [2000, self.params.air_freq], 'band', 
                            fs=self.sample_rate, output='sos')
            sos_air = butter(4, self.params.air_freq, 'high', 
                           fs=self.sample_rate, output='sos')
            
            low_band = sosfilt(sos_low, channel)
            mid_band = sosfilt(sos_mid, channel)
            high_band = sosfilt(sos_high, channel)
            air_band = sosfilt(sos_air, channel)
            
            # Normalize and saturate each band
            def process_band(band, drive, asymmetry=0.2):
                if drive <= 0:
                    return band
                peak = np.max(np.abs(band)) + 1e-10
                normalized = band / peak
                saturated = tube_saturate(normalized, drive, asymmetry)
                return saturated * peak
            
            low_sat = process_band(low_band, self.params.low_drive, 0.1)
            mid_sat = process_band(mid_band, self.params.mid_drive, 0.3)
            high_sat = process_band(high_band, self.params.high_drive, 0.2)
            air_sat = process_band(air_band, self.params.air_drive, 0.1)
            
            # Add explicit harmonics if requested
            if self.params.even_harmonics > 0 or self.params.odd_harmonics > 0:
                peak = np.max(np.abs(channel)) + 1e-10
                norm = channel / peak
                
                # Even harmonics (warm)
                h2 = chebyshev_harmonic(norm, 2)
                h4 = chebyshev_harmonic(norm, 4)
                even = self.params.even_harmonics * (h2 * 0.5 + h4 * 0.2) * peak * 0.15
                
                # Odd harmonics (edge)
                h3 = chebyshev_harmonic(norm, 3)
                h5 = chebyshev_harmonic(norm, 5)
                odd = self.params.odd_harmonics * (h3 * 0.4 + h5 * 0.15) * peak * 0.15
                
                # Add harmonics to high band
                high_sat = high_sat + even + odd
            
            # Sum bands
            wet = low_sat + mid_sat + high_sat + air_sat
            
            # Mix
            out = channel * (1 - self.params.mix) + wet * self.params.mix
            processed.append(out)
        
        if is_mono:
            return processed[0]
        return np.column_stack(processed)


# =============================================================================
# RESONANCE DETECTION AND SUPPRESSION
# =============================================================================

class ResonanceSuppressor:
    """
    Automatic resonance detection and suppression.
    
    Analyzes the spectrum to find narrow peaks (resonances) and
    applies adaptive notch filters to reduce them.
    """
    
    def __init__(self, params: ResonanceSuppressionParams, sample_rate: float):
        self.params = params
        self.sample_rate = sample_rate
        self.notch_filters: List[Tuple[BiquadFilter, BiquadFilter, float]] = []
        self._last_resonances: List[dict] = []
    
    def _detect_resonances(self, audio: np.ndarray) -> List[dict]:
        """Detect resonant peaks in spectrum."""
        if not HAS_SCIPY_FFT:
            return []
        
        # Use mono for analysis
        if len(audio.shape) > 1:
            mono = np.mean(audio, axis=1)
        else:
            mono = audio
        
        # Ensure we have enough samples
        if len(mono) < self.params.fft_size:
            mono = np.pad(mono, (0, self.params.fft_size - len(mono)))
        else:
            mono = mono[:self.params.fft_size]
        
        # Apply window and FFT
        window = np.hanning(self.params.fft_size)
        windowed = mono * window
        spectrum = rfft(windowed)
        frequencies = rfftfreq(self.params.fft_size, 1/self.sample_rate)
        
        # Magnitude in dB
        magnitude = np.abs(spectrum)
        magnitude_db = 20 * np.log10(magnitude + 1e-10)
        
        # Frequency resolution
        freq_resolution = frequencies[1] - frequencies[0]
        
        # Limit to analysis range
        freq_mask = ((frequencies >= self.params.frequency_range[0]) & 
                    (frequencies <= self.params.frequency_range[1]))
        freq_subset = frequencies[freq_mask]
        mag_subset = magnitude_db[freq_mask]
        
        # Find peaks
        prominence = 6.0 * self.params.sensitivity  # Higher sensitivity = lower threshold
        max_width_hz = 200
        max_width_bins = int(max_width_hz / freq_resolution)
        
        try:
            peaks, properties = find_peaks(
                mag_subset,
                prominence=prominence,
                width=(1, max_width_bins)
            )
        except Exception:
            return []
        
        # Build resonance list
        resonances = []
        for i, peak_idx in enumerate(peaks):
            freq = freq_subset[peak_idx]
            mag = mag_subset[peak_idx]
            
            width_bins = properties['widths'][i]
            width_hz = width_bins * freq_resolution
            q = freq / max(width_hz, 1)
            
            # Only include if Q exceeds threshold (narrow peaks)
            if q >= self.params.min_q:
                resonances.append({
                    'frequency': freq,
                    'magnitude_db': mag,
                    'q': min(q, 50.0),
                    'width_hz': width_hz,
                    'prominence_db': properties['prominences'][i]
                })
        
        # Sort by prominence and limit
        resonances.sort(key=lambda x: x['prominence_db'], reverse=True)
        return resonances[:self.params.max_bands]
    
    def _update_notch_filters(self, resonances: List[dict]):
        """Update notch filters based on detected resonances."""
        self.notch_filters = []
        
        for res in resonances:
            # Calculate reduction based on prominence
            reduction_db = -min(res['prominence_db'] * 0.5, 
                              abs(self.params.max_reduction_db))
            
            b, a = calculate_biquad_coefficients(
                FilterType.PEAK,
                res['frequency'],
                self.sample_rate,
                reduction_db,
                res['q']
            )
            
            filter_l = BiquadFilter()
            filter_r = BiquadFilter()
            filter_l.set_coefficients(b, a)
            filter_r.set_coefficients(b, a)
            
            self.notch_filters.append((filter_l, filter_r, res['frequency']))
    
    def process(self, audio: np.ndarray) -> np.ndarray:
        """
        Process audio with resonance suppression.
        
        Args:
            audio: Input audio
            
        Returns:
            Audio with resonances suppressed
        """
        if not self.params.enabled or not HAS_SCIPY_FFT:
            return audio
        
        # Detect resonances
        resonances = self._detect_resonances(audio)
        self._last_resonances = resonances
        
        if not resonances:
            return audio
        
        # Update notch filters
        self._update_notch_filters(resonances)
        
        # Apply filters
        output = audio.copy()
        is_mono = len(audio.shape) == 1
        
        for filter_l, filter_r, freq in self.notch_filters:
            if is_mono:
                output = filter_l.process_block(output)
            else:
                output[:, 0] = filter_l.process_block(output[:, 0])
                output[:, 1] = filter_r.process_block(output[:, 1])
        
        return output
    
    @property
    def detected_resonances(self) -> List[dict]:
        """Get the last detected resonances."""
        return self._last_resonances


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def apply_parametric_eq(audio: np.ndarray, 
                        bands: List[dict],
                        sample_rate: float = SAMPLE_RATE) -> np.ndarray:
    """
    Apply parametric EQ with simple band definitions.
    
    Args:
        audio: Input audio
        bands: List of band dicts with keys:
               type (str), frequency (float), gain_db (float), q (float)
        sample_rate: Sample rate
        
    Returns:
        Processed audio
    
    Example:
        bands = [
            {'type': 'low_shelf', 'frequency': 100, 'gain_db': 3, 'q': 0.7},
            {'type': 'peak', 'frequency': 1000, 'gain_db': -2, 'q': 2},
            {'type': 'high_shelf', 'frequency': 8000, 'gain_db': 2, 'q': 0.7},
        ]
        output = apply_parametric_eq(audio, bands)
    """
    output = audio.copy()
    
    for band in bands:
        # Parse filter type
        type_str = band.get('type', 'peak').lower().replace(' ', '_')
        filter_type = FilterType[type_str.upper()]
        
        frequency = band.get('frequency', 1000)
        gain_db = band.get('gain_db', 0)
        q = band.get('q', 1.0)
        
        if gain_db == 0 and filter_type in [FilterType.PEAK, 
                                             FilterType.LOW_SHELF, 
                                             FilterType.HIGH_SHELF]:
            continue
        
        b, a = calculate_biquad_coefficients(
            filter_type, frequency, sample_rate, gain_db, q
        )
        
        if len(output.shape) > 1:
            for ch in range(output.shape[1]):
                output[:, ch] = lfilter(b, a, output[:, ch])
        else:
            output = lfilter(b, a, output)
    
    return output


def apply_3band_eq(audio: np.ndarray,
                   low_gain_db: float = 0.0,
                   mid_gain_db: float = 0.0,
                   high_gain_db: float = 0.0,
                   low_freq: float = 200.0,
                   high_freq: float = 5000.0,
                   sample_rate: float = SAMPLE_RATE) -> np.ndarray:
    """
    Apply simple 3-band EQ.
    
    Args:
        audio: Input audio
        low_gain_db: Low band gain in dB
        mid_gain_db: Mid band gain in dB (peak at geometric mean of low/high)
        high_gain_db: High band gain in dB
        low_freq: Low shelf corner frequency
        high_freq: High shelf corner frequency
        sample_rate: Sample rate
        
    Returns:
        Processed audio
    """
    mid_freq = np.sqrt(low_freq * high_freq)  # Geometric mean
    
    bands = []
    if low_gain_db != 0:
        bands.append({'type': 'low_shelf', 'frequency': low_freq, 
                     'gain_db': low_gain_db, 'q': 0.7})
    if mid_gain_db != 0:
        bands.append({'type': 'peak', 'frequency': mid_freq, 
                     'gain_db': mid_gain_db, 'q': 0.7})
    if high_gain_db != 0:
        bands.append({'type': 'high_shelf', 'frequency': high_freq, 
                     'gain_db': high_gain_db, 'q': 0.7})
    
    if not bands:
        return audio
    
    return apply_parametric_eq(audio, bands, sample_rate)
