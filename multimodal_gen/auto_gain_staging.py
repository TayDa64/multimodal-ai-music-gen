"""
Auto-Gain Staging Module

Professional loudness measurement (ITU-R BS.1770-4) and intelligent
gain staging for multi-track mixing. Provides LUFS metering, true peak
detection, and genre-aware gain staging.

Key Features:
- ITU-R BS.1770-4 compliant LUFS measurement
- K-weighting filter implementation
- True peak detection with 4x oversampling
- Momentary, short-term, and integrated loudness
- Genre-specific gain staging templates
- Multi-track stem leveling

References:
- ITU-R BS.1770-4: Algorithms to measure audio programme loudness
- EBU R128: Loudness normalisation and permitted maximum level
- AES TD1004.1.15-10: Recommendation for loudness of audio streaming

Author: Multimodal AI Music Generator
"""

import numpy as np
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from scipy import signal

from .utils import SAMPLE_RATE, TARGET_LUFS, TARGET_TRUE_PEAK


# =============================================================================
# CONSTANTS
# =============================================================================

# ITU-R BS.1770-4 Constants
MOMENTARY_WINDOW_MS = 400       # 400ms window for momentary loudness
SHORT_TERM_WINDOW_MS = 3000     # 3s window for short-term loudness
GATE_BLOCK_MS = 400             # Gating block duration
GATE_OVERLAP = 0.75             # 75% overlap between gating blocks

# Gating thresholds
ABSOLUTE_GATE_LUFS = -70.0      # Absolute threshold (silence gate)
RELATIVE_GATE_LU = -10.0        # Relative threshold (-10 LU below ungated)

# Channel weights (ITU-R BS.1770-4)
CHANNEL_WEIGHTS = {
    'left': 1.0,
    'right': 1.0,
    'center': 1.0,
    'lfe': 0.0,                 # LFE excluded from loudness
    'left_surround': 1.41,
    'right_surround': 1.41,
}

# True peak oversampling factor
TRUE_PEAK_OVERSAMPLE = 4


# =============================================================================
# K-WEIGHTING FILTER DESIGN
# =============================================================================

def design_k_weighting_filters(sample_rate: int) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """
    Design K-weighting filters per ITU-R BS.1770-4.
    
    K-weighting consists of two stages:
    1. Pre-filter (high-shelf): +4 dB @ high frequencies
       - Accounts for acoustic effects of head
    2. High-pass filter: Removes sub-bass
       - Reflects reduced loudness perception at low frequencies
    
    Args:
        sample_rate: Audio sample rate in Hz
    
    Returns:
        Tuple of (b1, a1, b2, a2) filter coefficients:
        - b1, a1: Pre-filter (high shelf) coefficients
        - b2, a2: High-pass filter coefficients
    """
    # Stage 1: Pre-filter (shelving filter)
    # High shelf: fc = 1681.97 Hz, gain = +4 dB, Q = 0.7071
    f0 = 1681.974450955533
    Q = 0.7071752369554196
    K = np.tan(np.pi * f0 / sample_rate)
    Vh = 10 ** (4.0 / 20.0)  # +4 dB
    Vb = Vh ** 0.4996667741545416
    
    a0 = 1.0 + K / Q + K * K
    b0 = (Vh + Vb * K / Q + K * K) / a0
    b1_coef = 2.0 * (K * K - Vh) / a0
    b2_coef = (Vh - Vb * K / Q + K * K) / a0
    a1_coef = 2.0 * (K * K - 1.0) / a0
    a2_coef = (1.0 - K / Q + K * K) / a0
    
    b1 = np.array([b0, b1_coef, b2_coef])
    a1 = np.array([1.0, a1_coef, a2_coef])
    
    # Stage 2: High-pass filter (RLB weighting)
    # 2nd order high-pass at 38.13 Hz
    f0_hp = 38.13547087602444
    Q_hp = 0.5003270373238773
    K_hp = np.tan(np.pi * f0_hp / sample_rate)
    
    a0_hp = 1.0 + K_hp / Q_hp + K_hp * K_hp
    b0_hp = 1.0 / a0_hp
    b1_hp = -2.0 / a0_hp
    b2_hp = 1.0 / a0_hp
    a1_hp = 2.0 * (K_hp * K_hp - 1.0) / a0_hp
    a2_hp = (1.0 - K_hp / Q_hp + K_hp * K_hp) / a0_hp
    
    b2 = np.array([b0_hp, b1_hp, b2_hp])
    a2 = np.array([1.0, a1_hp, a2_hp])
    
    return b1, a1, b2, a2


def apply_k_weighting(audio: np.ndarray, sample_rate: int) -> np.ndarray:
    """
    Apply K-weighting filter to audio.
    
    Args:
        audio: Input audio (mono or stereo)
        sample_rate: Sample rate in Hz
    
    Returns:
        K-weighted audio
    """
    b1, a1, b2, a2 = design_k_weighting_filters(sample_rate)
    
    # Handle mono and stereo
    if len(audio.shape) == 1:
        # Stage 1: Pre-filter
        filtered = signal.lfilter(b1, a1, audio)
        # Stage 2: High-pass
        filtered = signal.lfilter(b2, a2, filtered)
        return filtered
    else:
        result = np.zeros_like(audio)
        for ch in range(audio.shape[1]):
            filtered = signal.lfilter(b1, a1, audio[:, ch])
            filtered = signal.lfilter(b2, a2, filtered)
            result[:, ch] = filtered
        return result


