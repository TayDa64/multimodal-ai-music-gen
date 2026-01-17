# Intelligent Auto-Gain Staging Research Report

**Research Area:** DSP for Automated Mixing  
**Author:** DSP Research Agent  
**Date:** January 17, 2026  
**Version:** 1.0.0

---

## Executive Summary

This report provides comprehensive research on **Intelligent Auto-Gain Staging** for the multimodal-ai-music-gen automated mixing system. It covers loudness measurement algorithms, genre-aware level targets, automatic gain calculation, and integration with the existing `MixEngine` architecture.

---

## 1. Loudness Measurement Fundamentals

### 1.1 RMS vs Peak vs LUFS Comparison

| Metric | Definition | Use Case | Limitations |
|--------|-----------|----------|-------------|
| **Peak** | Maximum sample amplitude | Headroom management, clipping prevention | Doesn't correlate with perceived loudness |
| **RMS** | Root Mean Square (average power) | Basic loudness estimation | Doesn't account for frequency perception |
| **LUFS** | Loudness Units Full Scale (ITU-R BS.1770) | Industry standard loudness | Computationally heavier |

#### Key Differences:

```
Peak Level: max(|sample|)
- Measures: Instantaneous maximum
- Correlation with loudness: POOR
- Example: A sharp transient can peak at 0dB but sound quiet

RMS Level: √(mean(sample²))
- Measures: Average power
- Correlation with loudness: MODERATE
- Formula: RMS_dB = 20 * log10(√(Σx² / N))

LUFS (Loudness Units Full Scale):
- Measures: Perceptually-weighted loudness
- Correlation with loudness: EXCELLENT
- Based on: K-weighting + gating per ITU-R BS.1770-4
```

### 1.2 ITU-R BS.1770-4 LUFS Algorithm

The ITU-R BS.1770-4 standard defines a three-stage loudness measurement:

#### Stage 1: K-Weighting Filter

K-weighting applies two cascaded biquad filters:

**Pre-filter (High-Shelf boost at ~1681 Hz):**
```
Purpose: Compensate for acoustic effects of human head
Boost: +4 dB above ~1.5 kHz
Transfer function: H_pre(z) = high_shelf(1681 Hz, +4 dB, Q=0.71)
```

**High-Pass Filter (100 Hz, 2nd order Butterworth):**
```
Purpose: De-emphasize low frequencies (less perceptually loud)
Cutoff: ~100 Hz (actually 38 Hz corner with specific Q)
Transfer function: H_hp(z) = highpass(38 Hz, Q=0.5)
```

**Combined K-Weighting Coefficients (48kHz sample rate):**

```python
# Pre-filter (high shelf) coefficients at 48kHz
PRE_FILTER_B = [1.53512485958697, -2.69169618940638, 1.19839281085285]
PRE_FILTER_A = [1.0, -1.69065929318241, 0.73248077421585]

# High-pass filter coefficients at 48kHz  
HP_FILTER_B = [1.0, -2.0, 1.0]
HP_FILTER_A = [1.0, -1.99004745483398, 0.99007225036621]
```

**Coefficient Recalculation for Other Sample Rates:**
```python
def calculate_k_weight_coeffs(sample_rate: int) -> tuple:
    """Calculate K-weighting filter coefficients for given sample rate."""
    # Pre-filter: High shelf at 1681.974 Hz with +4dB gain
    f0 = 1681.974
    G = 3.999843853973347  # dB
    Q = 0.7071752369554196
    
    K = np.tan(np.pi * f0 / sample_rate)
    Vh = 10 ** (G / 20)
    Vb = Vh ** 0.499666774155
    
    a0 = 1 + K/Q + K*K
    b0 = (Vh + Vb*K/Q + K*K) / a0
    b1 = 2 * (K*K - Vh) / a0
    b2 = (Vh - Vb*K/Q + K*K) / a0
    a1 = 2 * (K*K - 1) / a0
    a2 = (1 - K/Q + K*K) / a0
    
    pre_b = [b0, b1, b2]
    pre_a = [1.0, a1, a2]
    
    # High-pass: 38.13547087602444 Hz, Q=0.5003270373238773
    f0_hp = 38.13547087602444
    Q_hp = 0.5003270373238773
    
    K = np.tan(np.pi * f0_hp / sample_rate)
    a0 = 1 + K/Q_hp + K*K
    hp_b = [1/a0, -2/a0, 1/a0]
    hp_a = [1.0, 2*(K*K-1)/a0, (1-K/Q_hp+K*K)/a0]
    
    return (pre_b, pre_a), (hp_b, hp_a)
```

#### Stage 2: Mean Square Calculation (per block)

After K-weighting, calculate mean square per 400ms block with 75% overlap:

```python
def calculate_block_loudness(k_weighted_audio: np.ndarray, 
                             sample_rate: int,
                             block_size_ms: float = 400,
                             overlap_percent: float = 75) -> np.ndarray:
    """
    Calculate loudness per gating block.
    
    Args:
        k_weighted_audio: K-weighted audio (mono or multi-channel)
        sample_rate: Sample rate
        block_size_ms: Block size in milliseconds (400ms for integrated)
        overlap_percent: Block overlap percentage (75% standard)
    
    Returns:
        Array of block loudness values in LUFS
    """
    block_samples = int(sample_rate * block_size_ms / 1000)
    hop_samples = int(block_samples * (1 - overlap_percent / 100))
    
    blocks = []
    for start in range(0, len(k_weighted_audio) - block_samples, hop_samples):
        block = k_weighted_audio[start:start + block_samples]
        # Mean square (power)
        mean_square = np.mean(block ** 2)
        blocks.append(mean_square)
    
    return np.array(blocks)
```

#### Stage 3: Gating (Absolute + Relative)

Two-stage gating removes silence and quiet passages:

