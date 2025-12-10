"""
Assets Generator Module

Generates procedural audio samples for when bundled samples aren't available.
Creates royalty-free sounds using pure synthesis:

- 808 bass (sine wave with pitch envelope)
- Kick drum (sine with fast decay)
- Snare/clap (filtered noise burst)
- Hi-hat (high-passed noise)
- Vinyl crackle (sparse impulses + filtered noise)
- Rain/atmosphere (filtered noise)

All synthesis uses numpy for CPU-based generation.
Output: 44.1kHz, 16-bit WAV files.
"""

import numpy as np
from typing import Optional, Tuple, Dict, List
import os
from dataclasses import dataclass
from enum import Enum

try:
    import soundfile as sf
    HAS_SOUNDFILE = True
except ImportError:
    HAS_SOUNDFILE = False
    import wave
    import struct

from .utils import SAMPLE_RATE, BIT_DEPTH


# =============================================================================
# SYNTHESIS UTILITIES
# =============================================================================

def normalize_audio(audio: np.ndarray, target_peak: float = 0.95) -> np.ndarray:
    """Normalize audio to target peak level."""
    peak = np.max(np.abs(audio))
    if peak > 0:
        return audio * (target_peak / peak)
    return audio


def apply_envelope(
    audio: np.ndarray,
    attack_samples: int,
    decay_samples: int,
    sustain_level: float,
    release_samples: int,
    sustain_samples: int = 0
) -> np.ndarray:
    """Apply ADSR envelope to audio."""
    total_samples = len(audio)
    envelope = np.ones(total_samples)
    
    # Attack
    if attack_samples > 0:
        attack_end = min(attack_samples, total_samples)
        envelope[:attack_end] = np.linspace(0, 1, attack_end)
    
    # Decay
    decay_start = attack_samples
    decay_end = min(decay_start + decay_samples, total_samples)
    if decay_end > decay_start:
        envelope[decay_start:decay_end] = np.linspace(1, sustain_level, decay_end - decay_start)
    
    # Sustain
    sustain_start = decay_end
    sustain_end = min(sustain_start + sustain_samples, total_samples)
    if sustain_end > sustain_start:
        envelope[sustain_start:sustain_end] = sustain_level
    
    # Release
    release_start = sustain_end if sustain_samples > 0 else decay_end
    if release_start < total_samples:
        release_len = total_samples - release_start
        envelope[release_start:] = np.linspace(
            envelope[release_start - 1] if release_start > 0 else sustain_level,
            0,
            release_len
        )
    
    return audio * envelope


def lowpass_filter(audio: np.ndarray, cutoff_hz: float, sample_rate: int = SAMPLE_RATE) -> np.ndarray:
    """Simple one-pole lowpass filter."""
    # Compute coefficient
    rc = 1.0 / (2.0 * np.pi * cutoff_hz)
    dt = 1.0 / sample_rate
    alpha = dt / (rc + dt)
    
    # Apply filter
    filtered = np.zeros_like(audio)
    filtered[0] = audio[0] * alpha
    
    for i in range(1, len(audio)):
        filtered[i] = filtered[i-1] + alpha * (audio[i] - filtered[i-1])
    
    return filtered


def highpass_filter(audio: np.ndarray, cutoff_hz: float, sample_rate: int = SAMPLE_RATE) -> np.ndarray:
    """Simple one-pole highpass filter."""
    # Compute coefficient
    rc = 1.0 / (2.0 * np.pi * cutoff_hz)
    dt = 1.0 / sample_rate
    alpha = rc / (rc + dt)
    
    # Apply filter
    filtered = np.zeros_like(audio)
    filtered[0] = audio[0]
    
    for i in range(1, len(audio)):
        filtered[i] = alpha * (filtered[i-1] + audio[i] - audio[i-1])
    
    return filtered


def bandpass_filter(
    audio: np.ndarray,
    low_cutoff: float,
    high_cutoff: float,
    sample_rate: int = SAMPLE_RATE
) -> np.ndarray:
    """Bandpass filter using sequential LP and HP."""
    return highpass_filter(lowpass_filter(audio, high_cutoff, sample_rate), low_cutoff, sample_rate)


def add_saturation(audio: np.ndarray, amount: float = 0.3) -> np.ndarray:
    """Add soft saturation/warmth to audio."""
    # Soft clipping using tanh
    return np.tanh(audio * (1 + amount * 2)) / np.tanh(1 + amount * 2)