# =============================================================================
# LUFS METER
# =============================================================================

class LUFSMeter:
    """
    Loudness measurement per ITU-R BS.1770-4.
    
    Provides momentary (400ms), short-term (3s), and integrated
    loudness measurements with proper gating.
    
    Usage:
        >>> meter = LUFSMeter(sample_rate=44100)
        >>> lufs = meter.measure_integrated(audio)
        >>> true_peak = meter.measure_true_peak(audio)
    """
    
    def __init__(self, sample_rate: int = SAMPLE_RATE):
        """
        Initialize LUFS meter.
        
        Args:
            sample_rate: Audio sample rate in Hz
        """
        self.sample_rate = sample_rate
        self._init_k_weighting()
        
        # Window sizes in samples
        self.momentary_samples = int(MOMENTARY_WINDOW_MS * sample_rate / 1000)
        self.short_term_samples = int(SHORT_TERM_WINDOW_MS * sample_rate / 1000)
        self.gate_block_samples = int(GATE_BLOCK_MS * sample_rate / 1000)
    
    def _init_k_weighting(self):
        """Initialize K-weighting filter coefficients."""
        self.b1, self.a1, self.b2, self.a2 = design_k_weighting_filters(self.sample_rate)
    
    def _apply_k_weighting(self, audio: np.ndarray) -> np.ndarray:
        """Apply K-weighting filter chain."""
        if len(audio.shape) == 1:
            filtered = signal.lfilter(self.b1, self.a1, audio)
            filtered = signal.lfilter(self.b2, self.a2, filtered)
            return filtered
        else:
            result = np.zeros_like(audio)
            for ch in range(audio.shape[1]):
                filtered = signal.lfilter(self.b1, self.a1, audio[:, ch])
                filtered = signal.lfilter(self.b2, self.a2, filtered)
                result[:, ch] = filtered
            return result
    
    def _calculate_mean_square(self, audio: np.ndarray) -> float:
        """
        Calculate mean square for mono or stereo audio with channel weights.
        
        Args:
            audio: K-weighted audio
        
        Returns:
            Weighted mean square value
        """
        if len(audio.shape) == 1:
            # Mono
            return np.mean(audio ** 2)
        else:
            # Stereo or multi-channel
            n_channels = audio.shape[1]
            
            # Get channel weights (assume L/R for stereo)
            if n_channels == 2:
                weights = [CHANNEL_WEIGHTS['left'], CHANNEL_WEIGHTS['right']]
            else:
                weights = [1.0] * n_channels
            
            # Calculate weighted sum of mean squares
            total = 0.0
            for ch in range(n_channels):
                total += weights[ch] * np.mean(audio[:, ch] ** 2)
            
            return total
    
    def _mean_square_to_lufs(self, mean_square: float) -> float:
        """
        Convert mean square to LUFS.
        
        Formula: LUFS = -0.691 + 10 * log10(sum)
        
        Args:
            mean_square: Weighted mean square value
        
        Returns:
            LUFS value
        """
        if mean_square <= 0:
            return -np.inf
        return -0.691 + 10.0 * np.log10(mean_square)
    
    def measure_momentary(self, audio: np.ndarray) -> float:
        """
        Measure momentary loudness (400ms window).
        
        Returns the loudness of the last 400ms of the audio.
        
        Args:
            audio: Input audio array
        
        Returns:
            Momentary LUFS value
        """
        if len(audio) == 0:
            return -np.inf
        
        # Apply K-weighting
        weighted = self._apply_k_weighting(audio)
        
        # Use last 400ms window
        window_samples = min(self.momentary_samples, len(weighted))
        if len(weighted.shape) == 1:
            window = weighted[-window_samples:]
        else:
            window = weighted[-window_samples:, :]
        
        # Calculate mean square and convert to LUFS
        ms = self._calculate_mean_square(window)
        return self._mean_square_to_lufs(ms)
    
    def measure_short_term(self, audio: np.ndarray) -> float:
        """
        Measure short-term loudness (3s window).
        
        Returns the loudness of the last 3 seconds of the audio.
        
        Args:
            audio: Input audio array
        
        Returns:
            Short-term LUFS value
        """
        if len(audio) == 0:
            return -np.inf
        
        # Apply K-weighting
        weighted = self._apply_k_weighting(audio)
        
        # Use last 3s window
        window_samples = min(self.short_term_samples, len(weighted))
        if len(weighted.shape) == 1:
            window = weighted[-window_samples:]
        else:
            window = weighted[-window_samples:, :]
        
        # Calculate mean square and convert to LUFS
        ms = self._calculate_mean_square(window)
        return self._mean_square_to_lufs(ms)
    
    def measure_integrated(self, audio: np.ndarray) -> float:
        """
        Measure integrated loudness with gating per ITU-R BS.1770-4.
        
        Process:
        1. Apply K-weighting filter
        2. Divide into overlapping 400ms blocks
        3. Calculate loudness per block
        4. First gate: absolute -70 LUFS threshold
        5. Calculate ungated average
        6. Second gate: -10 LU relative to ungated
        7. Calculate final gated average
        
        Args:
            audio: Input audio array
        
        Returns:
            Integrated LUFS value
        """
        if len(audio) == 0:
            return -np.inf
        
        # Apply K-weighting
        weighted = self._apply_k_weighting(audio)
        
        # Calculate block hop size (75% overlap = 25% hop)
        hop_samples = int(self.gate_block_samples * (1.0 - GATE_OVERLAP))
        
        # Collect loudness values for each block
        block_loudness = []
        
        # Get mono or stereo length
        n_samples = len(weighted) if len(weighted.shape) == 1 else weighted.shape[0]
        
        start = 0
        while start + self.gate_block_samples <= n_samples:
            # Extract block
            if len(weighted.shape) == 1:
                block = weighted[start:start + self.gate_block_samples]
            else:
                block = weighted[start:start + self.gate_block_samples, :]
            
            # Calculate block loudness
            ms = self._calculate_mean_square(block)
            lufs = self._mean_square_to_lufs(ms)
            
            if lufs > ABSOLUTE_GATE_LUFS:
                block_loudness.append(ms)
            
            start += hop_samples
        
        if len(block_loudness) == 0:
            return -np.inf
        
        # First pass: ungated average (above absolute threshold)
        ungated_mean = np.mean(block_loudness)
        ungated_lufs = self._mean_square_to_lufs(ungated_mean)
        
        # Second pass: relative gating
        relative_threshold_lufs = ungated_lufs + RELATIVE_GATE_LU
        relative_threshold_ms = 10 ** ((relative_threshold_lufs + 0.691) / 10.0)
        
        # Keep only blocks above relative threshold
        gated_blocks = [ms for ms in block_loudness if ms >= relative_threshold_ms]
        
        if len(gated_blocks) == 0:
            return -np.inf
        
        # Final integrated loudness
        gated_mean = np.mean(gated_blocks)
        return self._mean_square_to_lufs(gated_mean)
    
    def measure_true_peak(self, audio: np.ndarray) -> float:
        """
        Measure true peak level in dBTP using oversampling.
        
        True peak detection uses 4x oversampling to catch
        inter-sample peaks that may occur after D/A conversion.
        
        Args:
            audio: Input audio array
        
        Returns:
            True peak level in dBTP
        """
        if len(audio) == 0:
            return -np.inf
        
        # Handle stereo
        if len(audio.shape) > 1:
            # Find max across all channels
            peaks = []
            for ch in range(audio.shape[1]):
                peaks.append(self._measure_channel_true_peak(audio[:, ch]))
            return max(peaks)
        else:
            return self._measure_channel_true_peak(audio)
    
    def _measure_channel_true_peak(self, audio: np.ndarray) -> float:
        """Measure true peak for a single channel."""
        # Upsample by factor of 4 using polyphase filter
        upsampled = signal.resample_poly(audio, TRUE_PEAK_OVERSAMPLE, 1)
        
        # Find absolute maximum
        peak = np.max(np.abs(upsampled))
        
        if peak <= 0:
            return -np.inf
        
        return 20.0 * np.log10(peak)
    
    def measure_loudness_range(self, audio: np.ndarray) -> float:
        """
        Measure loudness range (LRA) in LU.
        
        LRA describes the variation of loudness over time,
        calculated as the difference between the 95th and 10th
        percentile of short-term loudness measurements.
        
        Args:
            audio: Input audio array
        
        Returns:
            Loudness range in LU
        """
        if len(audio) == 0:
            return 0.0
        
        # Apply K-weighting
        weighted = self._apply_k_weighting(audio)
        
        # Calculate short-term loudness for 3s blocks with 75% overlap
        block_samples = self.short_term_samples
        hop_samples = int(block_samples * (1.0 - GATE_OVERLAP))
        
        n_samples = len(weighted) if len(weighted.shape) == 1 else weighted.shape[0]
        
        loudness_values = []
        start = 0
        
        while start + block_samples <= n_samples:
            if len(weighted.shape) == 1:
                block = weighted[start:start + block_samples]
            else:
                block = weighted[start:start + block_samples, :]
            
            ms = self._calculate_mean_square(block)
            lufs = self._mean_square_to_lufs(ms)
            
            if lufs > ABSOLUTE_GATE_LUFS:
                loudness_values.append(lufs)
            
            start += hop_samples
        
        if len(loudness_values) < 2:
            return 0.0
        
        # Calculate percentiles
        low = np.percentile(loudness_values, 10)
        high = np.percentile(loudness_values, 95)
        
        return high - low
    
    def get_full_analysis(self, audio: np.ndarray) -> Dict:
        """
        Get complete loudness analysis.
        
        Args:
            audio: Input audio array
        
        Returns:
            Dict with all loudness metrics
        """
        return {
            'integrated_lufs': self.measure_integrated(audio),
            'momentary_max_lufs': self._measure_momentary_max(audio),
            'short_term_max_lufs': self._measure_short_term_max(audio),
            'true_peak_dbtp': self.measure_true_peak(audio),
            'loudness_range_lu': self.measure_loudness_range(audio),
        }
    
    def _measure_momentary_max(self, audio: np.ndarray) -> float:
        """Measure maximum momentary loudness."""
        weighted = self._apply_k_weighting(audio)
        
        hop_samples = int(self.momentary_samples * 0.1)  # 10% hop
        n_samples = len(weighted) if len(weighted.shape) == 1 else weighted.shape[0]
        
        max_lufs = -np.inf
        start = 0
        
        while start + self.momentary_samples <= n_samples:
            if len(weighted.shape) == 1:
                block = weighted[start:start + self.momentary_samples]
            else:
                block = weighted[start:start + self.momentary_samples, :]
            
            ms = self._calculate_mean_square(block)
            lufs = self._mean_square_to_lufs(ms)
            max_lufs = max(max_lufs, lufs)
            
            start += hop_samples
        
        return max_lufs
    
    def _measure_short_term_max(self, audio: np.ndarray) -> float:
        """Measure maximum short-term loudness."""
        weighted = self._apply_k_weighting(audio)
        
        hop_samples = int(self.short_term_samples * 0.1)  # 10% hop
        n_samples = len(weighted) if len(weighted.shape) == 1 else weighted.shape[0]
        
        max_lufs = -np.inf
        start = 0
        
        while start + self.short_term_samples <= n_samples:
            if len(weighted.shape) == 1:
                block = weighted[start:start + self.short_term_samples]
            else:
                block = weighted[start:start + self.short_term_samples, :]
            
            ms = self._calculate_mean_square(block)
            lufs = self._mean_square_to_lufs(ms)
            max_lufs = max(max_lufs, lufs)
            
            start += hop_samples
        
        return max_lufs


