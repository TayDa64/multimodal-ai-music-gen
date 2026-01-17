"""
True Peak Limiter with Intersample Peak (ISP) Detection

Professional-grade true peak limiting following ITU-R BS.1770-4 standards.
Designed for streaming platform compliance (Spotify, Apple Music, YouTube).

Key Features:
- 4x oversampling for intersample peak detection
- Lookahead gain reduction to catch ISP before they occur
- Smooth gain envelope to avoid audible artifacts
- Compliance reporting for -1 dBTP ceiling verification

References:
- ITU-R BS.1770-4: Algorithms to measure audio programme loudness
- EBU R128: Loudness normalisation and permitted maximum level
- AES TD1004.1.15-10: Recommendation for Loudness of Audio Streaming

Author: Multimodal AI Music Generator
"""

import numpy as np
from dataclasses import dataclass
from typing import Optional, Dict, Tuple
from scipy import signal

from .mix_chain import EffectParams


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def measure_true_peak(audio: np.ndarray, oversampling: int = 4) -> float:
    """
    Measure the true peak level of audio using oversampling.
    
    True peak measurement accounts for intersample peaks (ISP) that can occur
    when the digital signal is reconstructed to analog. This is critical for
    streaming platforms that require -1 dBTP or lower.
    
    Args:
        audio: Input audio array (mono or stereo)
        oversampling: Oversampling factor (2, 4, or 8). Default 4x per ITU-R BS.1770-4
    
    Returns:
        True peak level as linear amplitude (not dB)
    
    Reference:
        ITU-R BS.1770-4 Section 2.4 - True-peak level measurement
    """
    if len(audio) == 0:
        return 0.0
    
    # Validate oversampling factor
    if oversampling not in [2, 4, 8]:
        oversampling = 4
    
    # Handle stereo by processing both channels
    if len(audio.shape) > 1 and audio.shape[1] == 2:
        left_peak = measure_true_peak(audio[:, 0], oversampling)
        right_peak = measure_true_peak(audio[:, 1], oversampling)
        return max(left_peak, right_peak)
    
    # Ensure 1D array
    audio_1d = audio.flatten() if len(audio.shape) > 1 else audio
    
    # Oversample using polyphase filtering
    # resample_poly uses efficient polyphase implementation
    oversampled = signal.resample_poly(audio_1d, up=oversampling, down=1)
    
    # Find maximum absolute value in oversampled domain
    true_peak = np.max(np.abs(oversampled))
    
    return float(true_peak)


def linear_to_db(linear: float) -> float:
    """Convert linear amplitude to decibels (dBTP)."""
    if linear <= 0:
        return -np.inf
    return 20.0 * np.log10(linear)


def db_to_linear(db: float) -> float:
    """Convert decibels to linear amplitude."""
    return 10.0 ** (db / 20.0)


# =============================================================================
# PARAMETERS
# =============================================================================

@dataclass
class TruePeakLimiterParams(EffectParams):
    """
    Parameters for True Peak Limiter with ISP detection.
    
    Designed for streaming platform compliance. Default values target
    the -1 dBTP ceiling recommended by Spotify, Apple Music, and YouTube.
    
    Attributes:
        ceiling_dbtp: True Peak ceiling in dBTP. -1.0 for streaming platforms.
        oversampling: Oversampling factor for ISP detection (2, 4, or 8).
                     4x is recommended by ITU-R BS.1770-4.
        lookahead_ms: Lookahead time in milliseconds. 1-5ms typical.
                     Allows limiter to anticipate peaks before they occur.
        release_ms: Release time in milliseconds. 50-300ms typical.
                   Controls how quickly gain returns after limiting.
        attack_ms: Attack time in milliseconds. Very fast (0.05-0.5ms).
                  Must be fast enough to catch transients.
    
    Reference:
        ITU-R BS.1770-4, EBU R128
    """
    ceiling_dbtp: float = -1.0      # True Peak ceiling (streaming standard)
    oversampling: int = 4           # 4x recommended by ITU-R BS.1770-4
    lookahead_ms: float = 1.5       # Lookahead for ISP anticipation
    release_ms: float = 100.0       # Release time (50-300ms typical)
    attack_ms: float = 0.1          # Very fast attack for transients


# =============================================================================
# TRUE PEAK LIMITER CLASS
# =============================================================================

