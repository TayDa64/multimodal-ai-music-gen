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
from typing import Optional, Tuple, Dict, List, Iterable
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
    """Apply ADSR envelope to audio.

    When attack+decay+release exceeds the note length, A/D/R are compressed
    proportionally so the release still reaches zero. This prevents short notes
    (shorter than attack+decay) from being truncated mid-amplitude, which caused
    audible clicks. Normal-length notes are unchanged.
    """
    total_samples = len(audio)
    if total_samples <= 0:
        return audio

    a = int(max(0, attack_samples))
    d = int(max(0, decay_samples))
    r = int(max(0, release_samples))
    s = int(max(0, sustain_samples))

    if a + d + r > total_samples:
        scale = total_samples / float(a + d + r)
        a = int(a * scale)
        d = int(d * scale)
        r = total_samples - a - d
        s = 0
        if r <= 0:  # guarantee a release so the note always fades to zero
            r = 1 if total_samples >= 1 else 0
            d = max(0, total_samples - a - r)

    envelope = np.ones(total_samples)

    # Attack
    if a > 0:
        attack_end = min(a, total_samples)
        envelope[:attack_end] = np.linspace(0, 1, attack_end)

    # Decay
    decay_start = a
    decay_end = min(decay_start + d, total_samples)
    if decay_end > decay_start:
        envelope[decay_start:decay_end] = np.linspace(1, sustain_level, decay_end - decay_start)

    # Sustain
    sustain_start = decay_end
    sustain_end = min(sustain_start + s, total_samples)
    if sustain_end > sustain_start:
        envelope[sustain_start:sustain_end] = sustain_level

    # Release
    release_start = sustain_end if s > 0 else decay_end
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


# ---------------------------------------------------------------------------
# Shared natural-instrument DSP foundation (InstrumentPatch-aligned)
#
# These helpers back the mainstream physical-modeling upgrades (guitar, bass,
# piano, brass) with the same class of techniques already proven on the
# Ethiopian engines: velocity-sensitive excitation, filter envelopes, and
# dispersion. They are pure/additive and change no existing engine on their
# own. Determinism is provided via _seeded_rng so upgraded engines stay stable
# under the offline render path (which does not seed a global RNG per note).
# ---------------------------------------------------------------------------


def _seeded_rng(*keys: float) -> np.random.Generator:
    """Return a deterministic RNG seeded from note-scoped numeric keys.

    Using a per-note seed keeps "organic" noise reproducible under the offline
    render path, which does not set a global np.random seed per note.
    """
    h = 1469598103934665603  # FNV-1a 64-bit offset basis
    for key in keys:
        quantized = int(round(float(key) * 1000.0)) & 0xFFFFFFFFFFFFFFFF
        h = ((h ^ quantized) * 1099511628211) & 0xFFFFFFFFFFFFFFFF
    return np.random.default_rng(h & 0x7FFFFFFF)


def apply_velocity_map(
    velocity: float,
    velocity_map: object = None,
    *,
    amp: float = 1.0,
    cutoff_delta_hz: float = 0.0,
    transient_level: float = 0.0,
    noise_level: float = 0.0,
    amp_curve: float = 0.6,
) -> Dict[str, float]:
    """Resolve a VelocityMap into concrete per-note contributions.

    Extends velocity beyond amplitude so it can drive filter cutoff, transient
    intensity, and breath/pluck noise. Accepts a VelocityMap-like object (duck
    typed) or explicit keyword defaults. ``amp`` follows a mild perceptual
    curve; the other fields scale linearly with velocity.
    """
    v = float(np.clip(velocity, 0.0, 1.0))
    if velocity_map is not None:
        amp = float(getattr(velocity_map, "amp", amp))
        cutoff_delta_hz = float(getattr(velocity_map, "cutoff_delta_hz", cutoff_delta_hz))
        transient_level = float(getattr(velocity_map, "transient_level", transient_level))
        noise_level = float(getattr(velocity_map, "noise_level", noise_level))

    curved = v ** max(0.1, float(amp_curve))
    return {
        "velocity": v,
        "amp": float(amp) * curved,
        "cutoff_delta_hz": float(cutoff_delta_hz) * v,
        "transient_level": float(transient_level) * v,
        "noise_level": float(noise_level) * v,
    }


def apply_filter_envelope(
    audio: np.ndarray,
    base_cutoff_hz: float,
    *,
    attack_ms: float = 0.0,
    decay_ms: float = 120.0,
    sustain_level: float = 0.5,
    release_ms: float = 120.0,
    amount_hz: float = 0.0,
    sample_rate: int = SAMPLE_RATE,
    floor_hz: float = 80.0,
) -> np.ndarray:
    """Apply a time-varying low-pass whose cutoff follows an ADSR contour.

    The cutoff blooms to ``base + amount_hz`` right after the attack and settles
    toward ``base + amount_hz * sustain_level``, brightening onsets and darkening
    decays the way natural instruments do. With ``amount_hz == 0`` it reduces to
    a static one-pole low-pass at ``base_cutoff_hz``.
    """
    n = int(audio.shape[0]) if audio.ndim else 0
    if n <= 0:
        return audio.astype(np.float64, copy=True) if audio.size else audio

    nyquist = max(200.0, sample_rate / 2.0 - 100.0)
    floor_hz = float(np.clip(floor_hz, 1.0, nyquist))
    base = float(np.clip(base_cutoff_hz, floor_hz, nyquist))

    if abs(amount_hz) < 1e-6:
        cutoff = np.full(n, base, dtype=np.float64)
    else:
        contour = np.zeros(n, dtype=np.float64)
        a = min(n, max(0, int(attack_ms * 1e-3 * sample_rate)))
        d = min(n - a, max(0, int(decay_ms * 1e-3 * sample_rate)))
        r = min(n, max(0, int(release_ms * 1e-3 * sample_rate)))
        sustain = float(np.clip(sustain_level, 0.0, 1.0))

        idx = 0
        if a > 0:
            contour[:a] = np.linspace(0.0, 1.0, a, endpoint=False)
            idx = a
        else:
            contour[:1] = 1.0
        if d > 0:
            end = min(n, idx + d)
            contour[idx:end] = np.linspace(1.0, sustain, end - idx, endpoint=False)
            idx = end
        if idx < n:
            contour[idx:] = sustain
        if r > 0:
            contour[-r:] = np.linspace(contour[max(0, n - r - 1)], 0.0, r)

        cutoff = np.clip(base + amount_hz * contour, floor_hz, nyquist)

    # Time-varying one-pole low-pass (matches lowpass_filter topology).
    dt = 1.0 / sample_rate
    rc = 1.0 / (2.0 * np.pi * cutoff)
    alpha = dt / (rc + dt)

    src = audio.astype(np.float64, copy=False)
    out = np.empty(n, dtype=np.float64)
    prev = src[0] * alpha[0]
    out[0] = prev
    for i in range(1, n):
        prev = prev + alpha[i] * (src[i] - prev)
        out[i] = prev
    return np.nan_to_num(out, nan=0.0, posinf=0.0, neginf=0.0)


def resolve_filter_envelope_params(
    voice: object = None,
    *,
    attack_ms: float,
    decay_ms: float,
    sustain_level: float,
    release_ms: float,
    amount_hz: float,
) -> Dict[str, float]:
    """Pull filter-envelope params from a SynthesisVoice.filter_envelope.

    Lets the InstrumentPatch registry drive the offline filter envelope while
    falling back to the caller's tuned defaults when no voice / field exists.
    """
    fe = getattr(voice, "filter_envelope", None) if voice is not None else None
    if fe is None:
        return {
            "attack_ms": attack_ms,
            "decay_ms": decay_ms,
            "sustain_level": sustain_level,
            "release_ms": release_ms,
            "amount_hz": amount_hz,
        }
    return {
        "attack_ms": float(getattr(fe, "attack_ms", attack_ms)),
        "decay_ms": float(getattr(fe, "decay_ms", decay_ms)),
        "sustain_level": float(getattr(fe, "sustain_level", sustain_level)),
        "release_ms": float(getattr(fe, "release_ms", release_ms)),
        "amount_hz": float(getattr(fe, "amount", amount_hz)),
    }


def _dispersion_allpass(
    audio: np.ndarray,
    coefficient: float = 0.4,
    stages: int = 2,
    sample_rate: int = SAMPLE_RATE,
) -> np.ndarray:
    """Add frequency-dependent dispersion (stiff-string inharmonicity).

    Cascades first-order allpass sections so high partials are delayed relative
    to the fundamental, the physical cue behind piano/guitar inharmonicity.
    """
    c = float(np.clip(coefficient, -0.95, 0.95))
    stages = int(np.clip(stages, 0, 8))
    if stages <= 0 or abs(c) < 1e-6 or audio.size == 0:
        return audio.astype(np.float64, copy=True)

    signal = audio.astype(np.float64, copy=True)
    n = signal.shape[0]
    for _ in range(stages):
        out = np.empty(n, dtype=np.float64)
        x1 = 0.0
        y1 = 0.0
        for i in range(n):
            x0 = signal[i]
            y0 = c * x0 + x1 - c * y1
            out[i] = y0
            x1 = x0
            y1 = y0
        signal = out
    return signal


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


def generate_guitar_tone(
    frequency: float,
    duration: float = 0.5,
    velocity: float = 0.8,
    sample_rate: int = SAMPLE_RATE,
    drive: float = 0.45,
    voice: object = None,
) -> np.ndarray:
    """Generate a physically-modeled electric-guitar/crunch fallback tone.

    Upgraded to the same class of techniques proven on the Ethiopian plucked
    strings: a Karplus-Strong core with pick-position comb excitation, blended
    with an additive harmonic body, plus string dispersion, a velocity-driven
    filter envelope (bright pick attack, darker sustain), and a velocity-scaled
    pick transient. Deterministic (seeded per note), finite, bounded, and
    zero-duration safe so the offline render and golden tests stay stable.
    """
    num_samples = int(duration * sample_rate)
    if num_samples <= 0:
        return np.zeros(0, dtype=np.float32)

    frequency = float(np.clip(frequency, 20.0, sample_rate / 2.5))
    velocity = float(np.clip(velocity, 0.0, 1.0))
    drive = float(np.clip(drive, 0.0, 1.0))
    t = np.arange(num_samples) / sample_rate
    rng = _seeded_rng(frequency, duration, velocity, drive)

    # Velocity opens the tone: brighter, stronger pick, more pick noise.
    vmap = apply_velocity_map(
        velocity,
        velocity_map=getattr(voice, "velocity_map", None),
        cutoff_delta_hz=1400.0,
        transient_level=1.0,
        noise_level=1.0,
    )

    # === KARPLUS-STRONG PLUCKED-STRING CORE ===
    period_samples = max(2, int(sample_rate / frequency))
    excitation = rng.standard_normal(period_samples)
    # Harder plucks land at a brighter pluck position (this comb brightens as
    # the pluck point moves toward center), so louder notes read brighter.
    pick_position = float(np.clip(0.30 + 0.18 * velocity, 0.12, 0.5))
    pick_delay = max(1, int(pick_position * period_samples))
    if pick_delay < period_samples:
        excitation[pick_delay:] -= excitation[:-pick_delay] * 0.7
    smoothing_passes = 2 + int((1.0 - velocity) * 2)
    for _ in range(smoothing_passes):
        excitation = np.convolve(excitation, [0.15, 0.7, 0.15], mode="same")

    ks = np.zeros(num_samples, dtype=np.float64)
    delay_line = excitation.copy()
    damping = 0.990 + 0.003 * velocity  # louder plucks ring a little longer
    write_pos = 0
    for i in range(num_samples):
        read_pos = (write_pos + 1) % period_samples
        next_pos = (read_pos + 1) % period_samples
        filtered = damping * 0.5 * (delay_line[read_pos] + delay_line[next_pos])
        ks[i] = filtered
        delay_line[write_pos] = filtered
        write_pos = (write_pos + 1) % period_samples

    # === ADDITIVE HARMONIC BODY (fullness the KS core alone lacks) ===
    body = np.zeros(num_samples, dtype=np.float64)
    for harmonic, level in [(1, 1.0), (2, 0.42), (3, 0.28), (4, 0.16), (5, 0.10)]:
        harmonic_freq = frequency * harmonic
        if harmonic_freq >= sample_rate / 2 - 200:
            break
        body += level * np.sin(2 * np.pi * harmonic_freq * t)
    fifth_freq = frequency * 1.5
    if fifth_freq < sample_rate / 2 - 200:
        body += 0.10 * np.sin(2 * np.pi * fifth_freq * t)

    ks_peak = float(np.max(np.abs(ks))) if ks.size else 0.0
    if ks_peak > 1e-9:
        ks /= ks_peak
    body_peak = float(np.max(np.abs(body))) if body.size else 0.0
    if body_peak > 1e-9:
        body /= body_peak
    audio = 0.62 * ks + 0.38 * body

    # String stiffness dispersion (inharmonicity) for a less synthetic tone.
    audio = _dispersion_allpass(audio, coefficient=0.32, stages=2, sample_rate=sample_rate)

    # Deterministic pick transient; noisy scrape scales with velocity.
    pick_len = min(num_samples, max(1, int(0.006 * sample_rate)))
    pick_env = np.exp(-np.arange(pick_len) / max(1.0, 0.0018 * sample_rate))
    pick = np.sin(2 * np.pi * min(5200.0, sample_rate / 4.0) * (np.arange(pick_len) / sample_rate))
    pick_noise = rng.standard_normal(pick_len) * np.exp(-np.arange(pick_len) / max(1.0, 0.0012 * sample_rate))
    audio[:pick_len] += (pick + 0.5 * pick_noise) * pick_env * (0.06 + 0.12 * vmap["transient_level"])

    # Mild amp-style saturation driven by the amp/overdrive, not velocity, so
    # louder notes stay brighter rather than getting darker from extra clipping.
    saturation = 0.20 + drive * 1.80
    audio = np.tanh(audio * saturation) / np.tanh(saturation)

    # Velocity-driven filter envelope: bright pick attack -> darker sustain.
    fe = resolve_filter_envelope_params(
        voice, attack_ms=2.0, decay_ms=140.0, sustain_level=0.5, release_ms=120.0, amount_hz=2200.0
    )
    base_cutoff = 2200.0 + 900.0 * velocity - drive * 600.0
    audio = apply_filter_envelope(
        audio,
        base_cutoff,
        attack_ms=fe["attack_ms"],
        decay_ms=fe["decay_ms"],
        sustain_level=fe["sustain_level"],
        release_ms=fe["release_ms"],
        amount_hz=fe["amount_hz"] + vmap["cutoff_delta_hz"],
        sample_rate=sample_rate,
    )
    audio = highpass_filter(audio, 70, sample_rate)

    # Subtle deterministic amp flutter (body vibration) that settles quickly.
    audio *= 1.0 + 0.02 * np.sin(2 * np.pi * 5.0 * t) * np.exp(-t / 0.5)

    attack = int(0.004 * sample_rate)
    decay = int(0.090 * sample_rate)
    sustain_level = 0.42 + (0.18 * drive)
    release = int(0.120 * sample_rate)
    sustain_samples = max(0, num_samples - attack - decay - release)
    audio = apply_envelope(audio, attack, decay, sustain_level, release, sustain_samples)

    audio = np.nan_to_num(audio, nan=0.0, posinf=0.0, neginf=0.0)
    audio = normalize_audio(audio, 0.72 * velocity) if np.any(audio) else audio
    return audio.astype(np.float32)


