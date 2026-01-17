"""
Spectral Processing Suite

Professional-grade spectral processing tools for frequency-domain audio manipulation.
Provides Dynamic EQ, Resonance Suppression, Harmonic Excitement, and STFT framework.

Key Features:
- Dynamic EQ: Frequency-dependent compression/expansion
- Resonance Suppressor: Auto-detect and tame harsh frequencies (de-esser)
- Harmonic Exciter: Add warmth and air with controlled harmonic saturation
- STFT Framework: Base class for custom spectral processing

References:
- Sound On Sound: Dynamic EQ principles
- Waves Sibilance / FabFilter Pro-DS: De-essing algorithms
- Aphex Aural Exciter: Harmonic enhancement concepts

Author: Multimodal AI Music Generator
"""

import numpy as np
from dataclasses import dataclass, field
from typing import Optional, List, Tuple, Dict, Any
from scipy import signal
from scipy.fft import rfft, irfft, rfftfreq

from .utils import SAMPLE_RATE


# =============================================================================
# PARAMETER DATACLASSES
# =============================================================================

@dataclass
class DynamicEQBand:
    """
    Configuration for a single Dynamic EQ band.
    
    Dynamic EQ applies compression/expansion only to a specific frequency range,
    leaving the rest of the spectrum untouched.
    
    Attributes:
        frequency: Center frequency in Hz (20-20000)
        q: Bandwidth Q factor (0.1-10). Higher = narrower band.
        threshold_db: Level where gain reduction begins (-60 to 0 dB)
        ratio: Compression ratio (1.0 = no compression, 10.0 = limiting)
        attack_ms: Attack time in milliseconds (0.1-100)
        release_ms: Release time in milliseconds (10-1000)
        range_db: Maximum gain reduction/boost in dB (0-24)
        mode: "compress" reduces loud frequencies, "expand" boosts quiet ones
    """
    frequency: float = 1000.0
    q: float = 1.0
    threshold_db: float = -20.0
    ratio: float = 4.0
    attack_ms: float = 10.0
    release_ms: float = 100.0
    range_db: float = 12.0
    mode: str = "compress"  # "compress" or "expand"


@dataclass
class DynamicEQParams:
    """
    Parameters for the Dynamic EQ processor.
    
    Attributes:
        bands: List of DynamicEQBand configurations
        lookahead_ms: Lookahead time for catching transients (0-20ms)
        global_mix: Wet/dry mix (0.0-1.0)
    """
    bands: List[DynamicEQBand] = field(default_factory=list)
    lookahead_ms: float = 5.0
    global_mix: float = 1.0


@dataclass
class ResonanceSuppressorParams:
    """
    Parameters for Resonance Suppression (De-Esser / Harsh Frequency Tamer).
    
    Automatically detects and suppresses harsh resonant frequencies that
    stand out from the overall spectrum.
    
    Attributes:
        detection_mode: "auto" (detect peaks), "manual" (use fixed bands), 
                       "learn" (analyze and remember problematic frequencies)
        sensitivity: How aggressive detection is (0.0-1.0)
        max_reduction_db: Maximum gain reduction allowed (0-24 dB)
        frequency_range: Tuple of (low_hz, high_hz) to search for resonances
        attack_ms: Attack time (fast for catching sibilants)
        release_ms: Release time
        num_bands: Number of analysis bands within frequency range
        sidechain_filter: Apply highpass to detection signal
    """
    detection_mode: str = "auto"
    sensitivity: float = 0.5
    max_reduction_db: float = 12.0
    frequency_range: Tuple[float, float] = (2000.0, 10000.0)
    attack_ms: float = 1.0
    release_ms: float = 50.0
    num_bands: int = 8
    sidechain_filter: bool = True


@dataclass
class HarmonicExciterParams:
    """
    Parameters for Harmonic Exciter.
    
    Adds musical harmonic content through controlled saturation,
    enhancing presence and perceived loudness.
    
    Attributes:
        drive: Amount of harmonic generation (0.0-1.0)
        mix: Wet/dry mix for harmonics (0.0-1.0)
        frequency: Highpass frequency before saturation (500-8000 Hz)
        harmonics_type: "odd" (tube-like), "even" (tape-like), "both"
        air_boost_db: High shelf boost at 10kHz+ (0-6 dB)
        warmth_boost_db: Low shelf boost at 200Hz- (0-6 dB)
        output_gain_db: Output level compensation (-12 to +6 dB)
    """
    drive: float = 0.3
    mix: float = 0.5
    frequency: float = 3000.0
    harmonics_type: str = "odd"  # "odd", "even", "both"
    air_boost_db: float = 0.0
    warmth_boost_db: float = 0.0
    output_gain_db: float = 0.0


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def ms_to_samples(ms: float, sample_rate: int) -> int:
    """Convert milliseconds to samples."""
    return max(1, int(ms * sample_rate / 1000.0))


def db_to_linear(db: float) -> float:
    """Convert decibels to linear gain."""
    return 10.0 ** (db / 20.0)


def linear_to_db(linear: float) -> float:
    """Convert linear gain to decibels."""
    return 20.0 * np.log10(max(linear, 1e-10))


def calculate_envelope_coeff(time_ms: float, sample_rate: int) -> float:
    """Calculate one-pole filter coefficient for envelope follower."""
    time_samples = time_ms * sample_rate / 1000.0
    if time_samples <= 0:
        return 0.0
    return np.exp(-1.0 / time_samples)