# =============================================================================
# PARAMETERS
# =============================================================================

@dataclass
class GainStagingParams:
    """
    Parameters for master gain staging.
    
    Attributes:
        target_lufs: Target integrated LUFS (-24 to -6)
        target_true_peak: True peak ceiling in dBTP
        max_gain_db: Maximum amplification allowed
        min_gain_db: Maximum attenuation allowed
        use_limiter: Apply true peak limiter after gain
        limiter_release_ms: Limiter release time in ms
    """
    target_lufs: float = TARGET_LUFS       # -14 LUFS (streaming standard)
    target_true_peak: float = TARGET_TRUE_PEAK  # -1.0 dBTP ceiling
    max_gain_db: float = 12.0              # Maximum +12dB amplification
    min_gain_db: float = -12.0             # Maximum -12dB attenuation
    use_limiter: bool = True               # Apply limiter after gain
    limiter_release_ms: float = 100.0      # Limiter release time


@dataclass
class TrackStagingParams:
    """
    Parameters for individual track gain staging.
    
    Attributes:
        role: Track role ('drums', 'bass', 'melodic', 'vocal', 'fx', '808')
        target_rms_db: Target RMS level in dB
        headroom_db: Headroom to leave for summing
        priority: Mix priority (1=highest, 4=lowest)
    """
    role: str = "other"                    # Track role for template lookup
    target_rms_db: float = -18.0           # Target RMS level
    headroom_db: float = 6.0               # Headroom for summing
    priority: int = 3                       # Mix priority