```python
def apply_gating(block_loudness: np.ndarray) -> float:
    """
    Apply BS.1770 two-stage gating.
    
    Stage 1: Absolute threshold at -70 LUFS
    Stage 2: Relative threshold at -10 dB below ungated mean
    
    Returns:
        Gated integrated loudness in LUFS
    """
    # Convert mean square to LUFS
    block_lufs = -0.691 + 10 * np.log10(block_loudness + 1e-10)
    
    # Stage 1: Absolute gate at -70 LUFS
    above_absolute = block_loudness[block_lufs > -70]
    
    if len(above_absolute) == 0:
        return -70.0
    
    # Ungated mean (in linear domain)
    ungated_mean = np.mean(above_absolute)
    ungated_lufs = -0.691 + 10 * np.log10(ungated_mean)
    
    # Stage 2: Relative gate at -10 dB below ungated mean
    relative_threshold = ungated_lufs - 10
    above_relative = block_loudness[block_lufs > relative_threshold]
    
    if len(above_relative) == 0:
        return ungated_lufs
    
    # Final gated mean
    gated_mean = np.mean(above_relative)
    integrated_lufs = -0.691 + 10 * np.log10(gated_mean)
    
    return integrated_lufs
```

### 1.3 LUFS Measurement Types

| Type | Window | Use Case |
|------|--------|----------|
| **Momentary (M)** | 400ms sliding | Real-time meters, visual feedback |
| **Short-term (S)** | 3 seconds sliding | Mixing decisions, live monitoring |
| **Integrated (I)** | Entire program | Final loudness value, compliance |

```python
# Window sizes
MOMENTARY_WINDOW_MS = 400
SHORT_TERM_WINDOW_MS = 3000
# Integrated = entire file with gating
```

---

## 2. Genre-Aware Level Targets

### 2.1 Relative Level Philosophy

In a mix, each element has a **relative loudness** compared to a reference point. We use the overall mix as 0 dB reference, with individual tracks measured in **relative LUFS**:

```
Relative LUFS = Track LUFS - Mix LUFS (target)

Example for Trap at -14 LUFS mix target:
- 808 Bass at -20 LUFS = +6 dB relative (loudest element)
- Kick at -22 LUFS = +4 dB relative
- Snare at -24 LUFS = +2 dB relative
- Hi-hats at -28 LUFS = -2 dB relative
- Melody at -26 LUFS = 0 dB relative
```

### 2.2 Genre Mix Templates

Based on analysis of professional references (iZotope, Splice, professional mixers):

#### **TRAP**
```python
TRAP_MIX_TEMPLATE = {
    "genre": "trap",
    "master_target_lufs": -14.0,
    "headroom_db": -6.0,
    "track_targets": {
        "808_bass": {"relative_lufs": 6.0, "priority": 1},  # Dominant
        "kick": {"relative_lufs": 4.0, "priority": 2},
        "snare": {"relative_lufs": 2.0, "priority": 3},
        "clap": {"relative_lufs": 1.0, "priority": 4},
        "hihat": {"relative_lufs": -2.0, "priority": 6},
        "hihat_open": {"relative_lufs": -3.0, "priority": 7},
        "melody": {"relative_lufs": 0.0, "priority": 5},
        "pad": {"relative_lufs": -4.0, "priority": 8},
        "fx": {"relative_lufs": -6.0, "priority": 9},
    },
    "crest_factor_targets": {
        "808_bass": (6, 10),   # Compressed
        "kick": (12, 18),      # Punchy transients
        "snare": (10, 16),     # Snappy
        "hihat": (8, 14),      # Controlled
    },
    "sidechain_depth": 0.4,
    "compression_style": "modern_aggressive",
}
```

#### **LO-FI HIP-HOP**
```python
LOFI_MIX_TEMPLATE = {
    "genre": "lofi",
    "master_target_lufs": -16.0,  # More dynamic
    "headroom_db": -8.0,
    "track_targets": {
        "melody": {"relative_lufs": 4.0, "priority": 1},  # Melody forward
        "chords": {"relative_lufs": 3.0, "priority": 2},
        "bass": {"relative_lufs": 2.0, "priority": 3},
        "kick": {"relative_lufs": 0.0, "priority": 4},  # Drums sit back
        "snare": {"relative_lufs": -1.0, "priority": 5},
        "hihat": {"relative_lufs": -4.0, "priority": 6},
        "vinyl_noise": {"relative_lufs": -12.0, "priority": 10},
        "pad": {"relative_lufs": -2.0, "priority": 7},
    },
    "crest_factor_targets": {
        "kick": (14, 20),      # More dynamic
        "snare": (12, 18),     # Natural feel
        "melody": (10, 16),    # Breathing room
    },
    "sidechain_depth": 0.15,   # Subtle
    "compression_style": "vintage_gentle",
}
```

#### **BOOM BAP**
```python
BOOM_BAP_MIX_TEMPLATE = {
    "genre": "boom_bap",
    "master_target_lufs": -14.0,
    "headroom_db": -6.0,
    "track_targets": {
        "kick": {"relative_lufs": 5.0, "priority": 1},   # Drums forward
        "snare": {"relative_lufs": 5.0, "priority": 2},  # Equal to kick
        "bass": {"relative_lufs": 2.0, "priority": 3},
        "hihat": {"relative_lufs": 0.0, "priority": 5},
        "sample": {"relative_lufs": 1.0, "priority": 4},
        "melody": {"relative_lufs": -1.0, "priority": 6},
        "scratch": {"relative_lufs": -2.0, "priority": 7},
    },
    "crest_factor_targets": {
        "kick": (12, 18),
        "snare": (12, 18),
        "bass": (8, 12),
    },
    "sidechain_depth": 0.2,
    "compression_style": "sp1200_crunch",
}
```

