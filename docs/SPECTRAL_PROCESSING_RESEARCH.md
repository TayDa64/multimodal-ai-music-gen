# Spectral Processing Research Report
## DSP Techniques for Professional Audio Mastering

**Document Type:** Research Specification  
**Version:** 1.0  
**Date:** January 2026  
**Scope:** Dynamic EQ, Resonance Suppression, Harmonic Enhancement, De-Essing  

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Dynamic EQ](#1-dynamic-eq)
3. [Resonance Detection & Suppression](#2-resonance-detection--suppression)
4. [Harmonic Enhancement/Exciter](#3-harmonic-enhancementexciter)
5. [De-Essing](#4-de-essing)
6. [Dataclass Schemas](#5-dataclass-schemas)
7. [Python Code Snippets](#6-python-code-snippets)
8. [MixChain Integration Notes](#7-mixchain-integration-notes)
9. [Professional References](#8-professional-references)

---

## Executive Summary

This research document specifies DSP algorithms for implementing professional-grade spectral processing effects in the multimodal-ai-music-gen project. The four core processing modules covered are:

| Module | Purpose | Key Algorithm |
|--------|---------|---------------|
| Dynamic EQ | Frequency-selective dynamics | Per-band envelope follower + threshold gate |
| Resonance Suppression | Automatic problematic frequency reduction | FFT peak detection + adaptive notch filtering |
| Harmonic Exciter | Warmth/presence enhancement | Waveshaping with frequency-dependent saturation |
| De-Esser | Sibilance reduction | Split-band or broadband compression with HF sidechain |

---

## 1. Dynamic EQ

### 1.1 Concept

Dynamic EQ combines parametric equalization with dynamics processing. Unlike static EQ (constant gain at a frequency), dynamic EQ applies gain changes **only when the signal at that frequency exceeds a threshold**. This allows surgical control over problem frequencies without affecting the mix when they're not problematic.

### 1.2 Algorithm Architecture

```
Input Signal
    │
    ├──► Band Isolation (Bandpass Filter)
    │         │
    │         ▼
    │    Envelope Follower ──► Compare to Threshold
    │         │                      │
    │         │                      ▼
    │         │              Gain Computer (Ratio-based)
    │         │                      │
    │         ▼                      │
    │    Attack/Release ◄────────────┘
    │    Smoothing
    │         │
    │         ▼
    │    Gain Multiplier ◄── Mix Control
    │         │
    ▼         ▼
Parallel ──► Summed Output
Path
```

### 1.3 Per-Band Processing

For each dynamic EQ band, the following parameters apply:

| Parameter | Range | Description |
|-----------|-------|-------------|
| `frequency` | 20 Hz - 20 kHz | Center frequency of the band |
| `q` | 0.1 - 20.0 | Bandwidth (Q factor) |
| `threshold_db` | -60 to 0 dB | Level above which processing activates |
| `ratio` | 1:1 to ∞:1 | Compression/expansion ratio |
| `attack_ms` | 0.1 - 500 ms | Attack time for gain reduction |
| `release_ms` | 10 - 5000 ms | Release time for gain restoration |
| `gain_db` | -24 to +24 dB | Target gain when triggered |
| `mode` | "cut" or "boost" | Direction of dynamic action |

### 1.4 Envelope Follower Design

The envelope follower extracts the amplitude envelope of a specific frequency band:

```
envelope[n] = {
    attack_coef * input[n] + (1 - attack_coef) * envelope[n-1]   if input[n] > envelope[n-1]
    release_coef * input[n] + (1 - release_coef) * envelope[n-1] otherwise
}

where:
    attack_coef = 1 - exp(-2.2 / (attack_ms * sample_rate / 1000))
    release_coef = 1 - exp(-2.2 / (release_ms * sample_rate / 1000))
```

### 1.5 Gain Computation

Once the envelope exceeds the threshold, gain reduction is computed:

```
over_threshold_db = envelope_db - threshold_db

if mode == "cut":
    if over_threshold_db > 0:
        gain_reduction_db = over_threshold_db * (1 - 1/ratio)
    else:
        gain_reduction_db = 0

if mode == "boost":
    if over_threshold_db < 0:  # Signal below threshold
        gain_boost_db = abs(over_threshold_db) * (1 - 1/ratio) * upward_expansion
    else:
        gain_boost_db = 0
```

### 1.6 Sidechain Options

| Sidechain Type | Description | Use Case |
|----------------|-------------|----------|
| Internal | Same band triggers its own compression | Standard dynamic EQ |
| External | Separate signal triggers band | Ducking specific frequencies |
| Frequency-shifted | Adjacent band triggers | Preventing masking |

### 1.7 Use Case: Taming Harsh 2-4 kHz

**Problem:** Vocal or guitar presence region (2-4 kHz) becomes harsh at loud passages.

**Solution:**
```python
band_config = {
    "frequency": 3000,      # Center at 3 kHz
    "q": 2.0,               # Moderate width (~1.5 octaves)
    "threshold_db": -12,    # Activate when presence is prominent
    "ratio": 3.0,           # Moderate ratio
    "attack_ms": 5,         # Fast attack to catch transients
    "release_ms": 50,       # Medium release for natural decay
    "gain_db": -6,          # Maximum 6dB cut
    "mode": "cut"
}
```

---

## 2. Resonance Detection & Suppression

### 2.1 Concept

Resonances are narrow frequency peaks caused by room modes, instrument body resonance, or feedback. They create an unnatural "ringy" or "honky" quality. Automated resonance suppression (like Soothe2) continuously analyzes the spectrum and applies narrow-band reduction to problematic peaks.

### 2.2 FFT Analysis for Peak Detection

#### 2.2.1 Spectral Analysis Pipeline

```
Audio Buffer (N samples)
    │
    ▼
Window Function (Hann, Blackman-Harris)
    │
    ▼
FFT (N-point, typically 2048-8192)
    │
    ▼
Magnitude Spectrum |X[k]|
    │
    ▼
Convert to dB: 20 * log10(|X[k]| + ε)
    │
    ▼
Peak Detection (scipy.signal.find_peaks)
    │
    ▼
Peak Classification (resonance vs. harmonic)
    │
    ▼
Adaptive Notch Filter Placement
```

#### 2.2.2 Peak Detection Algorithm

```python
# Using scipy.signal.find_peaks with resonance-specific parameters
peaks, properties = find_peaks(
    magnitude_db,
    height=-40,              # Minimum peak height (dB from max)
    prominence=6,            # Peak must be 6dB above neighbors (resonance threshold)
    distance=5,              # Minimum bins between peaks
    width=(1, 20)            # Resonances are narrow (1-20 bins)
)
```

### 2.3 Resonance Classification

Not all spectral peaks are problematic. Harmonics of musical content should be preserved:

| Peak Type | Width (Q) | Temporal Behavior | Action |
|-----------|-----------|-------------------|--------|
| Harmonic | Variable | Tracks pitch | Preserve |
| Resonance | Narrow (Q > 10) | Static or slow drift | Suppress |
| Transient | Wide | Brief | Preserve |

#### 2.3.1 Resonance Score Calculation

```
resonance_score = prominence_db * narrowness_factor * persistence_factor

where:
    prominence_db = peak_height - average_neighboring_level
    narrowness_factor = Q / Q_threshold  (higher Q = more resonant)
    persistence_factor = time_present / analysis_window  (static peaks score higher)
```

### 2.4 Q Factor Selection

The Q factor of the suppression filter should match the detected resonance width:

```
detected_bandwidth_hz = freq_at_right_base - freq_at_left_base
center_freq = (freq_at_right_base + freq_at_left_base) / 2
notch_Q = center_freq / detected_bandwidth_hz

# Clamp to reasonable range
notch_Q = clamp(notch_Q, 5.0, 50.0)
```

### 2.5 Adaptive Notch Filter

Each detected resonance gets a notch filter with:

```
H(z) = (1 - 2r*cos(ω₀)*z⁻¹ + r²*z⁻²) / (1 - 2r*cos(ω₀)*z⁻¹ + r²*z⁻²)

where:
    ω₀ = 2π * f_center / sample_rate  (normalized center frequency)
    r = 1 - (π * bandwidth / sample_rate)  (controls notch width)
```

### 2.6 Real-Time vs. Offline Analysis

| Mode | FFT Size | Hop Size | Latency | Use Case |
|------|----------|----------|---------|----------|
| Real-time | 2048 | 512 | ~11ms @ 48kHz | Live performance |
| Low-latency | 4096 | 1024 | ~21ms @ 48kHz | Tracking |
| Offline | 8192+ | 2048 | N/A | Mastering |

### 2.7 Soothe2-Style Implementation Notes

Professional resonance suppressors like Soothe2 use:

1. **Overlapping FFT analysis** (75% overlap) for smooth tracking
2. **Psychoacoustic weighting** (resonances in 1-4 kHz are more annoying)
3. **Attack/release per frequency band** (not just global)
4. **Delta mode** (only suppress frequencies that increase in level)
5. **Soft/hard modes** (aggressive vs. transparent processing)

---

## 3. Harmonic Enhancement/Exciter

### 3.1 Concept

Harmonic exciters generate new harmonic content from the input signal, adding "warmth," "presence," or "air" depending on which harmonics are emphasized. This emulates the pleasant distortion of analog equipment.

### 3.2 Harmonic Types and Character

| Harmonic | Relationship | Character | Source Emulation |
|----------|--------------|-----------|------------------|
| 2nd (even) | Octave above | Warm, musical, rich | Tube amplifiers |
| 3rd (odd) | Octave + fifth | Edge, bite, presence | Transistor/tape |
| 4th (even) | 2 octaves | Smooth brightness | Tube + transformer |
| 5th (odd) | 2 octaves + third | Aggressive, harsh | Hard clipping |

### 3.3 Waveshaping Functions

Waveshaping applies a nonlinear transfer function to generate harmonics:

#### 3.3.1 Soft Saturation (Even + Odd Harmonics)

```
# Hyperbolic tangent (most common)
y = tanh(drive * x)

# Produces decreasing odd harmonics: 3rd > 5th > 7th...
# Even harmonics appear with asymmetric drive
```

#### 3.3.2 Tube Emulation (Emphasize Even Harmonics)

```
# Asymmetric soft clipping for even harmonics
y = {
    tanh(x * drive * 1.2)     if x >= 0
    tanh(x * drive * 0.8)     if x < 0
}

# Or polynomial approximation:
y = x - (x³/3) + (x⁵/5) * asymmetry_factor
```

#### 3.3.3 Hard Clipping (Strong Odd Harmonics)

```
y = {
    threshold       if x > threshold
    x               if -threshold <= x <= threshold
    -threshold      if x < -threshold
}
```

#### 3.3.4 Full-Wave Rectification (Even Harmonics Only)

```
y = |x|  # Produces only even harmonics (2nd, 4th, 6th...)
```

### 3.4 Frequency-Dependent Saturation

Professional exciters process different frequency bands separately to avoid muddiness:

```
Input Signal
    │
    ├──► Low Pass (< 200 Hz) ──► Minimal/No saturation (preserve clarity)
    │
    ├──► Band Pass (200-2kHz) ──► Moderate saturation (warmth)
    │
    ├──► Band Pass (2k-8kHz) ──► Presence saturation (bite)
    │
    └──► High Pass (> 8kHz) ──► Air enhancement (see 3.5)
    
    All bands ──► Sum ──► Output
```

### 3.5 "Air" Enhancement (Above 10 kHz)

Air enhancement adds harmonic content above 10 kHz for "sparkle" and "openness":

```
# Extract high frequencies
high_band = high_shelf_filter(input, freq=10000, gain=0)

# Generate harmonics (2nd and 3rd)
# Use multiband saturation focused on highs
excited = soft_saturate(high_band, drive=0.3)

# Filter out content below 10kHz (only keep new harmonics)
air_only = high_pass(excited, freq=10000)

# Mix back
output = input + air_only * air_amount
```

**Maag EQ4 "Air Band" approach:**
- Fixed frequency shelf at 40 kHz (!) 
- The filter's slope creates a gentle boost starting around 10 kHz
- Combined with subtle saturation from the analog circuit

### 3.6 Harmonic Generation Formulas

#### Chebyshev Polynomials (Generate Specific Harmonics)

```python
def chebyshev_T(n, x):
    """Generate nth Chebyshev polynomial - produces only nth harmonic."""
    if n == 0: return 1
    if n == 1: return x
    if n == 2: return 2*x**2 - 1        # 2nd harmonic
    if n == 3: return 4*x**3 - 3*x      # 3rd harmonic
    if n == 4: return 8*x**4 - 8*x**2 + 1  # 4th harmonic
    if n == 5: return 16*x**5 - 20*x**3 + 5*x  # 5th harmonic
```

#### Mixed Harmonic Blend

```python
def harmonic_exciter(x, even_amount, odd_amount):
    """
    Generate mixed harmonics.
    
    even_amount: 0-1, controls 2nd/4th harmonic level
    odd_amount: 0-1, controls 3rd/5th harmonic level
    """
    # Normalize input
    x_norm = x / np.max(np.abs(x) + 1e-10)
    
    # Even harmonics (warm)
    even = even_amount * (chebyshev_T(2, x_norm) * 0.5 + 
                          chebyshev_T(4, x_norm) * 0.25)
    
    # Odd harmonics (edge)
    odd = odd_amount * (chebyshev_T(3, x_norm) * 0.4 + 
                        chebyshev_T(5, x_norm) * 0.15)
    
    return x + even + odd
```

---

## 4. De-Essing

### 4.1 Concept

De-essing reduces excessive sibilance ("s", "sh", "ch" sounds) in vocal recordings. Sibilance occurs in the 2-10 kHz range (typically 4-8 kHz for most voices) and can be fatiguing, especially on headphones.

### 4.2 Sibilance Frequency Ranges

| Voice Type | Typical Sibilance Range | Peak Frequency |
|------------|------------------------|----------------|
| Male (low) | 3-6 kHz | 4-5 kHz |
| Male (high) | 4-7 kHz | 5-6 kHz |
| Female | 5-9 kHz | 6-8 kHz |
| Child | 6-10 kHz | 7-9 kHz |

### 4.3 De-Esser Architectures

#### 4.3.1 Wideband (Broadband) De-Essing

```
Input ──┬──► Bandpass Filter (sibilance band) ──► Envelope ──► Threshold
        │                                              │
        │                                              ▼
        │                                      Gain Computer
        │                                              │
        └──────────────────────────────────────────────┼───► Gain Stage ──► Output
                         (Full signal gain reduced)    │
```

**Pros:** Simpler, more natural
**Cons:** Reduces overall level during sibilance, can dull transients

#### 4.3.2 Split-Band De-Essing

```
Input ──┬──► Low Pass (< sibilance freq) ──────────────────────────┬──► Sum ──► Output
        │                                                           │
        └──► High Pass (> sibilance freq) ──► Compressor ───────────┘
                                                    ▲
                                                    │
                                        Sidechain (from HP band)
```

**Pros:** Only affects sibilant frequencies, preserves low-frequency content
**Cons:** Can sound "lispy" if over-processed

#### 4.3.3 Dynamic EQ De-Essing

```
Input ──► Dynamic EQ Band (4-8 kHz) ──► Output
              │
              ├── Threshold: -20 dB
              ├── Ratio: 4:1 to 10:1
              ├── Attack: 1-5 ms (fast!)
              └── Release: 20-50 ms
```

**Pros:** Most transparent, surgical control
**Cons:** Requires precise frequency targeting

### 4.4 Sibilance Detection Algorithm

```python
def detect_sibilance(audio, sample_rate, 
                     low_freq=4000, high_freq=9000,
                     threshold_db=-20):
    """
    Detect sibilant regions in audio.
    
    Returns: Boolean mask where True = sibilance detected
    """
    # Band-isolate sibilance region
    sibilance_band = bandpass_filter(audio, low_freq, high_freq, sample_rate)
    
    # Full-band level for comparison
    full_band_level = rms_envelope(audio, window_ms=10)
    sibilance_level = rms_envelope(sibilance_band, window_ms=5)
    
    # Sibilance ratio (how much of the signal is in sibilance band)
    ratio_db = 20 * np.log10(sibilance_level / (full_band_level + 1e-10))
    
    # Sibilance detected when HF ratio exceeds threshold
    is_sibilant = ratio_db > threshold_db
    
    return is_sibilant
```

### 4.5 Attack/Release Considerations

De-essers require **very fast attack** to catch the onset of sibilants:

| Parameter | Typical Value | Rationale |
|-----------|---------------|-----------|
| Attack | 0.1 - 5 ms | Sibilants have fast rise times |
| Release | 20 - 100 ms | Prevent pumping, allow natural decay |
| Lookahead | 1 - 5 ms | Pre-detect sibilance for zero-attack |

### 4.6 Over-Processing Artifacts

- **Lisping:** Too much reduction makes "s" sound like "th"
- **Dullness:** Wideband mode removes too much high frequency content
- **Pumping:** Release too slow causes audible gain changes
- **Unnatural:** Split-band can create phase artifacts at crossover

---

## 5. Dataclass Schemas

```python
from dataclasses import dataclass, field
from typing import List, Optional, Literal
from enum import Enum


class DynamicEQMode(Enum):
    CUT = "cut"
    BOOST = "boost"


class SidechainSource(Enum):
    INTERNAL = "internal"
    EXTERNAL = "external"
    ADJACENT_BAND = "adjacent_band"


class DeEsserMode(Enum):
    WIDEBAND = "wideband"
    SPLIT_BAND = "split_band"
    DYNAMIC_EQ = "dynamic_eq"


class ExciterType(Enum):
    TUBE = "tube"           # Emphasize even harmonics
    TAPE = "tape"           # Even + low-order odd
    TRANSISTOR = "transistor"  # Odd harmonics
    DIGITAL = "digital"     # Clean harmonic generation


@dataclass
class DynamicEQBandParams:
    """Parameters for a single Dynamic EQ band."""
    enabled: bool = True
    frequency: float = 1000.0          # Center frequency (Hz)
    q: float = 2.0                      # Q factor (bandwidth)
    threshold_db: float = -20.0         # Activation threshold
    ratio: float = 4.0                  # Compression/expansion ratio
    attack_ms: float = 10.0             # Attack time
    release_ms: float = 100.0           # Release time
    gain_db: float = 0.0                # Target gain (negative for cut)
    mode: DynamicEQMode = DynamicEQMode.CUT
    knee_db: float = 6.0                # Soft knee width
    sidechain: SidechainSource = SidechainSource.INTERNAL
    sidechain_freq: Optional[float] = None  # For adjacent band sidechain


@dataclass
class DynamicEQParams:
    """Full Dynamic EQ configuration."""
    enabled: bool = True
    bands: List[DynamicEQBandParams] = field(default_factory=list)
    global_output_gain_db: float = 0.0
    oversampling: int = 1               # 1, 2, or 4x oversampling
    linear_phase: bool = False          # Use linear phase filters
    lookahead_ms: float = 0.0           # Lookahead for detection


@dataclass
class ResonanceSuppressionParams:
    """Parameters for automatic resonance detection and suppression."""
    enabled: bool = True
    
    # Detection
    sensitivity: float = 0.5            # 0-1, how easily peaks are detected
    frequency_range: tuple = (100, 10000)  # Hz range to analyze
    min_q: float = 5.0                  # Minimum Q to consider resonant
    
    # FFT Analysis
    fft_size: int = 4096                # FFT window size
    hop_size: int = 1024                # Analysis hop size
    window: str = "hann"                # Window function
    
    # Suppression
    max_reduction_db: float = -12.0     # Maximum cut per resonance
    attack_ms: float = 5.0              # How fast suppression kicks in
    release_ms: float = 50.0            # How fast suppression releases
    
    # Advanced
    delta_mode: bool = False            # Only suppress increasing resonances
    soft_mode: bool = True              # Gentle (True) or aggressive (False)
    max_bands: int = 8                  # Maximum simultaneous notches
    psychoacoustic_weighting: bool = True  # Weight by perceptual sensitivity


@dataclass
class ExciterParams:
    """Parameters for harmonic exciter/enhancer."""
    enabled: bool = True
    
    # Harmonic blend
    even_harmonics: float = 0.5         # 0-1, 2nd/4th harmonic amount
    odd_harmonics: float = 0.3          # 0-1, 3rd/5th harmonic amount
    exciter_type: ExciterType = ExciterType.TUBE
    
    # Frequency targeting
    low_band_drive: float = 0.0         # Drive for < 200 Hz (usually 0)
    mid_band_drive: float = 0.3         # Drive for 200-2000 Hz
    high_band_drive: float = 0.5        # Drive for 2-8 kHz
    air_band_drive: float = 0.4         # Drive for > 8 kHz
    
    # Air enhancement
    air_freq: float = 10000             # Air band starts here (Hz)
    air_amount: float = 0.0             # 0-1, "air" effect amount
    
    # Global
    mix: float = 0.5                    # Wet/dry mix
    output_gain_db: float = 0.0         # Output compensation


@dataclass
class DeEsserParams:
    """Parameters for de-esser."""
    enabled: bool = True
    
    # Detection
    mode: DeEsserMode = DeEsserMode.SPLIT_BAND
    low_freq: float = 4000              # Sibilance band low edge (Hz)
    high_freq: float = 9000             # Sibilance band high edge (Hz)
    
    # Dynamics
    threshold_db: float = -20.0         # Detection threshold
    ratio: float = 6.0                  # Compression ratio
    attack_ms: float = 1.0              # Very fast attack!
    release_ms: float = 50.0            # Medium release
    
    # Advanced
    lookahead_ms: float = 2.0           # Lookahead for zero-attack
    max_reduction_db: float = -12.0     # Maximum gain reduction
    listen_mode: bool = False           # Solo the sidechain for tuning
    
    # Auto-detection
    auto_frequency: bool = False        # Automatically find sibilance freq
    voice_type: Optional[str] = None    # "male", "female", "child" for presets


@dataclass
class SpectralProcessingChain:
    """Complete spectral processing configuration for mastering."""
    name: str = "Default Spectral Chain"
    
    # Processing modules (in order)
    dynamic_eq: Optional[DynamicEQParams] = None
    resonance_suppression: Optional[ResonanceSuppressionParams] = None
    de_esser: Optional[DeEsserParams] = None
    exciter: Optional[ExciterParams] = None
    
    # Global settings
    sample_rate: int = 48000
    enabled: bool = True
```

---

## 6. Python Code Snippets

### 6.1 FFT-Based Spectral Analysis

```python
import numpy as np
from scipy.fft import rfft, rfftfreq
from scipy.signal import find_peaks, butter, sosfilt


def analyze_spectrum(audio: np.ndarray, 
                     sample_rate: int = 48000,
                     fft_size: int = 4096,
                     window: str = "hann") -> tuple:
    """
    Perform FFT analysis on audio buffer.
    
    Args:
        audio: Mono audio samples
        sample_rate: Sample rate in Hz
        fft_size: FFT window size
        window: Window function name
        
    Returns:
        frequencies: Array of frequency bins (Hz)
        magnitude_db: Magnitude spectrum in dB
        phase: Phase spectrum in radians
    """
    # Apply window
    if window == "hann":
        win = np.hanning(fft_size)
    elif window == "blackman":
        win = np.blackman(fft_size)
    elif window == "blackman_harris":
        win = np.blackman(fft_size)  # Approximate
    else:
        win = np.ones(fft_size)
    
    # Zero-pad or truncate
    if len(audio) < fft_size:
        audio = np.pad(audio, (0, fft_size - len(audio)))
    else:
        audio = audio[:fft_size]
    
    # Windowed FFT
    windowed = audio * win
    spectrum = rfft(windowed)
    
    # Frequency bins
    frequencies = rfftfreq(fft_size, 1/sample_rate)
    
    # Magnitude in dB
    magnitude = np.abs(spectrum)
    magnitude_db = 20 * np.log10(magnitude + 1e-10)
    
    # Phase
    phase = np.angle(spectrum)
    
    return frequencies, magnitude_db, phase


def detect_resonances(frequencies: np.ndarray,
                      magnitude_db: np.ndarray,
                      prominence_db: float = 6.0,
                      min_freq: float = 100,
                      max_freq: float = 10000,
                      max_width_hz: float = 200) -> list:
    """
    Detect resonant peaks in spectrum.
    
    Args:
        frequencies: Frequency bins array
        magnitude_db: Magnitude spectrum in dB
        prominence_db: Minimum prominence for peak detection
        min_freq: Minimum frequency to analyze
        max_freq: Maximum frequency to analyze
        max_width_hz: Maximum width for a peak to be considered resonant
        
    Returns:
        List of dicts with resonance info: {freq, magnitude, q, width}
    """
    # Frequency resolution
    freq_resolution = frequencies[1] - frequencies[0]
    
    # Limit frequency range
    freq_mask = (frequencies >= min_freq) & (frequencies <= max_freq)
    freq_subset = frequencies[freq_mask]
    mag_subset = magnitude_db[freq_mask]
    
    # Convert width limit to bins
    max_width_bins = int(max_width_hz / freq_resolution)
    
    # Find peaks
    peaks, properties = find_peaks(
        mag_subset,
        prominence=prominence_db,
        width=(1, max_width_bins)
    )
    
    resonances = []
    for i, peak_idx in enumerate(peaks):
        freq = freq_subset[peak_idx]
        mag = mag_subset[peak_idx]
        
        # Calculate width and Q
        width_bins = properties['widths'][i]
        width_hz = width_bins * freq_resolution
        q = freq / max(width_hz, 1)  # Q = f_center / bandwidth
        
        resonances.append({
            'frequency': freq,
            'magnitude_db': mag,
            'q': q,
            'width_hz': width_hz,
            'prominence_db': properties['prominences'][i]
        })
    
    return resonances
```

### 6.2 Envelope Follower

```python
def envelope_follower(audio: np.ndarray,
                      sample_rate: int,
                      attack_ms: float = 10.0,
                      release_ms: float = 100.0) -> np.ndarray:
    """
    Compute amplitude envelope with attack/release smoothing.
    
    Args:
        audio: Input audio (mono)
        sample_rate: Sample rate in Hz
        attack_ms: Attack time in milliseconds
        release_ms: Release time in milliseconds
        
    Returns:
        Envelope array (same length as audio)
    """
    # Compute coefficients
    attack_coef = 1 - np.exp(-2.2 / (attack_ms * sample_rate / 1000))
    release_coef = 1 - np.exp(-2.2 / (release_ms * sample_rate / 1000))
    
    # Rectify signal
    rectified = np.abs(audio)
    
    # Envelope follower (iterative for accuracy)
    envelope = np.zeros_like(rectified)
    envelope[0] = rectified[0]
    
    for i in range(1, len(rectified)):
        if rectified[i] > envelope[i-1]:
            # Attack
            envelope[i] = attack_coef * rectified[i] + (1 - attack_coef) * envelope[i-1]
        else:
            # Release
            envelope[i] = release_coef * rectified[i] + (1 - release_coef) * envelope[i-1]
    
    return envelope


def envelope_follower_vectorized(audio: np.ndarray,
                                  sample_rate: int,
                                  attack_ms: float = 10.0,
                                  release_ms: float = 100.0) -> np.ndarray:
    """
    Vectorized envelope follower using scipy (faster for large buffers).
    
    Note: Less accurate than iterative version but suitable for real-time.
    """
    from scipy.signal import lfilter
    
    # Rectify
    rectified = np.abs(audio)
    
    # Use single pole filter (approximation)
    # Blend attack and release via separate filters
    attack_coef = 1 - np.exp(-2.2 / (attack_ms * sample_rate / 1000))
    release_coef = 1 - np.exp(-2.2 / (release_ms * sample_rate / 1000))
    
    # Average coefficient (simplified)
    avg_coef = (attack_coef + release_coef) / 2
    
    b = [avg_coef]
    a = [1, -(1 - avg_coef)]
    
    envelope = lfilter(b, a, rectified)
    
    return envelope
```

### 6.3 Harmonic Exciter Core

```python
def soft_saturate(x: np.ndarray, drive: float = 1.0) -> np.ndarray:
    """
    Soft saturation using tanh.
    Generates both even and odd harmonics (mostly odd).
    """
    return np.tanh(x * drive) / np.tanh(drive)  # Normalize


def tube_saturate(x: np.ndarray, drive: float = 1.0, asymmetry: float = 0.2) -> np.ndarray:
    """
    Asymmetric saturation for tube-like even harmonics.
    
    Args:
        x: Input signal (-1 to 1 range)
        drive: Saturation amount
        asymmetry: 0 = symmetric (odd only), 1 = fully asymmetric (more even)
    """
    # Asymmetric drive
    positive_drive = drive * (1 + asymmetry)
    negative_drive = drive * (1 - asymmetry)
    
    y = np.where(
        x >= 0,
        np.tanh(x * positive_drive),
        np.tanh(x * negative_drive)
    )
    
    return y


def chebyshev_harmonic(x: np.ndarray, n: int) -> np.ndarray:
    """
    Generate nth harmonic using Chebyshev polynomial.
    
    Args:
        x: Input signal (should be normalized to -1 to 1)
        n: Harmonic number (2 = octave, 3 = octave + fifth, etc.)
    """
    if n == 1:
        return x
    elif n == 2:
        return 2 * x**2 - 1
    elif n == 3:
        return 4 * x**3 - 3 * x
    elif n == 4:
        return 8 * x**4 - 8 * x**2 + 1
    elif n == 5:
        return 16 * x**5 - 20 * x**3 + 5 * x
    else:
        # General recursion: T_n(x) = 2x*T_{n-1}(x) - T_{n-2}(x)
        t_prev2 = np.ones_like(x)  # T_0 = 1
        t_prev1 = x.copy()          # T_1 = x
        for _ in range(2, n + 1):
            t_curr = 2 * x * t_prev1 - t_prev2
            t_prev2 = t_prev1
            t_prev1 = t_curr
        return t_prev1


def multiband_exciter(audio: np.ndarray,
                      sample_rate: int,
                      params: 'ExciterParams') -> np.ndarray:
    """
    Apply frequency-dependent harmonic excitation.
    
    Args:
        audio: Input audio (mono or stereo)
        sample_rate: Sample rate
        params: ExciterParams dataclass
        
    Returns:
        Processed audio with added harmonics
    """
    from scipy.signal import butter, sosfilt
    
    # Handle stereo
    if len(audio.shape) == 1:
        channels = [audio]
    else:
        channels = [audio[:, i] for i in range(audio.shape[1])]
    
    processed_channels = []
    
    for channel in channels:
        # Band split
        # Low: < 200 Hz
        sos_low = butter(4, 200, btype='low', fs=sample_rate, output='sos')
        low_band = sosfilt(sos_low, channel)
        
        # Mid: 200 - 2000 Hz
        sos_mid = butter(4, [200, 2000], btype='band', fs=sample_rate, output='sos')
        mid_band = sosfilt(sos_mid, channel)
        
        # High: 2000 - 8000 Hz
        sos_high = butter(4, [2000, 8000], btype='band', fs=sample_rate, output='sos')
        high_band = sosfilt(sos_high, channel)
        
        # Air: > 8000 Hz
        sos_air = butter(4, params.air_freq, btype='high', fs=sample_rate, output='sos')
        air_band = sosfilt(sos_air, channel)
        
        # Normalize for saturation
        def normalize(x):
            peak = np.max(np.abs(x)) + 1e-10
            return x / peak, peak
        
        # Apply saturation per band
        low_norm, low_peak = normalize(low_band)
        low_saturated = tube_saturate(low_norm, params.low_band_drive) * low_peak
        
        mid_norm, mid_peak = normalize(mid_band)
        mid_saturated = tube_saturate(mid_norm, params.mid_band_drive, asymmetry=0.3) * mid_peak
        
        high_norm, high_peak = normalize(high_band)
        high_saturated = tube_saturate(high_norm, params.high_band_drive, asymmetry=0.2) * high_peak
        
        air_norm, air_peak = normalize(air_band)
        air_saturated = soft_saturate(air_norm, params.air_band_drive) * air_peak
        
        # Sum bands
        processed = low_saturated + mid_saturated + high_saturated + air_saturated
        
        # Mix with dry
        output = channel * (1 - params.mix) + processed * params.mix
        
        processed_channels.append(output)
    
    if len(processed_channels) == 1:
        return processed_channels[0]
    else:
        return np.column_stack(processed_channels)
```

### 6.4 De-Esser Core

```python
def de_esser(audio: np.ndarray,
             sample_rate: int,
             params: 'DeEsserParams') -> np.ndarray:
    """
    Apply de-essing to vocal audio.
    
    Args:
        audio: Input audio (mono or stereo)
        sample_rate: Sample rate
        params: DeEsserParams dataclass
        
    Returns:
        De-essed audio
    """
    from scipy.signal import butter, sosfilt
    
    # Handle stereo
    if len(audio.shape) == 1:
        mono = audio
    else:
        mono = np.mean(audio, axis=1)  # Sum to mono for detection
    
    # Extract sibilance band for detection
    sos_sib = butter(4, [params.low_freq, params.high_freq], 
                     btype='band', fs=sample_rate, output='sos')
    sibilance_band = sosfilt(sos_sib, mono)
    
    # Envelope of sibilance band
    sib_envelope = envelope_follower(
        sibilance_band, 
        sample_rate,
        attack_ms=params.attack_ms,
        release_ms=params.release_ms
    )
    
    # Convert to dB
    sib_db = 20 * np.log10(sib_envelope + 1e-10)
    
    # Compute gain reduction
    over_threshold = sib_db - params.threshold_db
    gain_reduction_db = np.where(
        over_threshold > 0,
        -over_threshold * (1 - 1/params.ratio),
        0
    )
    
    # Clamp to max reduction
    gain_reduction_db = np.maximum(gain_reduction_db, params.max_reduction_db)
    
    # Convert to linear gain
    gain = 10 ** (gain_reduction_db / 20)
    
    if params.mode == DeEsserMode.WIDEBAND:
        # Apply gain to full signal
        if len(audio.shape) == 1:
            return audio * gain
        else:
            return audio * gain[:, np.newaxis]
    
    elif params.mode == DeEsserMode.SPLIT_BAND:
        # Only apply gain to high frequency band
        if len(audio.shape) == 1:
            # Split into low and high
            sos_low = butter(4, params.low_freq, btype='low', 
                            fs=sample_rate, output='sos')
            sos_high = butter(4, params.low_freq, btype='high', 
                             fs=sample_rate, output='sos')
            
            low_band = sosfilt(sos_low, audio)
            high_band = sosfilt(sos_high, audio)
            
            # Apply gain only to high band
            high_processed = high_band * gain
            
            return low_band + high_processed
        else:
            # Process each channel
            output = np.zeros_like(audio)
            for ch in range(audio.shape[1]):
                sos_low = butter(4, params.low_freq, btype='low', 
                                fs=sample_rate, output='sos')
                sos_high = butter(4, params.low_freq, btype='high', 
                                 fs=sample_rate, output='sos')
                
                low_band = sosfilt(sos_low, audio[:, ch])
                high_band = sosfilt(sos_high, audio[:, ch])
                
                output[:, ch] = low_band + high_band * gain
            
            return output
    
    else:  # DYNAMIC_EQ mode
        # Use parametric EQ with dynamic gain
        # Simplified: bandpass the sibilance region and apply gain
        sos_sib = butter(2, [params.low_freq, params.high_freq], 
                        btype='band', fs=sample_rate, output='sos')
        
        if len(audio.shape) == 1:
            sib_band = sosfilt(sos_sib, audio)
            return audio + sib_band * (gain - 1)  # Add difference
        else:
            output = audio.copy()
            for ch in range(audio.shape[1]):
                sib_band = sosfilt(sos_sib, audio[:, ch])
                output[:, ch] = audio[:, ch] + sib_band * (gain - 1)
            return output
```

---

## 7. MixChain Integration Notes

### 7.1 Extending EffectType Enum

Add new effect types to [mix_chain.py](../multimodal_gen/mix_chain.py):

```python
class EffectType(Enum):
    # Existing
    EQ_3BAND = "eq_3band"
    COMPRESSOR = "compressor"
    # ...
    
    # New spectral processing types
    DYNAMIC_EQ = "dynamic_eq"
    RESONANCE_SUPPRESSION = "resonance_suppression"
    DE_ESSER = "de_esser"
    EXCITER = "exciter"
```

### 7.2 Processing Order

Recommended order in mastering chain:

```
1. De-Esser (if vocals present)
2. Dynamic EQ (surgical problem solving)
3. Resonance Suppression (automatic cleanup)
4. [Existing: EQ, Compression]
5. Exciter (add harmonics after dynamics)
6. [Existing: Saturation, Limiting]
```

### 7.3 Latency Considerations

| Effect | Typical Latency | Cause |
|--------|-----------------|-------|
| Dynamic EQ | 1-5 ms | Lookahead |
| Resonance Suppression | 20-100 ms | FFT analysis |
| De-Esser | 1-5 ms | Lookahead |
| Exciter | 0 ms | No lookahead needed |

For real-time use, consider:
- Reducing FFT size for resonance detection
- Disabling lookahead for dynamic EQ
- Using split-band de-essing (lower latency than dynamic EQ mode)

### 7.4 CPU Optimization

For real-time processing:
1. Use `scipy.fft` (faster than numpy for large arrays)
2. Process in blocks matching FFT hop size
3. Vectorize envelope followers where possible
4. Consider SIMD via NumPy ufuncs
5. For production: port critical paths to Cython or use `numba.jit`

---

## 8. Professional References

### 8.1 Hardware/Software Models

| Product | Technique | Notable Features |
|---------|-----------|------------------|
| **FabFilter Pro-Q 3** | Dynamic EQ | Per-band dynamics, linear phase option, spectrum analyzer |
| **Soothe2** | Resonance Suppression | Spectral dynamics, soft/hard modes, delta preview |
| **Soundtoys Decapitator** | Saturation/Exciter | 5 saturation styles, tone control, mix knob |
| **Soundtoys Radiator** | Tube Saturation | Altec 1567A emulation, transformer harmonics |
| **Maag EQ4** | Air Enhancement | 40kHz "Air Band" shelf, 6 frequency options |
| **Waves De-Esser** | De-Essing | Wideband/split, sidechain listen, auto threshold |
| **FabFilter Pro-DS** | De-Essing | Lookahead, allround/single-band, audition modes |

### 8.2 Academic References

1. **Spectral Processing:** Zölzer, U. "DAFX: Digital Audio Effects" (Wiley, 2011)
2. **Dynamics Processing:** Giannoulis et al. "Digital Dynamic Range Compressor Design—A Tutorial and Analysis" (JAES, 2012)
3. **Harmonic Analysis:** Smith, J.O. "Spectral Audio Signal Processing" (W3K Publishing, 2011) - Available free online
4. **Peak Detection:** SciPy documentation for `scipy.signal.find_peaks`

### 8.3 Key Algorithms Summary

| Technique | Core Algorithm | Key Parameters |
|-----------|---------------|----------------|
| Dynamic EQ | Envelope follower + threshold-gated gain | Frequency, Q, threshold, ratio, attack/release |
| Resonance Detection | FFT + peak finding + prominence analysis | FFT size, prominence threshold, Q threshold |
| Harmonic Exciter | Waveshaping (tanh, Chebyshev) | Drive, even/odd balance, frequency bands |
| De-Esser | Band-split + fast envelope + compression | Sibilance freq range, threshold, ratio, attack |

---

## Appendix A: Quick Reference Formulas

### Envelope Follower Coefficients
```
attack_coef = 1 - exp(-2.2 / (attack_ms * sample_rate / 1000))
release_coef = 1 - exp(-2.2 / (release_ms * sample_rate / 1000))
```

### Q Factor
```
Q = f_center / bandwidth
bandwidth = f_upper - f_lower (at -3dB points)
```

### dB Conversions
```
dB = 20 * log10(linear)
linear = 10^(dB/20)
```

### Compression Gain Reduction
```
gain_reduction_dB = over_threshold_dB * (1 - 1/ratio)
```

### Soft Saturation (Tanh)
```
y = tanh(drive * x)
```

### Chebyshev Polynomials (Harmonic Generation)
```
T_2(x) = 2x² - 1       (2nd harmonic)
T_3(x) = 4x³ - 3x      (3rd harmonic)
T_4(x) = 8x⁴ - 8x² + 1 (4th harmonic)
```

---

*End of Research Document*