# =============================================================================
# GENRE TEMPLATES
# =============================================================================

GENRE_TEMPLATES = {
    "trap": {
        "drums": {"target_rms_db": -12, "priority": 1},
        "808": {"target_rms_db": -10, "priority": 1},      # 808 LOUD
        "bass": {"target_rms_db": -14, "priority": 2},
        "melodic": {"target_rms_db": -18, "priority": 3},
        "vocal": {"target_rms_db": -14, "priority": 2},
        "fx": {"target_rms_db": -24, "priority": 4},
        "master_lufs": -8,                                  # Trap is loud
        "headroom_db": 3.0,
    },
    "lofi": {
        "drums": {"target_rms_db": -16, "priority": 2},
        "bass": {"target_rms_db": -14, "priority": 1},
        "melodic": {"target_rms_db": -12, "priority": 1},  # Keys forward
        "vocal": {"target_rms_db": -14, "priority": 2},
        "fx": {"target_rms_db": -18, "priority": 3},
        "master_lufs": -14,                                 # Relaxed
        "headroom_db": 6.0,
    },
    "edm": {
        "drums": {"target_rms_db": -10, "priority": 1},
        "bass": {"target_rms_db": -10, "priority": 1},
        "melodic": {"target_rms_db": -14, "priority": 2},
        "vocal": {"target_rms_db": -12, "priority": 2},
        "fx": {"target_rms_db": -18, "priority": 3},
        "synth": {"target_rms_db": -12, "priority": 1},
        "master_lufs": -6,                                  # EDM is very loud
        "headroom_db": 2.0,
    },
    "hiphop": {
        "drums": {"target_rms_db": -12, "priority": 1},
        "808": {"target_rms_db": -12, "priority": 1},
        "bass": {"target_rms_db": -14, "priority": 2},
        "melodic": {"target_rms_db": -16, "priority": 3},
        "vocal": {"target_rms_db": -12, "priority": 1},    # Vocals important
        "fx": {"target_rms_db": -22, "priority": 4},
        "master_lufs": -10,
        "headroom_db": 4.0,
    },
    "rnb": {
        "drums": {"target_rms_db": -14, "priority": 2},
        "bass": {"target_rms_db": -12, "priority": 1},
        "melodic": {"target_rms_db": -14, "priority": 2},
        "vocal": {"target_rms_db": -10, "priority": 1},    # Vocals forward
        "fx": {"target_rms_db": -20, "priority": 4},
        "keys": {"target_rms_db": -14, "priority": 2},
        "master_lufs": -12,
        "headroom_db": 5.0,
    },
    "pop": {
        "drums": {"target_rms_db": -12, "priority": 1},
        "bass": {"target_rms_db": -14, "priority": 2},
        "melodic": {"target_rms_db": -14, "priority": 2},
        "vocal": {"target_rms_db": -10, "priority": 1},    # Pop = vocals
        "fx": {"target_rms_db": -20, "priority": 3},
        "synth": {"target_rms_db": -14, "priority": 2},
        "master_lufs": -10,
        "headroom_db": 4.0,
    },
    "acoustic": {
        "drums": {"target_rms_db": -18, "priority": 2},
        "bass": {"target_rms_db": -16, "priority": 2},
        "melodic": {"target_rms_db": -14, "priority": 1},  # Guitars forward
        "vocal": {"target_rms_db": -12, "priority": 1},
        "fx": {"target_rms_db": -24, "priority": 4},
        "strings": {"target_rms_db": -16, "priority": 2},
        "master_lufs": -16,                                 # Dynamic
        "headroom_db": 8.0,
    },
    "jazz": {
        "drums": {"target_rms_db": -18, "priority": 2},
        "bass": {"target_rms_db": -14, "priority": 1},
        "melodic": {"target_rms_db": -14, "priority": 1},
        "vocal": {"target_rms_db": -12, "priority": 1},
        "fx": {"target_rms_db": -24, "priority": 4},
        "brass": {"target_rms_db": -14, "priority": 1},
        "keys": {"target_rms_db": -14, "priority": 1},
        "master_lufs": -16,                                 # Very dynamic
        "headroom_db": 10.0,
    },
    "ethiopian": {
        "drums": {"target_rms_db": -14, "priority": 1},
        "bass": {"target_rms_db": -14, "priority": 2},
        "melodic": {"target_rms_db": -12, "priority": 1},  # Melody forward
        "vocal": {"target_rms_db": -12, "priority": 1},
        "fx": {"target_rms_db": -22, "priority": 4},
        "brass": {"target_rms_db": -14, "priority": 1},
        "strings": {"target_rms_db": -14, "priority": 2},
        "master_lufs": -12,
        "headroom_db": 6.0,
    },
    "g_funk": {
        "drums": {"target_rms_db": -14, "priority": 2},
        "bass": {"target_rms_db": -12, "priority": 1},
        "melodic": {"target_rms_db": -14, "priority": 2},
        "vocal": {"target_rms_db": -12, "priority": 1},
        "fx": {"target_rms_db": -20, "priority": 3},
        "synth": {"target_rms_db": -10, "priority": 1},    # G-Funk synths
        "master_lufs": -10,
        "headroom_db": 4.0,
    },
    "boom_bap": {
        "drums": {"target_rms_db": -10, "priority": 1},    # Drums dominant
        "bass": {"target_rms_db": -14, "priority": 2},
        "melodic": {"target_rms_db": -16, "priority": 3},
        "vocal": {"target_rms_db": -12, "priority": 1},
        "fx": {"target_rms_db": -22, "priority": 4},
        "master_lufs": -12,
        "headroom_db": 4.0,
    },
}