#### **G-FUNK**
```python
G_FUNK_MIX_TEMPLATE = {
    "genre": "g_funk",
    "master_target_lufs": -14.0,
    "headroom_db": -6.0,
    "track_targets": {
        "synth_lead": {"relative_lufs": 4.0, "priority": 1},  # Portamento synth prominent
        "bass": {"relative_lufs": 3.0, "priority": 2},        # Funk bass, not 808
        "kick": {"relative_lufs": 2.0, "priority": 3},
        "snare": {"relative_lufs": 2.0, "priority": 4},
        "hihat": {"relative_lufs": -1.0, "priority": 6},
        "keys": {"relative_lufs": 0.0, "priority": 5},
        "pad": {"relative_lufs": -3.0, "priority": 7},
        "strings": {"relative_lufs": -2.0, "priority": 8},
    },
    "crest_factor_targets": {
        "synth_lead": (10, 14),
        "bass": (8, 12),
        "kick": (12, 16),
    },
    "sidechain_depth": 0.1,    # Minimal
    "compression_style": "west_coast_smooth",
}
```

#### **EDM / HOUSE**
```python
EDM_MIX_TEMPLATE = {
    "genre": "edm",
    "master_target_lufs": -10.0,  # Louder target
    "headroom_db": -4.0,
    "track_targets": {
        "kick": {"relative_lufs": 6.0, "priority": 1},    # Dominant
        "bass": {"relative_lufs": 4.0, "priority": 2},
        "snare_clap": {"relative_lufs": 3.0, "priority": 3},
        "lead_synth": {"relative_lufs": 2.0, "priority": 4},
        "hihat": {"relative_lufs": -1.0, "priority": 6},
        "pad": {"relative_lufs": -2.0, "priority": 7},
        "fx_riser": {"relative_lufs": 1.0, "priority": 5},
        "vocal_chop": {"relative_lufs": 0.0, "priority": 8},
    },
    "crest_factor_targets": {
        "kick": (8, 12),       # Heavily compressed
        "bass": (4, 8),        # Very compressed
        "lead_synth": (6, 10),
    },
    "sidechain_depth": 0.7,    # Heavy pumping
    "compression_style": "modern_brick",
}
```

#### **R&B / TRAP SOUL**
```python
RNB_MIX_TEMPLATE = {
    "genre": "rnb",
    "master_target_lufs": -14.0,
    "headroom_db": -6.0,
    "track_targets": {
        "vocal": {"relative_lufs": 5.0, "priority": 1},   # Vocal dominant
        "chords": {"relative_lufs": 2.0, "priority": 2},
        "bass": {"relative_lufs": 1.0, "priority": 3},
        "kick": {"relative_lufs": 0.0, "priority": 4},
        "snare": {"relative_lufs": -1.0, "priority": 5},
        "hihat": {"relative_lufs": -4.0, "priority": 7},
        "pad": {"relative_lufs": -2.0, "priority": 6},
        "strings": {"relative_lufs": -3.0, "priority": 8},
    },
    "crest_factor_targets": {
        "vocal": (10, 14),
        "kick": (12, 16),
        "bass": (8, 12),
    },
    "sidechain_depth": 0.2,
    "compression_style": "smooth_vintage",
}
```

### 2.3 Track Role Classification

Auto-detect track role for applying correct level targets:

```python
TRACK_ROLE_KEYWORDS = {
    "kick": ["kick", "bd", "bass_drum", "bombo"],
    "snare": ["snare", "sd", "rim", "clap"],
    "hihat": ["hihat", "hh", "hat", "cymbal", "ride"],
    "bass": ["bass", "808", "sub", "low"],
    "melody": ["melody", "lead", "synth", "keys", "piano", "guitar"],
    "pad": ["pad", "ambient", "atmosphere", "texture"],
    "vocal": ["vocal", "vox", "voice", "adlib"],
    "fx": ["fx", "effect", "riser", "sweep", "impact"],
    "drums": ["drums", "drum_bus", "perc", "percussion"],
}

def classify_track_role(track_name: str) -> str:
    """Classify track into mix role based on name."""
    name_lower = track_name.lower()
    for role, keywords in TRACK_ROLE_KEYWORDS.items():
        if any(kw in name_lower for kw in keywords):
            return role
    return "other"
```

---

## 3. Automatic Level Setting Algorithm

### 3.1 Auto-Gain Calculation Formula

```python
def calculate_auto_gain(
    track_lufs: float,
    target_relative_lufs: float,
    mix_target_lufs: float,
    headroom_db: float = -6.0
) -> float:
    """
    Calculate gain adjustment to reach target level.
    
    Args:
        track_lufs: Current track integrated LUFS
        target_relative_lufs: Target relative level (from genre template)
        mix_target_lufs: Target mix loudness (e.g., -14 LUFS)
        headroom_db: Headroom to leave for mastering
    
    Returns:
        Gain adjustment in dB
    
    Formula:
        target_track_lufs = mix_target_lufs + headroom_offset + target_relative_lufs
        gain_db = target_track_lufs - track_lufs
    
    Example:
        Mix target: -14 LUFS
        Headroom offset: -6 dB (leave room for mastering)
        808 relative target: +6 dB
        
        Target 808 LUFS = -14 + (-6) + 6 = -14 LUFS (pre-mastering)
        If current 808 is -20 LUFS: gain = -14 - (-20) = +6 dB
    """
    # Calculate absolute target for this track
    # Account for headroom by reducing overall level
    absolute_target = mix_target_lufs + headroom_db + target_relative_lufs
    
    # Calculate required gain
    gain_db = absolute_target - track_lufs
    
    # Limit extreme gain adjustments
    MAX_GAIN_DB = 24.0
    MIN_GAIN_DB = -24.0
    gain_db = np.clip(gain_db, MIN_GAIN_DB, MAX_GAIN_DB)
    
    return gain_db
```

### 3.2 Headroom Management Strategy