def design_bandpass_filter(
    center_freq: float, 
    q: float, 
    sample_rate: int,
    order: int = 2
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Design a bandpass filter using cascaded butterworth sections.
    
    Args:
        center_freq: Center frequency in Hz
        q: Q factor (bandwidth = center_freq / q)
        sample_rate: Sample rate
        order: Filter order per section
    
    Returns:
        Tuple of (b, a) filter coefficients
    """
    nyquist = sample_rate / 2.0
    
    # Calculate bandwidth from Q
    bandwidth = center_freq / max(q, 0.1)
    low_freq = max(center_freq - bandwidth / 2, 20.0)
    high_freq = min(center_freq + bandwidth / 2, nyquist - 100)
    
    # Normalize frequencies
    low_norm = low_freq / nyquist
    high_norm = high_freq / nyquist
    
    # Clamp to valid range
    low_norm = np.clip(low_norm, 0.001, 0.999)
    high_norm = np.clip(high_norm, low_norm + 0.001, 0.999)
    
    b, a = signal.butter(order, [low_norm, high_norm], btype='band')
    return b, a


def design_highpass_filter(
    cutoff_freq: float,
    sample_rate: int,
    order: int = 2
) -> Tuple[np.ndarray, np.ndarray]:
    """Design a highpass Butterworth filter."""
    nyquist = sample_rate / 2.0
    normalized = np.clip(cutoff_freq / nyquist, 0.001, 0.999)
    b, a = signal.butter(order, normalized, btype='high')
    return b, a


def design_lowpass_filter(
    cutoff_freq: float,
    sample_rate: int,
    order: int = 2
) -> Tuple[np.ndarray, np.ndarray]:
    """Design a lowpass Butterworth filter."""
    nyquist = sample_rate / 2.0
    normalized = np.clip(cutoff_freq / nyquist, 0.001, 0.999)
    b, a = signal.butter(order, normalized, btype='low')
    return b, a


def design_peak_filter(
    center_freq: float,
    q: float,
    gain_db: float,
    sample_rate: int
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Design a peak/notch EQ filter (parametric EQ band).
    
    Based on Robert Bristow-Johnson's Audio EQ Cookbook.
    
    Args:
        center_freq: Center frequency in Hz
        q: Q factor
        gain_db: Gain in dB (positive = boost, negative = cut)
        sample_rate: Sample rate
    
    Returns:
        Tuple of (b, a) filter coefficients
    """
    A = 10.0 ** (gain_db / 40.0)  # sqrt of linear gain
    w0 = 2.0 * np.pi * center_freq / sample_rate
    cos_w0 = np.cos(w0)
    sin_w0 = np.sin(w0)
    alpha = sin_w0 / (2.0 * max(q, 0.1))
    
    b0 = 1.0 + alpha * A
    b1 = -2.0 * cos_w0
    b2 = 1.0 - alpha * A
    a0 = 1.0 + alpha / A
    a1 = -2.0 * cos_w0
    a2 = 1.0 - alpha / A
    
    # Normalize
    b = np.array([b0 / a0, b1 / a0, b2 / a0])
    a = np.array([1.0, a1 / a0, a2 / a0])
    
    return b, a


def design_shelf_filter(
    frequency: float,
    gain_db: float,
    sample_rate: int,
    shelf_type: str = 'high'
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Design a shelving filter.
    
    Args:
        frequency: Shelf frequency in Hz
        gain_db: Gain in dB
        sample_rate: Sample rate
        shelf_type: 'high' for high shelf, 'low' for low shelf
    
    Returns:
        Tuple of (b, a) filter coefficients
    """
    A = 10.0 ** (gain_db / 40.0)
    w0 = 2.0 * np.pi * frequency / sample_rate
    cos_w0 = np.cos(w0)
    sin_w0 = np.sin(w0)
    
    # Slope factor (0.5 = 6dB/oct, 1.0 = 12dB/oct)
    S = 1.0
    alpha = sin_w0 / 2.0 * np.sqrt((A + 1.0 / A) * (1.0 / S - 1.0) + 2.0)
    
    sqrt_A = np.sqrt(A)
    
    if shelf_type == 'high':
        b0 = A * ((A + 1) + (A - 1) * cos_w0 + 2 * sqrt_A * alpha)
        b1 = -2 * A * ((A - 1) + (A + 1) * cos_w0)
        b2 = A * ((A + 1) + (A - 1) * cos_w0 - 2 * sqrt_A * alpha)
        a0 = (A + 1) - (A - 1) * cos_w0 + 2 * sqrt_A * alpha
        a1 = 2 * ((A - 1) - (A + 1) * cos_w0)
        a2 = (A + 1) - (A - 1) * cos_w0 - 2 * sqrt_A * alpha
    else:  # low shelf
        b0 = A * ((A + 1) - (A - 1) * cos_w0 + 2 * sqrt_A * alpha)
        b1 = 2 * A * ((A - 1) - (A + 1) * cos_w0)
        b2 = A * ((A + 1) - (A - 1) * cos_w0 - 2 * sqrt_A * alpha)
        a0 = (A + 1) + (A - 1) * cos_w0 + 2 * sqrt_A * alpha
        a1 = -2 * ((A - 1) + (A + 1) * cos_w0)
        a2 = (A + 1) + (A - 1) * cos_w0 - 2 * sqrt_A * alpha
    
    b = np.array([b0 / a0, b1 / a0, b2 / a0])
    a = np.array([1.0, a1 / a0, a2 / a0])
    
    return b, a


def envelope_follower(
    audio: np.ndarray,
    attack_coeff: float,
    release_coeff: float
) -> np.ndarray:
    """
    Follow the envelope of an audio signal.
    
    Args:
        audio: Input audio (mono)
        attack_coeff: Attack coefficient (0-1)
        release_coeff: Release coefficient (0-1)
    
    Returns:
        Envelope signal
    """
    rectified = np.abs(audio)
    n_samples = len(rectified)
    envelope = np.zeros(n_samples)
    
    state = 0.0
    for i in range(n_samples):
        input_val = rectified[i]
        if input_val > state:
            state = attack_coeff * state + (1.0 - attack_coeff) * input_val
        else:
            state = release_coeff * state + (1.0 - release_coeff) * input_val
        envelope[i] = state
    
    return envelope


def soft_clip_tanh(x: np.ndarray, threshold: float = 0.9) -> np.ndarray:
    """Soft clip using tanh for smooth limiting."""
    output = np.copy(x)
    scale = 1.0 / (1.0 - threshold)
    
    pos_mask = x > threshold
    if np.any(pos_mask):
        over = (x[pos_mask] - threshold) * scale
        output[pos_mask] = threshold + (1.0 - threshold) * np.tanh(over)
    
    neg_mask = x < -threshold
    if np.any(neg_mask):
        over = (-x[neg_mask] - threshold) * scale
        output[neg_mask] = -threshold - (1.0 - threshold) * np.tanh(over)
    
    return output


# =============================================================================
# STFT PROCESSOR BASE CLASS
# =============================================================================

class STFTProcessor:
    """
    Base class for spectral domain processing using STFT.
    
    Provides analysis (audio → frequency) and synthesis (frequency → audio)
    with proper overlap-add reconstruction.
    
    Subclass this and override process_frame() for custom spectral processing.
    
    Attributes:
        fft_size: FFT window size (power of 2 recommended)
        hop_size: Hop between frames (typically fft_size // 4)
        window: Window function name or array
        sample_rate: Audio sample rate
    
    Example:
        >>> class MySpectralEffect(STFTProcessor):
        ...     def process_frame(self, frame):
        ...         # frame is complex array of frequency bins
        ...         return frame * 0.5  # Example: reduce magnitude
        >>> processor = MySpectralEffect()
        >>> processed = processor.process(audio)
    """
    
    def __init__(
        self,
        fft_size: int = 2048,
        hop_size: int = 512,
        window: str = 'hann',
        sample_rate: int = SAMPLE_RATE
    ):
        """
        Initialize STFT processor.
        
        Args:
            fft_size: FFT size (window length)
            hop_size: Hop size between frames
            window: Window function name ('hann', 'hamming', 'blackman')
            sample_rate: Sample rate in Hz
        """
        self.fft_size = fft_size
        self.hop_size = hop_size
        self.sample_rate = sample_rate
        
        # Create window function
        self.window = signal.get_window(window, fft_size)
        
        # Synthesis window for COLA (constant overlap-add)
        self.synthesis_window = self._create_synthesis_window()
    
    def _create_synthesis_window(self) -> np.ndarray:
        """
        Create synthesis window for perfect reconstruction.
        
        Uses overlap-add normalization so that windows sum to unity.
        """
        # For Hann window with 75% overlap (hop = fft/4), COLA is satisfied
        # For other configurations, normalize by sum of squared windows
        overlap = self.fft_size - self.hop_size
        num_overlaps = self.fft_size // self.hop_size
        
        # Calculate normalization factor
        sum_of_squares = np.zeros(self.hop_size)
        for i in range(num_overlaps):
            start = i * self.hop_size
            end = start + self.hop_size
            if end <= self.fft_size:
                sum_of_squares += self.window[start:end] ** 2
        
        # Avoid division by zero
        sum_of_squares = np.tile(sum_of_squares, num_overlaps)
        sum_of_squares = np.maximum(sum_of_squares, 1e-10)
        
        return self.window / sum_of_squares
    
    def analyze(self, audio: np.ndarray) -> np.ndarray:
        """
        Convert audio to STFT representation.
        
        Args:
            audio: Input audio (mono)
        
        Returns:
            Complex STFT array of shape (n_frames, n_bins)
        """
        n_samples = len(audio)
        n_frames = (n_samples - self.fft_size) // self.hop_size + 1
        n_bins = self.fft_size // 2 + 1
        
        stft = np.zeros((n_frames, n_bins), dtype=np.complex128)
        
        for i in range(n_frames):
            start = i * self.hop_size
            end = start + self.fft_size
            
            if end > n_samples:
                # Pad with zeros if needed
                frame = np.zeros(self.fft_size)
                frame[:n_samples - start] = audio[start:]
            else:
                frame = audio[start:end]
            
            # Apply analysis window and FFT
            windowed = frame * self.window
            stft[i] = rfft(windowed)
        
        return stft
    
    def synthesize(self, stft: np.ndarray, output_length: Optional[int] = None) -> np.ndarray:
        """
        Convert STFT back to audio using overlap-add.
        
        Args:
            stft: Complex STFT array of shape (n_frames, n_bins)
            output_length: Desired output length (trims/pads if specified)
        
        Returns:
            Reconstructed audio
        """
        n_frames, n_bins = stft.shape
        
        # Calculate output length
        length = self.fft_size + (n_frames - 1) * self.hop_size
        if output_length is not None:
            length = output_length
        
        output = np.zeros(length)
        
        for i in range(n_frames):
            start = i * self.hop_size
            end = start + self.fft_size
            
            # Inverse FFT
            frame = irfft(stft[i], n=self.fft_size)
            
            # Apply synthesis window
            frame = frame * self.synthesis_window
            
            # Overlap-add
            if end <= length:
                output[start:end] += frame
            else:
                remaining = length - start
                if remaining > 0:
                    output[start:length] += frame[:remaining]
        
        return output
    
    def process_frame(self, frame: np.ndarray) -> np.ndarray:
        """
        Process a single STFT frame. Override in subclasses.
        
        Args:
            frame: Complex frequency bin array
        
        Returns:
            Processed complex frequency bin array
        """
        return frame  # Pass-through by default
    
    def process(self, audio: np.ndarray) -> np.ndarray:
        """
        Process audio through STFT → process_frame → synthesis.
        
        Handles stereo by processing channels independently.
        
        Args:
            audio: Input audio (mono or stereo)
        
        Returns:
            Processed audio
        """
        is_stereo = len(audio.shape) > 1 and audio.shape[1] == 2
        
        if is_stereo:
            left = self._process_mono(audio[:, 0])
            right = self._process_mono(audio[:, 1])
            return np.column_stack([left, right])
        else:
            return self._process_mono(audio)
    
    def _process_mono(self, audio: np.ndarray) -> np.ndarray:
        """Process mono audio through STFT pipeline."""
        original_length = len(audio)
        
        # Analyze
        stft = self.analyze(audio)
        
        # Process each frame
        for i in range(stft.shape[0]):
            stft[i] = self.process_frame(stft[i])
        
        # Synthesize
        output = self.synthesize(stft, original_length)
        
        return output
    
    def get_frequency_bins(self) -> np.ndarray:
        """Get the frequency values for each STFT bin."""
        return rfftfreq(self.fft_size, 1.0 / self.sample_rate)


# =============================================================================
# DYNAMIC EQ PROCESSOR
# =============================================================================

class DynamicEQ:
    """
    Dynamic EQ - Frequency-dependent compression/expansion.
    
    Unlike static EQ, Dynamic EQ only applies gain changes when the
    signal in a frequency band exceeds (or falls below) a threshold.
    This allows surgical frequency control without affecting quieter content.
    
    Algorithm:
    1. For each band, extract the frequency content using bandpass filter
    2. Track the envelope of that band
    3. Calculate gain reduction based on envelope vs threshold
    4. Apply the gain to just that frequency band
    5. Sum all bands back together
    
    Usage:
        >>> params = DynamicEQParams(bands=[
        ...     DynamicEQBand(frequency=6000, threshold_db=-20, ratio=4.0),
        ...     DynamicEQBand(frequency=200, threshold_db=-10, ratio=2.0, mode="expand")
        ... ])
        >>> eq = DynamicEQ(params, sample_rate=44100)
        >>> processed = eq.process(audio)
    """
    
    def __init__(self, params: DynamicEQParams, sample_rate: int = SAMPLE_RATE):
        """
        Initialize Dynamic EQ.
        
        Args:
            params: DynamicEQParams configuration
            sample_rate: Audio sample rate
        """
        self.params = params
        self.sample_rate = sample_rate
        
        # Pre-compute filter coefficients for each band
        self.band_filters = []
        self.band_envelopes = []
        
        for band in params.bands:
            # Bandpass filter for isolation
            bp_b, bp_a = design_bandpass_filter(
                band.frequency, band.q, sample_rate
            )
            
            # Envelope coefficients
            attack_coeff = calculate_envelope_coeff(band.attack_ms, sample_rate)
            release_coeff = calculate_envelope_coeff(band.release_ms, sample_rate)
            
            self.band_filters.append({
                'bp_b': bp_b,
                'bp_a': bp_a,
                'attack_coeff': attack_coeff,
                'release_coeff': release_coeff,
                'band': band
            })
        
        # Lookahead
        self.lookahead_samples = ms_to_samples(params.lookahead_ms, sample_rate)
        
        # Gain smoothing
        self.gain_smooth_coeff = calculate_envelope_coeff(2.0, sample_rate)
    
    def process(self, audio: np.ndarray) -> np.ndarray:
        """
        Process audio through Dynamic EQ.
        
        Args:
            audio: Input audio (mono or stereo)
        
        Returns:
            Processed audio
        """
        if len(audio) == 0 or len(self.band_filters) == 0:
            return audio
        
        is_stereo = len(audio.shape) > 1 and audio.shape[1] == 2
        
        if is_stereo:
            left = self._process_mono(audio[:, 0])
            right = self._process_mono(audio[:, 1])
            return np.column_stack([left, right])
        else:
            return self._process_mono(audio)
    
    def _process_mono(self, audio: np.ndarray) -> np.ndarray:
        """Process mono audio through Dynamic EQ."""
        n_samples = len(audio)
        output = np.copy(audio)
        
        for filt in self.band_filters:
            band = filt['band']
            
            # Extract band content
            band_signal = signal.lfilter(filt['bp_b'], filt['bp_a'], audio)
            
            # Get envelope of band
            band_env = envelope_follower(
                band_signal,
                filt['attack_coeff'],
                filt['release_coeff']
            )
            
            # Apply lookahead
            if self.lookahead_samples > 0:
                band_env = np.concatenate([
                    band_env[self.lookahead_samples:],
                    np.zeros(self.lookahead_samples)
                ])
            
            # Calculate gain reduction
            gain = self._calculate_gain(band_env, band)
            
            # Smooth gain
            gain = self._smooth_gain(gain)
            
            # Apply gain only to the band
            band_processed = band_signal * gain
            
            # Replace band in output
            # Subtract original band, add processed band
            output = output - band_signal + band_processed
        
        # Apply global mix
        if self.params.global_mix < 1.0:
            output = audio * (1.0 - self.params.global_mix) + output * self.params.global_mix
        
        return output
    
    def _calculate_gain(self, envelope: np.ndarray, band: DynamicEQBand) -> np.ndarray:
        """Calculate gain based on envelope and compression settings."""
        threshold_linear = db_to_linear(band.threshold_db)
        max_reduction = db_to_linear(-band.range_db)
        
        if band.mode == "compress":
            # Compress: reduce gain when envelope exceeds threshold
            ratio = max(band.ratio, 1.0)
            
            gain = np.ones_like(envelope)
            above_threshold = envelope > threshold_linear
            
            if np.any(above_threshold):
                # Calculate compression
                over_db = 20.0 * np.log10(
                    envelope[above_threshold] / threshold_linear + 1e-10
                )
                gain_reduction_db = over_db * (1.0 - 1.0 / ratio)
                gain_reduction_db = np.minimum(gain_reduction_db, band.range_db)
                
                gain[above_threshold] = db_to_linear(-gain_reduction_db)
        
        else:  # expand
            # Expand: boost when envelope is below threshold
            ratio = max(band.ratio, 1.0)
            
            gain = np.ones_like(envelope)
            below_threshold = envelope < threshold_linear
            
            if np.any(below_threshold):
                # Calculate expansion
                under_db = 20.0 * np.log10(
                    threshold_linear / (envelope[below_threshold] + 1e-10)
                )
                gain_boost_db = under_db * (ratio - 1.0) / ratio
                gain_boost_db = np.minimum(gain_boost_db, band.range_db)
                
                gain[below_threshold] = db_to_linear(gain_boost_db)
        
        return gain
    
    def _smooth_gain(self, gain: np.ndarray) -> np.ndarray:
        """Smooth gain envelope to prevent clicks."""
        n_samples = len(gain)
        smoothed = np.zeros(n_samples)
        state = gain[0] if n_samples > 0 else 1.0
        
        for i in range(n_samples):
            state = self.gain_smooth_coeff * state + (1.0 - self.gain_smooth_coeff) * gain[i]
            smoothed[i] = state
        
        return smoothed


# =============================================================================
# RESONANCE SUPPRESSOR (DE-ESSER / HARSH FREQUENCY TAMER)
# =============================================================================

class ResonanceSuppressor:
    """
    Resonance Suppressor - Auto-detect and tame harsh frequencies.
    
    Functions as a smart de-esser that can automatically find and suppress
    resonant frequencies that stand out harshly from the spectrum.
    
    Algorithm:
    1. Divide frequency range into analysis bands
    2. For each band, track the energy relative to neighboring bands
    3. When a band exceeds neighbors by sensitivity threshold, reduce it
    4. Apply smooth gain reduction to avoid artifacts
    
    Usage:
        >>> params = ResonanceSuppressorParams(
        ...     sensitivity=0.6,
        ...     frequency_range=(2000, 10000)
        ... )
        >>> suppressor = ResonanceSuppressor(params, sample_rate=44100)
        >>> processed = suppressor.process(audio)
    """
    
    def __init__(self, params: ResonanceSuppressorParams, sample_rate: int = SAMPLE_RATE):
        """
        Initialize Resonance Suppressor.
        
        Args:
            params: ResonanceSuppressorParams configuration
            sample_rate: Audio sample rate
        """
        self.params = params
        self.sample_rate = sample_rate
        
        # Calculate band frequencies (logarithmic spacing)
        low_hz, high_hz = params.frequency_range
        self.band_freqs = np.geomspace(low_hz, high_hz, params.num_bands + 1)
        self.band_centers = np.sqrt(self.band_freqs[:-1] * self.band_freqs[1:])
        
        # Design bandpass filters for each band
        self.band_filters = []
        for i in range(params.num_bands):
            center = self.band_centers[i]
            bandwidth = self.band_freqs[i + 1] - self.band_freqs[i]
            q = center / max(bandwidth, 1.0)
            q = np.clip(q, 0.5, 10.0)
            
            bp_b, bp_a = design_bandpass_filter(center, q, sample_rate)
            
            # Peak filter for reduction (used when applying gain)
            # This allows more surgical cuts
            
            self.band_filters.append({
                'center': center,
                'q': q,
                'bp_b': bp_b,
                'bp_a': bp_a
            })
        
        # Envelope settings
        self.attack_coeff = calculate_envelope_coeff(params.attack_ms, sample_rate)
        self.release_coeff = calculate_envelope_coeff(params.release_ms, sample_rate)
        
        # Sidechain highpass
        if params.sidechain_filter:
            self.sidechain_b, self.sidechain_a = design_highpass_filter(
                params.frequency_range[0] * 0.5, sample_rate
            )
        else:
            self.sidechain_b = self.sidechain_a = None
        
        # Max reduction in linear
        self.max_reduction = db_to_linear(-params.max_reduction_db)
        
        # Detection threshold based on sensitivity
        # Higher sensitivity = lower threshold = more aggressive
        self.detection_threshold = 1.5 + (1.0 - params.sensitivity) * 3.0
        
        # Learned resonances (for "learn" mode)
        self.learned_resonances: List[Tuple[float, float]] = []
    
    def process(self, audio: np.ndarray) -> np.ndarray:
        """
        Process audio through Resonance Suppressor.
        
        Args:
            audio: Input audio (mono or stereo)
        
        Returns:
            Processed audio
        """
        if len(audio) == 0:
            return audio
        
        is_stereo = len(audio.shape) > 1 and audio.shape[1] == 2
        
        if is_stereo:
            left = self._process_mono(audio[:, 0])
            right = self._process_mono(audio[:, 1])
            return np.column_stack([left, right])
        else:
            return self._process_mono(audio)
    
    def _process_mono(self, audio: np.ndarray) -> np.ndarray:
        """Process mono audio through Resonance Suppressor."""
        n_samples = len(audio)
        
        # Apply sidechain filter for detection
        if self.sidechain_b is not None:
            detection_signal = signal.lfilter(self.sidechain_b, self.sidechain_a, audio)
        else:
            detection_signal = audio
        
        # Get envelope for each band
        band_envelopes = []
        band_signals = []
        
        for filt in self.band_filters:
            band_signal = signal.lfilter(filt['bp_b'], filt['bp_a'], detection_signal)
            band_env = envelope_follower(band_signal, self.attack_coeff, self.release_coeff)
            
            band_signals.append(band_signal)
            band_envelopes.append(band_env)
        
        band_envelopes = np.array(band_envelopes)  # Shape: (num_bands, n_samples)
        
        # Calculate average envelope (for relative comparison)
        avg_envelope = np.mean(band_envelopes, axis=0)
        
        # Calculate gain for each band based on relative level
        output = np.copy(audio)
        
        for i, (filt, band_signal) in enumerate(zip(self.band_filters, band_signals)):
            band_env = band_envelopes[i]
            
            # Calculate how much this band exceeds the average
            ratio = band_env / (avg_envelope + 1e-10)
            
            # Apply reduction when ratio exceeds threshold
            gain = np.ones(n_samples)
            exceeds = ratio > self.detection_threshold
            
            if np.any(exceeds):
                # Calculate reduction
                excess = ratio[exceeds] / self.detection_threshold
                reduction_db = np.minimum(
                    20.0 * np.log10(excess),
                    self.params.max_reduction_db
                )
                gain[exceeds] = db_to_linear(-reduction_db * self.params.sensitivity)
                gain[exceeds] = np.maximum(gain[exceeds], self.max_reduction)
            
            # Smooth the gain
            gain = self._smooth_gain(gain)
            
            # Apply reduction to the band
            # Subtract original, add reduced
            output = output - band_signal + band_signal * gain
        
        return output
    
    def _smooth_gain(self, gain: np.ndarray) -> np.ndarray:
        """Smooth gain to prevent clicks."""
        n_samples = len(gain)
        smoothed = np.zeros(n_samples)
        smooth_coeff = calculate_envelope_coeff(1.0, self.sample_rate)
        
        state = gain[0] if n_samples > 0 else 1.0
        for i in range(n_samples):
            state = smooth_coeff * state + (1.0 - smooth_coeff) * gain[i]
            smoothed[i] = state
        
        return smoothed
    
    def learn(self, audio: np.ndarray) -> List[Tuple[float, float]]:
        """
        Analyze audio to learn problematic resonances.
        
        Args:
            audio: Audio to analyze
        
        Returns:
            List of (frequency, severity) tuples
        """
        if len(audio.shape) > 1:
            mono = np.mean(audio, axis=1)
        else:
            mono = audio
        
        # Analyze spectrum
        frequencies = rfftfreq(len(mono), 1.0 / self.sample_rate)
        spectrum = np.abs(rfft(mono))
        
        # Find peaks that stand out
        low_idx = np.searchsorted(frequencies, self.params.frequency_range[0])
        high_idx = np.searchsorted(frequencies, self.params.frequency_range[1])
        
        search_spectrum = spectrum[low_idx:high_idx]
        search_freqs = frequencies[low_idx:high_idx]
        
        # Find peaks
        peaks, properties = signal.find_peaks(
            search_spectrum,
            prominence=np.std(search_spectrum) * (1.5 - self.params.sensitivity)
        )
        
        resonances = []
        for peak in peaks:
            freq = search_freqs[peak]
            severity = search_spectrum[peak] / np.median(search_spectrum)
            resonances.append((freq, severity))
        
        self.learned_resonances = resonances
        return resonances


# =============================================================================
# HARMONIC EXCITER
# =============================================================================

class HarmonicExciter:
    """
    Harmonic Exciter - Add warmth and presence through controlled saturation.
    
    Generates musical harmonic content by:
    1. Isolating high frequencies (to prevent bass mud)
    2. Applying waveshaping saturation
    3. Mixing harmonics back with original
    4. Optional air/warmth shelving EQ
    
    Harmonic types:
    - Odd harmonics (3rd, 5th, 7th): Tube-like, aggressive
    - Even harmonics (2nd, 4th, 6th): Tape-like, warm
    - Both: Rich, full saturation
    
    Usage:
        >>> params = HarmonicExciterParams(
        ...     drive=0.4,
        ...     harmonics_type="even",
        ...     warmth_boost_db=2.0
        ... )
        >>> exciter = HarmonicExciter(params, sample_rate=44100)
        >>> processed = exciter.process(audio)
    """
    
    def __init__(self, params: HarmonicExciterParams, sample_rate: int = SAMPLE_RATE):
        """
        Initialize Harmonic Exciter.
        
        Args:
            params: HarmonicExciterParams configuration
            sample_rate: Audio sample rate
        """
        self.params = params
        self.sample_rate = sample_rate
        
        # Highpass filter before saturation (isolate highs)
        self.hp_b, self.hp_a = design_highpass_filter(
            params.frequency, sample_rate, order=2
        )
        
        # Air boost shelf (high shelf at 10kHz)
        if params.air_boost_db != 0:
            self.air_b, self.air_a = design_shelf_filter(
                10000.0, params.air_boost_db, sample_rate, 'high'
            )
        else:
            self.air_b = self.air_a = None
        
        # Warmth boost shelf (low shelf at 200Hz)
        if params.warmth_boost_db != 0:
            self.warmth_b, self.warmth_a = design_shelf_filter(
                200.0, params.warmth_boost_db, sample_rate, 'low'
            )
        else:
            self.warmth_b = self.warmth_a = None
        
        # Output gain
        self.output_gain = db_to_linear(params.output_gain_db)
        
        # Drive amount (scale for saturation)
        self.drive = np.clip(params.drive, 0.0, 1.0)
        self.mix = np.clip(params.mix, 0.0, 1.0)
    
    def process(self, audio: np.ndarray) -> np.ndarray:
        """
        Process audio through Harmonic Exciter.
        
        Args:
            audio: Input audio (mono or stereo)
        
        Returns:
            Processed audio with added harmonics
        """
        if len(audio) == 0:
            return audio
        
        is_stereo = len(audio.shape) > 1 and audio.shape[1] == 2
        
        if is_stereo:
            left = self._process_mono(audio[:, 0])
            right = self._process_mono(audio[:, 1])
            output = np.column_stack([left, right])
        else:
            output = self._process_mono(audio)
        
        return output
    
    def _process_mono(self, audio: np.ndarray) -> np.ndarray:
        """Process mono audio through Harmonic Exciter."""
        # Start with dry signal
        dry = audio
        
        # Isolate highs for harmonic generation
        highs = signal.lfilter(self.hp_b, self.hp_a, audio)
        
        # Apply drive/pre-gain
        drive_gain = 1.0 + self.drive * 10.0  # Scale drive for saturation
        driven = highs * drive_gain
        
        # Apply waveshaping based on harmonic type
        if self.params.harmonics_type == "odd":
            saturated = self._odd_harmonics(driven)
        elif self.params.harmonics_type == "even":
            saturated = self._even_harmonics(driven)
        else:  # both
            odd = self._odd_harmonics(driven)
            even = self._even_harmonics(driven)
            saturated = (odd + even) * 0.5
        
        # Normalize saturated signal
        saturated = saturated / drive_gain
        
        # Extract only the new harmonics (subtract the original highs)
        harmonics = saturated - highs
        
        # Mix harmonics with dry signal
        wet = dry + harmonics * self.mix
        
        # Apply air boost
        if self.air_b is not None:
            wet = signal.lfilter(self.air_b, self.air_a, wet)
        
        # Apply warmth boost
        if self.warmth_b is not None:
            wet = signal.lfilter(self.warmth_b, self.warmth_a, wet)
        
        # Apply output gain
        output = wet * self.output_gain
        
        # Soft clip to prevent overs
        output = soft_clip_tanh(output, 0.95)
        
        return output
    
    def _odd_harmonics(self, x: np.ndarray) -> np.ndarray:
        """
        Generate odd harmonics using tanh saturation.
        
        Tanh produces primarily odd harmonics (3rd, 5th, 7th, etc.)
        giving a tube-like character.
        """
        return np.tanh(x)
    
    def _even_harmonics(self, x: np.ndarray) -> np.ndarray:
        """
        Generate even harmonics using asymmetric saturation.
        
        Soft asymmetric clipping produces even harmonics (2nd, 4th, 6th)
        giving a tape-like warmth.
        """
        # Asymmetric soft clipping
        # Positive half: tanh
        # Negative half: less saturation
        positive = np.maximum(x, 0)
        negative = np.minimum(x, 0)
        
        return np.tanh(positive * 1.2) + np.tanh(negative * 0.8)


# =============================================================================
# SPECTRUM ANALYZER
# =============================================================================

class SpectrumAnalyzer:
    """
    Spectrum analysis utility for frequency domain insights.
    
    Provides tools for analyzing spectral content, finding peaks,
    calculating spectral balance, and more.
    
    Usage:
        >>> analyzer = SpectrumAnalyzer(sample_rate=44100)
        >>> analysis = analyzer.analyze(audio)
        >>> print(analysis['peak_frequencies'])
    """
    
    def __init__(self, sample_rate: int = SAMPLE_RATE, fft_size: int = 4096):
        """
        Initialize Spectrum Analyzer.
        
        Args:
            sample_rate: Audio sample rate
            fft_size: FFT size for analysis
        """
        self.sample_rate = sample_rate
        self.fft_size = fft_size
        self.window = signal.get_window('hann', fft_size)
    
    def analyze(self, audio: np.ndarray) -> Dict[str, Any]:
        """
        Comprehensive spectrum analysis.
        
        Args:
            audio: Input audio
        
        Returns:
            Dictionary with analysis results
        """
        # Convert to mono for analysis
        if len(audio.shape) > 1:
            mono = np.mean(audio, axis=1)
        else:
            mono = audio
        
        # Get frequency axis
        frequencies = rfftfreq(self.fft_size, 1.0 / self.sample_rate)
        
        # Calculate average spectrum over the whole signal
        n_frames = len(mono) // self.fft_size
        if n_frames < 1:
            # Pad short signals
            padded = np.zeros(self.fft_size)
            padded[:len(mono)] = mono
            spectrum = np.abs(rfft(padded * self.window))
            n_frames = 1
        else:
            spectra = []
            for i in range(n_frames):
                start = i * self.fft_size
                frame = mono[start:start + self.fft_size] * self.window
                spectra.append(np.abs(rfft(frame)))
            spectrum = np.mean(spectra, axis=0)
        
        # Convert to dB
        spectrum_db = 20.0 * np.log10(spectrum + 1e-10)
        
        # Find peaks
        peaks, properties = signal.find_peaks(
            spectrum_db,
            prominence=6.0,  # At least 6dB prominence
            distance=10      # At least 10 bins apart
        )
        
        peak_frequencies = frequencies[peaks].tolist()
        peak_magnitudes = spectrum_db[peaks].tolist()
        
        # Calculate spectral centroid (brightness)
        total_energy = np.sum(spectrum ** 2)
        if total_energy > 0:
            centroid = np.sum(frequencies * spectrum ** 2) / total_energy
        else:
            centroid = 0.0
        
        # Calculate spectral rolloff (95% of energy)
        cumulative_energy = np.cumsum(spectrum ** 2)
        rolloff_idx = np.searchsorted(cumulative_energy, total_energy * 0.95)
        rolloff = frequencies[min(rolloff_idx, len(frequencies) - 1)]
        
        # Calculate band energies
        bands = {
            'sub_bass': (20, 60),
            'bass': (60, 250),
            'low_mid': (250, 500),
            'mid': (500, 2000),
            'high_mid': (2000, 4000),
            'presence': (4000, 8000),
            'brilliance': (8000, 20000)
        }
        
        band_energies = {}
        for name, (low, high) in bands.items():
            low_idx = np.searchsorted(frequencies, low)
            high_idx = np.searchsorted(frequencies, high)
            band_energy = np.sum(spectrum[low_idx:high_idx] ** 2)
            band_energies[name] = 10.0 * np.log10(band_energy + 1e-10)
        
        # Calculate spectral flatness (tonality measure)
        # Geometric mean / arithmetic mean
        geometric_mean = np.exp(np.mean(np.log(spectrum + 1e-10)))
        arithmetic_mean = np.mean(spectrum)
        flatness = geometric_mean / (arithmetic_mean + 1e-10)
        
        return {
            'frequencies': frequencies.tolist(),
            'magnitude_db': spectrum_db.tolist(),
            'peak_frequencies': peak_frequencies,
            'peak_magnitudes': peak_magnitudes,
            'spectral_centroid_hz': float(centroid),
            'spectral_rolloff_hz': float(rolloff),
            'band_energies_db': band_energies,
            'spectral_flatness': float(flatness),
            'is_tonal': flatness < 0.1,  # Low flatness = tonal
            'is_noisy': flatness > 0.5   # High flatness = noisy
        }


# =============================================================================
# PRESETS
# =============================================================================

SPECTRAL_PRESETS: Dict[str, Any] = {
    # De-esser presets
    "de_esser": DynamicEQParams(bands=[
        DynamicEQBand(frequency=6000, q=2.0, threshold_db=-25, ratio=6.0, 
                      attack_ms=1.0, release_ms=50.0, range_db=10.0),
        DynamicEQBand(frequency=8000, q=2.0, threshold_db=-25, ratio=4.0,
                      attack_ms=1.0, release_ms=50.0, range_db=8.0),
    ]),
    
    "de_esser_aggressive": DynamicEQParams(bands=[
        DynamicEQBand(frequency=5500, q=1.5, threshold_db=-30, ratio=8.0,
                      attack_ms=0.5, release_ms=30.0, range_db=15.0),
        DynamicEQBand(frequency=7500, q=1.5, threshold_db=-28, ratio=6.0,
                      attack_ms=0.5, release_ms=30.0, range_db=12.0),
        DynamicEQBand(frequency=9500, q=2.0, threshold_db=-30, ratio=4.0,
                      attack_ms=0.5, release_ms=30.0, range_db=10.0),
    ]),
    
    # Resonance suppression presets
    "harsh_tamer": ResonanceSuppressorParams(
        sensitivity=0.6,
        frequency_range=(2500, 8000),
        max_reduction_db=10.0,
        attack_ms=2.0,
        release_ms=80.0,
        num_bands=6
    ),
    
    "mud_cleaner": ResonanceSuppressorParams(
        sensitivity=0.5,
        frequency_range=(200, 500),
        max_reduction_db=8.0,
        attack_ms=10.0,
        release_ms=100.0,
        num_bands=4
    ),
    
    # Harmonic exciter presets
    "vocal_presence": HarmonicExciterParams(
        drive=0.2,
        mix=0.4,
        frequency=2500,
        harmonics_type="odd",
        air_boost_db=2.0,
        warmth_boost_db=0.0
    ),
    
    "tape_warmth": HarmonicExciterParams(
        drive=0.4,
        mix=0.5,
        frequency=1000,
        harmonics_type="even",
        air_boost_db=0.0,
        warmth_boost_db=2.0
    ),
    
    "master_air": HarmonicExciterParams(
        drive=0.15,
        mix=0.3,
        frequency=5000,
        harmonics_type="odd",
        air_boost_db=3.0,
        warmth_boost_db=0.0
    ),
    
    "analog_warmth": HarmonicExciterParams(
        drive=0.3,
        mix=0.4,
        frequency=800,
        harmonics_type="both",
        air_boost_db=1.0,
        warmth_boost_db=2.5
    ),
    
    "radio_ready": HarmonicExciterParams(
        drive=0.25,
        mix=0.35,
        frequency=3000,
        harmonics_type="odd",
        air_boost_db=2.5,
        warmth_boost_db=1.0,
        output_gain_db=1.0
    ),
}


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def dynamic_eq(
    audio: np.ndarray,
    bands: List[DynamicEQBand],
    sample_rate: int = SAMPLE_RATE
) -> np.ndarray:
    """
    Apply Dynamic EQ with specified bands.
    
    Args:
        audio: Input audio
        bands: List of DynamicEQBand configurations
        sample_rate: Audio sample rate
    
    Returns:
        Processed audio
    
    Example:
        >>> bands = [
        ...     DynamicEQBand(frequency=6000, threshold_db=-20, ratio=4.0),
        ...     DynamicEQBand(frequency=200, threshold_db=-15, ratio=3.0)
        ... ]
        >>> processed = dynamic_eq(audio, bands)
    """
    params = DynamicEQParams(bands=bands)
    eq = DynamicEQ(params, sample_rate)
    return eq.process(audio)


def suppress_resonances(
    audio: np.ndarray,
    sensitivity: float = 0.5,
    frequency_range: Tuple[float, float] = (2000, 10000),
    sample_rate: int = SAMPLE_RATE
) -> np.ndarray:
    """
    Auto-detect and suppress harsh resonances.
    
    Args:
        audio: Input audio
        sensitivity: Detection sensitivity (0.0-1.0)
        frequency_range: Tuple of (low_hz, high_hz) to search
        sample_rate: Audio sample rate
    
    Returns:
        Processed audio with suppressed resonances
    
    Example:
        >>> # Tame harsh vocals
        >>> smooth_vocal = suppress_resonances(vocal, sensitivity=0.6)
    """
    params = ResonanceSuppressorParams(
        sensitivity=sensitivity,
        frequency_range=frequency_range,
        detection_mode="auto"
    )
    suppressor = ResonanceSuppressor(params, sample_rate)
    return suppressor.process(audio)


def add_harmonics(
    audio: np.ndarray,
    drive: float = 0.3,
    frequency: float = 3000.0,
    harmonics_type: str = "odd",
    sample_rate: int = SAMPLE_RATE
) -> np.ndarray:
    """
    Add harmonic excitement to audio.
    
    Args:
        audio: Input audio
        drive: Harmonic generation amount (0.0-1.0)
        frequency: Highpass frequency before saturation
        harmonics_type: "odd", "even", or "both"
        sample_rate: Audio sample rate
    
    Returns:
        Processed audio with added harmonics
    
    Example:
        >>> # Add tube-like warmth
        >>> warm_audio = add_harmonics(audio, drive=0.4, harmonics_type="even")
    """
    params = HarmonicExciterParams(
        drive=drive,
        mix=0.5,
        frequency=frequency,
        harmonics_type=harmonics_type
    )
    exciter = HarmonicExciter(params, sample_rate)
    return exciter.process(audio)


def analyze_spectrum(
    audio: np.ndarray,
    sample_rate: int = SAMPLE_RATE
) -> Dict[str, Any]:
    """
    Analyze audio spectrum and return frequency characteristics.
    
    Args:
        audio: Input audio
        sample_rate: Audio sample rate
    
    Returns:
        Dictionary with spectral analysis:
        - peak_frequencies: List of dominant frequencies
        - spectral_centroid_hz: Brightness indicator
        - band_energies_db: Energy in each frequency band
        - is_tonal: True if signal is tonal
        - is_noisy: True if signal is noisy
    
    Example:
        >>> analysis = analyze_spectrum(audio)
        >>> print(f"Brightness: {analysis['spectral_centroid_hz']} Hz")
    """
    analyzer = SpectrumAnalyzer(sample_rate)
    return analyzer.analyze(audio)


def apply_spectral_preset(
    audio: np.ndarray,
    preset_name: str,
    sample_rate: int = SAMPLE_RATE
) -> np.ndarray:
    """
    Apply a named spectral processing preset.
    
    Args:
        audio: Input audio
        preset_name: Name of preset from SPECTRAL_PRESETS
        sample_rate: Audio sample rate
    
    Returns:
        Processed audio
    
    Available presets:
        - de_esser: Standard de-essing
        - de_esser_aggressive: Heavy de-essing
        - harsh_tamer: Reduce harsh high frequencies
        - mud_cleaner: Clean up muddy low-mids
        - vocal_presence: Add vocal clarity
        - tape_warmth: Warm analog character
        - master_air: Add high-end sparkle
        - analog_warmth: Full analog character
        - radio_ready: Broadcast-ready enhancement
    
    Example:
        >>> de_essed = apply_spectral_preset(vocal, "de_esser")
    """
    if preset_name not in SPECTRAL_PRESETS:
        available = ', '.join(SPECTRAL_PRESETS.keys())
        raise ValueError(f"Unknown preset: {preset_name}. Available: {available}")
    
    preset = SPECTRAL_PRESETS[preset_name]
    
    if isinstance(preset, DynamicEQParams):
        processor = DynamicEQ(preset, sample_rate)
    elif isinstance(preset, ResonanceSuppressorParams):
        processor = ResonanceSuppressor(preset, sample_rate)
    elif isinstance(preset, HarmonicExciterParams):
        processor = HarmonicExciter(preset, sample_rate)
    else:
        raise ValueError(f"Unknown preset type for: {preset_name}")
    
    return processor.process(audio)


# =============================================================================
# SPECTRAL BALANCE MATCHER
# =============================================================================

class SpectralBalanceMatcher(STFTProcessor):
    """
    Match spectral balance of one audio to a reference.
    
    Analyzes the average spectrum of a reference and applies
    corrective EQ to make the input match.
    
    Usage:
        >>> matcher = SpectralBalanceMatcher()
        >>> matcher.learn_reference(reference_audio)
        >>> matched = matcher.process(input_audio)
    """
    
    def __init__(
        self,
        fft_size: int = 4096,
        sample_rate: int = SAMPLE_RATE,
        smoothing: float = 0.5
    ):
        """
        Initialize Spectral Balance Matcher.
        
        Args:
            fft_size: FFT size for analysis
            sample_rate: Audio sample rate
            smoothing: Smoothing amount for EQ curve (0-1)
        """
        super().__init__(fft_size, fft_size // 4, 'hann', sample_rate)
        self.smoothing = smoothing
        self.reference_spectrum: Optional[np.ndarray] = None
        self.correction_curve: Optional[np.ndarray] = None
    
    def learn_reference(self, reference: np.ndarray):
        """
        Analyze reference audio and store target spectrum.
        
        Args:
            reference: Reference audio to match
        """
        if len(reference.shape) > 1:
            mono = np.mean(reference, axis=1)
        else:
            mono = reference
        
        # Analyze reference
        stft = self.analyze(mono)
        
        # Average spectrum magnitude
        self.reference_spectrum = np.mean(np.abs(stft), axis=0)
        
        # Apply smoothing
        if self.smoothing > 0:
            kernel_size = int(self.smoothing * 50) + 1
            if kernel_size % 2 == 0:
                kernel_size += 1
            kernel = np.ones(kernel_size) / kernel_size
            self.reference_spectrum = np.convolve(
                self.reference_spectrum, kernel, mode='same'
            )
    
    def process_frame(self, frame: np.ndarray) -> np.ndarray:
        """Apply spectral correction to a frame."""
        if self.reference_spectrum is None:
            return frame
        
        # Get magnitude and phase
        magnitude = np.abs(frame)
        phase = np.angle(frame)
        
        # Calculate correction
        # Avoid division by zero
        safe_mag = np.maximum(magnitude, 1e-10)
        correction = self.reference_spectrum / safe_mag
        
        # Limit correction range (±12dB)
        correction = np.clip(correction, 0.25, 4.0)
        
        # Apply correction
        new_magnitude = magnitude * correction
        
        # Reconstruct complex signal
        return new_magnitude * np.exp(1j * phase)


# =============================================================================
# MODULE EXPORTS
# =============================================================================

__all__ = [
    # Parameter classes
    'DynamicEQBand',
    'DynamicEQParams',
    'ResonanceSuppressorParams',
    'HarmonicExciterParams',
    
    # Processor classes
    'STFTProcessor',
    'DynamicEQ',
    'ResonanceSuppressor',
    'HarmonicExciter',
    'SpectrumAnalyzer',
    'SpectralBalanceMatcher',
    
    # Presets
    'SPECTRAL_PRESETS',
    
    # Convenience functions
    'dynamic_eq',
    'suppress_resonances',
    'add_harmonics',
    'analyze_spectrum',
    'apply_spectral_preset',
    
    # Helper functions
    'db_to_linear',
    'linear_to_db',
]
