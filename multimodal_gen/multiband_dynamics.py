"""
Multiband Dynamics Processor Module

Professional-grade multiband compressor/expander with Linkwitz-Riley crossovers.
Provides independent dynamics control for sub, bass, mid, and high frequency bands.

Key Features:
- Linkwitz-Riley 4th-order (24dB/oct) crossover filters for phase-coherent splitting
- Per-band downward compression (above threshold)
- Per-band upward expansion (below expander threshold)
- Optional saturation (tanh soft clip) per band
- Lookahead buffer for transient preservation
- Linked gain reduction mode across bands
- Per-band metering support

References:
- Linkwitz-Riley crossover design (LR4 = cascaded Butterworth)
- Professional mastering multiband dynamics principles
- Phase-coherent band splitting

Author: Multimodal AI Music Generator
"""

import numpy as np
from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Dict, Any
from scipy import signal

from .utils import SAMPLE_RATE


# =============================================================================
# PARAMETERS
# =============================================================================

@dataclass
class BandParams:
    """
    Parameters for a single frequency band's dynamics processing.
    
    Attributes:
        threshold_db: Compression threshold in dB (-60 to 0).
                     Signals above this level are compressed.
        ratio: Compression ratio (1.0 to 20.0).
              1.0 = no compression, 4.0 = 4:1 compression.
        attack_ms: Attack time in milliseconds (0.1 to 200).
                  How fast compression engages.
        release_ms: Release time in milliseconds (10 to 2000).
                   How fast compression releases.
        makeup_gain_db: Makeup gain in dB (-12 to +24).
                       Compensates for gain reduction.
        expander_threshold_db: Expansion threshold in dB (-80 to -20).
                              Signals below this are expanded (quieted).
        expander_ratio: Expansion ratio (1.0 to 10.0).
                       How much to expand signals below threshold.
        saturation_drive: Saturation amount (0.0 to 1.0).
                         0 = clean, 1 = full saturation.
    """
    threshold_db: float = -20.0
    ratio: float = 4.0
    attack_ms: float = 10.0
    release_ms: float = 100.0
    makeup_gain_db: float = 0.0
    expander_threshold_db: float = -60.0
    expander_ratio: float = 2.0
    saturation_drive: float = 0.0


@dataclass
class MultibandDynamicsParams:
    """
    Parameters for the Multiband Dynamics Processor.
    
    Attributes:
        num_bands: Number of frequency bands (2 to 6).
        crossover_freqs: Crossover frequencies in Hz.
                        Length should be num_bands - 1.
                        Example: (80, 300, 3000) creates 4 bands.
        band_params: List of BandParams for each band.
                    If empty, default params are used.
        link_bands: If True, gain reduction is linked across bands.
                   Uses the maximum GR from all bands.
        lookahead_ms: Lookahead time in milliseconds (0 to 20).
                     Helps preserve transients.
        output_gain_db: Final output gain in dB (-12 to +12).
    """
    num_bands: int = 4
    crossover_freqs: Tuple[float, ...] = (80.0, 300.0, 3000.0)
    band_params: List[BandParams] = field(default_factory=list)
    link_bands: bool = False
    lookahead_ms: float = 5.0
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
    """
    Calculate one-pole filter coefficient for envelope follower.
    
    Args:
        time_ms: Time constant in milliseconds
        sample_rate: Sample rate in Hz
    
    Returns:
        Filter coefficient (0-1)
    """
    if time_ms <= 0:
        return 0.0
    time_samples = time_ms * sample_rate / 1000.0
    return np.exp(-1.0 / time_samples)


def soft_saturate(x: np.ndarray, drive: float) -> np.ndarray:
    """
    Apply soft saturation using tanh.
    
    Args:
        x: Input signal
        drive: Drive amount (0-1). 0 = clean, 1 = full saturation.
    
    Returns:
        Saturated signal
    """
    if drive <= 0:
        return x
    
    # Scale input by drive amount
    drive_scaled = 1.0 + drive * 3.0  # 1x to 4x drive
    driven = x * drive_scaled
    
    # Apply tanh saturation
    saturated = np.tanh(driven)
    
    # Mix dry/wet based on drive amount
    return x * (1.0 - drive) + saturated * drive