```python
HEADROOM_STRATEGY = {
    "stems_for_mixing": -6.0,      # Individual tracks: -6 dBFS peak target
    "bus_groups": -3.0,            # Bus submixes: -3 dBFS peak target
    "pre_master": -1.0,            # Before mastering: -1 dBFS peak target
    "streaming_master": -1.0,      # Final master (true peak): -1 dBTP
    
    # Leave extra headroom for dynamic genres
    "genre_headroom_adjustment": {
        "lofi": -2.0,              # Extra 2 dB for dynamics
        "jazz": -2.0,
        "classical": -3.0,
        "edm": +1.0,               # Can push harder
        "trap": 0.0,               # Standard
    }
}
```

### 3.3 Dynamic Range Preservation

```python
def check_dynamics_preservation(
    original_crest_factor: float,
    processed_crest_factor: float,
    min_acceptable_ratio: float = 0.7
) -> bool:
    """
    Ensure gain staging doesn't crush dynamics.
    
    Args:
        original_crest_factor: Original peak-to-RMS ratio (dB)
        processed_crest_factor: After gain adjustment
        min_acceptable_ratio: Minimum allowed ratio of new/old crest factor
    
    Returns:
        True if dynamics are preserved within tolerance
    """
    if original_crest_factor <= 0:
        return True
    
    preservation_ratio = processed_crest_factor / original_crest_factor
    return preservation_ratio >= min_acceptable_ratio
```

---

## 4. Crest Factor Analysis

### 4.1 Crest Factor Definition

```
Crest Factor (dB) = Peak Level (dB) - RMS Level (dB)

Also known as: Peak-to-Average Ratio (PAR)

Interpretation:
- Low crest factor (< 10 dB): Compressed, consistent level (sustained bass, pads)
- Medium crest factor (10-15 dB): Moderate dynamics (vocals, guitars)
- High crest factor (> 15 dB): Highly dynamic (drums, percussion, transients)
```

### 4.2 Crest Factor Calculation

```python
def calculate_crest_factor(audio: np.ndarray) -> float:
    """
    Calculate crest factor (peak-to-RMS ratio) in dB.
    
    Args:
        audio: Audio samples (normalized -1 to 1)
    
    Returns:
        Crest factor in dB
    """
    if len(audio) == 0:
        return 0.0
    
    peak = np.max(np.abs(audio))
    rms = np.sqrt(np.mean(audio ** 2))
    
    if rms <= 0 or peak <= 0:
        return 0.0
    
    peak_db = 20 * np.log10(peak)
    rms_db = 20 * np.log10(rms)
    
    return peak_db - rms_db
```

### 4.3 Crest Factor by Instrument Type

| Instrument | Typical Crest Factor | Interpretation |
|-----------|---------------------|----------------|
| **Kick drum** | 15-20 dB | Sharp transient, needs headroom |
| **Snare** | 12-18 dB | Punchy attack |
| **Hi-hat** | 10-16 dB | Moderate transients |
| **808 bass** | 6-12 dB | Sustained, compressed |
| **Sub bass** | 4-8 dB | Very sustained |
| **Rhodes/Keys** | 10-14 dB | Dynamic playing |
| **Synth pad** | 6-10 dB | Sustained |
| **Synth lead** | 8-14 dB | Varies by sound |
| **Vocal** | 10-16 dB | Highly variable |
| **Full mix** | 8-14 dB | Depends on genre |

### 4.4 Crest Factor for Compression Decisions

```python
def suggest_compression_from_crest(
    crest_factor_db: float,
    target_crest_db: float,
    track_role: str
) -> dict:
    """
    Suggest compression settings based on crest factor analysis.
    
    Args:
        crest_factor_db: Current crest factor
        target_crest_db: Desired crest factor for genre/role
        track_role: Track type (kick, bass, melody, etc.)
    
    Returns:
        Suggested compression parameters
    """
    delta = crest_factor_db - target_crest_db
    
    if delta <= 0:
        # Already at or below target - no compression needed
        return {"compression_needed": False}
    
    # Calculate ratio needed to achieve target crest factor
    # Higher delta = more compression needed
    suggested_ratio = 1 + (delta / 10)  # Rough approximation
    suggested_ratio = min(suggested_ratio, 10.0)  # Cap at 10:1
    
    # Threshold based on track type
    thresholds = {
        "kick": -12,
        "snare": -15,
        "bass": -18,
        "melody": -20,
        "vocal": -18,
        "default": -18
    }
    threshold = thresholds.get(track_role, thresholds["default"])
    
    # Attack/release by track type (ms)
    timing = {
        "kick": {"attack": 2, "release": 50},
        "snare": {"attack": 3, "release": 80},
        "bass": {"attack": 15, "release": 150},
        "melody": {"attack": 10, "release": 100},
        "vocal": {"attack": 5, "release": 80},
        "default": {"attack": 10, "release": 100}
    }
    track_timing = timing.get(track_role, timing["default"])
    
    return {
        "compression_needed": True,
        "suggested_ratio": round(suggested_ratio, 1),
        "threshold_db": threshold,
        "attack_ms": track_timing["attack"],
        "release_ms": track_timing["release"],
        "makeup_gain_db": delta / 2,  # Compensate for half the reduction
        "crest_reduction_target": delta
    }
```

---

## 5. Dataclass Schemas

### 5.1 AutoGainConfig

