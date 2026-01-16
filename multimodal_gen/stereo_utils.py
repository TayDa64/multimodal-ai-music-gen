"""
Stereo Utilities Module - Mid/Side Processing and Stereo Image Control.

Professional masterclass M/S processing for music production:
- Stereo width enhancement/reduction
- Center (mid) isolation
- Side-only effects (reverb, EQ)
- Bass mono-ification for club systems
- M/S EQ with independent mid/side curves

Mathematical foundation:
  Encode: M = (L+R)/2, S = (L-R)/2
  Decode: L = M+S, R = M-S

This module provides production-ready stereo processing utilities
for professional audio mastering and mixing workflows.
"""

import numpy as np
from typing import Callable, Optional, Tuple, Union
from dataclasses import dataclass, field
from scipy.signal import butter, sosfiltfilt

# Type aliases
AudioArray = np.ndarray
ProcessorFn = Callable[[np.ndarray], np.ndarray]


@dataclass
class MSSignal:
    """
    Mid/Side signal container with metadata.
    
    This dataclass holds the separated mid and side components
    of a stereo signal along with associated metadata for
    reconstruction and processing.
    
    Attributes:
        mid: The mid (center) component of the stereo signal.
             Contains mono-compatible content (L+R)/2.
        side: The side (stereo difference) component.
              Contains stereo width information (L-R)/2.
        sample_rate: Sample rate of the audio in Hz.
        original_peak: Peak amplitude of the original stereo signal
                       before M/S encoding. Used for gain staging.
    
    Example:
        >>> audio = np.random.randn(2, 44100)  # Stereo audio
        >>> mid, side = ms_encode(audio)
        >>> ms_signal = MSSignal(
        ...     mid=mid,
        ...     side=side,
        ...     sample_rate=44100,
        ...     original_peak=float(np.max(np.abs(audio)))
        ... )
    """
    mid: np.ndarray
    side: np.ndarray
    sample_rate: int = 44100
    original_peak: float = 0.0


# Stereo width presets for common use cases
STEREO_PRESETS = {
    "mono": 0.0,           # Full mono collapse
    "narrow": 0.5,         # 50% stereo width
    "normal": 1.0,         # Original stereo width
    "wide": 1.3,           # 30% wider
    "extra_wide": 1.6,     # 60% wider
    "mono_compat": 0.85,   # Safer for radio/TV broadcast
}


def _ensure_stereo(audio: np.ndarray) -> np.ndarray:
    """
    Ensure audio is in stereo format (2, samples).
    
    Args:
        audio: Input audio array, can be mono (samples,) or stereo (2, samples).
    
    Returns:
        Stereo audio array with shape (2, samples).
    
    Raises:
        ValueError: If audio has more than 2 channels or invalid shape.
    """
    if audio.ndim == 1:
        # Mono: duplicate to stereo
        return np.vstack([audio, audio])
    elif audio.ndim == 2:
        if audio.shape[0] == 2:
            return audio
        elif audio.shape[0] == 1:
            # Single channel row: duplicate
            return np.vstack([audio[0], audio[0]])
        elif audio.shape[1] == 2:
            # Samples x Channels format: transpose
            return audio.T
        else:
            raise ValueError(
                f"Invalid stereo shape: {audio.shape}. "
                "Expected (2, samples) or (samples, 2)."
            )
    else:
        raise ValueError(f"Audio must be 1D or 2D, got {audio.ndim}D.")


def _validate_audio(audio: np.ndarray, name: str = "audio") -> None:
    """
    Validate audio array for processing.
    
    Args:
        audio: Audio array to validate.
        name: Name for error messages.
    
    Raises:
        ValueError: If audio is empty or contains invalid values.
    """
    if audio.size == 0:
        raise ValueError(f"{name} array is empty.")
    if not np.isfinite(audio).all():
        raise ValueError(f"{name} contains NaN or Inf values.")


