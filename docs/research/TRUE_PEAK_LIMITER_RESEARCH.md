# True Peak Limiting with Inter-Sample Peak (ISP) Detection
## Research Report for Broadcast-Compliant Mastering

**Document Version:** 1.0  
**Date:** January 17, 2026  
**Scope:** DSP Research & Specification  

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Inter-Sample Peaks (ISP) - The Problem](#inter-sample-peaks-isp---the-problem)
3. [Mathematical Foundation](#mathematical-foundation)
4. [ISP Detection Methods](#isp-detection-methods)
5. [Broadcast Standards](#broadcast-standards)
6. [True Peak Limiter Design](#true-peak-limiter-design)
7. [Professional Reference Implementations](#professional-reference-implementations)
8. [Python Implementation Guidelines](#python-implementation-guidelines)
9. [Data Structures & Schema](#data-structures--schema)
10. [Compliance Verification](#compliance-verification)
11. [References](#references)

---

## Executive Summary

**Inter-Sample Peaks (ISP)** are signal peaks that occur between discrete digital samples when the audio is reconstructed during digital-to-analog (D/A) conversion. Standard peak limiters that only examine sample values will miss these peaks, potentially causing:

- Clipping/distortion on playback devices
- Non-compliance with broadcast loudness standards
- Codec artifacts during lossy encoding (MP3, AAC, Opus)
- Failed quality control checks for streaming platforms

**True Peak limiting** addresses this by:
1. Detecting peaks in the reconstructed continuous-time signal (via oversampling)
2. Limiting with sufficient lookahead to catch ISP before they occur
3. Meeting broadcast specifications (EBU R128, ITU-R BS.1770)

---

## Inter-Sample Peaks (ISP) - The Problem

### Why ISP Occur

Digital audio represents a continuous analog signal as discrete samples taken at regular intervals (e.g., 44,100 samples/second for CD audio). According to the **Nyquist-Shannon sampling theorem**, if we sample above twice the highest frequency component, we can perfectly reconstruct the original signal.

However, the **reconstruction** process uses interpolation (typically sinc interpolation in ideal D/A converters), which can produce values BETWEEN samples that exceed any individual sample value.

### The Overshoot Phenomenon

```
Sample values:        [0.95]  [0.98]  [0.95]
                         │       │       │
Reconstructed signal:    │   ┌───┴───┐   │
                         │  /         \  │
                     ────┴─/───────────\─┴────
                          │     ▲       │
                          │   1.03 dB   │  ← TRUE PEAK (exceeds 0 dBFS!)
                          │   (ISP)     │
```

**Key insight:** When consecutive samples are near 0 dBFS (full scale), the smooth interpolation curve can overshoot, creating peaks up to **+3 dB** above the sample values.

### Why Standard Limiters Miss ISP

Standard peak limiters operate on a per-sample basis:

```python
# Standard peak limiter (INCORRECT for True Peak)
def naive_limit(sample, ceiling):
    if abs(sample) > ceiling:
        return ceiling * np.sign(sample)
    return sample
```

This only checks sample values, not the interpolated waveform. A signal could have all samples at -0.1 dBFS yet produce True Peaks at +1.5 dBFS after reconstruction.

### Common ISP Scenarios

| Scenario | Description | Typical Overshoot |
|----------|-------------|-------------------|
| **Sine wave at Nyquist/2** | 11 kHz @ 44.1 kHz SR | Up to +0.5 dB |
| **Consecutive high samples** | Plateau near 0 dBFS | Up to +1.5 dB |
| **Sharp transients** | Limiting artifacts | Up to +3.0 dB |
| **Lossy codec output** | MP3/AAC reconstruction | Up to +2.0 dB |

---

## Mathematical Foundation

### Sinc Interpolation (Ideal Reconstruction)

The continuous-time signal $x(t)$ is reconstructed from samples $x[n]$ using the **sinc interpolation formula**:

$$x(t) = \sum_{n=-\infty}^{\infty} x[n] \cdot \text{sinc}\left(\frac{t - nT_s}{T_s}\right)$$

Where:
- $T_s = 1/f_s$ is the sampling period
- $\text{sinc}(x) = \frac{\sin(\pi x)}{\pi x}$

### Peak Overshoot Analysis

For a signal approaching 0 dBFS, the maximum overshoot depends on the signal's spectral content. The worst-case occurs when:

1. Consecutive samples are at maximum amplitude
2. The signal has significant energy near Nyquist/2

**Theoretical maximum overshoot** for bandlimited signals:

$$\text{Overshoot}_{\text{max}} \approx \frac{\pi}{4} \approx 0.785 \approx +3.9 \text{ dB}$$

In practice, typical music content exhibits overshoots of **0.5 to 2.0 dB**.

### True Peak Calculation

True Peak level in dBTP (decibels True Peak) is:

$$\text{TP}_{\text{dBTP}} = 20 \cdot \log_{10}(\text{max}(|x_{\text{oversampled}}|))$$

Where $x_{\text{oversampled}}$ is the signal after oversampling (typically 4x).

---

## ISP Detection Methods

### Method 1: Oversampling (ITU-R BS.1770 Standard)

The **ITU-R BS.1770-4** standard specifies 4x oversampling for True Peak measurement.

**Pseudocode:**

```
function measure_true_peak(samples, sample_rate):
    # Step 1: Upsample by 4x using polyphase filter
    oversampled = upsample_4x(samples)
    
    # Step 2: Find absolute maximum in oversampled domain
    true_peak_linear = max(abs(oversampled))
    
    # Step 3: Convert to dBTP
    true_peak_dbtp = 20 * log10(true_peak_linear)
    
    return true_peak_dbtp
```

**Oversampling ratios:**

| Factor | Use Case | Accuracy | CPU Cost |
|--------|----------|----------|----------|
| 2x | Quick preview | ±0.5 dB | Low |
| **4x** | **ITU Standard** | **±0.1 dB** | **Medium** |
| 8x | High precision | ±0.01 dB | High |
| 16x | Research/validation | Near-exact | Very High |

### Method 2: Polyphase Filter Upsampling

More efficient than FFT-based resampling for real-time applications:

```
function polyphase_upsample_4x(samples, filter_coeffs):
    # Filter coefficients: Low-pass FIR with cutoff at fs/2
    # Typically 32-128 taps Kaiser windowed
    
    output = zeros(len(samples) * 4)
    
    for phase in [0, 1, 2, 3]:
        # Apply polyphase filter bank
        output[phase::4] = convolve(samples, filter_coeffs[phase])
    
    return output
```

### Method 3: Parabolic Interpolation (Fast Approximation)

For real-time applications with CPU constraints:

```
function estimate_intersample_peak(s0, s1, s2):
    # Fit parabola through 3 consecutive samples
    # s0 = sample at n-1
    # s1 = sample at n (current)
    # s2 = sample at n+1
    
    # Parabola: y = a*x² + b*x + c
    a = (s0 + s2) / 2 - s1
    b = (s2 - s0) / 2
    c = s1
    
    # Peak occurs at x = -b / (2a)
    if a != 0:
        x_peak = -b / (2 * a)
        if -1 <= x_peak <= 1:  # Peak is between samples
            peak_value = a * x_peak² + b * x_peak + c
            return abs(peak_value)
    
    return max(abs(s0), abs(s1), abs(s2))
```

**Accuracy comparison:**

| Method | Max Error | Latency | CPU |
|--------|-----------|---------|-----|
| 4x Oversampling | ±0.1 dB | ~1ms | Medium |
| Parabolic | ±1.0 dB | 0 | Very Low |
| Sinc (direct) | ±0.01 dB | ~5ms | High |

### ITU-R BS.1770-4 Filter Specification

The standard specifies a **4x oversampling** with this filter characteristic:

- **Filter type:** FIR lowpass
- **Cutoff frequency:** 0.5 × original Nyquist (fs/4 of oversampled)
- **Stopband attenuation:** ≥ 50 dB
- **Passband ripple:** ≤ 0.1 dB
- **Recommended taps:** 48 (12 per phase)

---

## Broadcast Standards

### EBU R128 (European Broadcasting Union)

**Key specifications for True Peak:**

| Parameter | Requirement |
|-----------|-------------|
| **True Peak Maximum** | **-1 dBTP** |
| Target Loudness | -23 LUFS (±1 LU) |
| Loudness Range | Unrestricted (recommend 5-20 LU) |
| Measurement | ITU-R BS.1770-4 algorithm |

### ITU-R BS.1770-5 (International Standard)

The definitive specification for loudness and True Peak measurement:

1. **K-weighted filtering** for perceived loudness
2. **4x oversampling** for True Peak measurement
3. **Gate threshold** at -10 LU (relative) for LUFS calculation
4. **Measurement window** of 400ms for momentary loudness

### Streaming Platform Requirements

| Platform | True Peak Limit | Target Loudness |
|----------|-----------------|-----------------|
| **Spotify** | **-1 dBTP** | -14 LUFS |
| **Apple Music** | **-1 dBTP** | -16 LUFS |
| **YouTube** | **-1 dBTP** | -14 LUFS |
| **Amazon Music** | **-2 dBTP** | -14 LUFS |
| **Tidal** | **-1 dBTP** | -14 LUFS |
| **SoundCloud** | **-1 dBTP** | -14 LUFS |

**Note:** Most platforms normalize to their target loudness. Exceeding True Peak limits causes clipping or re-encoding artifacts.

---

## True Peak Limiter Design

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    TRUE PEAK LIMITER                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  INPUT ──► [4x Upsample] ──► [Peak Detect] ──► [Gain Calc]     │
│                   │                               │             │
│                   │                               ▼             │
│                   └──────────────────────► [Gain Apply]        │
│                                                   │             │
│                                                   ▼             │
│                                            [4x Downsample]     │
│                                                   │             │
│                                                   ▼             │
│                                               OUTPUT            │
│                                                                 │
│  ◄─────────────── LOOKAHEAD DELAY ──────────────►              │
│         (typically 1.5-5ms = 64-220 samples @ 44.1kHz)         │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Critical Design Parameters

#### 1. Lookahead Time

Lookahead allows the limiter to "see" upcoming peaks and apply gain reduction smoothly:

| Lookahead | Trade-off |
|-----------|-----------|
| 0.5 ms | Fast response but audible pumping |
| **1.5 ms** | **Good balance for mastering** |
| 3.0 ms | Very clean but adds latency |
| 5.0 ms | Transparent but high latency |

```
lookahead_samples = sample_rate * lookahead_ms / 1000
# For 44.1 kHz, 1.5ms = 66 samples
```

#### 2. Attack Time

Must be fast enough to catch ISP but not so fast as to cause distortion:

```
attack_time_ms = 0.1  # to 1.0 ms typical
attack_coeff = exp(-1.0 / (attack_time_ms * sample_rate / 1000))
```

#### 3. Release Time

Program-dependent release for musical limiting:

```
# Adaptive release based on gain reduction depth
if gain_reduction < -6 dB:
    release_ms = 200  # Slower for heavy limiting
else:
    release_ms = 50   # Faster for light limiting
```

#### 4. Oversampled Processing

Process gain calculation in oversampled domain, then downsample:

```
# Process at 4x, then anti-alias filter on downsample
oversampled_gain = calculate_gain_reduction(oversampled_signal, threshold)
final_output = downsample_4x(oversampled_signal * oversampled_gain)
```

### Brickwall vs. Soft-Knee Limiting

**Brickwall (Hard-knee):**
- Guarantees ceiling is never exceeded
- Can sound harsh on transients
- Required for strict True Peak compliance

**Soft-knee:**
- Gentler compression curve near threshold
- More musical sound
- May allow micro-overshoots (not compliant)

```
# Brickwall gain calculation
if peak > threshold:
    gain = threshold / peak  # Hard limit
    
# Soft-knee gain calculation (NOT for True Peak compliance)
knee_width_db = 6.0
if peak > (threshold - knee_width):
    # Gradual compression in knee region
    overshoot = peak - threshold + knee_width
    gain = 1.0 - (overshoot ** 2) / (4 * knee_width)
```

### Complete Limiter Algorithm Pseudocode

```
class TruePeakLimiter:
    initialize(sample_rate, ceiling_dbtp, lookahead_ms, release_ms):
        self.sample_rate = sample_rate
        self.ceiling = 10^(ceiling_dbtp / 20)
        self.lookahead_samples = int(sample_rate * lookahead_ms / 1000)
        self.release_coeff = exp(-1 / (release_ms * sample_rate / 1000))
        
        # Buffers
        self.delay_buffer = circular_buffer(lookahead_samples)
        self.gain_buffer = circular_buffer(lookahead_samples)
        self.envelope = 0.0
        
        # 4x oversampling filters
        self.upsample_filter = design_lowpass_fir(48)  # 48 taps
        self.downsample_filter = design_lowpass_fir(48)
    
    process_block(input_samples):
        # 1. Upsample 4x
        oversampled = polyphase_upsample(input_samples, 4, self.upsample_filter)
        
        # 2. Calculate gain reduction envelope
        for i in range(len(oversampled)):
            peak = abs(oversampled[i])
            
            # Attack: instant for peaks above ceiling
            if peak > self.ceiling:
                target_gain = self.ceiling / peak
            else:
                target_gain = 1.0
            
            # Update envelope with release
            if target_gain < self.envelope:
                self.envelope = target_gain  # Instant attack
            else:
                self.envelope = self.release_coeff * self.envelope + 
                               (1 - self.release_coeff) * target_gain
            
            self.gain_buffer.push(self.envelope)
        
        # 3. Apply lookahead: use minimum gain in lookahead window
        smoothed_gain = zeros(len(oversampled))
        for i in range(len(oversampled)):
            # Look ahead for minimum gain
            lookahead_window = self.gain_buffer.get_range(i, i + lookahead_samples * 4)
            smoothed_gain[i] = min(lookahead_window)
        
        # 4. Apply gain in oversampled domain
        limited = oversampled * smoothed_gain
        
        # 5. Downsample with anti-aliasing
        output = polyphase_downsample(limited, 4, self.downsample_filter)
        
        # 6. Apply delay compensation
        delayed_input = self.delay_buffer.read(lookahead_samples)
        self.delay_buffer.write(input_samples)
        
        return output
```

---

## Professional Reference Implementations

### iZotope Maximizer (True Peak Mode)

Key characteristics:
- **IRC (Intelligent Release Control):** Adaptive release based on program content
- **Character modes:** Clean, Punchy, Pumping
- **Oversampling:** Up to 4x internally
- **Lookahead:** Variable, user-controlled

### FabFilter Pro-L 2

Features relevant to True Peak:
- **True Peak limiting mode** with ITU-R BS.1770 compliance
- **Up to 32x oversampling** (overkill but ultra-transparent)
- **8 algorithm styles:** Modern, Aggressive, Safe, etc.
- **Lookahead:** Automatic based on algorithm

### Nugen ISL (Inter-Sample Peak Limiter)

Purpose-built for broadcast compliance:
- **Real-time True Peak metering**
- **Look-behind correction** (fixes ISP after the fact)
- **BS.1770 compliant** measurement
- **Presets** for all major streaming platforms

### Sonnox Oxford Limiter v3

- **Enhance mode:** Adds harmonics while limiting
- **True Peak mode:** Guarantees compliance
- **Reconstruction:** Uses proprietary oversampling

---

## Python Implementation Guidelines

### Recommended SciPy Functions

#### Upsampling with `scipy.signal.resample_poly`

```python
import numpy as np
from scipy import signal

def upsample_4x(audio: np.ndarray, sample_rate: int) -> np.ndarray:
    """
    Upsample audio by 4x using polyphase filtering.
    
    ITU-R BS.1770-4 compliant True Peak measurement requires
    at least 4x oversampling.
    
    Args:
        audio: Input audio samples (mono)
        sample_rate: Original sample rate (for filter design)
        
    Returns:
        Upsampled audio (4x the input length)
    """
    # Use polyphase filtering for efficiency
    # up=4, down=1 gives 4x upsampling
    # Kaiser window with beta=5.0 gives good stopband rejection
    upsampled = signal.resample_poly(audio, up=4, down=1, window=('kaiser', 5.0))
    
    return upsampled


def downsample_4x(audio: np.ndarray) -> np.ndarray:
    """
    Downsample audio by 4x with anti-aliasing.
    
    Must apply lowpass filter before downsampling to prevent aliasing.
    """
    # down=4, up=1 gives 4x downsampling with built-in anti-aliasing
    downsampled = signal.resample_poly(audio, up=1, down=4, window=('kaiser', 5.0))
    
    return downsampled
```

#### Alternative: FFT-based Resampling (Higher Quality)

```python
def upsample_4x_fft(audio: np.ndarray) -> np.ndarray:
    """
    Upsample using FFT method - higher quality but slower.
    
    Ideal for offline processing where quality is paramount.
    """
    target_samples = len(audio) * 4
    return signal.resample(audio, target_samples)
```

### True Peak Measurement Function

```python
def measure_true_peak_dbtp(audio: np.ndarray, sample_rate: int = 44100) -> float:
    """
    Measure True Peak level per ITU-R BS.1770-4.
    
    Args:
        audio: Audio samples, mono or stereo (shape: [samples] or [samples, channels])
        sample_rate: Sample rate in Hz
        
    Returns:
        True Peak level in dBTP (decibels True Peak)
    """
    # Ensure 2D array
    if audio.ndim == 1:
        audio = audio[:, np.newaxis]
    
    max_peak = 0.0
    
    # Process each channel
    for ch in range(audio.shape[1]):
        channel = audio[:, ch]
        
        # Upsample 4x
        oversampled = signal.resample_poly(channel, up=4, down=1, window=('kaiser', 5.0))
        
        # Find peak
        channel_peak = np.max(np.abs(oversampled))
        max_peak = max(max_peak, channel_peak)
    
    # Convert to dBTP
    if max_peak > 0:
        return 20 * np.log10(max_peak)
    else:
        return -np.inf
```

### Filter Design for Oversampling

```python
def design_true_peak_filter(num_taps: int = 48) -> np.ndarray:
    """
    Design FIR lowpass filter for True Peak measurement.
    
    ITU-R BS.1770-4 recommends:
    - At least 4 filter coefficients per phase (48 taps for 4x oversampling)
    - Stopband attenuation >= 50 dB
    - Passband ripple <= 0.1 dB
    
    Args:
        num_taps: Number of filter coefficients (must be divisible by 4)
        
    Returns:
        FIR filter coefficients
    """
    # Kaiser window beta for ~50 dB stopband attenuation
    beta = 4.5
    
    # Cutoff at 0.5 * Nyquist of oversampled signal = 0.125 normalized
    cutoff = 0.125
    
    # Design lowpass FIR
    coeffs = signal.firwin(num_taps, cutoff, window=('kaiser', beta))
    
    return coeffs
```

---

## Data Structures & Schema

### TruePeakLimiterParams Dataclass

```python
from dataclasses import dataclass, field
from typing import Optional, List, Literal
from enum import Enum


class LimiterAlgorithm(Enum):
    """Limiting algorithm style."""
    TRANSPARENT = "transparent"    # Clean, minimal coloration
    AGGRESSIVE = "aggressive"      # Punchy, more compression character
    SAFE = "safe"                  # Extra margin for codec encoding
    BROADCAST = "broadcast"        # Strict EBU R128 compliance


class OversamplingFactor(Enum):
    """Oversampling rate for True Peak detection."""
    X2 = 2   # Fast preview
    X4 = 4   # ITU standard (recommended)
    X8 = 8   # High precision
    X16 = 16 # Maximum quality


@dataclass
class TruePeakLimiterParams:
    """
    Configuration parameters for True Peak limiting.
    
    Designed for broadcast-compliant mastering per EBU R128 and ITU-R BS.1770-4.
    """
    
    # Core limiting parameters
    ceiling_dbtp: float = -1.0
    """True Peak ceiling in dBTP. -1 dBTP for most streaming platforms."""
    
    lookahead_ms: float = 1.5
    """Lookahead time in milliseconds. Range: 0.1 to 10.0 ms."""
    
    release_ms: float = 100.0
    """Release time in milliseconds. Range: 10 to 1000 ms."""
    
    attack_ms: float = 0.1
    """Attack time in milliseconds. Near-instant for True Peak compliance."""
    
    # Oversampling configuration
    oversampling: OversamplingFactor = OversamplingFactor.X4
    """Oversampling factor for ISP detection. 4x is ITU standard."""
    
    # Algorithm selection
    algorithm: LimiterAlgorithm = LimiterAlgorithm.TRANSPARENT
    """Limiting algorithm/character."""
    
    # Advanced parameters
    knee_db: float = 0.0
    """Soft knee width in dB. 0 = brickwall (required for True Peak compliance)."""
    
    channel_link: float = 1.0
    """Stereo linking. 1.0 = fully linked, 0.0 = independent channels."""
    
    auto_release: bool = True
    """Enable program-dependent adaptive release."""
    
    # Safety margin for lossy codecs
    codec_margin_db: float = 0.0
    """Extra headroom for codec encoding. +0.5 dB recommended for MP3/AAC."""
    
    def effective_ceiling(self) -> float:
        """Calculate effective ceiling with codec margin."""
        return self.ceiling_dbtp - self.codec_margin_db
    
    def validate(self) -> List[str]:
        """Validate parameters and return list of warnings."""
        warnings = []
        
        if self.ceiling_dbtp > 0:
            warnings.append("Ceiling above 0 dBTP will cause clipping")
        
        if self.ceiling_dbtp > -1.0:
            warnings.append("Ceiling above -1 dBTP may fail streaming platform QC")
        
        if self.knee_db > 0 and self.algorithm == LimiterAlgorithm.BROADCAST:
            warnings.append("Soft knee is not compliant for broadcast")
        
        if self.oversampling.value < 4:
            warnings.append("Oversampling below 4x is not ITU-R BS.1770 compliant")
        
        if self.lookahead_ms < 0.5:
            warnings.append("Very short lookahead may cause audible artifacts")
        
        return warnings


@dataclass
class TruePeakMeasurement:
    """Result of True Peak measurement."""
    
    true_peak_dbtp: float
    """Measured True Peak level in dBTP."""
    
    sample_peak_dbfs: float
    """Sample peak level in dBFS (for comparison)."""
    
    overshoot_db: float
    """Difference between True Peak and Sample Peak."""
    
    peak_location_samples: int
    """Sample index where True Peak occurred."""
    
    is_compliant: bool
    """Whether signal meets specified ceiling."""
    
    target_ceiling_dbtp: float
    """Target ceiling that was tested against."""


@dataclass
class TruePeakLimiterState:
    """Runtime state for True Peak limiter processing."""
    
    gain_reduction_db: float = 0.0
    """Current gain reduction in dB."""
    
    peak_hold_db: float = -np.inf
    """Peak hold for metering."""
    
    envelope: float = 1.0
    """Current envelope follower state."""
    
    samples_processed: int = 0
    """Total samples processed."""
    
    clipping_events: int = 0
    """Number of times limiting was applied."""


@dataclass
class BroadcastPreset:
    """Preset configurations for different broadcast/streaming targets."""
    
    name: str
    ceiling_dbtp: float
    target_lufs: float
    codec_margin_db: float = 0.0
    notes: str = ""


# Pre-defined broadcast presets
BROADCAST_PRESETS = {
    "spotify": BroadcastPreset(
        name="Spotify",
        ceiling_dbtp=-1.0,
        target_lufs=-14.0,
        codec_margin_db=0.5,
        notes="Spotify normalizes to -14 LUFS with Ogg Vorbis encoding"
    ),
    "apple_music": BroadcastPreset(
        name="Apple Music",
        ceiling_dbtp=-1.0,
        target_lufs=-16.0,
        codec_margin_db=0.5,
        notes="Apple uses Sound Check normalization to -16 LUFS"
    ),
    "youtube": BroadcastPreset(
        name="YouTube",
        ceiling_dbtp=-1.0,
        target_lufs=-14.0,
        codec_margin_db=0.3,
        notes="YouTube normalizes to -14 LUFS"
    ),
    "ebu_r128": BroadcastPreset(
        name="EBU R128 Broadcast",
        ceiling_dbtp=-1.0,
        target_lufs=-23.0,
        codec_margin_db=0.0,
        notes="European broadcast standard"
    ),
    "atsc_a85": BroadcastPreset(
        name="ATSC A/85 (US Broadcast)",
        ceiling_dbtp=-2.0,
        target_lufs=-24.0,
        codec_margin_db=0.0,
        notes="US broadcast standard (CALM Act)"
    ),
    "amazon_music": BroadcastPreset(
        name="Amazon Music",
        ceiling_dbtp=-2.0,
        target_lufs=-14.0,
        codec_margin_db=0.5,
        notes="Amazon uses -2 dBTP for extra safety"
    ),
}
```

---

## Compliance Verification

### Test Procedure for True Peak Compliance

```python
def verify_true_peak_compliance(
    audio: np.ndarray,
    sample_rate: int,
    target_ceiling_dbtp: float = -1.0
) -> TruePeakMeasurement:
    """
    Verify audio meets True Peak compliance.
    
    Per ITU-R BS.1770-4, measurement uses 4x oversampling.
    
    Args:
        audio: Audio to verify
        sample_rate: Sample rate
        target_ceiling_dbtp: Target ceiling (default: -1 dBTP for streaming)
        
    Returns:
        TruePeakMeasurement with compliance status
    """
    # Measure sample peak
    sample_peak = np.max(np.abs(audio))
    sample_peak_dbfs = 20 * np.log10(sample_peak) if sample_peak > 0 else -np.inf
    
    # Measure true peak with 4x oversampling
    if audio.ndim == 1:
        audio = audio[:, np.newaxis]
    
    max_true_peak = 0.0
    peak_location = 0
    
    for ch in range(audio.shape[1]):
        oversampled = signal.resample_poly(audio[:, ch], 4, 1, window=('kaiser', 5.0))
        ch_peak_idx = np.argmax(np.abs(oversampled))
        ch_peak = np.abs(oversampled[ch_peak_idx])
        
        if ch_peak > max_true_peak:
            max_true_peak = ch_peak
            peak_location = ch_peak_idx // 4  # Convert back to original sample index
    
    true_peak_dbtp = 20 * np.log10(max_true_peak) if max_true_peak > 0 else -np.inf
    overshoot = true_peak_dbtp - sample_peak_dbfs
    
    return TruePeakMeasurement(
        true_peak_dbtp=true_peak_dbtp,
        sample_peak_dbfs=sample_peak_dbfs,
        overshoot_db=overshoot,
        peak_location_samples=peak_location,
        is_compliant=true_peak_dbtp <= target_ceiling_dbtp,
        target_ceiling_dbtp=target_ceiling_dbtp
    )
```

### Test Signals for Validation

To verify a True Peak limiter implementation, use these test signals:

```python
def generate_isp_test_signal(sample_rate: int, duration_s: float = 1.0) -> np.ndarray:
    """
    Generate signal known to produce inter-sample peaks.
    
    A sine wave at Nyquist/2 with amplitude 0.9 will produce
    ISP of approximately +1 dB.
    """
    t = np.arange(int(sample_rate * duration_s)) / sample_rate
    frequency = sample_rate / 4  # Nyquist / 2
    signal = 0.9 * np.sin(2 * np.pi * frequency * t)
    return signal


def generate_worst_case_isp(sample_rate: int, num_samples: int = 1000) -> np.ndarray:
    """
    Generate worst-case ISP test signal.
    
    Alternating +0.95, -0.95 samples produce maximum overshoot.
    """
    signal = np.zeros(num_samples)
    signal[::2] = 0.95
    signal[1::2] = -0.95
    return signal
```

### Expected Test Results

| Test Signal | Sample Peak | Expected True Peak | Overshoot |
|-------------|-------------|-------------------|-----------|
| Sine @ fs/4, amp=0.9 | -0.92 dBFS | ~0.0 dBTP | ~0.9 dB |
| Alternating ±0.95 | -0.45 dBFS | ~+2.5 dBTP | ~3.0 dB |
| Pink noise, normalized | 0.0 dBFS | ~+0.5 dBTP | ~0.5 dB |
| Mastered music, limited to 0 dBFS | 0.0 dBFS | +1 to +2 dBTP | 1-2 dB |

---

## References

### Standards Documents

1. **ITU-R BS.1770-5** (2023) - "Algorithms to measure audio programme loudness and true-peak audio level"
   - Definitive specification for True Peak measurement
   - Available: https://www.itu.int/rec/R-REC-BS.1770

2. **EBU R128** (2020) - "Loudness normalisation and permitted maximum level of audio signals"
   - European broadcast loudness standard
   - Available: https://tech.ebu.ch/publications/r128

3. **EBU Tech 3341** - "Loudness Metering: 'EBU Mode' metering to supplement loudness normalisation"
   - Detailed metering specifications

4. **AES TD1004.1.15-10** - "Recommendation for Loudness of Audio Streaming"
   - Streaming platform guidelines

### Academic Papers

5. Nielsen, S.H. & Lund, T. (2003) - "Overload in Signal Conversion"
   - Seminal paper on inter-sample peaks
   - TC Electronic technical paper

6. Katz, B. (2015) - "Mastering Audio: The Art and the Science" (3rd Edition)
   - Chapter on loudness and True Peak limiting

### Software Documentation

7. **SciPy Signal Processing Reference**
   - `scipy.signal.resample_poly` - Polyphase resampling
   - `scipy.signal.resample` - FFT-based resampling
   - https://docs.scipy.org/doc/scipy/reference/signal.html

8. **libebur128** - Open-source BS.1770 implementation
   - Reference implementation for loudness measurement
   - https://github.com/jiixyj/libebur128

---

## Summary: Key Implementation Decisions

| Decision Point | Recommendation | Rationale |
|----------------|----------------|-----------|
| Oversampling factor | **4x** | ITU standard, good accuracy/CPU balance |
| Filter type | **Polyphase FIR** | Efficient, linear phase |
| Filter taps | **48** | 12 per phase, meets spec |
| Lookahead | **1.5 ms** | Clean limiting, manageable latency |
| Attack | **< 0.1 ms** | Must catch ISP |
| Release | **Adaptive 50-200 ms** | Program-dependent |
| Ceiling | **-1.0 dBTP** | Meets all major platforms |
| Codec margin | **+0.5 dB** | For MP3/AAC safety |

---

*This research document provides specifications only. Implementation should be validated against ITU-R BS.1770 reference signals and professional True Peak meters.*