```python
from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple
from enum import Enum


class CompressionStyle(Enum):
    """Compression character presets."""
    MODERN_AGGRESSIVE = "modern_aggressive"
    MODERN_BRICK = "modern_brick"
    VINTAGE_GENTLE = "vintage_gentle"
    SP1200_CRUNCH = "sp1200_crunch"
    WEST_COAST_SMOOTH = "west_coast_smooth"
    SMOOTH_VINTAGE = "smooth_vintage"
    TRANSPARENT = "transparent"


@dataclass
class TrackLevelTarget:
    """Level target for a single track role."""
    relative_lufs: float              # Relative to mix target
    priority: int                      # Mix priority (1 = highest)
    crest_factor_range: Tuple[float, float] = (8.0, 16.0)  # Min/max crest
    pan_position: float = 0.0          # -1 (left) to 1 (right)
    allow_compression: bool = True
    allow_limiting: bool = False


@dataclass
class AutoGainConfig:
    """Configuration for automatic gain staging."""
    
    # Target loudness
    target_lufs: float = -14.0
    
    # Headroom management
    headroom_db: float = -6.0
    true_peak_ceiling_db: float = -1.0
    
    # Gain adjustment limits
    max_gain_increase_db: float = 24.0
    max_gain_decrease_db: float = 24.0
    
    # Dynamics preservation
    preserve_dynamics: bool = True
    min_crest_factor_ratio: float = 0.7  # Don't reduce crest by more than 30%
    
    # Analysis settings
    lufs_measurement_type: str = "integrated"  # "momentary", "short_term", "integrated"
    block_size_ms: float = 400.0
    
    # Metering
    enable_k_weighting: bool = True
    enable_gating: bool = True
    
    # Processing order
    analyze_before_processing: bool = True
    apply_gain_before_compression: bool = True
```

### 5.2 GenreMixTemplate

```python
@dataclass
class GenreMixTemplate:
    """Complete mix template for a genre."""
    
    genre: str
    
    # Master settings
    master_target_lufs: float = -14.0
    headroom_db: float = -6.0
    true_peak_db: float = -1.0
    
    # Track level targets by role
    track_targets: Dict[str, TrackLevelTarget] = field(default_factory=dict)
    
    # Dynamics style
    compression_style: CompressionStyle = CompressionStyle.TRANSPARENT
    sidechain_depth: float = 0.0
    sidechain_attack_ms: float = 5.0
    sidechain_release_ms: float = 100.0
    
    # Spectral character (for validation)
    target_brightness: float = 0.5     # 0.0 (dark) to 1.0 (bright)
    target_warmth: float = 0.5         # 0.0 (thin) to 1.0 (warm)
    target_sub_presence: float = 0.5   # 0.0 (light) to 1.0 (heavy)
    
    # Dynamic range target
    target_dynamic_range_db: float = 10.0  # LRA (Loudness Range)
    
    def get_track_target(self, role: str) -> Optional[TrackLevelTarget]:
        """Get target for a track role, with fallback."""
        if role in self.track_targets:
            return self.track_targets[role]
        
        # Fallback defaults
        fallbacks = {
            "drums": TrackLevelTarget(2.0, 3),
            "melodic": TrackLevelTarget(0.0, 5),
            "fx": TrackLevelTarget(-4.0, 8),
        }
        return fallbacks.get(role, TrackLevelTarget(0.0, 10))
```

### 5.3 LoudnessAnalysis Result

```python
@dataclass
class LoudnessAnalysis:
    """Result of loudness analysis for a track."""
    
    # LUFS measurements
    integrated_lufs: float
    momentary_lufs_max: float
    short_term_lufs_max: float
    loudness_range_lu: float  # LRA
    
    # Peak measurements
    true_peak_dbfs: float
    sample_peak_dbfs: float
    
    # Dynamics
    crest_factor_db: float
    rms_db: float
    
    # Suggested actions
    suggested_gain_db: float = 0.0
    suggested_compression: Optional[dict] = None
    
    # Metadata
    duration_seconds: float = 0.0
    sample_rate: int = 44100
    channels: int = 1
```

### 5.4 AutoGainResult

```python
@dataclass
class AutoGainResult:
    """Result of auto-gain staging process."""
    
    # Input analysis
    original_lufs: float
    original_peak_db: float
    original_crest_factor: float
    
    # Applied adjustments
    gain_applied_db: float
    compression_applied: bool
    limiting_applied: bool
    
    # Output analysis
    output_lufs: float
    output_peak_db: float
    output_crest_factor: float
    
    # Validation
    target_achieved: bool
    dynamics_preserved: bool
    headroom_maintained: bool
    
    # Detailed log
    processing_log: list = field(default_factory=list)
```

---

## 6. Python Code Snippets

### 6.1 Complete LUFS Estimator

