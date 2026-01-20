# Dynamic EQ and Spectral Processing Research Report
## Comprehensive Technical Specification for multimodal-ai-music-gen

**Document Type:** Research Report  
**Version:** 1.0  
**Date:** January 2026  
**Scope:** Dynamic EQ Architecture, Resonance Detection, Harmonic Exciters, Parametric EQ Implementation

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Dynamic EQ Architecture](#2-dynamic-eq-architecture)
3. [FabFilter Pro-Q & iZotope Implementation Analysis](#3-fabfilter-pro-q--izotope-implementation-analysis)
4. [Resonance Detection and Suppression](#4-resonance-detection-and-suppression)
5. [Harmonic Exciter/Enhancer Implementations](#5-harmonic-exciterenhancer-implementations)
6. [Python Parametric EQ Implementation](#6-python-parametric-eq-implementation)
7. [Sidechain-Triggered EQ Bands](#7-sidechain-triggered-eq-bands)
8. [Integration with mix_chain.py](#8-integration-with-mix_chainpy)
9. [References](#9-references)

---

## 1. Executive Summary

This research provides specifications for implementing professional-grade spectral processing in Python. Key findings:

| Component | Key Algorithm | Complexity | Real-time Capable |
|-----------|--------------|------------|-------------------|
| Dynamic EQ | Per-band envelope follower + biquad | Medium | Yes |
| Parametric EQ | RBJ Cookbook biquad coefficients | Low | Yes |
| Resonance Suppression | FFT peak detection + adaptive notch | High | With optimization |
| Harmonic Exciter | Chebyshev waveshaping | Low | Yes |
| Sidechain EQ | External envelope → gain modulation | Medium | Yes |

---

## 2. Dynamic EQ Architecture

### 2.1 Concept: Compression Per Frequency Band

Dynamic EQ combines parametric equalization with dynamics processing. Unlike static EQ (constant gain), dynamic EQ applies gain changes **only when the signal at that frequency exceeds a threshold**.

```
                        ┌─────────────────────────────────────┐
                        │       DYNAMIC EQ BAND               │
                        │                                     │
Input ──┬──────────────►│ Biquad Filter (frequency isolation) │
        │               │         │                           │
        │               │         ▼                           │
        │               │   Envelope Follower                 │
        │               │         │                           │
        │               │         ▼                           │
        │               │   Threshold Comparison              │
        │               │         │                           │
        │               │         ▼                           │
        │               │   Gain Computer (ratio)             │
        │               │         │                           │
        │               │         ▼                           │
        │               │   Attack/Release Smoothing          │
        │               │         │                           │
        │               └─────────┼───────────────────────────┘
        │                         │
        │                         ▼
        └───────────────► Gain Multiplier ──────────────────► Output
```

### 2.2 Per-Band Signal Flow

For each dynamic EQ band:

1. **Band Isolation**: Extract frequency content via bandpass biquad
2. **Envelope Detection**: Track amplitude using attack/release envelope follower
3. **Gain Computation**: Calculate gain reduction based on threshold and ratio
4. **Gain Smoothing**: Apply attack/release to gain changes
5. **Output**: Apply computed gain to either the band or full signal

### 2.3 Core Parameters Per Band

| Parameter | Range | Description |
|-----------|-------|-------------|
| `frequency` | 20 Hz - 20 kHz | Center frequency |
| `q` | 0.1 - 20.0 | Bandwidth (higher Q = narrower) |
| `threshold_db` | -60 to 0 dB | Activation threshold |
| `ratio` | 1:1 to ∞:1 | Compression/expansion ratio |
| `attack_ms` | 0.1 - 500 ms | Gain reduction onset speed |
| `release_ms` | 10 - 5000 ms | Gain restoration speed |
| `gain_db` | -24 to +24 dB | Maximum gain change |
| `mode` | "compress" / "expand" | Cut when loud / boost when quiet |

### 2.4 Envelope Follower Mathematics

The envelope follower extracts amplitude over time:

```python
# Attack/Release Coefficients
attack_coef = 1 - exp(-2.2 / (attack_ms * sample_rate / 1000))
release_coef = 1 - exp(-2.2 / (release_ms * sample_rate / 1000))

# Per-Sample Envelope Update
if abs(input[n]) > envelope[n-1]:
    envelope[n] = attack_coef * abs(input[n]) + (1 - attack_coef) * envelope[n-1]
else:
    envelope[n] = release_coef * abs(input[n]) + (1 - release_coef) * envelope[n-1]
```

### 2.5 Gain Computation (Compression Curve)

```python
# Convert envelope to dB
envelope_db = 20 * log10(envelope + 1e-10)

# Calculate how much over threshold
over_threshold_db = envelope_db - threshold_db

# Compute gain reduction (soft knee optional)
if over_threshold_db > 0:
    # Standard compression: reduce by (1 - 1/ratio) of overshoot
    gain_reduction_db = -over_threshold_db * (1 - 1/ratio)
else:
    gain_reduction_db = 0

# Convert back to linear
gain_linear = 10 ** (gain_reduction_db / 20)
```

---

## 3. FabFilter Pro-Q & iZotope Implementation Analysis

### 3.1 FabFilter Pro-Q 3 Architecture

Based on analysis of behavior and documentation:

**Key Features:**
1. **Linear Phase Mode**: Uses FFT-based filtering to eliminate phase distortion
2. **Natural Phase Mode**: Minimum-phase IIR for lowest latency
3. **Dynamic Mode Per Band**: Each of 24 bands can be dynamic
4. **Spectrum Analyzer**: Real-time FFT with adjustable resolution

**Dynamic EQ Implementation:**
- Uses parallel processing: dry signal + filtered dynamic path
- Sidechain from same band (internal) or external source
- Attack range: 0-500ms, Release range: 0-5000ms
- Lookahead available (introduces latency)
- Auto-gain compensation to maintain perceived loudness

```
Pro-Q Dynamic Band Architecture:
                                    ┌─────────────────┐
Input ──┬──────────────────────────►│   Dry Path      │──┐
        │                           └─────────────────┘  │
        │                                                │
        │   ┌───────────────────────────────────────┐   │
        └──►│ Bandpass (sidechain)                  │   │
            │         │                             │   │
            │         ▼                             │   │
            │  Envelope Detector (RMS or Peak)      │   │
            │         │                             │   │
            │         ▼                             │   │
            │  Compressor/Expander                  │   │
            │         │                             │   │
            │         ▼                             │   │
            │  Bell/Shelf EQ with variable gain    │───┼──► Mix ──► Output
            └───────────────────────────────────────┘   │
                                                        │
                                        Mix Control ◄───┘
```

### 3.2 iZotope Dynamic EQ (Ozone)

**Key Differentiators:**
1. **Multiband Architecture**: True multiband with crossover filters
2. **Learn Function**: Analyzes audio to suggest EQ curves
3. **Codec Preview**: Hear effect of lossy compression
4. **Vintage Modes**: Emulate analog EQ curves (Baxandall, Pultec)

**Dynamic Processing:**
- Each band has independent dynamics
- Global and per-band threshold
- Adaptive release (program-dependent)
- Mid/Side processing option

### 3.3 Key Takeaways for Implementation

| Feature | Pro-Q Approach | iZotope Approach | Our Implementation |
|---------|---------------|------------------|-------------------|
| Filter Type | Biquad cascades | State-variable | Biquad (RBJ) |
| Phase | Linear/Natural selectable | Minimum phase | Minimum phase |
| Bands | Up to 24 floating | Fixed multiband | Configurable |
| Detection | RMS/Peak selectable | Adaptive | Configurable |
| Oversampling | Optional 4x | Internal | Optional 2x |

---

## 4. Resonance Detection and Suppression

### 4.1 Algorithm Overview (Soothe2-style)

Resonance suppressors continuously analyze the spectrum and apply narrow-band reduction to problematic peaks.

```
Audio Buffer (e.g., 4096 samples)
       │
       ▼
┌──────────────────────────────────┐
│   Window Function (Hann)         │
└──────────────────────────────────┘
       │
       ▼
┌──────────────────────────────────┐
│   FFT (Real → Complex)           │
└──────────────────────────────────┘
       │
       ▼
┌──────────────────────────────────┐
│   Magnitude Spectrum (dB)        │
└──────────────────────────────────┘
       │
       ▼
┌──────────────────────────────────┐
│   Peak Detection                 │
│   (scipy.signal.find_peaks)      │
│   - prominence > 6dB             │
│   - width < 200 Hz               │
└──────────────────────────────────┘
       │
       ▼
┌──────────────────────────────────┐
│   Resonance Classification       │
│   - Narrow Q (>10) = resonance   │
│   - Static over time = resonance │
└──────────────────────────────────┘
       │
       ▼
┌──────────────────────────────────┐
│   Adaptive Notch Placement       │
│   - Q matches detected width     │
│   - Gain proportional to peak    │
└──────────────────────────────────┘
       │
       ▼
┌──────────────────────────────────┐
│   Apply Notch Filters to Audio   │
└──────────────────────────────────┘
```

### 4.2 Peak Detection Algorithm

```python
from scipy.signal import find_peaks
from scipy.fft import rfft, rfftfreq
import numpy as np

def detect_resonances(audio, sample_rate, fft_size=4096, 
                      prominence_db=6.0, max_width_hz=200):
    """
    Detect resonant peaks in audio spectrum.
    
    Args:
        audio: Mono audio buffer
        sample_rate: Sample rate in Hz
        fft_size: FFT window size
        prominence_db: Minimum peak prominence to detect
        max_width_hz: Maximum width for a resonance
        
    Returns:
        List of resonances: [{freq, magnitude_db, q, width_hz}]
    """
    # Apply window
    window = np.hanning(fft_size)
    
    # Zero-pad or truncate
    if len(audio) < fft_size:
        audio = np.pad(audio, (0, fft_size - len(audio)))
    else:
        audio = audio[:fft_size]
    
    # FFT
    windowed = audio * window
    spectrum = rfft(windowed)
    frequencies = rfftfreq(fft_size, 1/sample_rate)
    
    # Magnitude in dB
    magnitude = np.abs(spectrum)
    magnitude_db = 20 * np.log10(magnitude + 1e-10)
    
    # Frequency resolution
    freq_resolution = frequencies[1] - frequencies[0]
    max_width_bins = int(max_width_hz / freq_resolution)
    
    # Find peaks with prominence and width constraints
    peaks, properties = find_peaks(
        magnitude_db,
        prominence=prominence_db,
        width=(1, max_width_bins)
    )
    
    # Build resonance list
    resonances = []
    for i, peak_idx in enumerate(peaks):
        freq = frequencies[peak_idx]
        mag = magnitude_db[peak_idx]
        
        # Calculate bandwidth and Q
        width_bins = properties['widths'][i]
        width_hz = width_bins * freq_resolution
        q = freq / max(width_hz, 1)  # Q = f_center / bandwidth
        
        # Only include if Q > threshold (narrow peaks)
        if q > 5.0:  # Q > 5 suggests resonance
            resonances.append({
                'frequency': freq,
                'magnitude_db': mag,
                'q': min(q, 50.0),  # Clamp Q
                'width_hz': width_hz,
                'prominence_db': properties['prominences'][i]
            })
    
    return resonances
```

### 4.3 Q Factor and Notch Filter Design

The suppression filter Q should match the detected resonance:

```python
def design_notch_filter(center_freq, q, sample_rate, reduction_db=-6):
    """
    Design a notch filter for resonance suppression.
    Uses RBJ cookbook peaking EQ with negative gain.
    
    Args:
        center_freq: Center frequency in Hz
        q: Q factor (bandwidth = center_freq / q)
        sample_rate: Sample rate in Hz
        reduction_db: Amount of reduction (negative)
        
    Returns:
        b, a: Filter coefficients
    """
    A = 10 ** (reduction_db / 40)  # For peaking EQ
    w0 = 2 * np.pi * center_freq / sample_rate
    
    cos_w0 = np.cos(w0)
    sin_w0 = np.sin(w0)
    alpha = sin_w0 / (2 * q)
    
    # Peaking EQ coefficients (from RBJ cookbook)
    b0 = 1 + alpha * A
    b1 = -2 * cos_w0
    b2 = 1 - alpha * A
    a0 = 1 + alpha / A
    a1 = -2 * cos_w0
    a2 = 1 - alpha / A
    
    # Normalize
    b = np.array([b0/a0, b1/a0, b2/a0])
    a = np.array([1.0, a1/a0, a2/a0])
    
    return b, a
```

---

## 5. Harmonic Exciter/Enhancer Implementations

### 5.1 Harmonic Generation Theory

Exciters generate new harmonic content by applying nonlinear transfer functions (waveshaping):

| Harmonic | Musical Interval | Character | Primary Source |
|----------|-----------------|-----------|----------------|
| 2nd | Octave | Warm, rich | Tube saturation |
| 3rd | Octave + fifth | Edge, presence | Tape, transistors |
| 4th | 2 octaves | Smooth brightness | Tube + transformer |
| 5th | 2 oct + major 3rd | Aggressive | Hard clipping |

### 5.2 Waveshaping Functions

```python
import numpy as np

def soft_clip_tanh(x, drive=1.0):
    """
    Soft saturation using tanh.
    Generates mostly odd harmonics (3rd, 5th, 7th...).
    """
    return np.tanh(x * drive)

def tube_saturation(x, drive=1.0, asymmetry=0.2):
    """
    Asymmetric saturation for tube-like even harmonics.
    
    Args:
        x: Input signal (normalized -1 to 1)
        drive: Saturation amount (1.0 = moderate)
        asymmetry: 0 = symmetric (odd only), higher = more even harmonics
    """
    # Different drive for positive and negative halves
    pos_drive = drive * (1 + asymmetry)
    neg_drive = drive * (1 - asymmetry)
    
    y = np.where(x >= 0, 
                 np.tanh(x * pos_drive),
                 np.tanh(x * neg_drive))
    return y

def chebyshev_harmonic(x, n):
    """
    Generate specific harmonic using Chebyshev polynomial.
    T_n(cos(θ)) = cos(nθ) means T_n generates nth harmonic.
    
    Args:
        x: Input signal (normalized to -1 to 1)
        n: Harmonic number (2=octave, 3=octave+fifth, etc.)
    """
    if n == 1:
        return x
    elif n == 2:
        return 2 * x**2 - 1  # 2nd harmonic (octave)
    elif n == 3:
        return 4 * x**3 - 3 * x  # 3rd harmonic
    elif n == 4:
        return 8 * x**4 - 8 * x**2 + 1  # 4th harmonic
    elif n == 5:
        return 16 * x**5 - 20 * x**3 + 5 * x  # 5th harmonic
    else:
        # Recursive: T_n = 2x*T_{n-1} - T_{n-2}
        t_prev2 = np.ones_like(x)
        t_prev1 = x.copy()
        for _ in range(2, n + 1):
            t_curr = 2 * x * t_prev1 - t_prev2
            t_prev2 = t_prev1
            t_prev1 = t_curr
        return t_prev1

def harmonic_exciter(x, even_amount=0.3, odd_amount=0.2):
    """
    Generate blended harmonics for warmth and presence.
    
    Args:
        x: Input signal
        even_amount: Level of 2nd/4th harmonics (0-1)
        odd_amount: Level of 3rd/5th harmonics (0-1)
        
    Returns:
        Signal with added harmonics
    """
    # Normalize input
    peak = np.max(np.abs(x)) + 1e-10
    x_norm = x / peak
    
    # Even harmonics (warm, tube-like)
    h2 = chebyshev_harmonic(x_norm, 2)
    h4 = chebyshev_harmonic(x_norm, 4)
    even = even_amount * (h2 * 0.6 + h4 * 0.25)
    
    # Odd harmonics (edge, presence)
    h3 = chebyshev_harmonic(x_norm, 3)
    h5 = chebyshev_harmonic(x_norm, 5)
    odd = odd_amount * (h3 * 0.5 + h5 * 0.2)
    
    # Add harmonics to original
    return x + (even + odd) * peak * 0.3  # Scale for subtlety
```

### 5.3 Frequency-Dependent Exciter (Multiband)

Professional exciters process different bands separately:

```python
from scipy.signal import butter, sosfilt

def multiband_exciter(audio, sample_rate, 
                      low_drive=0.0, 
                      mid_drive=0.2,
                      high_drive=0.3,
                      air_drive=0.4,
                      air_freq=8000,
                      mix=0.5):
    """
    Apply frequency-dependent harmonic excitation.
    
    Args:
        audio: Input audio (mono or stereo)
        sample_rate: Sample rate
        low_drive: Drive for <200 Hz (usually 0)
        mid_drive: Drive for 200-2000 Hz
        high_drive: Drive for 2-8 kHz
        air_drive: Drive for >8 kHz
        air_freq: Air band frequency cutoff
        mix: Wet/dry mix
    """
    # Handle stereo
    if len(audio.shape) == 1:
        channels = [audio]
    else:
        channels = [audio[:, i] for i in range(audio.shape[1])]
    
    processed = []
    
    for channel in channels:
        # Band-split
        sos_low = butter(4, 200, 'low', fs=sample_rate, output='sos')
        sos_mid = butter(4, [200, 2000], 'band', fs=sample_rate, output='sos')
        sos_high = butter(4, [2000, air_freq], 'band', fs=sample_rate, output='sos')
        sos_air = butter(4, air_freq, 'high', fs=sample_rate, output='sos')
        
        low_band = sosfilt(sos_low, channel)
        mid_band = sosfilt(sos_mid, channel)
        high_band = sosfilt(sos_high, channel)
        air_band = sosfilt(sos_air, channel)
        
        # Apply saturation per band
        low_sat = tube_saturation(low_band / (np.max(np.abs(low_band)) + 1e-10), 
                                   low_drive) * np.max(np.abs(low_band))
        mid_sat = tube_saturation(mid_band / (np.max(np.abs(mid_band)) + 1e-10),
                                   mid_drive, asymmetry=0.3) * np.max(np.abs(mid_band))
        high_sat = tube_saturation(high_band / (np.max(np.abs(high_band)) + 1e-10),
                                    high_drive, asymmetry=0.2) * np.max(np.abs(high_band))
        air_sat = soft_clip_tanh(air_band / (np.max(np.abs(air_band)) + 1e-10),
                                  air_drive) * np.max(np.abs(air_band))
        
        # Sum bands
        wet = low_sat + mid_sat + high_sat + air_sat
        
        # Mix
        out = channel * (1 - mix) + wet * mix
        processed.append(out)
    
    if len(processed) == 1:
        return processed[0]
    return np.column_stack(processed)
```

---

## 6. Python Parametric EQ Implementation

### 6.1 RBJ Audio EQ Cookbook Implementation

The Robert Bristow-Johnson Audio EQ Cookbook provides standard formulas for biquad filter coefficients. Here's a complete implementation:

```python
import numpy as np
from enum import Enum
from dataclasses import dataclass
from typing import Optional, List, Tuple

class FilterType(Enum):
    LOWPASS = "lowpass"
    HIGHPASS = "highpass"
    BANDPASS = "bandpass"
    NOTCH = "notch"
    PEAK = "peak"
    LOW_SHELF = "low_shelf"
    HIGH_SHELF = "high_shelf"
    ALLPASS = "allpass"


@dataclass
class EQBandParams:
    """Parameters for a single EQ band."""
    filter_type: FilterType = FilterType.PEAK
    frequency: float = 1000.0  # Hz
    gain_db: float = 0.0       # dB (for peak/shelf only)
    q: float = 1.0             # Q factor
    enabled: bool = True


def calculate_biquad_coefficients(filter_type: FilterType,
                                   frequency: float,
                                   sample_rate: float,
                                   gain_db: float = 0.0,
                                   q: float = 1.0) -> Tuple[np.ndarray, np.ndarray]:
    """
    Calculate biquad filter coefficients using RBJ Audio EQ Cookbook.
    
    Args:
        filter_type: Type of filter
        frequency: Center/corner frequency in Hz
        sample_rate: Sample rate in Hz
        gain_db: Gain in dB (for peak and shelf filters)
        q: Q factor (bandwidth)
        
    Returns:
        b, a: Numerator and denominator coefficients
    """
    # Intermediate variables
    A = 10 ** (gain_db / 40)  # For peaking and shelving
    w0 = 2 * np.pi * frequency / sample_rate
    cos_w0 = np.cos(w0)
    sin_w0 = np.sin(w0)
    alpha = sin_w0 / (2 * q)
    
    if filter_type == FilterType.LOWPASS:
        b0 = (1 - cos_w0) / 2
        b1 = 1 - cos_w0
        b2 = (1 - cos_w0) / 2
        a0 = 1 + alpha
        a1 = -2 * cos_w0
        a2 = 1 - alpha
        
    elif filter_type == FilterType.HIGHPASS:
        b0 = (1 + cos_w0) / 2
        b1 = -(1 + cos_w0)
        b2 = (1 + cos_w0) / 2
        a0 = 1 + alpha
        a1 = -2 * cos_w0
        a2 = 1 - alpha
        
    elif filter_type == FilterType.BANDPASS:
        b0 = alpha
        b1 = 0
        b2 = -alpha
        a0 = 1 + alpha
        a1 = -2 * cos_w0
        a2 = 1 - alpha
        
    elif filter_type == FilterType.NOTCH:
        b0 = 1
        b1 = -2 * cos_w0
        b2 = 1
        a0 = 1 + alpha
        a1 = -2 * cos_w0
        a2 = 1 - alpha
        
    elif filter_type == FilterType.PEAK:
        b0 = 1 + alpha * A
        b1 = -2 * cos_w0
        b2 = 1 - alpha * A
        a0 = 1 + alpha / A
        a1 = -2 * cos_w0
        a2 = 1 - alpha / A
        
    elif filter_type == FilterType.LOW_SHELF:
        sqrt_A = np.sqrt(A)
        sqrt_2A_alpha = 2 * sqrt_A * alpha
        
        b0 = A * ((A + 1) - (A - 1) * cos_w0 + sqrt_2A_alpha)
        b1 = 2 * A * ((A - 1) - (A + 1) * cos_w0)
        b2 = A * ((A + 1) - (A - 1) * cos_w0 - sqrt_2A_alpha)
        a0 = (A + 1) + (A - 1) * cos_w0 + sqrt_2A_alpha
        a1 = -2 * ((A - 1) + (A + 1) * cos_w0)
        a2 = (A + 1) + (A - 1) * cos_w0 - sqrt_2A_alpha
        
    elif filter_type == FilterType.HIGH_SHELF:
        sqrt_A = np.sqrt(A)
        sqrt_2A_alpha = 2 * sqrt_A * alpha
        
        b0 = A * ((A + 1) + (A - 1) * cos_w0 + sqrt_2A_alpha)
        b1 = -2 * A * ((A - 1) + (A + 1) * cos_w0)
        b2 = A * ((A + 1) + (A - 1) * cos_w0 - sqrt_2A_alpha)
        a0 = (A + 1) - (A - 1) * cos_w0 + sqrt_2A_alpha
        a1 = 2 * ((A - 1) - (A + 1) * cos_w0)
        a2 = (A + 1) - (A - 1) * cos_w0 - sqrt_2A_alpha
        
    elif filter_type == FilterType.ALLPASS:
        b0 = 1 - alpha
        b1 = -2 * cos_w0
        b2 = 1 + alpha
        a0 = 1 + alpha
        a1 = -2 * cos_w0
        a2 = 1 - alpha
    
    else:
        raise ValueError(f"Unknown filter type: {filter_type}")
    
    # Normalize by a0
    b = np.array([b0/a0, b1/a0, b2/a0])
    a = np.array([1.0, a1/a0, a2/a0])
    
    return b, a


class BiquadFilter:
    """Single biquad filter with state."""
    
    def __init__(self):
        self.b = np.array([1.0, 0.0, 0.0])
        self.a = np.array([1.0, 0.0, 0.0])
        self.z1 = 0.0
        self.z2 = 0.0
    
    def set_coefficients(self, b: np.ndarray, a: np.ndarray):
        """Set filter coefficients."""
        self.b = b
        self.a = a
    
    def reset(self):
        """Reset filter state."""
        self.z1 = 0.0
        self.z2 = 0.0
    
    def process_sample(self, x: float) -> float:
        """
        Process single sample (Transposed Direct Form II).
        More numerically stable for floating point.
        """
        y = self.b[0] * x + self.z1
        self.z1 = self.b[1] * x - self.a[1] * y + self.z2
        self.z2 = self.b[2] * x - self.a[2] * y
        return y
    
    def process_block(self, audio: np.ndarray) -> np.ndarray:
        """Process block of samples."""
        output = np.zeros_like(audio)
        for i in range(len(audio)):
            output[i] = self.process_sample(audio[i])
        return output


class ParametricEQ:
    """
    Multi-band parametric equalizer.
    
    Each band is a biquad filter with configurable type, frequency, gain, and Q.
    """
    
    def __init__(self, sample_rate: float = 48000.0, num_bands: int = 8):
        self.sample_rate = sample_rate
        self.bands: List[Tuple[EQBandParams, BiquadFilter, BiquadFilter]] = []
        
        for _ in range(num_bands):
            params = EQBandParams()
            # Stereo: left and right filters
            filter_l = BiquadFilter()
            filter_r = BiquadFilter()
            self.bands.append((params, filter_l, filter_r))
    
    def set_band(self, band_index: int, 
                 filter_type: FilterType,
                 frequency: float,
                 gain_db: float = 0.0,
                 q: float = 1.0,
                 enabled: bool = True):
        """Configure a single band."""
        if band_index >= len(self.bands):
            raise IndexError(f"Band index {band_index} out of range")
        
        params, filter_l, filter_r = self.bands[band_index]
        
        params.filter_type = filter_type
        params.frequency = frequency
        params.gain_db = gain_db
        params.q = q
        params.enabled = enabled
        
        # Calculate and set coefficients
        b, a = calculate_biquad_coefficients(
            filter_type, frequency, self.sample_rate, gain_db, q
        )
        filter_l.set_coefficients(b, a)
        filter_r.set_coefficients(b, a)
    
    def process(self, audio: np.ndarray) -> np.ndarray:
        """
        Process audio through all enabled bands.
        
        Args:
            audio: Mono or stereo audio array
            
        Returns:
            Processed audio
        """
        if len(audio) == 0:
            return audio
        
        # Handle mono/stereo
        is_mono = len(audio.shape) == 1
        if is_mono:
            audio = audio.reshape(-1, 1)
        
        output = audio.copy()
        
        # Process through each enabled band
        for params, filter_l, filter_r in self.bands:
            if not params.enabled or params.gain_db == 0.0:
                continue
            
            # Left channel
            output[:, 0] = filter_l.process_block(output[:, 0])
            
            # Right channel (if stereo)
            if output.shape[1] > 1:
                output[:, 1] = filter_r.process_block(output[:, 1])
        
        return output.flatten() if is_mono else output
    
    def reset(self):
        """Reset all filter states."""
        for _, filter_l, filter_r in self.bands:
            filter_l.reset()
            filter_r.reset()
```

### 6.2 Vectorized Biquad Processing (Faster)

For better performance with numpy arrays:

```python
from scipy.signal import lfilter

def process_biquad_vectorized(audio: np.ndarray, 
                               b: np.ndarray, 
                               a: np.ndarray) -> np.ndarray:
    """
    Vectorized biquad filtering using scipy.
    Much faster than sample-by-sample processing.
    """
    if len(audio.shape) == 1:
        return lfilter(b, a, audio)
    else:
        output = np.zeros_like(audio)
        for ch in range(audio.shape[1]):
            output[:, ch] = lfilter(b, a, audio[:, ch])
        return output
```

---

## 7. Sidechain-Triggered EQ Bands

### 7.1 Concept

Sidechain EQ uses a separate signal (or different frequency band) to control the gain of an EQ band. Common uses:

- **Ducking bass when kick hits**: Sidechain from kick to bass EQ
- **De-masking**: Sidechain vocal presence range to guitar
- **Frequency-dependent compression**: Internal sidechain

### 7.2 Implementation

```python
@dataclass
class SidechainEQParams:
    """Parameters for sidechain-triggered EQ."""
    # Target band settings
    target_frequency: float = 100.0  # Hz
    target_q: float = 2.0
    max_reduction_db: float = -12.0  # Maximum cut
    
    # Sidechain settings
    sidechain_source: str = "external"  # "internal" or "external"
    sidechain_frequency: float = 100.0  # For internal sidechain
    sidechain_q: float = 1.0
    
    # Dynamics
    threshold_db: float = -20.0
    ratio: float = 4.0
    attack_ms: float = 10.0
    release_ms: float = 100.0


class SidechainEQ:
    """
    Sidechain-triggered EQ band.
    Uses external or internal signal to control EQ gain.
    """
    
    def __init__(self, params: SidechainEQParams, sample_rate: float):
        self.params = params
        self.sample_rate = sample_rate
        
        # Target filter (will have gain modulated)
        self.target_filter_l = BiquadFilter()
        self.target_filter_r = BiquadFilter()
        
        # Sidechain bandpass filter
        self.sc_filter = BiquadFilter()
        b, a = calculate_biquad_coefficients(
            FilterType.BANDPASS,
            params.sidechain_frequency,
            sample_rate,
            q=params.sidechain_q
        )
        self.sc_filter.set_coefficients(b, a)
        
        # Envelope follower state
        self.envelope = 0.0
        
        # Precompute coefficients
        self.attack_coef = 1 - np.exp(-2.2 / (params.attack_ms * sample_rate / 1000))
        self.release_coef = 1 - np.exp(-2.2 / (params.release_ms * sample_rate / 1000))
        
        # Threshold in linear
        self.threshold_linear = 10 ** (params.threshold_db / 20)
    
    def _update_envelope(self, sidechain_level: float):
        """Update envelope follower with attack/release."""
        if sidechain_level > self.envelope:
            self.envelope = (self.attack_coef * sidechain_level + 
                           (1 - self.attack_coef) * self.envelope)
        else:
            self.envelope = (self.release_coef * sidechain_level + 
                           (1 - self.release_coef) * self.envelope)
        return self.envelope
    
    def _compute_gain(self, envelope: float) -> float:
        """Compute gain reduction based on envelope vs threshold."""
        if envelope < 1e-10:
            return 1.0
        
        env_db = 20 * np.log10(envelope)
        over_db = env_db - self.params.threshold_db
        
        if over_db > 0:
            # Calculate gain reduction
            reduction_db = -over_db * (1 - 1/self.params.ratio)
            reduction_db = max(reduction_db, self.params.max_reduction_db)
            return 10 ** (reduction_db / 20)
        
        return 1.0
    
    def process(self, audio: np.ndarray, 
                sidechain: Optional[np.ndarray] = None) -> np.ndarray:
        """
        Process audio with sidechain-triggered EQ.
        
        Args:
            audio: Main audio to process
            sidechain: External sidechain signal (optional)
            
        Returns:
            Processed audio
        """
        if sidechain is None:
            # Internal sidechain: use filtered version of input
            if len(audio.shape) > 1:
                sc_mono = np.mean(audio, axis=1)
            else:
                sc_mono = audio
            sidechain = self.sc_filter.process_block(sc_mono)
        else:
            if len(sidechain.shape) > 1:
                sidechain = np.mean(sidechain, axis=1)
        
        # Process sample by sample
        output = np.zeros_like(audio)
        is_stereo = len(audio.shape) > 1 and audio.shape[1] > 1
        
        for i in range(len(audio)):
            # Get sidechain level
            sc_level = abs(sidechain[i])
            
            # Update envelope and compute gain
            env = self._update_envelope(sc_level)
            gain = self._compute_gain(env)
            
            # Update target filter coefficients with current gain
            # (Simplified: multiply output by gain instead of recalculating coefficients)
            gain_db = 20 * np.log10(gain + 1e-10)
            
            # Calculate filter coefficients for this gain
            b, a = calculate_biquad_coefficients(
                FilterType.PEAK,
                self.params.target_frequency,
                self.sample_rate,
                gain_db=self.params.max_reduction_db * (1 - gain),  # Apply reduction
                q=self.params.target_q
            )
            self.target_filter_l.set_coefficients(b, a)
            self.target_filter_r.set_coefficients(b, a)
            
            # Process audio
            if is_stereo:
                output[i, 0] = self.target_filter_l.process_sample(audio[i, 0])
                output[i, 1] = self.target_filter_r.process_sample(audio[i, 1])
            else:
                output[i] = self.target_filter_l.process_sample(audio[i])
        
        return output
```

---

## 8. Integration with mix_chain.py

### 8.1 New Effect Types to Add

```python
# Add to EffectType enum in mix_chain.py
class EffectType(Enum):
    # ... existing types ...
    PARAMETRIC_EQ = "parametric_eq"
    DYNAMIC_EQ = "dynamic_eq"
    RESONANCE_SUPPRESSION = "resonance_suppression"
    HARMONIC_EXCITER = "harmonic_exciter"
    SIDECHAIN_EQ = "sidechain_eq"
```

### 8.2 New Parameter Classes

```python
@dataclass
class ParametricEQParams(EffectParams):
    """Multi-band parametric EQ parameters."""
    bands: List[dict] = field(default_factory=list)
    # Each band: {type, frequency, gain_db, q, enabled}
    
    def __post_init__(self):
        if not self.bands:
            # Default: 4-band semi-parametric
            self.bands = [
                {'type': 'low_shelf', 'frequency': 100, 'gain_db': 0, 'q': 0.7},
                {'type': 'peak', 'frequency': 500, 'gain_db': 0, 'q': 1.0},
                {'type': 'peak', 'frequency': 2000, 'gain_db': 0, 'q': 1.0},
                {'type': 'high_shelf', 'frequency': 8000, 'gain_db': 0, 'q': 0.7},
            ]


@dataclass
class DynamicEQParams(EffectParams):
    """Dynamic EQ parameters."""
    frequency: float = 3000.0
    q: float = 2.0
    threshold_db: float = -20.0
    ratio: float = 4.0
    attack_ms: float = 10.0
    release_ms: float = 100.0
    max_cut_db: float = -12.0
    mode: str = "compress"  # "compress" or "expand"


@dataclass
class ExciterParams(EffectParams):
    """Harmonic exciter parameters."""
    even_harmonics: float = 0.3  # 0-1, 2nd/4th
    odd_harmonics: float = 0.2   # 0-1, 3rd/5th
    low_drive: float = 0.0
    mid_drive: float = 0.2
    high_drive: float = 0.3
    air_drive: float = 0.4
    air_freq: float = 8000.0
```

### 8.3 DSP Class Extensions

Add to the `DSP` class:

```python
@staticmethod
def parametric_eq(audio: np.ndarray, params: ParametricEQParams, 
                  sample_rate: int) -> np.ndarray:
    """Apply multi-band parametric EQ."""
    from scipy.signal import lfilter
    
    output = audio.copy()
    
    for band in params.bands:
        if band.get('gain_db', 0) == 0:
            continue
        
        # Map string type to FilterType enum
        filter_type = FilterType[band['type'].upper()]
        
        b, a = calculate_biquad_coefficients(
            filter_type,
            band['frequency'],
            sample_rate,
            band.get('gain_db', 0),
            band.get('q', 1.0)
        )
        
        if len(output.shape) > 1:
            for ch in range(output.shape[1]):
                output[:, ch] = lfilter(b, a, output[:, ch])
        else:
            output = lfilter(b, a, output)
    
    return output

@staticmethod
def dynamic_eq(audio: np.ndarray, params: DynamicEQParams,
               sample_rate: int) -> np.ndarray:
    """Apply dynamic EQ band."""
    # Implementation using DynamicEQBand class
    band = DynamicEQBand(params, sample_rate)
    return band.process(audio)

@staticmethod
def harmonic_exciter(audio: np.ndarray, params: ExciterParams,
                     sample_rate: int) -> np.ndarray:
    """Apply harmonic exciter."""
    return multiband_exciter(
        audio, sample_rate,
        low_drive=params.low_drive,
        mid_drive=params.mid_drive,
        high_drive=params.high_drive,
        air_drive=params.air_drive,
        air_freq=params.air_freq,
        mix=params.mix
    )
```

### 8.4 MixChain.process() Updates

```python
def process(self, audio: np.ndarray, sample_rate: int = SAMPLE_RATE) -> np.ndarray:
    """Process audio through the chain."""
    if len(audio) == 0:
        return audio
        
    processed = audio.copy()
    
    for effect_type, params in self.effects:
        if not params.enabled:
            continue
        
        # ... existing effects ...
        
        elif effect_type == EffectType.PARAMETRIC_EQ:
            processed = DSP.parametric_eq(processed, params, sample_rate)
        elif effect_type == EffectType.DYNAMIC_EQ:
            processed = DSP.dynamic_eq(processed, params, sample_rate)
        elif effect_type == EffectType.HARMONIC_EXCITER:
            processed = DSP.harmonic_exciter(processed, params, sample_rate)
        
    return processed
```

### 8.5 New Chain Presets

```python
def create_vocal_chain() -> MixChain:
    """Chain optimized for vocals."""
    chain = MixChain("Vocal Chain")
    
    # High-pass to remove rumble
    chain.add_effect(EffectType.PARAMETRIC_EQ, ParametricEQParams(
        bands=[
            {'type': 'highpass', 'frequency': 80, 'gain_db': 0, 'q': 0.7},
        ]
    ))
    
    # De-ess harsh frequencies dynamically
    chain.add_effect(EffectType.DYNAMIC_EQ, DynamicEQParams(
        frequency=5000,
        q=3.0,
        threshold_db=-18,
        ratio=6.0,
        attack_ms=2,
        release_ms=50,
        max_cut_db=-8
    ))
    
    # Gentle compression
    chain.add_effect(EffectType.COMPRESSOR, CompressorParams(
        threshold_db=-15,
        ratio=3.0,
        attack_ms=15,
        release_ms=100
    ))
    
    # Add presence
    chain.add_effect(EffectType.HARMONIC_EXCITER, ExciterParams(
        even_harmonics=0.2,
        odd_harmonics=0.1,
        high_drive=0.2,
        air_drive=0.3,
        mix=0.3
    ))
    
    return chain


def create_mastering_chain() -> MixChain:
    """Full mastering chain with spectral processing."""
    chain = MixChain("Mastering Chain")
    
    # Surgical EQ
    chain.add_effect(EffectType.PARAMETRIC_EQ, ParametricEQParams(
        bands=[
            {'type': 'high_pass', 'frequency': 30, 'gain_db': 0, 'q': 0.7},
            {'type': 'low_shelf', 'frequency': 80, 'gain_db': 1.5, 'q': 0.7},
            {'type': 'peak', 'frequency': 200, 'gain_db': -1.5, 'q': 1.5},
            {'type': 'peak', 'frequency': 3000, 'gain_db': 0.5, 'q': 2.0},
            {'type': 'high_shelf', 'frequency': 10000, 'gain_db': 1.0, 'q': 0.7},
        ]
    ))
    
    # Tame harsh midrange dynamically
    chain.add_effect(EffectType.DYNAMIC_EQ, DynamicEQParams(
        frequency=2500,
        q=2.5,
        threshold_db=-15,
        ratio=3.0,
        attack_ms=5,
        release_ms=75,
        max_cut_db=-6
    ))
    
    # Gentle bus compression
    chain.add_effect(EffectType.COMPRESSOR, CompressorParams(
        threshold_db=-6,
        ratio=2.0,
        attack_ms=30,
        release_ms=150,
        knee_width_db=6.0
    ))
    
    # Add warmth and air
    chain.add_effect(EffectType.HARMONIC_EXCITER, ExciterParams(
        even_harmonics=0.15,
        odd_harmonics=0.05,
        mid_drive=0.1,
        air_drive=0.2,
        mix=0.25
    ))
    
    # Stereo width enhancement
    chain.add_effect(EffectType.STEREO_WIDTH, StereoWidthParams(
        width=1.1,
        mono_below_hz=100
    ))
    
    # Final limiting
    chain.add_effect(EffectType.TRUE_PEAK_LIMITER, TruePeakLimiterParams(
        ceiling_db=-1.0,
        release_ms=100
    ))
    
    return chain
```

---

## 9. References

### 9.1 Essential Technical Resources

| Resource | Type | Content |
|----------|------|---------|
| [W3C Audio EQ Cookbook](https://www.w3.org/TR/audio-eq-cookbook/) | Standard | RBJ biquad coefficient formulas |
| [EarLevel Biquad Calculator](https://www.earlevel.com/main/2021/09/02/biquad-calculator-v3/) | Tool | Interactive coefficient calculation |
| [MusicDSP.org Filters](https://www.musicdsp.org/en/latest/Filters/) | Archive | Filter implementations |
| DAFX: Digital Audio Effects (Zölzer) | Book | Comprehensive DSP reference |

### 9.2 Professional Plugin References

| Plugin | Feature | Implementation Notes |
|--------|---------|---------------------|
| FabFilter Pro-Q 3 | Dynamic EQ | Per-band dynamics, linear phase option |
| iZotope Ozone | Multiband | Adaptive release, vintage modes |
| Soothe2 | Resonance | FFT-based spectral analysis |
| Soundtoys Decapitator | Saturation | 5 saturation styles |
| Maag EQ4 | Air band | 40kHz shelf creates "air" |

### 9.3 Key Formulas Summary

```
Envelope Coefficients:
  attack_coef = 1 - exp(-2.2 / (attack_ms * sample_rate / 1000))
  release_coef = 1 - exp(-2.2 / (release_ms * sample_rate / 1000))

Q Factor:
  Q = f_center / bandwidth
  bandwidth = f_high - f_low (at -3dB points)

dB Conversions:
  dB = 20 * log10(linear)
  linear = 10^(dB/20)

Compression Gain:
  gain_reduction_dB = over_threshold_dB * (1 - 1/ratio)

Chebyshev Polynomials:
  T_2(x) = 2x² - 1       (2nd harmonic)
  T_3(x) = 4x³ - 3x      (3rd harmonic)
  T_4(x) = 8x⁴ - 8x² + 1 (4th harmonic)
  T_5(x) = 16x⁵ - 20x³ + 5x (5th harmonic)
```

---

*End of Research Report*