# =============================================================================
# TRUE PEAK LIMITER
# =============================================================================

class TruePeakLimiter:
    """
    Simple true peak limiter for preventing overs.
    
    Uses lookahead and soft-knee gain reduction to prevent
    true peaks from exceeding the ceiling.
    """
    
    def __init__(
        self, 
        ceiling_dbtp: float = -1.0,
        release_ms: float = 100.0,
        sample_rate: int = SAMPLE_RATE
    ):
        """
        Initialize true peak limiter.
        
        Args:
            ceiling_dbtp: Maximum true peak level in dBTP
            release_ms: Release time in milliseconds
            sample_rate: Audio sample rate
        """
        self.ceiling_linear = 10 ** (ceiling_dbtp / 20.0)
        self.release_coeff = np.exp(-1.0 / (release_ms * sample_rate / 1000.0))
        self.sample_rate = sample_rate
        
        # Lookahead for catching transients (5ms)
        self.lookahead_samples = int(5.0 * sample_rate / 1000.0)
    
    def process(self, audio: np.ndarray) -> np.ndarray:
        """
        Apply true peak limiting.
        
        Args:
            audio: Input audio array
        
        Returns:
            Limited audio
        """
        if len(audio) == 0:
            return audio
        
        # Get mono signal for gain calculation
        if len(audio.shape) > 1:
            mono = np.max(np.abs(audio), axis=1)
        else:
            mono = np.abs(audio)
        
        # Pad for lookahead
        padded_mono = np.concatenate([mono, np.zeros(self.lookahead_samples)])
        
        # Calculate gain reduction envelope
        n_samples = len(mono)
        gain = np.ones(n_samples)
        
        envelope = 0.0
        
        for i in range(n_samples):
            # Look ahead
            look_idx = min(i + self.lookahead_samples, len(padded_mono) - 1)
            peak = max(padded_mono[i:look_idx + 1].max(), mono[i])
            
            # Calculate required gain reduction
            if peak > self.ceiling_linear:
                target_gain = self.ceiling_linear / (peak + 1e-10)
            else:
                target_gain = 1.0
            
            # Smooth envelope (instant attack, slow release)
            if target_gain < envelope:
                envelope = target_gain
            else:
                envelope = self.release_coeff * envelope + (1 - self.release_coeff) * target_gain
            
            gain[i] = envelope
        
        # Apply gain
        if len(audio.shape) > 1:
            return audio * gain[:, np.newaxis]
        else:
            return audio * gain