class TruePeakLimiter:
    """
    Professional True Peak Limiter with Intersample Peak (ISP) detection.
    
    This limiter ensures audio peaks stay below a specified ceiling in the
    true peak domain, accounting for intersample peaks that occur during
    digital-to-analog conversion. Essential for streaming platform compliance.
    
    Algorithm:
    1. Oversample input signal 4x using polyphase filtering
    2. Detect peaks in oversampled domain (true peak measurement)
    3. Calculate required gain reduction with lookahead buffer
    4. Apply smooth gain envelope to avoid audible artifacts
    5. Downsample back to original rate
    
    Usage:
        >>> params = TruePeakLimiterParams(ceiling_dbtp=-1.0)
        >>> limiter = TruePeakLimiter(params, sample_rate=44100)
        >>> limited_audio = limiter.process(audio)
        >>> report = limiter.get_compliance_report()
    
    Reference:
        ITU-R BS.1770-4: Algorithms to measure audio programme loudness
        EBU R128: Loudness normalisation and permitted maximum level
    """
    
    def __init__(self, params: TruePeakLimiterParams, sample_rate: int = 44100):
        """
        Initialize the True Peak Limiter.
        
        Args:
            params: TruePeakLimiterParams configuration
            sample_rate: Audio sample rate in Hz (default: 44100)
        """
        self.params = params
        self.sample_rate = sample_rate
        
        # Validate and set oversampling
        self.oversampling = params.oversampling if params.oversampling in [2, 4, 8] else 4
        self.oversampled_rate = sample_rate * self.oversampling
        
        # Convert ceiling to linear with small safety margin (0.05 dB)
        # This accounts for smoothing and downsampling artifacts
        safety_margin_db = 0.1
        self.ceiling_linear = db_to_linear(params.ceiling_dbtp - safety_margin_db)
        self.final_ceiling_linear = db_to_linear(params.ceiling_dbtp)
        
        # Calculate lookahead in samples (at oversampled rate)
        self.lookahead_samples = int(params.lookahead_ms * self.oversampled_rate / 1000.0)
        self.lookahead_samples = max(1, self.lookahead_samples)
        
        # Calculate attack/release coefficients for envelope smoothing
        # Using one-pole IIR filter coefficients
        self.attack_coeff = np.exp(-1.0 / (params.attack_ms * self.oversampled_rate / 1000.0))
        self.release_coeff = np.exp(-1.0 / (params.release_ms * self.oversampled_rate / 1000.0))
        
        # Statistics for compliance reporting
        self._input_true_peak = 0.0
        self._output_true_peak = 0.0
        self._max_gain_reduction_db = 0.0
        self._samples_limited = 0
        self._total_samples = 0
    
    def process(self, audio: np.ndarray) -> np.ndarray:
        """
        Process audio through the True Peak Limiter.
        
        Handles both mono and stereo input. For stereo, uses linked detection
        (same gain reduction on both channels) to preserve stereo image.
        
        Args:
            audio: Input audio array. Shape: (samples,) for mono or
                  (samples, 2) for stereo.
        
        Returns:
            Limited audio with same shape as input, guaranteed to have
            true peak level at or below ceiling_dbtp.
        """
        if len(audio) == 0:
            return audio
        
        # Store input true peak for reporting
        self._input_true_peak = measure_true_peak(audio, self.oversampling)
        
        # Handle stereo vs mono
        is_stereo = len(audio.shape) > 1 and audio.shape[1] == 2
        
        if is_stereo:
            # Process stereo with linked detection
            limited = self._process_stereo(audio)
        else:
            # Process mono
            limited = self._process_mono(audio)
        
        # Final compliance verification pass
        # If output exceeds ceiling due to reconstruction, apply micro-correction
        output_tp = measure_true_peak(limited, self.oversampling)
        if output_tp > self.final_ceiling_linear:
            # Calculate correction factor
            correction = self.final_ceiling_linear / output_tp * 0.999  # Small margin
            limited = limited * correction
        
        # Measure output true peak for compliance verification
        self._output_true_peak = measure_true_peak(limited, self.oversampling)
        
        return limited
    
    def _process_mono(self, audio: np.ndarray) -> np.ndarray:
        """Process mono audio through the limiter."""
        # Step 1: Oversample
        oversampled = signal.resample_poly(audio, up=self.oversampling, down=1)
        
        # Step 2: Calculate gain reduction envelope
        gain_envelope = self._calculate_gain_envelope(oversampled)
        
        # Step 3: Apply gain reduction
        limited_oversampled = oversampled * gain_envelope
        
        # Step 4: Hard clip in oversampled domain for guaranteed compliance
        limited_oversampled = np.clip(
            limited_oversampled, 
            -self.final_ceiling_linear, 
            self.final_ceiling_linear
        )
        
        # Step 5: Downsample back to original rate
        limited = signal.resample_poly(limited_oversampled, up=1, down=self.oversampling)
        
        # Ensure output length matches input
        limited = limited[:len(audio)]
        
        return limited
    
    def _process_stereo(self, audio: np.ndarray) -> np.ndarray:
        """
        Process stereo audio with linked detection.
        
        Uses the maximum peak across both channels for gain calculation
        to preserve the stereo image.
        """
        left = audio[:, 0]
        right = audio[:, 1]
        
        # Step 1: Oversample both channels
        left_os = signal.resample_poly(left, up=self.oversampling, down=1)
        right_os = signal.resample_poly(right, up=self.oversampling, down=1)
        
        # Step 2: Calculate linked gain envelope (max of both channels)
        combined_peak = np.maximum(np.abs(left_os), np.abs(right_os))
        gain_envelope = self._calculate_gain_envelope_from_peaks(combined_peak)
        
        # Step 3: Apply same gain reduction to both channels
        left_limited = left_os * gain_envelope
        right_limited = right_os * gain_envelope
        
        # Step 4: Hard clip in oversampled domain for guaranteed compliance
        left_limited = np.clip(left_limited, -self.final_ceiling_linear, self.final_ceiling_linear)
        right_limited = np.clip(right_limited, -self.final_ceiling_linear, self.final_ceiling_linear)
        
        # Step 5: Downsample back to original rate
        left_out = signal.resample_poly(left_limited, up=1, down=self.oversampling)
        right_out = signal.resample_poly(right_limited, up=1, down=self.oversampling)
        
        # Ensure output length matches input
        left_out = left_out[:len(left)]
        right_out = right_out[:len(right)]
        
        return np.column_stack([left_out, right_out])
    
    def _calculate_gain_envelope(self, audio: np.ndarray) -> np.ndarray:
        """
        Calculate the gain reduction envelope for mono signal.
        
        Uses lookahead to anticipate peaks and smooth envelope following
        for artifact-free limiting.
        """
        peaks = np.abs(audio)
        return self._calculate_gain_envelope_from_peaks(peaks)
    
    def _calculate_gain_envelope_from_peaks(self, peaks: np.ndarray) -> np.ndarray:
        """
        Calculate gain envelope from peak values.
        
        Algorithm:
        1. Calculate target gain for each sample based on peak vs ceiling
        2. Apply lookahead by finding minimum gain in lookahead window
        3. Smooth the gain envelope using attack/release
        """
        n_samples = len(peaks)
        
        # Calculate raw gain needed at each sample
        # gain = ceiling / peak (or 1.0 if below ceiling)
        raw_gain = np.ones(n_samples)
        above_ceiling = peaks > self.ceiling_linear
        
        if np.any(above_ceiling):
            raw_gain[above_ceiling] = self.ceiling_linear / peaks[above_ceiling]
        
        # Track statistics
        if np.any(above_ceiling):
            min_gain = np.min(raw_gain)
            self._max_gain_reduction_db = max(
                self._max_gain_reduction_db,
                abs(linear_to_db(min_gain))
            )
            self._samples_limited += np.sum(above_ceiling)
        self._total_samples += n_samples
        
        # Apply lookahead: look ahead and take minimum gain
        # This ensures we reduce gain BEFORE the peak arrives
        lookahead_gain = np.ones(n_samples)
        
        for i in range(n_samples):
            # Look ahead window
            end_idx = min(i + self.lookahead_samples, n_samples)
            lookahead_gain[i] = np.min(raw_gain[i:end_idx])
        
        # Smooth the gain envelope with attack/release
        smoothed_gain = self._smooth_gain_envelope(lookahead_gain)
        
        return smoothed_gain
    
    def _smooth_gain_envelope(self, gain: np.ndarray) -> np.ndarray:
        """
        Smooth gain envelope using exponential attack/release.
        
        Attack: How fast gain reduction is applied (very fast)
        Release: How fast gain recovers after peak passes (slower)
        """
        n_samples = len(gain)
        smoothed = np.ones(n_samples)
        
        envelope_state = 1.0
        
        for i in range(n_samples):
            target = gain[i]
            
            if target < envelope_state:
                # Attack: gain needs to decrease (fast)
                coeff = self.attack_coeff
            else:
                # Release: gain recovering (slower)
                coeff = self.release_coeff
            
            # One-pole smoothing: y[n] = coeff * y[n-1] + (1 - coeff) * x[n]
            envelope_state = coeff * envelope_state + (1.0 - coeff) * target
            smoothed[i] = envelope_state
        
        return smoothed
    
    @staticmethod
    def measure_true_peak_db(audio: np.ndarray, oversampling: int = 4) -> float:
        """
        Measure true peak level in dBTP.
        
        Static method for convenient true peak measurement without
        instantiating the limiter.
        
        Args:
            audio: Input audio array (mono or stereo)
            oversampling: Oversampling factor (default: 4)
        
        Returns:
            True peak level in dBTP (decibels relative to true peak)
        
        Example:
            >>> peak_db = TruePeakLimiter.measure_true_peak_db(audio)
            >>> if peak_db > -1.0:
            ...     print("Audio exceeds streaming platform limits!")
        """
        true_peak_linear = measure_true_peak(audio, oversampling)
        return linear_to_db(true_peak_linear)
    
    def get_compliance_report(self) -> Dict:
        """
        Get a compliance report for streaming platform requirements.
        
        Returns a dictionary with:
        - Input/output true peak levels
        - Whether output meets the ceiling requirement
        - Maximum gain reduction applied
        - Percentage of samples that were limited
        
        Returns:
            Dict with compliance information:
            {
                'input_true_peak_dbtp': float,
                'output_true_peak_dbtp': float,
                'ceiling_dbtp': float,
                'compliant': bool,
                'max_gain_reduction_db': float,
                'samples_limited_percent': float,
                'streaming_platforms': {
                    'spotify': bool,
                    'apple_music': bool,
                    'youtube': bool
                }
            }
        """
        input_dbtp = linear_to_db(self._input_true_peak)
        output_dbtp = linear_to_db(self._output_true_peak)
        
        # Check compliance with common streaming platform requirements
        # All major platforms recommend -1 dBTP or lower
        spotify_compliant = output_dbtp <= -1.0
        apple_music_compliant = output_dbtp <= -1.0
        youtube_compliant = output_dbtp <= -1.0
        
        # Calculate percentage of samples limited
        limited_percent = 0.0
        if self._total_samples > 0:
            # Adjust for oversampling (statistics collected at oversampled rate)
            limited_percent = (self._samples_limited / self._total_samples) * 100.0
        
        return {
            'input_true_peak_dbtp': round(input_dbtp, 2),
            'output_true_peak_dbtp': round(output_dbtp, 2),
            'ceiling_dbtp': self.params.ceiling_dbtp,
            'compliant': output_dbtp <= self.params.ceiling_dbtp,
            'max_gain_reduction_db': round(self._max_gain_reduction_db, 2),
            'samples_limited_percent': round(limited_percent, 2),
            'streaming_platforms': {
                'spotify': spotify_compliant,
                'apple_music': apple_music_compliant,
                'youtube': youtube_compliant
            }
        }
    
    def reset_statistics(self) -> None:
        """Reset compliance statistics for a new processing session."""
        self._input_true_peak = 0.0
        self._output_true_peak = 0.0
        self._max_gain_reduction_db = 0.0
        self._samples_limited = 0
        self._total_samples = 0


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def limit_to_true_peak(
    audio: np.ndarray,
    ceiling_dbtp: float = -1.0,
    sample_rate: int = 44100,
    return_report: bool = False
) -> Tuple[np.ndarray, Optional[Dict]]:
    """
    Convenience function to limit audio to a true peak ceiling.
    
    Args:
        audio: Input audio array (mono or stereo)
        ceiling_dbtp: True peak ceiling in dBTP (default: -1.0 for streaming)
        sample_rate: Audio sample rate
        return_report: If True, also return compliance report
    
    Returns:
        Limited audio array, and optionally a compliance report dict
    
    Example:
        >>> limited, report = limit_to_true_peak(audio, -1.0, return_report=True)
        >>> print(f"Output: {report['output_true_peak_dbtp']} dBTP")
    """
    params = TruePeakLimiterParams(ceiling_dbtp=ceiling_dbtp)
    limiter = TruePeakLimiter(params, sample_rate)
    
    limited = limiter.process(audio)
    
    if return_report:
        return limited, limiter.get_compliance_report()
    
    return limited, None


def check_true_peak_compliance(
    audio: np.ndarray,
    ceiling_dbtp: float = -1.0,
    oversampling: int = 4
) -> Dict:
    """
    Check if audio meets true peak requirements without processing.
    
    Args:
        audio: Input audio array
        ceiling_dbtp: Required ceiling in dBTP
        oversampling: Oversampling factor for measurement
    
    Returns:
        Dict with compliance status and measured true peak
    """
    true_peak_linear = measure_true_peak(audio, oversampling)
    true_peak_dbtp = linear_to_db(true_peak_linear)
    
    return {
        'true_peak_dbtp': round(true_peak_dbtp, 2),
        'ceiling_dbtp': ceiling_dbtp,
        'compliant': true_peak_dbtp <= ceiling_dbtp,
        'exceeds_by_db': round(max(0, true_peak_dbtp - ceiling_dbtp), 2),
        'streaming_compliant': true_peak_dbtp <= -1.0
    }
