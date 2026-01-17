"""
Reference Track Matching Module

Professional reference track analysis and matching for mastering-quality
mix matching. Extracts sonic profiles from reference tracks and applies
EQ, dynamics, and loudness adjustments to match input audio.

Key Features:
- Comprehensive spectral analysis (1/3 octave resolution)
- Dynamics profiling (crest factor, dynamic range)
- Transient detection and analysis
- Stereo width and correlation measurement
- EQ curve matching with linear-phase filters
- Dynamics matching with intelligent compression suggestions
- A/B comparison utilities

References:
- ITU-R BS.1770-4: Loudness measurement
- AES-17: Dynamic range measurement
- ISO 226:2003: Equal-loudness contours
- Pro audio mastering best practices

Author: Multimodal AI Music Generator
"""

import json
import numpy as np
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Tuple, Any
from scipy import signal
from scipy.fft import rfft, irfft, rfftfreq

from .utils import SAMPLE_RATE
from .auto_gain_staging import LUFSMeter, measure_lufs


# =============================================================================
# CONSTANTS
# =============================================================================

# 1/3 Octave band center frequencies (ISO standard)
THIRD_OCTAVE_CENTERS = np.array([
    20, 25, 31.5, 40, 50, 63, 80, 100, 125, 160,
    200, 250, 315, 400, 500, 630, 800, 1000, 1250, 1600,
    2000, 2500, 3150, 4000, 5000, 6300, 8000, 10000, 12500, 16000, 20000
])

# Frequency band boundaries for energy analysis
FREQ_BANDS = {
    'sub': (20, 80),
    'low': (80, 200),
    'low_mid': (200, 500),
    'mid': (500, 2000),
    'high_mid': (2000, 6000),
    'high': (6000, 20000),
}

# Simplified bands for quick analysis
SIMPLE_BANDS = {
    'sub': (20, 80),
    'low': (20, 200),
    'mid': (200, 2000),
    'high': (2000, 20000),
}

# Default FFT size for spectral analysis
DEFAULT_FFT_SIZE = 4096