def mix_audio(*tracks: np.ndarray, levels: Optional[List[float]] = None) -> np.ndarray:
    """Mix multiple audio tracks together."""
    if not tracks:
        return np.array([])
    
    # Get max length
    max_len = max(len(t) for t in tracks)
    
    # Pad and mix
    if levels is None:
        levels = [1.0] * len(tracks)
    
    mixed = np.zeros(max_len)
    for track, level in zip(tracks, levels):
        padded = np.zeros(max_len)
        padded[:len(track)] = track
        mixed += padded * level
    
    return mixed


# =============================================================================
# DRUM SYNTHESIS
# =============================================================================

def generate_808_kick(
    duration: float = 0.8,
    pitch_start_hz: float = 150,
    pitch_end_hz: float = 40,
    pitch_decay: float = 0.15,
    sample_rate: int = SAMPLE_RATE
) -> np.ndarray:
    """
    Generate 808-style kick/bass with pitch envelope.
    
    The 808 kick is characterized by:
    - Sine wave oscillator
    - Rapid pitch decay from ~150Hz to ~40Hz
    - Long sustain at low frequency
    """
    num_samples = int(duration * sample_rate)
    t = np.arange(num_samples) / sample_rate
    
    # Pitch envelope (exponential decay)
    pitch_env = pitch_end_hz + (pitch_start_hz - pitch_end_hz) * np.exp(-t / pitch_decay)
    
    # Generate phase from instantaneous frequency
    phase = 2 * np.pi * np.cumsum(pitch_env) / sample_rate
    
    # Sine wave with pitch envelope
    audio = np.sin(phase)
    
    # Amplitude envelope
    attack_samples = int(0.002 * sample_rate)  # 2ms attack
    decay_samples = int(0.05 * sample_rate)    # 50ms decay to sustain
    sustain_level = 0.7
    release_samples = int(0.3 * sample_rate)   # 300ms release
    sustain_samples = num_samples - attack_samples - decay_samples - release_samples
    
    audio = apply_envelope(audio, attack_samples, decay_samples, sustain_level, release_samples, sustain_samples)
    
    # Add subtle saturation for warmth
    audio = add_saturation(audio, 0.2)
    
    return normalize_audio(audio, 0.9)


def generate_kick(
    duration: float = 0.3,
    pitch_start_hz: float = 200,
    pitch_end_hz: float = 50,
    sample_rate: int = SAMPLE_RATE
) -> np.ndarray:
    """Generate punchy kick drum (shorter than 808)."""
    num_samples = int(duration * sample_rate)
    t = np.arange(num_samples) / sample_rate
    
    # Fast pitch decay
    pitch_env = pitch_end_hz + (pitch_start_hz - pitch_end_hz) * np.exp(-t / 0.03)
    phase = 2 * np.pi * np.cumsum(pitch_env) / sample_rate
    audio = np.sin(phase)
    
    # Fast decay envelope
    env = np.exp(-t / 0.08)
    audio = audio * env
    
    # Add click transient
    click_samples = int(0.003 * sample_rate)
    click = np.random.randn(click_samples) * 0.3
    click = click * np.exp(-np.arange(click_samples) / (click_samples * 0.3))
    click = lowpass_filter(click, 3000, sample_rate)
    
    audio[:click_samples] += click
    
    return normalize_audio(audio, 0.9)


def generate_snare(
    duration: float = 0.25,
    tone_freq: float = 200,
    noise_amount: float = 0.7,
    sample_rate: int = SAMPLE_RATE
) -> np.ndarray:
    """
    Generate snare drum.
    
    Combination of:
    - Pitched body (sine wave)
    - Noise burst (snare wires)
    """
    num_samples = int(duration * sample_rate)
    t = np.arange(num_samples) / sample_rate
    
    # Body: pitched sine with fast decay
    body = np.sin(2 * np.pi * tone_freq * t)
    body_env = np.exp(-t / 0.04)
    body = body * body_env * (1 - noise_amount)
    
    # Noise: filtered white noise
    noise = np.random.randn(num_samples)
    noise = bandpass_filter(noise, 500, 8000, sample_rate)
    noise_env = np.exp(-t / 0.08)
    noise = noise * noise_env * noise_amount
    
    audio = body + noise
    
    return normalize_audio(audio, 0.85)