def ms_encode(audio: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """
    Encode stereo audio to Mid/Side representation.
    
    Converts left/right stereo channels to mid (sum) and side (difference)
    components using the standard M/S encoding formula:
      Mid = (Left + Right) * 0.5
      Side = (Left - Right) * 0.5
    
    Args:
        audio: Stereo audio array with shape (2, samples) or (samples, 2).
               Mono input (samples,) will be duplicated to stereo first.
    
    Returns:
        Tuple of (mid, side) arrays, each with shape (samples,).
        - mid: Contains center/mono content (vocals, bass, kick drum)
        - side: Contains stereo width content (reverbs, wide synths)
    
    Raises:
        ValueError: If audio is empty or has invalid shape.
    
    Example:
        >>> # Create a stereo signal
        >>> left = np.sin(2 * np.pi * 440 * np.arange(44100) / 44100)
        >>> right = np.sin(2 * np.pi * 445 * np.arange(44100) / 44100)
        >>> stereo = np.vstack([left, right])
        >>> mid, side = ms_encode(stereo)
        >>> print(f"Mid shape: {mid.shape}, Side shape: {side.shape}")
        Mid shape: (44100,), Side shape: (44100,)
    """
    _validate_audio(audio, "audio")
    stereo = _ensure_stereo(audio)
    
    left = stereo[0]
    right = stereo[1]
    
    mid = (left + right) * 0.5
    side = (left - right) * 0.5
    
    return mid, side


def ms_decode(mid: np.ndarray, side: np.ndarray) -> np.ndarray:
    """
    Decode Mid/Side representation back to stereo Left/Right.
    
    Converts mid and side components back to standard stereo using:
      Left = Mid + Side
      Right = Mid - Side
    
    Args:
        mid: Mid (center) component array with shape (samples,).
        side: Side (difference) component array with shape (samples,).
    
    Returns:
        Stereo audio array with shape (2, samples).
    
    Raises:
        ValueError: If mid and side have different lengths or are empty.
    
    Example:
        >>> mid = np.sin(2 * np.pi * 440 * np.arange(44100) / 44100)
        >>> side = np.sin(2 * np.pi * 880 * np.arange(44100) / 44100) * 0.3
        >>> stereo = ms_decode(mid, side)
        >>> print(f"Stereo shape: {stereo.shape}")
        Stereo shape: (2, 44100)
    """
    _validate_audio(mid, "mid")
    _validate_audio(side, "side")
    
    if mid.shape != side.shape:
        raise ValueError(
            f"Mid and side must have same shape. "
            f"Got mid={mid.shape}, side={side.shape}."
        )
    
    # Flatten if needed (ensure 1D)
    mid = mid.ravel()
    side = side.ravel()
    
    left = mid + side
    right = mid - side
    
    return np.vstack([left, right])


def apply_stereo_width(
    audio: np.ndarray,
    width: float = 1.0,
    preserve_center: bool = False
) -> np.ndarray:
    """
    Adjust stereo width by scaling the side signal.
    
    Width values:
      - 0.0: Full mono (side = 0)
      - 0.5: Narrow stereo (50% width)
      - 1.0: Original stereo (unchanged)
      - 1.5: Wide stereo (150% width)
      - 2.0: Extra wide (200% width, may clip!)
    
    Args:
        audio: Stereo audio array with shape (2, samples).
        width: Stereo width multiplier. 0.0=mono, 1.0=original, >1.0=wider.
               Negative values will invert the stereo image.
        preserve_center: If True, normalize mid to preserve center energy
                        when widening (prevents center from getting quieter).
    
    Returns:
        Width-adjusted stereo audio array with shape (2, samples).
    
    Raises:
        ValueError: If audio is empty or has invalid shape.
    
    Example:
        >>> stereo = np.random.randn(2, 44100) * 0.5
        >>> narrow = apply_stereo_width(stereo, width=0.5)
        >>> wide = apply_stereo_width(stereo, width=1.5)
        >>> mono = apply_stereo_width(stereo, width=0.0)
    """
    _validate_audio(audio, "audio")
    stereo = _ensure_stereo(audio)
    
    mid, side = ms_encode(stereo)
    
    # Scale side signal for width adjustment
    side_scaled = side * width
    
    if preserve_center and width > 1.0:
        # Compensate mid to maintain center energy
        # When widening, the overall level increases
        compensation = 1.0 / np.sqrt(0.5 + 0.5 * width * width)
        mid = mid * compensation
        side_scaled = side_scaled * compensation
    
    return ms_decode(mid, side_scaled)


def process_mid(
    audio: np.ndarray,
    processor: ProcessorFn
) -> np.ndarray:
    """
    Apply a processing function to only the mid (center) channel.
    
    Useful for:
      - Center EQ (boost/cut vocals, bass)
      - Center compression
      - Center saturation
    
    Args:
        audio: Stereo audio array with shape (2, samples).
        processor: Function that takes a 1D array and returns a 1D array
                   of the same length.
    
    Returns:
        Stereo audio with processed mid and original side.
    
    Raises:
        ValueError: If audio is empty or processor returns wrong shape.
    
    Example:
        >>> def boost_3db(x):
        ...     return x * 1.41  # ~+3dB
        >>> stereo = np.random.randn(2, 44100)
        >>> result = process_mid(stereo, boost_3db)
    """
    _validate_audio(audio, "audio")
    stereo = _ensure_stereo(audio)
    
    mid, side = ms_encode(stereo)
    
    # Process mid channel
    processed_mid = processor(mid)
    
    if processed_mid.shape != mid.shape:
        raise ValueError(
            f"Processor changed array shape from {mid.shape} "
            f"to {processed_mid.shape}. Must return same shape."
        )
    
    return ms_decode(processed_mid, side)


def process_side(
    audio: np.ndarray,
    processor: ProcessorFn
) -> np.ndarray:
    """
    Apply a processing function to only the side (stereo) channel.
    
    Useful for:
      - Adding reverb to sides only (keeps center dry)
      - Side EQ (boost high frequencies for "air")
      - Side compression (tame wild stereo content)
    
    Args:
        audio: Stereo audio array with shape (2, samples).
        processor: Function that takes a 1D array and returns a 1D array
                   of the same length.
    
    Returns:
        Stereo audio with original mid and processed side.
    
    Raises:
        ValueError: If audio is empty or processor returns wrong shape.
    
    Example:
        >>> def add_reverb_tail(x):
        ...     # Simplified reverb example
        ...     return x + np.convolve(x, np.exp(-np.arange(1000)/100), 'same') * 0.3
        >>> stereo = np.random.randn(2, 44100)
        >>> result = process_side(stereo, add_reverb_tail)
    """
    _validate_audio(audio, "audio")
    stereo = _ensure_stereo(audio)
    
    mid, side = ms_encode(stereo)
    
    # Process side channel
    processed_side = processor(side)
    
    if processed_side.shape != side.shape:
        raise ValueError(
            f"Processor changed array shape from {side.shape} "
            f"to {processed_side.shape}. Must return same shape."
        )
    
    return ms_decode(mid, processed_side)


def process_ms(
    audio: np.ndarray,
    mid_processor: Optional[ProcessorFn] = None,
    side_processor: Optional[ProcessorFn] = None
) -> np.ndarray:
    """
    Apply independent processing to mid and side channels.
    
    This is the most flexible M/S processing function, allowing
    different effects chains for center and stereo content.
    
    Args:
        audio: Stereo audio array with shape (2, samples).
        mid_processor: Optional function to process the mid channel.
                       If None, mid passes through unchanged.
        side_processor: Optional function to process the side channel.
                        If None, side passes through unchanged.
    
    Returns:
        Stereo audio with independently processed mid and side.
    
    Raises:
        ValueError: If audio is empty or processors return wrong shapes.
    
    Example:
        >>> def compress_mid(x):
        ...     threshold = 0.5
        ...     ratio = 4.0
        ...     over = np.abs(x) > threshold
        ...     x[over] = np.sign(x[over]) * (threshold + (np.abs(x[over]) - threshold) / ratio)
        ...     return x
        >>> def boost_highs_side(x):
        ...     # Simplified high shelf
        ...     return x * 1.2
        >>> stereo = np.random.randn(2, 44100)
        >>> result = process_ms(stereo, compress_mid, boost_highs_side)
    """
    _validate_audio(audio, "audio")
    stereo = _ensure_stereo(audio)
    
    mid, side = ms_encode(stereo)
    
    # Process mid if processor provided
    if mid_processor is not None:
        processed_mid = mid_processor(mid)
        if processed_mid.shape != mid.shape:
            raise ValueError(
                f"Mid processor changed shape from {mid.shape} "
                f"to {processed_mid.shape}."
            )
        mid = processed_mid
    
    # Process side if processor provided
    if side_processor is not None:
        processed_side = side_processor(side)
        if processed_side.shape != side.shape:
            raise ValueError(
                f"Side processor changed shape from {side.shape} "
                f"to {processed_side.shape}."
            )
        side = processed_side
    
    return ms_decode(mid, side)


def mono_bass(
    audio: np.ndarray,
    cutoff_hz: float = 150.0,
    sr: int = 44100,
    filter_order: int = 4,
    crossover_slope: str = "steep"
) -> np.ndarray:
    """
    Make bass frequencies mono for better club/PA system compatibility.
    
    This is essential for vinyl cutting and club sound systems where
    out-of-phase bass can cause needle skipping or speaker damage.
    
    The process:
      1. Split audio into M/S
      2. High-pass filter the side channel (remove bass from sides)
      3. Recombine (bass is now centered, highs retain stereo)
    
    Args:
        audio: Stereo audio array with shape (2, samples).
        cutoff_hz: Crossover frequency in Hz. Bass below this becomes mono.
                   Common values: 80-200 Hz.
        sr: Sample rate in Hz.
        filter_order: Butterworth filter order (2, 4, 6, 8).
                      Higher = steeper cutoff but more latency.
        crossover_slope: "gentle" (2nd order), "medium" (4th order),
                         "steep" (6th order), or "brick" (8th order).
    
    Returns:
        Stereo audio with mono bass and preserved stereo highs.
    
    Raises:
        ValueError: If cutoff is invalid or audio is empty.
    
    Example:
        >>> stereo = np.random.randn(2, 44100) * 0.5
        >>> club_ready = mono_bass(stereo, cutoff_hz=120.0, sr=44100)
    """
    _validate_audio(audio, "audio")
    stereo = _ensure_stereo(audio)
    
    if cutoff_hz <= 0 or cutoff_hz >= sr / 2:
        raise ValueError(
            f"Cutoff frequency must be between 0 and Nyquist ({sr/2} Hz). "
            f"Got {cutoff_hz} Hz."
        )
    
    # Map slope names to filter orders
    slope_orders = {
        "gentle": 2,
        "medium": 4,
        "steep": 6,
        "brick": 8
    }
    if crossover_slope in slope_orders:
        filter_order = slope_orders[crossover_slope]
    
    mid, side = ms_encode(stereo)
    
    # High-pass filter the side channel to remove bass
    nyquist = sr / 2.0
    normalized_cutoff = cutoff_hz / nyquist
    
    # Design Butterworth high-pass filter (second-order sections for stability)
    sos = butter(filter_order, normalized_cutoff, btype='high', output='sos')
    
    # Apply zero-phase filtering to avoid phase shift
    # Handle edge case of very short signals
    min_padlen = 3 * max(len(sos) * 2, 1)
    if len(side) > min_padlen:
        side_filtered = sosfiltfilt(sos, side)
    else:
        # For very short signals, use direct filtering
        from scipy.signal import sosfilt
        side_filtered = sosfilt(sos, side)
    
    return ms_decode(mid, side_filtered)


def ms_eq(
    audio: np.ndarray,
    mid_eq_fn: Optional[ProcessorFn] = None,
    side_eq_fn: Optional[ProcessorFn] = None
) -> np.ndarray:
    """
    Apply independent EQ curves to mid and side channels.
    
    This is a specialized wrapper around process_ms for equalization.
    Common use cases:
      - Boost mid presence (1-4kHz) for vocal clarity
      - Cut mid mudiness (200-400Hz) for cleaner mix
      - Boost side "air" (8-12kHz) for spaciousness
      - Cut side low-mids to reduce mud in reverb tails
    
    Args:
        audio: Stereo audio array with shape (2, samples).
        mid_eq_fn: EQ function for mid channel. Should take a 1D array
                   and return an equalized 1D array of same length.
        side_eq_fn: EQ function for side channel.
    
    Returns:
        Stereo audio with M/S equalization applied.
    
    Raises:
        ValueError: If audio is empty or EQ functions return wrong shapes.
    
    Example:
        >>> from scipy.signal import butter, sosfiltfilt
        >>> def mid_presence_boost(x, sr=44100):
        ...     # Boost 2-4kHz by ~3dB using bandpass
        ...     sos = butter(2, [2000/(sr/2), 4000/(sr/2)], btype='band', output='sos')
        ...     boosted = sosfiltfilt(sos, x) * 0.5
        ...     return x + boosted
        >>> stereo = np.random.randn(2, 44100)
        >>> result = ms_eq(stereo, mid_eq_fn=mid_presence_boost)
    """
    return process_ms(audio, mid_processor=mid_eq_fn, side_processor=side_eq_fn)


def dc_block(
    audio: np.ndarray,
    coefficient: float = 0.995
) -> np.ndarray:
    """
    Remove DC offset using a high-pass filter.
    
    DC offset is a common problem after heavy processing that can
    cause asymmetric waveforms and reduced headroom. This filter
    removes sub-1Hz content with minimal audible effect.
    
    The filter implements: y[n] = x[n] - x[n-1] + coefficient * y[n-1]
    
    Args:
        audio: Audio array, can be mono (samples,) or stereo (2, samples).
        coefficient: Filter coefficient, typically 0.99-0.999.
                     Higher = slower DC removal, less bass loss.
                     Lower = faster DC removal, may affect sub-bass.
    
    Returns:
        Audio with DC offset removed, same shape as input.
    
    Raises:
        ValueError: If audio is empty or coefficient is invalid.
    
    Example:
        >>> # Create signal with DC offset
        >>> signal = np.sin(2 * np.pi * 100 * np.arange(44100) / 44100) + 0.3
        >>> print(f"DC offset before: {np.mean(signal):.3f}")
        DC offset before: 0.300
        >>> cleaned = dc_block(signal)
        >>> print(f"DC offset after: {np.mean(cleaned):.3f}")
        DC offset after: 0.001
    """
    _validate_audio(audio, "audio")
    
    if not 0.9 <= coefficient <= 0.9999:
        raise ValueError(
            f"Coefficient should be between 0.9 and 0.9999. Got {coefficient}."
        )
    
    def _dc_block_1d(x: np.ndarray) -> np.ndarray:
        """Apply DC blocking filter to 1D signal."""
        y = np.zeros_like(x)
        if len(x) == 0:
            return y
        
        y[0] = x[0]
        for i in range(1, len(x)):
            y[i] = x[i] - x[i-1] + coefficient * y[i-1]
        return y
    
    # Handle mono vs stereo
    if audio.ndim == 1:
        return _dc_block_1d(audio)
    else:
        # Process each channel
        result = np.zeros_like(audio)
        for ch in range(audio.shape[0]):
            result[ch] = _dc_block_1d(audio[ch])
        return result


def dc_block_vectorized(
    audio: np.ndarray,
    cutoff_hz: float = 5.0,
    sr: int = 44100
) -> np.ndarray:
    """
    Remove DC offset using a vectorized high-pass filter (faster for long audio).
    
    Uses a first-order Butterworth high-pass filter at a very low frequency.
    This is more efficient for long audio files than the recursive approach.
    
    Args:
        audio: Audio array, can be mono (samples,) or stereo (2, samples).
        cutoff_hz: Cutoff frequency in Hz. Should be very low (1-10 Hz).
        sr: Sample rate in Hz.
    
    Returns:
        Audio with DC offset removed, same shape as input.
    
    Raises:
        ValueError: If audio is empty.
    
    Example:
        >>> signal = np.sin(2 * np.pi * 100 * np.arange(441000) / 44100) + 0.2
        >>> cleaned = dc_block_vectorized(signal, cutoff_hz=3.0, sr=44100)
    """
    _validate_audio(audio, "audio")
    
    nyquist = sr / 2.0
    normalized_cutoff = cutoff_hz / nyquist
    
    # Very low cutoff high-pass filter
    sos = butter(1, normalized_cutoff, btype='high', output='sos')
    
    if audio.ndim == 1:
        if len(audio) > 20:
            return sosfiltfilt(sos, audio)
        else:
            from scipy.signal import sosfilt
            return sosfilt(sos, audio)
    else:
        result = np.zeros_like(audio)
        for ch in range(audio.shape[0]):
            if len(audio[ch]) > 20:
                result[ch] = sosfiltfilt(sos, audio[ch])
            else:
                from scipy.signal import sosfilt
                result[ch] = sosfilt(sos, audio[ch])
        return result


def soft_clip(x: np.ndarray, threshold: float = 0.9) -> np.ndarray:
    """
    Apply soft clipping/saturation to prevent hard digital clipping.
    
    Uses a tanh-based soft clipper that smoothly limits peaks above
    the threshold while preserving dynamics below it.
    
    Args:
        x: Input signal.
        threshold: Level at which soft clipping begins (0.0 to 1.0).
    
    Returns:
        Soft-clipped signal.
    """
    # Scale to apply saturation curve
    scale = 1.0 / threshold
    return np.tanh(x * scale) / scale


def stereo_width_safe(
    audio: np.ndarray,
    width: float,
    limiter: bool = True,
    ceiling: float = 0.99
) -> np.ndarray:
    """
    Adjust stereo width with optional limiting to prevent clipping.
    
    When increasing stereo width, peak levels can exceed 0dBFS.
    This function provides safe width adjustment with automatic
    gain management.
    
    Args:
        audio: Stereo audio array with shape (2, samples).
        width: Stereo width multiplier. 0.0=mono, 1.0=original, >1.0=wider.
        limiter: If True, apply soft limiting to prevent clipping.
        ceiling: Maximum output level (0.0 to 1.0). Default 0.99 (-0.1dB).
    
    Returns:
        Width-adjusted and optionally limited stereo audio.
    
    Raises:
        ValueError: If audio is empty or ceiling is invalid.
    
    Example:
        >>> stereo = np.random.randn(2, 44100) * 0.7
        >>> # Safe extra-wide stereo
        >>> wide = stereo_width_safe(stereo, width=1.8, limiter=True)
        >>> print(f"Peak level: {np.max(np.abs(wide)):.3f}")
    """
    _validate_audio(audio, "audio")
    
    if not 0.0 < ceiling <= 1.0:
        raise ValueError(f"Ceiling must be between 0 and 1. Got {ceiling}.")
    
    # Apply stereo width
    result = apply_stereo_width(audio, width)
    
    if limiter:
        # Check if limiting is needed
        peak = np.max(np.abs(result))
        
        if peak > ceiling:
            # Apply soft clipping with makeup gain
            result = soft_clip(result, threshold=ceiling)
            
            # Ensure we don't exceed ceiling
            current_peak = np.max(np.abs(result))
            if current_peak > ceiling:
                result = result * (ceiling / current_peak)
    
    return result


def stereo_to_mono(audio: np.ndarray, method: str = "average") -> np.ndarray:
    """
    Convert stereo audio to mono using various methods.
    
    Args:
        audio: Stereo audio array with shape (2, samples).
        method: Conversion method:
                - "average": (L + R) / 2 (standard)
                - "left": Use left channel only
                - "right": Use right channel only
                - "mid": Extract mid component (same as average)
                - "side": Extract side component (stereo difference)
    
    Returns:
        Mono audio array with shape (samples,).
    
    Raises:
        ValueError: If audio is empty or method is unknown.
    
    Example:
        >>> stereo = np.random.randn(2, 44100)
        >>> mono = stereo_to_mono(stereo, method="average")
        >>> print(f"Mono shape: {mono.shape}")
        Mono shape: (44100,)
    """
    _validate_audio(audio, "audio")
    stereo = _ensure_stereo(audio)
    
    methods = {
        "average": lambda s: (s[0] + s[1]) * 0.5,
        "left": lambda s: s[0].copy(),
        "right": lambda s: s[1].copy(),
        "mid": lambda s: (s[0] + s[1]) * 0.5,
        "side": lambda s: (s[0] - s[1]) * 0.5,
    }
    
    if method not in methods:
        raise ValueError(
            f"Unknown method '{method}'. "
            f"Available: {list(methods.keys())}"
        )
    
    return methods[method](stereo)


def mono_to_stereo(
    audio: np.ndarray,
    method: str = "duplicate"
) -> np.ndarray:
    """
    Convert mono audio to stereo using various methods.
    
    Args:
        audio: Mono audio array with shape (samples,).
        method: Conversion method:
                - "duplicate": Copy mono to both channels
                - "haas": Apply Haas effect (slight delay on one channel)
                         for pseudo-stereo widening
    
    Returns:
        Stereo audio array with shape (2, samples).
    
    Example:
        >>> mono = np.sin(2 * np.pi * 440 * np.arange(44100) / 44100)
        >>> stereo = mono_to_stereo(mono, method="duplicate")
    """
    _validate_audio(audio, "audio")
    
    if audio.ndim != 1:
        if audio.ndim == 2 and audio.shape[0] == 2:
            return audio  # Already stereo
        audio = audio.ravel()
    
    if method == "duplicate":
        return np.vstack([audio, audio])
    elif method == "haas":
        # Apply ~20ms delay to right channel for pseudo-stereo
        delay_samples = int(0.02 * 44100)  # Assume 44.1kHz
        right = np.zeros_like(audio)
        right[delay_samples:] = audio[:-delay_samples] if delay_samples > 0 else audio
        return np.vstack([audio, right])
    else:
        raise ValueError(f"Unknown method '{method}'. Available: ['duplicate', 'haas']")


def get_stereo_correlation(audio: np.ndarray) -> float:
    """
    Calculate stereo correlation coefficient.
    
    Values:
      +1.0: Mono (channels are identical)
       0.0: Uncorrelated (independent channels)
      -1.0: Out of phase (channels are inverted copies)
    
    This is useful for:
      - Checking mono compatibility
      - Detecting phase issues
      - Measuring "stereo-ness" of a signal
    
    Args:
        audio: Stereo audio array with shape (2, samples).
    
    Returns:
        Correlation coefficient from -1.0 to +1.0.
    
    Example:
        >>> # Perfect mono
        >>> mono_signal = np.vstack([np.arange(100), np.arange(100)])
        >>> print(f"Mono correlation: {get_stereo_correlation(mono_signal):.2f}")
        Mono correlation: 1.00
        >>> # Out of phase
        >>> oop = np.vstack([np.arange(100), -np.arange(100)])
        >>> print(f"Out of phase: {get_stereo_correlation(oop):.2f}")
        Out of phase: -1.00
    """
    _validate_audio(audio, "audio")
    stereo = _ensure_stereo(audio)
    
    left = stereo[0]
    right = stereo[1]
    
    # Handle edge case of zero variance
    if np.std(left) == 0 or np.std(right) == 0:
        return 0.0
    
    correlation = np.corrcoef(left, right)[0, 1]
    return float(correlation) if np.isfinite(correlation) else 0.0


def get_stereo_balance(audio: np.ndarray) -> float:
    """
    Calculate stereo balance (panning position).
    
    Values:
      -1.0: Full left
       0.0: Center (balanced)
      +1.0: Full right
    
    Args:
        audio: Stereo audio array with shape (2, samples).
    
    Returns:
        Balance coefficient from -1.0 (left) to +1.0 (right).
    
    Example:
        >>> left_heavy = np.vstack([np.ones(100) * 0.8, np.ones(100) * 0.2])
        >>> print(f"Balance: {get_stereo_balance(left_heavy):.2f}")
    """
    _validate_audio(audio, "audio")
    stereo = _ensure_stereo(audio)
    
    left_rms = np.sqrt(np.mean(stereo[0] ** 2))
    right_rms = np.sqrt(np.mean(stereo[1] ** 2))
    
    total_rms = left_rms + right_rms
    if total_rms == 0:
        return 0.0
    
    # -1 = full left, +1 = full right
    balance = (right_rms - left_rms) / total_rms
    return float(balance)


def swap_channels(audio: np.ndarray) -> np.ndarray:
    """
    Swap left and right channels.
    
    Args:
        audio: Stereo audio array with shape (2, samples).
    
    Returns:
        Stereo audio with channels swapped.
    
    Example:
        >>> stereo = np.vstack([np.ones(100), np.zeros(100)])
        >>> swapped = swap_channels(stereo)
        >>> print(f"Left now: {swapped[0, 0]}, Right now: {swapped[1, 0]}")
        Left now: 0.0, Right now: 1.0
    """
    _validate_audio(audio, "audio")
    stereo = _ensure_stereo(audio)
    return np.vstack([stereo[1], stereo[0]])


def invert_phase(
    audio: np.ndarray,
    channel: str = "both"
) -> np.ndarray:
    """
    Invert phase (polarity) of audio channels.
    
    Args:
        audio: Stereo audio array with shape (2, samples).
        channel: Which channel(s) to invert:
                 - "left": Invert left channel only
                 - "right": Invert right channel only
                 - "both": Invert both channels
                 - "side": Invert side component only (swaps stereo image)
    
    Returns:
        Audio with inverted phase.
    
    Example:
        >>> stereo = np.random.randn(2, 44100)
        >>> inverted = invert_phase(stereo, channel="right")
    """
    _validate_audio(audio, "audio")
    stereo = _ensure_stereo(audio).copy()
    
    if channel == "left":
        stereo[0] = -stereo[0]
    elif channel == "right":
        stereo[1] = -stereo[1]
    elif channel == "both":
        stereo = -stereo
    elif channel == "side":
        mid, side = ms_encode(stereo)
        stereo = ms_decode(mid, -side)
    else:
        raise ValueError(
            f"Unknown channel '{channel}'. "
            "Available: ['left', 'right', 'both', 'side']"
        )
    
    return stereo


def create_ms_signal(
    audio: np.ndarray,
    sample_rate: int = 44100
) -> MSSignal:
    """
    Create an MSSignal container from stereo audio.
    
    Args:
        audio: Stereo audio array with shape (2, samples).
        sample_rate: Sample rate in Hz.
    
    Returns:
        MSSignal dataclass with mid, side, and metadata.
    
    Example:
        >>> stereo = np.random.randn(2, 44100)
        >>> ms = create_ms_signal(stereo, sample_rate=44100)
        >>> print(f"Mid peak: {np.max(np.abs(ms.mid)):.3f}")
    """
    _validate_audio(audio, "audio")
    stereo = _ensure_stereo(audio)
    
    mid, side = ms_encode(stereo)
    original_peak = float(np.max(np.abs(stereo)))
    
    return MSSignal(
        mid=mid,
        side=side,
        sample_rate=sample_rate,
        original_peak=original_peak
    )


def decode_ms_signal(ms_signal: MSSignal) -> np.ndarray:
    """
    Decode an MSSignal container back to stereo audio.
    
    Args:
        ms_signal: MSSignal dataclass with mid and side components.
    
    Returns:
        Stereo audio array with shape (2, samples).
    
    Example:
        >>> stereo = np.random.randn(2, 44100)
        >>> ms = create_ms_signal(stereo)
        >>> # Process mid/side...
        >>> ms.mid = ms.mid * 1.2  # Boost mid
        >>> reconstructed = decode_ms_signal(ms)
    """
    return ms_decode(ms_signal.mid, ms_signal.side)


# Convenience function for preset-based width adjustment
def apply_width_preset(
    audio: np.ndarray,
    preset: str = "normal",
    safe: bool = True
) -> np.ndarray:
    """
    Apply stereo width using a named preset.
    
    Available presets:
      - "mono": Full mono collapse (0.0)
      - "narrow": 50% stereo width (0.5)
      - "normal": Original stereo (1.0)
      - "wide": 30% wider (1.3)
      - "extra_wide": 60% wider (1.6)
      - "mono_compat": Safe for broadcast (0.85)
    
    Args:
        audio: Stereo audio array with shape (2, samples).
        preset: Name of width preset from STEREO_PRESETS.
        safe: If True, use stereo_width_safe with limiting.
    
    Returns:
        Width-adjusted stereo audio.
    
    Raises:
        ValueError: If preset is unknown.
    
    Example:
        >>> stereo = np.random.randn(2, 44100) * 0.5
        >>> wide = apply_width_preset(stereo, "wide")
        >>> mono_safe = apply_width_preset(stereo, "mono_compat", safe=True)
    """
    if preset not in STEREO_PRESETS:
        raise ValueError(
            f"Unknown preset '{preset}'. "
            f"Available: {list(STEREO_PRESETS.keys())}"
        )
    
    width = STEREO_PRESETS[preset]
    
    if safe:
        return stereo_width_safe(audio, width, limiter=True)
    else:
        return apply_stereo_width(audio, width)
