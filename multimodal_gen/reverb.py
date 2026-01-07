"""
Convolution Reverb - FFT-based reverb with procedural impulse responses.

Provides realistic room simulation through convolution with generated
or loaded impulse responses.
"""

from dataclasses import dataclass
from typing import Dict, Optional, Tuple
import numpy as np
from scipy import signal


@dataclass
class IRConfig:
    """Impulse response generation configuration."""
    ir_type: str = "room"           # "room", "hall", "plate", "spring", "lofi"
    decay_seconds: float = 1.5      # RT60 decay time
    damping: float = 0.5            # High frequency absorption (0-1)
    size: float = 0.5               # Room size factor (0-1)
    diffusion: float = 0.7          # Echo density (0-1)
    modulation: float = 0.0         # Chorus-like modulation (0-1)
    pre_delay_ms: float = 0.0       # Initial delay before reverb


@dataclass
class ReverbConfig:
    """Reverb effect configuration."""
    wet_dry: float = 0.3            # Wet/dry mix (0=dry, 1=wet)
    pre_delay_ms: float = 20.0      # Pre-delay in ms
    low_cut_hz: float = 80.0        # High-pass on wet signal
    high_cut_hz: float = 12000.0    # Low-pass on wet signal
    stereo_width: float = 1.0       # Stereo spread (0=mono, 1=full)