# =============================================================================
# AUTO-GAIN STAGING
# =============================================================================

class AutoGainStaging:
    """
    Intelligent gain staging for mastering.
    
    Analyzes audio loudness and applies gain to hit target LUFS
    while respecting true peak limits.
    
    Usage:
        >>> params = GainStagingParams(target_lufs=-14.0)
        >>> staging = AutoGainStaging(params)
        >>> analysis = staging.analyze(audio)
        >>> processed = staging.process(audio)
    """
    
    def __init__(self, params: GainStagingParams = None, sample_rate: int = SAMPLE_RATE):
        """
        Initialize auto-gain staging.
        
        Args:
            params: GainStagingParams configuration
            sample_rate: Audio sample rate
        """
        self.params = params or GainStagingParams()
        self.sample_rate = sample_rate
        self.lufs_meter = LUFSMeter(sample_rate)
        
        if self.params.use_limiter:
            self.limiter = TruePeakLimiter(
                ceiling_dbtp=self.params.target_true_peak,
                release_ms=self.params.limiter_release_ms,
                sample_rate=sample_rate
            )
        else:
            self.limiter = None
    
    def analyze(self, audio: np.ndarray) -> Dict:
        """
        Analyze audio and return loudness metrics.
        
        Args:
            audio: Input audio array
        
        Returns:
            Dict with analysis results
        """
        integrated = self.lufs_meter.measure_integrated(audio)
        momentary_max = self.lufs_meter._measure_momentary_max(audio)
        short_term_max = self.lufs_meter._measure_short_term_max(audio)
        true_peak = self.lufs_meter.measure_true_peak(audio)
        loudness_range = self.lufs_meter.measure_loudness_range(audio)
        
        # Calculate suggested gain
        if integrated > -np.inf:
            suggested_gain = self.params.target_lufs - integrated
            suggested_gain = np.clip(
                suggested_gain, 
                self.params.min_gain_db, 
                self.params.max_gain_db
            )
        else:
            suggested_gain = 0.0
        
        # Check if limiting will be needed
        if true_peak > -np.inf:
            peak_after_gain = true_peak + suggested_gain
            needs_limiting = peak_after_gain > self.params.target_true_peak
        else:
            needs_limiting = False
        
        return {
            "integrated_lufs": integrated,
            "momentary_max_lufs": momentary_max,
            "short_term_max_lufs": short_term_max,
            "true_peak_dbtp": true_peak,
            "loudness_range_lu": loudness_range,
            "suggested_gain_db": suggested_gain,
            "needs_limiting": needs_limiting,
            "target_lufs": self.params.target_lufs,
        }
    
    def process(self, audio: np.ndarray) -> np.ndarray:
        """
        Apply gain staging to hit target LUFS.
        
        Args:
            audio: Input audio array
        
        Returns:
            Gain-staged audio
        """
        if len(audio) == 0:
            return audio
        
        # Measure current loudness
        current_lufs = self.lufs_meter.measure_integrated(audio)
        
        if current_lufs <= -np.inf:
            # Audio is silent
            return audio
        
        # Calculate required gain
        gain_db = self.params.target_lufs - current_lufs
        gain_db = np.clip(gain_db, self.params.min_gain_db, self.params.max_gain_db)
        
        # Apply gain
        gain_linear = 10 ** (gain_db / 20.0)
        result = audio * gain_linear
        
        # Apply limiter if enabled
        if self.limiter is not None:
            result = self.limiter.process(result)
        
        return result
    
    def process_to_peak(self, audio: np.ndarray) -> np.ndarray:
        """
        Normalize to true peak ceiling instead of LUFS.
        
        Useful for stems where LUFS isn't the primary target.
        
        Args:
            audio: Input audio array
        
        Returns:
            Peak-normalized audio
        """
        if len(audio) == 0:
            return audio
        
        true_peak = self.lufs_meter.measure_true_peak(audio)
        
        if true_peak <= -np.inf:
            return audio
        
        # Calculate gain to hit ceiling
        gain_db = self.params.target_true_peak - true_peak
        gain_db = np.clip(gain_db, self.params.min_gain_db, self.params.max_gain_db)
        
        gain_linear = 10 ** (gain_db / 20.0)
        return audio * gain_linear


# =============================================================================
# MULTI-TRACK STAGING
# =============================================================================

