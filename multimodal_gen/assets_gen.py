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
# WAVEFORM TYPES
# =============================================================================

class WaveformType(Enum):
    """Supported waveform types for hybrid synthesis."""
    SINE = "sine"
    TRIANGLE = "triangle"
    SQUARE = "square"
    SAWTOOTH = "sawtooth"
    PULSE = "pulse"


@dataclass
class ADSRParameters:
    """ADSR envelope parameters for natural musical shape."""
    attack_ms: float = 10.0      # Attack time in milliseconds
    decay_ms: float = 100.0      # Decay time in milliseconds
    sustain_level: float = 0.7   # Sustain level (0-1)
    release_ms: float = 200.0    # Release time in milliseconds
    
    def to_samples(self, sample_rate: int = SAMPLE_RATE) -> tuple:
        """Convert time values to sample counts."""
        return (
            int(self.attack_ms * sample_rate / 1000),
            int(self.decay_ms * sample_rate / 1000),
            self.sustain_level,
            int(self.release_ms * sample_rate / 1000)
        )


@dataclass
class SynthesisParameters:
    """Complete synthesis parameters for procedural audio generation."""
    waveform: WaveformType = WaveformType.SINE
    frequency: float = 440.0
    duration_sec: float = 1.0
    adsr: ADSRParameters = None
    duty_cycle: float = 0.5  # For pulse wave (0.1-0.9)
    
    def __post_init__(self):
        if self.adsr is None:
            self.adsr = ADSRParameters()


def generate_waveform(
    waveform_type: WaveformType,
    frequency: float,
    duration: float,
    duty_cycle: float = 0.5,
    sample_rate: int = SAMPLE_RATE
) -> np.ndarray:
    """
    Generate basic waveform for procedural synthesis.
    
    Args:
        waveform_type: Type of waveform (sine, triangle, square, etc.)
        frequency: Frequency in Hz
        duration: Duration in seconds
        duty_cycle: Duty cycle for pulse wave (0.2 = thin, 0.5 = square)
        sample_rate: Sample rate
        
    Returns:
        Generated waveform as numpy array
    """
    num_samples = int(duration * sample_rate)
    t = np.arange(num_samples) / sample_rate
    
    if waveform_type == WaveformType.SINE:
        # Sine wave: smooth, warm tone
        audio = np.sin(2 * np.pi * frequency * t)
    
    elif waveform_type == WaveformType.TRIANGLE:
        # Triangle wave: softer than square, more harmonic content than sine
        phase = (frequency * t) % 1.0
        audio = 2 * np.abs(2 * phase - 1) - 1
    
    elif waveform_type == WaveformType.SQUARE:
        # Square wave: harsh, hollow tone (50% duty cycle)
        audio = np.sign(np.sin(2 * np.pi * frequency * t))
    
    elif waveform_type == WaveformType.SAWTOOTH:
        # Sawtooth wave: bright, buzzy tone
        phase = (frequency * t) % 1.0
        audio = 2 * phase - 1
    
    elif waveform_type == WaveformType.PULSE:
        # Pulse wave: variable duty cycle (thin to square)
        # duty_cycle: 0.2 = thin pulse, 0.5 = square wave
        phase = (frequency * t) % 1.0
        audio = np.where(phase < duty_cycle, 1.0, -1.0)
    
    else:
        # Default to sine
        audio = np.sin(2 * np.pi * frequency * t)
    
    return audio


def generate_tone_with_adsr(
    params: SynthesisParameters,
    sample_rate: int = SAMPLE_RATE
) -> np.ndarray:
    """
    Generate a tone with specified waveform and ADSR envelope.
    
    This is the main function for procedural synthesis fallback when
    samples are missing.
    
    Args:
        params: Complete synthesis parameters
        sample_rate: Sample rate
        
    Returns:
        Generated audio with envelope applied
    """
    # Generate base waveform
    audio = generate_waveform(
        params.waveform,
        params.frequency,
        params.duration_sec,
        params.duty_cycle,
        sample_rate
    )
    
    # Apply ADSR envelope
    attack_samples, decay_samples, sustain_level, release_samples = params.adsr.to_samples(sample_rate)
    
    # Calculate sustain duration
    total_samples = len(audio)
    sustain_samples = max(0, total_samples - attack_samples - decay_samples - release_samples)
    
    audio = apply_envelope(
        audio,
        attack_samples,
        decay_samples,
        sustain_level,
        release_samples,
        sustain_samples
    )
    
    return audio


def generate_hybrid_sound(
    sound_type: str,
    frequency: float = 440.0,
    duration: float = 0.5,
    adsr: Optional[ADSRParameters] = None,
    sample_rate: int = SAMPLE_RATE
) -> np.ndarray:
    """
    Generate hybrid procedural sound based on type.
    
    Automatically selects appropriate waveform and parameters for
    different sound types (kick, snare, bass, etc.).
    
    Args:
        sound_type: Type of sound ('kick', 'snare', 'bass', 'pad', 'pluck')
        frequency: Base frequency in Hz
        duration: Duration in seconds
        adsr: Custom ADSR parameters (optional)
        sample_rate: Sample rate
        
    Returns:
        Generated audio
    """
    if sound_type == 'kick':
        # Kick: sine with fast pitch decay
        params = SynthesisParameters(
            waveform=WaveformType.SINE,
            frequency=frequency,
            duration_sec=duration,
            adsr=adsr or ADSRParameters(
                attack_ms=1.0,
                decay_ms=80.0,
                sustain_level=0.0,
                release_ms=0.0
            )
        )
        return generate_tone_with_adsr(params, sample_rate)
    
    elif sound_type == 'bass':
        # Bass: sine or triangle, medium sustain
        params = SynthesisParameters(
            waveform=WaveformType.TRIANGLE,
            frequency=frequency,
            duration_sec=duration,
            adsr=adsr or ADSRParameters(
                attack_ms=5.0,
                decay_ms=50.0,
                sustain_level=0.8,
                release_ms=100.0
            )
        )
        return generate_tone_with_adsr(params, sample_rate)
    
    elif sound_type == 'pad':
        # Pad: multiple detuned sine waves for warmth
        params = SynthesisParameters(
            waveform=WaveformType.SINE,
            frequency=frequency,
            duration_sec=duration,
            adsr=adsr or ADSRParameters(
                attack_ms=200.0,
                decay_ms=100.0,
                sustain_level=0.9,
                release_ms=500.0
            )
        )
        # Generate detuned layers
        layer1 = generate_tone_with_adsr(params, sample_rate)
        params.frequency = frequency * 1.005  # Slightly sharp
        layer2 = generate_tone_with_adsr(params, sample_rate)
        params.frequency = frequency * 0.995  # Slightly flat
        layer3 = generate_tone_with_adsr(params, sample_rate)
        
        # Mix layers
        return (layer1 + layer2 + layer3) / 3.0
    
    elif sound_type == 'pluck':
        # Pluck: triangle with fast decay
        params = SynthesisParameters(
            waveform=WaveformType.TRIANGLE,
            frequency=frequency,
            duration_sec=duration,
            adsr=adsr or ADSRParameters(
                attack_ms=1.0,
                decay_ms=200.0,
                sustain_level=0.2,
                release_ms=100.0
            )
        )
        return generate_tone_with_adsr(params, sample_rate)
    
    elif sound_type == 'lead':
        # Lead: pulse or sawtooth, bright
        params = SynthesisParameters(
            waveform=WaveformType.PULSE,
            frequency=frequency,
            duration_sec=duration,
            duty_cycle=0.3,  # Thin pulse for bright tone
            adsr=adsr or ADSRParameters(
                attack_ms=10.0,
                decay_ms=100.0,
                sustain_level=0.7,
                release_ms=150.0
            )
        )
        return generate_tone_with_adsr(params, sample_rate)
    
    else:
        # Default: sine wave
        params = SynthesisParameters(
            waveform=WaveformType.SINE,
            frequency=frequency,
            duration_sec=duration,
            adsr=adsr or ADSRParameters()
        )
        return generate_tone_with_adsr(params, sample_rate)


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


