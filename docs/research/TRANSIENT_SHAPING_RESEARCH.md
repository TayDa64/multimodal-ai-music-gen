# Transient Shaping: Comprehensive DSP Research Report

**Research Date:** January 17, 2026  
**Domain:** Professional Audio Mixing / Digital Signal Processing  
**Scope:** Transient detection, attack/sustain separation, and envelope-based processing

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Transient Detection Algorithms](#1-transient-detection-algorithms)
3. [Attack Enhancement Techniques](#2-attack-enhancement-techniques)
4. [Sustain Control Methods](#3-sustain-control-methods)
5. [Professional Implementation Analysis](#4-professional-implementation-analysis)
6. [Use Cases & Recipes](#5-use-cases--recipes)
7. [Data Structures & Schemas](#6-data-structures--schemas)
8. [Artifact Avoidance](#7-artifact-avoidance)
9. [References](#8-references)

---

## Executive Summary

Transient shaping is a dynamics processing technique that allows independent control of the **attack** (initial transient) and **sustain** (decay/body) portions of a sound. Unlike compressors that respond to level thresholds, transient shapers detect the *envelope shape* and apply gain modification based on whether the signal is rising (transient) or falling (sustain).

### Core Principle

The fundamental approach is **differential envelope detection**:

```
Transient Signal = Fast Envelope - Slow Envelope
Sustain Signal = Slow Envelope
```

By controlling gain applied to each component separately, we achieve:
- **Attack boost**: Punch, snap, definition
- **Attack reduction**: Softer, smoother, less aggressive
- **Sustain boost**: Ambient, lush, fuller
- **Sustain reduction**: Tight, dry, controlled decay

---

## 1. Transient Detection Algorithms

### 1.1 Envelope Follower Design

The envelope follower is the core building block. It tracks the amplitude contour of a signal using a one-pole lowpass filter with asymmetric attack/release coefficients.

#### Mathematical Foundation

**One-pole filter coefficient from time constant:**

$$
\alpha = e^{-\frac{1}{\tau \cdot f_s}}
$$

Where:
- $\alpha$ = filter coefficient (0 to 1)
- $\tau$ = time constant in seconds  
- $f_s$ = sample rate in Hz

**Alternative formulation (from cutoff frequency):**

$$
\alpha = e^{-2\pi \cdot \frac{f_c}{f_s}}
$$

Where $f_c$ is the cutoff frequency in Hz.

#### Time Constant to Coefficient Conversion

| Time (ms) | Coefficient @ 44.1kHz | Coefficient @ 48kHz |
|-----------|----------------------|---------------------|
| 0.1       | 0.7959               | 0.8106              |
| 1.0       | 0.9773               | 0.9792              |
| 5.0       | 0.9955               | 0.9958              |
| 10.0      | 0.9977               | 0.9979              |
| 50.0      | 0.9995               | 0.9996              |
| 100.0     | 0.9998               | 0.9998              |

#### Envelope Follower Pseudocode

```
FUNCTION envelope_follower(input, attack_coeff, release_coeff):
    state = 0
    output = []
    
    FOR sample IN input:
        rectified = ABS(sample)  # or sample^2 for RMS-like behavior
        
        IF rectified > state:
            # Attack phase - fast rise
            coeff = attack_coeff
        ELSE:
            # Release phase - slow decay
            coeff = release_coeff
        
        state = coeff * state + (1 - coeff) * rectified
        output.APPEND(state)
    
    RETURN output
```

**NumPy Reference Implementation:**

```python
import numpy as np

def compute_envelope_coeff(time_ms: float, sample_rate: int) -> float:
    """
    Convert time constant (in milliseconds) to one-pole filter coefficient.
    
    Formula: coeff = exp(-1 / (time_seconds * sample_rate))
    """
    if time_ms <= 0:
        return 0.0  # Instant response
    time_seconds = time_ms / 1000.0
    return np.exp(-1.0 / (time_seconds * sample_rate))


def envelope_follower(
    signal: np.ndarray,
    attack_ms: float,
    release_ms: float,
    sample_rate: int
) -> np.ndarray:
    """
    Track signal envelope with asymmetric attack/release ballistics.
    
    Args:
        signal: Input audio (mono)
        attack_ms: Attack time constant in milliseconds
        release_ms: Release time constant in milliseconds
        sample_rate: Audio sample rate
    
    Returns:
        Envelope signal (same length as input)
    """
    attack_coeff = compute_envelope_coeff(attack_ms, sample_rate)
    release_coeff = compute_envelope_coeff(release_ms, sample_rate)
    
    rectified = np.abs(signal)
    envelope = np.zeros_like(rectified)
    state = 0.0
    
    for i in range(len(rectified)):
        if rectified[i] > state:
            coeff = attack_coeff
        else:
            coeff = release_coeff
        
        state = coeff * state + (1 - coeff) * rectified[i]
        envelope[i] = state
    
    return envelope
```

### 1.2 Differential Envelope (Transient Detection)

The key innovation in transient shaping is using **two envelope followers** with different time constants:

- **Fast envelope**: Responds quickly to amplitude changes (attack: 0.1-1ms)
- **Slow envelope**: Follows the overall level more gradually (attack: 10-50ms)

The **difference** between these envelopes reveals transient activity:

$$
\text{Transient}(n) = \text{EnvFast}(n) - \text{EnvSlow}(n)
$$

When transients occur:
- Fast envelope rises quickly → large value
- Slow envelope hasn't caught up yet → smaller value
- Difference is **positive and significant**

During sustain:
- Both envelopes track similarly
- Difference approaches **zero**

#### Differential Detection Pseudocode

```
FUNCTION detect_transients(input, sample_rate):
    # Time constants (critical for sound quality)
    FAST_ATTACK_MS = 0.5    # Very fast - catches transient onset
    FAST_RELEASE_MS = 5.0   # Moderate release
    SLOW_ATTACK_MS = 20.0   # Slow - misses transient, tracks body
    SLOW_RELEASE_MS = 100.0 # Slow release
    
    fast_env = envelope_follower(input, FAST_ATTACK_MS, FAST_RELEASE_MS, sample_rate)
    slow_env = envelope_follower(input, SLOW_ATTACK_MS, SLOW_RELEASE_MS, sample_rate)
    
    # Transient = fast minus slow, only positive values
    transient = MAX(fast_env - slow_env, 0)
    
    # Sustain = slow envelope
    sustain = slow_env
    
    RETURN transient, sustain
```

### 1.3 Zero-Crossing Detection for Precise Timing

For sample-accurate transient timing, zero-crossing detection helps identify the exact moment a transient begins:

```python
def find_transient_onsets(
    transient_signal: np.ndarray,
    threshold: float = 0.1,
    min_spacing_samples: int = 441  # ~10ms at 44.1kHz
) -> np.ndarray:
    """
    Find transient onset positions using threshold crossing.
    
    Args:
        transient_signal: Output from differential envelope
        threshold: Detection threshold (0-1 normalized)
        min_spacing_samples: Minimum samples between detected transients
    
    Returns:
        Array of sample indices where transients begin
    """
    # Normalize
    normalized = transient_signal / (np.max(transient_signal) + 1e-10)
    
    # Find threshold crossings (rising edge)
    above_threshold = normalized > threshold
    crossings = np.where(np.diff(above_threshold.astype(int)) > 0)[0]
    
    # Enforce minimum spacing
    if len(crossings) == 0:
        return np.array([])
    
    filtered = [crossings[0]]
    for onset in crossings[1:]:
        if onset - filtered[-1] >= min_spacing_samples:
            filtered.append(onset)
    
    return np.array(filtered)
```

### 1.4 Lookahead Buffering

Transients begin *before* the envelope follower can react. Professional implementations use **lookahead** to catch the initial attack:

```
LOOKAHEAD_MS = 5.0  # Typical range: 1-10ms

FUNCTION process_with_lookahead(input, gain_curve, lookahead_samples):
    # Delay the audio, but not the gain curve
    delayed_audio = delay(input, lookahead_samples)
    
    # Apply gain curve (which now leads the audio)
    output = delayed_audio * gain_curve
    
    RETURN output
```

**Implementation Note:** Lookahead introduces latency. For real-time applications, this must be compensated for in the host DAW's plugin delay compensation (PDC) system.

---

## 2. Attack Enhancement Techniques

### 2.1 Basic Attack Boost

```python
def apply_attack_boost(
    audio: np.ndarray,
    transient_signal: np.ndarray,
    boost_amount: float,  # 0 to 1 (0 = no change, 1 = +6dB)
    max_gain_db: float = 12.0
) -> np.ndarray:
    """
    Boost transient portions of the audio.
    
    Args:
        audio: Input audio
        transient_signal: Detected transient envelope
        boost_amount: Boost intensity (0-1)
        max_gain_db: Maximum gain to apply
    
    Returns:
        Processed audio with enhanced transients
    """
    # Normalize transient signal
    trans_norm = transient_signal / (np.max(transient_signal) + 1e-10)
    
    # Convert boost amount to gain multiplier
    # boost_amount 0 -> gain 1.0 (0 dB)
    # boost_amount 1 -> gain ~2.0 (+6 dB)
    max_gain_linear = 10 ** (max_gain_db / 20)
    
    # Gain follows transient contour
    gain = 1.0 + trans_norm * boost_amount * (max_gain_linear - 1)
    
    return audio * gain
```

### 2.2 Clip-Safe Attack Boosting (Soft Clipping Integration)

Aggressive attack boosting can cause clipping. Integrate soft clipping for safety:

$$
\text{SoftClip}(x) = \frac{2}{\pi} \arctan\left(\frac{\pi x}{2}\right)
$$

Or using tanh (faster):

$$
\text{SoftClip}(x) = \tanh(x)
$$

```python
def soft_clip_tanh(signal: np.ndarray, threshold: float = 0.9) -> np.ndarray:
    """
    Apply soft clipping using tanh function.
    
    Preserves dynamics below threshold, gently limits above.
    """
    # Scale signal so threshold maps to ~0.76 (tanh(1))
    scale = 1.0 / threshold
    scaled = signal * scale
    
    # Apply tanh
    clipped = np.tanh(scaled)
    
    # Scale back
    return clipped / scale


def attack_boost_clip_safe(
    audio: np.ndarray,
    transient_signal: np.ndarray,
    boost_amount: float,
    soft_clip_threshold: float = 0.95
) -> np.ndarray:
    """
    Boost attack with integrated soft clipping.
    """
    # Apply boost
    boosted = apply_attack_boost(audio, transient_signal, boost_amount)
    
    # Soft clip to prevent harsh digital clipping
    return soft_clip_tanh(boosted, soft_clip_threshold)
```

### 2.3 Frequency-Dependent Attack Shaping

Boost attack only in specific frequency bands (e.g., 2-8kHz for "snap"):

```
FUNCTION multiband_attack_shape(audio, transient_signal, bands, boosts):
    # Split into bands using Linkwitz-Riley crossovers
    low = lowpass(audio, bands[0])
    mid = bandpass(audio, bands[0], bands[1])
    high = highpass(audio, bands[1])
    
    # Apply different boost amounts per band
    low_processed = apply_attack_boost(low, transient_signal, boosts.low)
    mid_processed = apply_attack_boost(mid, transient_signal, boosts.mid)
    high_processed = apply_attack_boost(high, transient_signal, boosts.high)
    
    # Sum bands
    RETURN low_processed + mid_processed + high_processed
```

**Typical frequency ranges for drum attack:**

| Component | Frequency Range | Attack Boost Effect |
|-----------|-----------------|---------------------|
| Sub       | 20-80 Hz        | Adds "weight" to kick |
| Low-mid   | 80-300 Hz       | Body, punch |
| Mid       | 300 Hz - 2 kHz  | Presence, smack |
| High-mid  | 2-8 kHz         | Snap, crack, definition |
| High      | 8-20 kHz        | Air, sizzle |

---

## 3. Sustain Control Methods

### 3.1 Sustain Enhancement (Boost)

To boost sustain, we apply gain inversely proportional to transient activity:

```python
def apply_sustain_boost(
    audio: np.ndarray,
    sustain_signal: np.ndarray,
    transient_signal: np.ndarray,
    boost_amount: float  # 0 to 1
) -> np.ndarray:
    """
    Boost sustain/body portions while preserving transients.
    """
    # During transients, reduce boost
    # During sustain (low transient activity), increase boost
    
    trans_norm = transient_signal / (np.max(transient_signal) + 1e-10)
    sust_norm = sustain_signal / (np.max(sustain_signal) + 1e-10)
    
    # Sustain boost is active when transient is low
    sustain_activity = sust_norm * (1 - trans_norm)
    
    # Apply boost
    max_gain_db = 6.0  # Max +6dB sustain boost
    max_gain = 10 ** (max_gain_db / 20)
    gain = 1.0 + sustain_activity * boost_amount * (max_gain - 1)
    
    return audio * gain
```

### 3.2 Sustain Reduction (Ducking)

Reduce sustain for tighter, punchier sounds:

```python
def apply_sustain_reduction(
    audio: np.ndarray,
    sustain_signal: np.ndarray,
    transient_signal: np.ndarray,
    reduction_amount: float  # 0 to 1
) -> np.ndarray:
    """
    Reduce sustain while preserving transient impact.
    """
    trans_norm = transient_signal / (np.max(transient_signal) + 1e-10)
    
    # During sustain (transient is low), reduce gain
    # During transient, maintain full gain
    
    # Exponential reduction for more natural sound
    min_gain_db = -12.0  # Maximum reduction
    min_gain = 10 ** (min_gain_db / 20)
    
    # Gain is high during transient, reduced during sustain
    gain = 1.0 - (1 - trans_norm) * reduction_amount * (1 - min_gain)
    gain = np.maximum(gain, min_gain)  # Floor at min_gain
    
    return audio * gain
```

### 3.3 Expansion-Based Sustain Control

For more aggressive control, use expansion rather than simple gain:

$$
\text{Expansion Ratio: } R = 2:1 \text{ to } 4:1
$$

When signal drops below threshold, attenuate by the expansion ratio:

```
FUNCTION expand_sustain(audio, envelope, threshold_db, ratio):
    envelope_db = 20 * LOG10(envelope + 1e-10)
    
    FOR each sample:
        IF envelope_db[i] < threshold_db:
            # Below threshold: expand (attenuate)
            below_threshold = threshold_db - envelope_db[i]
            gain_reduction_db = below_threshold * (ratio - 1)
            gain[i] = 10^(-gain_reduction_db / 20)
        ELSE:
            gain[i] = 1.0
    
    RETURN audio * gain
```

---

## 4. Professional Implementation Analysis

### 4.1 SPL Transient Designer Principles

The SPL Transient Designer (hardware) pioneered the differential envelope approach:

**Key characteristics:**
- Two controls: Attack (-15dB to +15dB), Sustain (-24dB to +24dB)
- No threshold control (level-independent operation)
- **Differential detector**: Attack derived from fast/slow envelope difference
- **Duration parameter** (internal): Controls how long the "attack phase" lasts
- VCA-based gain control for analog implementations

**Conceptual signal flow:**

```
Input → Rectifier → [Fast Envelope] ─┬─ Difference → Attack Gain ─┐
                                     │                             │
                    [Slow Envelope] ─┴─ Direct → Sustain Gain ────┤
                                                                   │
Input ────────────────────────────────────────────────────────────→ VCA → Output
```

### 4.2 Sonnox TransMod Approach

Oxford TransMod adds sophistication:

- **Rise/Fall separate controls** for attack and sustain
- **Soft/Aggressive modes** affecting detection sensitivity
- **Oversampling** for cleaner transient reproduction
- **Lookahead** to catch initial waveform

### 4.3 Native Instruments Transient Master

Simplified interface with musical results:

- Attack: -100% to +100%
- Sustain: -100% to +100%
- Mode switch: Smooth (gentle) / Punch (aggressive)
- Internal auto-limiting to prevent clipping

---

## 5. Use Cases & Recipes

### 5.1 Drum Punch (Tight, Punchy Kick/Snare)

**Goal:** Enhance attack, reduce sustain for a punchy, controlled sound.

```python
TransientShaperParams(
    attack_amount=60,    # +60% attack boost
    sustain_amount=-40,  # -40% sustain reduction
    detection_mode='peak',
    fast_attack_ms=0.5,
    slow_attack_ms=20.0
)
```

### 5.2 Sustain Enhancement (Ambient, Smooth Pads)

**Goal:** Reduce attack harshness, boost sustain for ambient textures.

```python
TransientShaperParams(
    attack_amount=-30,   # -30% attack reduction (softer)
    sustain_amount=50,   # +50% sustain boost (fuller)
    detection_mode='rms',
    fast_attack_ms=1.0,
    slow_attack_ms=50.0
)
```

### 5.3 Snare Crack

**Goal:** Aggressive attack boost with frequency shaping (2-8kHz emphasis).

```python
TransientShaperParams(
    attack_amount=80,
    sustain_amount=-20,
    multiband=True,
    band_attacks={
        'low': 20,       # Subtle low boost
        'mid': 40,       # Moderate mid
        'high': 80       # Aggressive high-mid for crack
    }
)
```

### 5.4 808 Tightening

**Goal:** Reduce sustain to prevent low-end muddiness, preserve initial punch.

```python
TransientShaperParams(
    attack_amount=30,    # Slight attack enhancement
    sustain_amount=-60,  # Significant sustain reduction
    detection_mode='peak',
    slow_attack_ms=100.0  # Longer to catch 808 decay
)
```

### 5.5 Room Mic Squash (Parallel Processing)

**Goal:** Maximize sustain for parallel drum compression.

```python
TransientShaperParams(
    attack_amount=-80,   # Heavily reduce attack
    sustain_amount=100,  # Maximum sustain
    output_mix=0.5       # Blend 50% with dry
)
```

---

## 6. Data Structures & Schemas

### 6.1 TransientShaperParams Dataclass

```python
from dataclasses import dataclass, field
from typing import Optional, Dict
from enum import Enum


class DetectionMode(Enum):
    """Envelope detection mode."""
    PEAK = "peak"      # Fast, punchy response
    RMS = "rms"        # Smoother, average-based


class ClipMode(Enum):
    """Output clipping mode."""
    NONE = "none"           # No clipping (allow overs)
    SOFT = "soft"           # Soft clip (tanh)
    HARD = "hard"           # Hard clip at 0dBFS
    LIMITER = "limiter"     # Brickwall limiter


@dataclass
class TransientShaperParams:
    """
    Configuration parameters for transient shaping processor.
    
    All percentage values range from -100 to +100:
    - Negative values reduce the component
    - Positive values boost the component
    - Zero means no change
    """
    
    # === Primary Controls ===
    attack_amount: float = 0.0
    """Attack enhancement: -100 (soften) to +100 (punch). Default: 0 (bypass)."""
    
    sustain_amount: float = 0.0
    """Sustain enhancement: -100 (tighten) to +100 (lengthen). Default: 0 (bypass)."""
    
    # === Detection Parameters ===
    detection_mode: DetectionMode = DetectionMode.PEAK
    """Envelope detection algorithm."""
    
    fast_attack_ms: float = 0.5
    """Fast envelope attack time (ms). Range: 0.1 - 5.0. Affects transient sensitivity."""
    
    fast_release_ms: float = 5.0
    """Fast envelope release time (ms). Range: 1.0 - 50.0."""
    
    slow_attack_ms: float = 20.0
    """Slow envelope attack time (ms). Range: 5.0 - 100.0. Affects sustain detection."""
    
    slow_release_ms: float = 100.0
    """Slow envelope release time (ms). Range: 20.0 - 500.0."""
    
    # === Lookahead ===
    lookahead_ms: float = 5.0
    """Lookahead time (ms). Range: 0 - 20. Higher = catch more attack, more latency."""
    
    # === Output ===
    clip_mode: ClipMode = ClipMode.SOFT
    """Output clipping mode to prevent digital overs."""
    
    output_gain_db: float = 0.0
    """Output gain adjustment (dB). Range: -12 to +12."""
    
    output_mix: float = 1.0
    """Dry/wet mix. 0.0 = fully dry, 1.0 = fully wet. Range: 0.0 - 1.0."""
    
    # === Multiband (Optional) ===
    multiband_enabled: bool = False
    """Enable frequency-dependent processing."""
    
    crossover_low_hz: float = 200.0
    """Low/mid crossover frequency (Hz)."""
    
    crossover_high_hz: float = 4000.0
    """Mid/high crossover frequency (Hz)."""
    
    band_attack_amounts: Dict[str, float] = field(default_factory=lambda: {
        'low': 0.0,
        'mid': 0.0,
        'high': 0.0
    })
    """Per-band attack amounts when multiband is enabled."""
    
    band_sustain_amounts: Dict[str, float] = field(default_factory=lambda: {
        'low': 0.0,
        'mid': 0.0,
        'high': 0.0
    })
    """Per-band sustain amounts when multiband is enabled."""
    
    def __post_init__(self):
        """Validate parameter ranges."""
        self._clamp_param('attack_amount', -100, 100)
        self._clamp_param('sustain_amount', -100, 100)
        self._clamp_param('fast_attack_ms', 0.1, 5.0)
        self._clamp_param('fast_release_ms', 1.0, 50.0)
        self._clamp_param('slow_attack_ms', 5.0, 100.0)
        self._clamp_param('slow_release_ms', 20.0, 500.0)
        self._clamp_param('lookahead_ms', 0, 20.0)
        self._clamp_param('output_gain_db', -12, 12)
        self._clamp_param('output_mix', 0.0, 1.0)
        self._clamp_param('crossover_low_hz', 50, 500)
        self._clamp_param('crossover_high_hz', 1000, 10000)
    
    def _clamp_param(self, name: str, min_val: float, max_val: float):
        """Clamp parameter to valid range."""
        value = getattr(self, name)
        clamped = max(min_val, min(max_val, value))
        setattr(self, name, clamped)
    
    @property
    def attack_gain_factor(self) -> float:
        """Convert attack_amount to linear gain multiplier."""
        # -100 -> 0.25 (-12dB), 0 -> 1.0, +100 -> 4.0 (+12dB)
        db = self.attack_amount * 0.12  # ±12dB range
        return 10 ** (db / 20)
    
    @property
    def sustain_gain_factor(self) -> float:
        """Convert sustain_amount to linear gain multiplier."""
        db = self.sustain_amount * 0.12
        return 10 ** (db / 20)
    
    @property
    def is_bypass(self) -> bool:
        """Check if processing would be a no-op."""
        return (
            abs(self.attack_amount) < 0.1 and 
            abs(self.sustain_amount) < 0.1 and
            not self.multiband_enabled
        )
```

### 6.2 Parameter Ranges Summary

| Parameter | Min | Max | Default | Unit |
|-----------|-----|-----|---------|------|
| `attack_amount` | -100 | +100 | 0 | % |
| `sustain_amount` | -100 | +100 | 0 | % |
| `fast_attack_ms` | 0.1 | 5.0 | 0.5 | ms |
| `fast_release_ms` | 1.0 | 50.0 | 5.0 | ms |
| `slow_attack_ms` | 5.0 | 100.0 | 20.0 | ms |
| `slow_release_ms` | 20.0 | 500.0 | 100.0 | ms |
| `lookahead_ms` | 0 | 20.0 | 5.0 | ms |
| `output_gain_db` | -12 | +12 | 0 | dB |
| `output_mix` | 0.0 | 1.0 | 1.0 | ratio |
| `crossover_low_hz` | 50 | 500 | 200 | Hz |
| `crossover_high_hz` | 1000 | 10000 | 4000 | Hz |

---

## 7. Artifact Avoidance

### 7.1 Clicks and Pops

**Cause:** Discontinuous gain changes, especially at transient boundaries.

**Solutions:**
1. **Smoothing the gain curve** with a short lowpass filter (1-5ms)
2. **Minimum gain floor** (don't reduce below -12dB)
3. **Rate limiting** on gain changes

```python
def smooth_gain_curve(gain: np.ndarray, smooth_ms: float, sample_rate: int) -> np.ndarray:
    """Smooth gain curve to prevent clicks."""
    coeff = compute_envelope_coeff(smooth_ms, sample_rate)
    smoothed = np.zeros_like(gain)
    state = gain[0]
    
    for i in range(len(gain)):
        state = coeff * state + (1 - coeff) * gain[i]
        smoothed[i] = state
    
    return smoothed
```

### 7.2 Pumping

**Cause:** Overly aggressive sustain reduction creating unnatural "breathing" effect.

**Solutions:**
1. **Longer release times** on sustain reduction
2. **Program-dependent release** that adapts to material
3. **Blend with dry signal** (output_mix < 1.0)

### 7.3 Timing Smear

**Cause:** Fast envelope not responding quickly enough, blurring transient definition.

**Solutions:**
1. **Shorter fast_attack_ms** (0.1-0.5ms)
2. **Lookahead** to compensate for detection lag
3. **Peak detection** instead of RMS

### 7.4 Aliasing on Attack Boost

**Cause:** Boosting transients creates high-frequency harmonics that exceed Nyquist.

**Solutions:**
1. **Oversampling** (2x or 4x) before attack boost
2. **Soft clipping** to limit harmonic generation
3. **Lowpass filter** before final output

### 7.5 DC Offset

**Cause:** Asymmetric gain application can introduce DC component.

**Solutions:**
1. **DC blocker** on output (highpass at ~5Hz)
2. **Symmetric gain application** (avoid negative gain)

```python
def dc_block(signal: np.ndarray, cutoff_hz: float = 5.0, sample_rate: int = 44100) -> np.ndarray:
    """Simple DC blocking filter (one-pole highpass)."""
    coeff = np.exp(-2 * np.pi * cutoff_hz / sample_rate)
    output = np.zeros_like(signal)
    prev_in = 0.0
    prev_out = 0.0
    
    for i in range(len(signal)):
        output[i] = signal[i] - prev_in + coeff * prev_out
        prev_in = signal[i]
        prev_out = output[i]
    
    return output
```

---

## 8. References

### Academic & Technical

1. Giannoulis, D., Massberg, M., & Zölzer, U. (2012). "Digital Dynamic Range Compressor Design—A Tutorial and Analysis." *Journal of the Audio Engineering Society*, 60(6), 399-408.

2. Zölzer, U. (2011). *DAFX: Digital Audio Effects* (2nd ed.). Wiley.

3. Pirkle, W. C. (2019). *Designing Audio Effect Plugins in C++* (2nd ed.). Routledge.

### Online Resources

4. Earlevel Engineering - One-pole filter: https://www.earlevel.com/main/2012/12/15/a-one-pole-filter/

5. Cytomic Technical Papers - Dynamic Smoothing: https://cytomic.com/files/dsp/DynamicSmoothing.pdf

### Commercial Reference Implementations

6. SPL Transient Designer (hardware/plugin)
7. Sonnox Oxford TransMod
8. Native Instruments Transient Master
9. FabFilter Pro-MB (multiband dynamics)
10. Waves Smack Attack

---

## Appendix A: Complete Processing Chain Pseudocode

```
FUNCTION process_transient_shaper(audio, params):
    # 0. Bypass check
    IF params.is_bypass:
        RETURN audio
    
    # 1. Create detection sidechain (mono sum)
    IF audio.channels > 1:
        sidechain = MEAN(ABS(audio), axis=channels)
    ELSE:
        sidechain = ABS(audio)
    
    # 2. Compute dual envelopes
    fast_env = envelope_follower(
        sidechain, 
        params.fast_attack_ms, 
        params.fast_release_ms
    )
    slow_env = envelope_follower(
        sidechain,
        params.slow_attack_ms,
        params.slow_release_ms
    )
    
    # 3. Derive transient and sustain signals
    transient = MAX(fast_env - slow_env, 0)
    sustain = slow_env
    
    # 4. Normalize for gain calculation
    trans_norm = transient / (MAX(transient) + 1e-10)
    sust_norm = sustain / (MAX(sustain) + 1e-10)
    
    # 5. Calculate gain curve
    attack_gain = 1.0 + trans_norm * (params.attack_gain_factor - 1)
    sustain_gain = 1.0 + (1 - trans_norm) * sust_norm * (params.sustain_gain_factor - 1)
    combined_gain = attack_gain * sustain_gain
    
    # 6. Smooth gain to prevent clicks
    smoothed_gain = smooth_gain_curve(combined_gain, 1.0, sample_rate)
    
    # 7. Apply lookahead (delay audio, not gain)
    IF params.lookahead_ms > 0:
        lookahead_samples = INT(params.lookahead_ms * sample_rate / 1000)
        audio = delay(audio, lookahead_samples)
    
    # 8. Apply gain
    processed = audio * smoothed_gain
    
    # 9. Soft clip if enabled
    IF params.clip_mode == SOFT:
        processed = soft_clip_tanh(processed, 0.95)
    
    # 10. DC block
    processed = dc_block(processed)
    
    # 11. Output gain
    processed = processed * (10 ^ (params.output_gain_db / 20))
    
    # 12. Dry/wet mix
    output = params.output_mix * processed + (1 - params.output_mix) * audio
    
    RETURN output
```

---

*End of Research Report*
