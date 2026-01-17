# Spatial Audio and Dolby Atmos Preparation Research Report

## DSP Research for Immersive Music Production

**Date:** January 17, 2026  
**Scope:** Binaural Rendering, Stereo-to-Surround Upmixing, Height Channels, Object-Based Panning, Dolby Atmos Music Specs

---

## Table of Contents

1. [Binaural Rendering](#1-binaural-rendering)
2. [Stereo-to-Surround Upmixing](#2-stereo-to-surround-upmixing)
3. [Height Channel Generation](#3-height-channel-generation)
4. [Object-Based Panning (VBAP)](#4-object-based-panning-vbap)
5. [Dolby Atmos Music Specifications](#5-dolby-atmos-music-specifications)
6. [Python Data Schemas](#6-python-data-schemas)
7. [Algorithm Specifications](#7-algorithm-specifications)
8. [Implementation Notes](#8-implementation-notes)

---

## 1. Binaural Rendering

### 1.1 HRTF Fundamentals

**Head-Related Transfer Function (HRTF)** describes how sound from a specific direction is filtered by the head, pinnae (outer ear), ear canal, and torso before reaching the eardrum.

#### Key Concepts:
- **HRIR (Head-Related Impulse Response)**: Time-domain representation
- **HRTF**: Frequency-domain representation (Fourier transform of HRIR)
- **ITD (Interaural Time Difference)**: Time delay between ears (0-650 μs)
- **ILD (Interaural Level Difference)**: Level difference between ears (up to 20 dB at high frequencies)

#### HRTF Components:
```
HRTF(f, θ, φ) where:
  f = frequency
  θ = azimuth angle (-180° to +180°)
  φ = elevation angle (-90° to +90°)
```

#### Localization Cues:
| Frequency Range | Primary Cue | Mechanism |
|-----------------|-------------|-----------|
| < 800 Hz | ITD (phase) | Wavelength > head size |
| 800-1600 Hz | Transition zone | Both ITD and ILD |
| > 1600 Hz | ILD + spectral | Head shadow effect |

### 1.2 MIT KEMAR HRTF Dataset

The MIT Media Lab KEMAR dataset is the most widely used free HRTF dataset:

**Specifications:**
- **Sample Rate:** 44.1 kHz
- **Elevations:** -40° to +90° (14 elevation angles)
- **Azimuths:** 710 total positions
- **Filter Length:** 128-512 samples (compact/full)
- **Format:** 16-bit signed integer WAV files

**File Organization:**
```
compact/
  elev-40/    # -40° elevation
    H-40e000a.wav  # Left ear, 0° azimuth
    H-40e000a.wav  # Right ear, 0° azimuth
    ...
  elev0/      # 0° elevation (ear level)
  elev90/     # +90° (directly above)
```

**Available Variants:**
- `compact/`: Minimum phase HRIRs (faster, less accurate)
- `full/`: Full phase HRIRs (accurate ITD)
- `diffuse/`: Diffuse-field equalized (flatter frequency response)

### 1.3 Binaural Synthesis Algorithm

#### Core Convolution Process:
```
For a mono source S positioned at (θ, φ):

1. Load HRIR_L(θ, φ) and HRIR_R(θ, φ)
2. Output_L = S ⊛ HRIR_L  (convolution)
3. Output_R = S ⊛ HRIR_R
```

#### HRTF Interpolation (for positions between measurements):

**Bilinear Interpolation:**
```
Given target position (θ, φ) between four measured positions:
  P1(θ1, φ1), P2(θ2, φ1), P3(θ1, φ2), P4(θ2, φ2)

Weights:
  w_θ = (θ - θ1) / (θ2 - θ1)
  w_φ = (φ - φ1) / (φ2 - φ1)

Interpolated HRIR:
  H = (1-w_θ)(1-w_φ)H1 + w_θ(1-w_φ)H2 + (1-w_θ)w_φH3 + w_θ*w_φH4
```

**Spherical Linear Interpolation (SLERP)** for phase-coherent interpolation:
```
H_interp = sin((1-t)Ω)/sin(Ω) * H1 + sin(tΩ)/sin(Ω) * H2
where Ω = arccos(H1 · H2)
```

### 1.4 Headphone vs Speaker Mixing

| Aspect | Headphones | Speakers |
|--------|------------|----------|
| Crosstalk | None (isolated) | Natural (sound reaches both ears) |
| HRTF needed | Always | Optional (room provides cues) |
| Head tracking | Beneficial | Not applicable |
| Sweet spot | Head-locked | Room position dependent |
| ITD simulation | Required | Natural from speaker positions |
| Externalization | Challenging | Natural |

#### Headphone Equalization:
```
Headphone Transfer Function (HTF) compensation:
  Target_Signal = Source * HRTF / HTF

Without HTF compensation, sounds may appear "inside the head"
```

### 1.5 Python HRTF Convolution Specification

```python
# HRTF Convolution Algorithm (Specification Only)

def binaural_render(
    mono_signal: np.ndarray,        # Input mono audio
    hrir_left: np.ndarray,          # Left ear impulse response
    hrir_right: np.ndarray,         # Right ear impulse response
    use_fft: bool = True            # Use FFT convolution for efficiency
) -> tuple[np.ndarray, np.ndarray]:
    """
    Renders mono signal to binaural stereo using HRTF convolution.
    
    Algorithm:
    1. If use_fft:
       - Compute FFT of signal and HRIRs
       - Multiply in frequency domain
       - IFFT to get time-domain output
    2. Else:
       - Direct time-domain convolution
    
    Returns: (left_channel, right_channel)
    """
    pass

def interpolate_hrtf(
    hrtf_database: dict,            # Loaded HRTF measurements
    target_azimuth: float,          # Desired azimuth (-180 to 180)
    target_elevation: float,        # Desired elevation (-40 to 90)
    method: str = 'bilinear'        # 'nearest', 'bilinear', 'spherical'
) -> tuple[np.ndarray, np.ndarray]:
    """
    Interpolates HRTF for arbitrary source position.
    
    Algorithm:
    1. Find surrounding measured positions
    2. Calculate interpolation weights
    3. Blend HRIRs using weighted sum
    
    Returns: (hrir_left, hrir_right)
    """
    pass
```

---

## 2. Stereo-to-Surround Upmixing

### 2.1 Basic Matrix Formulas

Given stereo input: **L** (left) and **R** (right)

#### Sum/Difference Decoding (Passive):
```
Center (C)     = (L + R) / 2        # In-phase content (vocals, bass)
LFE            = lowpass(C, 120Hz)  # Sub-bass extraction
Surround Sum   = L + R              # Mono ambient
Surround Diff  = L - R              # Side/ambient content

Front Left (FL)  = L
Front Right (FR) = R
Rear Left (RL)   = k * (L - R)      # k = 0.5-0.7 attenuation
Rear Right (RR)  = k * (R - L)
```

#### Improved 5.1 Extraction:
```
# Phase-based steering
C  = (L + R) * 0.5 * center_gain
FL = L - (C * center_reduction)
FR = R - (C * center_reduction)

# Ambient extraction using decorrelation
Ambient_L = allpass_filter(L - R)
Ambient_R = allpass_filter(R - L)

RL = ambient_gain * (Ambient_L + reverb_tail_L)
RR = ambient_gain * (Ambient_R + reverb_tail_R)

# LFE
LFE = lowpass((L + R), 120Hz) * lfe_gain
```

### 2.2 Frequency-Domain Upmixing

#### Spectral Decomposition Approach:
```
For each frequency bin k in STFT:
  
  1. Compute magnitude ratio:
     ratio = |L[k]| / (|L[k]| + |R[k]| + ε)
  
  2. Compute phase difference:
     phase_diff = angle(L[k]) - angle(R[k])
  
  3. Estimate source position:
     if |phase_diff| < threshold and ratio ≈ 0.5:
         → Center channel
     elif ratio > 0.7:
         → Left channel
     elif ratio < 0.3:
         → Right channel
     else:
         → Distribute to surrounds based on decorrelation
```

### 2.3 Ambient Extraction for Rear Channels

#### Techniques:
1. **Side Signal (M/S)**: `Side = (L - R)` captures stereo width
2. **Decorrelation**: Apply different allpass filters to create spaciousness
3. **Reverb Tail Isolation**: Use transient detection to separate reverb
4. **Principal Component Analysis**: Extract uncorrelated ambient components

#### Delay-Based Ambient Enhancement:
```
Rear_L = delay(L - R, 10-30ms) * 0.5
Rear_R = delay(R - L, 10-30ms) * 0.5

# Additional decorrelation
Rear_L = allpass_cascade(Rear_L, seed=1)
Rear_R = allpass_cascade(Rear_R, seed=2)
```

### 2.4 ML-Based Upmixing (Research Notes)

**Approaches in Literature:**
- **Source Separation Networks**: Demucs, Spleeter for stem extraction
- **U-Net Architectures**: For spectral masking
- **Spatial Audio Codecs**: MPEG-H, Dolby AC-4 parametric upmixing

**Key Papers:**
- "Deep Learning for Spatial Audio" (IEEE Signal Processing)
- "Neural Network-Based Upmixing" (AES Convention)

**Note:** Full ML implementation requires significant training data and is outside scope of basic DSP preparation.

---

## 3. Height Channel Generation

### 3.1 Frequency-Based Routing

**Principle:** High-frequency content (cymbals, harmonics, air) naturally perceived as "above"

```
Height channel contribution:
  
  # High-pass crossover
  Height_L = highpass(L, 4000-8000 Hz) * height_gain
  Height_R = highpass(R, 4000-8000 Hz) * height_gain
  
  # Gentle slope (12-24 dB/octave) to avoid harsh transitions
  
  # Reduce main channels to compensate
  Main_L = L - (Height_L * compensation_factor)
  Main_R = R - (Height_R * compensation_factor)
```

### 3.2 Reverb/Ambience Extraction

**Height channels benefit from diffuse, ambient content:**

```
# Method 1: Reverb tail extraction
envelope = compute_envelope(stereo_sum)
reverb_mask = envelope < threshold  # Low-energy = reverb
height_content = stereo * reverb_mask

# Method 2: Transient removal
transients = detect_transients(stereo)
ambient = stereo - transients
height_L = ambient[0] * decorrelate_filter_1
height_R = ambient[1] * decorrelate_filter_2

# Method 3: Side-chain from reverb send
# Route a portion of reverb return to height channels
height_reverb_L = reverb_output_L * height_reverb_send
height_reverb_R = reverb_output_R * height_reverb_send
```

### 3.3 Object-Based vs Bed-Based Approaches

| Approach | Description | Use Case |
|----------|-------------|----------|
| **Bed-Based** | Fixed channel assignment | Ambient, backgrounds, reverb |
| **Object-Based** | Dynamic position metadata | Moving elements, spot effects |

**7.1.4 Bed Configuration:**
```
Ear-level (7.1):
  L, R, C, LFE, Ls, Rs, Lrs, Rrs

Height layer (.4):
  Ltf, Rtf, Ltr, Rtr
  (Left/Right Top Front/Rear)
```

**Object Metadata:**
```python
@dataclass
class AtmosObject:
    audio_id: int
    position: tuple[float, float, float]  # x, y, z (-1 to 1)
    size: float                            # 0 (point) to 1 (diffuse)
    divergence: float                      # Spread factor
```

---

## 4. Object-Based Panning (VBAP)

### 4.1 VBAP Algorithm (Vector Base Amplitude Panning)

**Developed by Ville Pulkki (Helsinki University of Technology)**

#### Concept:
VBAP positions a virtual source by distributing signal to a subset of speakers forming a triangle (3D) or pair (2D) around the source direction.

#### 2D VBAP (Horizontal Panning):
```
Given:
  - Source direction vector: p = (cos(θ), sin(θ))
  - Two speakers at angles θ1, θ2
  - Speaker direction vectors: l1, l2

Gain calculation:
  g = p * inv([l1, l2]^T)
  
  where g = [g1, g2] are the speaker gains
  
Normalization (energy preservation):
  g_normalized = g / sqrt(g1² + g2²)
```

#### 3D VBAP (With Height):
```
Given:
  - Source direction: p = (x, y, z) normalized
  - Three speakers forming a triangle: l1, l2, l3
  - Speaker matrix L = [l1, l2, l3]^T

Gain calculation:
  g = p * inv(L)
  g = [g1, g2, g3]

Conditions:
  - All gains must be positive (source inside triangle)
  - If any gain < 0, choose different speaker triplet

Normalization:
  g_normalized = g / sqrt(g1² + g2² + g3²)
```

### 4.2 Speaker Layout Triangulation

For 3D VBAP, pre-compute speaker triangles covering the sphere:

```python
# Conceptual triangulation for 7.1.4
speaker_positions = {
    'L':   (−30°, 0°),
    'R':   (+30°, 0°),
    'C':   (0°, 0°),
    'Ls':  (−110°, 0°),
    'Rs':  (+110°, 0°),
    'Lrs': (−150°, 0°),
    'Rrs': (+150°, 0°),
    'Ltf': (−45°, +45°),
    'Rtf': (+45°, +45°),
    'Ltr': (−135°, +45°),
    'Rtr': (+135°, +45°),
}

# Triangles are pre-computed using Delaunay triangulation
# on the unit sphere
```

### 4.3 Distance-Based Attenuation

```
Attenuation = 1 / (1 + k * (distance - reference_distance))

where:
  k = rolloff coefficient (typically 0.5-2.0)
  reference_distance = 1.0 (normalized)

Additional cues for distance:
  - High-frequency rolloff (air absorption)
  - Increased reverb ratio (wet/dry)
  - Reduced direct sound level
```

### 4.4 3D Coordinate Systems

**Dolby Atmos Coordinates:**
```
x: left (-1) to right (+1)
y: back (-1) to front (+1)  [Note: Some use opposite convention]
z: floor (0) to ceiling (+1)

Conversion from spherical:
  x = sin(azimuth) * cos(elevation)
  y = cos(azimuth) * cos(elevation)
  z = sin(elevation)
```

---

## 5. Dolby Atmos Music Specifications

### 5.1 7.1.4 Bed + Objects Workflow

**Bed Channels (12 fixed channels):**
| Channel | Position | Purpose |
|---------|----------|---------|
| L | Left front | Main stereo field |
| R | Right front | Main stereo field |
| C | Center | Dialogue, lead vocals |
| LFE | Subwoofer | Low frequency effects |
| Ls | Left surround | Ambient, width |
| Rs | Right surround | Ambient, width |
| Lrs | Left rear surround | Rear ambient |
| Rrs | Right rear surround | Rear ambient |
| Ltf | Left top front | Height layer |
| Rtf | Right top front | Height layer |
| Ltr | Left top rear | Height ambience |
| Rtr | Right top rear | Height ambience |

**Objects (up to 118 in cinema, 16 concurrent in home):**
- Dynamic position over time
- Spatial coding reduces to ~7 active object clusters
- Each object has: position (x,y,z), size, and audio content

### 5.2 ADM (Audio Definition Model) Metadata

**ITU-R BS.2076 Standard**

ADM is an XML-based metadata format embedded in BWF (Broadcast Wave Format) files.

**Key ADM Elements:**
```xml
<audioProgramme audioProgrammeID="APR_1001" audioProgrammeName="Main">
  <audioContentIDRef>ACO_1001</audioContentIDRef>
</audioProgramme>

<audioContent audioContentID="ACO_1001">
  <audioObjectIDRef>AO_1001</audioObjectIDRef>
</audioContent>

<audioObject audioObjectID="AO_1001" audioObjectName="Lead Vocal">
  <audioPackFormatIDRef>AP_00031001</audioPackFormatIDRef>
  <audioTrackUIDRef>ATU_00000001</audioTrackUIDRef>
</audioObject>

<audioBlockFormat audioBlockFormatID="AB_00031001_00000001">
  <position coordinate="azimuth">0.0</position>
  <position coordinate="elevation">0.0</position>
  <position coordinate="distance">1.0</position>
</audioBlockFormat>
```

**ADM Position Formats:**
- Spherical: azimuth, elevation, distance
- Cartesian: x, y, z

### 5.3 Renderer Requirements

**Dolby Atmos Renderer:**
- Proprietary software (Dolby Atmos Production Suite)
- Plugin for Pro Tools, Nuendo, Logic
- Renders object audio to speaker feeds in real-time

**What We Can Prepare Without Dolby Tools:**
1. ✅ ADM-BWF metadata structure (open standard)
2. ✅ 7.1.4 bed channel audio
3. ✅ Object position automation data
4. ✅ Binaural preview using HRTF
5. ❌ Official Dolby Atmos master file (.atmos)
6. ❌ Spatial coding/compression

### 5.4 Binaural Fold-Down

**Atmos-to-Headphone Rendering:**
```
For each speaker channel/object:
  1. Determine virtual position (azimuth, elevation)
  2. Look up or interpolate HRTF for that position
  3. Convolve audio with HRTF
  4. Sum all contributions to stereo output

Additional processing:
  - Room modeling (early reflections)
  - Head tracking compensation (if available)
  - Loudness normalization
```

**Binaural Rendering Quality Factors:**
- HRTF personalization (generic vs measured)
- Interpolation quality between HRTF positions
- Room simulation accuracy
- Head tracking latency

---

## 6. Python Data Schemas

### 6.1 Core Data Classes

```python
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List, Tuple
import numpy as np

class CoordinateSystem(Enum):
    SPHERICAL = "spherical"      # azimuth, elevation, distance
    CARTESIAN = "cartesian"      # x, y, z

class SpeakerLayout(Enum):
    STEREO = "2.0"
    SURROUND_51 = "5.1"
    SURROUND_71 = "7.1"
    ATMOS_514 = "5.1.4"
    ATMOS_714 = "7.1.4"
    ATMOS_91624 = "9.1.6+24obj"  # Dolby Atmos max

@dataclass
class SpatialPosition:
    """3D position for audio source or speaker."""
    
    # Cartesian coordinates (normalized -1 to 1, z: 0 to 1)
    x: float = 0.0              # left (-1) to right (+1)
    y: float = 0.0              # back (-1) to front (+1)
    z: float = 0.0              # floor (0) to ceiling (+1)
    
    # Spherical alternative
    azimuth: Optional[float] = None    # degrees, 0=front, CCW positive
    elevation: Optional[float] = None  # degrees, 0=ear level, up positive
    distance: float = 1.0              # normalized, 1.0 = reference
    
    coordinate_system: CoordinateSystem = CoordinateSystem.CARTESIAN
    
    def to_cartesian(self) -> Tuple[float, float, float]:
        """Convert to Cartesian coordinates."""
        if self.coordinate_system == CoordinateSystem.CARTESIAN:
            return (self.x, self.y, self.z)
        else:
            az_rad = np.radians(self.azimuth)
            el_rad = np.radians(self.elevation)
            x = np.sin(az_rad) * np.cos(el_rad) * self.distance
            y = np.cos(az_rad) * np.cos(el_rad) * self.distance
            z = np.sin(el_rad) * self.distance
            return (x, y, z)
    
    def to_spherical(self) -> Tuple[float, float, float]:
        """Convert to spherical coordinates."""
        if self.coordinate_system == CoordinateSystem.SPHERICAL:
            return (self.azimuth, self.elevation, self.distance)
        else:
            dist = np.sqrt(self.x**2 + self.y**2 + self.z**2)
            az = np.degrees(np.arctan2(self.x, self.y))
            el = np.degrees(np.arcsin(self.z / (dist + 1e-10)))
            return (az, el, dist)


@dataclass
class BinauralConfig:
    """Configuration for binaural rendering."""
    
    # HRTF settings
    hrtf_database_path: str = "assets/hrtf/kemar"
    hrtf_sample_rate: int = 44100
    hrtf_filter_length: int = 512
    use_diffuse_field_eq: bool = True
    
    # Interpolation
    interpolation_method: str = "bilinear"  # nearest, bilinear, spherical
    
    # Headphone compensation
    apply_headphone_eq: bool = False
    headphone_model: Optional[str] = None
    
    # Processing
    use_crossfade: bool = True
    crossfade_samples: int = 64
    
    # Head tracking
    enable_head_tracking: bool = False
    head_tracking_smoothing: float = 0.1
    
    def validate(self) -> bool:
        """Validate configuration."""
        if self.hrtf_filter_length not in [128, 256, 512, 1024]:
            return False
        if self.interpolation_method not in ["nearest", "bilinear", "spherical"]:
            return False
        return True


@dataclass
class SurroundConfig:
    """Configuration for surround sound rendering."""
    
    # Output layout
    speaker_layout: SpeakerLayout = SpeakerLayout.ATMOS_714
    
    # Speaker positions (can be customized from standard)
    speaker_positions: dict = field(default_factory=dict)
    
    # Upmixing parameters
    center_extraction_gain: float = 0.7
    surround_decorrelation: bool = True
    lfe_crossover_freq: float = 120.0
    
    # Height channel routing
    height_crossover_freq: float = 6000.0
    height_gain: float = 0.5
    
    # VBAP settings
    vbap_spread: float = 0.0        # 0 = point source, 1 = diffuse
    distance_attenuation: float = 1.0
    
    # Rendering
    render_binaural_preview: bool = True
    binaural_config: Optional[BinauralConfig] = None
    
    def __post_init__(self):
        if not self.speaker_positions:
            self.speaker_positions = self._get_default_positions()
    
    def _get_default_positions(self) -> dict:
        """Get default speaker positions for layout."""
        if self.speaker_layout == SpeakerLayout.ATMOS_714:
            return {
                'L':   SpatialPosition(azimuth=-30, elevation=0),
                'R':   SpatialPosition(azimuth=30, elevation=0),
                'C':   SpatialPosition(azimuth=0, elevation=0),
                'LFE': SpatialPosition(azimuth=0, elevation=-30),
                'Ls':  SpatialPosition(azimuth=-90, elevation=0),
                'Rs':  SpatialPosition(azimuth=90, elevation=0),
                'Lrs': SpatialPosition(azimuth=-135, elevation=0),
                'Rrs': SpatialPosition(azimuth=135, elevation=0),
                'Ltf': SpatialPosition(azimuth=-45, elevation=45),
                'Rtf': SpatialPosition(azimuth=45, elevation=45),
                'Ltr': SpatialPosition(azimuth=-135, elevation=45),
                'Rtr': SpatialPosition(azimuth=135, elevation=45),
            }
        # Add other layouts...
        return {}


@dataclass
class SpatialObject:
    """Audio object with position and movement."""
    
    object_id: str
    name: str
    
    # Position (current or keyframe at time 0)
    position: SpatialPosition = field(default_factory=SpatialPosition)
    
    # Object properties
    size: float = 0.0               # 0 = point source, 1 = fully diffuse
    divergence: float = 0.0         # Spatial spread
    gain: float = 1.0               # Linear gain
    
    # Automation (list of time, position pairs)
    position_automation: List[Tuple[float, SpatialPosition]] = field(default_factory=list)
    
    # Routing
    is_bed_channel: bool = False
    bed_channel_name: Optional[str] = None
    
    # Audio reference
    audio_track_id: Optional[int] = None
    
    def get_position_at_time(self, time_seconds: float) -> SpatialPosition:
        """Interpolate position at given time."""
        if not self.position_automation:
            return self.position
        
        # Find surrounding keyframes
        prev_kf = (0.0, self.position)
        next_kf = None
        
        for t, pos in self.position_automation:
            if t <= time_seconds:
                prev_kf = (t, pos)
            else:
                next_kf = (t, pos)
                break
        
        if next_kf is None:
            return prev_kf[1]
        
        # Linear interpolation
        t_ratio = (time_seconds - prev_kf[0]) / (next_kf[0] - prev_kf[0])
        px1, py1, pz1 = prev_kf[1].to_cartesian()
        px2, py2, pz2 = next_kf[1].to_cartesian()
        
        return SpatialPosition(
            x=px1 + t_ratio * (px2 - px1),
            y=py1 + t_ratio * (py2 - py1),
            z=pz1 + t_ratio * (pz1 - pz1),
        )


@dataclass
class AtmosSession:
    """Dolby Atmos session container."""
    
    name: str
    sample_rate: int = 48000
    bit_depth: int = 24
    
    # Configuration
    bed_layout: SpeakerLayout = SpeakerLayout.ATMOS_714
    max_objects: int = 118
    
    # Content
    bed_channels: dict = field(default_factory=dict)  # channel_name: audio_data
    objects: List[SpatialObject] = field(default_factory=list)
    
    # Metadata
    loudness_integrated: Optional[float] = None  # LUFS
    loudness_peak: Optional[float] = None        # dBTP
    
    # Binaural preview config
    binaural_config: BinauralConfig = field(default_factory=BinauralConfig)
    
    def add_object(self, obj: SpatialObject) -> bool:
        """Add spatial object to session."""
        if len(self.objects) >= self.max_objects:
            return False
        self.objects.append(obj)
        return True
    
    def export_adm_metadata(self) -> str:
        """Generate ADM XML metadata."""
        # Implementation would generate ITU-R BS.2076 compliant XML
        pass
```

---

## 7. Algorithm Specifications

### 7.1 VBAP Gain Calculation

```python
def calculate_vbap_gains(
    source_position: SpatialPosition,
    speaker_triplet: List[SpatialPosition],
    normalize_energy: bool = True
) -> List[float]:
    """
    Calculate VBAP gains for 3D panning.
    
    Algorithm:
    1. Convert all positions to unit vectors
    2. Build speaker matrix L = [l1, l2, l3]^T
    3. Compute gains: g = source_vector @ inv(L)
    4. Check all gains positive (source inside triangle)
    5. Normalize for energy preservation
    
    Parameters:
        source_position: Target position for virtual source
        speaker_triplet: Three speakers forming triangle
        normalize_energy: If True, normalize so sum of squares = 1
    
    Returns:
        List of three gain values [g1, g2, g3]
        Returns None if source outside triangle (negative gain)
    """
    # Specification only - implementation details:
    # - Use numpy for matrix operations
    # - Handle degenerate cases (speakers colinear)
    # - Clamp small negative values to 0 (numerical precision)
    pass


def select_speaker_triplet(
    source_position: SpatialPosition,
    all_triangles: List[List[int]],
    speaker_positions: List[SpatialPosition]
) -> Optional[int]:
    """
    Select appropriate speaker triangle for source position.
    
    Pre-requisite: Triangulate speaker positions using Delaunay
    triangulation on unit sphere.
    
    Algorithm:
    1. For each triangle:
       - Calculate VBAP gains
       - If all gains >= 0, source is inside this triangle
    2. Return first valid triangle index
    
    Note: For efficiency, use spatial indexing (octree, BVH)
    """
    pass
```

### 7.2 Binaural Rendering Pipeline

```python
def render_binaural(
    spatial_objects: List[Tuple[np.ndarray, SpatialPosition]],
    hrtf_database: 'HRTFDatabase',
    config: BinauralConfig,
    block_size: int = 512
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Render multiple spatial objects to binaural stereo.
    
    Algorithm (per block):
    1. For each object:
       a. Get object position (interpolate if animated)
       b. Look up/interpolate HRTF for position
       c. Convolve object audio with HRTF
       d. Apply distance attenuation
    2. Sum all object contributions
    3. Apply final limiting/normalization
    
    Optimization notes:
    - Use overlap-add FFT convolution
    - Cache HRTF interpolations for static sources
    - Process objects in parallel
    
    Parameters:
        spatial_objects: List of (audio_block, position) tuples
        hrtf_database: Loaded HRTF measurements
        config: Binaural rendering configuration
        block_size: Processing block size in samples
    
    Returns:
        (left_channel, right_channel) as numpy arrays
    """
    pass


def apply_distance_cues(
    audio: np.ndarray,
    distance: float,
    sample_rate: int,
    config: dict
) -> np.ndarray:
    """
    Apply distance-based processing.
    
    Effects:
    1. Level attenuation: gain = 1 / (1 + k * (d - 1))
    2. High-frequency rolloff: air absorption
    3. Wet/dry ratio increase: more reverb at distance
    
    Parameters:
        audio: Input audio
        distance: Normalized distance (1.0 = reference)
        sample_rate: Audio sample rate
        config: Distance processing parameters
    
    Returns:
        Processed audio with distance cues
    """
    pass
```

### 7.3 Stereo-to-7.1.4 Upmix

```python
def upmix_stereo_to_714(
    left: np.ndarray,
    right: np.ndarray,
    config: SurroundConfig
) -> dict:
    """
    Upmix stereo to 7.1.4 surround.
    
    Output channels:
    - L, R: Derived from input with center reduction
    - C: Center extraction (L+R correlation)
    - LFE: Low-pass filtered center
    - Ls, Rs: Decorrelated side signal
    - Lrs, Rrs: Further decorrelated/delayed
    - Ltf, Rtf, Ltr, Rtr: High-frequency + ambient
    
    Algorithm:
    1. Extract center: C = (L + R) * 0.5 * center_gain
    2. Extract side: S = L - R
    3. Derive surrounds from decorrelated side
    4. Extract heights from high-frequency content
    5. Apply crossover and level balancing
    
    Parameters:
        left: Left channel input
        right: Right channel input
        config: Surround configuration
    
    Returns:
        Dictionary mapping channel names to audio arrays
    """
    pass
```

---

## 8. Implementation Notes

### 8.1 Without Dolby Tools

**What We Can Build:**
1. **HRTF-based binaural renderer** - Fully implementable
2. **VBAP panner** - Open algorithm, fully implementable
3. **Stereo upmixer** - Basic matrix math, implementable
4. **ADM metadata generator** - Open ITU standard
5. **7.1.4 bed renderer** - Standard channel routing

**What Requires Dolby:**
1. Official `.atmos` master files
2. Dolby Atmos spatial coding compression
3. Certification for streaming platforms
4. Cinema distribution formats

### 8.2 HRTF Resources

| Dataset | Source | License | Notes |
|---------|--------|---------|-------|
| MIT KEMAR | MIT Media Lab | Free (cite) | Most widely used |
| CIPIC | UC Davis | Academic | 45 subjects |
| LISTEN | IRCAM | Free | Higher resolution |
| SADIE II | York University | CC-BY | Modern, validated |
| SOFA format | AES69-2015 | Standard | Universal container |

### 8.3 Recommended Libraries

```
- scipy.signal: Convolution, filtering
- numpy: Array operations, FFT
- soundfile: Audio I/O
- librosa: Audio analysis
- pysofaconventions: SOFA file handling
- python-sounddevice: Real-time audio
```

### 8.4 Testing Considerations

1. **Reference Tracks**: Use commercial Atmos releases for A/B comparison
2. **HRTF Validation**: Test with known spatial positions
3. **Loudness**: Verify -14 to -16 LUFS for streaming
4. **Phase Coherence**: Check for comb filtering artifacts
5. **Mono Compatibility**: Fold-down should not cause cancellation

---

## References

1. ITU-R BS.2076-2: Audio Definition Model
2. Pulkki, V. "Virtual Sound Source Positioning Using VBAP" (1997)
3. MIT Media Lab KEMAR HRTF Database Documentation
4. Dolby Atmos Music Creation Guide (professional.dolby.com)
5. AES69-2015: SOFA (Spatially Oriented Format for Acoustics)
6. Gerzon, M.A. "Periphony: With-Height Sound Reproduction" (1973)
7. Blauert, J. "Spatial Hearing" (MIT Press)
8. EBU Tech 3364: Audio Definition Model Guidelines

---

*This research document provides specifications for spatial audio preparation. Implementation should follow these algorithms and data structures while adapting to the specific needs of the multimodal-ai-music-gen project.*