def generate_piano_tone(
    frequency: float,
    duration: float = 0.6,
    velocity: float = 0.8,
    sample_rate: int = SAMPLE_RATE
) -> np.ndarray:
    """Generate a more piano-like tone (procedural fallback).

    This is intentionally lightweight (numpy only) but aims to be less "toyish"
    than FM plucks by modeling:
    - Fast hammer transient (band-limited noise)
    - Additive harmonic stack with faster decay for higher partials
    - Slight inharmonicity and mild detune (chorus-like)
    """
    num_samples = max(1, int(duration * sample_rate))
    t = np.arange(num_samples) / sample_rate

    # Harmonic stack with mild inharmonicity (piano strings)
    inharm = 0.00015 + (min(frequency, 1000) / 1000.0) * 0.00015
    audio = np.zeros(num_samples, dtype=np.float64)

    num_partials = 14
    base_decay = 0.9 + 0.6 * (1.0 - min(frequency, 1000) / 1000.0)  # lower notes sustain longer

    # Two slightly detuned layers (piano unison strings)
    detunes = [1.0, 1.003]
    for detune in detunes:
        layer = np.zeros(num_samples, dtype=np.float64)
        for n in range(1, num_partials + 1):
            # Inharmonic partial frequency
            partial_freq = frequency * detune * (n + inharm * (n ** 2))
            if partial_freq > sample_rate / 2 - 200:
                break

            amp = (1.0 / n) ** 1.15
            # Higher partials decay faster
            decay = base_decay / (n ** 0.65)
            env = np.exp(-t / max(0.05, decay))
            layer += amp * np.sin(2 * np.pi * partial_freq * t) * env

        audio += layer

    audio /= len(detunes)

    # Hammer noise transient (first ~12ms)
    transient_len = min(num_samples, int(0.012 * sample_rate))
    if transient_len > 8:
        noise = np.random.randn(transient_len)
        noise = bandpass_filter(noise, 900, 8000, sample_rate)
        noise_env = np.exp(-np.arange(transient_len) / (0.004 * sample_rate))
        noise = noise * noise_env * 0.12
        audio[:transient_len] += noise

    # Envelope: fast attack, gentle release
    attack = int(0.003 * sample_rate)
    decay = int(0.18 * sample_rate)
    sustain_level = 0.25
    release = int(0.22 * sample_rate)
    sustain_samples = max(0, num_samples - attack - decay - release)
    audio = apply_envelope(audio, attack, decay, sustain_level, release, sustain_samples)

    # Warmth + gentle saturation
    audio = lowpass_filter(audio, 9000, sample_rate)
    audio = add_saturation(audio, 0.12)

    # Velocity scaling and normalization
    audio = normalize_audio(audio, target_peak=0.85) * float(np.clip(velocity, 0.0, 1.0))
    return audio.astype(np.float32)


def generate_lead_tone(
    frequency: float,
    duration: float = 0.4,
    velocity: float = 0.8,
    sample_rate: int = SAMPLE_RATE
) -> np.ndarray:
    """Generate a trap-friendly synth lead (procedural fallback).

    Designed to avoid the "toy xylophone" vibe when MIDI uses GM lead programs.
    Pulse/saw hybrid with mild vibrato, short attack, and controlled brightness.
    """
    num_samples = max(1, int(duration * sample_rate))
    t = np.arange(num_samples) / sample_rate

    # Mild vibrato
    vib_rate = 5.5
    vib_depth = 0.004  # ~0.4%
    inst_freq = frequency * (1.0 + vib_depth * np.sin(2 * np.pi * vib_rate * t))
    phase = 2 * np.pi * np.cumsum(inst_freq) / sample_rate

    # Pulse + saw-ish harmonic stack
    pulse = np.sign(np.sin(phase))
    saw = np.zeros(num_samples, dtype=np.float64)
    for n in range(1, 10):
        saw += (1.0 / n) * np.sin(phase * n)
    saw *= 0.55

    audio = 0.55 * pulse + 0.45 * saw

    # Envelope: fast attack, medium decay, short release
    attack = int(0.005 * sample_rate)
    decay = int(0.08 * sample_rate)
    sustain_level = 0.55
    release = int(0.10 * sample_rate)
    sustain_samples = max(0, num_samples - attack - decay - release)
    audio = apply_envelope(audio, attack, decay, sustain_level, release, sustain_samples)

    # Tone shaping
    audio = lowpass_filter(audio, 6000, sample_rate)
    audio = highpass_filter(audio, 120, sample_rate)
    audio = add_saturation(audio, 0.18)

    audio = normalize_audio(audio, 0.85) * float(np.clip(velocity, 0.0, 1.0))
    return audio.astype(np.float32)


# =============================================================================
# ETHIOPIAN INSTRUMENT SYNTHESIS
# =============================================================================
# MASTERCLASS ETHIOPIAN INSTRUMENT SYNTHESIS
# =============================================================================
# 
# Based on deep acoustic analysis of traditional Ethiopian music and instruments.
# Key acoustic principles modeled:
#
# KRAR (ክራር) - Bowl Lyre:
#   - Karplus-Strong physical modeling for authentic plucked string
#   - Goatskin membrane body resonance (150-600Hz formants)
#   - 5-6 nylon/gut strings with sympathetic coupling
#   - Bright "twang" transient from plectrum attack
#   - Ethiopian pentatonic tuning (tizita/bati qenet)
#
# MASENQO (ማሲንቆ) - Single-String Fiddle:
#   - Stick-slip bowing dynamics (sawtooth-rich with jitter)
#   - Voice-like nasal formants (F1≈450Hz, F2≈1200Hz, F3≈2400Hz)
#   - Wide expressive vibrato (5-7Hz, up to 30 cents)
#   - Characteristic "crying" ornaments (portamento, mordents)
#   - Diamond body with goatskin resonance
#
# WASHINT (ዋሺንት) - Bamboo Flute:
#   - End-blown with strong breath noise component
#   - Hollow bamboo tube resonance
#   - Ornamental grace notes and trills
#   - Developing vibrato with air pressure modulation
#
# BEGENA (በገና) - Bass Lyre:
#   - 10-string drone instrument for religious music
#   - Characteristic "buzz" from leather string wrappings
#   - Deep, meditative sustained tones
#   - Complex sympathetic resonance network
# =============================================================================


def _karplus_strong_pluck(
    frequency: float,
    duration: float,
    brightness: float = 0.5,
    damping: float = 0.996,
    sample_rate: int = SAMPLE_RATE
) -> np.ndarray:
    """
    Karplus-Strong plucked string synthesis.
    
    Physical modeling algorithm that simulates a vibrating string
    by filtering a noise burst through a delay line with feedback.
    This creates the natural overtone structure of plucked strings.
    
    Args:
        frequency: Fundamental frequency in Hz
        duration: Duration in seconds
        brightness: 0-1, higher = brighter/more high harmonics
        damping: Feedback coefficient, higher = longer sustain
        sample_rate: Audio sample rate
    
    Returns:
        Numpy array of synthesized plucked string audio
    """
    num_samples = int(duration * sample_rate)
    
    # Delay line length determines fundamental frequency
    delay_length = int(sample_rate / frequency)
    if delay_length < 2:
        delay_length = 2
    
    # Initialize delay line with filtered noise burst (the "pluck")
    # Brightness controls the initial noise spectrum
    noise = np.random.randn(delay_length)
    
    # Apply brightness filter to initial excitation
    if brightness < 0.5:
        # Low brightness: more lowpass filtering
        for _ in range(int((0.5 - brightness) * 6)):
            noise = np.convolve(noise, [0.25, 0.5, 0.25], mode='same')
    else:
        # High brightness: add some high-frequency emphasis
        emphasis = (brightness - 0.5) * 0.3
        noise = noise + emphasis * np.diff(np.concatenate([[0], noise]))
    
    # Output buffer
    output = np.zeros(num_samples)
    output[:delay_length] = noise
    
    # Karplus-Strong loop with averaging lowpass filter
    # The averaging creates natural harmonic decay (higher harmonics fade faster)
    delay_line = noise.copy()
    write_pos = 0
    
    for i in range(delay_length, num_samples):
        # Read from delay line
        read_pos = (write_pos + 1) % delay_length
        next_pos = (read_pos + 1) % delay_length
        
        # Two-point averaging filter (simulates string damping)
        new_sample = damping * 0.5 * (delay_line[read_pos] + delay_line[next_pos])
        
        # Write to output and delay line
        output[i] = new_sample
        delay_line[write_pos] = new_sample
        write_pos = (write_pos + 1) % delay_length
    
    return output


def _generate_bow_excitation(
    frequency: float,
    duration: float,
    bow_pressure: float = 0.7,
    bow_speed: float = 0.5,
    sample_rate: int = SAMPLE_RATE
) -> np.ndarray:
    """
    Generate bowed string excitation signal.
    
    Models the stick-slip friction of a bow on a string, creating
    the characteristic sawtooth-rich waveform with natural jitter.
    
    The Masenqo uses a horsehair bow on a horsehair string, creating
    a particularly rough, expressive tone.
    
    Args:
        frequency: Fundamental frequency
        duration: Duration in seconds
        bow_pressure: 0-1, affects harmonic content and noise
        bow_speed: 0-1, affects fundamental stability
    """
    num_samples = int(duration * sample_rate)
    t = np.arange(num_samples) / sample_rate
    
    audio = np.zeros(num_samples)
    
    # Generate sawtooth with micro-variations (bow jitter)
    # Real bowing creates pitch instability at stick-slip transitions
    jitter_amount = 0.003 * (1.2 - bow_speed)  # More jitter at low bow speed
    jitter = np.cumsum(np.random.randn(num_samples)) * jitter_amount / sample_rate
    jitter = lowpass_filter(jitter, 50, sample_rate)  # Slow jitter
    
    phase = 2 * np.pi * frequency * (t + jitter)
    
    # Build sawtooth from harmonics with bow pressure affecting brightness
    num_harmonics = int(20 * bow_pressure) + 8
    for i in range(1, num_harmonics):
        # Sawtooth harmonic amplitudes: 1/n
        amp = 1.0 / i
        
        # Odd harmonics slightly emphasized (adds nasal quality)
        if i % 2 == 1:
            amp *= 1.15
        
        # High harmonics reduced at low bow pressure
        if i > 6:
            amp *= bow_pressure
        
        audio += amp * np.sin(phase * i)
    
    # Add stick-slip noise component (bow scratchiness)
    noise = np.random.randn(num_samples)
    
    # Filter to mid-high frequencies (bow noise character)
    noise = bandpass_simple(noise, 1200, 4500, sample_rate)
    
    # Modulate noise by bow pressure variations
    pressure_env = 1.0 + 0.2 * np.sin(2 * np.pi * 3.5 * t)  # ~3.5Hz arm movement
    noise *= pressure_env * bow_pressure * 0.08
    
    audio += noise
    
    return audio