def generate_clap(
    duration: float = 0.3,
    sample_rate: int = SAMPLE_RATE
) -> np.ndarray:
    """
    Generate handclap sound.
    
    Multiple offset noise bursts for natural clap feel.
    """
    num_samples = int(duration * sample_rate)
    audio = np.zeros(num_samples)
    
    # Multiple clap layers (slight timing offsets)
    num_layers = 4
    layer_offsets = [0, 0.01, 0.015, 0.02]  # seconds
    
    for i, offset in enumerate(layer_offsets):
        offset_samples = int(offset * sample_rate)
        layer_len = num_samples - offset_samples
        
        if layer_len > 0:
            t = np.arange(layer_len) / sample_rate
            
            # Bandpassed noise
            layer = np.random.randn(layer_len)
            layer = bandpass_filter(layer, 800, 5000, sample_rate)
            
            # Envelope
            layer_env = np.exp(-t / (0.05 + i * 0.02))
            layer = layer * layer_env * (1.0 - i * 0.15)
            
            audio[offset_samples:offset_samples + layer_len] += layer
    
    # Add reverb tail (simple filtered noise)
    tail_len = int(0.15 * sample_rate)
    tail = np.random.randn(tail_len) * 0.1
    tail = lowpass_filter(tail, 3000, sample_rate)
    tail_env = np.exp(-np.arange(tail_len) / (0.08 * sample_rate))
    tail = tail * tail_env
    
    audio[-tail_len:] += tail
    
    return normalize_audio(audio, 0.85)


def generate_hihat(
    duration: float = 0.1,
    is_open: bool = False,
    sample_rate: int = SAMPLE_RATE
) -> np.ndarray:
    """
    Generate hi-hat sound.
    
    Args:
        is_open: If True, generate open hi-hat (longer decay)
    """
    if is_open:
        duration = 0.4
    
    num_samples = int(duration * sample_rate)
    t = np.arange(num_samples) / sample_rate
    
    # High-frequency filtered noise
    noise = np.random.randn(num_samples)
    noise = highpass_filter(noise, 6000, sample_rate)
    
    # Add some metallic character with band-limited noise
    metallic = np.random.randn(num_samples)
    metallic = bandpass_filter(metallic, 8000, 12000, sample_rate)
    
    audio = noise * 0.7 + metallic * 0.3
    
    # Envelope
    decay_time = 0.3 if is_open else 0.03
    env = np.exp(-t / decay_time)
    audio = audio * env
    
    return normalize_audio(audio, 0.7)


def generate_rim(
    duration: float = 0.1,
    sample_rate: int = SAMPLE_RATE
) -> np.ndarray:
    """Generate rimshot/sidestick sound."""
    num_samples = int(duration * sample_rate)
    t = np.arange(num_samples) / sample_rate
    
    # High pitched click
    click_freq = 1200
    click = np.sin(2 * np.pi * click_freq * t)
    click_env = np.exp(-t / 0.01)
    
    # Noise component
    noise = np.random.randn(num_samples) * 0.3
    noise = bandpass_filter(noise, 1000, 5000, sample_rate)
    noise_env = np.exp(-t / 0.02)
    
    audio = click * click_env + noise * noise_env
    
    return normalize_audio(audio, 0.8)


# =============================================================================
# TEXTURE SYNTHESIS
# =============================================================================

def generate_vinyl_crackle(
    duration: float,
    density: float = 0.3,
    sample_rate: int = SAMPLE_RATE
) -> np.ndarray:
    """
    Generate vinyl crackle texture.
    
    Combination of:
    - Random impulses (pops)
    - Low-level continuous noise (surface noise)
    """
    num_samples = int(duration * sample_rate)
    
    # Surface noise (low-level filtered noise)
    surface = np.random.randn(num_samples) * 0.02
    surface = bandpass_filter(surface, 200, 4000, sample_rate)
    
    # Pops and crackles (sparse impulses)
    num_pops = int(duration * 5 * density)  # ~5 pops per second at full density
    pops = np.zeros(num_samples)
    
    for _ in range(num_pops):
        pos = np.random.randint(0, num_samples)
        pop_len = np.random.randint(10, 50)
        
        if pos + pop_len < num_samples:
            # Create impulse
            impulse = np.random.randn(pop_len)
            impulse = impulse * np.exp(-np.arange(pop_len) / (pop_len * 0.3))
            impulse = lowpass_filter(impulse, 5000, sample_rate)
            
            amplitude = np.random.uniform(0.05, 0.2)
            pops[pos:pos + pop_len] += impulse * amplitude
    
    audio = surface + pops
    
    return audio  # Don't normalize - keep at low level


def generate_rain(
    duration: float,
    intensity: float = 0.5,
    sample_rate: int = SAMPLE_RATE
) -> np.ndarray:
    """
    Generate rain ambience.
    
    Filtered noise with varying intensity.
    """
    num_samples = int(duration * sample_rate)
    
    # Base rain (filtered noise)
    rain = np.random.randn(num_samples)
    rain = bandpass_filter(rain, 400, 8000, sample_rate)
    
    # Add some low-frequency rumble
    rumble = np.random.randn(num_samples) * 0.2
    rumble = lowpass_filter(rumble, 150, sample_rate)
    
    # Modulate intensity slowly
    mod_freq = 0.1  # Very slow modulation
    t = np.arange(num_samples) / sample_rate
    intensity_mod = 0.7 + 0.3 * np.sin(2 * np.pi * mod_freq * t)
    
    audio = (rain + rumble) * intensity_mod * intensity * 0.3
    
    return audio