def generate_bass_tone(
    frequency: float,
    duration: float = 0.5,
    velocity: float = 0.8,
    sample_rate: int = SAMPLE_RATE,
    voice: object = None,
) -> np.ndarray:
    """Generate a physically-modeled electric/acoustic bass fallback tone.

    Uses the same plucked-string physical modeling proven on the Ethiopian
    strings: a Karplus-Strong core (pick-position comb, velocity-dependent
    damping so louder notes sustain longer) blended with a fundamental-heavy
    additive body, plus a velocity-scaled pick transient, growl saturation, and
    a velocity-driven filter envelope. Deterministic, finite, bounded, and
    zero-duration safe. This is the general (non-rock) bass path; the rock
    renderer keeps its dedicated sub-controlled electric-bass fallback.
    """
    num_samples = int(duration * sample_rate)
    if num_samples <= 0:
        return np.zeros(0, dtype=np.float32)

    frequency = float(np.clip(frequency, 30.0, sample_rate / 4.0))
    velocity = float(np.clip(velocity, 0.0, 1.0))
    t = np.arange(num_samples) / sample_rate
    rng = _seeded_rng(frequency, duration, velocity)
    vmap = apply_velocity_map(
        velocity,
        velocity_map=getattr(voice, "velocity_map", None),
        cutoff_delta_hz=600.0,
        transient_level=1.0,
        noise_level=0.5,
    )

    # === KARPLUS-STRONG STRING CORE ===
    period_samples = max(2, int(sample_rate / frequency))
    excitation = rng.standard_normal(period_samples)
    pick_position = float(np.clip(0.32 + 0.15 * velocity, 0.15, 0.5))
    pick_delay = max(1, int(pick_position * period_samples))
    if pick_delay < period_samples:
        excitation[pick_delay:] -= excitation[:-pick_delay] * 0.6
    smoothing_passes = 3 + int((1.0 - velocity) * 2)
    for _ in range(smoothing_passes):
        excitation = np.convolve(excitation, [0.15, 0.7, 0.15], mode="same")

    ks = np.zeros(num_samples, dtype=np.float64)
    delay_line = excitation.copy()
    damping = 0.993 + 0.002 * velocity  # bass strings ring long
    write_pos = 0
    for i in range(num_samples):
        read_pos = (write_pos + 1) % period_samples
        next_pos = (read_pos + 1) % period_samples
        filtered = damping * 0.5 * (delay_line[read_pos] + delay_line[next_pos])
        ks[i] = filtered
        delay_line[write_pos] = filtered
        write_pos = (write_pos + 1) % period_samples

    # === FUNDAMENTAL-HEAVY ADDITIVE BODY ===
    body = np.zeros(num_samples, dtype=np.float64)
    for harmonic, level in [(1, 1.0), (2, 0.55), (3, 0.30), (4, 0.15)]:
        harmonic_freq = frequency * harmonic
        if harmonic_freq >= sample_rate / 2 - 200:
            break
        body += level * np.sin(2 * np.pi * harmonic_freq * t)

    ks_peak = float(np.max(np.abs(ks))) if ks.size else 0.0
    if ks_peak > 1e-9:
        ks /= ks_peak
    body_peak = float(np.max(np.abs(body))) if body.size else 0.0
    if body_peak > 1e-9:
        body /= body_peak
    audio = 0.6 * ks + 0.4 * body

    # Velocity-scaled pick/finger transient (lower/rounder than guitar).
    pick_len = min(num_samples, max(1, int(0.008 * sample_rate)))
    pick_env = np.exp(-np.arange(pick_len) / max(1.0, 0.0025 * sample_rate))
    pick_tone = np.sin(2 * np.pi * min(1800.0, sample_rate / 4.0) * (np.arange(pick_len) / sample_rate))
    audio[:pick_len] += pick_tone * pick_env * (0.05 + 0.10 * vmap["transient_level"])

    # Growl saturation; keep the velocity coupling light so louder stays brighter.
    audio = np.tanh(audio * (1.1 + 0.15 * velocity))

    # Velocity-driven filter envelope: brighter attack, warm sustain.
    fe = resolve_filter_envelope_params(
        voice, attack_ms=3.0, decay_ms=100.0, sustain_level=0.55, release_ms=120.0, amount_hz=1200.0
    )
    base_cutoff = 700.0 + 1400.0 * velocity
    audio = apply_filter_envelope(
        audio,
        base_cutoff,
        attack_ms=fe["attack_ms"],
        decay_ms=fe["decay_ms"],
        sustain_level=fe["sustain_level"],
        release_ms=fe["release_ms"],
        amount_hz=fe["amount_hz"] + vmap["cutoff_delta_hz"],
        sample_rate=sample_rate,
    )
    audio = highpass_filter(audio, 40, sample_rate)

    attack = int(0.004 * sample_rate)
    decay = int(0.06 * sample_rate)
    sustain_level = 0.7
    release = int(0.10 * sample_rate)
    sustain_samples = max(0, num_samples - attack - decay - release)
    audio = apply_envelope(audio, attack, decay, sustain_level, release, sustain_samples)

    audio = np.nan_to_num(audio, nan=0.0, posinf=0.0, neginf=0.0)
    audio = normalize_audio(audio, 0.8 * velocity) if np.any(audio) else audio
    return audio.astype(np.float32)


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
    sample_rate: int = SAMPLE_RATE,
    voice: object = None,
) -> np.ndarray:
    """Generate a more piano-like tone (procedural fallback).

    Physically-modeled fallback that is deterministic (seeded per note) so the
    offline render stays stable. Models:
    - Additive partials with string inharmonicity (stiff-string dispersion)
    - Velocity-scaled hammer-noise transient
    - Two slightly detuned unison strings (chorus-like beating)
    - A velocity-driven filter envelope (harder strikes are brighter)
    - Light soundboard body resonance for low-mid warmth
    """
    num_samples = max(1, int(duration * sample_rate))
    t = np.arange(num_samples) / sample_rate
    velocity = float(np.clip(velocity, 0.0, 1.0))
    rng = _seeded_rng(frequency, duration, velocity)
    vmap = apply_velocity_map(
        velocity,
        velocity_map=getattr(voice, "velocity_map", None),
        cutoff_delta_hz=3500.0,
        transient_level=1.0,
        noise_level=1.0,
    )

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

    # Hammer noise transient (first ~12ms); harder strikes hit brighter/louder.
    transient_len = min(num_samples, int(0.012 * sample_rate))
    if transient_len > 8:
        noise = rng.standard_normal(transient_len)
        noise = bandpass_filter(noise, 900, 8000, sample_rate)
        noise_env = np.exp(-np.arange(transient_len) / (0.004 * sample_rate))
        hammer_gain = 0.06 + 0.14 * vmap["transient_level"]
        noise = noise * noise_env * hammer_gain
        audio[:transient_len] += noise

    # Envelope: fast attack, gentle release
    attack = int(0.003 * sample_rate)
    decay = int(0.18 * sample_rate)
    sustain_level = 0.25
    release = int(0.22 * sample_rate)
    sustain_samples = max(0, num_samples - attack - decay - release)
    audio = apply_envelope(audio, attack, decay, sustain_level, release, sustain_samples)

    # Velocity-driven filter envelope: harder strikes are brighter.
    fe = resolve_filter_envelope_params(
        voice, attack_ms=1.0, decay_ms=350.0, sustain_level=0.35, release_ms=200.0, amount_hz=3000.0
    )
    base_cutoff = 4500.0 + 2500.0 * velocity
    audio = apply_filter_envelope(
        audio,
        base_cutoff,
        attack_ms=fe["attack_ms"],
        decay_ms=fe["decay_ms"],
        sustain_level=fe["sustain_level"],
        release_ms=fe["release_ms"],
        amount_hz=fe["amount_hz"] + vmap["cutoff_delta_hz"],
        sample_rate=sample_rate,
    )

    # Light soundboard body resonance (low-mid warmth), kept subtle.
    resonant = np.zeros_like(audio)
    for res_freq, res_q, res_gain in ((120.0, 8.0, 0.5), (230.0, 6.0, 0.35)):
        bandwidth = res_freq / res_q
        low = max(20.0, res_freq - bandwidth / 2.0)
        high = min(sample_rate / 2 - 100.0, res_freq + bandwidth / 2.0)
        band = highpass_filter(lowpass_filter(audio, high, sample_rate), low, sample_rate)
        resonant += band * res_gain
    audio = audio * 0.9 + resonant * 0.1

    # Warmth + gentle saturation
    audio = add_saturation(audio, 0.12)

    # Velocity scaling and normalization
    audio = normalize_audio(audio, target_peak=0.85) * velocity
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


_STATIC_WAVETABLE_CACHE: Dict[int, Tuple[str, np.ndarray]] = {}


def get_static_wavetable_bank(table_size: int = 512) -> Tuple[str, np.ndarray]:
    """Return a small, bounded single-cycle wavetable bank.

    This is a truthful *foundation* only: a few static tables intended for
    procedural fallback use, not a full wavetable engine.
    """
    table_size = int(np.clip(table_size, 64, 4096))
    cached = _STATIC_WAVETABLE_CACHE.get(table_size)
    if cached is not None:
        return cached

    phase = np.linspace(0.0, 1.0, table_size, endpoint=False, dtype=np.float64)
    sine = np.sin(2.0 * np.pi * phase)
    triangle = 2.0 * np.abs(2.0 * phase - 1.0) - 1.0
    soft_saw = np.zeros(table_size, dtype=np.float64)
    hollow_square = np.zeros(table_size, dtype=np.float64)

    for harmonic in range(1, 24):
        soft_saw += (1.0 / harmonic) * np.sin(2.0 * np.pi * harmonic * phase)
        if harmonic % 2 == 1:
            hollow_square += (1.0 / harmonic) * np.sin(2.0 * np.pi * harmonic * phase)

    tables = np.stack(
        [
            normalize_audio(sine, 1.0),
            normalize_audio(0.72 * triangle + 0.28 * sine, 1.0),
            normalize_audio(soft_saw, 1.0),
            normalize_audio(0.58 * hollow_square + 0.42 * soft_saw, 1.0),
        ],
        axis=0,
    ).astype(np.float32)
    names = ("sine", "triangle", "soft_saw", "hollow_square")
    cached = (names, tables)
    _STATIC_WAVETABLE_CACHE[table_size] = cached
    return cached


def render_static_wavetable_tone(
    frequency: float,
    duration: float,
    sample_rate: int = SAMPLE_RATE,
    *,
    morph_position: float = 0.5,
    morph_span: float = 0.0,
    table_size: int = 512,
) -> np.ndarray:
    """Render a bounded single-voice tone from the static wavetable bank.

    Supports two layers of interpolation:
    - sample interpolation within each single-cycle table
    - table-to-table morphing across the small static bank
    """
    num_samples = int(duration * sample_rate)
    if num_samples <= 0:
        return np.zeros(0, dtype=np.float32)

    names, tables = get_static_wavetable_bank(table_size)
    del names  # Names are for diagnostics/tests; rendering uses the stacked bank.

    frequency = float(np.clip(frequency, 20.0, sample_rate / 3.0))
    morph_position = float(np.clip(morph_position, 0.0, 1.0))
    morph_span = float(np.clip(morph_span, 0.0, 1.0))

    phase_increment = frequency / float(sample_rate)
    phases = np.mod(np.arange(num_samples, dtype=np.float64) * phase_increment, 1.0)
    table_positions = phases * tables.shape[1]
    base_idx = np.floor(table_positions).astype(np.int32) % tables.shape[1]
    next_idx = (base_idx + 1) % tables.shape[1]
    frac = (table_positions - np.floor(table_positions)).astype(np.float32)

    if morph_span > 0.0:
        morph_curve = np.linspace(
            morph_position - morph_span * 0.5,
            morph_position + morph_span * 0.5,
            num_samples,
            dtype=np.float32,
        )
    else:
        morph_curve = np.full(num_samples, morph_position, dtype=np.float32)
    morph_curve = np.clip(morph_curve, 0.0, 1.0)

    max_table_index = tables.shape[0] - 1
    morph_scaled = morph_curve * max_table_index
    lower_table = np.floor(morph_scaled).astype(np.int32)
    upper_table = np.clip(lower_table + 1, 0, max_table_index)
    table_blend = (morph_scaled - lower_table).astype(np.float32)

    lower_a = tables[lower_table, base_idx]
    lower_b = tables[lower_table, next_idx]
    upper_a = tables[upper_table, base_idx]
    upper_b = tables[upper_table, next_idx]

    lower_wave = lower_a + (lower_b - lower_a) * frac
    upper_wave = upper_a + (upper_b - upper_a) * frac
    audio = lower_wave + (upper_wave - lower_wave) * table_blend
    return np.nan_to_num(audio, nan=0.0, posinf=0.0, neginf=0.0).astype(np.float32)


def generate_unison_lead_tone(
    frequency: float,
    duration: float = 0.4,
    velocity: float = 0.8,
    sample_rate: int = SAMPLE_RATE,
    *,
    voices: int = 7,
    detune_cents: float = 14.0,
    table_position: Optional[float] = None,
    table_motion: Optional[float] = None,
) -> np.ndarray:
    """Generate a bounded EDM/pop unison lead using a static wavetable bank.

    This is a small, safe fallback intended for EDM/pop-like genres when the
    renderer is in procedural mode (no SoundFont/sample packs).

    Important: this is **not** a full wavetable engine. It is a bounded static
    wavetable foundation with a few single-cycle tables, sample interpolation,
    and light table morphing only for this fallback path.
    """
    num_samples = int(duration * sample_rate)
    if num_samples <= 0:
        return np.zeros(0, dtype=np.float32)

    frequency = float(np.clip(frequency, 20.0, sample_rate / 3.0))
    velocity = float(np.clip(velocity, 0.0, 1.0))
    voices = int(np.clip(voices, 1, 11))
    detune_cents = float(np.clip(detune_cents, 0.0, 40.0))
    audio = np.zeros(num_samples, dtype=np.float64)

    # Symmetric detune spread around 0 cents.
    if voices == 1:
        cents_list = [0.0]
    else:
        # E.g. voices=7 -> [-1, -2/3, -1/3, 0, 1/3, 2/3, 1] * detune
        idx = np.linspace(-1.0, 1.0, voices)
        cents_list = (idx * detune_cents).tolist()

    legacy_base_morph = 0.58
    legacy_motion_span = 0.10 + 0.10 * velocity
    base_morph = legacy_base_morph if table_position is None else float(np.clip(table_position, 0.0, 1.0))
    morph_offsets = np.linspace(-0.16, 0.16, voices, dtype=np.float32)
    morph_span = legacy_motion_span if table_motion is None else float(np.clip(table_motion, 0.0, 1.0)) * 0.20

    for cents, morph_offset in zip(cents_list, morph_offsets):
        ratio = 2.0 ** (cents / 1200.0)
        wavetable_voice = render_static_wavetable_tone(
            frequency * ratio,
            duration,
            sample_rate=sample_rate,
            morph_position=float(np.clip(base_morph + morph_offset, 0.0, 1.0)),
            morph_span=morph_span,
        )
        audio += wavetable_voice.astype(np.float64)

    audio /= float(len(cents_list))

    # Envelope: pop/edm-friendly fast attack, medium decay, sustained body.
    attack = int(0.004 * sample_rate)
    decay = int(0.10 * sample_rate)
    sustain_level = 0.62
    release = int(0.16 * sample_rate)
    sustain_samples = max(0, num_samples - attack - decay - release)
    audio = apply_envelope(audio, attack, decay, sustain_level, release, sustain_samples)

    # Tone shaping: keep bright but controlled.
    audio = highpass_filter(audio, 120, sample_rate)
    audio = lowpass_filter(audio, 9000, sample_rate)
    audio = add_saturation(audio, 0.22)

    audio = np.nan_to_num(audio, nan=0.0, posinf=0.0, neginf=0.0)
    audio = normalize_audio(audio, 0.85) * velocity if np.any(audio) else audio
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


def _resolve_krar_profile(profile: str) -> Dict[str, object]:
    """Return bounded Krar timbre parameters for the requested profile."""
    normalized = str(profile or 'traditional_warm').strip().lower().replace('-', '_').replace(' ', '_')
    profiles: Dict[str, Dict[str, object]] = {
        'traditional_warm': {
            'pick_position_base': 0.45,
            'pick_position_velocity_span': 0.10,
            'comb_strength': 0.20,
            'excitation_smoothing_passes': 12,
            'damping_base': 0.997,
            'damping_velocity_scale': 0.002,
            'body_mode_gains': (0.25, 0.18, 0.10),
            'goatskin_lowpass_1': 1800.0,
            'goatskin_lowpass_2': 2200.0,
            'sympathetic_ratios': (1.5, 2.0),
            'sympathetic_max_freq': 1000.0,
            'sympathetic_gain': 0.012,
            'attack_seconds': 0.015,
            'attack_smoothing_passes': 15,
            'attack_gain': 0.08,
            'contact_transient_gain': 0.018,
            'contact_presence_gain': 0.010,
            'final_lowpass': 2000.0,
            'final_highpass': 70.0,
        },
        'azmari_bright': {
            'pick_position_base': 0.28,
            'pick_position_velocity_span': 0.06,
            'comb_strength': 0.32,
            'excitation_smoothing_passes': 6,
            'damping_base': 0.9965,
            'damping_velocity_scale': 0.0025,
            'body_mode_gains': (0.22, 0.17, 0.11),
            'goatskin_lowpass_1': 2600.0,
            'goatskin_lowpass_2': 3200.0,
            'sympathetic_ratios': (1.5, 2.0, 2.5),
            'sympathetic_max_freq': 1400.0,
            'sympathetic_gain': 0.016,
            'attack_seconds': 0.010,
            'attack_smoothing_passes': 8,
            'attack_gain': 0.12,
            'contact_transient_gain': 0.030,
            'contact_presence_gain': 0.018,
            'final_lowpass': 3200.0,
            'final_highpass': 80.0,
        },
    }
    return profiles.get(normalized, profiles['traditional_warm'])


def _resolve_masenqo_profile(profile: str) -> Dict[str, object]:
    """Return bounded Masenqo articulation parameters for the requested profile."""
    normalized = str(profile or 'vocal_clean').strip().lower().replace('-', '_').replace(' ', '_')
    profiles: Dict[str, Dict[str, object]] = {
        'vocal_clean': {
            'smooth_period_divisor': 8.0,
            'bow_pressure_depth': 0.04,
            'bow_noise_low': 1400.0,
            'bow_noise_high': 3600.0,
            'bow_noise_amount': 0.010,
            'bow_noise_decay': 0.085,
            'bow_noise_floor': 0.075,
            'direct_mix': 0.55,
            'f1_mix': 0.20,
            'f2_mix': 0.20,
            'f3_mix': 0.05,
            'attack_seconds': 0.05,
            'release_seconds': 0.08,
            'swell_depth': 0.08,
            'attack_presence_low': 1600.0,
            'attack_presence_high': 3600.0,
            'attack_presence_gain': 0.014,
            'attack_presence_decay': 0.06,
            'sustained_rosin_gain': 0.014,
            'scrape_flux_gain': 0.008,
            'final_lowpass': 5000.0,
            'final_highpass': 100.0,
            'saturation_drive': 1.10,
        },
        'azmari_grit': {
            'smooth_period_divisor': 11.0,
            'bow_pressure_depth': 0.06,
            'bow_noise_low': 1800.0,
            'bow_noise_high': 5200.0,
            'bow_noise_amount': 0.044,
            'bow_noise_decay': 0.065,
            'bow_noise_floor': 0.16,
            'direct_mix': 0.50,
            'f1_mix': 0.18,
            'f2_mix': 0.22,
            'f3_mix': 0.10,
            'attack_seconds': 0.035,
            'release_seconds': 0.07,
            'swell_depth': 0.10,
            'attack_presence_low': 1800.0,
            'attack_presence_high': 4200.0,
            'attack_presence_gain': 0.085,
            'attack_presence_decay': 0.05,
            'sustained_rosin_gain': 0.024,
            'scrape_flux_gain': 0.028,
            'final_lowpass': 5800.0,
            'final_highpass': 110.0,
            'saturation_drive': 1.18,
        },
        'mp3_reference_bow': {
            'smooth_period_divisor': 14.0,
            'bow_pressure_depth': 0.082,
            'bow_noise_low': 1500.0,
            'bow_noise_high': 9200.0,
            'bow_noise_amount': 0.088,
            'bow_noise_decay': 0.090,
            'bow_noise_floor': 0.30,
            'direct_mix': 0.44,
            'f1_mix': 0.12,
            'f2_mix': 0.13,
            'f3_mix': 0.06,
            'attack_seconds': 0.030,
            'release_seconds': 0.060,
            'swell_depth': 0.07,
            'attack_presence_low': 1700.0,
            'attack_presence_high': 6800.0,
            'attack_presence_gain': 0.135,
            'attack_presence_decay': 0.060,
            'sustained_rosin_gain': 0.065,
            'scrape_flux_gain': 0.082,
            'rosin_air_gain': 0.040,
            'harmonic_core_gain': 0.24,
            'sawtooth_gain': 0.050,
            'friction_layer_gain': 0.25,
            'rosin_body_gain': 0.21,
            'nasal_core_gain': 0.14,
            'bridge_core_gain': 0.10,
            'body_shell_gain': 0.06,
            'final_lowpass': 9600.0,
            'final_highpass': 120.0,
            'saturation_drive': 1.06,
        },
    }
    return profiles.get(normalized, profiles['vocal_clean'])