class ConvolutionReverb:
    """
    FFT-based convolution reverb.
    
    Usage:
        reverb = ConvolutionReverb(sample_rate=44100)
        
        # Use preset IR
        wet = reverb.process(audio, preset="hall")
        
        # Or generate custom IR
        ir = reverb.generate_ir(IRConfig(ir_type="plate", decay_seconds=2.0))
        wet = reverb.convolve(audio, ir, config)
    """
    
    def __init__(self, sample_rate: int = 44100):
        self.sample_rate = sample_rate
        self._ir_cache: Dict[str, np.ndarray] = {}
        self._init_presets()
    
    def _init_presets(self) -> None:
        """Pre-generate common IR presets."""
        # Generate and cache preset IRs
        for preset_name, ir_config in IR_PRESETS.items():
            self._ir_cache[preset_name] = self.generate_ir(ir_config)
    
    def generate_ir(self, config: IRConfig) -> np.ndarray:
        """
        Generate a procedural impulse response.
        
        Techniques by type:
        - room: Exponential decay with early reflections
        - hall: Long decay with dense late reverb
        - plate: Bright, dense, smooth decay
        - spring: Bouncy with characteristic "boing"
        - lofi: Short, colored, lo-fi character
        
        Args:
            config: IR generation configuration
            
        Returns:
            Stereo impulse response array
        """
        # Calculate IR length based on decay time
        ir_length = int(config.decay_seconds * self.sample_rate * 1.5)
        
        # Generate early reflections
        early = self.generate_early_reflections(config.size, num_reflections=12)
        
        # Generate late reverb
        late = self.generate_late_reverb(
            config.decay_seconds,
            config.damping,
            config.diffusion
        )
        
        # Ensure both parts are same length
        max_len = max(len(early), len(late))
        if len(early) < max_len:
            early = np.pad(early, ((0, max_len - len(early)), (0, 0)), mode='constant')
        if len(late) < max_len:
            late = np.pad(late, ((0, max_len - len(late)), (0, 0)), mode='constant')
        
        # Type-specific processing
        if config.ir_type == "room":
            # Room: balanced early/late, moderate decay
            ir = early * 0.4 + late * 0.6
            
        elif config.ir_type == "hall":
            # Hall: reduced early, dominant late reverb
            ir = early * 0.2 + late * 0.8
            
        elif config.ir_type == "plate":
            # Plate: very dense, bright
            # Add extra high-frequency energy
            noise = np.random.randn(max_len, 2) * 0.1
            # High-pass the noise
            sos = signal.butter(4, 2000, btype='high', fs=self.sample_rate, output='sos')
            noise_filtered = np.column_stack([
                signal.sosfilt(sos, noise[:, 0]),
                signal.sosfilt(sos, noise[:, 1])
            ])
            ir = early * 0.3 + late * 0.5 + noise_filtered * 0.2
            
        elif config.ir_type == "spring":
            # Spring: bouncy with resonances
            # Add resonant peaks
            num_bounces = 8
            bounce_decay = 0.6
            ir = np.zeros((max_len, 2))
            for i in range(num_bounces):
                delay_samples = int((i + 1) * 0.05 * self.sample_rate * config.size)
                if delay_samples < max_len:
                    amplitude = bounce_decay ** i
                    # Add a spike for each bounce
                    ir[delay_samples:delay_samples + 10] += amplitude * 0.3
            # Mix with some late reverb
            ir += late * 0.4
            
        elif config.ir_type == "lofi":
            # Lofi: short, colored
            ir = early * 0.7 + late * 0.3
            # Truncate for lo-fi character
            lofi_length = int(config.decay_seconds * self.sample_rate * 0.5)
            if lofi_length < len(ir):
                ir = ir[:lofi_length]
            # Add some grit
            ir = np.tanh(ir * 1.5) * 0.8
        else:
            # Default to room
            ir = early * 0.4 + late * 0.6
        
        # Apply damping (high-frequency rolloff)
        if config.damping > 0:
            # Create damping envelope that increases over time
            damping_curve = np.linspace(0, config.damping, len(ir))
            # Apply low-pass filter with increasing cutoff reduction
            for i in range(0, len(ir), 512):
                chunk_end = min(i + 512, len(ir))
                chunk = ir[i:chunk_end]
                
                # Calculate cutoff based on damping curve
                avg_damping = np.mean(damping_curve[i:chunk_end])
                cutoff = 20000 * (1 - avg_damping * 0.8)  # 20kHz to 4kHz
                
                if cutoff < self.sample_rate / 2:
                    sos = signal.butter(2, cutoff, btype='low', fs=self.sample_rate, output='sos')
                    ir[i:chunk_end, 0] = signal.sosfilt(sos, chunk[:, 0])
                    ir[i:chunk_end, 1] = signal.sosfilt(sos, chunk[:, 1])
        
        # Apply modulation if requested (chorus-like effect)
        if config.modulation > 0:
            mod_depth = config.modulation * 0.002 * self.sample_rate  # Max 2ms modulation
            mod_rate = 0.5  # Hz
            t = np.arange(len(ir)) / self.sample_rate
            mod_signal = np.sin(2 * np.pi * mod_rate * t) * mod_depth
            
            # Apply modulation to right channel only for stereo effect
            for i in range(len(ir)):
                delay = int(mod_signal[i])
                if 0 <= i + delay < len(ir):
                    ir[i, 1] = ir[min(max(i + delay, 0), len(ir) - 1), 1]
        
        # Add pre-delay if specified
        if config.pre_delay_ms > 0:
            pre_delay_samples = int(config.pre_delay_ms * self.sample_rate / 1000)
            ir = np.pad(ir, ((pre_delay_samples, 0), (0, 0)), mode='constant')
        
        # Normalize to prevent clipping
        # Use RMS normalization rather than peak to maintain energy but prevent excessive peaks
        rms = np.sqrt(np.mean(ir ** 2))
        if rms > 0:
            # Target RMS of 0.1 (leaves plenty of headroom)
            ir = ir / rms * 0.1
        
        # Additional peak limiting to be safe
        peak = np.max(np.abs(ir))
        if peak > 0.3:
            ir = ir / peak * 0.3
        
        return ir
    
    def generate_early_reflections(
        self,
        size: float,
        num_reflections: int = 12
    ) -> np.ndarray:
        """Generate discrete early reflections based on room size."""
        # Calculate max delay based on room size
        max_delay_ms = 80 * size  # 0 to 80ms
        max_delay_samples = int(max_delay_ms * self.sample_rate / 1000)
        
        # Create IR buffer
        ir_length = max(max_delay_samples + 1000, 2000)
        ir = np.zeros((ir_length, 2))
        
        # Initial impulse
        ir[0] = [1.0, 1.0]
        
        # Generate reflections with random delays and amplitudes
        np.random.seed(42)  # Reproducible reflections
        for i in range(num_reflections):
            # Delay time (ms) - clustered early, then spread out
            if i < num_reflections // 2:
                delay_ms = np.random.uniform(5, max_delay_ms * 0.5)
            else:
                delay_ms = np.random.uniform(max_delay_ms * 0.5, max_delay_ms)
            
            delay_samples = int(delay_ms * self.sample_rate / 1000)
            
            # Amplitude decay with distance
            amplitude = 0.7 ** (i + 1)
            
            # Slightly different amplitudes for L/R
            amp_l = amplitude * np.random.uniform(0.8, 1.0)
            amp_r = amplitude * np.random.uniform(0.8, 1.0)
            
            # Add reflection
            if delay_samples < ir_length:
                ir[delay_samples, 0] += amp_l
                ir[delay_samples, 1] += amp_r
        
        return ir
    
    def generate_late_reverb(
        self,
        decay_seconds: float,
        damping: float,
        diffusion: float
    ) -> np.ndarray:
        """Generate diffuse late reverb tail."""
        # Length of late reverb
        length_samples = int(decay_seconds * self.sample_rate * 1.2)
        
        # Start late reverb after early reflections
        start_delay = int(0.08 * self.sample_rate)  # 80ms
        
        # Generate dense noise
        density = int(1000 * diffusion)  # Number of echoes per second
        num_echoes = int(decay_seconds * density)
        
        ir = np.zeros((length_samples, 2))
        
        # Create exponential decay envelope
        t = np.arange(length_samples) / self.sample_rate
        decay_curve = np.exp(-t * (6.91 / decay_seconds))  # -60dB at decay_seconds
        
        # Generate random echo times (Velvet noise approach)
        np.random.seed(123)  # Reproducible
        echo_times = np.sort(np.random.uniform(0, decay_seconds, num_echoes))
        
        for echo_time in echo_times:
            sample_idx = int(echo_time * self.sample_rate)
            if sample_idx < length_samples:
                # Random polarity for each echo (reduces modal resonances)
                polarity_l = 1 if np.random.rand() > 0.5 else -1
                polarity_r = 1 if np.random.rand() > 0.5 else -1
                
                amplitude = decay_curve[sample_idx]
                ir[sample_idx, 0] += polarity_l * amplitude
                ir[sample_idx, 1] += polarity_r * amplitude
        
        # Smooth with short filter for diffusion
        if diffusion > 0.5:
            window_size = int(0.005 * self.sample_rate)  # 5ms smoothing
            window = np.hanning(window_size)
            window = window / np.sum(window)
            
            ir[:, 0] = np.convolve(ir[:, 0], window, mode='same')
            ir[:, 1] = np.convolve(ir[:, 1], window, mode='same')
        
        return ir
    
    def convolve(
        self,
        audio: np.ndarray,
        ir: np.ndarray,
        config: ReverbConfig
    ) -> np.ndarray:
        """
        Apply convolution reverb to audio.
        
        Uses FFT-based overlap-add for efficiency.
        
        Args:
            audio: Input audio (mono or stereo)
            ir: Impulse response
            config: Reverb configuration
            
        Returns:
            Processed audio with reverb applied
        """
        if len(audio) == 0:
            return audio
        
        # Store original length and shape
        original_length = len(audio)
        is_mono = len(audio.shape) == 1
        
        # Convert audio to stereo if mono
        if is_mono:
            audio_stereo = np.stack([audio, audio], axis=1)
        else:
            audio_stereo = audio
        
        # Don't add pre-delay by padding audio - handle it differently
        # Pre-delay will be handled by mixing the wet signal later
        
        # Perform convolution
        wet = self.fft_convolve(audio_stereo, ir)
        
        # Apply EQ to wet signal
        wet = self.apply_pre_eq(wet, config.low_cut_hz, config.high_cut_hz)
        
        # Apply stereo width
        wet = self.apply_stereo_width(wet, config.stereo_width)
        
        # Trim or pad wet signal to match original audio length
        if len(wet) > original_length:
            wet = wet[:original_length]
        elif len(wet) < original_length:
            wet = np.pad(wet, ((0, original_length - len(wet)), (0, 0)), mode='constant')
        
        # Apply pre-delay to wet signal by shifting it
        if config.pre_delay_ms > 0:
            pre_delay_samples = int(config.pre_delay_ms * self.sample_rate / 1000)
            if pre_delay_samples < original_length:
                wet = np.roll(wet, pre_delay_samples, axis=0)
                # Zero out the wrapped portion
                wet[:pre_delay_samples] = 0
        
        # Ensure audio_stereo is same length as wet
        if len(audio_stereo) < original_length:
            audio_stereo = np.pad(audio_stereo, ((0, original_length - len(audio_stereo)), (0, 0)), mode='constant')
        elif len(audio_stereo) > original_length:
            audio_stereo = audio_stereo[:original_length]
        
        # Mix with dry signal
        output = audio_stereo * (1 - config.wet_dry) + wet * config.wet_dry
        
        # Prevent clipping only if there's actual wet signal
        if config.wet_dry > 0:
            peak = np.max(np.abs(output))
            if peak > 0.99:
                output = output * (0.99 / peak)
        
        # Return same format as input
        if is_mono:
            return output[:, 0]  # Return mono
        else:
            return output
    
    def fft_convolve(
        self,
        audio: np.ndarray,
        ir: np.ndarray
    ) -> np.ndarray:
        """
        Efficient FFT-based convolution.
        
        Uses overlap-add method for long audio.
        """
        # Process each channel separately
        result = np.zeros((len(audio) + len(ir) - 1, 2))
        
        for ch in range(2):
            # Get channel data
            audio_ch = audio[:, ch] if audio.shape[1] > ch else audio[:, 0]
            ir_ch = ir[:, ch] if ir.shape[1] > ch else ir[:, 0]
            
            # Use scipy's fftconvolve for efficiency
            result[:, ch] = signal.fftconvolve(audio_ch, ir_ch, mode='full')
        
        return result
    
    def process(
        self,
        audio: np.ndarray,
        preset: str = "room",
        config: Optional[ReverbConfig] = None
    ) -> np.ndarray:
        """
        Process audio with a preset reverb.
        
        Args:
            audio: Input audio
            preset: Preset name (room, hall, plate, spring, lofi, tight_room)
            config: Optional reverb configuration override
            
        Returns:
            Processed audio
        """
        if config is None:
            config = ReverbConfig()
        
        # Get preset IR
        ir = self.get_preset_ir(preset)
        
        # Apply convolution
        return self.convolve(audio, ir, config)
    
    def apply_pre_eq(
        self,
        audio: np.ndarray,
        low_cut_hz: float,
        high_cut_hz: float
    ) -> np.ndarray:
        """Apply EQ to reverb signal (cut lows/highs)."""
        if len(audio) == 0:
            return audio
        
        result = audio.copy()
        
        # High-pass filter (cut lows)
        if low_cut_hz > 20 and low_cut_hz < self.sample_rate / 2:
            sos = signal.butter(2, low_cut_hz, btype='high', fs=self.sample_rate, output='sos')
            result[:, 0] = signal.sosfilt(sos, result[:, 0])
            result[:, 1] = signal.sosfilt(sos, result[:, 1])
        
        # Low-pass filter (cut highs)
        if high_cut_hz < self.sample_rate / 2:
            sos = signal.butter(2, high_cut_hz, btype='low', fs=self.sample_rate, output='sos')
            result[:, 0] = signal.sosfilt(sos, result[:, 0])
            result[:, 1] = signal.sosfilt(sos, result[:, 1])
        
        return result
    
    def apply_stereo_width(
        self,
        audio: np.ndarray,
        width: float
    ) -> np.ndarray:
        """Adjust stereo width of reverb (0=mono, 1=full, 2=widened)."""
        if len(audio) == 0 or width == 1.0:
            return audio
        
        # Mid-side processing
        mid = (audio[:, 0] + audio[:, 1]) / 2
        side = (audio[:, 0] - audio[:, 1]) / 2
        
        # Adjust side signal
        side = side * width
        
        # Convert back to L/R
        left = mid + side
        right = mid - side
        
        return np.stack([left, right], axis=1)
    
    def get_preset_ir(self, name: str) -> np.ndarray:
        """Get a cached preset IR by name."""
        if name not in self._ir_cache:
            raise ValueError(f"Unknown preset: {name}. Available: {list(self._ir_cache.keys())}")
        return self._ir_cache[name]
    
    def load_ir(self, path: str) -> np.ndarray:
        """Load an IR from a WAV file."""
        import soundfile as sf
        
        ir, sr = sf.read(path)
        
        # Resample if needed (simplified - in production use resampy)
        if sr != self.sample_rate:
            raise ValueError(f"IR sample rate ({sr}) doesn't match reverb ({self.sample_rate})")
        
        # Convert to stereo if mono
        if len(ir.shape) == 1:
            ir = np.stack([ir, ir], axis=1)
        
        return ir


