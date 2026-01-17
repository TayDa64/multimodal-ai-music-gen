"""
Stem Separation Module

Professional-grade stem separation supporting multiple backends:
- Demucs (Facebook's hybrid transformer model) - highest quality
- Spleeter (Deezer's U-Net model) - fast and lightweight
- Basic (frequency-based fallback) - no ML dependencies required

Provides unified interface for separating audio into stems (vocals, drums, bass, other)
with style transfer and remix capabilities.

Key Features:
- Multiple backend support with automatic fallback
- Lazy model loading for memory efficiency
- Batch processing for multiple files
- Style transfer tools (extract/replace drums, create instrumentals)
- Device auto-detection (CPU/CUDA/MPS)

References:
- Demucs: https://github.com/facebookresearch/demucs
- Spleeter: https://github.com/deezer/spleeter

Author: Multimodal AI Music Generator
"""

import numpy as np
import os
import tempfile
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Union
import warnings

from scipy import signal
from scipy.io import wavfile

from .utils import SAMPLE_RATE


# =============================================================================
# ENUMS & CONSTANTS
# =============================================================================

class SeparationBackend(Enum):
    """Available stem separation backends."""
    DEMUCS = "demucs"       # Facebook's hybrid transformer (best quality)
    SPLEETER = "spleeter"   # Deezer's U-Net (fast)
    BASIC = "basic"         # Simple frequency-based (no ML)
    AUTO = "auto"           # Automatically select best available


# Standard stem names
STANDARD_STEMS = ["vocals", "drums", "bass", "other"]
EXTENDED_STEMS_6 = ["vocals", "drums", "bass", "other", "piano", "guitar"]

# Demucs model options
DEMUCS_MODELS = {
    "htdemucs": "Hybrid Transformer Demucs (default, 4 stems)",
    "htdemucs_ft": "Fine-tuned version (slightly better vocals)",
    "htdemucs_6s": "6-stem model (adds piano, guitar)",
    "mdx_extra": "MDX-Net (alternative architecture)",
}


# =============================================================================
# PARAMETERS
# =============================================================================

@dataclass
class SeparationParams:
    """
    Parameters for stem separation.
    
    Attributes:
        backend: Which separation backend to use.
        model: Model name for the selected backend.
        stems: Which stems to extract.
        shifts: Number of random shifts for averaging (Demucs).
                Higher values improve quality but slow processing.
        overlap: Overlap ratio between chunks (0.0-0.5).
        segment: Segment length in seconds (None for auto).
        device: Processing device ("cpu", "cuda", "mps", "auto").
        jobs: Number of parallel jobs for batch processing.
    """
    backend: SeparationBackend = SeparationBackend.AUTO
    model: str = "htdemucs"
    stems: List[str] = field(default_factory=lambda: STANDARD_STEMS.copy())
    shifts: int = 1
    overlap: float = 0.25
    segment: Optional[float] = None
    device: str = "auto"
    jobs: int = 1


# =============================================================================
# ABSTRACT BASE CLASS
# =============================================================================