class MultiTrackStaging:
    """
    Intelligent gain staging for multiple stems.
    
    Uses genre templates to set appropriate levels for each
    track role (drums, bass, melodic, etc.).
    
    Usage:
        >>> staging = MultiTrackStaging(genre="trap")
        >>> staged_tracks = staging.stage_tracks({
        ...     "drums": drum_audio,
        ...     "808": bass_audio,
        ...     "melodic": melody_audio
        ... })
    """
    
    def __init__(self, genre: str = "trap", sample_rate: int = SAMPLE_RATE):
        """
        Initialize multi-track staging.
        
        Args:
            genre: Genre template to use
            sample_rate: Audio sample rate
        """
        self.genre = genre.lower()
        self.sample_rate = sample_rate
        
        # Get template (fall back to trap if unknown)
        self.template = GENRE_TEMPLATES.get(self.genre, GENRE_TEMPLATES["trap"])
        
        self.lufs_meter = LUFSMeter(sample_rate)
    
    def _calculate_rms_db(self, audio: np.ndarray) -> float:
        """Calculate RMS level in dB."""
        if len(audio) == 0:
            return -np.inf
        
        if len(audio.shape) > 1:
            rms = np.sqrt(np.mean(audio ** 2))
        else:
            rms = np.sqrt(np.mean(audio ** 2))
        
        if rms <= 0:
            return -np.inf
        
        return 20.0 * np.log10(rms)
    
    def analyze_tracks(self, tracks: Dict[str, np.ndarray]) -> Dict[str, Dict]:
        """
        Analyze all tracks and return level information.
        
        Args:
            tracks: Dict mapping track role to audio array
        
        Returns:
            Dict with analysis for each track
        """
        analysis = {}
        
        for role, audio in tracks.items():
            current_rms = self._calculate_rms_db(audio)
            current_lufs = self.lufs_meter.measure_integrated(audio)
            true_peak = self.lufs_meter.measure_true_peak(audio)
            
            # Get target from template
            template_entry = self.template.get(role, {"target_rms_db": -18, "priority": 3})
            target_rms = template_entry["target_rms_db"]
            priority = template_entry["priority"]
            
            # Calculate suggested gain
            if current_rms > -np.inf:
                suggested_gain = target_rms - current_rms
            else:
                suggested_gain = 0.0
            
            analysis[role] = {
                "current_rms_db": current_rms,
                "current_lufs": current_lufs,
                "true_peak_dbtp": true_peak,
                "target_rms_db": target_rms,
                "priority": priority,
                "suggested_gain_db": suggested_gain,
            }
        
        return analysis
    
    def stage_tracks(self, tracks: Dict[str, np.ndarray]) -> Dict[str, np.ndarray]:
        """
        Apply genre-aware gain staging to all tracks.
        
        Args:
            tracks: Dict mapping track role to audio array
        
        Returns:
            Dict mapping track role to staged audio
        """
        analysis = self.analyze_tracks(tracks)
        staged = {}
        
        # Sort by priority (process highest priority first)
        sorted_roles = sorted(
            analysis.keys(),
            key=lambda r: analysis[r]["priority"]
        )
        
        headroom_db = self.template.get("headroom_db", 6.0)
        
        for role in sorted_roles:
            audio = tracks[role]
            info = analysis[role]
            
            if len(audio) == 0 or info["current_rms_db"] <= -np.inf:
                staged[role] = audio
                continue
            
            # Calculate gain with headroom consideration
            gain_db = info["suggested_gain_db"]
            
            # Limit maximum gain based on headroom needs
            max_gain = 12.0 - (headroom_db / 2)
            gain_db = np.clip(gain_db, -12.0, max_gain)
            
            # Apply gain
            gain_linear = 10 ** (gain_db / 20.0)
            staged[role] = audio * gain_linear
        
        return staged
    
    def get_mix_preview(self, tracks: Dict[str, np.ndarray]) -> np.ndarray:
        """
        Generate a quick mix preview after staging.
        
        Args:
            tracks: Dict mapping track role to audio array
        
        Returns:
            Summed mix preview
        """
        staged = self.stage_tracks(tracks)
        
        # Find longest track
        max_len = max(len(audio) if len(audio.shape) == 1 else audio.shape[0] 
                      for audio in staged.values())
        
        # Determine channel count
        sample_audio = next(iter(staged.values()))
        n_channels = sample_audio.shape[1] if len(sample_audio.shape) > 1 else 1
        
        # Initialize mix buffer
        if n_channels > 1:
            mix = np.zeros((max_len, n_channels))
        else:
            mix = np.zeros(max_len)
        
        # Sum all tracks
        for audio in staged.values():
            audio_len = len(audio) if len(audio.shape) == 1 else audio.shape[0]
            if n_channels > 1:
                mix[:audio_len] += audio
            else:
                mix[:audio_len] += audio
        
        # Apply master limiting
        target_lufs = self.template.get("master_lufs", -14)
        params = GainStagingParams(target_lufs=target_lufs)
        master_staging = AutoGainStaging(params, self.sample_rate)
        
        return master_staging.process(mix)


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def measure_lufs(audio: np.ndarray, sample_rate: int = SAMPLE_RATE) -> float:
    """
    Quick integrated LUFS measurement.
    
    Args:
        audio: Input audio array
        sample_rate: Audio sample rate
    
    Returns:
        Integrated LUFS value
    
    Example:
        >>> lufs = measure_lufs(my_audio)
        >>> print(f"Loudness: {lufs:.1f} LUFS")
    """
    meter = LUFSMeter(sample_rate)
    return meter.measure_integrated(audio)


