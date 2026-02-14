"""
[UNREFERENCED] Spatial Audio Module - Professional 3D Audio Processing and Immersive Sound.

NOTE (Sprint 11.7): This module is not imported by any other module in the pipeline.
Candidate for future integration or removal. Retained for reference designs.

Provides production-ready spatial audio tools:
- HRTF-based binaural rendering for accurate 3D positioning
- Stereo to binaural conversion for headphone listening
- Stereo upmixing to 5.1/7.1/7.1.4 surround formats
- Object-based panning with VBAP for Atmos-style workflows
- Dolby Atmos ADM export preparation
- First-Order Ambisonic (FOA) B-format encoding/decoding

Reference standards:
- ITU-R BS.775-3 (5.1 surround)
- ITU-R BS.2051 (Immersive audio)
- Dolby Atmos ADM Profile
- AES69-2020 (Spatial audio object coding)
"""

import os
import math
import numpy as np
from typing import Dict, List, Optional, Tuple, Union
from dataclasses import dataclass, field
from scipy.signal import butter, sosfiltfilt, firwin, lfilter
from scipy.io import wavfile

from multimodal_gen.utils import SAMPLE_RATE


# =============================================================================
# CONSTANTS
# =============================================================================

SPEED_OF_SOUND = 343.0  # m/s at 20°C
DEFAULT_HEAD_RADIUS = 0.0875  # 8.75 cm average adult head radius

# Speaker layouts (normalized coordinates: x=L/R, y=F/B, z=U/D)
SPEAKER_LAYOUTS = {
    "2.0": {
        "L": (-1.0, 1.0, 0.0),
        "R": (1.0, 1.0, 0.0),
    },
    "5.1": {
        "L": (-0.707, 0.707, 0.0),    # 45° left
        "R": (0.707, 0.707, 0.0),      # 45° right
        "C": (0.0, 1.0, 0.0),          # Center front
        "LFE": (0.0, 0.0, 0.0),        # Subwoofer (omnidirectional)
        "Ls": (-0.707, -0.707, 0.0),   # 135° left surround
        "Rs": (0.707, -0.707, 0.0),    # 135° right surround
    },
    "7.1": {
        "L": (-0.707, 0.707, 0.0),
        "R": (0.707, 0.707, 0.0),
        "C": (0.0, 1.0, 0.0),
        "LFE": (0.0, 0.0, 0.0),
        "Lss": (-1.0, 0.0, 0.0),       # Side surround left
        "Rss": (1.0, 0.0, 0.0),        # Side surround right
        "Lrs": (-0.707, -0.707, 0.0),  # Rear surround left
        "Rrs": (0.707, -0.707, 0.0),   # Rear surround right
    },
    "7.1.4": {
        "L": (-0.707, 0.707, 0.0),
        "R": (0.707, 0.707, 0.0),
        "C": (0.0, 1.0, 0.0),
        "LFE": (0.0, 0.0, 0.0),
        "Lss": (-1.0, 0.0, 0.0),
        "Rss": (1.0, 0.0, 0.0),
        "Lrs": (-0.707, -0.707, 0.0),
        "Rrs": (0.707, -0.707, 0.0),
        "Ltf": (-0.5, 0.5, 0.866),     # Left top front (60° elevation)
        "Rtf": (0.5, 0.5, 0.866),      # Right top front
        "Ltb": (-0.5, -0.5, 0.866),    # Left top back
        "Rtb": (0.5, -0.5, 0.866),     # Right top back
    },
}

# Channel ordering for export
CHANNEL_ORDER = {
    "5.1": ["L", "R", "C", "LFE", "Ls", "Rs"],
    "7.1": ["L", "R", "C", "LFE", "Lss", "Rss", "Lrs", "Rrs"],
    "7.1.4": ["L", "R", "C", "LFE", "Lss", "Rss", "Lrs", "Rrs", "Ltf", "Rtf", "Ltb", "Rtb"],
}


# =============================================================================
# PARAMETER DATACLASSES
# =============================================================================

@dataclass
class BinauralParams:
    """Parameters for binaural rendering.
    
    Attributes:
        azimuth: Horizontal angle in degrees (-180 to 180, 0 = front)
        elevation: Vertical angle in degrees (-90 to 90, 0 = horizon)
        distance: Distance from listener in meters (affects ITD/ILD/attenuation)
        room_size: Simulated room reflection amount (0.0 = anechoic, 1.0 = large room)
        head_radius_cm: Head radius for ITD calculation (default 8.75cm)
    """
    azimuth: float = 0.0
    elevation: float = 0.0
    distance: float = 1.0
    room_size: float = 0.0
    head_radius_cm: float = 8.75


@dataclass
class UpmixParams:
    """Parameters for stereo to immersive upmixing.
    
    Attributes:
        output_format: Target format ("5.1", "7.1", "7.1.4")
        center_extraction: Amount of phantom center to extract (0.0-1.0)
        surround_level_db: Gain adjustment for surround channels
        height_level_db: Gain adjustment for height channels (7.1.4 only)
        lfe_crossover_hz: Low-pass cutoff frequency for LFE channel
        decorrelation: Amount of decorrelation for surround channels (0.0-1.0)
    """
    output_format: str = "5.1"
    center_extraction: float = 0.5
    surround_level_db: float = -6.0
    height_level_db: float = -9.0
    lfe_crossover_hz: float = 120.0
    decorrelation: float = 0.3


@dataclass
class SpatialObject:
    """An audio object with 3D position for object-based panning.
    
    Attributes:
        audio: Mono audio signal (numpy array)
        name: Object identifier/name
        x: Left-Right position (-1.0 to 1.0)
        y: Front-Back position (-1.0 to 1.0)
        z: Bottom-Top position (-1.0 to 1.0)
        size: Object size/spread (0.0 = point source, 1.0 = fully diffuse)
    """
    audio: np.ndarray
    name: str = ""
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    size: float = 0.0


@dataclass
class AtmosMetadata:
    """Metadata for Dolby Atmos ADM-BWF export.
    
    Attributes:
        program_name: Name of the audio program
        objects: List of SpatialObject instances
        bed_format: Bed channel format ("5.1", "7.1", "7.1.4")
        start_time: Program start time in seconds
        duration: Program duration in seconds
    """
    program_name: str = ""
    objects: List[SpatialObject] = field(default_factory=list)
    bed_format: str = "7.1.4"
    start_time: float = 0.0
    duration: float = 0.0


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def _ensure_mono(audio: np.ndarray) -> np.ndarray:
    """Ensure audio is mono (1D array)."""
    if audio.ndim == 2:
        if audio.shape[0] == 2:
            return (audio[0] + audio[1]) * 0.5
        elif audio.shape[1] == 2:
            return (audio[:, 0] + audio[:, 1]) * 0.5
    return audio.ravel()