def _apply_formant_filter(
    audio: np.ndarray,
    formants: list,
    bandwidths: list,
    gains: list,
    sample_rate: int = SAMPLE_RATE
) -> np.ndarray:
    """
    Apply formant filtering to create vocal/nasal qualities.
    
    Formants are resonant peaks that give instruments their
    characteristic "voice" - critical for masenqo's vocal quality.
    
    Args:
        audio: Input audio
        formants: List of formant center frequencies
        bandwidths: List of formant bandwidths
        gains: List of formant gains (0-1)
    """
    output = np.zeros_like(audio)
    
    for freq, bw, gain in zip(formants, bandwidths, gains):
        low = max(20, freq - bw/2)
        high = min(sample_rate/2 - 100, freq + bw/2)
        
        filtered = lowpass_filter(audio, high, sample_rate)
        filtered = highpass_filter(filtered, low, sample_rate)
        
        # Resonance boost proportional to Q
        q = freq / bw
        filtered *= gain * (1 + q * 0.1)
        output += filtered
    
    # Mix with slight original for presence
    return output * 0.7 + audio * 0.15


def _generate_ethiopian_ornament(
    frequency: float,
    ornament_type: str = 'mordent',
    sample_rate: int = SAMPLE_RATE
) -> np.ndarray:
    """
    Generate characteristic Ethiopian melodic ornaments.
    
    Ethiopian music features distinctive ornaments:
    - Mordent: Quick alternation with upper neighbor
    - Trill: Rapid alternation (faster than mordent)
    - Slide: Portamento between notes
    - Grace: Quick approach from below
    
    Args:
        frequency: Target note frequency
        ornament_type: Type of ornament
        sample_rate: Audio sample rate
    
    Returns:
        Short audio array containing the ornament
    """
    if ornament_type == 'mordent':
        # Quick upper neighbor and back
        duration = 0.06  # 60ms
        num_samples = int(duration * sample_rate)
        t = np.arange(num_samples) / sample_rate
        
        # Two segments: upper note, then target
        mid = num_samples // 2
        upper_freq = frequency * 1.125  # ~major second up
        
        ornament = np.zeros(num_samples)
        ornament[:mid] = np.sin(2 * np.pi * upper_freq * t[:mid])
        ornament[mid:] = np.sin(2 * np.pi * frequency * t[mid:])
        
        # Quick envelope
        env = np.exp(-t / 0.03)
        return ornament * env * 0.5
        
    elif ornament_type == 'grace':
        # Quick approach from below
        duration = 0.04  # 40ms
        num_samples = int(duration * sample_rate)
        t = np.arange(num_samples) / sample_rate
        
        # Slide up from minor second below
        start_freq = frequency / 1.067  # Minor second below
        freq_curve = start_freq + (frequency - start_freq) * (t / duration) ** 0.5
        
        phase = np.cumsum(2 * np.pi * freq_curve / sample_rate)
        ornament = np.sin(phase)
        
        env = np.exp(-t / 0.025)
        return ornament * env * 0.4
        
    elif ornament_type == 'slide':
        # Longer portamento slide
        duration = 0.08  # 80ms
        num_samples = int(duration * sample_rate)
        t = np.arange(num_samples) / sample_rate
        
        # Start from a third below
        start_freq = frequency / 1.2
        # Exponential slide (faster at start, slows at target)
        freq_curve = start_freq * np.exp(np.log(frequency/start_freq) * (t/duration)**0.6)
        
        phase = np.cumsum(2 * np.pi * freq_curve / sample_rate)
        return np.sin(phase) * 0.5
    
    else:  # trill
        duration = 0.1  # 100ms
        num_samples = int(duration * sample_rate)
        t = np.arange(num_samples) / sample_rate
        
        # Rapid alternation ~12Hz
        trill_rate = 12
        upper_freq = frequency * 1.125
        
        # Frequency oscillates between note and upper neighbor
        freq_mod = frequency + (upper_freq - frequency) * 0.5 * (1 + np.sin(2 * np.pi * trill_rate * t))
        
        phase = np.cumsum(2 * np.pi * freq_mod / sample_rate)
        ornament = np.sin(phase)
        
        env = np.exp(-t / 0.08)
        return ornament * env * 0.4


def _apply_body_resonance(
    audio: np.ndarray,
    resonance_freqs: list,
    resonance_qs: list,
    sample_rate: int = SAMPLE_RATE
) -> np.ndarray:
    """
    Apply body resonance simulation using parallel bandpass filters.
    
    Simulates the acoustic resonance of instrument bodies (wood, skin, gourd).
    Enhanced version with proper resonator modeling.
    """
    if len(resonance_freqs) != len(resonance_qs):
        return audio
    
    resonant = np.zeros_like(audio)
    
    for freq, q in zip(resonance_freqs, resonance_qs):
        # Calculate bandwidth from Q factor
        bandwidth = freq / q
        low = max(20, freq - bandwidth / 2)
        high = min(sample_rate / 2 - 100, freq + bandwidth / 2)
        
        # Bandpass using cascade of low and high pass
        filtered = lowpass_filter(audio, high, sample_rate)
        filtered = highpass_filter(filtered, low, sample_rate)
        
        # Resonance boost proportional to Q (higher Q = more pronounced peak)
        boost = 1.0 + (q - 5) * 0.15  # Baseline Q of 5
        resonant += filtered * boost
    
    # Mix: original provides attack/transients, resonant adds body color
    return audio * 0.5 + resonant * 0.5


def _generate_pluck_noise(
    duration_samples: int,
    brightness: float = 0.7,
    sample_rate: int = SAMPLE_RATE
) -> np.ndarray:
    """
    Generate pluck/attack noise transient.
    
    The characteristic "thwack" of plucking a string.
    Enhanced with body knock simulation.
    """
    noise = np.random.randn(duration_samples)
    
    # Shape the noise - very fast decay
    t = np.arange(duration_samples) / sample_rate
    envelope = np.exp(-t / 0.003)  # 3ms decay
    noise *= envelope
    
    # Filter based on brightness
    cutoff = 2000 + brightness * 6000  # 2-8 kHz
    noise = lowpass_filter(noise, cutoff, sample_rate)
    noise = highpass_filter(noise, 500, sample_rate)
    
    # Add body "knock" component (low thump from exciting the body)
    knock_samples = min(int(0.015 * sample_rate), duration_samples)
    knock = np.sin(2 * np.pi * 180 * t[:knock_samples])  # Low frequency body mode
    knock *= np.exp(-t[:knock_samples] / 0.008)
    
    knock_full = np.zeros(duration_samples)
    knock_full[:knock_samples] = knock * 0.3
    
    return noise * 0.12 + knock_full