class StemSeparator(ABC):
    """
    Abstract base class for stem separation backends.
    
    All backends must implement:
    - separate(): Perform stem separation
    - is_available(): Check if backend is usable
    """
    
    @abstractmethod
    def separate(
        self, 
        audio: np.ndarray, 
        sample_rate: int = SAMPLE_RATE
    ) -> Dict[str, np.ndarray]:
        """
        Separate audio into stems.
        
        Args:
            audio: Input audio array. Shape: (samples,) for mono or
                  (samples, 2) for stereo.
            sample_rate: Audio sample rate in Hz.
        
        Returns:
            Dictionary mapping stem names to audio arrays:
            {"vocals": ndarray, "drums": ndarray, "bass": ndarray, "other": ndarray}
            Each stem has the same shape as input.
        """
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """
        Check if this backend is installed and usable.
        
        Returns:
            True if all dependencies are satisfied.
        """
        pass
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Return the backend name for logging."""
        pass


# =============================================================================
# DEMUCS BACKEND
# =============================================================================

class DemucsBackend(StemSeparator):
    """
    Facebook's Demucs hybrid transformer model.
    
    Demucs uses a hybrid architecture combining:
    - Transformer for long-range dependencies
    - U-Net for local features
    
    Models:
    - htdemucs: Default hybrid transformer (4 stems)
    - htdemucs_ft: Fine-tuned for better vocals
    - htdemucs_6s: 6 stems (adds piano, guitar)
    - mdx_extra: MDX-Net architecture
    
    Requirements:
        pip install demucs
        For GPU: pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
    """
    
    def __init__(
        self, 
        model_name: str = "htdemucs",
        device: str = "auto",
        shifts: int = 1,
        overlap: float = 0.25,
        segment: Optional[float] = None
    ):
        """
        Initialize Demucs backend.
        
        Args:
            model_name: Demucs model to use.
            device: Processing device ("cpu", "cuda", "mps", "auto").
            shifts: Random shifts for averaging (1-10).
            overlap: Overlap between chunks (0.0-0.5).
            segment: Segment length in seconds.
        """
        self.model_name = model_name
        self._device = device
        self.shifts = max(1, min(10, shifts))
        self.overlap = max(0.0, min(0.5, overlap))
        self.segment = segment
        self._model = None
        self._apply_model = None
    
    @property
    def name(self) -> str:
        return f"demucs ({self.model_name})"
    
    def is_available(self) -> bool:
        """Check if Demucs is installed."""
        try:
            import demucs
            import torch
            return True
        except ImportError:
            return False
    
    def _get_device(self) -> "torch.device":
        """Determine the best available device."""
        import torch
        
        if self._device == "auto":
            if torch.cuda.is_available():
                return torch.device("cuda")
            elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                return torch.device("mps")
            else:
                return torch.device("cpu")
        else:
            return torch.device(self._device)
    
    def _load_model(self):
        """Lazy load the model on first use."""
        if self._model is not None:
            return
        
        from demucs.pretrained import get_model
        from demucs.apply import apply_model
        
        self._model = get_model(self.model_name)
        self._model.to(self._get_device())
        self._model.eval()
        self._apply_model = apply_model
    
    def separate(
        self, 
        audio: np.ndarray, 
        sample_rate: int = SAMPLE_RATE
    ) -> Dict[str, np.ndarray]:
        """
        Run Demucs stem separation.
        
        Handles resampling if input sample rate differs from Demucs's
        expected rate (44100 Hz).
        
        Args:
            audio: Input audio (mono or stereo).
            sample_rate: Input sample rate.
        
        Returns:
            Dictionary of separated stems.
        """
        import torch
        
        self._load_model()
        
        # Ensure stereo (Demucs expects stereo)
        if len(audio.shape) == 1:
            audio = np.column_stack([audio, audio])
        
        # Resample if necessary (Demucs expects 44100)
        if sample_rate != self._model.samplerate:
            audio = self._resample(audio, sample_rate, self._model.samplerate)
            original_sr = sample_rate
            sample_rate = self._model.samplerate
        else:
            original_sr = None
        
        # Convert to torch tensor: (batch, channels, samples)
        audio_tensor = torch.tensor(
            audio.T[np.newaxis, :, :],  # (1, 2, samples)
            dtype=torch.float32,
            device=self._get_device()
        )
        
        # Apply model
        with torch.no_grad():
            sources = self._apply_model(
                self._model,
                audio_tensor,
                shifts=self.shifts,
                overlap=self.overlap,
                segment=self.segment
            )
        
        # Convert back to numpy
        # sources shape: (batch, sources, channels, samples)
        sources_np = sources[0].cpu().numpy()  # (sources, channels, samples)
        
        # Map to stem names
        stem_names = self._model.sources  # e.g., ['drums', 'bass', 'other', 'vocals']
        stems = {}
        
        for i, stem_name in enumerate(stem_names):
            stem_audio = sources_np[i].T  # (samples, channels)
            
            # Resample back if we resampled input
            if original_sr is not None:
                stem_audio = self._resample(stem_audio, sample_rate, original_sr)
            
            stems[stem_name] = stem_audio
        
        return stems
    
    def _resample(
        self, 
        audio: np.ndarray, 
        from_sr: int, 
        to_sr: int
    ) -> np.ndarray:
        """Resample audio to target sample rate."""
        if from_sr == to_sr:
            return audio
        
        num_samples = int(len(audio) * to_sr / from_sr)
        
        if len(audio.shape) > 1:
            resampled = np.zeros((num_samples, audio.shape[1]))
            for ch in range(audio.shape[1]):
                resampled[:, ch] = signal.resample(audio[:, ch], num_samples)
            return resampled
        else:
            return signal.resample(audio, num_samples)


# =============================================================================
# SPLEETER BACKEND
# =============================================================================

class SpleeterBackend(StemSeparator):
    """
    Deezer's Spleeter U-Net model.
    
    Spleeter is lighter and faster than Demucs but generally
    produces lower quality separations, especially for drums.
    
    Configurations:
    - 2stems: vocals + accompaniment
    - 4stems: vocals + drums + bass + other (default)
    - 5stems: vocals + drums + bass + piano + other
    
    Requirements:
        pip install spleeter
    
    Note: Spleeter requires TensorFlow 2.x
    """
    
    def __init__(self, stems: int = 4):
        """
        Initialize Spleeter backend.
        
        Args:
            stems: Number of stems (2, 4, or 5).
        """
        if stems not in [2, 4, 5]:
            raise ValueError("Spleeter supports 2, 4, or 5 stems")
        self.stems = stems
        self._separator = None
    
    @property
    def name(self) -> str:
        return f"spleeter ({self.stems}stems)"
    
    def is_available(self) -> bool:
        """Check if Spleeter is installed."""
        try:
            from spleeter.separator import Separator
            return True
        except ImportError:
            return False
    
    def _load_separator(self):
        """Lazy load the separator on first use."""
        if self._separator is not None:
            return
        
        from spleeter.separator import Separator
        
        model_name = f"spleeter:{self.stems}stems"
        self._separator = Separator(model_name)
    
    def separate(
        self, 
        audio: np.ndarray, 
        sample_rate: int = SAMPLE_RATE
    ) -> Dict[str, np.ndarray]:
        """
        Run Spleeter stem separation.
        
        Spleeter works with files, so we use temp file handling
        for in-memory processing.
        
        Args:
            audio: Input audio (mono or stereo).
            sample_rate: Input sample rate.
        
        Returns:
            Dictionary of separated stems.
        """
        self._load_separator()
        
        # Ensure stereo
        if len(audio.shape) == 1:
            audio = np.column_stack([audio, audio])
        
        # Spleeter expects (samples, channels) float32
        audio = audio.astype(np.float32)
        
        # Use temp directory for Spleeter output
        with tempfile.TemporaryDirectory() as temp_dir:
            # Save input to temp file
            input_path = os.path.join(temp_dir, "input.wav")
            self._save_wav(input_path, audio, sample_rate)
            
            # Run separation
            self._separator.separate_to_file(input_path, temp_dir)
            
            # Load separated stems
            stems = self._load_separated_stems(temp_dir, audio.shape)
        
        return stems
    
    def _save_wav(self, path: str, audio: np.ndarray, sample_rate: int):
        """Save audio to WAV file."""
        # Scale to int16 range
        audio_int16 = np.clip(audio * 32767, -32768, 32767).astype(np.int16)
        wavfile.write(path, sample_rate, audio_int16)
    
    def _load_separated_stems(
        self, 
        output_dir: str, 
        original_shape: tuple
    ) -> Dict[str, np.ndarray]:
        """Load separated stems from Spleeter output directory."""
        stems = {}
        
        # Spleeter output structure: output_dir/input/stem_name.wav
        input_dir = os.path.join(output_dir, "input")
        
        # Map Spleeter stem names to standard names
        stem_mapping = {
            "vocals": "vocals",
            "accompaniment": "other",  # 2-stem mode
            "drums": "drums",
            "bass": "bass",
            "other": "other",
            "piano": "piano",  # 5-stem mode
        }
        
        for spleeter_name, standard_name in stem_mapping.items():
            stem_path = os.path.join(input_dir, f"{spleeter_name}.wav")
            
            if os.path.exists(stem_path):
                sr, audio_data = wavfile.read(stem_path)
                
                # Convert to float
                if audio_data.dtype == np.int16:
                    audio_data = audio_data.astype(np.float32) / 32767.0
                elif audio_data.dtype == np.int32:
                    audio_data = audio_data.astype(np.float32) / 2147483647.0
                
                stems[standard_name] = audio_data
        
        # Ensure all standard stems exist (fill missing with silence)
        for stem_name in STANDARD_STEMS:
            if stem_name not in stems:
                stems[stem_name] = np.zeros(original_shape, dtype=np.float32)
        
        return stems


# =============================================================================
# BASIC FREQUENCY-BASED BACKEND
# =============================================================================

class BasicSeparator(StemSeparator):
    """
    Simple frequency-based stem separation (no ML required).
    
    Uses basic DSP techniques:
    - Bass: Low-pass filter (<250 Hz)
    - Drums: Transient detection + mid frequencies
    - Vocals: Center channel extraction + bandpass (300-3000 Hz)
    - Other: Residual after subtracting other stems
    
    Quality Note:
        This is a fallback when ML backends are unavailable.
        Quality is significantly lower than Demucs or Spleeter.
        Useful for quick previews or systems without GPU/TensorFlow.
    """
    
    def __init__(self):
        """Initialize the basic separator."""
        pass
    
    @property
    def name(self) -> str:
        return "basic (frequency-based)"
    
    def is_available(self) -> bool:
        """Basic separator is always available."""
        return True
    
    def separate(
        self, 
        audio: np.ndarray, 
        sample_rate: int = SAMPLE_RATE
    ) -> Dict[str, np.ndarray]:
        """
        Perform frequency-based stem separation.
        
        Args:
            audio: Input audio (mono or stereo).
            sample_rate: Input sample rate.
        
        Returns:
            Dictionary of separated stems.
        """
        # Ensure stereo
        if len(audio.shape) == 1:
            audio = np.column_stack([audio, audio])
        
        n_samples = len(audio)
        nyquist = sample_rate / 2
        
        # Create empty stems
        stems = {name: np.zeros_like(audio) for name in STANDARD_STEMS}
        
        # 1. Extract bass: lowpass filter < 250 Hz
        bass_cutoff = min(250 / nyquist, 0.99)
        b_bass, a_bass = signal.butter(4, bass_cutoff, btype='low')
        for ch in range(audio.shape[1]):
            stems["bass"][:, ch] = signal.filtfilt(b_bass, a_bass, audio[:, ch])
        
        # 2. Extract mid-range for vocals (300-3000 Hz bandpass)
        low_cut = max(300 / nyquist, 0.001)
        high_cut = min(3000 / nyquist, 0.99)
        b_vocal, a_vocal = signal.butter(4, [low_cut, high_cut], btype='band')
        
        # Vocal extraction: center channel (L+R) minus sides
        mid = (audio[:, 0] + audio[:, 1]) / 2
        side = (audio[:, 0] - audio[:, 1]) / 2
        
        # Apply bandpass to mid channel
        mid_bp = signal.filtfilt(b_vocal, a_vocal, mid)
        
        # Vocals are often panned center
        vocal_mono = mid_bp * 1.5  # Boost center content
        stems["vocals"] = np.column_stack([vocal_mono * 0.7, vocal_mono * 0.7])
        
        # 3. Extract drums: transient detection + mid-high frequencies
        # Simple transient detection using difference
        drums_cutoff_low = max(100 / nyquist, 0.001)
        drums_cutoff_high = min(8000 / nyquist, 0.99)
        b_drums, a_drums = signal.butter(3, [drums_cutoff_low, drums_cutoff_high], btype='band')
        
        for ch in range(audio.shape[1]):
            filtered = signal.filtfilt(b_drums, a_drums, audio[:, ch])
            
            # Enhance transients using envelope
            envelope = np.abs(filtered)
            fast_env = self._envelope_follower(envelope, 0.001, 0.1, sample_rate)
            slow_env = self._envelope_follower(envelope, 0.05, 0.2, sample_rate)
            
            # Transient emphasis
            transient_mask = np.maximum(fast_env - slow_env, 0)
            transient_mask = transient_mask / (np.max(transient_mask) + 1e-10)
            
            stems["drums"][:, ch] = filtered * (0.5 + transient_mask * 1.5)
        
        # 4. Other: residual
        # Remove extracted stems from original
        residual = audio.copy()
        residual -= stems["bass"] * 0.8
        residual -= stems["vocals"] * 0.5
        residual -= stems["drums"] * 0.5
        
        # High-pass the residual to remove bass leakage
        hp_cutoff = max(200 / nyquist, 0.001)
        b_hp, a_hp = signal.butter(3, hp_cutoff, btype='high')
        for ch in range(audio.shape[1]):
            stems["other"][:, ch] = signal.filtfilt(b_hp, a_hp, residual[:, ch])
        
        # Normalize stems to prevent clipping
        for stem_name in stems:
            max_val = np.max(np.abs(stems[stem_name]))
            if max_val > 1.0:
                stems[stem_name] /= max_val
        
        return stems
    
    def _envelope_follower(
        self, 
        audio: np.ndarray, 
        attack_time: float, 
        release_time: float, 
        sample_rate: int
    ) -> np.ndarray:
        """Simple envelope follower."""
        attack_coeff = np.exp(-1.0 / (attack_time * sample_rate))
        release_coeff = np.exp(-1.0 / (release_time * sample_rate))
        
        envelope = np.zeros_like(audio)
        state = 0.0
        
        for i in range(len(audio)):
            if audio[i] > state:
                state = attack_coeff * state + (1 - attack_coeff) * audio[i]
            else:
                state = release_coeff * state + (1 - release_coeff) * audio[i]
            envelope[i] = state
        
        return envelope


# =============================================================================
# UNIFIED SEPARATOR INTERFACE
# =============================================================================

class StemSeparation:
    """
    Unified stem separation interface.
    
    Automatically selects the best available backend and provides
    a consistent API for all separation operations.
    
    Usage:
        >>> separator = StemSeparation()
        >>> stems = separator.separate(audio)
        >>> vocals = stems["vocals"]
        >>> drums = stems["drums"]
    
    File-based:
        >>> separator.separate_file("input.wav", "output_dir/")
        >>> # Creates: output_dir/vocals.wav, drums.wav, bass.wav, other.wav
    """
    
    def __init__(self, params: Optional[SeparationParams] = None):
        """
        Initialize the stem separator.
        
        Args:
            params: Separation parameters. Uses defaults if not provided.
        """
        self.params = params or SeparationParams()
        self._backend = self._init_backend()
    
    def _init_backend(self) -> StemSeparator:
        """Initialize the best available backend."""
        backend_type = self.params.backend
        
        # Auto-select best available
        if backend_type == SeparationBackend.AUTO:
            # Try Demucs first (highest quality)
            demucs = DemucsBackend(
                model_name=self.params.model,
                device=self.params.device,
                shifts=self.params.shifts,
                overlap=self.params.overlap,
                segment=self.params.segment
            )
            if demucs.is_available():
                return demucs
            
            # Try Spleeter next
            spleeter = SpleeterBackend(stems=len(self.params.stems))
            if spleeter.is_available():
                return spleeter
            
            # Fall back to basic
            return BasicSeparator()
        
        # Specific backend requested
        if backend_type == SeparationBackend.DEMUCS:
            backend = DemucsBackend(
                model_name=self.params.model,
                device=self.params.device,
                shifts=self.params.shifts,
                overlap=self.params.overlap,
                segment=self.params.segment
            )
            if backend.is_available():
                return backend
            warnings.warn("Demucs not available, falling back to basic separator")
            return BasicSeparator()
        
        if backend_type == SeparationBackend.SPLEETER:
            backend = SpleeterBackend(stems=len(self.params.stems))
            if backend.is_available():
                return backend
            warnings.warn("Spleeter not available, falling back to basic separator")
            return BasicSeparator()
        
        # Basic backend
        return BasicSeparator()
    
    @property
    def backend_name(self) -> str:
        """Get the name of the active backend."""
        return self._backend.name
    
    def separate(self, audio: np.ndarray) -> Dict[str, np.ndarray]:
        """
        Separate audio into stems.
        
        Args:
            audio: Input audio array (mono or stereo).
        
        Returns:
            Dictionary mapping stem names to audio arrays.
        """
        return self._backend.separate(audio, SAMPLE_RATE)
    
    def separate_file(
        self, 
        input_path: str, 
        output_dir: str,
        format: str = "wav",
        bit_depth: int = 24
    ) -> Dict[str, str]:
        """
        Separate audio file and save stems.
        
        Args:
            input_path: Path to input audio file.
            output_dir: Directory for output stem files.
            format: Output format ("wav", "flac").
            bit_depth: Output bit depth (16 or 24).
        
        Returns:
            Dictionary mapping stem names to output file paths.
        """
        # Create output directory
        os.makedirs(output_dir, exist_ok=True)
        
        # Load input audio
        sr, audio = wavfile.read(input_path)
        
        # Convert to float
        if audio.dtype == np.int16:
            audio = audio.astype(np.float32) / 32767.0
        elif audio.dtype == np.int32:
            audio = audio.astype(np.float32) / 2147483647.0
        
        # Resample if necessary
        if sr != SAMPLE_RATE:
            num_samples = int(len(audio) * SAMPLE_RATE / sr)
            if len(audio.shape) > 1:
                resampled = np.zeros((num_samples, audio.shape[1]))
                for ch in range(audio.shape[1]):
                    resampled[:, ch] = signal.resample(audio[:, ch], num_samples)
                audio = resampled
            else:
                audio = signal.resample(audio, num_samples)
        
        # Separate
        stems = self.separate(audio)
        
        # Save stems
        output_paths = {}
        base_name = Path(input_path).stem
        
        for stem_name, stem_audio in stems.items():
            output_path = os.path.join(output_dir, f"{base_name}_{stem_name}.{format}")
            self._save_audio(output_path, stem_audio, SAMPLE_RATE, bit_depth)
            output_paths[stem_name] = output_path
        
        return output_paths
    
    def _save_audio(
        self, 
        path: str, 
        audio: np.ndarray, 
        sample_rate: int, 
        bit_depth: int
    ):
        """Save audio to file."""
        # Scale to integer range
        if bit_depth == 16:
            audio_int = np.clip(audio * 32767, -32768, 32767).astype(np.int16)
        else:  # 24-bit stored as int32
            audio_int = np.clip(audio * 2147483647, -2147483648, 2147483647).astype(np.int32)
        
        wavfile.write(path, sample_rate, audio_int)
    
    @staticmethod
    def get_available_backends() -> List[str]:
        """
        Return list of available backends.
        
        Returns:
            List of backend names that are currently usable.
        """
        available = []
        
        if DemucsBackend().is_available():
            available.append("demucs")
        if SpleeterBackend().is_available():
            available.append("spleeter")
        available.append("basic")  # Always available
        
        return available


# =============================================================================
# STYLE TRANSFER / REMIX TOOLS
# =============================================================================

class StyleTransfer:
    """
    Extract style elements from reference tracks and apply to input.
    
    Provides tools for:
    - Extracting isolated stems (drums, vocals, bass)
    - Replacing stems in existing tracks
    - Creating instrumentals
    - Custom stem remixes
    
    Usage:
        >>> transfer = StyleTransfer()
        >>> drums = transfer.extract_drums(reference_track)
        >>> new_mix = transfer.replace_drums(original, drums)
    """
    
    def __init__(self, separator: Optional[StemSeparation] = None):
        """
        Initialize style transfer tools.
        
        Args:
            separator: Stem separator to use. Creates default if not provided.
        """
        self.separator = separator or StemSeparation()
    
    def extract_drums(self, audio: np.ndarray) -> np.ndarray:
        """
        Extract isolated drums from a track.
        
        Args:
            audio: Input audio array.
        
        Returns:
            Isolated drums audio.
        """
        stems = self.separator.separate(audio)
        return stems.get("drums", np.zeros_like(audio))
    
    def extract_bass(self, audio: np.ndarray) -> np.ndarray:
        """
        Extract isolated bass from a track.
        
        Args:
            audio: Input audio array.
        
        Returns:
            Isolated bass audio.
        """
        stems = self.separator.separate(audio)
        return stems.get("bass", np.zeros_like(audio))
    
    def extract_acapella(self, audio: np.ndarray) -> np.ndarray:
        """
        Extract isolated vocals (acapella) from a track.
        
        Args:
            audio: Input audio array.
        
        Returns:
            Isolated vocals audio.
        """
        stems = self.separator.separate(audio)
        return stems.get("vocals", np.zeros_like(audio))
    
    def create_instrumental(self, audio: np.ndarray) -> np.ndarray:
        """
        Remove vocals and keep instrumental.
        
        Args:
            audio: Input audio array.
        
        Returns:
            Instrumental (everything except vocals).
        """
        stems = self.separator.separate(audio)
        
        # Sum all stems except vocals
        instrumental = np.zeros_like(audio)
        for stem_name, stem_audio in stems.items():
            if stem_name != "vocals":
                instrumental += stem_audio
        
        # Normalize to prevent clipping
        max_val = np.max(np.abs(instrumental))
        if max_val > 1.0:
            instrumental /= max_val
        
        return instrumental
    
    def replace_drums(
        self, 
        original: np.ndarray, 
        new_drums: np.ndarray,
        blend: float = 1.0
    ) -> np.ndarray:
        """
        Replace drums in original with new drums.
        
        Args:
            original: Original audio to modify.
            new_drums: New drums audio to insert.
            blend: Mix ratio (0.0 = original drums, 1.0 = new drums).
        
        Returns:
            Audio with replaced drums.
        """
        stems = self.separator.separate(original)
        
        # Remove original drums
        no_drums = stems["vocals"] + stems["bass"] + stems["other"]
        
        # Blend drums
        blend = max(0.0, min(1.0, blend))
        blended_drums = (1 - blend) * stems["drums"] + blend * new_drums
        
        # Combine
        result = no_drums + blended_drums
        
        # Normalize
        max_val = np.max(np.abs(result))
        if max_val > 1.0:
            result /= max_val
        
        return result
    
    def replace_bass(
        self, 
        original: np.ndarray, 
        new_bass: np.ndarray,
        blend: float = 1.0
    ) -> np.ndarray:
        """
        Replace bass in original with new bass.
        
        Args:
            original: Original audio to modify.
            new_bass: New bass audio to insert.
            blend: Mix ratio (0.0 = original bass, 1.0 = new bass).
        
        Returns:
            Audio with replaced bass.
        """
        stems = self.separator.separate(original)
        
        # Remove original bass
        no_bass = stems["vocals"] + stems["drums"] + stems["other"]
        
        # Blend bass
        blend = max(0.0, min(1.0, blend))
        blended_bass = (1 - blend) * stems["bass"] + blend * new_bass
        
        # Combine
        result = no_bass + blended_bass
        
        # Normalize
        max_val = np.max(np.abs(result))
        if max_val > 1.0:
            result /= max_val
        
        return result
    
    def remix_stems(
        self, 
        audio: np.ndarray, 
        stem_levels: Dict[str, float]
    ) -> np.ndarray:
        """
        Remix with custom stem levels.
        
        Args:
            audio: Input audio array.
            stem_levels: Dictionary of stem levels.
                        {"vocals": 0.8, "drums": 1.2, "bass": 1.0, "other": 0.5}
                        Values > 1.0 boost, < 1.0 reduce.
        
        Returns:
            Remixed audio with adjusted stem levels.
        """
        stems = self.separator.separate(audio)
        
        # Apply levels
        remixed = np.zeros_like(audio)
        for stem_name, stem_audio in stems.items():
            level = stem_levels.get(stem_name, 1.0)
            remixed += stem_audio * level
        
        # Normalize
        max_val = np.max(np.abs(remixed))
        if max_val > 1.0:
            remixed /= max_val
        
        return remixed
    
    def swap_stems(
        self, 
        track_a: np.ndarray, 
        track_b: np.ndarray,
        stem_name: str
    ) -> tuple:
        """
        Swap a specific stem between two tracks.
        
        Args:
            track_a: First audio track.
            track_b: Second audio track.
            stem_name: Name of stem to swap ("vocals", "drums", "bass", "other").
        
        Returns:
            Tuple of (track_a_with_b_stem, track_b_with_a_stem).
        """
        stems_a = self.separator.separate(track_a)
        stems_b = self.separator.separate(track_b)
        
        # Create new tracks with swapped stems
        result_a = np.zeros_like(track_a)
        result_b = np.zeros_like(track_b)
        
        for name in STANDARD_STEMS:
            if name == stem_name:
                result_a += stems_b.get(name, np.zeros_like(track_a))
                result_b += stems_a.get(name, np.zeros_like(track_b))
            else:
                result_a += stems_a.get(name, np.zeros_like(track_a))
                result_b += stems_b.get(name, np.zeros_like(track_b))
        
        # Normalize
        for result in [result_a, result_b]:
            max_val = np.max(np.abs(result))
            if max_val > 1.0:
                result /= max_val
        
        return result_a, result_b


# =============================================================================
# BATCH PROCESSING
# =============================================================================

class BatchSeparator:
    """
    Process multiple files efficiently.
    
    Optimizes for batch operations by:
    - Loading model once
    - Processing files in sequence with progress tracking
    - Consistent output structure
    
    Usage:
        >>> batch = BatchSeparator()
        >>> results = batch.process_directory("input/", "output/")
    """
    
    def __init__(self, params: Optional[SeparationParams] = None):
        """
        Initialize batch separator.
        
        Args:
            params: Separation parameters.
        """
        self.separator = StemSeparation(params)
    
    def process_directory(
        self, 
        input_dir: str, 
        output_dir: str,
        pattern: str = "*.wav",
        recursive: bool = False
    ) -> List[Dict[str, str]]:
        """
        Process all matching files in directory.
        
        Args:
            input_dir: Input directory path.
            output_dir: Output directory path.
            pattern: Glob pattern for file matching.
            recursive: Search subdirectories if True.
        
        Returns:
            List of dictionaries with output paths for each file.
        """
        from glob import glob
        
        input_path = Path(input_dir)
        
        if recursive:
            files = list(input_path.rglob(pattern))
        else:
            files = list(input_path.glob(pattern))
        
        return self.process_files(
            [str(f) for f in files],
            output_dir
        )
    
    def process_files(
        self, 
        file_list: List[str], 
        output_dir: str
    ) -> List[Dict[str, str]]:
        """
        Process list of files.
        
        Args:
            file_list: List of input file paths.
            output_dir: Output directory path.
        
        Returns:
            List of dictionaries with output paths for each file.
        """
        results = []
        
        for i, file_path in enumerate(file_list):
            try:
                # Create subdirectory for each input file
                file_name = Path(file_path).stem
                file_output_dir = os.path.join(output_dir, file_name)
                
                # Process file
                output_paths = self.separator.separate_file(
                    file_path,
                    file_output_dir
                )
                
                results.append({
                    "input": file_path,
                    "output_dir": file_output_dir,
                    "stems": output_paths,
                    "status": "success"
                })
                
            except Exception as e:
                results.append({
                    "input": file_path,
                    "status": "error",
                    "error": str(e)
                })
        
        return results


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def separate_stems(
    audio: np.ndarray,
    backend: str = "auto",
    sample_rate: int = SAMPLE_RATE
) -> Dict[str, np.ndarray]:
    """
    Quick stem separation with auto backend selection.
    
    Args:
        audio: Input audio array.
        backend: Backend to use ("auto", "demucs", "spleeter", "basic").
        sample_rate: Audio sample rate.
    
    Returns:
        Dictionary of separated stems.
    
    Example:
        >>> stems = separate_stems(audio)
        >>> vocals = stems["vocals"]
        >>> drums = stems["drums"]
    """
    backend_enum = {
        "auto": SeparationBackend.AUTO,
        "demucs": SeparationBackend.DEMUCS,
        "spleeter": SeparationBackend.SPLEETER,
        "basic": SeparationBackend.BASIC,
    }.get(backend.lower(), SeparationBackend.AUTO)
    
    params = SeparationParams(backend=backend_enum)
    separator = StemSeparation(params)
    return separator.separate(audio)


def extract_vocals(audio: np.ndarray, sample_rate: int = SAMPLE_RATE) -> np.ndarray:
    """
    Extract vocals from audio.
    
    Args:
        audio: Input audio array.
        sample_rate: Audio sample rate.
    
    Returns:
        Isolated vocals audio.
    """
    stems = separate_stems(audio, sample_rate=sample_rate)
    return stems.get("vocals", np.zeros_like(audio))


def remove_vocals(audio: np.ndarray, sample_rate: int = SAMPLE_RATE) -> np.ndarray:
    """
    Create instrumental by removing vocals.
    
    Args:
        audio: Input audio array.
        sample_rate: Audio sample rate.
    
    Returns:
        Instrumental audio (no vocals).
    """
    transfer = StyleTransfer()
    return transfer.create_instrumental(audio)


def extract_drums(audio: np.ndarray, sample_rate: int = SAMPLE_RATE) -> np.ndarray:
    """
    Extract drums from audio.
    
    Args:
        audio: Input audio array.
        sample_rate: Audio sample rate.
    
    Returns:
        Isolated drums audio.
    """
    stems = separate_stems(audio, sample_rate=sample_rate)
    return stems.get("drums", np.zeros_like(audio))


def extract_bass(audio: np.ndarray, sample_rate: int = SAMPLE_RATE) -> np.ndarray:
    """
    Extract bass from audio.
    
    Args:
        audio: Input audio array.
        sample_rate: Audio sample rate.
    
    Returns:
        Isolated bass audio.
    """
    stems = separate_stems(audio, sample_rate=sample_rate)
    return stems.get("bass", np.zeros_like(audio))


def check_separation_backends() -> Dict[str, bool]:
    """
    Return availability status of all backends.
    
    Returns:
        Dictionary mapping backend names to availability status.
    
    Example:
        >>> check_separation_backends()
        {"demucs": True, "spleeter": False, "basic": True}
    """
    return {
        "demucs": DemucsBackend().is_available(),
        "spleeter": SpleeterBackend().is_available(),
        "basic": True,  # Always available
    }


def get_best_backend() -> str:
    """
    Get the name of the best available backend.
    
    Returns:
        Name of the highest quality available backend.
    """
    if DemucsBackend().is_available():
        return "demucs"
    elif SpleeterBackend().is_available():
        return "spleeter"
    else:
        return "basic"


# =============================================================================
# INSTALLATION HELPERS
# =============================================================================

def install_demucs() -> str:
    """
    Print instructions for installing Demucs.
    
    Returns:
        Installation instructions as string.
    """
    instructions = """