def _ensure_stereo(audio: np.ndarray) -> np.ndarray:
    """Ensure audio is stereo with shape (2, samples)."""
    if audio.ndim == 1:
        return np.vstack([audio, audio])
    elif audio.ndim == 2:
        if audio.shape[0] == 2:
            return audio
        elif audio.shape[1] == 2:
            return audio.T
    raise ValueError(f"Cannot convert shape {audio.shape} to stereo")


def _db_to_linear(db: float) -> float:
    """Convert decibels to linear gain."""
    return 10.0 ** (db / 20.0)


def _linear_to_db(linear: float) -> float:
    """Convert linear gain to decibels."""
    return 20.0 * math.log10(max(linear, 1e-10))


def _degrees_to_radians(degrees: float) -> float:
    """Convert degrees to radians."""
    return degrees * math.pi / 180.0


def _normalize_angle(degrees: float) -> float:
    """Normalize angle to -180 to 180 range."""
    while degrees > 180:
        degrees -= 360
    while degrees < -180:
        degrees += 360
    return degrees


def _fractional_delay(signal: np.ndarray, delay_samples: float) -> np.ndarray:
    """Apply fractional sample delay using linear interpolation."""
    if delay_samples <= 0:
        return signal.copy()
    
    int_delay = int(delay_samples)
    frac_delay = delay_samples - int_delay
    
    # Zero-pad for integer delay
    if int_delay > 0:
        delayed = np.zeros(len(signal) + int_delay)
        delayed[int_delay:int_delay + len(signal)] = signal
        delayed = delayed[:len(signal)]
    else:
        delayed = signal.copy()
    
    # Apply fractional delay with linear interpolation
    if frac_delay > 0 and len(delayed) > 1:
        output = np.zeros_like(delayed)
        output[1:] = delayed[:-1] * frac_delay + delayed[1:] * (1 - frac_delay)
        output[0] = delayed[0] * (1 - frac_delay)
        return output
    
    return delayed


# =============================================================================
# HRTF-BASED BINAURAL PROCESSOR
# =============================================================================