def _generate_sympathetic_strings(
    frequency: float,
    duration: float,
    num_strings: int = 5,
    tuning: str = 'tizita',
    sample_rate: int = SAMPLE_RATE
) -> np.ndarray:
    """
    Generate sympathetic string resonance with authentic Ethiopian tuning.
    
    When one string is played, nearby strings vibrate sympathetically,
    creating the characteristic shimmer of lyres and harps.
    
    Uses authentic Ethiopian scale tunings (qenet).
    
    Args:
        frequency: Played note frequency
        duration: Duration in seconds
        num_strings: Number of sympathetic strings (5-6 for krar, 10 for begena)
        tuning: Ethiopian scale tuning - 'tizita', 'bati', 'ambassel', 'anchihoye'
    """
    num_samples = int(duration * sample_rate)
    t = np.arange(num_samples) / sample_rate
    
    # Ethiopian pentatonic scale ratios (qenet tuning systems)
    tunings = {
        # Tizita Major - joyful, celebratory (similar to major pentatonic)
        'tizita': [1.0, 9/8, 5/4, 3/2, 27/16],  # C D E G A
        
        # Tizita Minor - melancholic (like minor pentatonic with b3)
        'tizita_minor': [1.0, 9/8, 6/5, 3/2, 8/5],  # C D Eb G Ab
        
        # Bati Major - uplifting, used in love songs
        'bati': [1.0, 9/8, 5/4, 3/2, 5/3],  # C D E G A (slightly different 6th)
        
        # Bati Minor - sorrowful
        'bati_minor': [1.0, 9/8, 6/5, 3/2, 9/5],  # C D Eb G Bb
        
        # Ambassel - religious, contemplative (like Dorian mode)
        'ambassel': [1.0, 9/8, 6/5, 4/3, 3/2],  # C D Eb F G
        
        # Anchihoye - unique Ethiopian mode
        'anchihoye': [1.0, 9/8, 6/5, 3/2, 27/16],  # C D Eb G A
    }
    
    ratios = tunings.get(tuning, tunings['tizita'])
    
    sympathetic = np.zeros(num_samples)
    
    for i in range(min(num_strings, len(ratios) * 2)):
        # Octave folding for instruments with more than 5 strings
        octave = i // len(ratios)
        ratio_idx = i % len(ratios)
        symp_freq = frequency * ratios[ratio_idx] * (2 ** octave)
        
        # Only resonate if sympathetic string is near the played frequency
        freq_ratio = symp_freq / frequency
        # Strings resonate most when close to unison, octave, or fifth
        resonance_strength = 0
        for interval in [1.0, 2.0, 1.5, 0.5, 0.667]:  # Unison, octave, fifth
            closeness = 1.0 - min(abs(freq_ratio - interval), 0.5)
            resonance_strength = max(resonance_strength, closeness)
        
        # Amplitude based on resonance coupling
        amp = 0.06 * resonance_strength / (octave + 1)
        
        # Staggered onset (physical delay from energy transfer)
        delay_samples = int((0.015 + 0.01 * i) * sample_rate)
        
        if delay_samples < num_samples:
            # Generate resonating string using simplified Karplus-Strong
            symp_tone = np.sin(2 * np.pi * symp_freq * t)
            
            # Add slight detuning (real strings aren't perfectly in tune)
            detune = 1.0 + (np.random.randn() * 0.002)
            symp_tone2 = np.sin(2 * np.pi * symp_freq * detune * t)
            symp_tone = symp_tone * 0.7 + symp_tone2 * 0.3
            
            # Slow swell and decay (sympathetic strings build slowly)
            attack_time = 0.1 + i * 0.05
            decay_time = 0.4 + i * 0.1
            env = np.exp(-t / decay_time) * (1 - np.exp(-t / attack_time))
            symp_tone *= env * amp
            
            # Apply delay
            padded = np.zeros(num_samples)
            if delay_samples < num_samples:
                remain = num_samples - delay_samples
                padded[delay_samples:] = symp_tone[:remain]
            sympathetic += padded
    
    return sympathetic


def _generate_membrane_resonance(
    audio: np.ndarray,
    membrane_freq: float = 280,
    damping: float = 0.4,
    sample_rate: int = SAMPLE_RATE
) -> np.ndarray:
    """
    Generate goatskin/hide membrane resonance.
    
    Ethiopian lyre bodies typically use stretched goatskin over
    a wooden bowl. This creates characteristic low-mid resonance.
    
    Args:
        audio: Input audio to excite the membrane
        membrane_freq: Primary membrane resonance frequency
        damping: Membrane damping (0=ringy, 1=dead)
    """
    num_samples = len(audio)
    t = np.arange(num_samples) / sample_rate
    
    # Membrane modes (circular membrane has specific mode ratios)
    mode_ratios = [1.0, 1.59, 2.14, 2.30, 2.65, 2.92]  # Bessel function zeros
    
    membrane_response = np.zeros(num_samples)
    
    for i, ratio in enumerate(mode_ratios):
        mode_freq = membrane_freq * ratio
        if mode_freq > sample_rate / 2 - 100:
            continue
            
        # Extract excitation energy at this frequency
        bw = 60  # Bandwidth
        excitation = bandpass_simple(audio, mode_freq - bw, mode_freq + bw, sample_rate)
        
        # Mode amplitude decreases for higher modes
        mode_amp = 0.15 / (i + 1)
        
        # Each mode rings with different decay
        mode_decay = (1 - damping) * 0.3 / (i + 1)
        
        # Simple decaying sinusoid excited by input
        # Envelope follows excitation energy with mode decay
        envelope = np.abs(excitation) + 0.001
        envelope = lowpass_filter(envelope, 30, sample_rate)  # Smooth
        envelope *= np.exp(-t / mode_decay)
        
        mode_sound = np.sin(2 * np.pi * mode_freq * t) * envelope * mode_amp
        membrane_response += mode_sound
    
    return audio + membrane_response * 0.4


def _generate_organic_imperfections(
    num_samples: int,
    frequency: float,
    sample_rate: int = SAMPLE_RATE
) -> tuple:
    """
    Generate organic micro-variations that make synthesis sound like a real acoustic instrument.
    
    Real acoustic instruments NEVER produce perfectly stable frequencies or amplitudes.
    This function generates the subtle imperfections that make synthesis organic.
    
    Returns:
        (pitch_drift, amp_flutter, micro_timing) arrays
    """
    t = np.arange(num_samples) / sample_rate
    
    # === PITCH DRIFT (slow, organic wandering) ===
    # Real strings slowly drift in pitch as they warm up, as temperature changes, etc.
    # Very slow (0.5-2Hz) subtle movement ±3-8 cents
    drift_cents = 4 + np.random.rand() * 4  # 4-8 cents total drift
    drift_rate = 0.3 + np.random.rand() * 0.7  # 0.3-1.0 Hz
    
    # Brownian-style drift (cumulative random walk)
    random_walk = np.cumsum(np.random.randn(num_samples) * 0.0001)
    random_walk = lowpass_filter(random_walk, 2, sample_rate)  # Very slow changes
    random_walk = random_walk / (np.std(random_walk) + 0.001) * (drift_cents / 1200)  # Scale to cents
    
    # Add slower sinusoidal component
    slow_drift = 0.003 * np.sin(2 * np.pi * drift_rate * t)
    
    pitch_drift = random_walk + slow_drift
    
    # === AMPLITUDE FLUTTER (tremolo from body vibration) ===
    # When you pluck a string, the whole body vibrates, causing amplitude modulation
    flutter_rate = 4 + np.random.rand() * 3  # 4-7 Hz
    flutter_depth = 0.04 + np.random.rand() * 0.06  # 4-10% modulation
    
    # Irregular flutter (not pure sine)
    flutter = flutter_depth * (
        np.sin(2 * np.pi * flutter_rate * t) + 
        0.3 * np.sin(2 * np.pi * flutter_rate * 1.5 * t + np.random.rand() * np.pi)
    )
    flutter *= np.exp(-t / 0.4)  # Flutter dies out as body settles
    amp_flutter = 1.0 + flutter
    
    # === MICRO-TIMING (attack jitter) ===
    # Human performance has tiny timing variations
    # This creates slight phase modulation in the attack
    attack_jitter = np.zeros(num_samples)
    jitter_samples = int(0.02 * sample_rate)  # First 20ms
    if jitter_samples < num_samples:
        attack_jitter[:jitter_samples] = (np.random.rand() - 0.5) * 0.001
    
    return pitch_drift, amp_flutter, attack_jitter


def _generate_room_ambience(
    audio: np.ndarray,
    room_size: float = 0.3,
    dampness: float = 0.6,
    sample_rate: int = SAMPLE_RATE
) -> np.ndarray:
    """
    Add subtle room ambience to make instruments sound like they're in a physical space.
    
    Ethiopian traditional music is typically performed in small to medium rooms
    with natural acoustics (not dead studios).
    
    Args:
        audio: Input audio
        room_size: 0-1, affects early reflection delays
        dampness: 0-1, affects high frequency absorption
    """
    num_samples = len(audio)
    reverbed = np.zeros(num_samples)
    
    # Early reflections (small room)
    delays_ms = [12, 19, 27, 35, 48, 63]  # Typical small room reflections
    gains = [0.08, 0.06, 0.05, 0.04, 0.03, 0.02]
    
    for delay_ms, gain in zip(delays_ms, gains):
        delay_samples = int(delay_ms * room_size * sample_rate / 1000)
        if delay_samples < num_samples:
            delayed = np.zeros(num_samples)
            delayed[delay_samples:] = audio[:-delay_samples] if delay_samples > 0 else audio
            # Each reflection loses high frequencies
            delayed = lowpass_filter(delayed, 4000 * (1 - dampness * 0.5), sample_rate)
            reverbed += delayed * gain
    
    # Late diffuse tail (very subtle)
    tail_samples = int(0.15 * sample_rate)  # 150ms tail
    if tail_samples < num_samples:
        tail = np.zeros(num_samples)
        # Create diffuse reverb by summing many random delays
        for _ in range(8):
            delay = int(np.random.randint(50, 150) * sample_rate / 1000)
            if delay < num_samples:
                d = np.zeros(num_samples)
                d[delay:] = audio[:-delay]
                d = lowpass_filter(d, 2000, sample_rate)
                tail += d * 0.01 * np.random.rand()
        reverbed += tail * np.exp(-np.arange(num_samples) / (0.1 * sample_rate))
    
    return audio + reverbed * 0.4