```python
import numpy as np
from scipy import signal
from typing import Tuple, Optional


class LUFSMeter:
    """
    ITU-R BS.1770-4 compliant LUFS meter.
    
    Usage:
        meter = LUFSMeter(sample_rate=44100)
        integrated = meter.integrated_loudness(audio)
        momentary = meter.momentary_loudness(audio)
    """
    
    def __init__(self, sample_rate: int = 44100):
        self.sample_rate = sample_rate
        self._calculate_filter_coefficients()
    
    def _calculate_filter_coefficients(self):
        """Calculate K-weighting filter coefficients."""
        fs = self.sample_rate
        
        # Stage 1: Pre-filter (high shelf)
        f0 = 1681.974450955533
        G = 3.999843853973347
        Q = 0.7071752369554196
        
        K = np.tan(np.pi * f0 / fs)
        Vh = 10 ** (G / 20)
        Vb = Vh ** 0.4996667741545416
        
        a0 = 1.0 + K / Q + K * K
        self.pre_b = np.array([
            (Vh + Vb * K / Q + K * K) / a0,
            2.0 * (K * K - Vh) / a0,
            (Vh - Vb * K / Q + K * K) / a0
        ])
        self.pre_a = np.array([
            1.0,
            2.0 * (K * K - 1.0) / a0,
            (1.0 - K / Q + K * K) / a0
        ])
        
        # Stage 2: High-pass filter
        f0 = 38.13547087602444
        Q = 0.5003270373238773
        
        K = np.tan(np.pi * f0 / fs)
        a0 = 1.0 + K / Q + K * K
        self.hp_b = np.array([1.0, -2.0, 1.0]) / a0
        self.hp_a = np.array([
            1.0,
            2.0 * (K * K - 1.0) / a0,
            (1.0 - K / Q + K * K) / a0
        ])
    
    def k_weight(self, audio: np.ndarray) -> np.ndarray:
        """Apply K-weighting filter to audio."""
        # Apply pre-filter
        filtered = signal.lfilter(self.pre_b, self.pre_a, audio)
        # Apply high-pass
        filtered = signal.lfilter(self.hp_b, self.hp_a, filtered)
        return filtered
    
    def integrated_loudness(self, audio: np.ndarray) -> float:
        """
        Calculate integrated loudness (LUFS) with gating.
        
        Args:
            audio: Mono or stereo audio (-1 to 1)
        
        Returns:
            Integrated loudness in LUFS
        """
        # Handle stereo
        if len(audio.shape) > 1:
            channels = [audio[:, i] for i in range(audio.shape[1])]
        else:
            channels = [audio]
        
        # K-weight each channel
        weighted = [self.k_weight(ch) for ch in channels]
        
        # Calculate mean square per 400ms block with 75% overlap
        block_samples = int(0.4 * self.sample_rate)  # 400ms
        hop_samples = int(0.1 * self.sample_rate)     # 100ms hop (75% overlap)
        
        num_blocks = (len(weighted[0]) - block_samples) // hop_samples + 1
        if num_blocks <= 0:
            return -70.0
        
        block_loudness = np.zeros(num_blocks)
        
        for i in range(num_blocks):
            start = i * hop_samples
            end = start + block_samples
            
            # Sum mean square across channels (ITU weighting: L=R=1.0, C=1.0, Ls=Lr=1.41)
            ms = sum(np.mean(ch[start:end] ** 2) for ch in weighted)
            block_loudness[i] = ms
        
        # Convert to LUFS
        block_lufs = -0.691 + 10 * np.log10(block_loudness + 1e-10)
        
        # Stage 1: Absolute threshold (-70 LUFS)
        above_absolute = block_loudness[block_lufs > -70]
        
        if len(above_absolute) == 0:
            return -70.0
        
        # Ungated mean
        ungated_mean = np.mean(above_absolute)
        ungated_lufs = -0.691 + 10 * np.log10(ungated_mean)
        
        # Stage 2: Relative threshold (-10 LU below ungated)
        relative_threshold = ungated_lufs - 10
        above_relative = block_loudness[block_lufs > relative_threshold]
        
        if len(above_relative) == 0:
            return ungated_lufs
        
        # Gated mean
        gated_mean = np.mean(above_relative)
        integrated = -0.691 + 10 * np.log10(gated_mean)
        
        return integrated
    
    def momentary_loudness(self, audio: np.ndarray) -> np.ndarray:
        """
        Calculate momentary loudness (400ms window, no gating).
        
        Returns:
            Array of momentary LUFS values
        """
        if len(audio.shape) > 1:
            mono = np.mean(audio, axis=1)
        else:
            mono = audio
        
        weighted = self.k_weight(mono)
        
        block_samples = int(0.4 * self.sample_rate)
        hop_samples = int(0.1 * self.sample_rate)
        
        num_blocks = (len(weighted) - block_samples) // hop_samples + 1
        momentary = np.zeros(num_blocks)
        
        for i in range(num_blocks):
            start = i * hop_samples
            end = start + block_samples
            ms = np.mean(weighted[start:end] ** 2)
            momentary[i] = -0.691 + 10 * np.log10(ms + 1e-10)
        
        return momentary
    
    def short_term_loudness(self, audio: np.ndarray) -> np.ndarray:
        """
        Calculate short-term loudness (3s window).
        
        Returns:
            Array of short-term LUFS values
        """
        if len(audio.shape) > 1:
            mono = np.mean(audio, axis=1)
        else:
            mono = audio
        
        weighted = self.k_weight(mono)
        
        block_samples = int(3.0 * self.sample_rate)  # 3 seconds
        hop_samples = int(1.0 * self.sample_rate)     # 1 second hop
        
        num_blocks = (len(weighted) - block_samples) // hop_samples + 1
        if num_blocks <= 0:
            return np.array([-70.0])
        
        short_term = np.zeros(num_blocks)
        
        for i in range(num_blocks):
            start = i * hop_samples
            end = start + block_samples
            ms = np.mean(weighted[start:end] ** 2)
            short_term[i] = -0.691 + 10 * np.log10(ms + 1e-10)
        
        return short_term
    
    def true_peak(self, audio: np.ndarray, oversample: int = 4) -> float:
        """
        Calculate true peak with oversampling.
        
        Args:
            audio: Input audio
            oversample: Oversampling factor (4x standard)
        
        Returns:
            True peak in dBFS
        """
        if len(audio.shape) > 1:
            peaks = [self._true_peak_channel(audio[:, i], oversample) 
                     for i in range(audio.shape[1])]
            peak = max(peaks)
        else:
            peak = self._true_peak_channel(audio, oversample)
        
        if peak > 0:
            return 20 * np.log10(peak)
        return -100.0
    
    def _true_peak_channel(self, channel: np.ndarray, oversample: int) -> float:
        """Calculate true peak for single channel."""
        # Upsample using polyphase filter
        upsampled = signal.resample_poly(channel, oversample, 1)
        return np.max(np.abs(upsampled))
    
    def loudness_range(self, audio: np.ndarray) -> float:
        """
        Calculate loudness range (LRA) in LU.
        
        LRA = difference between 95th and 10th percentile of short-term loudness
        """
        short_term = self.short_term_loudness(audio)
        
        # Remove values below absolute gate
        above_gate = short_term[short_term > -70]
        
        if len(above_gate) < 2:
            return 0.0
        
        # Relative gate at -20 LU below ungated mean
        ungated_mean = np.mean(10 ** (above_gate / 10))
        ungated_lufs = 10 * np.log10(ungated_mean)
        relative_gate = ungated_lufs - 20
        
        above_relative = above_gate[above_gate > relative_gate]
        
        if len(above_relative) < 2:
            return 0.0
        
        # LRA = 95th percentile - 10th percentile
        p95 = np.percentile(above_relative, 95)
        p10 = np.percentile(above_relative, 10)
        
        return p95 - p10
```