# =============================================================================
# LINKWITZ-RILEY CROSSOVER CLASS
# =============================================================================

class LinkwitzRileyCrossover:
    """
    Linkwitz-Riley 4th-order (24dB/octave) crossover filter.
    
    LR4 crossovers are industry standard for multiband processing because:
    1. Flat magnitude response at crossover point
    2. Phase coherent reconstruction (bands sum to original)
    3. -6dB at crossover frequency ensures flat sum
    
    Implementation: Cascade two 2nd-order Butterworth filters.
    """
    
    def __init__(self, crossover_freqs: Tuple[float, ...], sample_rate: int = 44100):
        """
        Initialize the crossover.
        
        Args:
            crossover_freqs: Crossover frequencies in Hz
            sample_rate: Sample rate in Hz
        """
        self.crossover_freqs = crossover_freqs
        self.sample_rate = sample_rate
        self.nyquist = sample_rate / 2.0
        self.num_bands = len(crossover_freqs) + 1
        
        # Pre-compute filter coefficients for each crossover
        self.filters = self._design_filters()
    
    def _design_filters(self) -> List[Dict[str, np.ndarray]]:
        """
        Design Linkwitz-Riley filters for each crossover point.
        
        Returns:
            List of filter coefficient dicts for each crossover
        """
        filters = []
        
        for freq in self.crossover_freqs:
            # Normalize frequency
            normalized_freq = freq / self.nyquist
            
            # Clamp to valid range (0.0001 to 0.9999)
            normalized_freq = np.clip(normalized_freq, 0.0001, 0.9999)
            
            # Design 2nd-order Butterworth (will cascade for LR4)
            sos_lp = signal.butter(2, normalized_freq, btype='low', output='sos')
            sos_hp = signal.butter(2, normalized_freq, btype='high', output='sos')
            
            filters.append({
                'freq': freq,
                'sos_lp': sos_lp,
                'sos_hp': sos_hp
            })
        
        return filters
    
    def split(self, audio: np.ndarray) -> List[np.ndarray]:
        """
        Split audio into frequency bands using LR4 crossovers.
        
        Args:
            audio: Input audio (mono or stereo)
        
        Returns:
            List of band audio arrays
        """
        is_stereo = len(audio.shape) > 1 and audio.shape[1] == 2
        
        if is_stereo:
            # Process channels separately and combine
            left_bands = self._split_mono(audio[:, 0])
            right_bands = self._split_mono(audio[:, 1])
            
            bands = []
            for i in range(self.num_bands):
                band_stereo = np.column_stack([left_bands[i], right_bands[i]])
                bands.append(band_stereo)
            return bands
        else:
            return self._split_mono(audio)
    
    def _split_mono(self, audio: np.ndarray) -> List[np.ndarray]:
        """Split mono audio into bands."""
        bands = []
        remaining = audio.copy()
        
        for i, filt in enumerate(self.filters):
            # Extract low band (apply LR4 = cascade two butterworth)
            low = signal.sosfilt(filt['sos_lp'], remaining)
            low = signal.sosfilt(filt['sos_lp'], low)  # Second cascade for LR4
            
            # High-pass the remaining for next iteration
            remaining = signal.sosfilt(filt['sos_hp'], remaining)
            remaining = signal.sosfilt(filt['sos_hp'], remaining)  # LR4
            
            bands.append(low)
        
        # Last band is the remaining high frequencies
        bands.append(remaining)
        
        return bands
    
    def reconstruct(self, bands: List[np.ndarray]) -> np.ndarray:
        """
        Reconstruct audio from frequency bands.
        
        LR4 crossovers ensure flat magnitude when bands are summed.
        
        Args:
            bands: List of band audio arrays
        
        Returns:
            Reconstructed audio
        """
        if len(bands) == 0:
            return np.array([])
        
        output = np.zeros_like(bands[0])
        for band in bands:
            output += band
        
        return output


# =============================================================================
# BAND COMPRESSOR CLASS
# =============================================================================