# Pre-defined IR configurations for common spaces
IR_PRESETS: Dict[str, IRConfig] = {
    "tight_room": IRConfig(
        ir_type="room",
        decay_seconds=0.3,
        damping=0.7,
        size=0.2,
        diffusion=0.5
    ),
    "room": IRConfig(
        ir_type="room",
        decay_seconds=0.8,
        damping=0.5,
        size=0.4,
        diffusion=0.6
    ),
    "large_room": IRConfig(
        ir_type="room",
        decay_seconds=1.2,
        damping=0.4,
        size=0.7,
        diffusion=0.7
    ),
    "hall": IRConfig(
        ir_type="hall",
        decay_seconds=2.5,
        damping=0.3,
        size=0.9,
        diffusion=0.8
    ),
    "plate": IRConfig(
        ir_type="plate",
        decay_seconds=1.5,
        damping=0.2,
        size=0.5,
        diffusion=0.9
    ),
    "spring": IRConfig(
        ir_type="spring",
        decay_seconds=1.0,
        damping=0.6,
        size=0.3,
        diffusion=0.4,
        modulation=0.3
    ),
    "lofi_room": IRConfig(
        ir_type="lofi",
        decay_seconds=0.6,
        damping=0.8,
        size=0.3,
        diffusion=0.5
    ),
}