class HRTFProcessor:
    """Head-Related Transfer Function processor for binaural spatialization.
    
    Implements a simplified HRTF model using:
    - ITD (Interaural Time Difference) via Woodworth formula
    - ILD (Interaural Level Difference) based on head shadow
    - Spectral coloration for elevation cues
    
    For production use, consider loading measured HRTF datasets (CIPIC, MIT KEMAR).
    """
    
    def __init__(self, sample_rate: int = SAMPLE_RATE):
        """Initialize HRTF processor.
        
        Args:
            sample_rate: Audio sample rate in Hz
        """
        self.sample_rate = sample_rate
        self._init_filters()
    
    def _init_filters(self) -> None:
        """Initialize spectral shaping filters for HRTF simulation."""
        nyquist = self.sample_rate / 2.0
        
        # High-shelf filter for head shadow (ILD)
        # Head shadow primarily affects frequencies above 1.5kHz
        self._shadow_freq = min(1500.0 / nyquist, 0.95)
        
        # Pinna notch filters for elevation cues (6-9kHz region)
        self._pinna_low = min(6000.0 / nyquist, 0.95)
        self._pinna_high = min(9000.0 / nyquist, 0.95)
        
        # Front-back differentiation filter (2-4kHz boost for front)
        self._front_boost_freq = min(3000.0 / nyquist, 0.95)
    
    def _calculate_itd(
        self,
        azimuth: float,
        distance: float,
        head_radius: float
    ) -> float:
        """Calculate Interaural Time Difference using Woodworth formula.
        
        The Woodworth formula models ITD for a spherical head:
        ITD = (r/c) * (θ + sin(θ)) for |θ| <= π/2
        
        Args:
            azimuth: Horizontal angle in degrees
            distance: Distance from source in meters
            head_radius: Head radius in meters
            
        Returns:
            ITD in samples (positive = right ear leads)
        """
        theta = _degrees_to_radians(_normalize_angle(azimuth))
        
        # Clamp theta to valid range
        theta = max(-math.pi / 2, min(math.pi / 2, theta))
        
        # Woodworth formula
        itd_seconds = (head_radius / SPEED_OF_SOUND) * (abs(theta) + math.sin(abs(theta)))
        
        # Sign: positive azimuth (right) means left ear is delayed
        if azimuth > 0:
            itd_seconds = -itd_seconds
        
        # Distance attenuation of ITD (closer = larger ITD)
        if distance > 0:
            distance_factor = min(1.0, 1.0 / distance)
            itd_seconds *= (1.0 + 0.5 * (1.0 - distance_factor))
        
        return itd_seconds * self.sample_rate
    
    def _calculate_ild(self, azimuth: float, frequency: float) -> Tuple[float, float]:
        """Calculate Interaural Level Difference based on head shadow.
        
        Head shadow effect increases with frequency (more shadowing at HF).
        
        Args:
            azimuth: Horizontal angle in degrees
            frequency: Frequency for ILD calculation
            
        Returns:
            Tuple of (left_gain, right_gain) in linear scale
        """
        theta = _degrees_to_radians(_normalize_angle(azimuth))
        
        # Frequency-dependent shadowing (more at high frequencies)
        freq_factor = min(1.0, frequency / 4000.0)  # Maximal above 4kHz
        
        # Maximum ILD is about 20dB at extreme angles for high frequencies
        max_ild_db = 20.0 * freq_factor
        
        # ILD varies with sin(theta)
        ild_db = max_ild_db * math.sin(theta)
        
        # Convert to gains (positive ILD = right ear louder)
        if ild_db >= 0:
            left_gain = _db_to_linear(-ild_db)
            right_gain = 1.0
        else:
            left_gain = 1.0
            right_gain = _db_to_linear(ild_db)
        
        return left_gain, right_gain
    
    def _create_hrtf_filter(
        self,
        azimuth: float,
        elevation: float
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Create simplified HRTF filter pair for left and right ears.
        
        Args:
            azimuth: Horizontal angle in degrees
            elevation: Vertical angle in degrees
            
        Returns:
            Tuple of (left_filter, right_filter) FIR coefficients
        """
        filter_length = 128
        
        # Base impulse response
        left_filter = np.zeros(filter_length)
        right_filter = np.zeros(filter_length)
        left_filter[0] = 1.0
        right_filter[0] = 1.0
        
        # Apply basic ILD (broadband approximation)
        left_gain, right_gain = self._calculate_ild(azimuth, 2000.0)
        
        # Elevation affects high-frequency content (pinna cues)
        # Higher elevation = more high-frequency roll-off
        elev_rad = _degrees_to_radians(elevation)
        hf_rolloff = 1.0 - 0.3 * abs(math.sin(elev_rad))
        
        # Front/back differentiation
        # Sources behind have less high-frequency energy
        behind = abs(_normalize_angle(azimuth)) > 90
        if behind:
            hf_rolloff *= 0.7
        
        # Simple spectral shaping using a low-pass tendency for rear/elevated sources
        if hf_rolloff < 1.0:
            # Create simple low-pass shape
            for i in range(filter_length):
                if i > 0:
                    decay = math.exp(-i / (filter_length * hf_rolloff * 0.5))
                    left_filter[i] = decay * 0.1
                    right_filter[i] = decay * 0.1
        
        # Apply gains
        left_filter *= left_gain
        right_filter *= right_gain
        
        # Normalize
        left_filter /= np.sum(np.abs(left_filter)) + 1e-10
        right_filter /= np.sum(np.abs(right_filter)) + 1e-10
        
        return left_filter, right_filter
    
    def _apply_room_simulation(
        self,
        audio: np.ndarray,
        room_size: float
    ) -> np.ndarray:
        """Apply simple room simulation using early reflections.
        
        Args:
            audio: Input audio (stereo, shape 2 x samples)
            room_size: Room size factor (0.0 to 1.0)
            
        Returns:
            Audio with room reflections added
        """
        if room_size <= 0:
            return audio
        
        output = audio.copy()
        
        # Early reflection delays (in ms, converted to samples)
        reflection_delays_ms = [15, 25, 35, 50, 70]
        reflection_gains = [0.5, 0.35, 0.25, 0.18, 0.12]
        
        for delay_ms, gain in zip(reflection_delays_ms, reflection_gains):
            delay_samples = int(delay_ms * self.sample_rate / 1000)
            adjusted_gain = gain * room_size * 0.5
            
            if delay_samples < len(audio[0]):
                # Add reflection to both channels with slight decorrelation
                left_delay = delay_samples
                right_delay = delay_samples + int(3 * self.sample_rate / 1000)  # 3ms offset
                
                if left_delay < len(audio[0]):
                    output[0, left_delay:] += audio[0, :-left_delay] * adjusted_gain
                if right_delay < len(audio[1]):
                    output[1, right_delay:] += audio[1, :-right_delay] * adjusted_gain
        
        return output
    
    def process(self, audio: np.ndarray, params: BinauralParams) -> np.ndarray:
        """Render mono audio to binaural stereo.
        
        Args:
            audio: Mono input audio
            params: BinauralParams with position and room settings
            
        Returns:
            Stereo binaural audio with shape (2, samples)
        """
        mono = _ensure_mono(audio)
        head_radius = params.head_radius_cm / 100.0  # Convert to meters
        
        # Calculate ITD
        itd_samples = self._calculate_itd(
            params.azimuth,
            params.distance,
            head_radius
        )
        
        # Apply ITD (delay appropriate ear)
        if itd_samples >= 0:
            # Left ear delayed (source on right)
            left = _fractional_delay(mono, abs(itd_samples))
            right = mono.copy()
        else:
            # Right ear delayed (source on left)
            left = mono.copy()
            right = _fractional_delay(mono, abs(itd_samples))
        
        # Get HRTF filters
        left_filter, right_filter = self._create_hrtf_filter(
            params.azimuth,
            params.elevation
        )
        
        # Apply HRTF filters
        left = np.convolve(left, left_filter, mode='same')
        right = np.convolve(right, right_filter, mode='same')
        
        # Apply distance attenuation (inverse square law with minimum)
        if params.distance > 0:
            distance_atten = min(1.0, 1.0 / max(params.distance, 0.3))
            left *= distance_atten
            right *= distance_atten
        
        # Combine to stereo
        stereo = np.vstack([left, right])
        
        # Apply room simulation if requested
        if params.room_size > 0:
            stereo = self._apply_room_simulation(stereo, params.room_size)
        
        return stereo
    
    def get_analysis(self, audio: np.ndarray) -> Dict:
        """Analyze audio for spatial characteristics.
        
        Args:
            audio: Audio to analyze (mono or stereo)
            
        Returns:
            Dict with analysis results
        """
        if audio.ndim == 1:
            mono = audio
        else:
            stereo = _ensure_stereo(audio)
            mono = (stereo[0] + stereo[1]) * 0.5
        
        peak_db = _linear_to_db(np.max(np.abs(mono)))
        rms = np.sqrt(np.mean(mono ** 2))
        rms_db = _linear_to_db(rms)
        
        return {
            "peak_level_db": peak_db,
            "rms_level_db": rms_db,
            "duration_samples": len(mono),
            "duration_seconds": len(mono) / self.sample_rate,
        }


# =============================================================================
# STEREO TO BINAURAL CONVERTER
# =============================================================================

class StereoBinauralizer:
    """Convert stereo mix to binaural headphone format.
    
    Applies crossfeed and HRTF processing to simulate speaker listening
    on headphones, reducing the "in-head" localization typical of
    standard stereo headphone playback.
    """
    
    def __init__(
        self,
        crossfeed_amount: float = 0.3,
        sample_rate: int = SAMPLE_RATE
    ):
        """Initialize stereo binauralizer.
        
        Args:
            crossfeed_amount: Amount of crossfeed (0.0-1.0)
            sample_rate: Audio sample rate in Hz
        """
        self.crossfeed = max(0.0, min(1.0, crossfeed_amount))
        self.sample_rate = sample_rate
        self.hrtf = HRTFProcessor(sample_rate)
        
        # Crossfeed delay (simulates speaker distance difference)
        self._crossfeed_delay_ms = 0.3  # 300 microseconds typical
        self._crossfeed_delay_samples = int(
            self._crossfeed_delay_ms * sample_rate / 1000
        )
        
        # Low-pass filter for crossfeed (head acts as low-pass)
        self._init_crossfeed_filter()
    
    def _init_crossfeed_filter(self) -> None:
        """Initialize low-pass filter for crossfeed signal."""
        nyquist = self.sample_rate / 2.0
        cutoff = min(2000.0 / nyquist, 0.95)  # 2kHz cutoff
        
        self._crossfeed_sos = butter(2, cutoff, btype='low', output='sos')
    
    def process(self, stereo_audio: np.ndarray) -> np.ndarray:
        """Apply crossfeed and HRTF for natural headphone listening.
        
        Args:
            stereo_audio: Stereo input audio
            
        Returns:
            Binaural stereo audio with crossfeed
        """
        stereo = _ensure_stereo(stereo_audio)
        left, right = stereo[0], stereo[1]
        
        if self.crossfeed <= 0:
            return stereo
        
        # Apply low-pass filter to crossfeed signals
        left_xfeed = sosfiltfilt(self._crossfeed_sos, left)
        right_xfeed = sosfiltfilt(self._crossfeed_sos, right)
        
        # Apply delay to crossfeed signals
        if self._crossfeed_delay_samples > 0:
            left_xfeed = _fractional_delay(left_xfeed, self._crossfeed_delay_samples)
            right_xfeed = _fractional_delay(right_xfeed, self._crossfeed_delay_samples)
        
        # Mix crossfeed with opposite channels
        crossfeed_gain = self.crossfeed * 0.5
        direct_gain = 1.0 - crossfeed_gain * 0.3  # Slight reduction to maintain balance
        
        out_left = left * direct_gain + right_xfeed * crossfeed_gain
        out_right = right * direct_gain + left_xfeed * crossfeed_gain
        
        # Apply subtle HRTF for speaker simulation (±30° stereo image)
        left_hrtf = self.hrtf.process(
            left,
            BinauralParams(azimuth=-30, elevation=0, distance=2.0, room_size=0.1)
        )
        right_hrtf = self.hrtf.process(
            right,
            BinauralParams(azimuth=30, elevation=0, distance=2.0, room_size=0.1)
        )
        
        # Blend HRTF with crossfeed result
        hrtf_blend = self.crossfeed * 0.3
        out_left = out_left * (1 - hrtf_blend) + left_hrtf[0] * hrtf_blend
        out_right = out_right * (1 - hrtf_blend) + right_hrtf[1] * hrtf_blend
        
        return np.vstack([out_left, out_right])


# =============================================================================
# STEREO UPMIXER
# =============================================================================

class StereoUpmixer:
    """Upmix stereo to surround/immersive formats.
    
    Extracts phantom center, creates decorrelated surround channels,
    derives LFE content, and optionally creates height channels for
    Dolby Atmos-compatible 7.1.4 format.
    """
    
    def __init__(
        self,
        params: UpmixParams,
        sample_rate: int = SAMPLE_RATE
    ):
        """Initialize stereo upmixer.
        
        Args:
            params: UpmixParams with output format and settings
            sample_rate: Audio sample rate in Hz
        """
        self.params = params
        self.sample_rate = sample_rate
        self._init_filters()
    
    def _init_filters(self) -> None:
        """Initialize filters for upmixing."""
        nyquist = self.sample_rate / 2.0
        
        # LFE low-pass filter
        lfe_cutoff = min(self.params.lfe_crossover_hz / nyquist, 0.95)
        self._lfe_sos = butter(4, lfe_cutoff, btype='low', output='sos')
        
        # High-pass for removing LFE content from main channels
        self._main_hp_sos = butter(2, lfe_cutoff, btype='high', output='sos')
        
        # Decorrelation filter delays (prime number samples for incoherence)
        self._decorr_delays = [17, 23, 31, 41, 53]
        
        # Ambience extraction bandpass (1kHz-8kHz typical reverb content)
        bp_low = min(1000.0 / nyquist, 0.95)
        bp_high = min(8000.0 / nyquist, 0.95)
        if bp_low < bp_high:
            self._ambience_sos = butter(2, [bp_low, bp_high], btype='band', output='sos')
        else:
            self._ambience_sos = None
    
    def extract_center(
        self,
        left: np.ndarray,
        right: np.ndarray
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Extract phantom center channel using M/S processing.
        
        Args:
            left: Left channel audio
            right: Right channel audio
            
        Returns:
            Tuple of (center, left_minus_center, right_minus_center)
        """
        # M/S encode
        mid = (left + right) * 0.5
        side = (left - right) * 0.5
        
        # Center is the common (mid) content scaled by extraction amount
        center = mid * self.params.center_extraction
        
        # Reconstruct L/R with reduced center
        remaining_mid = mid * (1.0 - self.params.center_extraction * 0.7)
        new_left = remaining_mid + side
        new_right = remaining_mid - side
        
        return center, new_left, new_right
    
    def create_surrounds(
        self,
        left: np.ndarray,
        right: np.ndarray
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Create decorrelated surround channels.
        
        Uses complementary comb filtering for natural decorrelation
        that maintains spectral content while reducing correlation.
        
        Args:
            left: Left channel audio
            right: Right channel audio
            
        Returns:
            Tuple of (left_surround, right_surround)
        """
        surround_gain = _db_to_linear(self.params.surround_level_db)
        
        # Extract side (stereo difference) for surround base
        side = (left - right) * 0.5
        
        # Add some mid content for fullness
        mid = (left + right) * 0.5
        ls_base = side + mid * 0.3
        rs_base = -side + mid * 0.3
        
        # Apply decorrelation using complementary comb filters
        if self.params.decorrelation > 0:
            ls_decorr = np.zeros_like(ls_base)
            rs_decorr = np.zeros_like(rs_base)
            
            for i, delay in enumerate(self._decorr_delays):
                gain = self.params.decorrelation * (0.8 ** i)
                if delay < len(ls_base):
                    # Alternate polarities for comb filtering
                    polarity = 1 if i % 2 == 0 else -1
                    ls_decorr[delay:] += ls_base[:-delay] * gain * polarity
                    rs_decorr[delay:] += rs_base[:-delay] * gain * -polarity
            
            ls_out = ls_base + ls_decorr
            rs_out = rs_base + rs_decorr
        else:
            ls_out = ls_base
            rs_out = rs_base
        
        return ls_out * surround_gain, rs_out * surround_gain
    
    def create_heights(
        self,
        left: np.ndarray,
        right: np.ndarray
    ) -> Dict[str, np.ndarray]:
        """Create height channels from ambience extraction.
        
        Height channels enhance immersion by placing reverb and
        ambience content in the overhead speakers.
        
        Args:
            left: Left channel audio
            right: Right channel audio
            
        Returns:
            Dict with height channel names as keys
        """
        height_gain = _db_to_linear(self.params.height_level_db)
        
        # Extract ambient content (side information filtered)
        side = (left - right) * 0.5
        
        if self._ambience_sos is not None:
            ambience_left = sosfiltfilt(self._ambience_sos, left)
            ambience_right = sosfiltfilt(self._ambience_sos, right)
            ambience_side = sosfiltfilt(self._ambience_sos, side)
        else:
            ambience_left = left * 0.5
            ambience_right = right * 0.5
            ambience_side = side * 0.5
        
        # Create 4 height channels with decorrelation
        heights = {}
        
        # Top front (more direct content)
        heights["Ltf"] = (ambience_left * 0.6 + ambience_side * 0.4) * height_gain
        heights["Rtf"] = (ambience_right * 0.6 - ambience_side * 0.4) * height_gain
        
        # Top back (more ambient content)
        delay_samples = int(20 * self.sample_rate / 1000)  # 20ms delay for depth
        heights["Ltb"] = np.zeros_like(ambience_left)
        heights["Rtb"] = np.zeros_like(ambience_right)
        
        if delay_samples < len(ambience_left):
            heights["Ltb"][delay_samples:] = (
                (ambience_left[:-delay_samples] * 0.4 - ambience_side[:-delay_samples] * 0.6)
                * height_gain
            )
            heights["Rtb"][delay_samples:] = (
                (ambience_right[:-delay_samples] * 0.4 + ambience_side[:-delay_samples] * 0.6)
                * height_gain
            )
        
        return heights
    
    def create_lfe(
        self,
        left: np.ndarray,
        right: np.ndarray
    ) -> np.ndarray:
        """Create LFE (Low Frequency Effects) channel.
        
        Args:
            left: Left channel audio
            right: Right channel audio
            
        Returns:
            LFE channel (low-passed mono sum)
        """
        # Sum to mono
        mono = (left + right) * 0.5
        
        # Low-pass filter
        lfe = sosfiltfilt(self._lfe_sos, mono)
        
        # LFE is typically -10dB relative to main channels
        lfe *= _db_to_linear(-10.0)
        
        return lfe
    
    def process(self, stereo_audio: np.ndarray) -> Dict[str, np.ndarray]:
        """Upmix stereo to surround format.
        
        Args:
            stereo_audio: Stereo input audio
            
        Returns:
            Dict of channel names to audio arrays
        """
        stereo = _ensure_stereo(stereo_audio)
        left, right = stereo[0].copy(), stereo[1].copy()
        
        channels = {}
        
        # Extract center
        center, left_new, right_new = self.extract_center(left, right)
        channels["C"] = center
        
        # Main L/R (high-passed to remove LFE content)
        channels["L"] = sosfiltfilt(self._main_hp_sos, left_new)
        channels["R"] = sosfiltfilt(self._main_hp_sos, right_new)
        
        # LFE
        channels["LFE"] = self.create_lfe(left, right)
        
        # Surrounds
        ls, rs = self.create_surrounds(left, right)
        
        if self.params.output_format == "5.1":
            channels["Ls"] = ls
            channels["Rs"] = rs
            
        elif self.params.output_format in ["7.1", "7.1.4"]:
            # 7.1 has side and rear surrounds
            channels["Lss"] = ls * 0.7  # Side surrounds
            channels["Rss"] = rs * 0.7
            channels["Lrs"] = ls * 0.5  # Rear surrounds (more ambient)
            channels["Rrs"] = rs * 0.5
            
            if self.params.output_format == "7.1.4":
                # Add height channels
                heights = self.create_heights(left, right)
                channels.update(heights)
        
        return channels


# =============================================================================
# OBJECT-BASED PANNER
# =============================================================================

class ObjectPanner:
    """3D object-based panning using Vector Base Amplitude Panning (VBAP).
    
    Supports Atmos-style object rendering to speaker feeds for
    7.1.4 and other immersive formats.
    """
    
    def __init__(
        self,
        output_format: str = "7.1.4",
        sample_rate: int = SAMPLE_RATE
    ):
        """Initialize object panner.
        
        Args:
            output_format: Target speaker layout ("5.1", "7.1", "7.1.4")
            sample_rate: Audio sample rate in Hz
        """
        self.format = output_format
        self.sample_rate = sample_rate
        self.speaker_positions = SPEAKER_LAYOUTS.get(
            output_format,
            SPEAKER_LAYOUTS["7.1.4"]
        )
    
    def _vbap_gains(
        self,
        x: float,
        y: float,
        z: float,
        size: float = 0.0
    ) -> Dict[str, float]:
        """Calculate VBAP gains for each speaker.
        
        Uses distance-based amplitude panning with optional
        object size (spread) handling.
        
        Args:
            x: Left-Right position (-1 to 1)
            y: Front-Back position (-1 to 1)
            z: Bottom-Top position (-1 to 1)
            size: Object spread (0 = point, 1 = diffuse)
            
        Returns:
            Dict of speaker name to linear gain
        """
        # Clamp positions
        x = max(-1.0, min(1.0, x))
        y = max(-1.0, min(1.0, y))
        z = max(-1.0, min(1.0, z))
        
        obj_pos = np.array([x, y, z])
        gains = {}
        
        # Calculate inverse-distance gains for each speaker
        total_weight = 0.0
        for name, spk_pos in self.speaker_positions.items():
            if name == "LFE":
                continue  # LFE handled separately
            
            spk_vec = np.array(spk_pos)
            
            # Distance from object to speaker (in normalized space)
            dist = np.linalg.norm(obj_pos - spk_vec)
            
            # Inverse distance weighting with minimum
            weight = 1.0 / (dist + 0.1)
            
            # Apply spread: larger size = more even distribution
            if size > 0:
                weight = weight * (1 - size) + size
            
            gains[name] = weight
            total_weight += weight ** 2
        
        # Normalize to preserve energy
        if total_weight > 0:
            norm_factor = 1.0 / math.sqrt(total_weight)
            for name in gains:
                gains[name] *= norm_factor
        
        # LFE gets low-frequency content based on position
        gains["LFE"] = 0.3  # Constant LFE contribution for objects
        
        return gains
    
    def render_object(self, obj: SpatialObject) -> Dict[str, np.ndarray]:
        """Render single audio object to speaker feeds.
        
        Args:
            obj: SpatialObject with audio and position
            
        Returns:
            Dict of speaker name to audio array
        """
        mono = _ensure_mono(obj.audio)
        gains = self._vbap_gains(obj.x, obj.y, obj.z, obj.size)
        
        channels = {}
        for name, gain in gains.items():
            channels[name] = mono * gain
        
        return channels
    
    def render_scene(
        self,
        objects: List[SpatialObject]
    ) -> Dict[str, np.ndarray]:
        """Render multiple objects and mix to speaker feeds.
        
        Args:
            objects: List of SpatialObject instances
            
        Returns:
            Dict of speaker name to mixed audio array
        """
        if not objects:
            return {}
        
        # Find maximum length
        max_length = max(len(_ensure_mono(obj.audio)) for obj in objects)
        
        # Initialize output channels
        channels = {}
        for name in self.speaker_positions:
            channels[name] = np.zeros(max_length)
        
        # Render and sum each object
        for obj in objects:
            obj_channels = self.render_object(obj)
            for name, audio in obj_channels.items():
                if name in channels:
                    # Pad if needed
                    if len(audio) < max_length:
                        audio = np.pad(audio, (0, max_length - len(audio)))
                    channels[name] += audio
        
        return channels


# =============================================================================
# DOLBY ATMOS ADM EXPORTER
# =============================================================================

class AtmosExporter:
    """Prepare audio for Dolby Atmos authoring tools.
    
    Exports bed channels and objects as individual WAV files
    with ADM-compatible XML metadata for import into Dolby
    Atmos Production Suite, Pro Tools, or other ADM-aware DAWs.
    """
    
    def __init__(
        self,
        sample_rate: int = SAMPLE_RATE,
        bit_depth: int = 24
    ):
        """Initialize Atmos exporter.
        
        Args:
            sample_rate: Audio sample rate in Hz
            bit_depth: Bit depth for WAV export (16 or 24)
        """
        self.sample_rate = sample_rate
        self.bit_depth = bit_depth
    
    def _normalize_audio(self, audio: np.ndarray) -> np.ndarray:
        """Normalize audio to prevent clipping."""
        peak = np.max(np.abs(audio))
        if peak > 0.99:
            audio = audio * (0.99 / peak)
        return audio
    
    def _to_int_format(self, audio: np.ndarray) -> np.ndarray:
        """Convert float audio to integer format for WAV export."""
        audio = self._normalize_audio(audio)
        
        if self.bit_depth == 24:
            # Scale to 24-bit range
            return (audio * 8388607).astype(np.int32)
        else:
            # Scale to 16-bit range
            return (audio * 32767).astype(np.int16)
    
    def export_bed(
        self,
        channel_dict: Dict[str, np.ndarray],
        output_dir: str
    ) -> List[str]:
        """Export bed channels as individual WAV files.
        
        Args:
            channel_dict: Dict of channel names to audio arrays
            output_dir: Directory for output files
            
        Returns:
            List of created file paths
        """
        os.makedirs(output_dir, exist_ok=True)
        
        created_files = []
        
        for name, audio in channel_dict.items():
            filename = f"{name}.wav"
            filepath = os.path.join(output_dir, filename)
            
            # Convert to integer format
            int_audio = self._to_int_format(audio)
            
            # Write WAV file
            wavfile.write(filepath, self.sample_rate, int_audio)
            created_files.append(filepath)
        
        return created_files
    
    def export_objects(
        self,
        objects: List[SpatialObject],
        output_dir: str
    ) -> List[str]:
        """Export audio objects as mono WAV files.
        
        Args:
            objects: List of SpatialObject instances
            output_dir: Directory for output files
            
        Returns:
            List of created file paths
        """
        os.makedirs(output_dir, exist_ok=True)
        
        created_files = []
        
        for i, obj in enumerate(objects):
            name = obj.name or f"Object_{i+1:02d}"
            filename = f"{name}.wav"
            filepath = os.path.join(output_dir, filename)
            
            mono = _ensure_mono(obj.audio)
            int_audio = self._to_int_format(mono)
            
            wavfile.write(filepath, self.sample_rate, int_audio)
            created_files.append(filepath)
        
        return created_files
    
    def create_adm_xml(self, metadata: AtmosMetadata) -> str:
        """Create ADM XML metadata for Atmos renderer import.
        
        Args:
            metadata: AtmosMetadata with program info and objects
            
        Returns:
            ADM XML string
        """
        # ADM XML structure (simplified for compatibility)
        xml_lines = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<audioFormatExtended version="ITU-R_BS.2076-2">',
            f'  <audioProgramme audioProgrammeID="APR_1001" audioProgrammeName="{metadata.program_name}">',
            f'    <audioProgrammeLabel language="en">{metadata.program_name}</audioProgrammeLabel>',
        ]
        
        # Add bed content reference
        xml_lines.extend([
            '    <audioContentIDRef>ACO_1001</audioContentIDRef>',
        ])
        
        # Add object content references
        for i, obj in enumerate(metadata.objects):
            xml_lines.append(f'    <audioContentIDRef>ACO_{2001+i}</audioContentIDRef>')
        
        xml_lines.append('  </audioProgramme>')
        
        # Bed channel definition
        xml_lines.extend([
            f'  <audioContent audioContentID="ACO_1001" audioContentName="Bed_{metadata.bed_format}">',
            '    <audioObjectIDRef>AO_1001</audioObjectIDRef>',
            '  </audioContent>',
            f'  <audioObject audioObjectID="AO_1001" audioObjectName="Bed">',
            '    <audioPackFormatIDRef>AP_00010001</audioPackFormatIDRef>',
            '  </audioObject>',
        ])
        
        # Object definitions
        for i, obj in enumerate(metadata.objects):
            obj_id = 2001 + i
            obj_name = obj.name or f"Object_{i+1}"
            
            # Convert position to spherical for ADM
            azimuth = math.atan2(obj.x, obj.y) * 180 / math.pi
            distance = math.sqrt(obj.x**2 + obj.y**2 + obj.z**2)
            elevation = math.asin(obj.z / max(distance, 0.001)) * 180 / math.pi if distance > 0 else 0
            
            xml_lines.extend([
                f'  <audioContent audioContentID="ACO_{obj_id}" audioContentName="{obj_name}">',
                f'    <audioObjectIDRef>AO_{obj_id}</audioObjectIDRef>',
                '  </audioContent>',
                f'  <audioObject audioObjectID="AO_{obj_id}" audioObjectName="{obj_name}">',
                f'    <audioBlockFormat audioBlockFormatID="AB_{obj_id}_00000001">',
                f'      <position coordinate="azimuth">{azimuth:.1f}</position>',
                f'      <position coordinate="elevation">{elevation:.1f}</position>',
                f'      <position coordinate="distance">{min(distance, 1.0):.2f}</position>',
                '    </audioBlockFormat>',
                '  </audioObject>',
            ])
        
        xml_lines.append('</audioFormatExtended>')
        
        return '\n'.join(xml_lines)


# =============================================================================
# AMBISONIC ENCODER
# =============================================================================

class AmbisonicEncoder:
    """First-Order Ambisonic (FOA) B-format encoding and decoding.
    
    B-format uses four channels:
    - W: Omnidirectional pressure (mono)
    - X: Front-back figure-8 (cos azimuth)
    - Y: Left-right figure-8 (sin azimuth)
    - Z: Up-down figure-8 (sin elevation)
    """
    
    def __init__(self, sample_rate: int = SAMPLE_RATE):
        """Initialize Ambisonic encoder.
        
        Args:
            sample_rate: Audio sample rate in Hz
        """
        self.sample_rate = sample_rate
        self.hrtf = HRTFProcessor(sample_rate)
    
    def encode(
        self,
        audio: np.ndarray,
        azimuth: float,
        elevation: float
    ) -> Dict[str, np.ndarray]:
        """Encode mono source to B-format.
        
        Args:
            audio: Mono input audio
            azimuth: Horizontal angle in degrees
            elevation: Vertical angle in degrees
            
        Returns:
            Dict with W, X, Y, Z channels
        """
        mono = _ensure_mono(audio)
        
        # Convert to radians
        azi_rad = _degrees_to_radians(azimuth)
        ele_rad = _degrees_to_radians(elevation)
        
        # B-format encoding coefficients
        # W = signal (omnidirectional, scaled by 1/sqrt(2) for energy normalization)
        # X = signal * cos(azimuth) * cos(elevation)
        # Y = signal * sin(azimuth) * cos(elevation)
        # Z = signal * sin(elevation)
        
        w_coef = 1.0 / math.sqrt(2)
        x_coef = math.cos(azi_rad) * math.cos(ele_rad)
        y_coef = math.sin(azi_rad) * math.cos(ele_rad)
        z_coef = math.sin(ele_rad)
        
        return {
            "W": mono * w_coef,
            "X": mono * x_coef,
            "Y": mono * y_coef,
            "Z": mono * z_coef,
        }
    
    def encode_stereo(
        self,
        stereo_audio: np.ndarray,
        spread: float = 60.0
    ) -> Dict[str, np.ndarray]:
        """Encode stereo source to B-format with configurable spread.
        
        Args:
            stereo_audio: Stereo input audio
            spread: Stereo spread angle in degrees (default ±30°)
            
        Returns:
            Dict with W, X, Y, Z channels
        """
        stereo = _ensure_stereo(stereo_audio)
        left, right = stereo[0], stereo[1]
        
        # Encode left and right at spread angles
        left_bformat = self.encode(left, -spread/2, 0)
        right_bformat = self.encode(right, spread/2, 0)
        
        # Sum B-format channels
        return {
            "W": left_bformat["W"] + right_bformat["W"],
            "X": left_bformat["X"] + right_bformat["X"],
            "Y": left_bformat["Y"] + right_bformat["Y"],
            "Z": left_bformat["Z"] + right_bformat["Z"],
        }
    
    def decode_to_binaural(
        self,
        bformat: Dict[str, np.ndarray]
    ) -> np.ndarray:
        """Decode B-format to binaural headphones.
        
        Uses a simple virtual speaker array approach with HRTF.
        
        Args:
            bformat: Dict with W, X, Y, Z channels
            
        Returns:
            Stereo binaural audio
        """
        w = bformat.get("W", np.zeros(1))
        x = bformat.get("X", np.zeros_like(w))
        y = bformat.get("Y", np.zeros_like(w))
        z = bformat.get("Z", np.zeros_like(w))
        
        # Virtual speaker positions for binaural decoding
        # Using a simple quad arrangement plus height
        speakers = [
            (45, 0),    # Front left
            (-45, 0),   # Front right
            (135, 0),   # Rear left
            (-135, 0),  # Rear right
            (0, 45),    # Top front
            (0, -30),   # Bottom (floor reflection)
        ]
        
        output_left = np.zeros_like(w)
        output_right = np.zeros_like(w)
        
        for azi, ele in speakers:
            # Decode B-format to this speaker position
            azi_rad = _degrees_to_radians(azi)
            ele_rad = _degrees_to_radians(ele)
            
            # Decode formula (inverse of encode)
            signal = (
                w * math.sqrt(2) +
                x * math.cos(azi_rad) * math.cos(ele_rad) +
                y * math.sin(azi_rad) * math.cos(ele_rad) +
                z * math.sin(ele_rad)
            ) * 0.25  # Normalize for number of speakers
            
            # Apply HRTF for this speaker position
            binaural = self.hrtf.process(
                signal,
                BinauralParams(azimuth=azi, elevation=ele, distance=1.5)
            )
            
            output_left += binaural[0]
            output_right += binaural[1]
        
        return np.vstack([output_left, output_right])
    
    def decode_to_speakers(
        self,
        bformat: Dict[str, np.ndarray],
        layout: str = "5.1"
    ) -> Dict[str, np.ndarray]:
        """Decode B-format to speaker layout.
        
        Args:
            bformat: Dict with W, X, Y, Z channels
            layout: Target speaker layout ("5.1", "7.1")
            
        Returns:
            Dict of speaker channels
        """
        w = bformat.get("W", np.zeros(1))
        x = bformat.get("X", np.zeros_like(w))
        y = bformat.get("Y", np.zeros_like(w))
        z = bformat.get("Z", np.zeros_like(w))
        
        speaker_positions = SPEAKER_LAYOUTS.get(layout, SPEAKER_LAYOUTS["5.1"])
        channels = {}
        
        for name, (sx, sy, sz) in speaker_positions.items():
            if name == "LFE":
                # LFE from W channel, low-passed
                channels["LFE"] = w * 0.5
                continue
            
            # Convert speaker position to spherical
            distance = math.sqrt(sx**2 + sy**2 + sz**2)
            if distance > 0:
                azi_rad = math.atan2(sx, sy)
                ele_rad = math.asin(sz / distance)
            else:
                azi_rad = 0
                ele_rad = 0
            
            # Decode to this speaker
            signal = (
                w * math.sqrt(2) +
                x * math.cos(azi_rad) * math.cos(ele_rad) +
                y * math.sin(azi_rad) * math.cos(ele_rad) +
                z * math.sin(ele_rad)
            )
            
            channels[name] = signal
        
        return channels


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def binauralize(
    audio: np.ndarray,
    azimuth: float = 0,
    elevation: float = 0,
    distance: float = 1.0,
    sample_rate: int = SAMPLE_RATE
) -> np.ndarray:
    """Quick binaural positioning of mono source.
    
    Args:
        audio: Mono input audio
        azimuth: Horizontal angle (-180 to 180, 0 = front)
        elevation: Vertical angle (-90 to 90, 0 = horizon)
        distance: Distance in meters
        sample_rate: Audio sample rate
        
    Returns:
        Stereo binaural audio
    """
    hrtf = HRTFProcessor(sample_rate)
    params = BinauralParams(
        azimuth=azimuth,
        elevation=elevation,
        distance=distance
    )
    return hrtf.process(audio, params)


def crossfeed_stereo(
    audio: np.ndarray,
    amount: float = 0.3,
    sample_rate: int = SAMPLE_RATE
) -> np.ndarray:
    """Apply crossfeed for natural headphone listening.
    
    Args:
        audio: Stereo input audio
        amount: Crossfeed amount (0.0-1.0)
        sample_rate: Audio sample rate
        
    Returns:
        Stereo audio with crossfeed
    """
    binauralizer = StereoBinauralizer(crossfeed_amount=amount, sample_rate=sample_rate)
    return binauralizer.process(audio)


def upmix_to_surround(
    stereo_audio: np.ndarray,
    format: str = "5.1",
    sample_rate: int = SAMPLE_RATE
) -> Dict[str, np.ndarray]:
    """Upmix stereo to surround channel dict.
    
    Args:
        stereo_audio: Stereo input audio
        format: Output format ("5.1", "7.1", "7.1.4")
        sample_rate: Audio sample rate
        
    Returns:
        Dict of channel names to audio arrays
    """
    params = UpmixParams(output_format=format)
    upmixer = StereoUpmixer(params, sample_rate)
    return upmixer.process(stereo_audio)


def create_atmos_session(
    tracks: Dict[str, np.ndarray],
    output_dir: str,
    objects: Optional[List[SpatialObject]] = None,
    program_name: str = "Atmos Session",
    sample_rate: int = SAMPLE_RATE
) -> Dict[str, Union[List[str], str]]:
    """Create Atmos-ready session folder with beds and objects.
    
    Args:
        tracks: Dict of track names to stereo audio arrays
        output_dir: Output directory path
        objects: Optional list of SpatialObject instances
        program_name: Program name for ADM metadata
        sample_rate: Audio sample rate
        
    Returns:
        Dict with paths to created files and metadata
    """
    exporter = AtmosExporter(sample_rate=sample_rate)
    
    # Create subdirectories
    bed_dir = os.path.join(output_dir, "beds")
    obj_dir = os.path.join(output_dir, "objects")
    os.makedirs(bed_dir, exist_ok=True)
    os.makedirs(obj_dir, exist_ok=True)
    
    created_files = {
        "beds": [],
        "objects": [],
        "metadata": "",
    }
    
    # Process and export bed tracks
    for name, audio in tracks.items():
        # Upmix each stereo track to 7.1.4
        channels = upmix_to_surround(audio, format="7.1.4", sample_rate=sample_rate)
        
        # Create subfolder for this track
        track_dir = os.path.join(bed_dir, name)
        bed_files = exporter.export_bed(channels, track_dir)
        created_files["beds"].extend(bed_files)
    
    # Export objects if provided
    if objects:
        obj_files = exporter.export_objects(objects, obj_dir)
        created_files["objects"] = obj_files
    
    # Create ADM metadata
    metadata = AtmosMetadata(
        program_name=program_name,
        objects=objects or [],
        bed_format="7.1.4",
        duration=max(len(a) for a in tracks.values()) / sample_rate if tracks else 0
    )
    
    adm_xml = exporter.create_adm_xml(metadata)
    adm_path = os.path.join(output_dir, "metadata.xml")
    with open(adm_path, 'w') as f:
        f.write(adm_xml)
    created_files["metadata"] = adm_path
    
    return created_files


# =============================================================================
# PRESETS
# =============================================================================

SPATIAL_PRESETS = {
    "headphone_natural": {
        "crossfeed": 0.3,
        "room": 0.1,
        "description": "Natural headphone listening with subtle room simulation"
    },
    "speaker_simulation": {
        "crossfeed": 0.5,
        "room": 0.3,
        "description": "Simulate speaker listening on headphones"
    },
    "immersive_upmix": UpmixParams(
        output_format="7.1.4",
        decorrelation=0.4,
        center_extraction=0.6,
        surround_level_db=-4.0,
        height_level_db=-8.0
    ),
    "cinema_upmix": UpmixParams(
        output_format="5.1",
        surround_level_db=-3.0,
        center_extraction=0.7,
        decorrelation=0.25
    ),
    "music_surround": UpmixParams(
        output_format="5.1",
        surround_level_db=-6.0,
        center_extraction=0.4,
        decorrelation=0.35
    ),
    "atmos_music": UpmixParams(
        output_format="7.1.4",
        surround_level_db=-5.0,
        height_level_db=-9.0,
        center_extraction=0.5,
        decorrelation=0.4
    ),
}


def apply_spatial_preset(
    audio: np.ndarray,
    preset_name: str,
    sample_rate: int = SAMPLE_RATE
) -> Union[np.ndarray, Dict[str, np.ndarray]]:
    """Apply a spatial audio preset to audio.
    
    Args:
        audio: Input audio (mono or stereo)
        preset_name: Name of preset from SPATIAL_PRESETS
        sample_rate: Audio sample rate
        
    Returns:
        Processed audio (stereo for binaural, dict for surround)
        
    Raises:
        ValueError: If preset name is unknown
    """
    if preset_name not in SPATIAL_PRESETS:
        available = list(SPATIAL_PRESETS.keys())
        raise ValueError(f"Unknown preset '{preset_name}'. Available: {available}")
    
    preset = SPATIAL_PRESETS[preset_name]
    
    if isinstance(preset, UpmixParams):
        # Upmix preset
        return upmix_to_surround(audio, format=preset.output_format, sample_rate=sample_rate)
    elif isinstance(preset, dict):
        # Binaural preset
        crossfeed = preset.get("crossfeed", 0.3)
        return crossfeed_stereo(audio, amount=crossfeed, sample_rate=sample_rate)
    else:
        raise ValueError(f"Invalid preset configuration for '{preset_name}'")