def generate_krar_tone(
    frequency: float,
    duration: float = 0.5,
    velocity: float = 0.8,
    sample_rate: int = SAMPLE_RATE,
    tuning: str = 'tizita',
    add_ornament: bool = False
) -> np.ndarray:
    """
    Generate authentic Krar (ክራር) - Ethiopian bowl lyre using Karplus-Strong.
    
    PHYSICAL MODELING based on Stanford CCRMA research (Julius O. Smith III).
    
    The Karplus-Strong algorithm simulates a plucked string:
    1. Initialize delay line with filtered noise burst (the "pluck")
    2. Feed output through lowpass filter back into delay line
    3. The delay line length determines pitch, filter determines decay/timbre
    
    Extended KS features:
    - Pick-position comb filter (affects harmonic content)
    - String-damping filter (natural decay)
    - Body resonance coloring
    """
    num_samples = int(duration * sample_rate)
    
    # === KARPLUS-STRONG CORE ===
    # Delay line length = samples per period
    period_samples = int(sample_rate / frequency)
    if period_samples < 2:
        period_samples = 2
    
    # Fractional delay for precise tuning
    frac_delay = (sample_rate / frequency) - period_samples
    
    # Initialize delay line with filtered noise burst (the "pluck")
    # Use VERY soft excitation to avoid banjo twang
    noise = np.random.randn(period_samples)
    
    # Pick-position: Pluck at CENTER of string for maximum warmth
    # Center pluck (β=0.5) gives round, harp-like tone - NO twang
    pick_position = 0.45 + (1 - velocity) * 0.10  # 0.45-0.55 (center = round)
    pick_delay = max(1, int(pick_position * period_samples))
    
    # MINIMAL comb filter - we want round tone, not twangy
    if pick_delay < len(noise):
        noise_comb = noise.copy()
        noise_comb[pick_delay:] -= noise[:-pick_delay] * 0.2  # Very subtle comb
        noise = noise_comb
    
    # VERY HEAVY low-pass filtering - remove ALL twang/brightness
    # Ethiopian Krar should sound like soft harp, not banjo
    # Apply many passes of strong smoothing
    for _ in range(12):  # 12 passes for ultra-smooth
        noise = np.convolve(noise, [0.15, 0.7, 0.15], mode='same')  # Strong center-weighted smoothing
    
    # Output buffer
    output = np.zeros(num_samples)
    
    # Initialize delay line
    delay_line = noise.copy()
    
    # String damping coefficient (higher = longer sustain)
    # Real strings: 0.996-0.9995 for gut/nylon
    # Increased for longer, more audible sustain
    damping = 0.997 + velocity * 0.002  # 0.997-0.999
    
    # String stiffness (causes slight inharmonicity)
    stiffness = 0.0003
    
    # === MAIN SYNTHESIS LOOP ===
    write_pos = 0
    
    # First-order allpass for fractional delay (tuning accuracy)
    allpass_coef = (1 - frac_delay) / (1 + frac_delay)
    allpass_state = 0.0
    
    for i in range(num_samples):
        # Read from delay line (two-point averaging = lowpass)
        read_pos = (write_pos + 1) % period_samples
        next_pos = (read_pos + 1) % period_samples
        
        # Two-point averaging lowpass filter (the classic KS filter)
        # This causes higher harmonics to decay faster than fundamental
        filtered = 0.5 * (delay_line[read_pos] + delay_line[next_pos])
        
        # Apply damping
        filtered *= damping
        
        # First-order allpass for fractional delay tuning
        allpass_out = allpass_coef * filtered + allpass_state
        allpass_state = filtered - allpass_coef * allpass_out
        
        # Write to output
        output[i] = allpass_out
        
        # Write back to delay line
        delay_line[write_pos] = allpass_out
        write_pos = (write_pos + 1) % period_samples
    
    # === BODY RESONANCE (formant filtering) ===
    # Ethiopian lyre body: wooden bowl + goatskin membrane
    # Very LOW resonances for warm, round African tone
    body_output = output.copy()
    
    # Body modes - very low and warm, like African drums
    # Emphasize fundamental and low harmonics only
    for mode_freq, mode_q, mode_gain in [(90, 5, 0.25), (180, 4, 0.18), (280, 3, 0.10)]:
        mode_band = bandpass_simple(output, mode_freq * 0.75, mode_freq * 1.25, sample_rate)
        body_output += mode_band * mode_gain
    
    output = body_output
    
    # === GOATSKIN MEMBRANE - STRONG HIGH ABSORPTION ===
    # Goatskin is soft and absorbs ALL high frequencies
    # This is what makes it NOT sound like banjo (which has tight drum head)
    output = lowpass_filter(output, 1800, sample_rate)  # Very aggressive high cut
    output = lowpass_filter(output, 2200, sample_rate)  # Double filter for steep rolloff
    
    # === SYMPATHETIC STRING RESONANCE ===
    # 5-6 strings ring sympathetically - warm shimmer only
    t = np.arange(num_samples) / sample_rate
    for ratio in [1.5, 2.0]:  # Fifth and octave only
        symp_freq = frequency * ratio
        if symp_freq < 1000:  # Only very warm sympathetics
            symp_env = np.exp(-t / 0.5) * np.clip((t - 0.04) / 0.2, 0, 1)
            output += 0.012 * np.sin(2 * np.pi * symp_freq * t) * symp_env
    
    # === SOFT FINGER ATTACK ===
    # Finger plucking creates soft onset, not sharp attack
    attack_samples = int(0.015 * sample_rate)  # 15ms soft attack
    if attack_samples < num_samples:
        soft_attack = np.random.randn(attack_samples)
        for _ in range(15):  # Very heavy filtering
            soft_attack = np.convolve(soft_attack, [0.15, 0.7, 0.15], mode='same')
        soft_attack *= np.exp(-np.arange(attack_samples) / (attack_samples * 0.4)) * 0.08 * velocity
        output[:attack_samples] += soft_attack
    
    # === FINAL WARMTH PROCESSING ===
    # Ethiopian Krar is WARM and ROUND - never bright or twangy
    output = lowpass_filter(output, 2000, sample_rate)  # Strong high rolloff
    output = highpass_filter(output, 70, sample_rate)  # Keep some low end
    
    # Remove any DC offset
    output = output - np.mean(output)
    
    # Output at moderate level to leave headroom for mixing (was 0.95)
    return normalize_audio(output, 0.70 * velocity)