# Default reverb configurations per genre
GENRE_REVERB_CONFIGS: Dict[str, Tuple[str, ReverbConfig]] = {
    "trap": ("tight_room", ReverbConfig(wet_dry=0.15, pre_delay_ms=10)),
    "boom_bap": ("room", ReverbConfig(wet_dry=0.2, pre_delay_ms=20)),
    "lofi": ("lofi_room", ReverbConfig(wet_dry=0.35, high_cut_hz=6000)),
    "house": ("plate", ReverbConfig(wet_dry=0.25, pre_delay_ms=30)),
    "jazz": ("hall", ReverbConfig(wet_dry=0.3, pre_delay_ms=25)),
    "orchestral": ("hall", ReverbConfig(wet_dry=0.4, pre_delay_ms=40)),
    "rock": ("room", ReverbConfig(wet_dry=0.2, pre_delay_ms=15)),
    "ambient": ("hall", ReverbConfig(wet_dry=0.6, stereo_width=1.5)),
}


# Convenience functions
def apply_reverb(
    audio: np.ndarray,
    preset: str = "room",
    wet_dry: float = 0.3,
    sample_rate: int = 44100
) -> np.ndarray:
    """
    Quick reverb application with preset.
    
    Args:
        audio: Input audio
        preset: IR preset name
        wet_dry: Mix amount (0-1)
        sample_rate: Sample rate
        
    Returns:
        Audio with reverb
    """
    reverb = ConvolutionReverb(sample_rate=sample_rate)
    config = ReverbConfig(wet_dry=wet_dry)
    return reverb.process(audio, preset=preset, config=config)


def apply_genre_reverb(
    audio: np.ndarray,
    genre: str,
    sample_rate: int = 44100
) -> np.ndarray:
    """
    Apply genre-appropriate reverb.
    
    Args:
        audio: Input audio
        genre: Genre name
        sample_rate: Sample rate
        
    Returns:
        Audio with genre-matched reverb
    """
    if genre not in GENRE_REVERB_CONFIGS:
        # Default to room reverb
        preset = "room"
        config = ReverbConfig()
    else:
        preset, config = GENRE_REVERB_CONFIGS[genre]
    
    reverb = ConvolutionReverb(sample_rate=sample_rate)
    return reverb.process(audio, preset=preset, config=config)