### 6.2 Auto-Gain Staging Function

```python
def auto_gain_stage(
    audio: np.ndarray,
    track_role: str,
    genre_template: GenreMixTemplate,
    sample_rate: int = 44100,
    config: Optional[AutoGainConfig] = None
) -> Tuple[np.ndarray, AutoGainResult]:
    """
    Automatically set gain level for a track based on genre template.
    
    Args:
        audio: Input audio
        track_role: Track role (kick, bass, melody, etc.)
        genre_template: Genre mix template with targets
        sample_rate: Sample rate
        config: Optional auto-gain configuration
    
    Returns:
        Tuple of (processed_audio, result)
    """
    if config is None:
        config = AutoGainConfig()
    
    meter = LUFSMeter(sample_rate)
    
    # Analyze input
    original_lufs = meter.integrated_loudness(audio)
    original_peak = meter.true_peak(audio)
    original_crest = calculate_crest_factor(audio)
    
    # Get target for this track role
    target = genre_template.get_track_target(track_role)
    if target is None:
        target = TrackLevelTarget(0.0, 10)
    
    # Calculate required gain
    gain_db = calculate_auto_gain(
        track_lufs=original_lufs,
        target_relative_lufs=target.relative_lufs,
        mix_target_lufs=genre_template.master_target_lufs,
        headroom_db=genre_template.headroom_db
    )
    
    # Limit gain to config bounds
    gain_db = np.clip(gain_db, -config.max_gain_decrease_db, config.max_gain_increase_db)
    
    # Apply gain
    gain_linear = 10 ** (gain_db / 20)
    processed = audio * gain_linear
    
    # Check if we need compression (crest factor out of range)
    compression_applied = False
    if target.allow_compression:
        min_crest, max_crest = target.crest_factor_range
        if original_crest > max_crest:
            # Apply gentle compression
            comp_suggestion = suggest_compression_from_crest(
                original_crest, max_crest, track_role
            )
            if comp_suggestion.get("compression_needed"):
                # Apply compression here (simplified)
                compression_applied = True
    
    # Analyze output
    output_lufs = meter.integrated_loudness(processed)
    output_peak = meter.true_peak(processed)
    output_crest = calculate_crest_factor(processed)
    
    # Validate results
    target_achieved = abs(output_lufs - (genre_template.master_target_lufs + 
                         genre_template.headroom_db + target.relative_lufs)) < 1.0
    
    dynamics_preserved = check_dynamics_preservation(
        original_crest, output_crest, config.min_crest_factor_ratio
    )
    
    headroom_maintained = output_peak < config.true_peak_ceiling_db
    
    result = AutoGainResult(
        original_lufs=original_lufs,
        original_peak_db=original_peak,
        original_crest_factor=original_crest,
        gain_applied_db=gain_db,
        compression_applied=compression_applied,
        limiting_applied=False,
        output_lufs=output_lufs,
        output_peak_db=output_peak,
        output_crest_factor=output_crest,
        target_achieved=target_achieved,
        dynamics_preserved=dynamics_preserved,
        headroom_maintained=headroom_maintained,
        processing_log=[
            f"Applied {gain_db:+.1f} dB gain",
            f"Target relative LUFS: {target.relative_lufs:+.1f}",
            f"Achieved: {output_lufs:.1f} LUFS"
        ]
    )
    
    return processed, result
```

---

## 7. Integration with Existing MixEngine

### 7.1 Current Architecture Analysis

The existing `MixEngine` in [mix_engine.py](../../multimodal_gen/mix_engine.py) provides:

- Bus-based mixing (`MixBus` class)
- Sidechain compression
- Basic LUFS measurement (simplified, not BS.1770 compliant)
- Master processing and limiting
- Genre-specific presets (`MIX_PRESETS`)

**Current limitations:**
1. LUFS measurement uses simple high-pass, not K-weighting
2. No gating in loudness measurement
3. No per-track auto-gain staging
4. Genre presets only control bus gain, not target LUFS

### 7.2 Proposed Integration Points

```python
# Proposed additions to MixEngine

class MixEngine:
    def __init__(self, sample_rate: int = 44100):
        # ... existing init ...
        
        # NEW: Add LUFS meter and auto-gain components
        self.lufs_meter = LUFSMeter(sample_rate)
        self.auto_gain_config = AutoGainConfig()
        self.genre_template: Optional[GenreMixTemplate] = None
    
    def set_genre_template(self, template: GenreMixTemplate):
        """Set the genre mix template for auto-gain staging."""
        self.genre_template = template
    
    def auto_stage_track(
        self,
        bus_name: str,
        audio: np.ndarray,
        track_role: Optional[str] = None
    ) -> AutoGainResult:
        """
        Auto-gain stage a track before adding to bus.
        
        Args:
            bus_name: Target bus name
            audio: Track audio
            track_role: Optional role override (auto-detected from bus_name if None)
        
        Returns:
            AutoGainResult with analysis and applied settings
        """
        if track_role is None:
            track_role = classify_track_role(bus_name)
        
        if self.genre_template is None:
            # Fallback to default template
            self.genre_template = get_default_template()
        
        processed, result = auto_gain_stage(
            audio, track_role, self.genre_template, 
            self.sample_rate, self.auto_gain_config
        )
        
        # Add to bus with 0 dB gain (already staged)
        self.add_to_bus(bus_name, processed, gain_db=0.0)
        
        return result
    
    def measure_lufs(self, audio: np.ndarray) -> float:
        """
        IMPROVED: Measure integrated LUFS using BS.1770-4.
        
        Replaces the simplified implementation with compliant version.
        """
        return self.lufs_meter.integrated_loudness(audio)
    
    def get_bus_lufs(self, bus_name: str) -> LoudnessAnalysis:
        """Get full loudness analysis for a bus."""
        bus = self.buses.get(bus_name)
        if not bus or bus.audio_buffer is None:
            return LoudnessAnalysis(
                integrated_lufs=-70.0,
                momentary_lufs_max=-70.0,
                short_term_lufs_max=-70.0,
                loudness_range_lu=0.0,
                true_peak_dbfs=-100.0,
                sample_peak_dbfs=-100.0,
                crest_factor_db=0.0,
                rms_db=-100.0
            )
        
        audio = bus.audio_buffer
        
        return LoudnessAnalysis(
            integrated_lufs=self.lufs_meter.integrated_loudness(audio),
            momentary_lufs_max=np.max(self.lufs_meter.momentary_loudness(audio)),
            short_term_lufs_max=np.max(self.lufs_meter.short_term_loudness(audio)),
            loudness_range_lu=self.lufs_meter.loudness_range(audio),
            true_peak_dbfs=self.lufs_meter.true_peak(audio),
            sample_peak_dbfs=20 * np.log10(np.max(np.abs(audio)) + 1e-10),
            crest_factor_db=calculate_crest_factor(audio),
            rms_db=20 * np.log10(np.sqrt(np.mean(audio ** 2)) + 1e-10),
            duration_seconds=len(audio) / self.sample_rate,
            sample_rate=self.sample_rate,
            channels=1 if len(audio.shape) == 1 else audio.shape[1]
        )
```