def generate_masenqo_tone(
    frequency: float,
    duration: float = 0.5,
    velocity: float = 0.8,
    sample_rate: int = SAMPLE_RATE,
    expressiveness: float = 0.7,
    add_ornament: bool = False
) -> np.ndarray:
    """
    Generate authentic Masenqo (ማሲንቆ) - Ethiopian bowed string fiddle.
    
    PHYSICAL MODELING based on Stanford CCRMA bowed string research.
    
    Bowed string synthesis uses:
    1. Stick-slip friction model (bow catches and releases string)
    2. This creates a sawtooth-like waveform with natural variation
    3. Vibrato from performer's hand creates pitch modulation
    4. Body resonances (formants) give "voice-like" quality
    
    The Masenqo sound is described as "crying" or "singing" because
    it follows vocal melodies and has strong nasal formants.
    """
    num_samples = int(duration * sample_rate)
    t = np.arange(num_samples) / sample_rate
    
    # === BOW-STRING INTERACTION MODEL ===
    # The bow creates a quasi-sawtooth through stick-slip friction
    # During "stick": string moves with bow velocity
    # During "slip": string snaps back
    # This creates a periodic but not perfect waveform
    
    # Period in samples
    base_period = sample_rate / frequency
    
    # === EXPRESSIVE VIBRATO ===
    # Masenqo has WIDE vibrato (characteristic "crying" quality)
    vibrato_rate = 5.0 + expressiveness * 1.0  # 5-6 Hz
    max_cents = 15 + 12 * expressiveness  # 15-27 cents
    vibrato_depth_ratio = (2 ** (max_cents / 1200)) - 1
    
    # Vibrato develops gradually (human performer)
    vibrato_onset = np.clip((t - 0.08) / 0.2, 0, 1)
    
    # Vibrato with slight irregularity
    vibrato_mod = np.sin(2 * np.pi * vibrato_rate * t + 0.1 * np.sin(2 * np.pi * 0.7 * t))
    vibrato = vibrato_depth_ratio * vibrato_onset * vibrato_mod
    
    # Instantaneous frequency with vibrato
    inst_freq = frequency * (1 + vibrato)
    
    # === STICK-SLIP SAWTOOTH GENERATION ===
    # Generate sawtooth by integrating frequency to get phase
    phase = np.cumsum(inst_freq) / sample_rate
    
    # Basic sawtooth: 2 * (phase mod 1) - 1
    raw_sawtooth = 2 * (phase % 1) - 1
    
    # SMOOTH the sawtooth slightly to reduce digital harshness
    # Real bowed strings have softer transients than digital sawtooth
    # Use simple moving average to soften edges
    smooth_window = max(3, int(sample_rate / frequency / 8))  # ~1/8 period
    kernel = np.ones(smooth_window) / smooth_window
    sawtooth = np.convolve(raw_sawtooth, kernel, mode='same')
    
    # Add bow pressure variation (amplitude modulation from bow arm)
    bow_pressure = 1 + 0.04 * expressiveness * np.sin(2 * np.pi * 3.5 * t)  # Subtle arm tremolo
    sawtooth *= bow_pressure
    
    # NO BOW NOISE - Masenqo should be CLEAN and vocal-like
    # The "crying" quality comes from vibrato and formants, not noise
    audio = sawtooth * 0.7  # Clean sawtooth only
    
    # === BODY/FORMANT RESONANCES ===
    # The masenqo body creates voice-like formants
    # These are what make it "sing" - narrow resonant peaks
    # Key: SMOOTH formants, not harsh - like human voice
    
    # F1: Chest/body warmth (~350 Hz) - foundation
    f1_band = bandpass_simple(audio, 300, 420, sample_rate)
    
    # F2: Vocal nasal resonance (~900 Hz) - the "singing" quality
    f2_band = bandpass_simple(audio, 800, 1050, sample_rate)
    
    # F3: Gentle presence (~1800 Hz) - REDUCED to avoid harshness
    f3_band = bandpass_simple(audio, 1600, 2000, sample_rate)
    
    # Mix: More fundamental, less high presence for smoother tone
    audio = audio * 0.55 + f1_band * 0.20 + f2_band * 0.20 + f3_band * 0.05
    
    # === ENVELOPE ===
    # Bowed instrument: soft attack as bow catches string
    envelope = np.ones(num_samples)
    
    # Attack: bow catching string (~50ms)
    attack_samples = int(0.05 * sample_rate)
    if attack_samples > 0 and attack_samples < num_samples:
        # S-curve attack (realistic bow attack)
        attack_t = np.arange(attack_samples) / attack_samples
        envelope[:attack_samples] = 0.5 * (1 - np.cos(np.pi * attack_t))
    
    # Sustain: slight swell in middle (expressive bowing)
    swell = 1 + 0.08 * expressiveness * np.sin(np.pi * t / duration)
    envelope *= swell
    
    # Release: bow lifting (~80ms)
    release_samples = int(0.08 * sample_rate)
    if release_samples > 0 and release_samples < num_samples:
        release_start = num_samples - release_samples
        release_t = np.arange(release_samples) / release_samples
        envelope[release_start:] *= 0.5 * (1 + np.cos(np.pi * release_t))
    
    audio *= envelope
    
    # === CRYING SLIDE ORNAMENT ===
    if add_ornament and duration > 0.25:
        # Characteristic entry: slide up from below
        slide_samples = int(0.08 * sample_rate)
        if slide_samples < num_samples:
            slide_t = np.arange(slide_samples) / sample_rate
            # Start minor third below
            start_freq = frequency / 1.19
            # Exponential slide
            slide_freq = start_freq * np.exp(np.log(frequency / start_freq) * (slide_t * sample_rate / slide_samples) ** 0.6)
            
            slide_phase = np.cumsum(slide_freq) / sample_rate
            slide_saw = 2 * (slide_phase % 1) - 1
            
            # Crossfade
            xfade = np.linspace(0.6, 0, slide_samples)
            audio[:slide_samples] = audio[:slide_samples] * (1 - xfade) + slide_saw * 0.4 * xfade * velocity
    
    # === FINAL PROCESSING ===
    # Remove DC offset (formant filtering can introduce asymmetry)
    audio = audio - np.mean(audio)
    
    # Warmth: acoustic instrument character
    audio = lowpass_filter(audio, 5000, sample_rate)
    audio = highpass_filter(audio, 100, sample_rate)
    
    # Remove any remaining DC offset after filtering - CRITICAL
    audio = audio - np.mean(audio)
    
    # Very gentle saturation for warmth (also helps symmetry)
    audio = np.tanh(audio * 1.1) / 1.1
    
    # Remove any final DC offset after saturation
    audio = audio - np.mean(audio)
    
    # Final normalization to prevent clipping when mixed
    max_val = np.max(np.abs(audio))
    if max_val > 0:
        audio = audio / max_val
    
    # Output at moderate level to leave headroom for mixing
    return audio * 0.65 * velocity


def generate_washint_tone(
    frequency: float,
    duration: float = 0.5,
    velocity: float = 0.8,
    sample_rate: int = SAMPLE_RATE,
    add_ornament: bool = False
) -> np.ndarray:
    """
    Generate authentic Washint (ዋሺንት) - Ethiopian bamboo flute tone.
    
    MASTERCLASS SYNTHESIS with breath modeling and Ethiopian ornaments.
    
    The Washint is a traditional end-blown bamboo flute:
    - 4 finger holes (pentatonic range)
    - End-blown like a bottle (not transverse)
    - Made from bamboo or river reed
    - Used for pastoral, romantic, and ceremonial music
    
    Acoustic characteristics:
    - Breathy, airy tone with prominent breath noise
    - Mostly odd harmonics (open pipe resonance)
    - Characteristic Ethiopian ornamental grace notes
    - Developing vibrato that intensifies through the note
    - Clear, penetrating upper register
    - Hollow bamboo tube resonance
    
    Playing techniques:
    - End-blown with precise embouchure
    - Half-holing for microtones
    - Ornamental trills and mordents
    - Pitch bends by adjusting air angle
    - Circular breathing for long phrases
    """
    num_samples = int(duration * sample_rate)
    t = np.arange(num_samples) / sample_rate
    
    audio = np.zeros(num_samples)
    
    # === MAIN FLUTE OSCILLATOR ===
    # Flutes have mostly odd harmonics (open pipe)
    for i in [1, 3, 5, 7]:
        harmonic_freq = frequency * i
        
        # Amplitude: strong fundamental, weak higher harmonics
        if i == 1:
            amp = 1.0
        elif i == 3:
            amp = 0.25
        elif i == 5:
            amp = 0.1
        else:
            amp = 0.05
        
        audio += amp * np.sin(2 * np.pi * harmonic_freq * t)
    
    # === BREATH NOISE ===
    # Characteristic breathy quality of end-blown flutes
    breath = np.random.randn(num_samples)
    
    # Filter breath to flute's resonant frequencies
    breath = lowpass_filter(breath, 6000, sample_rate)
    breath = highpass_filter(breath, 1500, sample_rate)
    
    # Breath follows note dynamics
    breath_envelope = np.exp(-t / 0.1) * 0.3 + 0.1  # Stronger at attack
    breath_envelope *= velocity
    
    audio += breath * breath_envelope * 0.12
    
    # === VIBRATO (delayed onset, increasing depth) ===
    vibrato_rate = 5.0 + np.sin(t * 0.5) * 0.5  # Slight rate modulation
    vibrato_depth = 0.006
    
    # Vibrato develops over time
    vibrato_onset = np.clip((t - 0.15) / 0.2, 0, 1)  # Starts after 150ms
    vibrato_increase = vibrato_onset * (1 + t / duration * 0.5)  # Increases through note
    
    vibrato = np.sin(2 * np.pi * vibrato_rate * t) * vibrato_depth * vibrato_increase
    
    # Apply vibrato to main tone
    audio_vibrato = np.sin(2 * np.pi * frequency * (t + vibrato))
    audio = audio * 0.5 + audio_vibrato * 0.5
    
    # === ORNAMENTAL GRACE NOTE (mordent) ===
    # Ethiopian flutes often have quick ornamental turns at note onset
    if duration > 0.2 and velocity > 0.5:
        grace_duration = int(0.03 * sample_rate)  # 30ms grace note
        grace_freq = frequency * 1.1  # Slightly higher pitch
        grace_t = np.arange(grace_duration) / sample_rate
        grace = np.sin(2 * np.pi * grace_freq * grace_t) * 0.4
        grace *= np.exp(-grace_t / 0.01)  # Quick decay
        audio[:grace_duration] += grace
    
    # === BODY RESONANCE (bamboo tube) ===
    # Bamboo has characteristic resonances
    body_resonances = [frequency * 2, frequency * 4, 2500, 4000]
    body_qs = [15, 12, 6, 4]
    audio = _apply_body_resonance(audio, body_resonances, body_qs, sample_rate)
    
    # === ENVELOPE ===
    # Soft attack (breath building), sustained, soft release
    attack = int(0.04 * sample_rate)  # 40ms attack
    decay = int(0.08 * sample_rate)
    sustain_level = 0.85
    release = int(0.12 * sample_rate)
    
    audio = apply_envelope(audio, attack, decay, sustain_level, release)
    
    # === FINAL PROCESSING ===
    # Clarity boost
    audio = highpass_filter(audio, 200, sample_rate)
    
    return normalize_audio(audio, 0.72 * velocity)