================================================================================
                         DEMUCS INSTALLATION GUIDE
================================================================================

Demucs is Facebook's state-of-the-art stem separation model using hybrid
transformer architecture. It provides the highest quality separations.

BASIC INSTALLATION:
-------------------
    pip install demucs

FOR GPU ACCELERATION (NVIDIA CUDA):
-----------------------------------
    # Install PyTorch with CUDA support first
    pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
    
    # Then install Demucs
    pip install demucs

FOR APPLE SILICON (MPS):
------------------------
    # PyTorch natively supports Apple Silicon
    pip install torch torchvision torchaudio
    pip install demucs

AVAILABLE MODELS:
-----------------
    - htdemucs     : Hybrid Transformer (default, best quality)
    - htdemucs_ft  : Fine-tuned for better vocal separation
    - htdemucs_6s  : 6 stems (adds piano and guitar)
    - mdx_extra    : Alternative MDX-Net architecture

MEMORY REQUIREMENTS:
--------------------
    - CPU: ~4GB RAM minimum, 8GB recommended
    - GPU: ~4GB VRAM for htdemucs, ~6GB for htdemucs_6s

VERIFY INSTALLATION:
--------------------
    python -c "import demucs; print('Demucs installed successfully')"

================================================================================
"""
    print(instructions)
    return instructions


def install_spleeter() -> str:
    """
    Print instructions for installing Spleeter.
    
    Returns:
        Installation instructions as string.
    """
    instructions = """