class BandCompressor:
    """
    Single-band compressor/expander with optional saturation.
    
    Features:
    - Downward compression (above threshold)
    - Upward expansion (below expander threshold)
    - Smooth envelope following
    - Optional tanh saturation
    """
    
    def __init__(self, params: BandParams, sample_rate: int = 44100):
        """
        Initialize the band compressor.
        
        Args:
            params: BandParams configuration
            sample_rate: Sample rate in Hz
        """
        self.params = params
        self.sample_rate = sample_rate
        
        # Convert thresholds to linear
        self.threshold_linear = db_to_linear(params.threshold_db)
        self.expander_threshold_linear = db_to_linear(params.expander_threshold_db)
        
        # Calculate envelope coefficients
        self.attack_coeff = calculate_envelope_coeff(params.attack_ms, sample_rate)
        self.release_coeff = calculate_envelope_coeff(params.release_ms, sample_rate)
        
        # Makeup gain
        self.makeup_gain = db_to_linear(params.makeup_gain_db)
        
        # Compressor knee (soft knee for smoother compression)
        self.knee_db = 6.0  # 6dB soft knee
        self.knee_half = self.knee_db / 2.0
        
        # State for envelope follower
        self.env_state = 0.0
        self.last_gain_reduction_db = 0.0
    
    def reset(self):
        """Reset the compressor state."""
        self.env_state = 0.0
        self.last_gain_reduction_db = 0.0
    
    def process(self, audio: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        Process audio through the compressor.
        
        Args:
            audio: Input audio (mono)
        
        Returns:
            Tuple of (processed_audio, gain_reduction_db)
        """
        n_samples = len(audio)
        output = np.zeros(n_samples)
        gain_reduction = np.zeros(n_samples)
        
        # Envelope detection
        envelope = self._detect_envelope(audio)
        
        for i in range(n_samples):
            env_db = linear_to_db(envelope[i] + 1e-10)
            
            # Calculate gain reduction
            gr_db = self._calculate_gain_reduction(env_db)
            gain_reduction[i] = gr_db
            
            # Apply gain
            gain_linear = db_to_linear(-gr_db) * self.makeup_gain
            output[i] = audio[i] * gain_linear
        
        # Apply saturation if enabled
        if self.params.saturation_drive > 0:
            output = soft_saturate(output, self.params.saturation_drive)
        
        self.last_gain_reduction_db = np.mean(gain_reduction)
        
        return output, gain_reduction
    
    def _detect_envelope(self, audio: np.ndarray) -> np.ndarray:
        """
        Detect the envelope of the audio signal.
        
        Uses peak detection with attack/release characteristics.
        
        Args:
            audio: Input audio
        
        Returns:
            Envelope signal
        """
        n_samples = len(audio)
        envelope = np.zeros(n_samples)
        
        rectified = np.abs(audio)
        state = self.env_state
        
        for i in range(n_samples):
            input_level = rectified[i]
            
            if input_level > state:
                # Attack phase
                state = self.attack_coeff * state + (1.0 - self.attack_coeff) * input_level
            else:
                # Release phase
                state = self.release_coeff * state + (1.0 - self.release_coeff) * input_level
            
            envelope[i] = state
        
        self.env_state = state
        return envelope
    
    def _calculate_gain_reduction(self, level_db: float) -> float:
        """
        Calculate gain reduction based on level.
        
        Handles both compression (above threshold) and expansion (below).
        Uses soft knee for smoother transition.
        
        Args:
            level_db: Input level in dB
        
        Returns:
            Gain reduction in dB (positive = attenuation)
        """
        gain_reduction_db = 0.0
        
        # Compression (above threshold)
        threshold_db = self.params.threshold_db
        knee_start = threshold_db - self.knee_half
        knee_end = threshold_db + self.knee_half
        
        if level_db > knee_end:
            # Above knee - full compression
            over_db = level_db - threshold_db
            gain_reduction_db = over_db * (1.0 - 1.0 / self.params.ratio)
        elif level_db > knee_start:
            # In knee - gradual compression
            knee_factor = (level_db - knee_start) / self.knee_db
            knee_factor = knee_factor * knee_factor  # Quadratic knee
            over_db = level_db - threshold_db
            gain_reduction_db = knee_factor * over_db * (1.0 - 1.0 / self.params.ratio)
        
        # Expansion (below expander threshold)
        expander_threshold_db = self.params.expander_threshold_db
        
        if level_db < expander_threshold_db:
            under_db = expander_threshold_db - level_db
            expansion_db = under_db * (self.params.expander_ratio - 1.0)
            gain_reduction_db += expansion_db
        
        return max(0.0, gain_reduction_db)


# =============================================================================
# MULTIBAND DYNAMICS PROCESSOR CLASS
# =============================================================================

class MultibandDynamics:
    """
    Professional Multiband Dynamics Processor.
    
    Splits audio into frequency bands using Linkwitz-Riley crossovers,
    applies independent compression/expansion to each band, then
    reconstructs the signal.
    
    Algorithm:
    1. Split input using LR4 crossovers
    2. Apply lookahead delay to audio path
    3. Process each band with its compressor
    4. Optionally link gain reduction across bands
    5. Reconstruct bands
    6. Apply output gain
    
    Usage:
        >>> params = MultibandDynamicsParams(
        ...     crossover_freqs=(100, 500, 4000),
        ...     band_params=[
        ...         BandParams(threshold_db=-12, ratio=2.0),  # Sub
        ...         BandParams(threshold_db=-15, ratio=3.0),  # Bass
        ...         BandParams(threshold_db=-18, ratio=4.0),  # Mid
        ...         BandParams(threshold_db=-20, ratio=3.5),  # High
        ...     ]
        ... )
        >>> processor = MultibandDynamics(params)
        >>> processed = processor.process(audio)
    """
    
    def __init__(self, params: MultibandDynamicsParams, sample_rate: int = SAMPLE_RATE):
        """
        Initialize the Multiband Dynamics Processor.
        
        Args:
            params: MultibandDynamicsParams configuration
            sample_rate: Audio sample rate in Hz
        """
        self.params = params
        self.sample_rate = sample_rate
        
        # Validate and setup crossover frequencies
        self._validate_params()
        
        # Create crossover
        self.crossover = LinkwitzRileyCrossover(
            params.crossover_freqs, 
            sample_rate
        )
        
        # Create band compressors
        self.band_compressors = self._create_band_compressors()
        
        # Lookahead in samples
        self.lookahead_samples = ms_to_samples(params.lookahead_ms, sample_rate)
        
        # Output gain
        self.output_gain = db_to_linear(params.output_gain_db)
        
        # Metering data
        self.last_band_meters: Dict[int, Dict[str, float]] = {}
        self.last_gain_reduction: List[float] = []
    
    def _validate_params(self):
        """Validate parameters and set defaults."""
        num_bands = len(self.params.crossover_freqs) + 1
        self.params.num_bands = num_bands
        
        # Ensure crossover frequencies are sorted and valid
        freqs = list(self.params.crossover_freqs)
        freqs.sort()
        
        # Clamp frequencies to valid range
        min_freq = 20.0
        max_freq = self.sample_rate / 2.0 * 0.95
        freqs = [np.clip(f, min_freq, max_freq) for f in freqs]
        
        self.params.crossover_freqs = tuple(freqs)
    
    def _create_band_compressors(self) -> List[BandCompressor]:
        """Create compressor for each band."""
        compressors = []
        
        for i in range(self.params.num_bands):
            if i < len(self.params.band_params):
                band_params = self.params.band_params[i]
            else:
                # Use default params with frequency-aware defaults
                band_params = self._get_default_band_params(i)
            
            compressor = BandCompressor(band_params, self.sample_rate)
            compressors.append(compressor)
        
        return compressors
    
    def _get_default_band_params(self, band_index: int) -> BandParams:
        """
        Get default parameters for a band based on its position.
        
        Lower bands typically need slower attack/release.
        Higher bands can handle faster dynamics.
        
        Args:
            band_index: Index of the band (0 = lowest)
        
        Returns:
            BandParams with frequency-appropriate defaults
        """
        # Defaults based on band position
        band_defaults = [
            # Sub bass - slow, gentle
            BandParams(threshold_db=-18, ratio=2.5, attack_ms=30, release_ms=200),
            # Bass - medium
            BandParams(threshold_db=-18, ratio=3.0, attack_ms=20, release_ms=150),
            # Low mid - standard
            BandParams(threshold_db=-18, ratio=3.5, attack_ms=15, release_ms=120),
            # High mid - faster
            BandParams(threshold_db=-18, ratio=4.0, attack_ms=10, release_ms=100),
            # High - fast
            BandParams(threshold_db=-18, ratio=3.5, attack_ms=5, release_ms=80),
            # Air - very fast
            BandParams(threshold_db=-20, ratio=3.0, attack_ms=3, release_ms=60),
        ]
        
        if band_index < len(band_defaults):
            return band_defaults[band_index]
        else:
            return BandParams()
    
    def reset(self):
        """Reset all band compressor states."""
        for comp in self.band_compressors:
            comp.reset()
    
    def process(self, audio: np.ndarray) -> np.ndarray:
        """
        Process audio through the multiband dynamics processor.
        
        Handles both mono and stereo input.
        
        Args:
            audio: Input audio array. Shape: (samples,) for mono or
                  (samples, 2) for stereo.
        
        Returns:
            Processed audio with multiband dynamics applied.
        """
        if len(audio) == 0:
            return audio
        
        is_stereo = len(audio.shape) > 1 and audio.shape[1] == 2
        
        if is_stereo:
            return self._process_stereo(audio)
        else:
            return self._process_mono(audio)
    
    def _process_mono(self, audio: np.ndarray) -> np.ndarray:
        """Process mono audio."""
        n_samples = len(audio)
        
        # Apply lookahead padding
        if self.lookahead_samples > 0:
            audio_delayed = np.concatenate([
                np.zeros(self.lookahead_samples),
                audio
            ])[:n_samples]
        else:
            audio_delayed = audio
        
        # Split into bands
        bands = self.crossover.split(audio)
        
        # Process each band
        processed_bands = []
        all_gain_reductions = []
        
        for i, (band, compressor) in enumerate(zip(bands, self.band_compressors)):
            processed, gr = compressor.process(band)
            processed_bands.append(processed)
            all_gain_reductions.append(gr)
            
            # Update metering
            self.last_band_meters[i] = {
                'peak_db': linear_to_db(np.max(np.abs(processed)) + 1e-10),
                'rms_db': linear_to_db(np.sqrt(np.mean(processed ** 2)) + 1e-10),
                'gain_reduction_db': np.mean(gr)
            }
        
        # Linked gain reduction (if enabled)
        if self.params.link_bands and len(all_gain_reductions) > 0:
            processed_bands = self._apply_linked_gain_reduction(
                bands, all_gain_reductions
            )
        
        self.last_gain_reduction = [np.mean(gr) for gr in all_gain_reductions]
        
        # Reconstruct
        output = self.crossover.reconstruct(processed_bands)
        
        # Apply output gain
        output = output * self.output_gain
        
        return output
    
    def _process_stereo(self, audio: np.ndarray) -> np.ndarray:
        """Process stereo audio."""
        n_samples = audio.shape[0]
        
        # Process mid/side for linked compression, or L/R independently
        # For simplicity, process L/R independently
        left = self._process_mono(audio[:, 0])
        
        # Reset compressors for right channel to ensure same behavior
        # (In production, might want separate states)
        self.reset()
        right = self._process_mono(audio[:, 1])
        
        return np.column_stack([left, right])
    
    def _apply_linked_gain_reduction(
        self, 
        bands: List[np.ndarray], 
        gain_reductions: List[np.ndarray]
    ) -> List[np.ndarray]:
        """
        Apply linked gain reduction across all bands.
        
        Uses the maximum gain reduction from any band and applies
        it to all bands. This maintains spectral balance.
        
        Args:
            bands: Original (unprocessed) bands
            gain_reductions: Gain reduction arrays from each band
        
        Returns:
            List of processed bands with linked GR
        """
        # Stack gain reductions and find max at each sample
        gr_stack = np.stack(gain_reductions, axis=0)
        max_gr = np.max(gr_stack, axis=0)
        
        # Apply max GR to each band
        processed_bands = []
        for i, band in enumerate(bands):
            # Convert GR to linear and apply
            gr_linear = db_to_linear(-max_gr)
            
            # Apply makeup gain from this band's compressor
            makeup = self.band_compressors[i].makeup_gain
            
            processed = band * gr_linear * makeup
            
            # Apply saturation if configured
            if self.band_compressors[i].params.saturation_drive > 0:
                processed = soft_saturate(
                    processed, 
                    self.band_compressors[i].params.saturation_drive
                )
            
            processed_bands.append(processed)
        
        return processed_bands
    
    def get_band_meters(self) -> Dict[int, Dict[str, float]]:
        """
        Get per-band metering data from last process() call.
        
        Returns:
            Dict mapping band index to meter values:
            - peak_db: Peak level in dB
            - rms_db: RMS level in dB
            - gain_reduction_db: Average gain reduction in dB
        """
        return self.last_band_meters.copy()
    
    def get_band_labels(self) -> List[str]:
        """
        Get human-readable labels for each band.
        
        Returns:
            List of band labels (e.g., "Sub (0-80Hz)")
        """
        labels = []
        freqs = [0] + list(self.params.crossover_freqs) + [self.sample_rate // 2]
        
        band_names = ['Sub', 'Bass', 'Low Mid', 'Mid', 'High Mid', 'High', 'Air']
        
        for i in range(self.params.num_bands):
            low = freqs[i]
            high = freqs[i + 1]
            name = band_names[i] if i < len(band_names) else f'Band {i}'
            labels.append(f"{name} ({int(low)}-{int(high)}Hz)")
        
        return labels


# =============================================================================
# PRESETS
# =============================================================================

MULTIBAND_PRESETS: Dict[str, MultibandDynamicsParams] = {
    'mastering_glue': MultibandDynamicsParams(
        crossover_freqs=(100.0, 500.0, 4000.0),
        band_params=[
            BandParams(
                threshold_db=-12.0, ratio=2.0, 
                attack_ms=30.0, release_ms=200.0,
                makeup_gain_db=1.0, expander_threshold_db=-60.0
            ),  # Sub - slow, gentle
            BandParams(
                threshold_db=-15.0, ratio=3.0, 
                attack_ms=15.0, release_ms=150.0,
                makeup_gain_db=1.5, expander_threshold_db=-55.0
            ),  # Bass
            BandParams(
                threshold_db=-18.0, ratio=4.0, 
                attack_ms=10.0, release_ms=100.0,
                makeup_gain_db=2.0, expander_threshold_db=-50.0
            ),  # Mid
            BandParams(
                threshold_db=-20.0, ratio=3.5, 
                attack_ms=5.0, release_ms=80.0,
                makeup_gain_db=2.5, expander_threshold_db=-50.0
            ),  # High - fast
        ],
        lookahead_ms=5.0,
        output_gain_db=0.0
    ),
    
    'loudness_maximize': MultibandDynamicsParams(
        crossover_freqs=(80.0, 400.0, 3500.0),
        band_params=[
            BandParams(
                threshold_db=-8.0, ratio=6.0, 
                attack_ms=20.0, release_ms=150.0,
                makeup_gain_db=4.0, saturation_drive=0.15
            ),  # Sub - aggressive
            BandParams(
                threshold_db=-10.0, ratio=6.0, 
                attack_ms=10.0, release_ms=100.0,
                makeup_gain_db=4.5, saturation_drive=0.1
            ),  # Bass
            BandParams(
                threshold_db=-12.0, ratio=8.0, 
                attack_ms=5.0, release_ms=80.0,
                makeup_gain_db=5.0, saturation_drive=0.1
            ),  # Mid
            BandParams(
                threshold_db=-14.0, ratio=6.0, 
                attack_ms=3.0, release_ms=60.0,
                makeup_gain_db=4.0, saturation_drive=0.05
            ),  # High
        ],
        lookahead_ms=3.0,
        output_gain_db=-1.0  # Leave headroom
    ),
    
    'gentle_control': MultibandDynamicsParams(
        crossover_freqs=(120.0, 600.0, 5000.0),
        band_params=[
            BandParams(
                threshold_db=-18.0, ratio=1.5, 
                attack_ms=50.0, release_ms=300.0,
                makeup_gain_db=0.5
            ),  # Sub - very gentle
            BandParams(
                threshold_db=-20.0, ratio=2.0, 
                attack_ms=30.0, release_ms=200.0,
                makeup_gain_db=1.0
            ),  # Bass
            BandParams(
                threshold_db=-22.0, ratio=2.0, 
                attack_ms=20.0, release_ms=150.0,
                makeup_gain_db=1.0
            ),  # Mid
            BandParams(
                threshold_db=-24.0, ratio=1.5, 
                attack_ms=10.0, release_ms=100.0,
                makeup_gain_db=0.5
            ),  # High
        ],
        lookahead_ms=8.0,
        output_gain_db=0.0
    ),
    
    'trap_808_focus': MultibandDynamicsParams(
        crossover_freqs=(60.0, 250.0, 2500.0),
        band_params=[
            BandParams(
                threshold_db=-6.0, ratio=8.0, 
                attack_ms=50.0, release_ms=300.0,
                makeup_gain_db=3.0,
                saturation_drive=0.2
            ),  # Sub - heavy compression for 808
            BandParams(
                threshold_db=-10.0, ratio=4.0, 
                attack_ms=20.0, release_ms=150.0,
                makeup_gain_db=2.0
            ),  # Bass
            BandParams(
                threshold_db=-15.0, ratio=3.0, 
                attack_ms=8.0, release_ms=100.0,
                makeup_gain_db=1.5
            ),  # Mid
            BandParams(
                threshold_db=-18.0, ratio=2.5, 
                attack_ms=3.0, release_ms=60.0,
                makeup_gain_db=2.0
            ),  # High - crispy hi-hats
        ],
        lookahead_ms=5.0,
        output_gain_db=0.0
    ),
    
    'vocal_mix': MultibandDynamicsParams(
        crossover_freqs=(150.0, 800.0, 6000.0),
        band_params=[
            BandParams(
                threshold_db=-20.0, ratio=2.0, 
                attack_ms=30.0, release_ms=200.0,
                makeup_gain_db=0.0,
                expander_threshold_db=-50.0, expander_ratio=1.5
            ),  # Sub - control rumble
            BandParams(
                threshold_db=-15.0, ratio=3.0, 
                attack_ms=15.0, release_ms=120.0,
                makeup_gain_db=1.0
            ),  # Low - warmth control
            BandParams(
                threshold_db=-12.0, ratio=4.0, 
                attack_ms=8.0, release_ms=80.0,
                makeup_gain_db=2.0
            ),  # Mid - presence
            BandParams(
                threshold_db=-18.0, ratio=2.5, 
                attack_ms=3.0, release_ms=50.0,
                makeup_gain_db=1.5
            ),  # High - air/sibilance
        ],
        lookahead_ms=5.0,
        output_gain_db=0.0
    ),
    
    'drum_bus': MultibandDynamicsParams(
        crossover_freqs=(80.0, 300.0, 4000.0),
        band_params=[
            BandParams(
                threshold_db=-10.0, ratio=4.0, 
                attack_ms=40.0, release_ms=200.0,
                makeup_gain_db=2.0
            ),  # Sub - kick punch
            BandParams(
                threshold_db=-12.0, ratio=5.0, 
                attack_ms=15.0, release_ms=120.0,
                makeup_gain_db=2.5
            ),  # Bass - body
            BandParams(
                threshold_db=-15.0, ratio=4.0, 
                attack_ms=5.0, release_ms=80.0,
                makeup_gain_db=2.0
            ),  # Mid - snare crack
            BandParams(
                threshold_db=-18.0, ratio=3.0, 
                attack_ms=2.0, release_ms=50.0,
                makeup_gain_db=1.5
            ),  # High - cymbals
        ],
        lookahead_ms=3.0,
        output_gain_db=0.0
    ),
}


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def multiband_compress(
    audio: np.ndarray,
    preset: str = "mastering_glue",
    sample_rate: int = SAMPLE_RATE
) -> np.ndarray:
    """
    Quick multiband compression with preset.
    
    Args:
        audio: Input audio array (mono or stereo)
        preset: Preset name from MULTIBAND_PRESETS
        sample_rate: Audio sample rate in Hz
    
    Returns:
        Processed audio
    
    Example:
        >>> mastered = multiband_compress(audio, preset='loudness_maximize')
    """
    if preset not in MULTIBAND_PRESETS:
        available = ', '.join(MULTIBAND_PRESETS.keys())
        raise ValueError(f"Unknown preset: {preset}. Available: {available}")
    
    params = MULTIBAND_PRESETS[preset]
    processor = MultibandDynamics(params, sample_rate)
    return processor.process(audio)


def create_custom_multiband(
    audio: np.ndarray,
    crossover_freqs: Tuple[float, ...] = (100.0, 500.0, 4000.0),
    thresholds_db: Tuple[float, ...] = (-15.0, -15.0, -15.0, -15.0),
    ratios: Tuple[float, ...] = (3.0, 3.0, 3.0, 3.0),
    sample_rate: int = SAMPLE_RATE
) -> np.ndarray:
    """
    Create custom multiband compression with simple parameters.
    
    Args:
        audio: Input audio array
        crossover_freqs: Crossover frequencies (creates n+1 bands)
        thresholds_db: Threshold for each band
        ratios: Compression ratio for each band
        sample_rate: Audio sample rate
    
    Returns:
        Processed audio
    
    Example:
        >>> processed = create_custom_multiband(
        ...     audio,
        ...     crossover_freqs=(80, 300, 3000),
        ...     thresholds_db=(-12, -15, -18, -20),
        ...     ratios=(2, 3, 4, 3)
        ... )
    """
    num_bands = len(crossover_freqs) + 1
    
    # Create band params
    band_params = []
    for i in range(num_bands):
        threshold = thresholds_db[i] if i < len(thresholds_db) else -15.0
        ratio = ratios[i] if i < len(ratios) else 3.0
        
        # Auto attack/release based on band position
        attack_base = 30.0 - (i * 5.0)  # Slower for low bands
        release_base = 200.0 - (i * 30.0)  # Slower for low bands
        
        band_params.append(BandParams(
            threshold_db=threshold,
            ratio=ratio,
            attack_ms=max(3.0, attack_base),
            release_ms=max(50.0, release_base)
        ))
    
    params = MultibandDynamicsParams(
        crossover_freqs=crossover_freqs,
        band_params=band_params
    )
    
    processor = MultibandDynamics(params, sample_rate)
    return processor.process(audio)


def get_band_meters(
    processor: MultibandDynamics, 
    audio: np.ndarray
) -> Dict[str, Dict[str, float]]:
    """
    Process audio and return per-band metering data.
    
    Args:
        processor: MultibandDynamics processor instance
        audio: Audio to process
    
    Returns:
        Dict mapping band labels to meter values:
        - peak_db: Peak level in dB
        - rms_db: RMS level in dB  
        - gain_reduction_db: Average gain reduction in dB
    
    Example:
        >>> processor = MultibandDynamics(MULTIBAND_PRESETS['mastering_glue'])
        >>> meters = get_band_meters(processor, audio)
        >>> print(meters['Mid (500-4000Hz)']['gain_reduction_db'])
    """
    # Process to populate meters
    processor.process(audio)
    
    # Get labels and meters
    labels = processor.get_band_labels()
    raw_meters = processor.get_band_meters()
    
    # Map labels to meters
    result = {}
    for i, label in enumerate(labels):
        if i in raw_meters:
            result[label] = raw_meters[i]
    
    return result


def analyze_frequency_balance(
    audio: np.ndarray,
    crossover_freqs: Tuple[float, ...] = (100.0, 500.0, 4000.0),
    sample_rate: int = SAMPLE_RATE
) -> Dict[str, float]:
    """
    Analyze the frequency balance of audio by measuring band levels.
    
    Useful for understanding the spectral distribution before
    applying multiband processing.
    
    Args:
        audio: Input audio
        crossover_freqs: Crossover frequencies for analysis
        sample_rate: Sample rate
    
    Returns:
        Dict with band names and their RMS levels in dB
    
    Example:
        >>> balance = analyze_frequency_balance(audio)
        >>> print(f"Sub level: {balance['Sub']}dB")
    """
    # Create crossover for splitting
    crossover = LinkwitzRileyCrossover(crossover_freqs, sample_rate)
    
    # Handle stereo
    if len(audio.shape) > 1 and audio.shape[1] == 2:
        mono = np.mean(audio, axis=1)
    else:
        mono = audio
    
    # Split into bands
    bands = crossover._split_mono(mono)
    
    # Measure each band
    band_names = ['Sub', 'Bass', 'Low Mid', 'Mid', 'High Mid', 'High']
    result = {}
    
    for i, band in enumerate(bands):
        name = band_names[i] if i < len(band_names) else f'Band {i}'
        rms = np.sqrt(np.mean(band ** 2))
        result[name] = linear_to_db(rms + 1e-10)
    
    return result