def generate_begena_tone(
    frequency: float,
    duration: float = 1.0,
    velocity: float = 0.7,
    sample_rate: int = SAMPLE_RATE
) -> np.ndarray:
    """
    Generate authentic Begena (ባገና) - Ethiopian 10-string bass lyre.
    
    PHYSICAL MODELING with Karplus-Strong + characteristic "buzz".
    
    The Begena has a unique buzzing quality from leather pieces (enzirotch)
    wrapped around strings near the bridge. This creates beating between
    slightly detuned frequency components - NOT noise!
    
    Based on acoustic measurements:
    - Pitch range: 50-150 Hz (VERY low bass)
    - Characteristic "roughness" from leather buzzers
    - Long, meditative sustain
    - Deep, spiritual quality
    """
    num_samples = int(duration * sample_rate)
    t = np.arange(num_samples) / sample_rate
    
    # === KARPLUS-STRONG FOR MAIN STRING ===
    period_samples = int(sample_rate / frequency)
    if period_samples < 2:
        period_samples = 2
    
    # Initialize with VERY soft filtered noise (liturgical = gentle, meditative)
    noise = np.random.randn(period_samples)
    # VERY heavy filtering for deep, meditative gut string tone
    for _ in range(15):  # Many passes for ultra-soft attack
        noise = np.convolve(noise, [0.2, 0.6, 0.2], mode='same')
    
    # Output buffer
    output = np.zeros(num_samples)
    
    # Delay line for main string
    delay_line = noise.copy()
    
    # VERY long sustain for deep meditative quality (liturgical drone)
    damping = 0.9992  # Extremely high = very long, tranquil decay
    
    write_pos = 0
    for i in range(num_samples):
        read_pos = (write_pos + 1) % period_samples
        next_pos = (read_pos + 1) % period_samples
        
        # Two-point averaging
        filtered = 0.5 * (delay_line[read_pos] + delay_line[next_pos])
        filtered *= damping
        
        output[i] = filtered
        delay_line[write_pos] = filtered
        write_pos = (write_pos + 1) % period_samples
    
    # === JAWARI BUZZ (leather buzzer effect) ===
    # The leather creates a second, slightly detuned vibration
    # This causes BEATING - periodic amplitude variation, NOT noise
    
    # Buzz frequency is slightly detuned from main
    buzz_detune = 1.007  # ~12 cents sharp
    buzz_period = int(sample_rate / (frequency * buzz_detune))
    if buzz_period < 2:
        buzz_period = 2
    
    # Initialize buzz delay line
    buzz_noise = np.random.randn(buzz_period)
    for _ in range(5):
        buzz_noise = np.convolve(buzz_noise, [0.25, 0.5, 0.25], mode='same')
    
    buzz_output = np.zeros(num_samples)
    buzz_delay = buzz_noise.copy()
    buzz_damping = 0.997  # Slightly faster decay than main
    
    write_pos = 0
    for i in range(num_samples):
        read_pos = (write_pos + 1) % buzz_period
        next_pos = (read_pos + 1) % buzz_period
        
        filtered = 0.5 * (buzz_delay[read_pos] + buzz_delay[next_pos])
        filtered *= buzz_damping
        
        buzz_output[i] = filtered
        buzz_delay[write_pos] = filtered
        write_pos = (write_pos + 1) % buzz_period
    
    # Combine main and buzz (buzz creates the characteristic roughness)
    output = output * 0.7 + buzz_output * 0.3
    
    # === SYMPATHETIC STRINGS ===
    # 10 strings create rich sympathetic resonance
    for ratio in [1.5, 2.0, 3.0]:
        symp_freq = frequency * ratio
        if symp_freq < sample_rate / 2:
            symp_env = np.exp(-t / 1.0) * np.clip((t - 0.05) / 0.2, 0, 1)
            output += 0.03 * np.sin(2 * np.pi * symp_freq * t) * symp_env
    
    # === BODY RESONANCE ===
    # Large wooden bowl body
    body = bandpass_simple(output, 100, 250, sample_rate)
    output = output + body * 0.2
    
    # === ENVELOPE ===
    # Slow attack (measured ~90ms), long natural decay
    attack_samples = int(0.09 * sample_rate)
    envelope = np.ones(num_samples)
    if attack_samples > 0 and attack_samples < num_samples:
        envelope[:attack_samples] = np.linspace(0, 1, attack_samples)
    
    # Gentle release
    release_samples = int(0.15 * sample_rate)
    if release_samples > 0 and release_samples < num_samples:
        release_start = num_samples - release_samples
        envelope[release_start:] *= np.linspace(1, 0, release_samples)
    
    output *= envelope
    
    # === FINAL PROCESSING ===
    # DEEP bass emphasis for liturgical, meditative quality
    # Begena should rumble like a prayer - felt more than heard
    bass_boost = lowpass_filter(output, 150, sample_rate)
    output = output + bass_boost * 0.5  # Strong bass boost
    
    # Sub-bass presence for that deep spiritual feeling
    sub_bass = lowpass_filter(output, 80, sample_rate)
    output = output + sub_bass * 0.25
    
    # Warmth - remove all harshness, keep only tranquil tones
    output = lowpass_filter(output, 1800, sample_rate)  # Very warm
    output = highpass_filter(output, 30, sample_rate)  # Allow very deep bass
    
    return normalize_audio(output, 1.0 * velocity)  # Maximum for spectrum presence
    
    # === ENVELOPE ===
    # Attack: 0.09s measured, Effective duration: 0.58s
    attack = int(0.09 * sample_rate)
    decay = int(0.35 * sample_rate)
    sustain_level = 0.4
    release = int(min(duration * 0.4, 0.6) * sample_rate)
    
    audio = apply_envelope(audio, attack, decay, sustain_level, release)
    
    # === ROOM AMBIENCE (zema performed in quiet rooms) ===
    audio = _generate_room_ambience(audio, room_size=0.35, dampness=0.6, sample_rate=sample_rate)
    
    # === FINAL PROCESSING ===
    # Spectral rolloff target: 793 Hz with buzzers
    audio = lowpass_filter(audio, 2500, sample_rate)
    
    # Deep bass boost (this is a BASS instrument)
    bass = lowpass_filter(audio, 200, sample_rate)
    audio = audio + bass * 0.4
    
    # Subtle saturation for gut string warmth
    audio = np.tanh(audio * 1.15) / 1.15
    
    return normalize_audio(audio, 0.72 * velocity)


def generate_brass_tone(
    frequency: float,
    duration: float = 0.5,
    velocity: float = 0.8,
    sample_rate: int = SAMPLE_RATE
) -> np.ndarray:
    """
    Generate brass-like tone for Ethio-jazz style.
    
    Characteristic of Mulatu Astatke's Ethio-jazz fusion -
    bright, punchy brass with soul/funk influence.
    
    Acoustic characteristics:
    - Bright attack with "blat" transient
    - Strong even and odd harmonics
    - Slight vibrato on sustained notes
    - Punchy, rhythmic quality
    """
    num_samples = int(duration * sample_rate)
    t = np.arange(num_samples) / sample_rate
    
    audio = np.zeros(num_samples)
    
    # === BRASS OSCILLATOR ===
    # Rich harmonic content
    for i in range(1, 12):
        harmonic_freq = frequency * i
        
        # Brass harmonic profile: strong fundamentals and mid-harmonics
        if i <= 3:
            amp = 1.0 / i
        elif i <= 6:
            amp = 0.8 / i
        else:
            amp = 0.4 / i
        
        audio += amp * np.sin(2 * np.pi * harmonic_freq * t)
    
    # === ATTACK TRANSIENT ("blat") ===
    attack_noise = np.random.randn(num_samples) * velocity
    attack_env = np.exp(-t / 0.008)  # 8ms decay
    attack_noise *= attack_env
    attack_noise = highpass_filter(attack_noise, 800, sample_rate)
    attack_noise = lowpass_filter(attack_noise, 4000, sample_rate)
    audio += attack_noise * 0.2
    
    # === VIBRATO (delayed) ===
    if duration > 0.3:
        vibrato_rate = 5.5
        vibrato_depth = 0.008
        vibrato_onset = np.clip((t - 0.2) / 0.15, 0, 1)
        vibrato = np.sin(2 * np.pi * vibrato_rate * t) * vibrato_depth * vibrato_onset
        
        audio_vibrato = np.zeros(num_samples)
        for i in range(1, 8):
            amp = 0.9 / i if i <= 3 else 0.5 / i
            audio_vibrato += amp * np.sin(2 * np.pi * frequency * i * (t + vibrato))
        
        audio = audio * 0.6 + audio_vibrato * 0.4
    
    # === ENVELOPE ===
    attack = int(0.015 * sample_rate)
    decay = int(0.06 * sample_rate)
    sustain_level = 0.85
    release = int(0.08 * sample_rate)
    
    audio = apply_envelope(audio, attack, decay, sustain_level, release)
    
    # === BRIGHTNESS ===
    audio = highpass_filter(audio, 120, sample_rate)
    
    return normalize_audio(audio, 0.75 * velocity)