================================================================================
                        SPLEETER INSTALLATION GUIDE
================================================================================

Spleeter is Deezer's U-Net based stem separation model. It's faster than
Demucs but generally produces lower quality separations.

BASIC INSTALLATION:
-------------------
    pip install spleeter

IMPORTANT NOTES:
----------------
    - Spleeter requires TensorFlow 2.x
    - On first use, models are downloaded automatically (~300MB per model)
    - May have compatibility issues with newer Python versions

AVAILABLE CONFIGURATIONS:
-------------------------
    - 2stems : Vocals + Accompaniment
    - 4stems : Vocals + Drums + Bass + Other (default)
    - 5stems : Vocals + Drums + Bass + Piano + Other

VERIFY INSTALLATION:
--------------------
    python -c "from spleeter.separator import Separator; print('Spleeter installed')"

TROUBLESHOOTING:
----------------
    If you encounter TensorFlow issues:
    
    pip uninstall tensorflow
    pip install tensorflow==2.10.0

================================================================================
"""
    print(instructions)
    return instructions


def print_system_info() -> Dict[str, any]:
    """
    Print system information relevant to stem separation.
    
    Returns:
        Dictionary with system information.
    """
    info = {
        "backends": check_separation_backends(),
        "best_backend": get_best_backend(),
        "cuda_available": False,
        "mps_available": False,
        "recommended_device": "cpu",
    }
    
    try:
        import torch
        info["cuda_available"] = torch.cuda.is_available()
        info["mps_available"] = hasattr(torch.backends, "mps") and torch.backends.mps.is_available()
        
        if info["cuda_available"]:
            info["recommended_device"] = "cuda"
            info["gpu_name"] = torch.cuda.get_device_name(0)
        elif info["mps_available"]:
            info["recommended_device"] = "mps"
    except ImportError:
        pass
    
    print("=" * 60)
    print("              STEM SEPARATION SYSTEM INFO")
    print("=" * 60)
    print(f"\nAvailable Backends:")
    for backend, available in info["backends"].items():
        status = "✓ Available" if available else "✗ Not installed"
        print(f"  - {backend}: {status}")
    
    print(f"\nBest Available Backend: {info['best_backend']}")
    print(f"CUDA (NVIDIA GPU): {'Available' if info['cuda_available'] else 'Not available'}")
    print(f"MPS (Apple Silicon): {'Available' if info['mps_available'] else 'Not available'}")
    print(f"Recommended Device: {info['recommended_device']}")
    
    if "gpu_name" in info:
        print(f"GPU: {info['gpu_name']}")
    
    print("=" * 60)
    
    return info


# =============================================================================
# MODULE EXPORTS
# =============================================================================

__all__ = [
    # Enums
    "SeparationBackend",
    
    # Parameters
    "SeparationParams",
    
    # Backend classes
    "StemSeparator",
    "DemucsBackend",
    "SpleeterBackend",
    "BasicSeparator",
    
    # Main classes
    "StemSeparation",
    "StyleTransfer",
    "BatchSeparator",
    
    # Convenience functions
    "separate_stems",
    "extract_vocals",
    "remove_vocals",
    "extract_drums",
    "extract_bass",
    "check_separation_backends",
    "get_best_backend",
    
    # Installation helpers
    "install_demucs",
    "install_spleeter",
    "print_system_info",
    
    # Constants
    "STANDARD_STEMS",
    "EXTENDED_STEMS_6",
    "DEMUCS_MODELS",
]