def generate_tape_hiss(
    duration: float,
    level: float = 0.1,
    sample_rate: int = SAMPLE_RATE
) -> np.ndarray:
    """Generate tape hiss texture."""
    num_samples = int(duration * sample_rate)
    
    # High-frequency biased noise
    hiss = np.random.randn(num_samples)
    hiss = highpass_filter(hiss, 2000, sample_rate)
    hiss = lowpass_filter(hiss, 12000, sample_rate)
    
    return hiss * level


# =============================================================================
# MELODIC SYNTHESIS
# =============================================================================

def generate_sine_tone(
    frequency: float,
    duration: float,
    sample_rate: int = SAMPLE_RATE
) -> np.ndarray:
    """Generate pure sine tone."""
    num_samples = int(duration * sample_rate)
    t = np.arange(num_samples) / sample_rate
    return np.sin(2 * np.pi * frequency * t)


def generate_fm_pluck(
    frequency: float,
    duration: float = 0.5,
    mod_ratio: float = 2.0,
    mod_depth: float = 3.0,
    sample_rate: int = SAMPLE_RATE
) -> np.ndarray:
    """
    Generate FM synthesis pluck sound.
    
    Good for Rhodes-like tones and plucked strings.
    """
    num_samples = int(duration * sample_rate)
    t = np.arange(num_samples) / sample_rate
    
    # Modulator with decaying depth
    mod_freq = frequency * mod_ratio
    mod_env = np.exp(-t / 0.1) * mod_depth
    modulator = np.sin(2 * np.pi * mod_freq * t) * mod_env
    
    # Carrier
    carrier = np.sin(2 * np.pi * frequency * t + modulator)
    
    # Amplitude envelope
    attack = int(0.005 * sample_rate)
    decay = int(0.1 * sample_rate)
    carrier = apply_envelope(carrier, attack, decay, 0.3, num_samples - attack - decay)
    
    return normalize_audio(carrier, 0.7)


def generate_pad_tone(
    frequency: float,
    duration: float,
    sample_rate: int = SAMPLE_RATE
) -> np.ndarray:
    """Generate warm pad tone with multiple detuned oscillators."""
    num_samples = int(duration * sample_rate)
    t = np.arange(num_samples) / sample_rate
    
    # Multiple detuned oscillators
    detune_cents = [-7, -3, 0, 3, 7]
    audio = np.zeros(num_samples)
    
    for cents in detune_cents:
        detune_ratio = 2 ** (cents / 1200)
        freq = frequency * detune_ratio
        audio += np.sin(2 * np.pi * freq * t) * 0.2
    
    # Soft envelope
    attack = int(0.3 * sample_rate)
    release = int(0.5 * sample_rate)
    audio = apply_envelope(audio, attack, 0, 1.0, release, num_samples - attack - release)
    
    # Filter for warmth
    audio = lowpass_filter(audio, 3000, sample_rate)
    
    return normalize_audio(audio, 0.7)


# =============================================================================
# FILE I/O
# =============================================================================

def save_wav(
    audio: np.ndarray,
    filepath: str,
    sample_rate: int = SAMPLE_RATE,
    stereo: bool = False
) -> bool:
    """
    Save audio to WAV file.
    
    Uses soundfile if available, falls back to wave module.
    """
    # Ensure directory exists
    os.makedirs(os.path.dirname(filepath) if os.path.dirname(filepath) else '.', exist_ok=True)
    
    # Convert to int16
    audio_int = np.clip(audio * 32767, -32768, 32767).astype(np.int16)
    
    if stereo and len(audio_int.shape) == 1:
        # Convert mono to stereo
        audio_int = np.column_stack([audio_int, audio_int])
    
    if HAS_SOUNDFILE:
        sf.write(filepath, audio_int, sample_rate, subtype='PCM_16')
    else:
        # Fallback to wave module
        with wave.open(filepath, 'w') as wav:
            n_channels = 2 if stereo else 1
            wav.setnchannels(n_channels)
            wav.setsampwidth(2)  # 16-bit
            wav.setframerate(sample_rate)
            
            if stereo:
                wav.writeframes(audio_int.tobytes())
            else:
                wav.writeframes(audio_int.tobytes())
    
    return True