def normalize_to_lufs(
    audio: np.ndarray, 
    target_lufs: float = -14.0, 
    sample_rate: int = SAMPLE_RATE
) -> np.ndarray:
    """
    Normalize audio to target LUFS.
    
    Args:
        audio: Input audio array
        target_lufs: Target integrated LUFS
        sample_rate: Audio sample rate
    
    Returns:
        Normalized audio
    
    Example:
        >>> normalized = normalize_to_lufs(my_audio, target_lufs=-14.0)
    """
    params = GainStagingParams(target_lufs=target_lufs)
    staging = AutoGainStaging(params, sample_rate)
    return staging.process(audio)


def stage_for_genre(
    tracks: Dict[str, np.ndarray], 
    genre: str, 
    sample_rate: int = SAMPLE_RATE
) -> Dict[str, np.ndarray]:
    """
    Apply genre-aware gain staging to track dict.
    
    Args:
        tracks: Dict mapping track role to audio array
        genre: Genre template to use
        sample_rate: Audio sample rate
    
    Returns:
        Dict mapping track role to staged audio
    
    Example:
        >>> staged = stage_for_genre({
        ...     "drums": drum_audio,
        ...     "808": bass_808,
        ...     "melodic": melody
        ... }, genre="trap")
    """
    staging = MultiTrackStaging(genre, sample_rate)
    return staging.stage_tracks(tracks)


def calculate_headroom(tracks: List[np.ndarray], sample_rate: int = SAMPLE_RATE) -> float:
    """
    Calculate remaining headroom after summing tracks.
    
    Args:
        tracks: List of audio arrays to sum
        sample_rate: Audio sample rate
    
    Returns:
        Headroom in dB below 0 dBFS
    
    Example:
        >>> headroom = calculate_headroom([drums, bass, melody])
        >>> print(f"Headroom: {headroom:.1f} dB")
    """
    if not tracks:
        return np.inf
    
    # Find max length
    max_len = max(len(t) if len(t.shape) == 1 else t.shape[0] for t in tracks)
    
    # Sum tracks
    summed = np.zeros(max_len)
    for track in tracks:
        track_len = len(track) if len(track.shape) == 1 else track.shape[0]
        if len(track.shape) > 1:
            # Use mono sum for peak detection
            summed[:track_len] += np.sum(track, axis=1)
        else:
            summed[:track_len] += track
    
    # Measure true peak
    meter = LUFSMeter(sample_rate)
    true_peak = meter.measure_true_peak(summed)
    
    if true_peak <= -np.inf:
        return np.inf
    
    # Headroom is distance from 0 dBFS
    return -true_peak


def quick_analysis(audio: np.ndarray, sample_rate: int = SAMPLE_RATE) -> Dict:
    """
    Get quick loudness analysis of audio.
    
    Args:
        audio: Input audio array
        sample_rate: Audio sample rate
    
    Returns:
        Dict with loudness metrics
    
    Example:
        >>> stats = quick_analysis(my_audio)
        >>> print(f"LUFS: {stats['integrated_lufs']:.1f}")
        >>> print(f"True Peak: {stats['true_peak_dbtp']:.1f} dBTP")
    """
    meter = LUFSMeter(sample_rate)
    return meter.get_full_analysis(audio)


# =============================================================================
# PRESETS
# =============================================================================

GAIN_STAGING_PRESETS = {
    "streaming": GainStagingParams(
        target_lufs=-14.0,
        target_true_peak=-1.0,
        use_limiter=True,
    ),
    "spotify": GainStagingParams(
        target_lufs=-14.0,
        target_true_peak=-1.0,
        use_limiter=True,
    ),
    "apple_music": GainStagingParams(
        target_lufs=-16.0,
        target_true_peak=-1.0,
        use_limiter=True,
    ),
    "youtube": GainStagingParams(
        target_lufs=-14.0,
        target_true_peak=-1.0,
        use_limiter=True,
    ),
    "broadcast": GainStagingParams(
        target_lufs=-23.0,
        target_true_peak=-1.0,
        use_limiter=True,
    ),
    "cinema": GainStagingParams(
        target_lufs=-24.0,
        target_true_peak=-1.0,
        use_limiter=True,
    ),
    "mastering_loud": GainStagingParams(
        target_lufs=-8.0,
        target_true_peak=-0.3,
        use_limiter=True,
    ),
    "mastering_dynamic": GainStagingParams(
        target_lufs=-16.0,
        target_true_peak=-1.0,
        use_limiter=True,
    ),
}


def apply_gain_preset(
    audio: np.ndarray, 
    preset_name: str, 
    sample_rate: int = SAMPLE_RATE
) -> np.ndarray:
    """
    Apply a named gain staging preset.
    
    Args:
        audio: Input audio array
        preset_name: Preset name ('streaming', 'spotify', 'apple_music',
                    'youtube', 'broadcast', 'cinema', 'mastering_loud',
                    'mastering_dynamic')
        sample_rate: Audio sample rate
    
    Returns:
        Processed audio
    
    Example:
        >>> ready_for_spotify = apply_gain_preset(my_mix, 'spotify')
    """
    if preset_name not in GAIN_STAGING_PRESETS:
        available = ', '.join(GAIN_STAGING_PRESETS.keys())
        raise ValueError(f"Unknown preset: {preset_name}. Available: {available}")
    
    params = GAIN_STAGING_PRESETS[preset_name]
    staging = AutoGainStaging(params, sample_rate)
    return staging.process(audio)