# Transient detection defaults
TRANSIENT_THRESHOLD_DB = -20.0  # Threshold relative to peak for transient detection
TRANSIENT_MIN_INTERVAL_MS = 50  # Minimum time between transients


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class ReferenceProfile:
    """
    Captured characteristics of a reference track.
    
    Contains all the sonic attributes needed to match a mix to
    a reference, including spectral balance, dynamics, stereo image,
    and transient characteristics.
    
    Attributes:
        name: Identifier for this reference profile
        spectral_centroid: Brightness indicator in Hz
        spectral_rolloff: Frequency below which 85% of energy exists
        spectral_curve: Average magnitude spectrum (1/3 octave bands in dB)
        integrated_lufs: Overall loudness in LUFS
        dynamic_range_lu: Loudness range in LU
        crest_factor_db: Peak to RMS ratio in dB
        attack_density: Number of transients per second
        attack_sharpness: Average attack slope (higher = sharper)
        stereo_width: Stereo width factor (0=mono, 1=normal, 2=wide)
        correlation: Left/right correlation (-1 to 1)
        low_energy: Energy in 20-200Hz band (dB)
        mid_energy: Energy in 200-2000Hz band (dB)
        high_energy: Energy in 2000-20000Hz band (dB)
        sub_energy: Energy in 20-80Hz band (dB)
    """
    name: str = ""
    # Spectral characteristics
    spectral_centroid: float = 0.0
    spectral_rolloff: float = 0.0
    spectral_curve: Optional[np.ndarray] = field(default=None, repr=False)
    # Dynamics characteristics
    integrated_lufs: float = -14.0
    dynamic_range_lu: float = 8.0
    crest_factor_db: float = 12.0
    # Transient characteristics
    attack_density: float = 0.0
    attack_sharpness: float = 0.0
    # Stereo characteristics
    stereo_width: float = 1.0
    correlation: float = 1.0
    # Frequency balance (dB relative to total RMS)
    low_energy: float = 0.0
    mid_energy: float = 0.0
    high_energy: float = 0.0
    sub_energy: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert profile to serializable dictionary."""
        result = asdict(self)
        if result['spectral_curve'] is not None:
            result['spectral_curve'] = result['spectral_curve'].tolist()
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ReferenceProfile':
        """Create profile from dictionary."""
        if data.get('spectral_curve') is not None:
            data['spectral_curve'] = np.array(data['spectral_curve'])
        return cls(**data)


@dataclass
class ReferenceMatchParams:
    """
    Parameters controlling reference matching behavior.
    
    Attributes:
        eq_strength: How much EQ matching to apply (0-1)
        dynamics_strength: How much dynamics matching to apply (0-1)
        loudness_match: Whether to match integrated loudness
        stereo_match: Whether to match stereo width
        preserve_transients: Avoid excessive transient squashing
        max_eq_db: Maximum EQ boost/cut allowed
        eq_smoothing_octaves: Smoothing for EQ curve (1/3 = detailed, 1 = broad)
    """
    eq_strength: float = 1.0
    dynamics_strength: float = 1.0
    loudness_match: bool = True
    stereo_match: bool = True
    preserve_transients: bool = True
    max_eq_db: float = 12.0
    eq_smoothing_octaves: float = 1/3


# =============================================================================
# REFERENCE ANALYZER
# =============================================================================

class ReferenceAnalyzer:
    """
    Analyze reference tracks to extract comprehensive sonic profiles.
    
    Extracts spectral, dynamic, transient, and stereo characteristics
    from audio to create a ReferenceProfile that can be used for matching.
    
    Usage:
        >>> analyzer = ReferenceAnalyzer(sample_rate=44100)
        >>> profile = analyzer.analyze(reference_audio, name="my_reference")
        >>> print(f"Brightness: {profile.spectral_centroid:.0f} Hz")
    """
    
    def __init__(self, sample_rate: int = SAMPLE_RATE):
        """
        Initialize reference analyzer.
        
        Args:
            sample_rate: Audio sample rate in Hz
        """
        self.sample_rate = sample_rate
        self.lufs_meter = LUFSMeter(sample_rate)
        self.fft_size = DEFAULT_FFT_SIZE
    
    def analyze(self, audio: np.ndarray, name: str = "") -> ReferenceProfile:
        """
        Extract comprehensive profile from audio.
        
        Performs full analysis of spectral, dynamic, transient, and
        stereo characteristics to build a complete sonic profile.
        
        Args:
            audio: Input audio array (mono or stereo)
            name: Optional name for this profile
        
        Returns:
            ReferenceProfile with all extracted characteristics
        """
        # Ensure audio is valid
        if len(audio) == 0:
            return ReferenceProfile(name=name)
        
        # Convert to mono for spectral analysis
        if len(audio.shape) > 1 and audio.shape[1] > 1:
            mono = np.mean(audio, axis=1)
            is_stereo = True
        else:
            mono = audio.flatten() if len(audio.shape) > 1 else audio
            is_stereo = False
        
        # Spectral analysis
        spectral_centroid = self._calculate_spectral_centroid(mono)
        spectral_rolloff = self._calculate_spectral_rolloff(mono)
        spectral_curve = self._calculate_spectral_curve(mono)
        
        # Frequency band energy
        band_energy = self._calculate_band_energy(mono)
        
        # Dynamics analysis
        integrated_lufs = self.lufs_meter.measure_integrated(audio)
        dynamic_range_lu = self.lufs_meter.measure_loudness_range(audio)
        crest_factor_db = self._calculate_crest_factor(mono)
        
        # Transient analysis
        attack_density, attack_sharpness = self._analyze_transients(mono)
        
        # Stereo analysis
        if is_stereo:
            stereo_width = self._calculate_stereo_width(audio)
            correlation = self._calculate_correlation(audio)
        else:
            stereo_width = 0.0
            correlation = 1.0
        
        return ReferenceProfile(
            name=name,
            spectral_centroid=spectral_centroid,
            spectral_rolloff=spectral_rolloff,
            spectral_curve=spectral_curve,
            integrated_lufs=integrated_lufs,
            dynamic_range_lu=dynamic_range_lu,
            crest_factor_db=crest_factor_db,
            attack_density=attack_density,
            attack_sharpness=attack_sharpness,
            stereo_width=stereo_width,
            correlation=correlation,
            low_energy=band_energy.get('low', 0.0),
            mid_energy=band_energy.get('mid', 0.0),
            high_energy=band_energy.get('high', 0.0),
            sub_energy=band_energy.get('sub', 0.0),
        )
    
    def compare(self, profile_a: ReferenceProfile, profile_b: ReferenceProfile) -> Dict[str, float]:
        """
        Compare two profiles and return differences.
        
        Positive values mean profile_a has more of that characteristic.
        
        Args:
            profile_a: First profile
            profile_b: Second profile (reference)
        
        Returns:
            Dictionary with difference values for each characteristic
        """
        differences = {
            'brightness_diff_hz': profile_a.spectral_centroid - profile_b.spectral_centroid,
            'rolloff_diff_hz': profile_a.spectral_rolloff - profile_b.spectral_rolloff,
            'loudness_diff_lu': profile_a.integrated_lufs - profile_b.integrated_lufs,
            'dynamic_range_diff_lu': profile_a.dynamic_range_lu - profile_b.dynamic_range_lu,
            'crest_factor_diff_db': profile_a.crest_factor_db - profile_b.crest_factor_db,
            'attack_density_diff': profile_a.attack_density - profile_b.attack_density,
            'stereo_width_diff': profile_a.stereo_width - profile_b.stereo_width,
            'correlation_diff': profile_a.correlation - profile_b.correlation,
            'low_energy_diff_db': profile_a.low_energy - profile_b.low_energy,
            'mid_energy_diff_db': profile_a.mid_energy - profile_b.mid_energy,
            'high_energy_diff_db': profile_a.high_energy - profile_b.high_energy,
            'sub_energy_diff_db': profile_a.sub_energy - profile_b.sub_energy,
        }
        
        # Calculate spectral curve difference if both have curves
        if profile_a.spectral_curve is not None and profile_b.spectral_curve is not None:
            if len(profile_a.spectral_curve) == len(profile_b.spectral_curve):
                differences['spectral_curve_diff'] = (
                    profile_a.spectral_curve - profile_b.spectral_curve
                ).tolist()
        
        return differences
    
    def _calculate_spectral_centroid(self, audio: np.ndarray) -> float:
        """
        Calculate spectral centroid (brightness indicator).
        
        The spectral centroid is the center of mass of the spectrum,
        indicating where most of the spectral energy is concentrated.
        """
        # Use multiple windows and average
        hop_size = self.fft_size // 2
        n_frames = max(1, (len(audio) - self.fft_size) // hop_size + 1)
        
        centroids = []
        window = signal.windows.hann(self.fft_size)
        
        for i in range(n_frames):
            start = i * hop_size
            end = start + self.fft_size
            if end > len(audio):
                break
            
            frame = audio[start:end] * window
            spectrum = np.abs(rfft(frame))
            freqs = rfftfreq(self.fft_size, 1.0 / self.sample_rate)
            
            # Avoid division by zero
            total_energy = np.sum(spectrum)
            if total_energy > 1e-10:
                centroid = np.sum(freqs * spectrum) / total_energy
                centroids.append(centroid)
        
        return float(np.mean(centroids)) if centroids else 0.0
    
    def _calculate_spectral_rolloff(self, audio: np.ndarray, threshold: float = 0.85) -> float:
        """
        Calculate spectral rolloff frequency.
        
        The frequency below which 'threshold' (85%) of the spectral
        energy is contained.
        """
        hop_size = self.fft_size // 2
        n_frames = max(1, (len(audio) - self.fft_size) // hop_size + 1)
        
        rolloffs = []
        window = signal.windows.hann(self.fft_size)
        
        for i in range(n_frames):
            start = i * hop_size
            end = start + self.fft_size
            if end > len(audio):
                break
            
            frame = audio[start:end] * window
            spectrum = np.abs(rfft(frame)) ** 2  # Power spectrum
            freqs = rfftfreq(self.fft_size, 1.0 / self.sample_rate)
            
            # Cumulative sum
            cumsum = np.cumsum(spectrum)
            total = cumsum[-1]
            
            if total > 1e-10:
                # Find where cumsum exceeds threshold * total
                rolloff_idx = np.searchsorted(cumsum, threshold * total)
                if rolloff_idx < len(freqs):
                    rolloffs.append(freqs[rolloff_idx])
        
        return float(np.mean(rolloffs)) if rolloffs else 0.0
    
    def _calculate_spectral_curve(self, audio: np.ndarray) -> np.ndarray:
        """
        Calculate average magnitude spectrum in 1/3 octave bands.
        
        Returns dB values for each 1/3 octave band center frequency.
        """
        hop_size = self.fft_size // 2
        n_frames = max(1, (len(audio) - self.fft_size) // hop_size + 1)
        
        band_energies = np.zeros(len(THIRD_OCTAVE_CENTERS))
        n_valid_frames = 0
        window = signal.windows.hann(self.fft_size)
        freqs = rfftfreq(self.fft_size, 1.0 / self.sample_rate)
        
        # Calculate 1/3 octave band edges
        band_edges = []
        for center in THIRD_OCTAVE_CENTERS:
            low = center / (2 ** (1/6))
            high = center * (2 ** (1/6))
            band_edges.append((low, high))
        
        for i in range(n_frames):
            start = i * hop_size
            end = start + self.fft_size
            if end > len(audio):
                break
            
            frame = audio[start:end] * window
            spectrum = np.abs(rfft(frame)) ** 2  # Power spectrum
            
            # Sum energy in each 1/3 octave band
            for b_idx, (low, high) in enumerate(band_edges):
                mask = (freqs >= low) & (freqs < high)
                if np.any(mask):
                    band_energies[b_idx] += np.sum(spectrum[mask])
            
            n_valid_frames += 1
        
        # Average and convert to dB
        if n_valid_frames > 0:
            band_energies /= n_valid_frames
        
        # Convert to dB (with small epsilon to avoid log(0))
        band_db = 10 * np.log10(band_energies + 1e-10)
        
        # Normalize so average is 0 dB
        band_db -= np.mean(band_db)
        
        return band_db
    
    def _calculate_band_energy(self, audio: np.ndarray) -> Dict[str, float]:
        """Calculate energy in simple frequency bands (dB relative to total)."""
        # Get full spectrum
        spectrum = np.abs(rfft(audio)) ** 2
        freqs = rfftfreq(len(audio), 1.0 / self.sample_rate)
        
        total_energy = np.sum(spectrum)
        if total_energy < 1e-10:
            return {band: 0.0 for band in SIMPLE_BANDS}
        
        result = {}
        for band_name, (low, high) in SIMPLE_BANDS.items():
            mask = (freqs >= low) & (freqs < high)
            band_energy = np.sum(spectrum[mask])
            # dB relative to total
            result[band_name] = float(10 * np.log10(band_energy / total_energy + 1e-10))
        
        return result
    
    def _calculate_crest_factor(self, audio: np.ndarray) -> float:
        """
        Calculate crest factor (peak to RMS ratio) in dB.
        
        Higher values indicate more dynamic/transient material.
        Typical values: 12-20 dB for music.
        """
        peak = np.max(np.abs(audio))
        rms = np.sqrt(np.mean(audio ** 2))
        
        if rms < 1e-10:
            return 0.0
        
        return float(20 * np.log10(peak / rms))
    
    def _analyze_transients(self, audio: np.ndarray) -> Tuple[float, float]:
        """
        Analyze transient characteristics.
        
        Returns:
            Tuple of (attack_density, attack_sharpness)
            - attack_density: transients per second
            - attack_sharpness: average attack slope (0-1)
        """
        # Calculate envelope using RMS
        window_size = int(0.01 * self.sample_rate)  # 10ms window
        hop = window_size // 2
        
        envelope = []
        for i in range(0, len(audio) - window_size, hop):
            rms = np.sqrt(np.mean(audio[i:i+window_size] ** 2))
            envelope.append(rms)
        
        if len(envelope) < 3:
            return (0.0, 0.0)
        
        envelope = np.array(envelope)
        
        # Detect transients using derivative
        env_diff = np.diff(envelope)
        
        # Threshold for transient detection
        threshold = np.max(envelope) * (10 ** (TRANSIENT_THRESHOLD_DB / 20))
        min_interval_samples = int(TRANSIENT_MIN_INTERVAL_MS * self.sample_rate / 1000 / hop)
        
        # Find positive-going threshold crossings
        transients = []
        last_transient = -min_interval_samples
        
        for i in range(1, len(env_diff)):
            if (env_diff[i] > 0 and envelope[i] > threshold and 
                i - last_transient >= min_interval_samples):
                transients.append(i)
                last_transient = i
        
        # Calculate density (transients per second)
        duration_sec = len(audio) / self.sample_rate
        density = len(transients) / duration_sec if duration_sec > 0 else 0.0
        
        # Calculate average attack sharpness
        if len(transients) > 0:
            slopes = []
            for t_idx in transients:
                if t_idx < len(env_diff):
                    slopes.append(env_diff[t_idx])
            
            if slopes and np.max(envelope) > 1e-10:
                # Normalize by peak envelope
                sharpness = np.mean(slopes) / np.max(envelope)
                sharpness = np.clip(sharpness, 0, 1)
            else:
                sharpness = 0.0
        else:
            sharpness = 0.0
        
        return (float(density), float(sharpness))
    
    def _calculate_stereo_width(self, audio: np.ndarray) -> float:
        """
        Calculate stereo width.
        
        Returns:
            0 = mono, 1 = normal stereo, 2 = very wide
        """
        if len(audio.shape) < 2 or audio.shape[1] < 2:
            return 0.0
        
        left = audio[:, 0]
        right = audio[:, 1]
        
        # Mid-side analysis
        mid = (left + right) / 2
        side = (left - right) / 2
        
        mid_energy = np.mean(mid ** 2)
        side_energy = np.mean(side ** 2)
        
        if mid_energy < 1e-10:
            return 0.0
        
        # Width is ratio of side to mid energy
        # Normal stereo has ratio around 0.5-1.0
        ratio = side_energy / mid_energy
        
        # Scale so 0=mono, 1=normal, 2=wide
        width = np.sqrt(ratio) * 2
        return float(np.clip(width, 0, 2))
    
    def _calculate_correlation(self, audio: np.ndarray) -> float:
        """
        Calculate left/right correlation.
        
        Returns:
            1.0 = perfectly correlated (mono compatible)
            0.0 = uncorrelated
            -1.0 = anti-correlated (phase issues)
        """
        if len(audio.shape) < 2 or audio.shape[1] < 2:
            return 1.0
        
        left = audio[:, 0]
        right = audio[:, 1]
        
        # Pearson correlation
        left_mean = np.mean(left)
        right_mean = np.mean(right)
        
        left_centered = left - left_mean
        right_centered = right - right_mean
        
        numerator = np.sum(left_centered * right_centered)
        denominator = np.sqrt(np.sum(left_centered ** 2) * np.sum(right_centered ** 2))
        
        if denominator < 1e-10:
            return 1.0
        
        return float(numerator / denominator)


# =============================================================================
# EQ MATCHER
# =============================================================================

class EQMatcher:
    """
    Match EQ curve of input to reference profile.
    
    Analyzes the spectral difference between input audio and a reference
    profile, then generates and applies an EQ curve to match.
    
    Usage:
        >>> matcher = EQMatcher(fft_size=4096)
        >>> diff_curve = matcher.calculate_difference_curve(input_audio, ref_profile)
        >>> matched = matcher.apply_match_eq(input_audio, diff_curve, strength=0.8)
    """
    
    def __init__(
        self,
        fft_size: int = DEFAULT_FFT_SIZE,
        smoothing_octaves: float = 1/3,
        sample_rate: int = SAMPLE_RATE
    ):
        """
        Initialize EQ matcher.
        
        Args:
            fft_size: FFT size for analysis
            smoothing_octaves: Octave smoothing for EQ curve (1/3 = detailed)
            sample_rate: Audio sample rate
        """
        self.fft_size = fft_size
        self.smoothing = smoothing_octaves
        self.sample_rate = sample_rate
        self.analyzer = ReferenceAnalyzer(sample_rate)
    
    def calculate_difference_curve(
        self,
        input_audio: np.ndarray,
        reference_profile: ReferenceProfile,
        max_db: float = 12.0
    ) -> np.ndarray:
        """
        Calculate EQ curve (dB) to apply to input to match reference.
        
        Positive values = boost needed, negative = cut needed.
        
        Args:
            input_audio: Input audio to analyze
            reference_profile: Target profile to match
            max_db: Maximum boost/cut in dB
        
        Returns:
            EQ curve in dB for 1/3 octave bands
        """
        if reference_profile.spectral_curve is None:
            return np.zeros(len(THIRD_OCTAVE_CENTERS))
        
        # Get mono for analysis
        if len(input_audio.shape) > 1 and input_audio.shape[1] > 1:
            mono = np.mean(input_audio, axis=1)
        else:
            mono = input_audio.flatten() if len(input_audio.shape) > 1 else input_audio
        
        # Calculate input spectral curve
        input_curve = self.analyzer._calculate_spectral_curve(mono)
        
        # Calculate difference (reference - input = what we need to add)
        difference = reference_profile.spectral_curve - input_curve
        
        # Limit to max_db
        difference = np.clip(difference, -max_db, max_db)
        
        # Apply smoothing if needed
        if self.smoothing > 1/3:
            # Number of bands to average (1 octave = 3 bands in 1/3 octave)
            smooth_bands = max(1, int(self.smoothing * 3))
            if smooth_bands > 1:
                kernel = np.ones(smooth_bands) / smooth_bands
                difference = np.convolve(difference, kernel, mode='same')
        
        return difference
    
    def apply_match_eq(
        self,
        audio: np.ndarray,
        difference_curve: np.ndarray,
        strength: float = 1.0
    ) -> np.ndarray:
        """
        Apply the calculated EQ curve using linear-phase filtering.
        
        Args:
            audio: Input audio array
            difference_curve: EQ curve in dB (from calculate_difference_curve)
            strength: How much to apply (0-1, 1.0 = full match)
        
        Returns:
            EQ-matched audio
        """
        if len(audio) == 0 or strength <= 0:
            return audio
        
        # Scale difference by strength
        scaled_diff = difference_curve * strength
        
        # Create frequency response for filter
        # Interpolate from 1/3 octave bands to full FFT resolution
        fft_freqs = rfftfreq(self.fft_size, 1.0 / self.sample_rate)
        
        # Build magnitude response by interpolating between band centers
        log_centers = np.log10(THIRD_OCTAVE_CENTERS + 1)
        log_fft_freqs = np.log10(fft_freqs + 1)
        
        # Interpolate (log frequency scale)
        magnitude_response = np.interp(log_fft_freqs, log_centers, scaled_diff)
        
        # Convert dB to linear
        magnitude_linear = 10 ** (magnitude_response / 20)
        
        # Create minimum-phase impulse response
        # (Approximation using symmetric time-domain window)
        n_fft = self.fft_size * 2
        
        # Build symmetric magnitude response
        full_mag = np.zeros(n_fft // 2 + 1)
        full_mag[:len(magnitude_linear)] = magnitude_linear
        
        # Create linear phase (zero phase in time domain = symmetric)
        impulse = irfft(full_mag, n_fft)
        
        # Window to create smooth filter
        window = signal.windows.hann(n_fft)
        impulse = impulse * window
        
        # Normalize
        impulse = impulse / (np.sum(np.abs(impulse)) + 1e-10)
        
        # Apply filter
        if len(audio.shape) > 1 and audio.shape[1] > 1:
            # Stereo
            result = np.zeros_like(audio)
            for ch in range(audio.shape[1]):
                result[:, ch] = signal.fftconvolve(audio[:, ch], impulse, mode='same')
            return result
        else:
            return signal.fftconvolve(audio, impulse, mode='same')
    
    def get_eq_bands(self, difference_curve: np.ndarray) -> List[Dict[str, float]]:
        """
        Convert difference curve to parametric EQ band suggestions.
        
        Returns list of EQ bands with frequency, gain, and Q values
        suitable for a parametric equalizer.
        
        Args:
            difference_curve: EQ curve in dB
        
        Returns:
            List of dicts with 'freq', 'gain_db', 'q' keys
        """
        bands = []
        
        # Find significant deviations (> 1.5 dB)
        threshold = 1.5
        
        # Group adjacent bands with same direction
        i = 0
        while i < len(difference_curve):
            gain = difference_curve[i]
            if abs(gain) < threshold:
                i += 1
                continue
            
            # Find extent of this adjustment
            direction = np.sign(gain)
            start_idx = i
            end_idx = i
            
            while end_idx < len(difference_curve) - 1:
                next_gain = difference_curve[end_idx + 1]
                if np.sign(next_gain) == direction and abs(next_gain) >= threshold / 2:
                    end_idx += 1
                else:
                    break
            
            # Calculate band parameters
            center_idx = (start_idx + end_idx) // 2
            center_freq = THIRD_OCTAVE_CENTERS[center_idx]
            avg_gain = np.mean(difference_curve[start_idx:end_idx + 1])
            
            # Q based on bandwidth
            bandwidth_octaves = (end_idx - start_idx + 1) / 3  # 3 bands per octave
            q = 1 / bandwidth_octaves if bandwidth_octaves > 0 else 1.0
            
            bands.append({
                'freq': float(center_freq),
                'gain_db': float(avg_gain),
                'q': float(np.clip(q, 0.3, 10.0)),
            })
            
            i = end_idx + 1
        
        return bands


# =============================================================================
# DYNAMICS MATCHER
# =============================================================================

class DynamicsMatcher:
    """
    Match dynamic profile of input to reference.
    
    Analyzes dynamics characteristics and suggests/applies compression
    or expansion to match the reference profile's dynamic feel.
    
    Usage:
        >>> matcher = DynamicsMatcher(sample_rate=44100)
        >>> settings = matcher.calculate_compression_needed(audio, ref_profile)
        >>> matched = matcher.apply_dynamics_match(audio, target_crest=12, target_lufs=-14)
    """
    
    def __init__(self, sample_rate: int = SAMPLE_RATE):
        """
        Initialize dynamics matcher.
        
        Args:
            sample_rate: Audio sample rate
        """
        self.sample_rate = sample_rate
        self.lufs_meter = LUFSMeter(sample_rate)
    
    def calculate_compression_needed(
        self,
        input_audio: np.ndarray,
        reference_profile: ReferenceProfile
    ) -> Dict[str, float]:
        """
        Suggest compression settings to match dynamics.
        
        If input is more dynamic than reference, suggests compression.
        If input is less dynamic, suggests expansion.
        
        Args:
            input_audio: Input audio to analyze
            reference_profile: Target profile
        
        Returns:
            Dict with threshold_db, ratio, attack_ms, release_ms, makeup_db
        """
        # Get mono for analysis
        if len(input_audio.shape) > 1 and input_audio.shape[1] > 1:
            mono = np.mean(input_audio, axis=1)
        else:
            mono = input_audio.flatten() if len(input_audio.shape) > 1 else input_audio
        
        # Calculate input dynamics
        input_crest = self._calculate_crest_factor(mono)
        input_lufs = self.lufs_meter.measure_integrated(input_audio)
        input_dr = self.lufs_meter.measure_loudness_range(input_audio)
        
        # Calculate differences
        crest_diff = input_crest - reference_profile.crest_factor_db
        dr_diff = input_dr - reference_profile.dynamic_range_lu
        
        # Determine if we need compression or expansion
        needs_compression = crest_diff > 2 or dr_diff > 2
        needs_expansion = crest_diff < -2 or dr_diff < -2
        
        if needs_compression:
            # Calculate compression settings
            # Higher crest difference = lower threshold
            threshold = -20 - abs(crest_diff)
            threshold = np.clip(threshold, -40, -10)
            
            # Ratio based on dynamic range difference
            ratio = 1 + (abs(dr_diff) / 4)
            ratio = np.clip(ratio, 1.5, 8.0)
            
            # Attack/release based on transient density
            if reference_profile.attack_density > 5:
                attack = 10  # Fast for transient material
                release = 50
            else:
                attack = 30  # Slower for sustained
                release = 150
            
            # Makeup gain to compensate
            makeup = abs(crest_diff) / 2
            
        elif needs_expansion:
            # Expansion settings (ratio < 1 acts as expander)
            threshold = -30
            ratio = 0.5 + (abs(dr_diff) / 10)  # Expansion ratio
            ratio = np.clip(ratio, 0.3, 0.8)
            attack = 5
            release = 100
            makeup = 0
            
        else:
            # No significant dynamics change needed
            threshold = -24
            ratio = 1.0
            attack = 20
            release = 100
            makeup = 0
        
        return {
            'threshold_db': float(threshold),
            'ratio': float(ratio),
            'attack_ms': float(attack),
            'release_ms': float(release),
            'makeup_db': float(makeup),
            'needs_compression': bool(needs_compression),
            'needs_expansion': bool(needs_expansion),
            'crest_diff_db': float(crest_diff),
            'dr_diff_lu': float(dr_diff),
        }
    
    def apply_dynamics_match(
        self,
        audio: np.ndarray,
        target_crest_db: float,
        target_lufs: float
    ) -> np.ndarray:
        """
        Apply soft-knee compression/expansion to match targets.
        
        Args:
            audio: Input audio
            target_crest_db: Target crest factor
            target_lufs: Target integrated loudness
        
        Returns:
            Dynamics-matched audio
        """
        if len(audio) == 0:
            return audio
        
        # Get mono for analysis
        if len(audio.shape) > 1 and audio.shape[1] > 1:
            mono = np.mean(audio, axis=1)
        else:
            mono = audio.flatten() if len(audio.shape) > 1 else audio
        
        # Current crest factor
        current_crest = self._calculate_crest_factor(mono)
        crest_diff = current_crest - target_crest_db
        
        if abs(crest_diff) < 1:
            # Close enough, just normalize loudness
            current_lufs = self.lufs_meter.measure_integrated(audio)
            if current_lufs > -np.inf:
                gain_db = target_lufs - current_lufs
                gain_db = np.clip(gain_db, -12, 12)
                return audio * (10 ** (gain_db / 20))
            return audio
        
        # Apply soft compression/expansion
        # Calculate envelope
        window_ms = 10
        window_samples = int(window_ms * self.sample_rate / 1000)
        hop = window_samples // 2
        
        envelope = self._calculate_envelope(mono, window_samples, hop)
        
        # Calculate gain reduction curve
        threshold_db = -24
        knee_db = 6
        
        if crest_diff > 0:
            # Need compression
            ratio = 1 + (crest_diff / 6)
            ratio = np.clip(ratio, 1.5, 8)
        else:
            # Need expansion (less compression)
            ratio = 0.8
        
        # Apply compression curve to envelope
        env_db = 20 * np.log10(envelope + 1e-10)
        
        # Soft knee compression
        gain_db = np.zeros_like(env_db)
        
        for i, level in enumerate(env_db):
            if level < threshold_db - knee_db / 2:
                # Below knee
                gain_db[i] = 0
            elif level > threshold_db + knee_db / 2:
                # Above knee
                gain_db[i] = (threshold_db - level) * (1 - 1/ratio)
            else:
                # In knee region
                knee_factor = (level - threshold_db + knee_db / 2) / knee_db
                gain_db[i] = (knee_factor ** 2) * (threshold_db - level) * (1 - 1/ratio) / 2
        
        # Interpolate gain curve to full length
        gain_interp = np.interp(
            np.arange(len(mono)),
            np.arange(len(envelope)) * hop,
            10 ** (gain_db / 20)
        )
        
        # Smooth gain curve
        smooth_samples = int(5 * self.sample_rate / 1000)  # 5ms smoothing
        if smooth_samples > 1:
            kernel = np.ones(smooth_samples) / smooth_samples
            gain_interp = np.convolve(gain_interp, kernel, mode='same')
        
        # Apply gain
        if len(audio.shape) > 1:
            result = audio * gain_interp[:, np.newaxis]
        else:
            result = audio * gain_interp[:len(audio)]
        
        # Normalize to target loudness
        current_lufs = self.lufs_meter.measure_integrated(result)
        if current_lufs > -np.inf:
            gain_db = target_lufs - current_lufs
            gain_db = np.clip(gain_db, -12, 12)
            result = result * (10 ** (gain_db / 20))
        
        return result
    
    def _calculate_crest_factor(self, audio: np.ndarray) -> float:
        """Calculate crest factor in dB."""
        peak = np.max(np.abs(audio))
        rms = np.sqrt(np.mean(audio ** 2))
        if rms < 1e-10:
            return 0.0
        return float(20 * np.log10(peak / rms))
    
    def _calculate_envelope(
        self,
        audio: np.ndarray,
        window_samples: int,
        hop: int
    ) -> np.ndarray:
        """Calculate RMS envelope."""
        envelope = []
        for i in range(0, len(audio) - window_samples, hop):
            rms = np.sqrt(np.mean(audio[i:i+window_samples] ** 2))
            envelope.append(rms)
        return np.array(envelope)


# =============================================================================
# STEREO MATCHER
# =============================================================================

class StereoMatcher:
    """
    Match stereo width and characteristics.
    
    Adjusts mid-side balance to match reference stereo width.
    """
    
    def __init__(self, sample_rate: int = SAMPLE_RATE):
        """Initialize stereo matcher."""
        self.sample_rate = sample_rate
    
    def adjust_stereo_width(
        self,
        audio: np.ndarray,
        target_width: float,
        current_width: float = None
    ) -> np.ndarray:
        """
        Adjust stereo width to match target.
        
        Args:
            audio: Stereo audio array
            target_width: Target width (0=mono, 1=normal, 2=wide)
            current_width: Current width (calculated if not provided)
        
        Returns:
            Width-adjusted audio
        """
        if len(audio.shape) < 2 or audio.shape[1] < 2:
            # Can't adjust mono
            return audio
        
        if current_width is None:
            current_width = self._calculate_width(audio)
        
        if current_width < 0.01:
            # Essentially mono, can't widen
            return audio
        
        # Convert to mid-side
        left = audio[:, 0]
        right = audio[:, 1]
        mid = (left + right) / 2
        side = (left - right) / 2
        
        # Calculate adjustment factor
        # target_width / current_width gives us the side scaling factor
        if current_width > 0.01:
            scale = target_width / current_width
        else:
            scale = 1.0
        
        # Limit extreme adjustments
        scale = np.clip(scale, 0, 3)
        
        # Apply scaling to side
        side_adjusted = side * scale
        
        # Convert back to L/R
        left_new = mid + side_adjusted
        right_new = mid - side_adjusted
        
        return np.column_stack([left_new, right_new])
    
    def _calculate_width(self, audio: np.ndarray) -> float:
        """Calculate stereo width."""
        if len(audio.shape) < 2 or audio.shape[1] < 2:
            return 0.0
        
        left = audio[:, 0]
        right = audio[:, 1]
        
        mid = (left + right) / 2
        side = (left - right) / 2
        
        mid_energy = np.mean(mid ** 2)
        side_energy = np.mean(side ** 2)
        
        if mid_energy < 1e-10:
            return 0.0
        
        ratio = side_energy / mid_energy
        return float(np.sqrt(ratio) * 2)


# =============================================================================
# FULL REFERENCE MATCHER
# =============================================================================

class ReferenceMatcher:
    """
    Complete reference matching processor.
    
    Combines EQ, dynamics, loudness, and stereo matching to
    make input audio sound closer to a reference profile.
    
    Usage:
        >>> profile = ReferenceAnalyzer().analyze(reference_audio)
        >>> params = ReferenceMatchParams(eq_strength=0.8, dynamics_strength=0.5)
        >>> matcher = ReferenceMatcher(profile, params)
        >>> differences = matcher.analyze_differences(input_audio)
        >>> matched = matcher.process(input_audio)
    """
    
    def __init__(
        self,
        reference_profile: ReferenceProfile,
        params: ReferenceMatchParams = None,
        sample_rate: int = SAMPLE_RATE
    ):
        """
        Initialize reference matcher.
        
        Args:
            reference_profile: Target profile to match
            params: Matching parameters
            sample_rate: Audio sample rate
        """
        self.reference = reference_profile
        self.params = params or ReferenceMatchParams()
        self.sample_rate = sample_rate
        
        self.analyzer = ReferenceAnalyzer(sample_rate)
        self.eq_matcher = EQMatcher(
            smoothing_octaves=self.params.eq_smoothing_octaves,
            sample_rate=sample_rate
        )
        self.dynamics_matcher = DynamicsMatcher(sample_rate)
        self.stereo_matcher = StereoMatcher(sample_rate)
        self.lufs_meter = LUFSMeter(sample_rate)
    
    def analyze_differences(self, input_audio: np.ndarray) -> Dict[str, Any]:
        """
        Analyze input and return detailed comparison with reference.
        
        Args:
            input_audio: Audio to analyze
        
        Returns:
            Dict with detailed comparison metrics and recommendations
        """
        # Analyze input
        input_profile = self.analyzer.analyze(input_audio, "input")
        
        # Calculate differences
        diff = self.analyzer.compare(input_profile, self.reference)
        
        # Get EQ curve
        eq_curve = self.eq_matcher.calculate_difference_curve(
            input_audio, self.reference, self.params.max_eq_db
        )
        
        # Get compression suggestions
        compression = self.dynamics_matcher.calculate_compression_needed(
            input_audio, self.reference
        )
        
        # Generate recommendations
        recommendations = self._generate_recommendations(diff, compression)
        
        return {
            'input_profile': input_profile.to_dict(),
            'reference_profile': self.reference.to_dict(),
            'eq_curve': eq_curve.tolist(),
            'eq_bands': self.eq_matcher.get_eq_bands(eq_curve),
            'brightness_diff_db': diff.get('brightness_diff_hz', 0) / 100,  # Approx dB
            'low_end_diff_db': diff.get('low_energy_diff_db', 0),
            'dynamic_range_diff_lu': diff.get('dynamic_range_diff_lu', 0),
            'loudness_diff_lu': diff.get('loudness_diff_lu', 0),
            'stereo_width_diff': diff.get('stereo_width_diff', 0),
            'compression_settings': compression,
            'recommendations': recommendations,
        }
    
    def process(self, audio: np.ndarray) -> np.ndarray:
        """
        Apply full reference matching.
        
        Processes audio through EQ matching, dynamics matching,
        loudness matching, and stereo matching in sequence.
        
        Args:
            audio: Input audio
        
        Returns:
            Reference-matched audio
        """
        if len(audio) == 0:
            return audio
        
        result = audio.copy()
        
        # 1. EQ Matching
        if self.params.eq_strength > 0:
            eq_curve = self.eq_matcher.calculate_difference_curve(
                result, self.reference, self.params.max_eq_db
            )
            result = self.eq_matcher.apply_match_eq(
                result, eq_curve, self.params.eq_strength
            )
        
        # 2. Dynamics Matching
        if self.params.dynamics_strength > 0:
            target_crest = self.reference.crest_factor_db
            target_lufs = self.reference.integrated_lufs
            
            # If preserving transients, don't reduce crest factor as much
            if self.params.preserve_transients:
                input_crest = self._get_crest_factor(result)
                # Don't reduce crest by more than 3 dB
                if target_crest < input_crest - 3:
                    target_crest = input_crest - 3
            
            # Blend based on strength
            current_crest = self._get_crest_factor(result)
            blended_crest = (
                current_crest * (1 - self.params.dynamics_strength) +
                target_crest * self.params.dynamics_strength
            )
            
            result = self.dynamics_matcher.apply_dynamics_match(
                result, blended_crest, target_lufs
            )
        
        # 3. Loudness Matching (if not already done in dynamics)
        if self.params.loudness_match and self.params.dynamics_strength == 0:
            current_lufs = self.lufs_meter.measure_integrated(result)
            if current_lufs > -np.inf:
                gain_db = self.reference.integrated_lufs - current_lufs
                gain_db = np.clip(gain_db, -12, 12)
                result = result * (10 ** (gain_db / 20))
        
        # 4. Stereo Matching
        if self.params.stereo_match and len(result.shape) > 1 and result.shape[1] > 1:
            current_width = self.stereo_matcher._calculate_width(result)
            result = self.stereo_matcher.adjust_stereo_width(
                result,
                self.reference.stereo_width,
                current_width
            )
        
        return result
    
    def _get_crest_factor(self, audio: np.ndarray) -> float:
        """Get crest factor of audio."""
        if len(audio.shape) > 1:
            mono = np.mean(audio, axis=1)
        else:
            mono = audio
        peak = np.max(np.abs(mono))
        rms = np.sqrt(np.mean(mono ** 2))
        if rms < 1e-10:
            return 0.0
        return float(20 * np.log10(peak / rms))
    
    def _generate_recommendations(
        self,
        diff: Dict[str, float],
        compression: Dict[str, Any]
    ) -> List[str]:
        """Generate human-readable recommendations."""
        recommendations = []
        
        # Brightness
        brightness_diff = diff.get('brightness_diff_hz', 0)
        if brightness_diff > 500:
            recommendations.append("Input is brighter than reference - consider reducing highs")
        elif brightness_diff < -500:
            recommendations.append("Input is darker than reference - consider boosting highs")
        
        # Low end
        low_diff = diff.get('low_energy_diff_db', 0)
        if low_diff > 3:
            recommendations.append("Input has more low end - consider reducing bass")
        elif low_diff < -3:
            recommendations.append("Input has less low end - consider boosting bass")
        
        # Dynamics
        dr_diff = diff.get('dynamic_range_diff_lu', 0)
        if dr_diff > 3:
            recommendations.append("Input is more dynamic - consider compression")
        elif dr_diff < -3:
            recommendations.append("Input is less dynamic - consider parallel compression or less limiting")
        
        # Loudness
        lufs_diff = diff.get('loudness_diff_lu', 0)
        if lufs_diff > 2:
            recommendations.append(f"Input is {abs(lufs_diff):.1f} LU louder - reduce gain")
        elif lufs_diff < -2:
            recommendations.append(f"Input is {abs(lufs_diff):.1f} LU quieter - increase gain")
        
        # Stereo
        width_diff = diff.get('stereo_width_diff', 0)
        if width_diff > 0.3:
            recommendations.append("Input is wider - consider narrowing stereo image")
        elif width_diff < -0.3:
            recommendations.append("Input is narrower - consider widening stereo image")
        
        # Compression specifics
        if compression.get('needs_compression', False):
            ratio = compression.get('ratio', 2)
            threshold = compression.get('threshold_db', -20)
            recommendations.append(
                f"Suggested compression: {ratio:.1f}:1 ratio, {threshold:.0f} dB threshold"
            )
        
        if not recommendations:
            recommendations.append("Mix is close to reference - minimal adjustments needed")
        
        return recommendations


# =============================================================================
# A/B COMPARISON UTILITY
# =============================================================================

class ABComparison:
    """
    Utility for A/B listening comparison.
    
    Creates comparison audio and metrics for evaluating
    reference matching results.
    
    Usage:
        >>> ab = ABComparison(original, processed, reference)
        >>> metrics = ab.get_comparison_metrics()
        >>> ab_audio = ab.create_ab_audio(switch_interval_sec=4.0)
    """
    
    def __init__(
        self,
        original: np.ndarray,
        processed: np.ndarray,
        reference: Optional[np.ndarray] = None,
        sample_rate: int = SAMPLE_RATE
    ):
        """
        Initialize A/B comparison.
        
        Args:
            original: Original (unprocessed) audio
            processed: Processed (matched) audio
            reference: Optional reference audio
            sample_rate: Audio sample rate
        """
        self.original = original
        self.processed = processed
        self.reference = reference
        self.sample_rate = sample_rate
        self.analyzer = ReferenceAnalyzer(sample_rate)
        self.lufs_meter = LUFSMeter(sample_rate)
    
    def get_comparison_metrics(self) -> Dict[str, Any]:
        """
        Calculate metrics comparing all versions.
        
        Returns:
            Dict with metrics for original, processed, and reference
        """
        metrics = {
            'original': self._get_metrics(self.original, "Original"),
            'processed': self._get_metrics(self.processed, "Processed"),
        }
        
        if self.reference is not None:
            metrics['reference'] = self._get_metrics(self.reference, "Reference")
            
            # Calculate how close processed is to reference vs original
            ref_profile = self.analyzer.analyze(self.reference)
            orig_profile = self.analyzer.analyze(self.original)
            proc_profile = self.analyzer.analyze(self.processed)
            
            orig_diff = self.analyzer.compare(orig_profile, ref_profile)
            proc_diff = self.analyzer.compare(proc_profile, ref_profile)
            
            # Lower total difference = closer to reference
            orig_score = self._calculate_match_score(orig_diff)
            proc_score = self._calculate_match_score(proc_diff)
            
            metrics['original_match_score'] = orig_score
            metrics['processed_match_score'] = proc_score
            metrics['improvement'] = proc_score - orig_score
        
        return metrics
    
    def create_ab_audio(self, switch_interval_sec: float = 4.0) -> np.ndarray:
        """
        Create audio that switches between A (original) and B (processed).
        
        Useful for blind A/B testing.
        
        Args:
            switch_interval_sec: Time between A/B switches
        
        Returns:
            Combined A/B audio
        """
        interval_samples = int(switch_interval_sec * self.sample_rate)
        
        # Get minimum length
        min_len = min(len(self.original), len(self.processed))
        if len(self.original.shape) > 1:
            min_len = min(min_len, self.original.shape[0], self.processed.shape[0])
        
        # Determine output shape
        if len(self.original.shape) > 1:
            n_channels = self.original.shape[1]
            result = np.zeros((min_len, n_channels))
        else:
            result = np.zeros(min_len)
        
        # Alternate between A and B
        is_a = True
        pos = 0
        
        while pos < min_len:
            end = min(pos + interval_samples, min_len)
            
            # Crossfade length (10ms)
            fade_samples = min(int(0.01 * self.sample_rate), (end - pos) // 2)
            
            if is_a:
                source = self.original
            else:
                source = self.processed
            
            if len(result.shape) > 1:
                result[pos:end] = source[pos:end]
                # Apply crossfade at transitions
                if pos > 0 and fade_samples > 0:
                    fade_in = np.linspace(0, 1, fade_samples)[:, np.newaxis]
                    fade_out = np.linspace(1, 0, fade_samples)[:, np.newaxis]
                    prev_source = self.processed if is_a else self.original
                    result[pos:pos+fade_samples] = (
                        source[pos:pos+fade_samples] * fade_in +
                        prev_source[pos:pos+fade_samples] * fade_out
                    )
            else:
                result[pos:end] = source[pos:end]
                if pos > 0 and fade_samples > 0:
                    fade_in = np.linspace(0, 1, fade_samples)
                    fade_out = np.linspace(1, 0, fade_samples)
                    prev_source = self.processed if is_a else self.original
                    result[pos:pos+fade_samples] = (
                        source[pos:pos+fade_samples] * fade_in +
                        prev_source[pos:pos+fade_samples] * fade_out
                    )
            
            is_a = not is_a
            pos = end
        
        return result
    
    def export_stems(self, output_dir: str) -> Dict[str, str]:
        """
        Export original, processed, and reference as separate files.
        
        Args:
            output_dir: Directory to save files
        
        Returns:
            Dict mapping stem name to file path
        
        Note:
            Requires scipy.io.wavfile for export
        """
        import os
        from scipy.io import wavfile
        
        os.makedirs(output_dir, exist_ok=True)
        
        paths = {}
        
        # Normalize for 16-bit export
        def normalize_for_export(audio):
            peak = np.max(np.abs(audio))
            if peak > 0:
                audio = audio / peak * 0.95
            return (audio * 32767).astype(np.int16)
        
        # Export original
        orig_path = os.path.join(output_dir, "original.wav")
        wavfile.write(orig_path, self.sample_rate, normalize_for_export(self.original))
        paths['original'] = orig_path
        
        # Export processed
        proc_path = os.path.join(output_dir, "processed.wav")
        wavfile.write(proc_path, self.sample_rate, normalize_for_export(self.processed))
        paths['processed'] = proc_path
        
        # Export reference if available
        if self.reference is not None:
            ref_path = os.path.join(output_dir, "reference.wav")
            wavfile.write(ref_path, self.sample_rate, normalize_for_export(self.reference))
            paths['reference'] = ref_path
        
        return paths
    
    def _get_metrics(self, audio: np.ndarray, name: str) -> Dict[str, float]:
        """Get basic metrics for audio."""
        profile = self.analyzer.analyze(audio, name)
        return {
            'lufs': profile.integrated_lufs,
            'dynamic_range_lu': profile.dynamic_range_lu,
            'crest_factor_db': profile.crest_factor_db,
            'spectral_centroid': profile.spectral_centroid,
            'stereo_width': profile.stereo_width,
            'low_energy_db': profile.low_energy,
            'mid_energy_db': profile.mid_energy,
            'high_energy_db': profile.high_energy,
        }
    
    def _calculate_match_score(self, diff: Dict[str, float]) -> float:
        """
        Calculate overall match score (0-100, higher = better match).
        
        Weights different aspects of the mix.
        """
        # Weights for different aspects
        weights = {
            'loudness_diff_lu': 20,
            'dynamic_range_diff_lu': 15,
            'low_energy_diff_db': 20,
            'mid_energy_diff_db': 15,
            'high_energy_diff_db': 15,
            'stereo_width_diff': 10,
            'crest_factor_diff_db': 5,
        }
        
        total_weight = sum(weights.values())
        score = 100
        
        for key, weight in weights.items():
            if key in diff:
                # Penalize based on absolute difference
                # Max penalty per category is the weight
                diff_val = abs(diff[key])
                # Normalize: 0 diff = 0 penalty, 6+ diff = full penalty
                penalty = min(diff_val / 6, 1) * weight
                score -= penalty
        
        return max(0, score)


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def analyze_reference(
    audio: np.ndarray,
    name: str = "",
    sample_rate: int = SAMPLE_RATE
) -> ReferenceProfile:
    """
    Quick reference analysis.
    
    Args:
        audio: Reference audio to analyze
        name: Optional name for the profile
        sample_rate: Audio sample rate
    
    Returns:
        ReferenceProfile with extracted characteristics
    
    Example:
        >>> profile = analyze_reference(my_reference, name="master_ref")
        >>> print(f"LUFS: {profile.integrated_lufs:.1f}")
    """
    analyzer = ReferenceAnalyzer(sample_rate)
    return analyzer.analyze(audio, name)


def match_to_reference(
    input_audio: np.ndarray,
    reference_audio: np.ndarray,
    strength: float = 1.0,
    sample_rate: int = SAMPLE_RATE
) -> np.ndarray:
    """
    One-liner reference matching.
    
    Args:
        input_audio: Audio to process
        reference_audio: Reference to match
        strength: How much to apply (0-1)
        sample_rate: Audio sample rate
    
    Returns:
        Matched audio
    
    Example:
        >>> matched = match_to_reference(my_mix, commercial_track, strength=0.8)
    """
    analyzer = ReferenceAnalyzer(sample_rate)
    profile = analyzer.analyze(reference_audio, "reference")
    
    params = ReferenceMatchParams(
        eq_strength=strength,
        dynamics_strength=strength,
    )
    
    matcher = ReferenceMatcher(profile, params, sample_rate)
    return matcher.process(input_audio)


def get_eq_suggestions(
    input_audio: np.ndarray,
    reference_audio: np.ndarray,
    sample_rate: int = SAMPLE_RATE
) -> Dict[str, Any]:
    """
    Get EQ curve suggestions without applying.
    
    Args:
        input_audio: Audio to analyze
        reference_audio: Reference to compare against
        sample_rate: Audio sample rate
    
    Returns:
        Dict with 'curve' (1/3 octave dB values) and 'bands' (parametric EQ suggestions)
    
    Example:
        >>> suggestions = get_eq_suggestions(my_mix, reference)
        >>> for band in suggestions['bands']:
        ...     print(f"{band['freq']:.0f} Hz: {band['gain_db']:+.1f} dB, Q={band['q']:.1f}")
    """
    analyzer = ReferenceAnalyzer(sample_rate)
    profile = analyzer.analyze(reference_audio)
    
    matcher = EQMatcher(sample_rate=sample_rate)
    curve = matcher.calculate_difference_curve(input_audio, profile)
    bands = matcher.get_eq_bands(curve)
    
    return {
        'curve': curve.tolist(),
        'bands': bands,
        'frequencies': THIRD_OCTAVE_CENTERS.tolist(),
    }


def save_reference_profile(profile: ReferenceProfile, path: str) -> None:
    """
    Save profile to JSON for reuse.
    
    Args:
        profile: Profile to save
        path: Output file path
    
    Example:
        >>> profile = analyze_reference(reference_audio, "my_master")
        >>> save_reference_profile(profile, "profiles/my_master.json")
    """
    with open(path, 'w') as f:
        json.dump(profile.to_dict(), f, indent=2)


def load_reference_profile(path: str) -> ReferenceProfile:
    """
    Load saved profile.
    
    Args:
        path: Path to JSON profile file
    
    Returns:
        ReferenceProfile loaded from file
    
    Example:
        >>> profile = load_reference_profile("profiles/my_master.json")
        >>> matcher = ReferenceMatcher(profile)
    """
    with open(path, 'r') as f:
        data = json.load(f)
    return ReferenceProfile.from_dict(data)


# =============================================================================
# PRESETS (Industry Reference Profiles)
# =============================================================================

# Pre-computed profiles for common mastering targets
# These provide sensible defaults when no reference track is available

REFERENCE_PRESETS: Dict[str, ReferenceProfile] = {
    "streaming_master": ReferenceProfile(
        name="streaming_master",
        spectral_centroid=2500,
        spectral_rolloff=12000,
        spectral_curve=np.array([
            -15, -12, -9, -6, -4, -2, 0, 1, 2, 2,  # Sub to low-mid
            2, 1, 0, 0, 0, 0, -1, -1, -2, -3,       # Mid
            -4, -5, -6, -8, -10, -12, -15, -18, -22, -28, -35  # High
        ]),
        integrated_lufs=-14.0,
        dynamic_range_lu=8.0,
        crest_factor_db=12.0,
        attack_density=3.0,
        attack_sharpness=0.4,
        stereo_width=1.0,
        correlation=0.85,
        low_energy=-6.0,
        mid_energy=-3.0,
        high_energy=-9.0,
        sub_energy=-12.0,
    ),
    
    "club_ready": ReferenceProfile(
        name="club_ready",
        spectral_centroid=2000,
        spectral_rolloff=10000,
        spectral_curve=np.array([
            -10, -6, -3, 0, 2, 3, 3, 2, 1, 0,      # Heavy low end
            -1, -2, -3, -3, -3, -4, -5, -6, -7, -8,
            -10, -12, -14, -17, -20, -24, -28, -32, -38, -45, -55
        ]),
        integrated_lufs=-8.0,
        dynamic_range_lu=5.0,
        crest_factor_db=8.0,
        attack_density=4.0,
        attack_sharpness=0.6,
        stereo_width=1.2,
        correlation=0.9,
        low_energy=-3.0,
        mid_energy=-4.0,
        high_energy=-12.0,
        sub_energy=-6.0,
    ),
    
    "broadcast_safe": ReferenceProfile(
        name="broadcast_safe",
        spectral_centroid=2200,
        spectral_rolloff=11000,
        spectral_curve=np.array([
            -18, -15, -12, -9, -6, -4, -2, 0, 1, 1,
            1, 0, 0, -1, -1, -2, -2, -3, -4, -5,
            -6, -8, -10, -13, -16, -20, -25, -30, -36, -44, -55
        ]),
        integrated_lufs=-23.0,
        dynamic_range_lu=12.0,
        crest_factor_db=18.0,
        attack_density=2.0,
        attack_sharpness=0.3,
        stereo_width=0.8,
        correlation=0.95,
        low_energy=-8.0,
        mid_energy=-2.0,
        high_energy=-8.0,
        sub_energy=-15.0,
    ),
    
    "vinyl_warm": ReferenceProfile(
        name="vinyl_warm",
        spectral_centroid=1800,
        spectral_rolloff=8000,
        spectral_curve=np.array([
            -20, -16, -12, -8, -5, -3, -1, 1, 2, 3,  # Warm low-mids
            3, 3, 2, 1, 0, -1, -3, -5, -8, -12,       # Rolled-off highs
            -16, -20, -25, -30, -36, -42, -50, -58, -68, -80, -95
        ]),
        integrated_lufs=-16.0,
        dynamic_range_lu=14.0,
        crest_factor_db=16.0,
        attack_density=2.5,
        attack_sharpness=0.25,
        stereo_width=0.9,
        correlation=0.92,
        low_energy=-5.0,
        mid_energy=-1.0,
        high_energy=-14.0,
        sub_energy=-10.0,
    ),
    
    "hiphop_master": ReferenceProfile(
        name="hiphop_master",
        spectral_centroid=2100,
        spectral_rolloff=9500,
        spectral_curve=np.array([
            -8, -5, -2, 1, 3, 4, 3, 2, 1, 0,       # Strong sub/low
            -1, -2, -2, -2, -2, -3, -4, -5, -6, -8,
            -10, -13, -16, -20, -25, -30, -36, -44, -54, -66, -80
        ]),
        integrated_lufs=-10.0,
        dynamic_range_lu=6.0,
        crest_factor_db=10.0,
        attack_density=4.0,
        attack_sharpness=0.5,
        stereo_width=1.1,
        correlation=0.88,
        low_energy=-2.0,
        mid_energy=-4.0,
        high_energy=-11.0,
        sub_energy=-5.0,
    ),
    
    "acoustic_natural": ReferenceProfile(
        name="acoustic_natural",
        spectral_centroid=2800,
        spectral_rolloff=14000,
        spectral_curve=np.array([
            -20, -17, -14, -11, -8, -5, -3, -1, 0, 1,
            1, 1, 1, 0, 0, -1, -1, -2, -2, -3,
            -4, -5, -6, -8, -10, -13, -16, -20, -25, -32, -42
        ]),
        integrated_lufs=-16.0,
        dynamic_range_lu=16.0,
        crest_factor_db=20.0,
        attack_density=2.0,
        attack_sharpness=0.35,
        stereo_width=1.3,
        correlation=0.7,
        low_energy=-9.0,
        mid_energy=-2.0,
        high_energy=-6.0,
        sub_energy=-16.0,
    ),
    
    "edm_festival": ReferenceProfile(
        name="edm_festival",
        spectral_centroid=2400,
        spectral_rolloff=11000,
        spectral_curve=np.array([
            -6, -3, 0, 2, 4, 4, 3, 2, 1, 0,
            -1, -2, -2, -2, -3, -3, -4, -5, -6, -8,
            -10, -13, -16, -20, -25, -30, -36, -44, -54, -66, -80
        ]),
        integrated_lufs=-6.0,
        dynamic_range_lu=4.0,
        crest_factor_db=6.0,
        attack_density=6.0,
        attack_sharpness=0.7,
        stereo_width=1.4,
        correlation=0.85,
        low_energy=-2.0,
        mid_energy=-5.0,
        high_energy=-10.0,
        sub_energy=-4.0,
    ),
}


def get_preset_profile(preset_name: str) -> ReferenceProfile:
    """
    Get a preset reference profile by name.
    
    Args:
        preset_name: Name of preset ('streaming_master', 'club_ready', etc.)
    
    Returns:
        ReferenceProfile for the preset
    
    Raises:
        ValueError: If preset name not found
    
    Example:
        >>> profile = get_preset_profile("streaming_master")
        >>> matcher = ReferenceMatcher(profile)
    """
    if preset_name not in REFERENCE_PRESETS:
        available = ', '.join(REFERENCE_PRESETS.keys())
        raise ValueError(f"Unknown preset: {preset_name}. Available: {available}")
    
    return REFERENCE_PRESETS[preset_name]


def list_presets() -> List[str]:
    """
    List available preset profile names.
    
    Returns:
        List of preset names
    """
    return list(REFERENCE_PRESETS.keys())


def apply_preset_match(
    audio: np.ndarray,
    preset_name: str,
    strength: float = 1.0,
    sample_rate: int = SAMPLE_RATE
) -> np.ndarray:
    """
    Apply a preset reference profile to audio.
    
    Args:
        audio: Input audio
        preset_name: Preset to apply
        strength: How much to apply (0-1)
        sample_rate: Audio sample rate
    
    Returns:
        Matched audio
    
    Example:
        >>> ready_for_streaming = apply_preset_match(my_mix, "streaming_master")
    """
    profile = get_preset_profile(preset_name)
    
    params = ReferenceMatchParams(
        eq_strength=strength,
        dynamics_strength=strength,
    )
    
    matcher = ReferenceMatcher(profile, params, sample_rate)
    return matcher.process(audio)