# =============================================================================
# MAIN ASSETS GENERATOR CLASS
# =============================================================================

class AssetsGenerator:
    """
    Generates all required audio assets for a project.
    
    Creates procedural samples if bundled samples aren't available.
    """
    
    def __init__(
        self,
        output_dir: str,
        sample_rate: int = SAMPLE_RATE
    ):
        self.output_dir = output_dir
        self.sample_rate = sample_rate
        
        os.makedirs(output_dir, exist_ok=True)
    
    def generate_drum_kit(self) -> Dict[str, str]:
        """
        Generate complete drum kit.
        
        Returns:
            Dict mapping drum name to file path
        """
        kit = {}
        
        # 808 kick/bass
        audio = generate_808_kick()
        path = os.path.join(self.output_dir, '808_kick.wav')
        save_wav(audio, path, self.sample_rate)
        kit['808'] = path
        
        # Punchy kick
        audio = generate_kick()
        path = os.path.join(self.output_dir, 'kick.wav')
        save_wav(audio, path, self.sample_rate)
        kit['kick'] = path
        
        # Snare
        audio = generate_snare()
        path = os.path.join(self.output_dir, 'snare.wav')
        save_wav(audio, path, self.sample_rate)
        kit['snare'] = path
        
        # Clap
        audio = generate_clap()
        path = os.path.join(self.output_dir, 'clap.wav')
        save_wav(audio, path, self.sample_rate)
        kit['clap'] = path
        
        # Closed hi-hat
        audio = generate_hihat(is_open=False)
        path = os.path.join(self.output_dir, 'hihat_closed.wav')
        save_wav(audio, path, self.sample_rate)
        kit['hihat'] = path
        
        # Open hi-hat
        audio = generate_hihat(is_open=True)
        path = os.path.join(self.output_dir, 'hihat_open.wav')
        save_wav(audio, path, self.sample_rate)
        kit['hihat_open'] = path
        
        # Rim
        audio = generate_rim()
        path = os.path.join(self.output_dir, 'rim.wav')
        save_wav(audio, path, self.sample_rate)
        kit['rim'] = path
        
        return kit
    
    def generate_textures(self, duration: float = 180.0) -> Dict[str, str]:
        """
        Generate texture/ambience samples.
        
        Args:
            duration: Length in seconds
        
        Returns:
            Dict mapping texture name to file path
        """
        textures = {}
        
        # Vinyl crackle
        audio = generate_vinyl_crackle(duration)
        path = os.path.join(self.output_dir, 'vinyl_crackle.wav')
        save_wav(audio, path, self.sample_rate, stereo=True)
        textures['vinyl'] = path
        
        # Rain
        audio = generate_rain(duration)
        path = os.path.join(self.output_dir, 'rain.wav')
        save_wav(audio, path, self.sample_rate, stereo=True)
        textures['rain'] = path
        
        # Tape hiss
        audio = generate_tape_hiss(duration)
        path = os.path.join(self.output_dir, 'tape_hiss.wav')
        save_wav(audio, path, self.sample_rate, stereo=True)
        textures['tape'] = path
        
        return textures
    
    def generate_all(self, texture_duration: float = 180.0) -> Dict[str, Dict[str, str]]:
        """Generate all assets."""
        return {
            'drums': self.generate_drum_kit(),
            'textures': self.generate_textures(texture_duration),
        }


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def ensure_samples_exist(sample_dir: str) -> Dict[str, str]:
    """
    Ensure required samples exist, generating if needed.
    
    Returns:
        Dict mapping sample name to file path
    """
    generator = AssetsGenerator(sample_dir)
    
    # Check if samples already exist
    required = ['808_kick.wav', 'kick.wav', 'snare.wav', 'clap.wav', 'hihat_closed.wav']
    all_exist = all(
        os.path.exists(os.path.join(sample_dir, f)) 
        for f in required
    )
    
    if all_exist:
        # Return paths to existing samples
        samples = {}
        for f in required:
            name = f.replace('.wav', '')
            samples[name] = os.path.join(sample_dir, f)
        return samples
    
    # Generate samples
    return generator.generate_drum_kit()


if __name__ == '__main__':
    # Test generation
    test_dir = './test_assets'
    generator = AssetsGenerator(test_dir)
    
    print("Generating drum kit...")
    drums = generator.generate_drum_kit()
    for name, path in drums.items():
        print(f"  {name}: {path}")
    
    print("\nGenerating textures (10s test)...")
    textures = generator.generate_textures(10.0)
    for name, path in textures.items():
        print(f"  {name}: {path}")
    
    print("\nDone!")