def _resolve_washint_profile(profile: str) -> Dict[str, object]:
    """Return bounded Washint articulation parameters for the requested profile."""
    normalized = str(profile or 'alto_breathy').strip().lower().replace('-', '_').replace(' ', '_')
    profiles: Dict[str, Dict[str, object]] = {
        'alto_breathy': {
            'harmonic_gains': (1.0, 0.25, 0.10, 0.05),
            'breath_low': 1500.0,
            'breath_high': 6000.0,
            'breath_attack_scale': 0.30,
            'breath_floor': 0.10,
            'breath_amount': 0.12,
            'vibrato_depth': 0.006,
            'pressure_irregularity': 0.15,
            'jet_drive': 0.24,
            'grace_gain': 0.40,
            'ornament_direction': -1.0,
            'ornament_ratio': 0.050,
            'ornament_seconds': 0.024,
            'focus_shift': 0.06,
            'presence_low': 2200.0,
            'presence_high': 4200.0,
            'presence_gain': 0.0,
            'chiff_low': 2400.0,
            'chiff_high': 7200.0,
            'chiff_amount': 0.010,
            'chiff_decay': 0.020,
            'attack_seconds': 0.04,
            'decay_seconds': 0.08,
            'sustain_level': 0.85,
            'release_seconds': 0.12,
            'final_highpass': 200.0,
            'final_lowpass': 6500.0,
        },
        'dance_call': {
            'harmonic_gains': (1.0, 0.29, 0.15, 0.08),
            'breath_low': 2000.0,
            'breath_high': 7200.0,
            'breath_attack_scale': 0.34,
            'breath_floor': 0.08,
            'breath_amount': 0.10,
            'vibrato_depth': 0.0055,
            'pressure_irregularity': 0.19,
            'jet_drive': 0.32,
            'grace_gain': 0.52,
            'ornament_direction': 1.0,
            'ornament_ratio': 0.090,
            'ornament_seconds': 0.028,
            'focus_shift': 0.10,
            'presence_low': 2400.0,
            'presence_high': 5200.0,
            'presence_gain': 0.085,
            'chiff_low': 2600.0,
            'chiff_high': 8200.0,
            'chiff_amount': 0.032,
            'chiff_decay': 0.028,
            'attack_seconds': 0.028,
            'decay_seconds': 0.07,
            'sustain_level': 0.87,
            'release_seconds': 0.11,
            'final_highpass': 220.0,
            'final_lowpass': 7600.0,
        },
    }
    return profiles.get(normalized, profiles['alto_breathy'])