def generate_organ_tone(
    frequency: float,
    duration: float = 0.5,
    velocity: float = 0.8,
    sample_rate: int = SAMPLE_RATE
) -> np.ndarray:
    """
    Generate organ-like tone for Ethio-jazz style.
    
    Hammond-style organ with drawbar harmonics,
    characteristic of Ethio-jazz and Ethio-funk.
    """
    num_samples = int(duration * sample_rate)
    t = np.arange(num_samples) / sample_rate
    
    audio = np.zeros(num_samples)
    
    # === DRAWBAR OSCILLATORS ===
    # Hammond drawbar positions
    drawbar_ratios = [0.5, 1.5, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 8.0]
    drawbar_levels = [0.6, 0.4, 1.0, 0.8, 0.5, 0.6, 0.3, 0.4, 0.3]
    
    for ratio, level in zip(drawbar_ratios, drawbar_levels):
        # Slight detuning for chorus effect
        detune = 1 + (np.random.randn() * 0.001)
        audio += level * np.sin(2 * np.pi * frequency * ratio * detune * t)
    
    # === KEY CLICK ===
    click_duration = int(0.005 * sample_rate)
    click = np.random.randn(click_duration) * 0.3
    click *= np.exp(-np.arange(click_duration) / (0.001 * sample_rate))
    audio[:click_duration] += click
    
    # === LESLIE SPEAKER SIMULATION (subtle) ===
    if duration > 0.2:
        leslie_rate = 6.0  # Hz
        leslie_depth = 0.003
        leslie = np.sin(2 * np.pi * leslie_rate * t) * leslie_depth
        
        audio_leslie = np.zeros(num_samples)
        for ratio, level in zip(drawbar_ratios[:5], drawbar_levels[:5]):
            audio_leslie += level * np.sin(2 * np.pi * frequency * ratio * (t + leslie))
        
        audio = audio * 0.7 + audio_leslie * 0.3
    
    # === ENVELOPE ===
    attack = int(0.008 * sample_rate)
    decay = int(0.04 * sample_rate)
    sustain_level = 0.92
    release = int(0.06 * sample_rate)
    
    audio = apply_envelope(audio, attack, decay, sustain_level, release)
    
    return normalize_audio(audio, 0.72 * velocity)


def generate_kebero_hit(
    pitch: int = 63,
    velocity: float = 0.8,
    sample_rate: int = SAMPLE_RATE
) -> np.ndarray:
    """
    Generate Kebero/Conga-style drum hit for Ethiopian percussion.
    
    The Kebero is a double-headed conical drum with goatskin heads.
    This function also handles conga and bongo sounds for GM compatibility.
    
    Pitch mappings (GM standard):
    - 60: High Bongo (Atamo - small drum)
    - 61: Low Bongo
    - 62: High Conga (Kebero slap/tek)
    - 63: Low Conga (Kebero bass/doom)
    - 70: Shaker/Maracas
    
    Custom kebero range:
    - 50: Kebero bass
    - 51: Kebero slap
    - 52: Kebero muted
    """
    duration = 0.4
    num_samples = int(duration * sample_rate)
    t = np.arange(num_samples) / sample_rate
    
    audio = np.zeros(num_samples)
    
    if pitch in [63, 50, 61]:  # Low Conga / Kebero bass / Low Bongo
        # Deep "doom" sound - the foundation of Ethiopian rhythm
        base_freq = 75 if pitch == 63 else (65 if pitch == 50 else 85)
        
        # Characteristic pitch drop of hand drums
        freq_env = base_freq * (1 + 0.8 * np.exp(-t / 0.015))
        phase = 2 * np.pi * np.cumsum(freq_env) / sample_rate
        audio = np.sin(phase)
        
        # Add body resonance harmonics
        audio += 0.4 * np.sin(2 * np.pi * base_freq * 2.3 * t) * np.exp(-t / 0.08)
        audio += 0.2 * np.sin(2 * np.pi * base_freq * 3.5 * t) * np.exp(-t / 0.05)
        
        # Skin vibration texture
        skin_noise = np.random.randn(num_samples) * 0.08
        skin_noise = lowpass_filter(skin_noise, 400, sample_rate)
        audio += skin_noise * np.exp(-t / 0.1)
        
        # Envelope - quick attack, medium decay
        env = np.exp(-t / 0.18) * (1 - np.exp(-t / 0.003))
        audio *= env * velocity * 1.25  # Boost for mix presence
        
    elif pitch in [62, 51]:  # High Conga / Kebero slap
        # Sharp "tek" slap sound
        base_freq = 220 if pitch == 62 else 200
        
        # Slap has faster pitch drop
        freq_env = base_freq * (1 + 1.2 * np.exp(-t / 0.008))
        phase = 2 * np.pi * np.cumsum(freq_env) / sample_rate
        audio = np.sin(phase) * 0.7
        
        # Attack transient (hand slap) - warmer for traditional drum
        slap = np.random.randn(num_samples)
        slap = bandpass_simple(slap, 600, 2500, sample_rate)  # Lower range
        slap *= np.exp(-t / 0.012)
        audio += slap * 0.4
        
        # Quick decay
        env = np.exp(-t / 0.08) * (1 - np.exp(-t / 0.001))
        audio *= env * velocity * 1.3  # Boost for mix presence
        
        # Roll off highs for warm traditional sound
        audio = lowpass_filter(audio, 3500, sample_rate)
        
    elif pitch in [60]:  # High Bongo / Atamo
        # Bright but warm attack sound (traditional drum)
        base_freq = 280
        
        freq_env = base_freq * (1 + 0.5 * np.exp(-t / 0.006))
        phase = 2 * np.pi * np.cumsum(freq_env) / sample_rate
        audio = np.sin(phase) * 0.6
        
        # Add harmonic brightness (but controlled)
        audio += 0.25 * np.sin(2 * np.pi * base_freq * 2.2 * t) * np.exp(-t / 0.03)
        
        # Attack with moderate brightness
        attack = np.random.randn(num_samples)
        attack = bandpass_simple(attack, 800, 2500, sample_rate)  # Not too harsh
        attack *= np.exp(-t / 0.008)
        audio += attack * 0.2
        
        # Very short envelope
        env = np.exp(-t / 0.06) * (1 - np.exp(-t / 0.001))
        audio *= env * velocity
        
    elif pitch == 52:  # Muted kebero
        # Damped hit with very short decay
        base_freq = 100
        audio = np.sin(2 * np.pi * base_freq * t) * np.exp(-t / 0.03)
        audio += 0.3 * np.sin(2 * np.pi * 180 * t) * np.exp(-t / 0.02)
        
        env = np.exp(-t / 0.04)
        audio *= env * velocity * 0.7
        
    else:  # Default - medium conga-like sound
        base_freq = 150
        freq_env = base_freq * (1 + 0.6 * np.exp(-t / 0.01))
        phase = 2 * np.pi * np.cumsum(freq_env) / sample_rate
        audio = np.sin(phase)
        
        env = np.exp(-t / 0.12)
        audio *= env * velocity
    
    return normalize_audio(audio, 0.92)  # Increased from 0.75 for presence


def bandpass_simple(
    audio: np.ndarray,
    low_freq: float,
    high_freq: float,
    sample_rate: int = SAMPLE_RATE
) -> np.ndarray:
    """Simple bandpass filter using cascaded low and high pass."""
    audio = lowpass_filter(audio, high_freq, sample_rate)
    audio = highpass_filter(audio, low_freq, sample_rate)
    return audio


def generate_shaker_hit(
    velocity: float = 0.7,
    sample_rate: int = SAMPLE_RATE
) -> np.ndarray:
    """
    Generate traditional Ethiopian shaker/sese sound.
    
    Ethiopian shakers are typically made from gourds filled with seeds,
    creating a warm, muted texture rather than bright modern maracas.
    """
    duration = 0.08  # Very short
    num_samples = int(duration * sample_rate)
    t = np.arange(num_samples) / sample_rate
    
    # Create warm noise centered in low-mids
    audio = np.random.randn(num_samples)
    
    # Apply strong low-pass first
    audio = lowpass_filter(audio, 1200, sample_rate)
    
    # Add mid-range content
    mid_noise = np.random.randn(num_samples) * 0.3
    mid_noise = bandpass_simple(mid_noise, 400, 1000, sample_rate)
    audio += mid_noise
    
    # Add body/gourd resonance 
    body = np.random.randn(num_samples) * 0.4
    body = bandpass_simple(body, 200, 500, sample_rate)
    audio += body
    
    # Quick attack, very fast decay
    env = np.exp(-t / 0.02) * (1 - np.exp(-t / 0.002))
    audio *= env * velocity
    
    # Final aggressive low-pass
    audio = lowpass_filter(audio, 2000, sample_rate)
    
    # Present but not harsh
    return normalize_audio(audio, 0.32)  # Increased from 0.18


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