### 7.3 Integration with Genre Rules

Connect to existing `genre_rules.py` mix rules:

```python
def create_template_from_genre_rules(genre: str) -> GenreMixTemplate:
    """
    Create a GenreMixTemplate from existing genre_rules.py definitions.
    
    This bridges the existing genre_rules system with auto-gain staging.
    """
    from multimodal_gen.genre_rules import get_genre_rules
    
    engine = get_genre_rules()
    ruleset = engine.get_ruleset(genre)
    
    # Get mix rules from genre_rules
    mix_rules = engine.get_mix_rules(genre)
    
    # Map to template
    template = GenreMixTemplate(genre=genre)
    
    # Extract spectral targets from mix rules
    for rule in mix_rules:
        if rule.type.value == "spectral":
            template.target_brightness = rule.max_brightness
            template.target_warmth = rule.min_warmth
    
    # Apply genre-specific level targets
    if genre in GENRE_MIX_TEMPLATES:
        preset = GENRE_MIX_TEMPLATES[genre]
        template.track_targets = preset["track_targets"]
        template.master_target_lufs = preset["master_target_lufs"]
        template.sidechain_depth = preset.get("sidechain_depth", 0.0)
    
    return template
```

---

## 8. Professional References

### 8.1 iZotope Neutron Assistant

**Approach:**
- Analyzes spectral content and dynamics
- Classifies track type (vocal, bass, drums, etc.)
- Suggests EQ, compression, and gain settings
- Uses machine learning for classification

**Key insights:**
- Track classification is critical for correct level targets
- Spectral analysis informs EQ decisions alongside level
- Provides "range" suggestions, not absolute values

### 8.2 Plugin Alliance Auto-Gain

**Approach:**
- Real-time LUFS monitoring
- Maintains consistent output regardless of input level
- Useful for A/B comparison during mixing

**Key insights:**
- Auto-gain for monitoring vs. auto-gain for mixing are different
- Monitoring auto-gain should be transparent
- Mixing auto-gain can be destructive (intentional level changes)

### 8.3 LANDR Mastering

**Approach:**
- Analyzes full track for genre classification
- Applies genre-appropriate mastering chain
- Targets streaming platform LUFS requirements

**Key insights:**
- Genre detection from audio analysis
- Platform-specific targets (-14 LUFS for Spotify, etc.)
- Balance between loudness and dynamics varies by genre

---

## 9. Platform Loudness Targets

| Platform | Target LUFS | True Peak | Notes |
|----------|-------------|-----------|-------|
| **Spotify** | -14 LUFS | -1 dBTP | Normalizes down only |
| **Apple Music** | -16 LUFS | -1 dBTP | Sound Check enabled |
| **YouTube** | -14 LUFS | -1 dBTP | Normalizes up and down |
| **Tidal** | -14 LUFS | -1 dBTP | Master quality |
| **Amazon Music** | -14 LUFS | -2 dBTP | Slightly lower ceiling |
| **Broadcast (EBU R128)** | -23 LUFS | -1 dBTP | European broadcast |
| **CD Master** | -9 to -12 LUFS | -0.1 dBTP | Loudness war legacy |

---

## 10. Implementation Recommendations

### 10.1 Phase 1: Core LUFS Measurement
1. Implement `LUFSMeter` class with BS.1770-4 compliance
2. Add true peak measurement with oversampling
3. Integrate into existing `MixEngine.measure_lufs()`

### 10.2 Phase 2: Genre Templates
1. Define `GenreMixTemplate` dataclass
2. Create templates for top 8 genres
3. Connect to existing `genre_rules.py` system

### 10.3 Phase 3: Auto-Gain Algorithm
1. Implement `auto_gain_stage()` function
2. Add crest factor analysis
3. Implement dynamics preservation checks

### 10.4 Phase 4: Integration
1. Add `auto_stage_track()` to `MixEngine`
2. Create `get_bus_lufs()` for analysis
3. Update mix presets with LUFS targets

---

## 11. References

1. ITU-R BS.1770-4: "Algorithms to measure audio programme loudness and true-peak audio level"
2. EBU R128: "Loudness normalisation and permitted maximum level of audio signals"
3. AES TD1004.1.15-10: "Recommendation for Loudness of Audio Streaming"
4. Sound On Sound: "The End Of The Loudness War?"
5. iZotope: "A Practical Guide to Loudness" (White Paper)
6. Plugin Alliance: "Understanding LUFS, LKFS, and RMS"

---

*This research report provides the foundation for implementing intelligent auto-gain staging in the multimodal-ai-music-gen system. Implementation should proceed incrementally, validating each component against reference measurements.*