def generate_krar_tone(
    frequency: float,
    duration: float = 0.5,
    velocity: float = 0.8,
    sample_rate: int = SAMPLE_RATE,
    tuning: str = 'tizita',
    add_ornament: bool = False,
    profile: str = 'traditional_warm',
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
    krar_profile = _resolve_krar_profile(profile)
    num_samples = int(duration * sample_rate)
    t = np.arange(num_samples) / sample_rate
    low_register_support = float(np.clip((180.0 - float(frequency)) / 130.0, 0.0, 1.0))
    
    # === KARPLUS-STRONG CORE ===
    # Delay line length = samples per period
    period_samples = int(sample_rate / frequency)
    if period_samples < 2:
        period_samples = 2
    
    # Pick-position: Pluck at CENTER of string for maximum warmth
    # Center pluck (β=0.5) gives round, harp-like tone - NO twang
    pick_position = (
        float(krar_profile['pick_position_base'])
        + (1 - velocity) * float(krar_profile['pick_position_velocity_span'])
    )
    # String damping coefficient (higher = longer sustain)
    # Real strings: 0.996-0.9995 for gut/nylon
    # Increased for longer, more audible sustain
    damping = float(krar_profile['damping_base']) + velocity * float(krar_profile['damping_velocity_scale'])

    def _render_course(
        course_frequency: float,
        *,
        pick_shift: float = 0.0,
        smoothing_bias: int = 0,
        damping_bias: float = 0.0,
        comb_scale: float = 1.0,
    ) -> np.ndarray:
        course_period = max(2, int(sample_rate / max(course_frequency, 1e-6)))
        course_frac_delay = (sample_rate / max(course_frequency, 1e-6)) - course_period

        course_noise = np.random.randn(course_period)
        course_pick_position = float(np.clip(pick_position + pick_shift, 0.18, 0.62))
        course_pick_delay = max(1, int(course_pick_position * course_period))

        if course_pick_delay < len(course_noise):
            noise_comb = course_noise.copy()
            noise_comb[course_pick_delay:] -= (
                course_noise[:-course_pick_delay]
                * float(krar_profile['comb_strength'])
                * comb_scale
            )
            course_noise = noise_comb

        smoothing_passes = max(2, int(krar_profile['excitation_smoothing_passes']) + smoothing_bias)
        for _ in range(smoothing_passes):
            course_noise = np.convolve(course_noise, [0.15, 0.7, 0.15], mode='same')

        course_output = np.zeros(num_samples)
        delay_line = course_noise.copy()
        course_damping = float(np.clip(damping + damping_bias, 0.9925, 0.9998))
        write_pos = 0
        allpass_coef = (1 - course_frac_delay) / (1 + course_frac_delay)
        allpass_state = 0.0

        for i in range(num_samples):
            read_pos = (write_pos + 1) % course_period
            next_pos = (read_pos + 1) % course_period
            filtered = 0.5 * (delay_line[read_pos] + delay_line[next_pos])
            filtered *= course_damping

            allpass_out = allpass_coef * filtered + allpass_state
            allpass_state = filtered - allpass_coef * allpass_out

            course_output[i] = allpass_out
            delay_line[write_pos] = allpass_out
            write_pos = (write_pos + 1) % course_period

        return course_output

    main_course = _render_course(frequency)
    course_detune_cents = float(np.clip(
        np.interp(float(krar_profile['final_lowpass']), [1800.0, 3200.0], [2.4, 4.8]),
        2.4,
        4.8,
    ))
    companion_course = _render_course(
        frequency * (2 ** (course_detune_cents / 1200.0)),
        pick_shift=-0.08 if float(krar_profile['final_lowpass']) <= 2200.0 else -0.05,
        smoothing_bias=-2 if float(krar_profile['final_lowpass']) > 2400.0 else -1,
        damping_bias=-0.00045,
        comb_scale=1.10,
    )

    course_delay = int(
        sample_rate
        * np.interp(float(krar_profile['sympathetic_gain']), [0.012, 0.016], [0.006, 0.004])
    )
    coupled_course = np.zeros(num_samples)
    if 0 < course_delay < num_samples:
        coupled_course[course_delay:] = companion_course[:-course_delay]
    else:
        coupled_course = companion_course.copy()

    coupling_gate = 0.28 + 0.72 * np.clip((t - course_delay / sample_rate) / 0.06, 0.0, 1.0)
    output = main_course * 0.78 + coupled_course * 0.22 * coupling_gate

    _, amp_flutter, _ = _generate_organic_imperfections(num_samples, frequency, sample_rate)
    output *= 0.985 + 0.015 * amp_flutter

    course_interaction = bandpass_simple(
        main_course * 0.58 + coupled_course * 0.42 + (main_course - coupled_course) * 0.16,
        90.0,
        min(float(krar_profile['goatskin_lowpass_2']) * 1.10, sample_rate / 2 - 100.0),
        sample_rate,
    )
    bridge_energy = np.abs(
        np.diff(
            main_course + coupled_course,
            prepend=float(main_course[0] + coupled_course[0]),
        )
    )
    bridge_energy = lowpass_filter(bridge_energy, 55.0, sample_rate)
    bridge_peak = float(np.max(bridge_energy)) if bridge_energy.size else 0.0
    if bridge_peak > 1e-9:
        bridge_energy = bridge_energy / bridge_peak

    bridge_delay = int(
        sample_rate
        * np.interp(float(krar_profile['sympathetic_gain']), [0.012, 0.016], [0.012, 0.008])
    )
    bridge_drive = np.zeros(num_samples, dtype=np.float64)
    if 0 < bridge_delay < num_samples:
        bridge_drive[bridge_delay:] = course_interaction[:-bridge_delay]
    else:
        bridge_drive = course_interaction.copy()
    bridge_drive *= (
        0.26 + 0.74 * np.clip((t - 0.006) / 0.075, 0.0, 1.0)
    ) * (0.58 + 0.42 * bridge_energy)
    
    # === BODY RESONANCE (formant filtering) ===
    # Ethiopian lyre body: wooden bowl + goatskin membrane
    # Very LOW resonances for warm, round African tone
    body_output = output.copy()
    
    # Body modes - very low and warm, like African drums
    # Emphasize fundamental and low harmonics only
    body_mode_gains = krar_profile['body_mode_gains']
    for mode_freq, mode_q, mode_gain in [
        (90, 5, float(body_mode_gains[0])),
        (180, 4, float(body_mode_gains[1])),
        (280, 3, float(body_mode_gains[2])),
    ]:
        mode_band = bandpass_simple(output, mode_freq * 0.75, mode_freq * 1.25, sample_rate)
        low_register_mode_lift = 1.0 + low_register_support * (0.42 if mode_freq <= 180 else 0.24)
        body_output += mode_band * mode_gain * low_register_mode_lift
    
    output = body_output

    body_resonance_mix = float(np.clip(np.interp(float(krar_profile['final_lowpass']), [1800.0, 3400.0], [0.30, 0.22]), 0.22, 0.30))
    body_resonance = _apply_body_resonance(output, [110, 210, 360, 720], [14, 11, 7, 4], sample_rate)
    output = output * (1.0 - body_resonance_mix) + body_resonance * body_resonance_mix

    membrane_excitation = output * 0.78 + bridge_drive * 0.52 + course_interaction * 0.14
    membrane_body = _generate_membrane_resonance(
        membrane_excitation,
        membrane_freq=float(np.clip(frequency * 0.72, 180.0, 290.0)),
        damping=float(np.clip(
            np.interp(float(krar_profile['goatskin_lowpass_1']), [1800.0, 2600.0], [0.56, 0.44]),
            0.44,
            0.56,
        )),
        sample_rate=sample_rate,
    )
    body_bloom_gain = float(np.clip(
        np.interp(float(krar_profile['final_lowpass']), [1800.0, 3200.0], [0.34, 0.26]),
        0.26,
        0.34,
    ))
    body_bloom = bandpass_simple(
        membrane_body - membrane_excitation + bridge_drive * 0.28,
        140.0,
        820.0,
        sample_rate,
    )
    body_bloom *= (
        np.exp(-t / 0.44)
        * np.clip((t - 0.012) / 0.060, 0.0, 1.0)
        * (0.72 + 0.28 * bridge_energy)
    )
    output = output * 0.71 + membrane_body * 0.17 + body_bloom * body_bloom_gain + bridge_drive * 0.06

    if low_register_support > 0.0:
        low_body = bandpass_simple(
            output + membrane_body * 0.45 + bridge_drive * 0.22,
            55.0,
            460.0,
            sample_rate,
        )
        low_body_env = np.exp(-t / 0.78) * np.clip((t - 0.018) / 0.10, 0.0, 1.0)
        output += low_body * low_body_env * (0.050 + 0.075 * low_register_support)

    membrane_noise_gain = float(np.clip(np.interp(float(krar_profile['goatskin_lowpass_2']), [1800.0, 3200.0], [0.026, 0.018]), 0.018, 0.026))
    membrane = bandpass_filter(np.random.randn(num_samples), 120.0, 950.0, sample_rate)
    membrane = lowpass_filter(membrane, 900.0, sample_rate)
    membrane_env = np.exp(-t / 0.18) * np.clip((t + 0.004) / 0.028, 0.0, 1.0)
    output += membrane * membrane_env * membrane_noise_gain * velocity
    
    # === GOATSKIN MEMBRANE - STRONG HIGH ABSORPTION ===
    # Goatskin is soft and absorbs ALL high frequencies
    # This is what makes it NOT sound like banjo (which has tight drum head)
    output = lowpass_filter(output, float(krar_profile['goatskin_lowpass_1']), sample_rate)
    output = lowpass_filter(output, float(krar_profile['goatskin_lowpass_2']), sample_rate)
    
    # === SYMPATHETIC STRING RESONANCE ===
    # 5-6 strings ring sympathetically - warm shimmer only
    sympathetic_lowpass = float(np.clip(float(krar_profile['goatskin_lowpass_2']) * 0.74, 1400.0, 2400.0))
    helper_sympathetic = _generate_sympathetic_strings(
        frequency,
        duration,
        num_strings=5 if float(krar_profile['sympathetic_max_freq']) < 1200.0 else 6,
        tuning=tuning,
        sample_rate=sample_rate,
    )
    helper_sympathetic = lowpass_filter(helper_sympathetic, sympathetic_lowpass, sample_rate)
    helper_sympathetic = bandpass_simple(
        helper_sympathetic,
        160.0,
        min(sympathetic_lowpass * 1.15, sample_rate / 2 - 100.0),
        sample_rate,
    )
    course_beating = lowpass_filter(np.abs(main_course - coupled_course), 24.0, sample_rate)
    beating_peak = float(np.max(course_beating)) if course_beating.size else 0.0
    if beating_peak > 1e-9:
        course_beating = course_beating / beating_peak

    sympathetic_memory = lowpass_filter(np.abs(body_bloom + bridge_drive * 0.65), 18.0, sample_rate)
    sympathetic_peak = float(np.max(sympathetic_memory)) if sympathetic_memory.size else 0.0
    if sympathetic_peak > 1e-9:
        sympathetic_memory = sympathetic_memory / sympathetic_peak

    helper_sympathetic *= (
        np.exp(-t / 0.95)
        * np.clip((t - 0.020) / 0.18, 0.0, 1.0)
        * (0.44 + 0.28 * course_beating + 0.28 * sympathetic_memory)
    )
    output += helper_sympathetic * float(krar_profile['sympathetic_gain']) * 1.55

    for ratio in krar_profile['sympathetic_ratios']:
        symp_freq = frequency * ratio
        if symp_freq < float(krar_profile['sympathetic_max_freq']):
            symp_env = np.exp(-t / (0.52 + 0.06 * ratio)) * np.clip((t - 0.03) / 0.18, 0.0, 1.0)
            symp_env *= 0.52 + 0.24 * course_beating + 0.24 * sympathetic_memory
            symp_phase = 2 * np.pi * symp_freq * t
            symp = np.sin(
                symp_phase
                + 0.03 * np.sin(2 * np.pi * (0.8 + 0.15 * ratio) * t)
                + 0.01 * course_beating
            )
            symp += 0.18 * np.sin(2 * symp_phase + 0.35 + 0.04 * sympathetic_memory)
            symp = lowpass_filter(symp, sympathetic_lowpass, sample_rate)
            output += float(krar_profile['sympathetic_gain']) * 0.74 * symp * symp_env
    
    # === SOFT FINGER ATTACK ===
    # Finger plucking creates soft onset, not sharp attack
    attack_samples = int(float(krar_profile['attack_seconds']) * sample_rate)
    if 0 < attack_samples < num_samples:
        soft_attack = np.random.randn(attack_samples)
        for _ in range(int(krar_profile['attack_smoothing_passes'])):
            soft_attack = np.convolve(soft_attack, [0.15, 0.7, 0.15], mode='same')
        pluck_brightness = float(np.clip(
            np.interp(float(krar_profile['final_lowpass']), [1800.0, 3200.0], [0.34, 0.62]),
            0.34,
            0.62,
        ))
        pluck_attack = _generate_pluck_noise(attack_samples, brightness=pluck_brightness, sample_rate=sample_rate)
        soft_attack = soft_attack * 0.42 + pluck_attack * 0.58
        attack_lowpass = float(np.clip(float(krar_profile['goatskin_lowpass_2']) * 0.72, 1000.0, 2200.0))
        soft_attack = lowpass_filter(soft_attack, attack_lowpass, sample_rate)
        soft_attack *= (
            np.exp(-np.arange(attack_samples) / max(1, attack_samples * 0.4))
            * float(krar_profile['attack_gain'])
            * velocity
        )
        output[:attack_samples] += soft_attack

    contact_samples = min(num_samples, max(1, int(0.040 * sample_rate)))
    if contact_samples > 0:
        contact_t = np.arange(contact_samples, dtype=np.float64) / sample_rate
        contact_high = min(
            sample_rate / 2 - 120.0,
            max(1500.0, float(krar_profile['final_lowpass']) * 1.12),
        )
        contact = _generate_pluck_noise(
            contact_samples,
            brightness=float(np.clip(0.52 + 0.18 * float(krar_profile['comb_strength']), 0.48, 0.66)),
            sample_rate=sample_rate,
        )
        contact = bandpass_filter(contact, 720.0, contact_high, sample_rate)
        contact *= np.exp(-contact_t / (0.010 + 0.004 * low_register_support))
        output[:contact_samples] += (
            contact
            * float(krar_profile['contact_transient_gain'])
            * velocity
            * (1.0 + 0.22 * low_register_support)
        )

    contact_presence_high = min(
        sample_rate / 2 - 120.0,
        max(1600.0, float(krar_profile['final_lowpass']) * 1.18),
    )
    contact_motion = bandpass_filter(np.random.randn(num_samples), 820.0, contact_presence_high, sample_rate)
    contact_flux = lowpass_filter(
        np.abs(bridge_drive) + np.abs(course_interaction) * 0.42 + bridge_energy * 0.20,
        34.0,
        sample_rate,
    )
    flux_peak = float(np.max(contact_flux)) if contact_flux.size else 0.0
    if flux_peak > 1e-9:
        contact_flux = contact_flux / flux_peak
    contact_irregularity = np.clip(1.0 + 0.22 * _slow_noise_contour(num_samples, sample_rate, 9.0), 0.72, 1.28)
    contact_presence_env = (
        np.exp(-t / (0.36 + 0.20 * low_register_support))
        * np.clip((t + 0.004) / 0.028, 0.0, 1.0)
        * (0.34 + 0.66 * contact_flux)
        * contact_irregularity
    )
    output += (
        contact_motion
        * contact_presence_env
        * float(krar_profile['contact_presence_gain'])
        * velocity
    )

    bridge_presence = bandpass_simple(
        main_course + coupled_course + bridge_drive * 0.45,
        900.0,
        min(float(krar_profile['final_lowpass']) * 1.6, sample_rate / 2 - 100.0),
        sample_rate,
    )
    bridge_presence *= np.exp(-t / 0.24) * np.clip((t + 0.003) / 0.016, 0.0, 1.0)
    output += bridge_presence * float(np.clip(
        np.interp(float(krar_profile['final_lowpass']), [1800.0, 3200.0], [0.018, 0.042]),
        0.018,
        0.042,
    )) * velocity
    
    # === FINAL WARMTH PROCESSING ===
    # Ethiopian Krar is WARM and ROUND - never bright or twangy
    output = add_saturation(output, float(np.clip(0.06 + float(krar_profile['comb_strength']) * 0.10, 0.07, 0.10)))
    output = lowpass_filter(output, float(krar_profile['final_lowpass']), sample_rate)
    output = highpass_filter(output, float(krar_profile['final_highpass']), sample_rate)
    
    # Remove any DC offset
    output = np.nan_to_num(output - np.mean(output), nan=0.0, posinf=0.0, neginf=0.0)
    
    # Output at moderate level to leave headroom for mixing (was 0.95)
    return normalize_audio(output, 0.70 * velocity)


def generate_masenqo_tone(
    frequency: float,
    duration: float = 0.5,
    velocity: float = 0.8,
    sample_rate: int = SAMPLE_RATE,
    expressiveness: float = 0.7,
    add_ornament: bool = False,
    profile: str = 'vocal_clean',
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
    masenqo_profile = _resolve_masenqo_profile(profile)
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
    phase_radians = 2 * np.pi * phase
    
    # Basic sawtooth: 2 * (phase mod 1) - 1
    raw_sawtooth = 2 * (phase % 1) - 1
    
    # SMOOTH the sawtooth slightly to reduce digital harshness
    # Real bowed strings have softer transients than digital sawtooth
    # Use simple moving average to soften edges
    smooth_window = max(3, int(sample_rate / frequency / float(masenqo_profile['smooth_period_divisor'])))
    kernel = np.ones(smooth_window) / smooth_window
    sawtooth = np.convolve(raw_sawtooth, kernel, mode='same')
    
    # Add bow pressure variation (amplitude modulation from bow arm)
    bow_pressure = 1 + float(masenqo_profile['bow_pressure_depth']) * expressiveness * np.sin(2 * np.pi * 3.5 * t)
    sawtooth *= bow_pressure

    bow_drift = _slow_noise_contour(num_samples, sample_rate, 18.0)
    harmonic_wander = _slow_noise_contour(num_samples, sample_rate, 26.0)
    harmonic_core = np.zeros(num_samples, dtype=np.float64)
    for harmonic, level in enumerate((1.0, 0.55, 0.31, 0.18, 0.11, 0.06), start=1):
        if frequency * harmonic >= sample_rate / 2 - 200:
            break
        harmonic_gain = level * (
            1.0
            + harmonic_wander * (0.016 + 0.003 * harmonic)
            + bow_drift * (0.010 + 0.0015 * harmonic)
        )
        harmonic_core += harmonic_gain * np.sin(
            harmonic * phase_radians
            + bow_drift * (0.010 + 0.002 * harmonic)
            + harmonic_wander * (0.006 + 0.0015 * harmonic)
            + 0.08 * harmonic
        )
    harmonic_core *= 0.95 + 0.05 * bow_pressure
    harmonic_core = lowpass_filter(harmonic_core, 3600.0 + expressiveness * 500.0, sample_rate)
    sawtooth = lowpass_filter(sawtooth, 2600.0 + expressiveness * 600.0, sample_rate)

    slip_events = np.abs(np.diff(raw_sawtooth, prepend=raw_sawtooth[0]))
    slip_events = lowpass_filter(slip_events, 900.0, sample_rate)
    slip_peak = float(np.max(slip_events)) if slip_events.size else 0.0
    if slip_peak > 1e-9:
        slip_events = slip_events / slip_peak

    friction_excitation = _generate_bow_excitation(
        frequency,
        duration,
        bow_pressure=float(np.clip(0.56 + expressiveness * 0.18 + float(masenqo_profile['bow_pressure_depth']), 0.40, 0.95)),
        bow_speed=float(np.clip(0.68 - float(masenqo_profile['bow_noise_amount']) * 2.0 + velocity * 0.08, 0.38, 0.88)),
        sample_rate=sample_rate,
    )
    friction_core = bandpass_simple(
        friction_excitation,
        650.0,
        min(float(masenqo_profile['final_lowpass']) * 0.96, sample_rate / 2 - 100.0),
        sample_rate,
    )
    friction_attack = bandpass_simple(
        friction_excitation,
        max(1200.0, float(masenqo_profile['attack_presence_low']) * 0.92),
        min(float(masenqo_profile['attack_presence_high']) * 1.08, sample_rate / 2 - 100.0),
        sample_rate,
    )
    rosin_body = bandpass_simple(
        friction_excitation,
        260.0,
        min(1600.0 + expressiveness * 280.0, sample_rate / 2 - 100.0),
        sample_rate,
    )
    rosin_grain = bandpass_simple(
        friction_excitation,
        max(1000.0, float(masenqo_profile['attack_presence_low']) * 0.68),
        min(float(masenqo_profile['attack_presence_high']) * 0.88, sample_rate / 2 - 100.0),
        sample_rate,
    )
    bow_motion = 0.5 + 0.5 * np.clip(bow_drift, -1.0, 1.0)
    rosin_memory = lowpass_filter(np.abs(rosin_body) + slip_events * 0.40, 26.0, sample_rate)
    rosin_peak = float(np.max(rosin_memory)) if rosin_memory.size else 0.0
    if rosin_peak > 1e-9:
        rosin_memory = rosin_memory / rosin_peak
    bow_capture = np.clip((t + 0.010) / 0.075, 0.16, 1.0)
    bow_settle = np.clip((t - float(masenqo_profile['attack_seconds']) * 0.65) / 0.24, 0.0, 1.0)
    friction_envelope = (
        0.46 * np.exp(-t / 0.038) * (0.84 + 0.16 * slip_events)
        + (0.18 + 0.20 * bow_motion) * bow_capture
        + (0.12 + 0.22 * rosin_memory) * bow_settle
    )
    friction_drive = 0.32 * slip_events + 0.44 * bow_motion + 0.24 * rosin_memory
    friction_layer = friction_core * friction_envelope * friction_drive * (0.07 + 0.11 * expressiveness)
    rosin_body_layer = (
        rosin_body
        * (0.028 + 0.040 * velocity + 0.015 * expressiveness)
        * (0.32 + 0.68 * bow_settle)
        * (0.55 + 0.45 * rosin_memory)
    )
    attack_push = 1.0 + float(masenqo_profile['attack_presence_gain']) * 8.0 + float(masenqo_profile['bow_noise_amount']) * 2.0
    friction_attack_layer = friction_attack * (
        np.exp(-t / max(1e-4, float(masenqo_profile['attack_presence_decay']) * 0.72))
        * (0.010 + float(masenqo_profile['attack_presence_gain']) * 0.90 + float(masenqo_profile['bow_noise_amount']) * 0.45)
        * (0.50 + 0.50 * slip_events)
        * attack_push
        * velocity
    )
    rosin_grain_layer = rosin_grain * (
        np.exp(-t / max(1e-4, float(masenqo_profile['attack_presence_decay']) * 0.85))
        * (0.008 + float(masenqo_profile['bow_noise_amount']) * 0.16 + float(masenqo_profile['attack_presence_gain']) * 0.55)
        * (0.45 + 0.55 * slip_events)
        * velocity
    )
    sustained_rosin = bandpass_simple(
        friction_excitation + rosin_body * 0.42 + rosin_grain * 0.18,
        max(900.0, float(masenqo_profile['attack_presence_low']) * 0.70),
        min(float(masenqo_profile['attack_presence_high']) * 1.08, sample_rate / 2 - 100.0),
        sample_rate,
    )
    scrape_flux = bandpass_simple(
        friction_excitation * (0.70 + 0.30 * slip_events) + friction_attack * 0.22,
        max(1500.0, float(masenqo_profile['attack_presence_low']) * 0.96),
        min(float(masenqo_profile['bow_noise_high']) * 0.96, sample_rate / 2 - 100.0),
        sample_rate,
    )
    rosin_floor_env = (
        (0.30 + 0.70 * bow_settle)
        * (0.48 + 0.30 * bow_motion + 0.22 * rosin_memory)
        * np.clip((t + 0.006) / 0.070, 0.14, 1.0)
    )
    scrape_flux_env = (
        np.exp(-t / max(1e-4, float(masenqo_profile['attack_presence_decay']) * 1.55)) * (0.62 + 0.70 * slip_events)
        + 0.34 * (0.38 + 0.62 * rosin_memory) * bow_settle
    )
    sustained_rosin_layer = sustained_rosin * rosin_floor_env * float(masenqo_profile['sustained_rosin_gain']) * velocity
    scrape_flux_layer = scrape_flux * scrape_flux_env * float(masenqo_profile['scrape_flux_gain']) * velocity

    nasal_core = bandpass_simple(harmonic_core + friction_layer * 0.40 + rosin_body_layer * 0.30, 450.0, 2400.0, sample_rate)
    bridge_core = bandpass_simple(harmonic_core + friction_layer * 0.20 + rosin_body_layer * 0.45, 220.0, 900.0, sample_rate)
    audio = (
        harmonic_core * float(masenqo_profile.get('harmonic_core_gain', 0.36))
        + sawtooth * float(masenqo_profile.get('sawtooth_gain', 0.07))
        + friction_layer * float(masenqo_profile.get('friction_layer_gain', 0.16))
        + rosin_body_layer * float(masenqo_profile.get('rosin_body_gain', 0.14))
        + sustained_rosin_layer
        + scrape_flux_layer
        + nasal_core * float(masenqo_profile.get('nasal_core_gain', 0.23))
        + bridge_core * float(masenqo_profile.get('bridge_core_gain', 0.12))
    )
    audio += friction_attack_layer + rosin_grain_layer

    # Bounded bow-noise and attack presence profiling.
    bow_noise = bandpass_filter(
        np.random.randn(num_samples),
        float(masenqo_profile['bow_noise_low']),
        float(masenqo_profile['bow_noise_high']),
        sample_rate,
    )
    bow_noise_envelope = (
        np.exp(-t / max(1e-4, float(masenqo_profile['bow_noise_decay']))) * (0.54 + 0.32 * slip_events + 0.14 * rosin_memory)
        + float(masenqo_profile['bow_noise_floor'])
        * (0.46 + 0.24 * bow_motion + 0.30 * rosin_memory)
        * (0.52 + 0.48 * bow_settle)
    )
    audio += bow_noise * bow_noise_envelope * float(masenqo_profile['bow_noise_amount']) * velocity

    rosin_air_gain = float(masenqo_profile.get('rosin_air_gain', 0.0))
    if rosin_air_gain > 0.0:
        rosin_air = bandpass_filter(
            np.random.randn(num_samples),
            max(4400.0, float(masenqo_profile['attack_presence_high']) * 0.72),
            min(float(masenqo_profile['final_lowpass']) * 1.02, sample_rate / 2 - 100.0),
            sample_rate,
        )
        rosin_air_env = (
            (0.18 + 0.82 * rosin_memory)
            * (0.38 + 0.62 * bow_motion)
            * np.clip((t + 0.006) / 0.060, 0.12, 1.0)
            * (0.58 + 0.42 * bow_settle)
        )
        audio += rosin_air * rosin_air_env * rosin_air_gain * velocity

    attack_presence = bandpass_simple(
        audio + rosin_grain_layer * 0.20,
        float(masenqo_profile['attack_presence_low']),
        float(masenqo_profile['attack_presence_high']),
        sample_rate,
    )
    audio += (
        attack_presence
        * np.exp(-t / max(1e-4, float(masenqo_profile['attack_presence_decay'])))
        * (float(masenqo_profile['attack_presence_gain']) + float(masenqo_profile['bow_noise_amount']) * 0.35)
        * attack_push
        * velocity
    )
    
    # === BODY/FORMANT RESONANCES ===
    # The masenqo body creates voice-like formants
    # These are what make it "sing" - narrow resonant peaks
    # Key: SMOOTH formants, not harsh - like human voice
    
    bridge_wander = 0.5 + 0.5 * _slow_noise_contour(num_samples, sample_rate, 8.0)

    # F1/F2/F3 move subtly as bow pressure and bridge interaction evolve.
    f1_band = bandpass_simple(audio, 300.0, 420.0, sample_rate)
    f1_shifted = bandpass_simple(audio, 360.0, 620.0, sample_rate)
    f2_band = bandpass_simple(audio + friction_layer * 0.35, 780.0, 1050.0, sample_rate)
    f2_shifted = bandpass_simple(audio + friction_layer * 0.35, 980.0, 1320.0, sample_rate)
    f3_band = bandpass_simple(audio + friction_layer * 0.50, 1550.0, 2050.0, sample_rate)
    f3_shifted = bandpass_simple(audio + friction_layer * 0.50, 1850.0, 2550.0, sample_rate)

    moving_f1 = f1_band * (0.60 + 0.20 * (1.0 - bridge_wander)) + f1_shifted * (0.08 + 0.08 * bow_settle + 0.08 * bridge_wander)
    moving_f2 = f2_band * (0.48 + 0.18 * bridge_wander + 0.08 * bow_settle) + f2_shifted * (0.14 + 0.14 * (1.0 - bridge_wander))
    moving_f3 = f3_band * (0.42 + 0.14 * np.sin(2 * np.pi * 1.6 * t + bridge_wander * 0.35) + 0.08 * (1.0 - bow_settle)) + f3_shifted * (0.12 + 0.08 * bow_settle)
    body_shell = _apply_body_resonance(audio, [240.0, 420.0, 760.0], [8, 9, 6], sample_rate)

    # Mix: More vocal/body evolution, less static fixed-formant emphasis.
    audio = (
        audio * float(masenqo_profile['direct_mix'])
        + moving_f1 * float(masenqo_profile['f1_mix'])
        + moving_f2 * float(masenqo_profile['f2_mix'])
        + moving_f3 * float(masenqo_profile['f3_mix'])
        + body_shell * (float(masenqo_profile.get('body_shell_gain', 0.05)) + 0.05 * bow_settle)
    )
    
    # === ENVELOPE ===
    # Bowed instrument: soft attack as bow catches string
    envelope = np.ones(num_samples)
    
    # Attack: bow catching string (~50ms)
    attack_samples = int(float(masenqo_profile['attack_seconds']) * sample_rate)
    if attack_samples > 0 and attack_samples < num_samples:
        # S-curve attack (realistic bow attack)
        attack_t = np.arange(attack_samples) / attack_samples
        envelope[:attack_samples] = 0.5 * (1 - np.cos(np.pi * attack_t))
    
    # Sustain: slight swell in middle (expressive bowing)
    swell = 1 + float(masenqo_profile['swell_depth']) * expressiveness * np.sin(np.pi * t / max(duration, 1e-6))
    envelope *= swell
    
    # Release: bow lifting (~80ms)
    release_samples = int(float(masenqo_profile['release_seconds']) * sample_rate)
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
    audio = lowpass_filter(audio, float(masenqo_profile['final_lowpass']), sample_rate)
    audio = highpass_filter(audio, float(masenqo_profile['final_highpass']), sample_rate)
    
    # Remove any remaining DC offset after filtering - CRITICAL
    audio = audio - np.mean(audio)
    
    # Very gentle saturation for warmth (also helps symmetry)
    saturation_drive = float(masenqo_profile['saturation_drive'])
    audio = np.tanh(audio * saturation_drive) / np.tanh(saturation_drive)
    
    # Remove any final DC offset after saturation
    audio = np.nan_to_num(audio - np.mean(audio), nan=0.0, posinf=0.0, neginf=0.0)
    
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
    add_ornament: bool = False,
    profile: str = 'alto_breathy',
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
    washint_profile = _resolve_washint_profile(profile)
    velocity = float(np.clip(velocity, 0.0, 1.0))
    num_samples = int(duration * sample_rate)
    if num_samples <= 0:
        return np.zeros(0, dtype=np.float64)

    t = np.arange(num_samples) / sample_rate
    register_focus = float(np.clip((frequency - 480.0) / 520.0, 0.0, 1.0))

    breath_rise = np.clip((t + 0.004) / (0.022 + 0.010 * (1.0 - velocity)), 0.0, 1.0)
    column_settle = np.clip((t - 0.014) / (0.105 + 0.035 * (1.0 - register_focus)), 0.0, 1.0)
    onset_gate = np.exp(-t / max(1e-4, 0.052 - 0.010 * register_focus))

    embouchure_drift = _slow_noise_contour(num_samples, sample_rate, 22.0)
    pressure_drift = _slow_noise_contour(num_samples, sample_rate, 12.0)
    jet_flutter = _slow_noise_contour(num_samples, sample_rate, 34.0)
    gesture_instability = _slow_noise_contour(num_samples, sample_rate, 18.0)

    flute_variant = float(np.clip(
        1.0 + 0.06 * np.mean(gesture_instability[: max(1, int(0.025 * sample_rate))]),
        0.88,
        1.12,
    ))
    register_instability = float(np.clip(frequency / 900.0, 0.45, 1.25))

    # === IRREGULAR VIBRATO / EMBROUCHURE MOTION ===
    # Washint pitch motion should feel pressure-led and unstable, not like a clean synth LFO.
    vibrato_rate = np.clip(
        4.4
        + 0.48 * np.sin(2 * np.pi * (0.40 + 0.10 * register_focus) * t + 0.25 * jet_flutter)
        + 0.24 * pressure_drift
        + 0.12 * jet_flutter,
        3.6,
        6.4,
    )
    vibrato_phase = 2 * np.pi * np.cumsum(vibrato_rate) / sample_rate
    vibrato_depth = float(washint_profile['vibrato_depth'])
    vibrato_onset = np.clip((t - 0.14) / 0.22, 0.0, 1.0)
    vibrato_increase = vibrato_onset * (1.0 + 0.35 * t / max(duration, 1e-6))
    vibrato_shape = (
        np.sin(vibrato_phase + 0.10 * embouchure_drift)
        + 0.22 * np.sin(2.0 * vibrato_phase + 0.40 + 0.12 * pressure_drift)
        + 0.10 * jet_flutter
    )
    pitch_motion = (
        vibrato_shape * vibrato_depth * vibrato_increase
        + embouchure_drift * 0.0012 * (0.60 + 0.40 * velocity)
        + pressure_drift * register_instability * (0.0015 * onset_gate + 0.00055)
        + gesture_instability * 0.0004 * (0.30 + 0.70 * column_settle)
    )
    phase = 2 * np.pi * np.cumsum(frequency * np.clip(1.0 + pitch_motion, 0.55, 1.80)) / sample_rate

    # === HARMONIC / COLUMN SEED ===
    # Keep the open-pipe odd-harmonic identity, but let the balance migrate from airy onset
    # to more settled tube focus as the column locks in.
    harmonic_motion = 0.50 * embouchure_drift + 0.30 * pressure_drift + 0.20 * gesture_instability
    harmonic_core = np.zeros(num_samples, dtype=np.float64)
    for idx, (harmonic, amp) in enumerate(zip([1, 3, 5, 7], washint_profile['harmonic_gains'])):
        if harmonic == 1:
            transition = 0.92 - 0.06 * onset_gate + 0.24 * column_settle * (1.0 - 0.25 * register_focus)
        elif harmonic == 3:
            transition = 0.88 + 0.12 * onset_gate + 0.10 * column_settle + 0.08 * register_focus
        elif harmonic == 5:
            transition = 0.72 + 0.28 * onset_gate + 0.14 * register_focus - 0.08 * column_settle
        else:
            transition = 0.62 + 0.34 * onset_gate + 0.18 * register_focus - 0.12 * column_settle

        dynamic_gain = amp * transition * (1.0 + harmonic_motion * (0.045 + 0.012 * idx))
        harmonic_core += dynamic_gain * np.sin(
            harmonic * phase
            + embouchure_drift * (0.012 + 0.003 * idx) * harmonic
            + pressure_drift * 0.006 * (idx + 1)
        )

    harmonic_core += (
        0.025 + 0.020 * onset_gate + 0.020 * register_focus
    ) * np.sin(2 * phase + 0.25 + 0.18 * gesture_instability)
    harmonic_core += (
        0.008 + 0.012 * onset_gate
    ) * np.sin(4 * phase + 0.55 + 0.10 * pressure_drift)

    # === BREATH / AIR-JET EXCITATION ===
    # Use breath as the exciter that drives the bore, instead of only layering filtered hiss.
    breath = np.random.randn(num_samples)
    jet_breath = bandpass_filter(
        breath,
        float(washint_profile['breath_low']),
        float(washint_profile['breath_high']),
        sample_rate,
    )
    tube_breath = bandpass_filter(
        breath,
        max(260.0, frequency * 0.52 * flute_variant),
        min(2800.0, frequency * 3.5 * flute_variant),
        sample_rate,
    )
    bore_breath = bandpass_filter(
        breath,
        max(220.0, frequency * 0.45),
        min(2400.0, frequency * (2.9 + 0.7 * register_focus)),
        sample_rate,
    )

    air_pressure = velocity * np.clip(
        0.54
        + 0.28 * breath_rise
        + pressure_drift * float(washint_profile['pressure_irregularity'])
        + onset_gate * (0.08 + 0.06 * register_focus),
        0.04,
        1.20,
    )
    jet_wave = np.sin(phase + 0.32 + embouchure_drift * 0.22 + jet_flutter * 0.10)
    jet_pulse = 0.5 + 0.5 * np.tanh(1.8 * (jet_wave + 0.50 * pressure_drift - 0.18 * gesture_instability))
    jet_vorticity = jet_breath * (0.42 + 0.58 * jet_pulse) * air_pressure
    jet_edge = bandpass_simple(
        jet_vorticity + harmonic_core * (0.04 + 0.07 * onset_gate),
        max(260.0, frequency * 0.78),
        min(5200.0, frequency * (4.8 + 1.4 * register_focus)),
        sample_rate,
    )
    jet_memory = lowpass_filter(np.abs(jet_edge), 34.0, sample_rate)
    jet_memory_peak = float(np.max(jet_memory)) if jet_memory.size else 0.0
    if jet_memory_peak > 1e-9:
        jet_memory = jet_memory / jet_memory_peak

    tube_driver = harmonic_core * 0.58 + jet_edge * (0.22 + 0.18 * breath_rise) + tube_breath * 0.08 * onset_gate
    tube_low = bandpass_simple(
        tube_driver,
        max(180.0, frequency * 0.72 * flute_variant),
        min(1800.0, frequency * 2.3 * flute_variant),
        sample_rate,
    )
    tube_mid = bandpass_simple(
        tube_driver + jet_edge * 0.22,
        max(260.0, frequency * 0.90),
        min(3000.0, frequency * (3.7 + 0.5 * flute_variant)),
        sample_rate,
    )
    tube_high = bandpass_simple(
        tube_driver + jet_edge * 0.48,
        max(1000.0, frequency * 1.65),
        min(4700.0, frequency * (4.8 + 1.4 * register_focus)),
        sample_rate,
    )

    column_seed = (
        tube_low * 0.34
        + tube_mid * 0.38
        + tube_high * (0.10 + 0.08 * register_focus)
        + jet_edge * 0.18
    )
    reflection_delay = max(
        1,
        int(
            (sample_rate / max(frequency, 1e-6))
            * np.clip((0.21 - 0.05 * register_focus) * flute_variant, 0.12, 0.24)
        ),
    )
    bore_reflection = np.zeros(num_samples, dtype=np.float64)
    if reflection_delay < num_samples:
        bore_reflection[reflection_delay:] = column_seed[:-reflection_delay]
    else:
        bore_reflection = column_seed.copy()
    bore_reflection = bandpass_simple(
        bore_reflection,
        max(200.0, frequency * 0.66 * flute_variant),
        min(3900.0, frequency * (3.4 + 1.8 * register_focus)),
        sample_rate,
    )
    column_edges = np.abs(np.diff(column_seed, prepend=column_seed[0]))
    column_edges = lowpass_filter(column_edges, 1200.0, sample_rate)
    column_peak = float(np.max(column_edges)) if column_edges.size else 0.0
    if column_peak > 1e-9:
        column_edges = column_edges / column_peak
    column_memory = lowpass_filter(np.abs(column_seed) + 0.30 * column_edges + 0.18 * np.abs(bore_reflection), 24.0, sample_rate)
    column_memory_peak = float(np.max(column_memory)) if column_memory.size else 0.0
    if column_memory_peak > 1e-9:
        column_memory = column_memory / column_memory_peak

    column_core = (
        tube_low * (0.22 + 0.16 * column_settle * (1.0 - register_focus))
        + tube_mid * (0.28 + 0.16 * column_settle)
        + tube_high * (
            0.06
            + (0.10 + float(washint_profile['focus_shift']))
            * column_settle
            * (0.35 + 0.65 * register_focus)
        )
        + bore_reflection * (0.10 + 0.12 * register_focus + 0.08 * column_memory)
    )
    audio = (
        harmonic_core * (0.26 + 0.10 * onset_gate)
        + column_core
        + jet_edge * (
            0.05
            + float(washint_profile['jet_drive']) * onset_gate
            + 0.05 * jet_memory
        )
    )

    jet_envelope = (
        np.exp(-t / 0.042) * float(washint_profile['breath_attack_scale']) * (1.20 + 0.18 * register_focus)
        + float(washint_profile['breath_floor']) * (0.14 + 0.18 * jet_pulse + 0.18 * jet_memory)
    ) * velocity
    tube_air_envelope = (
        0.08 + 0.92 * column_settle
    ) * (0.72 + 0.28 * (1.0 - register_focus)) * velocity
    bore_air_envelope = (
        0.05 + 0.95 * column_settle
    ) * (0.38 + 0.62 * register_focus + 0.18 * column_memory) * velocity
    jet_coupling = np.clip(
        0.18 + 0.22 * column_edges + 0.28 * jet_pulse + 0.24 * jet_memory + 0.08 * pressure_drift,
        0.05,
        1.60,
    )
    bore_coupling = np.clip(
        0.20 + 0.24 * column_memory + 0.26 * register_focus + 0.18 * np.maximum(pressure_drift, 0.0),
        0.10,
        1.60,
    )

    audio += (
        jet_breath
        * jet_envelope
        * jet_coupling
        * float(washint_profile['breath_amount'])
        * (0.36 + 0.18 * float(washint_profile['jet_drive']))
    )
    audio += (
        tube_breath
        * tube_air_envelope
        * (0.010 + float(washint_profile['breath_amount']) * 0.060)
        * (0.40 + 0.60 * column_memory)
    )
    audio += (
        bore_breath
        * bore_air_envelope
        * (0.008 + float(washint_profile['breath_amount']) * 0.045 + 0.015 * float(washint_profile['jet_drive']))
        * bore_coupling
    )

    # === PROFILE-AWARE ENTRY ORNAMENT ===
    # Keep a subtle entry graze by default, but let add_ornament materially reshape the note entry.
    if duration > 0.18 and velocity > 0.35:
        ornament_seconds = float(washint_profile['ornament_seconds']) * (1.65 if add_ornament else 0.72)
        ornament_duration = min(num_samples, int(ornament_seconds * sample_rate))
        if ornament_duration > 4:
            ornament_t = np.arange(ornament_duration) / sample_rate
            ornament_direction = float(washint_profile['ornament_direction'])
            ornament_ratio = float(washint_profile['ornament_ratio']) * (1.25 if add_ornament else 0.55)
            start_ratio = 1.0 + ornament_direction * ornament_ratio
            arrival_curve = np.clip(
                (ornament_t / max(ornament_seconds, 1e-6)) ** (0.55 if ornament_direction < 0.0 else 0.72),
                0.0,
                1.0,
            )
            ornament_freq = frequency * (start_ratio + (1.0 - start_ratio) * arrival_curve)
            ornament_phase = 2 * np.pi * np.cumsum(ornament_freq) / sample_rate
            ornament_core = np.sin(ornament_phase)
            ornament_core += 0.22 * np.sin(
                3 * ornament_phase + 0.18 + 0.08 * embouchure_drift[:ornament_duration]
            )
            ornament_air = bandpass_simple(
                jet_breath[:ornament_duration] * (0.62 + 0.38 * jet_pulse[:ornament_duration]),
                max(1200.0, frequency * 1.15),
                min(float(washint_profile['presence_high']) * 1.08, sample_rate / 2 - 100.0),
                sample_rate,
            )
            ornament_shape = np.exp(
                -ornament_t / max(1e-4, ornament_seconds * (0.38 if add_ornament else 0.30))
            )
            ornament_shape *= np.linspace(1.0, 0.10 if add_ornament else 0.0, ornament_duration)
            ornament_mix = float(washint_profile['grace_gain']) * (0.16 + 0.52 * float(add_ornament)) * velocity
            audio[:ornament_duration] += (
                ornament_core * 0.56 + ornament_air * 0.44
            ) * ornament_shape * ornament_mix
    
    # === BODY RESONANCE (bamboo tube) ===
    # Bamboo has characteristic resonances
    body_resonances = [
        max(210.0, frequency * (0.96 + 0.04 * flute_variant)),
        min(2400.0, frequency * (2.05 + 0.20 * flute_variant)),
        min(3600.0, max(1350.0, frequency * (4.3 + 0.9 * register_focus))),
        min(
            4600.0,
            max(
                2150.0,
                frequency * (5.0 + 1.4 * register_focus + float(washint_profile['focus_shift'])),
            ),
        ),
    ]
    body_qs = [18, 12, 7, 4]
    hollow_column = _apply_body_resonance(audio + bore_reflection * 0.12 + jet_edge * 0.08, body_resonances, body_qs, sample_rate)

    woody_shell = bandpass_simple(
        hollow_column + tube_low * 0.30,
        max(220.0, frequency * 0.70),
        min(1900.0, frequency * 2.6),
        sample_rate,
    )

    lower_tube_focus = bandpass_simple(
        hollow_column + tube_mid * 0.28,
        max(220.0, frequency * 0.82),
        min(2500.0, frequency * (3.1 + 0.3 * flute_variant)),
        sample_rate,
    )
    upper_tube_focus = bandpass_simple(
        hollow_column + bore_reflection * 0.55 + tube_high * 0.40,
        max(1100.0, frequency * 1.65),
        min(4600.0, frequency * (4.7 + 1.9 * register_focus)),
        sample_rate,
    )
    sustain_focus = np.clip((t - 0.025) / 0.14, 0.0, 1.0)
    audio = (
        hollow_column * (0.40 + 0.14 * sustain_focus)
        + woody_shell * (0.11 + 0.05 * (1.0 - register_focus))
        + lower_tube_focus * (0.16 + 0.10 * sustain_focus * (1.0 - register_focus))
        + upper_tube_focus * (
            0.05
            + (0.10 + float(washint_profile['focus_shift']))
            * sustain_focus
            * (0.30 + 0.70 * register_focus)
        )
        + audio * (0.12 + 0.06 * onset_gate + 0.04 * jet_memory)
        + jet_edge * (0.04 + 0.12 * onset_gate)
    )

    presence_band = bandpass_simple(
        jet_edge * (0.70 + 0.30 * jet_memory)
        + upper_tube_focus * (0.32 + 0.36 * sustain_focus)
        + bore_reflection * 0.18,
        float(washint_profile['presence_low']),
        float(washint_profile['presence_high']),
        sample_rate,
    )
    audio += (
        presence_band
        * float(washint_profile['presence_gain'])
        * (0.30 * onset_gate + (0.12 + 0.22 * register_focus) * sustain_focus + 0.18 * jet_memory)
    )

    chiff = bandpass_simple(
        jet_breath * (0.44 + 0.56 * jet_pulse) + jet_edge * 0.26,
        float(washint_profile['chiff_low']),
        float(washint_profile['chiff_high']),
        sample_rate,
    )
    audio += (
        chiff
        * np.exp(-t / max(1e-4, float(washint_profile['chiff_decay'])))
        * (0.20 + 0.44 * jet_pulse + 0.18 * jet_memory + 0.18 * column_edges)
        * float(washint_profile['chiff_amount'])
        * velocity
    )
    
    # === ENVELOPE ===
    # Soft attack (breath building), sustained, soft release
    attack = int(float(washint_profile['attack_seconds']) * sample_rate)
    decay = int(float(washint_profile['decay_seconds']) * sample_rate)
    sustain_level = float(washint_profile['sustain_level'])
    release = int(float(washint_profile['release_seconds']) * sample_rate)
    sustain_samples = max(0, num_samples - attack - decay - release)
    
    audio = apply_envelope(audio, attack, decay, sustain_level, release, sustain_samples)
    
    # === FINAL PROCESSING ===
    # Clarity boost
    audio = add_saturation(audio, 0.06 + 0.01 * float(washint_profile['jet_drive']))
    audio = highpass_filter(audio, float(washint_profile['final_highpass']), sample_rate)
    audio = lowpass_filter(audio, float(washint_profile['final_lowpass']), sample_rate)
    audio = np.nan_to_num(audio - np.mean(audio), nan=0.0, posinf=0.0, neginf=0.0)
    
    return normalize_audio(audio, 0.72 * velocity)


def _resolve_begena_profile(profile: str) -> Dict[str, object]:
    """Return bounded Begena synthesis parameters for the requested profile."""
    normalized = str(profile or 'paraliturgical_drone').strip().lower().replace('-', '_').replace(' ', '_')
    if normalized in {'liturgical_drone', 'meditative_drone', 'sacred_drone'}:
        normalized = 'paraliturgical_drone'

    profiles: Dict[str, Dict[str, object]] = {
        'paraliturgical_drone': {
            'main_smoothing_passes': 32,
            'damping_base': 0.99885,
            'damping_sustain_scale': 0.00120,
            'buzz_smoothing_passes': 12,
            'buzz_damping_base': 0.99605,
            'buzz_damping_sustain_scale': 0.00110,
            'buzz_mix': 0.12,
            'buzz_persistence_base': 0.44,
            'buzz_persistence_scale': 0.72,
            'sympathetic_ratios': (1.5, 2.0, 3.0, 4.0),
            'sympathetic_gains': (0.030, 0.028, 0.020, 0.012),
            'sympathetic_decay_base': 0.84,
            'sympathetic_decay_scale': 0.76,
            'body_low': 72.0,
            'body_high': 240.0,
            'body_gain': 0.28,
            'body_low_mid_low': 230.0,
            'body_low_mid_high': 495.0,
            'body_low_mid_gain': 2.20,
            'body_mode_ratios': (2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0),
            'body_mode_gains': (0.006, 0.095, 0.165, 0.200, 0.190, 0.155, 0.115, 0.080),
            'body_mode_gain': 2.25,
            'attack_base_seconds': 0.078,
            'attack_sustain_scale': 0.012,
            'release_base_seconds': 0.12,
            'release_sustain_scale': 0.14,
            'bass_boost_gain': 0.22,
            'sub_bass_gain': 0.035,
            'roughness_lowpass_base': 360.0,
            'roughness_lowpass_span': 28.0,
            'final_lowpass': 520.0,
            'final_highpass': 42.0,
        },
        'mp3_reference_bright': {
            'main_smoothing_passes': 18,
            'damping_base': 0.99825,
            'damping_sustain_scale': 0.00070,
            'buzz_smoothing_passes': 6,
            'buzz_damping_base': 0.99545,
            'buzz_damping_sustain_scale': 0.00062,
            'buzz_mix': 0.155,
            'buzz_persistence_base': 0.24,
            'buzz_persistence_scale': 0.38,
            'sympathetic_ratios': (1.5, 2.0, 2.5, 3.0),
            'sympathetic_gains': (0.017, 0.016, 0.011, 0.008),
            'sympathetic_decay_base': 0.46,
            'sympathetic_decay_scale': 0.42,
            'body_low': 72.0,
            'body_high': 230.0,
            'body_gain': 0.15,
            'body_low_mid_low': 230.0,
            'body_low_mid_high': 480.0,
            'body_low_mid_gain': 0.78,
            'body_mode_ratios': (2.0, 3.0, 4.0, 5.0, 6.0),
            'body_mode_gains': (0.004, 0.040, 0.070, 0.080, 0.060),
            'body_mode_gain': 0.72,
            'attack_base_seconds': 0.040,
            'attack_sustain_scale': 0.006,
            'release_base_seconds': 0.060,
            'release_sustain_scale': 0.065,
            'bass_boost_gain': 0.070,
            'sub_bass_gain': 0.008,
            'roughness_lowpass_base': 900.0,
            'roughness_lowpass_span': 170.0,
            'roughness_component_lowpass_cap': 1800.0,
            'roughness_cluster_high': 2200.0,
            'roughness_cluster_ratio': 22.0,
            'contact_surface_gain': 0.070,
            'contact_surface_noise_gain': 0.010,
            'contact_surface_decay': 0.42,
            'presence_boost_gain': 0.085,
            'presence_band_low': 420.0,
            'presence_band_high': 2800.0,
            'final_lowpass': 6200.0,
            'final_highpass': 50.0,
        },
    }
    return profiles.get(normalized, profiles['paraliturgical_drone'])


def _resolve_begena_string_quality(string_quality: str) -> Dict[str, float]:
    """Return bounded Begena string-quality parameters."""
    normalized = str(string_quality or 'stable').strip().lower().replace('-', '_').replace(' ', '_')
    qualities: Dict[str, Dict[str, float]] = {
        'stable': {
            'roughness_gain': 0.72,
            'roughness_depth': 0.032,
            'spread_scale': 0.90,
            'main_damping_delta': 0.0,
            'buzz_damping_delta': 0.0,
            'buzz_persistence_delta': 0.0,
            'body_gain': 1.28,
            'sympathetic_gain': 1.00,
            'attack_softness': 1.00,
            'presence_gain': 0.50,
        },
        'worn': {
            'roughness_gain': 0.84,
            'roughness_depth': 0.055,
            'spread_scale': 1.00,
            'main_damping_delta': -0.00018,
            'buzz_damping_delta': -0.00022,
            'buzz_persistence_delta': -0.05,
            'body_gain': 1.34,
            'sympathetic_gain': 0.94,
            'attack_softness': 1.10,
            'presence_gain': 0.58,
        },
        'lively': {
            'roughness_gain': 0.86,
            'roughness_depth': 0.050,
            'spread_scale': 0.86,
            'main_damping_delta': 0.00008,
            'buzz_damping_delta': 0.00010,
            'buzz_persistence_delta': 0.05,
            'body_gain': 1.42,
            'sympathetic_gain': 1.06,
            'attack_softness': 0.92,
            'presence_gain': 0.68,
        },
    }
    return qualities.get(normalized, qualities['stable'])


def _generate_begena_delay_line(
    num_samples: int,
    period_samples: int,
    damping: float,
    smoothing_passes: int,
    kernel: Tuple[float, float, float] = (0.2, 0.6, 0.2),
) -> np.ndarray:
    """Generate a softly excited Karplus-Strong-style delay line for Begena."""
    if num_samples <= 0:
        return np.zeros(0, dtype=np.float64)

    period_samples = max(2, int(period_samples))
    excitation = np.random.randn(period_samples)
    smoothing_kernel = np.asarray(kernel, dtype=np.float64)
    kernel_sum = float(np.sum(smoothing_kernel))
    if kernel_sum > 1e-12:
        smoothing_kernel = smoothing_kernel / kernel_sum

    for _ in range(max(0, int(smoothing_passes))):
        excitation = np.convolve(excitation, smoothing_kernel, mode='same')

    output = np.zeros(num_samples, dtype=np.float64)
    delay_line = excitation.astype(np.float64, copy=True)
    write_pos = 0
    damping = float(damping)

    for i in range(num_samples):
        read_pos = (write_pos + 1) % period_samples
        next_pos = (read_pos + 1) % period_samples
        filtered = 0.5 * (delay_line[read_pos] + delay_line[next_pos])
        filtered *= damping
        output[i] = filtered
        delay_line[write_pos] = filtered
        write_pos = (write_pos + 1) % period_samples

    return output


def _generate_begena_buzz_cluster(
    frequency: float,
    duration: float,
    sample_rate: int,
    *,
    buzzers_enabled: bool,
    buzzer_position: float,
    sustain_bias: float,
    begena_profile: Dict[str, object],
    string_profile: Dict[str, float],
) -> np.ndarray:
    """Generate a small quasi-harmonic roughness cluster for the Begena buzz."""
    num_samples = int(duration * sample_rate)
    if not buzzers_enabled or num_samples <= 0:
        return np.zeros(0, dtype=np.float64)

    t = np.arange(num_samples, dtype=np.float64) / sample_rate
    position = float(np.clip(buzzer_position, 0.05, 0.95))
    spread = (0.0022 + 0.0048 * position) * float(string_profile['spread_scale'])
    buzz_damping = np.clip(
        float(begena_profile['buzz_damping_base'])
        + sustain_bias * float(begena_profile['buzz_damping_sustain_scale'])
        + float(string_profile['buzz_damping_delta']),
        0.9930,
        0.9994,
    )

    component_specs = [
        (1.0, -0.80 * spread, 0.24),
        (1.0, 0.55 * spread, 0.18),
        (2.0, -0.35 * spread, 0.09 + 0.02 * position),
    ]
    if position > 0.42 or float(string_profile['roughness_gain']) > 1.08:
        component_specs.append((1.5, 0.90 * spread, 0.07 + 0.01 * position))

    cluster = np.zeros(num_samples, dtype=np.float64)
    for idx, (ratio, detune, gain) in enumerate(component_specs):
        component_freq = max(35.0, frequency * ratio * (1.0 + detune))
        if component_freq >= sample_rate / 2 - 120:
            continue

        component = _generate_begena_delay_line(
            num_samples,
            period_samples=int(sample_rate / component_freq),
            damping=np.clip(buzz_damping - idx * 0.00010, 0.9925, 0.9994),
            smoothing_passes=int(begena_profile['buzz_smoothing_passes']) + (2 if ratio > 1.0 else 0),
            kernel=(0.24, 0.52, 0.24),
        )
        component = lowpass_filter(
            component,
            min(
                float(begena_profile.get('roughness_component_lowpass_cap', 520.0)),
                float(begena_profile['roughness_lowpass_base'])
                + ratio * float(begena_profile['roughness_lowpass_span']),
            ),
            sample_rate,
        )
        cluster += component * gain

    low_mid_contact = np.zeros(num_samples, dtype=np.float64)
    contact_drift = _slow_noise_contour(num_samples, sample_rate, lowpass_hz=3.0 + 4.0 * position)
    for idx, (ratio, gain) in enumerate(((3.0, 0.060), (4.0, 0.090), (5.0, 0.075))):
        contact_freq = frequency * ratio * (1.0 + (idx - 1) * spread * 0.35)
        if 180.0 <= contact_freq <= 500.0 and contact_freq < sample_rate / 2 - 120:
            phase = 2 * np.pi * contact_freq * t + contact_drift * (0.010 + 0.001 * ratio) + idx * 0.65
            low_mid_contact += gain * np.sin(phase)
    if np.any(low_mid_contact):
        low_mid_contact = bandpass_simple(low_mid_contact, 180.0, 500.0, sample_rate)
        cluster += low_mid_contact * (0.78 + 0.22 * position)

    contour = _slow_noise_contour(num_samples, sample_rate, lowpass_hz=4.0 + 6.0 * position)
    contour = np.clip(1.0 + float(string_profile['roughness_depth']) * contour, 0.84, 1.16)
    contact_ramp = np.clip(t / max(1e-4, 0.018 + 0.030 * (1.0 - position)), 0.0, 1.0)
    persistence = np.exp(
        -t / max(
            0.20,
            float(begena_profile['buzz_persistence_base'])
            + sustain_bias * float(begena_profile['buzz_persistence_scale'])
            + float(string_profile['buzz_persistence_delta']),
        )
    )
    cluster = bandpass_simple(
        cluster,
        max(45.0, frequency * 0.60),
        min(
            float(begena_profile.get('roughness_cluster_high', 540.0)),
            max(360.0, frequency * float(begena_profile.get('roughness_cluster_ratio', 5.8))),
        ),
        sample_rate,
    )
    cluster *= contour * (0.35 + 0.65 * contact_ramp) * persistence
    return cluster * float(begena_profile['buzz_mix']) * float(string_profile['roughness_gain'])


def generate_begena_tone(
    frequency: float,
    duration: float = 1.0,
    velocity: float = 0.7,
    sample_rate: int = SAMPLE_RATE,
    profile: str = 'paraliturgical_drone',
    buzzers_enabled: bool = True,
    buzzer_position: float = 0.35,
    string_quality: str = 'stable',
    sustain_bias: float = 0.8,
) -> np.ndarray:
    """
    Generate authentic Begena (ባገና) - Ethiopian 10-string bass lyre.

    PHYSICAL MODELING with Karplus-Strong + characteristic structured roughness.

    The Begena has a unique buzzing quality from leather pieces (enzirotch)
    wrapped around strings near the bridge. This creates beating/roughness
    between slightly detuned frequency components - NOT plain noise.

    Based on acoustic measurements:
    - Pitch range: 50-150 Hz (VERY low bass)
    - Characteristic "roughness" from leather buzzers
    - Long, meditative sustain
    - Deep, spiritual quality
    """
    num_samples = int(duration * sample_rate)
    if num_samples <= 0:
        return np.zeros(0, dtype=np.float64)

    frequency = max(1.0, float(frequency))
    sustain_bias = float(np.clip(sustain_bias, 0.0, 1.0))
    buzzer_position = float(np.clip(buzzer_position, 0.05, 0.95))
    t = np.arange(num_samples, dtype=np.float64) / sample_rate

    begena_profile = _resolve_begena_profile(profile)
    string_profile = _resolve_begena_string_quality(string_quality)

    # === KARPLUS-STRONG FOR MAIN STRING ===
    main_damping = np.clip(
        float(begena_profile['damping_base'])
        + sustain_bias * float(begena_profile['damping_sustain_scale'])
        + float(string_profile['main_damping_delta']),
        0.9960,
        0.99985,
    )
    output = _generate_begena_delay_line(
        num_samples,
        period_samples=int(sample_rate / frequency),
        damping=main_damping,
        smoothing_passes=int(begena_profile['main_smoothing_passes']),
    )

    # === STRUCTURED LEATHER-BUZZ ROUGHNESS ===
    if buzzers_enabled:
        output = output * 0.64 + _generate_begena_buzz_cluster(
            frequency,
            duration,
            sample_rate,
            buzzers_enabled=buzzers_enabled,
            buzzer_position=buzzer_position,
            sustain_bias=sustain_bias,
            begena_profile=begena_profile,
            string_profile=string_profile,
        )
    else:
        output *= 0.90

    # === SYMPATHETIC STRINGS ===
    sympathetic_decay = np.exp(
        -t / max(
            0.20,
            float(begena_profile['sympathetic_decay_base'])
            + sustain_bias * float(begena_profile['sympathetic_decay_scale']),
        )
    )
    sympathetic_gate = np.clip((t - 0.05) / 0.18, 0.0, 1.0)
    sympathetic_drift = _slow_noise_contour(num_samples, sample_rate, 10.0)
    for ratio, gain in zip(
        begena_profile['sympathetic_ratios'],
        begena_profile['sympathetic_gains'],
    ):
        symp_freq = frequency * float(ratio)
        if symp_freq < sample_rate / 2 - 120:
            output += (
                float(gain)
                * float(string_profile['sympathetic_gain'])
                * np.sin(2 * np.pi * symp_freq * t + sympathetic_drift * (0.012 * float(ratio)))
                * sympathetic_gate
                * sympathetic_decay
            )

    # === BODY RESONANCE ===
    body = bandpass_simple(
        output,
        float(begena_profile['body_low']),
        float(begena_profile['body_high']),
        sample_rate,
    )
    output = output + body * float(begena_profile['body_gain']) * float(string_profile['body_gain'])

    # Low-mid skin/box body reinforcement: a Begena-sized soundboard should
    # carry weight in the 180-520 Hz body band rather than turning the buzzer
    # into broadband edge.  These modes are quasi-harmonic multiples of the
    # plucked string and remain low/low-mid after filtering.
    body_low_mid = bandpass_simple(
        output,
        float(begena_profile['body_low_mid_low']),
        float(begena_profile['body_low_mid_high']),
        sample_rate,
    )
    output = output + body_low_mid * float(begena_profile['body_low_mid_gain']) * float(string_profile['body_gain'])

    body_modes = np.zeros(num_samples, dtype=np.float64)
    mode_drift = _slow_noise_contour(num_samples, sample_rate, lowpass_hz=4.0)
    for ratio, gain in zip(
        begena_profile['body_mode_ratios'],
        begena_profile['body_mode_gains'],
    ):
        mode_freq = frequency * float(ratio)
        if 150.0 <= mode_freq <= 500.0 and mode_freq < sample_rate / 2 - 120:
            phase = 2 * np.pi * mode_freq * t + mode_drift * (0.010 + 0.0015 * float(ratio))
            body_modes += float(gain) * np.sin(phase)
    if np.any(body_modes):
        mode_gate = np.clip(t / 0.055, 0.0, 1.0)
        mode_decay = np.exp(-t / max(0.42, 0.72 + 1.20 * sustain_bias))
        body_modes = bandpass_simple(
            body_modes,
            float(begena_profile['body_low_mid_low']),
            float(begena_profile['body_low_mid_high']),
            sample_rate,
        )
        output += (
            body_modes
            * mode_gate
            * mode_decay
            * float(begena_profile['body_mode_gain'])
            * float(string_profile['body_gain'])
        )

    skin_box_modes = np.zeros(num_samples, dtype=np.float64)
    for idx, (ratio, gain) in enumerate(((3.0, 0.070), (4.0, 0.120), (5.0, 0.135), (6.0, 0.115), (7.0, 0.085), (8.0, 0.060))):
        mode_freq = frequency * ratio
        if 250.0 <= mode_freq <= 495.0 and mode_freq < sample_rate / 2 - 120:
            phase = 2 * np.pi * mode_freq * t + mode_drift * (0.006 + 0.001 * idx) + idx * 0.31
            skin_box_modes += gain * np.sin(phase)
    if np.any(skin_box_modes):
        skin_gate = np.clip((t - 0.018) / 0.090, 0.0, 1.0)
        skin_decay = np.exp(-t / max(0.55, 0.86 + 1.35 * sustain_bias))
        skin_box_modes = bandpass_simple(skin_box_modes, 250.0, 495.0, sample_rate)
        output += skin_box_modes * skin_gate * skin_decay * 1.25 * float(string_profile['body_gain'])

    contact_surface_gain = float(begena_profile.get('contact_surface_gain', 0.0))
    if buzzers_enabled and contact_surface_gain > 0.0:
        contact_surface = np.zeros(num_samples, dtype=np.float64)
        surface_drift = _slow_noise_contour(num_samples, sample_rate, lowpass_hz=18.0)
        surface_ratios = (5.0, 6.0, 7.0, 8.5, 10.0, 12.0, 15.0, 18.0, 22.0, 27.0, 34.0, 43.0, 55.0)
        for idx, ratio in enumerate(surface_ratios):
            partial_freq = frequency * ratio * (1.0 + (idx % 3 - 1) * 0.0018)
            if 520.0 <= partial_freq <= min(7600.0, sample_rate / 2 - 160.0):
                partial_gain = (0.060 / (1.0 + idx * 0.18)) * (0.80 + 0.20 * buzzer_position)
                phase = 2 * np.pi * partial_freq * t + surface_drift * (0.010 + 0.0007 * ratio) + idx * 0.41
                contact_surface += partial_gain * np.sin(phase)
        if np.any(contact_surface):
            contact_surface = bandpass_simple(
                contact_surface,
                520.0,
                min(float(begena_profile['final_lowpass']) * 1.10, sample_rate / 2 - 140.0),
                sample_rate,
            )
            surface_gate = np.clip(t / 0.018, 0.0, 1.0)
            surface_decay = np.exp(-t / max(0.16, float(begena_profile.get('contact_surface_decay', 0.42)) + 0.28 * sustain_bias))
            surface_flutter = np.clip(1.0 + 0.06 * surface_drift, 0.86, 1.14)
            output += contact_surface * surface_gate * surface_decay * surface_flutter * contact_surface_gain * float(string_profile['presence_gain'])

        contact_noise_gain = float(begena_profile.get('contact_surface_noise_gain', 0.0))
        if contact_noise_gain > 0.0:
            contact_noise = bandpass_filter(
                np.random.randn(num_samples),
                2200.0,
                min(float(begena_profile['final_lowpass']) * 1.25, sample_rate / 2 - 160.0),
                sample_rate,
            )
            noise_gate = np.clip(t / 0.010, 0.0, 1.0) * np.exp(-t / max(0.12, 0.22 + 0.22 * sustain_bias))
            output += contact_noise * noise_gate * contact_noise_gain * (0.68 + 0.32 * float(string_profile['presence_gain']))

    sustain_support = lowpass_filter(output, 300.0, sample_rate)
    sustain_envelope = np.exp(-t / max(0.30, 0.48 + 1.70 * sustain_bias))
    sustain_late_ramp = np.clip((t - 0.16) / 0.58, 0.0, 1.0)
    output += (
        sustain_support
        * (0.025 + 0.24 * (sustain_bias ** 1.35))
        * sustain_envelope
        * (0.25 + 0.75 * sustain_late_ramp)
    )

    # === ENVELOPE ===
    envelope = np.ones(num_samples, dtype=np.float64)
    attack_seconds = (
        float(begena_profile['attack_base_seconds'])
        + sustain_bias * float(begena_profile['attack_sustain_scale']) * 0.20
    ) * float(string_profile['attack_softness'])
    attack_samples = int(attack_seconds * sample_rate)
    if attack_samples > 0 and attack_samples < num_samples:
        attack_t = np.arange(attack_samples, dtype=np.float64) / max(1, attack_samples)
        envelope[:attack_samples] = 0.5 * (1.0 - np.cos(np.pi * attack_t))

    release_seconds = min(
        duration,
        float(begena_profile['release_base_seconds'])
        + sustain_bias * float(begena_profile['release_sustain_scale']),
    )
    release_samples = int(release_seconds * sample_rate)
    if release_samples > 0 and release_samples < num_samples:
        release_start = num_samples - release_samples
        release_t = np.arange(release_samples, dtype=np.float64) / max(1, release_samples)
        envelope[release_start:] *= 0.5 * (1.0 + np.cos(np.pi * release_t))

    output *= envelope

    body_hold = lowpass_filter(output, 320.0, sample_rate)
    body_hold_ramp = np.clip((t - max(0.16, attack_seconds)) / 0.72, 0.0, 1.0)
    body_hold_decay = np.exp(-t / max(0.35, 0.66 + 2.35 * sustain_bias))
    output += body_hold * (0.02 + 0.55 * (sustain_bias ** 1.40)) * body_hold_ramp * body_hold_decay

    # === FINAL PROCESSING ===
    # Begena should rumble like a prayer - felt more than heard.
    bass_boost = lowpass_filter(output, 150, sample_rate)
    output = output + bass_boost * float(begena_profile['bass_boost_gain'])

    sub_bass = lowpass_filter(output, 80, sample_rate)
    output = output + sub_bass * float(begena_profile['sub_bass_gain'])

    if buzzers_enabled:
        presence_low = float(begena_profile.get('presence_band_low', max(120.0, frequency * 0.95)))
        presence_high = float(begena_profile.get('presence_band_high', min(520.0, frequency * 4.6)))
        presence_high = max(presence_low + 20.0, min(presence_high, sample_rate / 2 - 120.0))
        presence = bandpass_simple(output, presence_low, presence_high, sample_rate)
        output += presence * float(begena_profile.get('presence_boost_gain', 0.024)) * float(string_profile['presence_gain'])

    output = add_saturation(output, 0.025)
    output = lowpass_filter(output, float(begena_profile['final_lowpass']), sample_rate)
    output = lowpass_filter(output, float(begena_profile['final_lowpass']) * 0.98, sample_rate)
    output = highpass_filter(output, float(begena_profile['final_highpass']), sample_rate)
    output = highpass_filter(output, float(begena_profile['final_highpass']) * 0.88, sample_rate)
    output = np.nan_to_num(output - np.mean(output), nan=0.0, posinf=0.0, neginf=0.0)

    return normalize_audio(output, 1.0 * velocity) if np.any(output) else output


def generate_brass_tone(
    frequency: float,
    duration: float = 0.5,
    velocity: float = 0.8,
    sample_rate: int = SAMPLE_RATE,
    voice: object = None,
) -> np.ndarray:
    """
    Generate brass-like tone for Ethio-jazz style.

    Characteristic of Mulatu Astatke's Ethio-jazz fusion - bright, punchy
    brass with soul/funk influence. Deterministic (seeded per note) and
    velocity-expressive: the defining brass cue is that louder playing pushes
    far more upper-harmonic energy (the tone "blooms" and brightens), driven
    here by a velocity-scaled harmonic profile and filter envelope plus a
    pressure-scaled lip-reed "blat" attack.
    """
    num_samples = int(duration * sample_rate)
    if num_samples <= 0:
        return np.zeros(0, dtype=np.float32)

    velocity = float(np.clip(velocity, 0.0, 1.0))
    t = np.arange(num_samples) / sample_rate
    rng = _seeded_rng(frequency, duration, velocity)
    vmap = apply_velocity_map(
        velocity,
        velocity_map=getattr(voice, "velocity_map", None),
        cutoff_delta_hz=4000.0,
        transient_level=1.0,
        noise_level=1.0,
    )

    audio = np.zeros(num_samples, dtype=np.float64)

    # === BRASS OSCILLATOR (upper harmonics grow with playing intensity) ===
    brightness = 0.4 + 0.6 * velocity
    for i in range(1, 14):
        harmonic_freq = frequency * i
        if harmonic_freq >= sample_rate / 2 - 200:
            break
        if i <= 3:
            amp = 1.0 / i
        elif i <= 6:
            amp = (0.6 + 0.4 * brightness) / i
        else:
            amp = (0.15 + 0.55 * brightness) / i
        audio += amp * np.sin(2 * np.pi * harmonic_freq * t)

    # === LIP-REED ATTACK TRANSIENT ("blat", pressure ~ velocity) ===
    attack_noise = rng.standard_normal(num_samples) * (0.5 + velocity)
    attack_env = np.exp(-t / 0.008)  # 8ms decay
    attack_noise *= attack_env
    attack_noise = highpass_filter(attack_noise, 800, sample_rate)
    attack_noise = lowpass_filter(attack_noise, 4000, sample_rate)
    audio += attack_noise * (0.12 + 0.16 * vmap["transient_level"])

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

    # === VELOCITY-DRIVEN BRIGHTNESS BLOOM ===
    fe = resolve_filter_envelope_params(
        voice, attack_ms=12.0, decay_ms=120.0, sustain_level=0.6, release_ms=100.0, amount_hz=2500.0
    )
    base_cutoff = 1800.0 + 2600.0 * velocity
    audio = apply_filter_envelope(
        audio,
        base_cutoff,
        attack_ms=fe["attack_ms"],
        decay_ms=fe["decay_ms"],
        sustain_level=fe["sustain_level"],
        release_ms=fe["release_ms"],
        amount_hz=fe["amount_hz"] + vmap["cutoff_delta_hz"],
        sample_rate=sample_rate,
    )
    audio = highpass_filter(audio, 120, sample_rate)

    audio = np.nan_to_num(audio, nan=0.0, posinf=0.0, neginf=0.0)
    return normalize_audio(audio, 0.75 * velocity).astype(np.float32)


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
    if num_samples <= 0:
        return np.zeros(0)

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
    click_duration = min(int(0.005 * sample_rate), len(audio))
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


# ── Orchestral Synthesis Functions ─────────────────────────────────────


def generate_strings_tone(
    frequency: float,
    duration: float = 0.5,
    velocity: float = 0.8,
    sample_rate: int = SAMPLE_RATE
) -> np.ndarray:
    """Generate Western orchestral string ensemble tone.

    Models a section of bowed strings (violins/violas/cellos) with:
    - Slow, smooth bow attack
    - Rich harmonics with natural decay profile
    - Subtle ensemble chorus (multiple detuned voices)
    - Gentle vibrato onset after initial attack
    """
    num_samples = int(duration * sample_rate)
    t = np.arange(num_samples) / sample_rate
    audio = np.zeros(num_samples)

    # --- Ensemble voices (4 slightly detuned players) ---
    detune_cents = [-6, -2, 2, 6]
    for cents in detune_cents:
        ratio = 2 ** (cents / 1200)
        freq = frequency * ratio

        voice = np.zeros(num_samples)
        # Bowed string harmonic profile: strong odd harmonics, weaker even
        for n in range(1, 14):
            harmonic_freq = freq * n
            if harmonic_freq > sample_rate / 2 - 200:
                break
            if n % 2 == 1:  # odd harmonics stronger (bowed string characteristic)
                amp = 1.0 / (n ** 1.05)
            else:
                amp = 0.6 / (n ** 1.15)
            # Higher partials decay faster
            partial_decay = max(0.08, duration * 0.9 / (1 + 0.15 * n))
            env = np.exp(-t / partial_decay)
            voice += amp * np.sin(2 * np.pi * harmonic_freq * t) * env

        audio += voice * 0.25

    # --- Delayed vibrato (bow vibrato, not finger) ---
    if duration > 0.25:
        vib_rate = 5.0 + np.random.uniform(-0.5, 0.5)
        vib_depth = 0.004
        vib_onset = np.clip((t - 0.18) / 0.15, 0, 1)
        vibrato = np.sin(2 * np.pi * vib_rate * t) * vib_depth * vib_onset

        vib_audio = np.zeros(num_samples)
        for n in range(1, 8):
            amp = 0.8 / (n ** 1.1) if n % 2 == 1 else 0.5 / (n ** 1.2)
            vib_audio += amp * np.sin(2 * np.pi * frequency * n * (t + vibrato))
        audio = audio * 0.65 + vib_audio * 0.35

    # --- Envelope: slow bow attack ---
    attack = int(0.08 * sample_rate)
    decay = int(0.1 * sample_rate)
    sustain_level = 0.88
    release = int(0.15 * sample_rate)
    audio = apply_envelope(audio, attack, decay, sustain_level, release)

    # --- Warmth filter ---
    audio = lowpass_filter(audio, 6000, sample_rate)
    audio = highpass_filter(audio, 80, sample_rate)

    return normalize_audio(audio, 0.75 * velocity)


def generate_harp_tone(
    frequency: float,
    duration: float = 0.8,
    velocity: float = 0.8,
    sample_rate: int = SAMPLE_RATE
) -> np.ndarray:
    """Generate orchestral harp pluck tone.

    Models a concert harp string pluck with:
    - Bright initial pluck transient
    - Rich harmonic spectrum with fast upper-partial decay
    - Long natural sustain on lower notes
    - Gentle body resonance
    """
    num_samples = int(duration * sample_rate)
    t = np.arange(num_samples) / sample_rate
    audio = np.zeros(num_samples)

    # --- Harmonic stack with natural string decay ---
    base_decay = 0.6 + 1.2 * (1.0 - min(frequency, 800) / 800.0)  # lower notes ring longer
    for n in range(1, 16):
        harmonic_freq = frequency * n
        if harmonic_freq > sample_rate / 2 - 200:
            break
        # Harp: strong fundamental, rapid decay of higher partials
        amp = 1.0 / (n ** 1.3)
        decay_time = max(0.05, base_decay / (n ** 0.7))
        env = np.exp(-t / decay_time)
        audio += amp * np.sin(2 * np.pi * harmonic_freq * t) * env

    # --- Pluck transient (string snap) ---
    transient_len = min(num_samples, int(0.008 * sample_rate))
    if transient_len > 4:
        noise = np.random.randn(transient_len) * 0.15
        noise_env = np.exp(-np.arange(transient_len) / (0.002 * sample_rate))
        noise *= noise_env
        audio[:transient_len] += noise

    # --- Body resonance (low-frequency boost) ---
    if frequency < 400:
        body = lowpass_filter(audio, 300, sample_rate) * 0.2
        audio += body

    # --- Overall envelope ---
    attack = int(0.002 * sample_rate)
    decay = int(0.08 * sample_rate)
    sustain_level = 0.3
    release = int(0.3 * sample_rate)
    sustain_samples = max(0, num_samples - attack - decay - release)
    audio = apply_envelope(audio, attack, decay, sustain_level, release, sustain_samples)

    # --- Brightness control ---
    audio = lowpass_filter(audio, 8000, sample_rate)
    audio = highpass_filter(audio, 60, sample_rate)

    return normalize_audio(audio, 0.8 * velocity)


def generate_timpani_tone(
    frequency: float,
    duration: float = 0.6,
    velocity: float = 0.8,
    sample_rate: int = SAMPLE_RATE
) -> np.ndarray:
    """Generate orchestral timpani strike.

    Models a kettledrum with:
    - Short mallet impact (low-mid noise burst)
    - Pitched resonant membrane (inharmonic partials)
    - Natural decay with pitch droop on hard hits
    - Deep, boomy low-frequency content
    """
    num_samples = int(duration * sample_rate)
    t = np.arange(num_samples) / sample_rate
    audio = np.zeros(num_samples)

    # --- Pitched membrane partials (inharmonic like a real drumhead) ---
    # Timpani modal ratios (approximate circular membrane modes)
    modal_ratios = [1.0, 1.504, 1.742, 2.0, 2.296, 2.654]
    modal_amps = [1.0, 0.6, 0.35, 0.25, 0.15, 0.08]
    modal_decays = [0.45, 0.25, 0.18, 0.12, 0.08, 0.06]

    # Pitch droop on hard hits (membrane tension drops briefly)
    pitch_droop = 1.0
    if velocity > 0.6:
        droop_amount = 0.015 * velocity
        pitch_droop_env = 1.0 - droop_amount * np.exp(-t / 0.04)
    else:
        pitch_droop_env = np.ones(num_samples)

    for ratio, amp, decay_t in zip(modal_ratios, modal_amps, modal_decays):
        mode_freq = frequency * ratio * pitch_droop_env
        # Phase for each mode
        phase = np.cumsum(mode_freq / sample_rate) * 2 * np.pi
        env = np.exp(-t / decay_t)
        audio += amp * np.sin(phase) * env

    # --- Mallet impact noise ---
    impact_len = min(num_samples, int(0.015 * sample_rate))
    if impact_len > 4:
        impact_noise = np.random.randn(impact_len) * 0.4 * velocity
        impact_env = np.exp(-np.arange(impact_len) / (0.003 * sample_rate))
        impact_noise *= impact_env
        # Bandpass to low-mid range (mallet thud, not metallic)
        impact_noise = lowpass_filter(impact_noise, 2000, sample_rate)
        audio[:impact_len] += impact_noise

    # --- Low frequency boost (chest-punch quality) ---
    bass = lowpass_filter(audio, 150, sample_rate)
    audio += bass * 0.5

    # --- Overall envelope ---
    attack = int(0.002 * sample_rate)
    decay = int(0.15 * sample_rate)
    sustain_level = 0.15
    release = int(0.2 * sample_rate)
    audio = apply_envelope(audio, attack, decay, sustain_level, release)

    # --- Filter shaping ---
    audio = lowpass_filter(audio, 3500, sample_rate)
    audio = highpass_filter(audio, 30, sample_rate)

    return normalize_audio(audio, 0.85 * velocity)


def generate_choir_tone(
    frequency: float,
    duration: float = 0.5,
    velocity: float = 0.8,
    sample_rate: int = SAMPLE_RATE
) -> np.ndarray:
    """Generate choir/voice pad tone.

    Models an "aah" vocal ensemble with:
    - Formant resonances at vocal tract frequencies
    - Multiple detuned voices for ensemble width
    - Slow attack (breath onset)
    - Natural vibrato
    """
    num_samples = int(duration * sample_rate)
    t = np.arange(num_samples) / sample_rate
    audio = np.zeros(num_samples)

    # --- Formant frequencies for "aah" vowel ---
    formant_freqs = [730, 1090, 2440]
    formant_bw = [80, 90, 120]  # bandwidths

    # --- Multiple voices with slight detuning ---
    voice_detunes = [-5, -2, 0, 2, 5]  # cents
    for cents in voice_detunes:
        ratio = 2 ** (cents / 1200)
        f0 = frequency * ratio

        # Basic glottal pulse (sum of harmonics with 1/n rolloff)
        voice = np.zeros(num_samples)
        for n in range(1, 20):
            h_freq = f0 * n
            if h_freq > sample_rate / 2 - 200:
                break
            amp = 1.0 / (n ** 1.0)
            voice += amp * np.sin(2 * np.pi * h_freq * t)

        # Apply formant filtering (resonant peaks)
        for ff, bw in zip(formant_freqs, formant_bw):
            lo = max(20, ff - bw)
            hi = min(sample_rate // 2 - 100, ff + bw)
            if lo < hi:
                formant_band = bandpass_filter(voice, lo, hi, sample_rate)
                audio += formant_band * 0.3

        # Also add some unfiltered fundamental body
        audio += voice * 0.06

    audio /= len(voice_detunes)

    # --- Vibrato (delayed, subtle) ---
    if duration > 0.3:
        vib_rate = 5.2 + np.random.uniform(-0.3, 0.3)
        vib_depth = 0.005
        vib_onset = np.clip((t - 0.25) / 0.2, 0, 1)
        vibrato = np.sin(2 * np.pi * vib_rate * t) * vib_depth * vib_onset

        vib_layer = np.zeros(num_samples)
        for n in range(1, 8):
            amp = 0.7 / n
            vib_layer += amp * np.sin(2 * np.pi * frequency * n * (t + vibrato))
        audio = audio * 0.7 + vib_layer * 0.3

    # --- Envelope: breath onset ---
    attack = int(0.12 * sample_rate)
    decay = int(0.08 * sample_rate)
    sustain_level = 0.85
    release = int(0.2 * sample_rate)
    audio = apply_envelope(audio, attack, decay, sustain_level, release)

    # --- Warmth ---
    audio = lowpass_filter(audio, 5000, sample_rate)
    audio = highpass_filter(audio, 100, sample_rate)

    return normalize_audio(audio, 0.7 * velocity)


def generate_kebero_hit(
    pitch: int = 63,
    velocity: float = 0.8,
    sample_rate: int = SAMPLE_RATE,
    profile: str = 'eskista_dance',
) -> np.ndarray:
    """
    Generate a bounded Kebero-first hand-drum hit with GM compatibility.

    The Kebero is a double-headed conical Ethiopian drum with a large head
    (deep low tone) and a small head (higher tone), plus muted and edge
    articulations. GM conga/bongo notes are still supported for compatibility,
    but the synthesis stays centered on warm hand-drum behavior rather than a
    generic bright conga model.
    
    Pitch mappings (GM standard notes kept for compatibility):
    - 60: Atamo (small drum) - GM high-bongo note
    - 61: GM low-bongo note
    - 62: small head (high tone) - GM high-conga note
    - 63: large head (low tone) - GM low-conga note
    - 70: Shaker/Maracas
    
    Custom kebero range (authentic head-based):
    - 50: large head (low tone)
    - 51: small head (high tone)
    - 52: muted / dampened
    """
    def _resolve_kebero_profile(profile_name: str) -> Dict[str, float]:
        key = str(profile_name or 'eskista_dance').strip().lower().replace('-', '_').replace(' ', '_')
        profiles: Dict[str, Dict[str, float]] = {
            'eskista_dance': {
                'bass_pitch_scale': 0.92,
                'bass_pitch_drop': 0.95,
                'bass_body_gain': 0.44,
                'bass_overtone_gain': 0.22,
                'bass_noise_gain': 0.072,
                'bass_noise_cutoff': 420.0,
                'bass_noise_decay': 0.10,
                'bass_decay': 0.18,
                'bass_gain': 1.22,
                'slap_custom_freq': 195.0,
                'slap_gm_freq': 215.0,
                'slap_pitch_drop': 1.08,
                'slap_tone_gain': 0.68,
                'slap_noise_gain': 0.34,
                'slap_band_low': 700.0,
                'slap_band_high': 2300.0,
                'slap_noise_decay': 0.011,
                'slap_decay': 0.07,
                'slap_gain': 1.22,
                'slap_lowpass': 3100.0,
                'head_freq': 278.0,
                'head_harmonic_gain': 0.22,
                'head_attack_low': 850.0,
                'head_attack_high': 2400.0,
                'head_attack_gain': 0.18,
                'head_decay': 0.058,
                'muted_freq': 96.0,
                'muted_decay': 0.04,
                'muted_gain': 0.76,
                'medium_freq': 145.0,
                'medium_decay': 0.115,
                'medium_gain': 1.0,
            },
            'traditional_ceremony': {
                'bass_pitch_scale': 1.02,
                'bass_pitch_drop': 0.55,
                'bass_body_gain': 0.34,
                'bass_overtone_gain': 0.15,
                'bass_noise_gain': 0.055,
                'bass_noise_cutoff': 320.0,
                'bass_noise_decay': 0.085,
                'bass_decay': 0.145,
                'bass_gain': 1.10,
                'slap_custom_freq': 180.0,
                'slap_gm_freq': 195.0,
                'slap_pitch_drop': 0.82,
                'slap_tone_gain': 0.60,
                'slap_noise_gain': 0.26,
                'slap_band_low': 580.0,
                'slap_band_high': 1750.0,
                'slap_noise_decay': 0.016,
                'slap_decay': 0.095,
                'slap_gain': 1.08,
                'slap_lowpass': 2500.0,
                'head_freq': 255.0,
                'head_harmonic_gain': 0.18,
                'head_attack_low': 750.0,
                'head_attack_high': 2000.0,
                'head_attack_gain': 0.14,
                'head_decay': 0.07,
                'muted_freq': 92.0,
                'muted_decay': 0.05,
                'muted_gain': 0.64,
                'medium_freq': 155.0,
                'medium_decay': 0.13,
                'medium_gain': 0.96,
            },
            'ethio_jazz_hybrid': {
                'bass_pitch_scale': 1.0,
                'bass_pitch_drop': 0.70,
                'bass_body_gain': 0.38,
                'bass_overtone_gain': 0.18,
                'bass_noise_gain': 0.05,
                'bass_noise_cutoff': 360.0,
                'bass_noise_decay': 0.09,
                'bass_decay': 0.13,
                'bass_gain': 1.12,
                'slap_custom_freq': 188.0,
                'slap_gm_freq': 205.0,
                'slap_pitch_drop': 0.92,
                'slap_tone_gain': 0.64,
                'slap_noise_gain': 0.29,
                'slap_band_low': 640.0,
                'slap_band_high': 2100.0,
                'slap_noise_decay': 0.013,
                'slap_decay': 0.08,
                'slap_gain': 1.15,
                'slap_lowpass': 2900.0,
                'head_freq': 268.0,
                'head_harmonic_gain': 0.2,
                'head_attack_low': 800.0,
                'head_attack_high': 2250.0,
                'head_attack_gain': 0.16,
                'head_decay': 0.064,
                'muted_freq': 94.0,
                'muted_decay': 0.045,
                'muted_gain': 0.7,
                'medium_freq': 150.0,
                'medium_decay': 0.12,
                'medium_gain': 0.98,
            },
        }
        return profiles.get(key, profiles['eskista_dance'])

    cfg = _resolve_kebero_profile(profile)
    duration = 0.4
    num_samples = int(duration * sample_rate)
    t = np.arange(num_samples) / sample_rate
    
    audio = np.zeros(num_samples)
    
    if pitch in [63, 50, 61]:  # large head (low tone) / GM low-conga / GM low-bongo
        # Deep large-head (low tone) response
        base_freq = (75 if pitch == 63 else (65 if pitch == 50 else 85)) * cfg['bass_pitch_scale']
        
        # Characteristic pitch drop of hand drums
        freq_env = base_freq * (1 + cfg['bass_pitch_drop'] * np.exp(-t / 0.015))
        phase = 2 * np.pi * np.cumsum(freq_env) / sample_rate
        audio = np.sin(phase)
        
        # Add body resonance harmonics
        audio += cfg['bass_body_gain'] * np.sin(2 * np.pi * base_freq * 2.3 * t) * np.exp(-t / 0.08)
        audio += cfg['bass_overtone_gain'] * np.sin(2 * np.pi * base_freq * 3.5 * t) * np.exp(-t / 0.05)
        
        # Skin vibration texture
        skin_noise = np.random.randn(num_samples) * cfg['bass_noise_gain']
        skin_noise = lowpass_filter(skin_noise, cfg['bass_noise_cutoff'], sample_rate)
        audio += skin_noise * np.exp(-t / cfg['bass_noise_decay'])
        
        # Envelope - quick attack, medium decay
        env = np.exp(-t / cfg['bass_decay']) * (1 - np.exp(-t / 0.003))
        audio *= env * velocity * cfg['bass_gain']
        
    elif pitch in [62, 51]:  # small head (high tone) / GM high-conga
        # Pointed but still warm small-head (high tone) response
        base_freq = cfg['slap_gm_freq'] if pitch == 62 else cfg['slap_custom_freq']
        
        # Slap has faster pitch drop
        freq_env = base_freq * (1 + cfg['slap_pitch_drop'] * np.exp(-t / 0.008))
        phase = 2 * np.pi * np.cumsum(freq_env) / sample_rate
        audio = np.sin(phase) * cfg['slap_tone_gain']
        
        # Attack transient (controlled hand stroke, never conga-bright)
        slap = np.random.randn(num_samples)
        slap = bandpass_simple(slap, cfg['slap_band_low'], cfg['slap_band_high'], sample_rate)
        slap *= np.exp(-t / cfg['slap_noise_decay'])
        audio += slap * cfg['slap_noise_gain']
        
        # Quick decay
        env = np.exp(-t / cfg['slap_decay']) * (1 - np.exp(-t / 0.001))
        audio *= env * velocity * cfg['slap_gain']
        
        # Roll off highs to keep the hand-drum identity warm
        audio = lowpass_filter(audio, cfg['slap_lowpass'], sample_rate)
        
    elif pitch in [60]:  # Atamo (small drum) - GM compatibility
        # Compact upper-head articulation used for GM compatibility
        base_freq = cfg['head_freq']
        
        freq_env = base_freq * (1 + 0.5 * np.exp(-t / 0.006))
        phase = 2 * np.pi * np.cumsum(freq_env) / sample_rate
        audio = np.sin(phase) * 0.6
        
        # Add harmonic brightness (but controlled)
        audio += cfg['head_harmonic_gain'] * np.sin(2 * np.pi * base_freq * 2.2 * t) * np.exp(-t / 0.03)
        
        # Attack with moderate brightness
        attack = np.random.randn(num_samples)
        attack = bandpass_simple(attack, cfg['head_attack_low'], cfg['head_attack_high'], sample_rate)
        attack *= np.exp(-t / 0.008)
        audio += attack * cfg['head_attack_gain']
        
        # Very short envelope
        env = np.exp(-t / cfg['head_decay']) * (1 - np.exp(-t / 0.001))
        audio *= env * velocity
        
    elif pitch == 52:  # Muted kebero
        # Damped hit with very short decay
        base_freq = cfg['muted_freq']
        audio = np.sin(2 * np.pi * base_freq * t) * np.exp(-t / cfg['muted_decay'])
        audio += 0.3 * np.sin(2 * np.pi * 180 * t) * np.exp(-t / 0.02)
        
        env = np.exp(-t / cfg['muted_decay'])
        audio *= env * velocity * cfg['muted_gain']
        
    else:  # Default - controlled medium hand-drum sound
        base_freq = cfg['medium_freq']
        freq_env = base_freq * (1 + 0.6 * np.exp(-t / 0.01))
        phase = 2 * np.pi * np.cumsum(freq_env) / sample_rate
        audio = np.sin(phase)
        
        env = np.exp(-t / cfg['medium_decay'])
        audio *= env * velocity * cfg['medium_gain']
    
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


def _slow_noise_contour(
    num_samples: int,
    sample_rate: int = SAMPLE_RATE,
    lowpass_hz: float = 24.0,
) -> np.ndarray:
    """Generate a bounded slow-noise contour for acoustic micro-variation."""
    if num_samples <= 0:
        return np.zeros(0, dtype=np.float64)

    contour = np.random.randn(num_samples)
    contour = lowpass_filter(contour, max(1.0, lowpass_hz), sample_rate)
    contour = np.nan_to_num(contour - np.mean(contour), nan=0.0, posinf=0.0, neginf=0.0)

    peak = float(np.max(np.abs(contour))) if contour.size else 0.0
    if peak > 1e-9:
        contour = contour / peak
    return contour


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

def apply_tpdf_dither(audio: np.ndarray, bit_depth: int = 16) -> np.ndarray:
    """
    Apply TPDF (Triangular Probability Density Function) dither.
    
    TPDF dither is the industry standard for bit-depth reduction.
    It replaces quantization distortion with white noise, preserving
    perceived dynamic range and eliminating correlated distortion.
    
    Industry Reference:
    - Pro Tools uses POW-r dither (proprietary TPDF variant)
    - Logic Pro uses TPDF by default
    - iZotope uses MBIT+ (enhanced TPDF)
    
    Args:
        audio: Float audio array (-1.0 to 1.0)
        bit_depth: Target bit depth (typically 16)
        
    Returns:
        Dithered float audio ready for quantization
    """
    if bit_depth >= 24:
        # No dither needed for 24-bit (noise floor already below audibility)
        return audio
    
    # Calculate the quantization step size
    # For 16-bit: 2^16 = 65536 levels, step = 2/65536
    n_levels = 2 ** bit_depth
    step_size = 2.0 / n_levels  # For normalized -1 to 1 range
    
    # Generate TPDF dither (sum of two uniform distributions)
    # This creates triangular probability density, which:
    # - Adds no DC offset
    # - Has minimum crest factor
    # - Provides optimal noise shaping
    shape = audio.shape
    dither1 = np.random.uniform(-0.5, 0.5, shape)
    dither2 = np.random.uniform(-0.5, 0.5, shape)
    tpdf_dither = (dither1 + dither2) * step_size
    
    return audio + tpdf_dither


def save_wav(
    audio: np.ndarray,
    filepath: str,
    sample_rate: int = SAMPLE_RATE,
    stereo: bool = False,
    bit_depth: int = 16,
    apply_dither: bool = True
) -> bool:
    """
    Save audio to WAV file with configurable bit-depth.
    
    Professional bit-depth policy:
    - 24-bit stems: Maximum headroom for mixing/mastering workflows
    - 16-bit master: Universal compatibility with dither
    
    Args:
        audio: Float audio array (-1.0 to 1.0 range)
        filepath: Output path for WAV file
        sample_rate: Sample rate in Hz (default 44100)
        stereo: Convert mono to stereo if True
        bit_depth: Target bit depth (16 or 24)
        apply_dither: Apply TPDF dither when reducing to 16-bit
    
    Returns:
        True if successful
        
    Industry Note:
        24-bit offers 144dB dynamic range vs 96dB for 16-bit.
        Always use 24-bit for stems, 16-bit for final delivery.
    """
    # Ensure directory exists
    os.makedirs(os.path.dirname(filepath) if os.path.dirname(filepath) else '.', exist_ok=True)
    
    # Prepare audio for saving
    work_audio = audio.copy()
    
    # Apply dither if reducing to 16-bit
    if bit_depth == 16 and apply_dither:
        work_audio = apply_tpdf_dither(work_audio, bit_depth)
    
    # Determine format and scaling
    if bit_depth == 24:
        # 24-bit: scale to int32 range (use lower 24 bits)
        # Max value: 2^23 - 1 = 8388607
        scale = 8388607
        audio_int = np.clip(work_audio * scale, -8388608, 8388607).astype(np.int32)
        subtype = 'PCM_24'
        sampwidth = 3
    else:
        # 16-bit (default): scale to int16 range
        scale = 32767
        audio_int = np.clip(work_audio * scale, -32768, 32767).astype(np.int16)
        subtype = 'PCM_16'
        sampwidth = 2
    
    if stereo and len(audio_int.shape) == 1:
        # Convert mono to stereo
        audio_int = np.column_stack([audio_int, audio_int])
    
    if HAS_SOUNDFILE:
        sf.write(filepath, audio_int, sample_rate, subtype=subtype)
    else:
        # Fallback to wave module (16-bit only)
        if bit_depth == 24:
            print(f"Warning: wave module fallback only supports 16-bit, saving as 16-bit")
            audio_int = np.clip(work_audio * 32767, -32768, 32767).astype(np.int16)
            sampwidth = 2
        
        with wave.open(filepath, 'w') as wav:
            n_channels = 2 if (stereo or len(audio_int.shape) > 1) else 1
            wav.setnchannels(n_channels)
            wav.setsampwidth(sampwidth)
            wav.setframerate(sample_rate)
            wav.writeframes(audio_int.tobytes())
    
    return True


def save_stem(
    audio: np.ndarray,
    filepath: str,
    sample_rate: int = SAMPLE_RATE,
    stereo: bool = True
) -> bool:
    """
    Save audio as a 24-bit stem (professional mixing format).
    
    Convenience wrapper for save_wav with stem-appropriate settings.
    24-bit preserves full dynamic range for downstream processing.
    
    Args:
        audio: Float audio array
        filepath: Output path
        sample_rate: Sample rate in Hz
        stereo: Convert to stereo if needed
        
    Returns:
        True if successful
    """
    return save_wav(audio, filepath, sample_rate, stereo, bit_depth=24, apply_dither=False)


def save_master(
    audio: np.ndarray,
    filepath: str,
    sample_rate: int = SAMPLE_RATE,
    stereo: bool = True
) -> bool:
    """
    Save audio as a 16-bit master (delivery format).
    
    Convenience wrapper for save_wav with master-appropriate settings.
    16-bit with TPDF dither for CD/streaming compatibility.
    
    Args:
        audio: Float audio array
        filepath: Output path
        sample_rate: Sample rate in Hz
        stereo: Convert to stereo if needed
        
    Returns:
        True if successful
    """
    return save_wav(audio, filepath, sample_rate, stereo, bit_depth=16, apply_dither=True)


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
    
    def generate_drum_kit(self, drum_elements: Optional[Iterable[str]] = None) -> Dict[str, str]:
        """
        Generate complete drum kit.

        Args:
            drum_elements: Optional parsed/requested drum elements. When omitted,
                preserves the legacy full-kit behavior. When provided, only
                supported requested elements are generated.
        
        Returns:
            Dict mapping drum name to file path
        """
        kit = {}

        if drum_elements is None:
            requested = ['808', 'kick', 'snare', 'clap', 'hihat', 'hihat_open', 'rim']
        else:
            aliases = {
                '808': '808',
                'kick': 'kick',
                'snare': 'snare',
                'clap': 'clap',
                'hihat': 'hihat',
                'hihat_closed': 'hihat',
                'hihat_open': 'hihat_open',
                'rim': 'rim',
                'perc': 'shaker',
                'percussion': 'shaker',
                'hand_percussion': 'shaker',
                'hand_perc': 'shaker',
                'shaker': 'shaker',
                'kebero': 'kebero',
            }
            source_elements = [drum_elements] if isinstance(drum_elements, str) else drum_elements
            requested = []
            for element in source_elements:
                normalized = str(element).strip().lower().replace('-', '_').replace(' ', '_')
                key = aliases.get(normalized)
                if key and key not in requested:
                    requested.append(key)
        
        # 808 kick/bass
        if '808' in requested:
            audio = generate_808_kick()
            path = os.path.join(self.output_dir, '808_kick.wav')
            save_wav(audio, path, self.sample_rate)
            kit['808'] = path
        
        # Punchy kick
        if 'kick' in requested:
            audio = generate_kick()
            path = os.path.join(self.output_dir, 'kick.wav')
            save_wav(audio, path, self.sample_rate)
            kit['kick'] = path
        
        # Snare
        if 'snare' in requested:
            audio = generate_snare()
            path = os.path.join(self.output_dir, 'snare.wav')
            save_wav(audio, path, self.sample_rate)
            kit['snare'] = path
        
        # Clap
        if 'clap' in requested:
            audio = generate_clap()
            path = os.path.join(self.output_dir, 'clap.wav')
            save_wav(audio, path, self.sample_rate)
            kit['clap'] = path
        
        # Closed hi-hat
        if 'hihat' in requested:
            audio = generate_hihat(is_open=False)
            path = os.path.join(self.output_dir, 'hihat_closed.wav')
            save_wav(audio, path, self.sample_rate)
            kit['hihat'] = path
        
        # Open hi-hat
        if 'hihat_open' in requested:
            audio = generate_hihat(is_open=True)
            path = os.path.join(self.output_dir, 'hihat_open.wav')
            save_wav(audio, path, self.sample_rate)
            kit['hihat_open'] = path
        
        # Rim
        if 'rim' in requested:
            audio = generate_rim()
            path = os.path.join(self.output_dir, 'rim.wav')
            save_wav(audio, path, self.sample_rate)
            kit['rim'] = path

        # Ethiopian/hand percussion aliases used by parsed prompts.
        if 'shaker' in requested:
            audio = generate_shaker_hit(sample_rate=self.sample_rate)
            path = os.path.join(self.output_dir, 'shaker.wav')
            save_wav(audio, path, self.sample_rate)
            kit['shaker'] = path

        if 'kebero' in requested:
            # Kebero is a double-headed conical Ethiopian drum.
            # Pitch 50 = large head (low tone); pitch 51 = small head (high tone).
            low_path = os.path.join(self.output_dir, 'kebero_low.wav')
            audio = generate_kebero_hit(pitch=50, sample_rate=self.sample_rate)
            save_wav(audio, low_path, self.sample_rate)
            kit['kebero_low'] = low_path

            high_path = os.path.join(self.output_dir, 'kebero_high.wav')
            audio = generate_kebero_hit(pitch=51, sample_rate=self.sample_rate)
            save_wav(audio, high_path, self.sample_rate)
            kit['kebero_high'] = high_path

            # Deprecated Western alias keys retained for backward compatibility.
            # They point at the SAME authentic head-based sample files.
            kit['kebero_bass'] = low_path
            kit['kebero_slap'] = high_path
        
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

    def generate_vinyl_crackle(self, duration: float = 30.0, density: float = 0.3) -> str:
        """Generate a vinyl crackle texture and return its file path.

        Backward-compatible instance wrapper for callers that expect
        ``AssetsGenerator.generate_vinyl_crackle()`` while preserving the
        module-level synthesis function.
        """
        audio = generate_vinyl_crackle(duration, density=density, sample_rate=self.sample_rate)
        path = os.path.join(self.output_dir, 'vinyl_crackle.wav')
        save_wav(audio, path, self.sample_rate, stereo=True)
        return path

    def generate_rain_texture(self, duration: float = 30.0, intensity: float = 0.5) -> str:
        """Generate a rain ambience texture and return its file path."""
        audio = generate_rain(duration, intensity=intensity, sample_rate=self.sample_rate)
        path = os.path.join(self.output_dir, 'rain.wav')
        save_wav(audio, path, self.sample_rate, stereo=True)
        return path
    
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
