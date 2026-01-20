# Multiband Dynamics Processing Research Report

## Executive Summary

This document presents comprehensive research on professional multiband dynamics processing techniques, including crossover filter design, per-band compression algorithms, and Python DSP implementation approaches. The findings will inform enhancements to the existing `multiband_dynamics.py` module.

---

## 1. Professional Multiband Compressor Architecture

### 1.1 Signal Flow Overview

Professional multiband compressors follow a consistent architecture:

```
                    ┌──────────────────────────────────────────────────────┐
                    │           MULTIBAND DYNAMICS PROCESSOR               │
                    │                                                      │
  Input ──────────▶ │  ┌─────────────┐    ┌──────────────────┐           │
                    │  │  Crossover  │    │  Band Processors  │           │
                    │  │   Network   │───▶│  (Comp/Exp/etc)  │           │
                    │  └─────────────┘    └──────────────────┘           │
                    │         │                    │                      │
                    │         ▼                    ▼                      │
                    │  ┌─────────────┐    ┌──────────────────┐           │
                    │  │  Lookahead  │    │   Band Summing   │──────────▶│ Output
                    │  │   Buffer    │    │  (Reconstruction) │           │
                    │  └─────────────┘    └──────────────────┘           │
                    └──────────────────────────────────────────────────────┘
```

### 1.2 Core Components

| Component | Purpose | Implementation Notes |
|-----------|---------|---------------------|
| **Crossover Filters** | Split audio into frequency bands | LR4/LR8 most common |
| **Sidechain Detection** | Analyze signal level per band | Peak, RMS, or hybrid |
| **Gain Computer** | Calculate gain reduction | Threshold, ratio, knee |
| **Envelope Follower** | Smooth gain changes | Attack/release timing |
| **Lookahead Buffer** | Preserve transients | 1-10ms typical |
| **Band Reconstruction** | Sum processed bands | Phase-coherent summing |

### 1.3 Professional Tools Reference

| Tool | Crossover Type | Bands | Key Features |
|------|---------------|-------|--------------|
| **FabFilter Pro-MB** | Linear Phase / Min Phase | 6 | Mid/Side, dynamic range |
| **Waves Linear Phase MB** | Linear Phase FIR | 5 | Zero phase shift |
| **iZotope Ozone Dynamics** | Hybrid | 4 | Adaptive release |
| **Sonnox Oxford Dynamics** | IIR Linkwitz-Riley | 5 | Learn function |
| **TC Electronic Finalizer** | LR4 | 3 | Legacy mastering standard |

---

## 2. Crossover Filter Design

### 2.1 Filter Types Comparison

#### 2.1.1 Linkwitz-Riley (LR) Crossovers

**Definition**: Linkwitz-Riley filters are constructed by cascading two Butterworth filters of the same order. The result is a crossover with -6dB at the crossover frequency, ensuring flat summed magnitude response.

**Key Properties**:
- **LR2 (12dB/octave)**: Two cascaded 1st-order Butterworth
- **LR4 (24dB/octave)**: Two cascaded 2nd-order Butterworth - **Industry Standard**
- **LR8 (48dB/octave)**: Two cascaded 4th-order Butterworth

**Advantages**:
- Flat magnitude response when bands are summed
- In-phase outputs (0° or 360° phase difference)
- Clean reconstruction without bumps at crossover

**Mathematical Definition (LR4)**:
```
H_LP(s) = H_Butter(s)² = [1 / (s² + √2·s + 1)]²
H_HP(s) = H_Butter(s)² = [s² / (s² + √2·s + 1)]²
```

#### 2.1.2 Butterworth Crossovers

**Definition**: Maximally flat magnitude response in the passband.

**Key Properties**:
- -3dB at crossover frequency
- Summed output has +3dB bump at crossover
- 90° phase shift per order

**Use Case**: Less ideal for multiband processing due to summing bump.

#### 2.1.3 Bessel Crossovers

**Definition**: Optimized for linear phase response (constant group delay).

**Key Properties**:
- Best transient response
- Non-flat magnitude at crossover
- Gentler slopes than Butterworth

**Use Case**: Applications where phase linearity is critical.

### 2.2 Linear-Phase vs Minimum-Phase Crossovers

| Characteristic | Linear Phase (FIR) | Minimum Phase (IIR) |
|---------------|-------------------|---------------------|
| **Phase Response** | Zero phase shift | Frequency-dependent phase |
| **Latency** | Higher (filter order/2) | Lower |
| **CPU Usage** | Higher | Lower |
| **Pre-ringing** | Yes (symmetric ringing) | No |
| **Transient Preservation** | Can smear transients | Better transient attack |
| **Filter Order** | Typically 256-4096 taps | 2-8 poles |

#### 2.2.1 Linear Phase FIR Implementation

```python
def design_linear_phase_crossover(cutoff_hz, sample_rate, order=512):
    """
    Design linear-phase FIR crossover filters.
    
    Uses windowed-sinc method with Kaiser window for
    sharp transition and good stopband rejection.
    """
    from scipy.signal import firwin, freqz
    import numpy as np
    
    nyquist = sample_rate / 2
    normalized_cutoff = cutoff_hz / nyquist
    
    # Design lowpass prototype
    # Even order ensures symmetric impulse response
    lowpass = firwin(order + 1, normalized_cutoff, window='kaiser', pass_zero='lowpass')
    
    # Highpass is complementary: HP = δ[n] - LP
    # For linear phase, create spectral inverse
    highpass = -lowpass.copy()
    highpass[order // 2] += 1.0  # Add impulse at center
    
    return lowpass, highpass
```

#### 2.2.2 Minimum Phase IIR Implementation (Current Approach)

```python
def design_lr4_crossover(cutoff_hz, sample_rate):
    """
    Design Linkwitz-Riley 4th order (LR4) crossover.
    
    LR4 = Two cascaded 2nd-order Butterworth filters.
    """
    from scipy.signal import butter
    
    nyquist = sample_rate / 2
    normalized = cutoff_hz / nyquist
    
    # Single 2nd-order Butterworth
    sos_lp = butter(2, normalized, btype='low', output='sos')
    sos_hp = butter(2, normalized, btype='high', output='sos')
    
    # For LR4, cascade twice (apply filter twice)
    # Or use 4th-order Butterworth squared design
    return sos_lp, sos_hp
```

### 2.3 Crossover Frequency Selection Guidelines

| Band | Frequency Range | Typical Crossover | Musical Content |
|------|----------------|-------------------|-----------------|
| Sub | 20-80 Hz | 60-100 Hz | Sub bass, kick fundamental |
| Bass | 80-300 Hz | 200-400 Hz | Bass body, kick/snare punch |
| Low Mid | 300-2 kHz | 1-2 kHz | Warmth, vocal body |
| High Mid | 2-8 kHz | 4-6 kHz | Presence, attack |
| High | 8-20 kHz | 8-12 kHz | Air, brilliance |

---

## 3. Per-Band Dynamics Processing

### 3.1 Compression Algorithm Components

#### 3.1.1 Gain Computer (Static Curve)

The gain computer calculates the desired gain reduction based on input level:

```python
def compute_gain_reduction(input_db, threshold_db, ratio, knee_db=6.0):
    """
    Compute static compression curve with soft knee.
    
    Soft knee provides gradual transition into compression.
    """
    knee_half = knee_db / 2.0
    knee_start = threshold_db - knee_half
    knee_end = threshold_db + knee_half
    
    if input_db < knee_start:
        # Below knee - no compression
        return 0.0
    elif input_db > knee_end:
        # Above knee - full compression
        over_db = input_db - threshold_db
        return over_db * (1.0 - 1.0 / ratio)
    else:
        # In knee region - quadratic interpolation
        knee_factor = (input_db - knee_start) / knee_db
        knee_factor = knee_factor ** 2  # Quadratic
        over_db = input_db - threshold_db
        return knee_factor * over_db * (1.0 - 1.0 / ratio)
```

#### 3.1.2 Envelope Follower (Dynamics)

Two primary approaches for level detection:

**Peak Detection** (faster, catches transients):
```python
def peak_envelope(signal, attack_coeff, release_coeff):
    envelope = np.zeros(len(signal))
    state = 0.0
    
    for i, sample in enumerate(np.abs(signal)):
        if sample > state:
            state = attack_coeff * state + (1 - attack_coeff) * sample
        else:
            state = release_coeff * state + (1 - release_coeff) * sample
        envelope[i] = state
    
    return envelope
```

**RMS Detection** (smoother, relates to perceived loudness):
```python
def rms_envelope(signal, window_ms, sample_rate):
    window_samples = int(window_ms * sample_rate / 1000)
    squared = signal ** 2
    
    # Moving average of squared signal
    from scipy.ndimage import uniform_filter1d
    mean_squared = uniform_filter1d(squared, window_samples, mode='nearest')
    
    return np.sqrt(mean_squared)
```

#### 3.1.3 Attack/Release Time Constants

Convert time constants to filter coefficients:

```python
def time_to_coeff(time_ms, sample_rate):
    """
    Calculate one-pole filter coefficient from time constant.
    
    The coefficient determines how quickly the envelope
    reaches 63.2% of its target value.
    """
    if time_ms <= 0:
        return 0.0
    time_samples = time_ms * sample_rate / 1000.0
    return np.exp(-1.0 / time_samples)
```

**Recommended Time Constants by Band**:

| Band | Attack (ms) | Release (ms) | Rationale |
|------|------------|--------------|-----------|
| Sub (< 100 Hz) | 30-100 | 200-500 | Slow to preserve low-frequency content |
| Bass (100-300 Hz) | 15-50 | 100-300 | Medium, avoid pumping |
| Low Mid (300-2k Hz) | 5-30 | 50-200 | Standard vocal/instrument response |
| High Mid (2-8k Hz) | 1-15 | 30-100 | Fast for transient control |
| High (> 8 kHz) | 0.5-10 | 20-80 | Very fast for cymbals/air |

### 3.2 Advanced Compression Features

#### 3.2.1 Lookahead Processing

Lookahead allows the compressor to "see" transients before they arrive:

```python
def apply_lookahead(audio, gain_reduction, lookahead_samples):
    """
    Apply lookahead by delaying audio relative to gain reduction.
    
    This preserves transient attacks while still controlling peaks.
    """
    # Delay the audio path
    audio_delayed = np.concatenate([
        np.zeros(lookahead_samples),
        audio[:-lookahead_samples]
    ])
    
    # Gain reduction is applied immediately
    return audio_delayed * gain_reduction
```

#### 3.2.2 Linked vs Independent Bands

**Independent** (default): Each band has its own compression behavior.

**Linked**: Gain reduction is synchronized across bands to preserve spectral balance:

```python
def link_band_gain_reduction(band_gr_list):
    """
    Link gain reduction across all bands using maximum GR.
    
    Maintains spectral balance but may over-compress some bands.
    """
    # Stack and find maximum at each sample
    gr_stack = np.stack(band_gr_list, axis=0)
    max_gr = np.max(gr_stack, axis=0)
    return max_gr
```

#### 3.2.3 Program-Dependent Release

Adaptive release that responds to signal characteristics:

```python
def adaptive_release(gr_history, base_release_ms, sample_rate):
    """
    Adjust release time based on recent compression activity.
    
    More compression = longer release (avoid pumping)
    Less compression = shorter release (faster recovery)
    """
    avg_gr = np.mean(gr_history[-1000:])  # Last ~23ms at 44.1kHz
    
    # Scale release: heavier compression = slower release
    release_multiplier = 1.0 + (avg_gr / 10.0)  # 0-10dB GR → 1x-2x
    return base_release_ms * release_multiplier
```

### 3.3 Expansion (Downward)

Expansion reduces signals below a threshold, useful for noise reduction:

```python
def compute_expansion(input_db, threshold_db, ratio):
    """
    Downward expansion: signals below threshold are attenuated.
    
    Ratio of 2:1 means 2dB below threshold → 1dB output below threshold.
    """
    if input_db >= threshold_db:
        return 0.0
    
    under_db = threshold_db - input_db
    expansion_db = under_db * (ratio - 1.0)
    return expansion_db  # Positive = attenuation
```

---

## 4. Python DSP Libraries for Multiband Processing

### 4.1 Core Libraries

#### 4.1.1 SciPy Signal Processing

**Key Functions for Crossover Design**:

```python
from scipy.signal import (
    butter,      # Butterworth filter design
    bessel,      # Bessel filter design
    cheby1,      # Chebyshev Type I
    ellip,       # Elliptic (Cauer) filter
    firwin,      # FIR filter design (windowed-sinc)
    remez,       # Parks-McClellan optimal FIR
    sosfilt,     # SOS (biquad) filtering
    sosfiltfilt, # Zero-phase SOS filtering
    lfilter,     # General IIR filtering
    filtfilt,    # Zero-phase IIR filtering
    freqz,       # Frequency response
    tf2sos,      # Transfer function to SOS
)
```

**Example: Complete LR4 Crossover**:

```python
from scipy.signal import butter, sosfilt
import numpy as np

class LinkwitzRileyCrossover:
    def __init__(self, freqs, sample_rate):
        self.freqs = freqs
        self.sr = sample_rate
        self.filters = self._design_filters()
    
    def _design_filters(self):
        filters = []
        nyquist = self.sr / 2
        
        for freq in self.freqs:
            norm_freq = np.clip(freq / nyquist, 0.001, 0.999)
            
            # 2nd order Butterworth for LR4
            sos_lp = butter(2, norm_freq, 'low', output='sos')
            sos_hp = butter(2, norm_freq, 'high', output='sos')
            
            filters.append({'lp': sos_lp, 'hp': sos_hp})
        
        return filters
    
    def split(self, audio):
        """Split audio into frequency bands."""
        bands = []
        remaining = audio.copy()
        
        for filt in self.filters:
            # LR4 = apply twice
            low = sosfilt(filt['lp'], remaining)
            low = sosfilt(filt['lp'], low)
            
            remaining = sosfilt(filt['hp'], remaining)
            remaining = sosfilt(filt['hp'], remaining)
            
            bands.append(low)
        
        bands.append(remaining)  # Highest band
        return bands
    
    def reconstruct(self, bands):
        """Sum bands back together."""
        return sum(bands)
```

#### 4.1.2 NumPy for Vectorized Operations

```python
import numpy as np

# Efficient envelope follower using NumPy
def vectorized_envelope(signal, attack_samples, release_samples):
    """
    Vectorized envelope follower using exponential smoothing.
    
    Note: True attack/release requires sample-by-sample processing,
    but this approximation is efficient for many applications.
    """
    from scipy.ndimage import maximum_filter1d, uniform_filter1d
    
    # Peak detection with smoothing
    peaks = maximum_filter1d(np.abs(signal), size=attack_samples)
    smoothed = uniform_filter1d(peaks, size=release_samples)
    
    return smoothed
```

#### 4.1.3 Librosa for Audio Analysis

```python
import librosa

# Useful for frequency analysis before compression
def analyze_spectral_content(audio, sr):
    """Analyze frequency content for intelligent crossover placement."""
    
    # Mel spectrogram for perceptual frequency analysis
    mel = librosa.feature.melspectrogram(y=audio, sr=sr)
    
    # Find dominant frequencies
    spectral_centroid = librosa.feature.spectral_centroid(y=audio, sr=sr)
    
    # Detect transients
    onset_strength = librosa.onset.onset_strength(y=audio, sr=sr)
    
    return mel, spectral_centroid, onset_strength
```

### 4.2 Performance Optimization

#### 4.2.1 Numba JIT Compilation

```python
from numba import jit
import numpy as np

@jit(nopython=True)
def fast_envelope_follower(signal, attack_coeff, release_coeff):
    """
    JIT-compiled envelope follower for real-time performance.
    
    ~10-50x faster than pure Python.
    """
    n = len(signal)
    envelope = np.zeros(n)
    state = 0.0
    
    for i in range(n):
        rect = abs(signal[i])
        if rect > state:
            state = attack_coeff * state + (1.0 - attack_coeff) * rect
        else:
            state = release_coeff * state + (1.0 - release_coeff) * rect
        envelope[i] = state
    
    return envelope

@jit(nopython=True)
def fast_gain_computer(levels_db, threshold, ratio, knee_width):
    """
    JIT-compiled gain computation for entire buffer.
    """
    n = len(levels_db)
    gain_reduction = np.zeros(n)
    knee_half = knee_width / 2.0
    knee_start = threshold - knee_half
    knee_end = threshold + knee_half
    
    for i in range(n):
        level = levels_db[i]
        
        if level < knee_start:
            gain_reduction[i] = 0.0
        elif level > knee_end:
            over = level - threshold
            gain_reduction[i] = over * (1.0 - 1.0 / ratio)
        else:
            factor = (level - knee_start) / knee_width
            factor = factor * factor
            over = level - threshold
            gain_reduction[i] = factor * over * (1.0 - 1.0 / ratio)
    
    return gain_reduction
```

#### 4.2.2 Parallel Processing with Joblib

```python
from joblib import Parallel, delayed

def process_bands_parallel(bands, band_params, sample_rate):
    """
    Process multiple bands in parallel using joblib.
    
    Useful for systems with many CPU cores.
    """
    def process_single_band(band, params, sr):
        compressor = BandCompressor(params, sr)
        return compressor.process(band)
    
    results = Parallel(n_jobs=-1)(
        delayed(process_single_band)(band, params, sample_rate)
        for band, params in zip(bands, band_params)
    )
    
    return results
```

### 4.3 Advanced Libraries

| Library | Use Case | Key Features |
|---------|----------|--------------|
| **pedalboard** (Spotify) | Real-time audio effects | GPU acceleration, VST support |
| **pyo** | Real-time DSP | C-based, very fast |
| **JUCE** (via cppyy) | Professional audio | Industry-standard DSP |
| **essentia** | Audio analysis | Feature extraction |

---

## 5. Integration with Existing mix_chain.py

### 5.1 Current Architecture Analysis

The existing `multiband_dynamics.py` already implements:

✅ **Linkwitz-Riley 4th Order Crossovers** - Industry standard  
✅ **Per-band Compression with Soft Knee**  
✅ **Attack/Release Envelope Following**  
✅ **Downward Expansion**  
✅ **Lookahead Buffer**  
✅ **Band Linking Option**  
✅ **Per-band Saturation**  
✅ **Comprehensive Presets**  

### 5.2 Recommended Enhancements

Based on this research, the following enhancements are recommended:

#### 5.2.1 Add Linear-Phase Crossover Option

```python
class MultibandDynamicsParams:
    # ... existing params ...
    crossover_type: str = 'linkwitz-riley'  # or 'linear-phase'
    linear_phase_order: int = 512  # FIR filter order
```

#### 5.2.2 Add RMS Detection Mode

```python
class BandParams:
    # ... existing params ...
    detection_mode: str = 'peak'  # or 'rms'
    rms_window_ms: float = 10.0
```

#### 5.2.3 Add Program-Dependent Release

```python
class BandParams:
    # ... existing params ...
    auto_release: bool = False
    auto_release_sensitivity: float = 1.0
```

#### 5.2.4 Add Mid/Side Processing Option

```python
class MultibandDynamicsParams:
    # ... existing params ...
    processing_mode: str = 'stereo'  # or 'mid-side'
```

### 5.3 Integration with MixChain

Add multiband dynamics as a first-class effect in `mix_chain.py`:

```python
# In mix_chain.py

class EffectType(Enum):
    # ... existing ...
    MULTIBAND_DYNAMICS = "multiband_dynamics"

@dataclass  
class MultibandDynamicsEffectParams(EffectParams):
    preset: str = "mastering_glue"
    custom_params: Optional[MultibandDynamicsParams] = None

class DSP:
    @staticmethod
    def multiband_dynamics(audio, params, sample_rate):
        from .multiband_dynamics import (
            MultibandDynamics, 
            MULTIBAND_PRESETS,
            MultibandDynamicsParams
        )
        
        if params.custom_params:
            mb_params = params.custom_params
        elif params.preset in MULTIBAND_PRESETS:
            mb_params = MULTIBAND_PRESETS[params.preset]
        else:
            mb_params = MultibandDynamicsParams()
        
        processor = MultibandDynamics(mb_params, sample_rate)
        return processor.process(audio)
```

---

## 6. Best Practices Summary

### 6.1 Crossover Design

1. **Use LR4 (24dB/oct)** for most applications - industry standard
2. **Use Linear Phase** only when phase coherence is critical and latency is acceptable
3. **Avoid crossover frequencies** near 100Hz, 1kHz, 3kHz (sensitive regions)
4. **Keep minimum 1 octave** between adjacent crossover frequencies

### 6.2 Per-Band Settings

1. **Low bands**: Slow attack (30-50ms), slow release (200-400ms)
2. **High bands**: Fast attack (1-10ms), fast release (30-100ms)
3. **Use soft knee** (4-6dB) for transparent compression
4. **Gentle ratios** (2:1 to 4:1) for mastering, higher for mixing

### 6.3 General Guidelines

1. **Start with presets**, then fine-tune
2. **Use metering** to monitor per-band gain reduction
3. **A/B compare** frequently with bypass
4. **Target 2-4dB** average gain reduction for mastering
5. **Check mono compatibility** after multiband processing

---

## 7. References

1. Linkwitz, S. (1976). "Active Crossover Networks for Noncoincident Drivers". JAES.
2. Bohn, D. (2005). "Linkwitz-Riley Crossovers: A Primer". Rane Corporation.
3. Giannoulis, D. et al. (2012). "Digital Dynamic Range Compressor Design". JAES.
4. Wikipedia: Linkwitz-Riley Filter, Dynamic Range Compression, Audio Crossover
5. SciPy Documentation: scipy.signal module
6. Librosa Documentation: Audio feature extraction

---

## 8. Appendix: Python Code Templates

### A.1 Complete Linear-Phase Multiband Crossover

```python
import numpy as np
from scipy.signal import firwin, fftconvolve

class LinearPhaseCrossover:
    """
    Linear-phase FIR crossover for phase-coherent band splitting.
    
    Advantages:
    - Zero phase distortion
    - Perfect reconstruction when bands summed
    
    Disadvantages:
    - Higher latency (order/2 samples)
    - More CPU intensive
    - Pre-ringing on transients
    """
    
    def __init__(self, crossover_freqs, sample_rate, order=512):
        self.freqs = list(crossover_freqs)
        self.sr = sample_rate
        self.order = order
        self.num_bands = len(self.freqs) + 1
        self.latency = order // 2
        self.filters = self._design_filters()
    
    def _design_filters(self):
        """Design complementary FIR bandpass filters."""
        nyquist = self.sr / 2
        filters = []
        
        # Add boundaries
        band_edges = [0] + self.freqs + [nyquist * 0.99]
        
        for i in range(self.num_bands):
            low = band_edges[i] / nyquist
            high = band_edges[i + 1] / nyquist
            
            if i == 0:
                # Lowpass for first band
                fir = firwin(self.order + 1, high, window='kaiser')
            elif i == self.num_bands - 1:
                # Highpass for last band
                fir = firwin(self.order + 1, low, pass_zero=False, window='kaiser')
            else:
                # Bandpass for middle bands
                fir = firwin(self.order + 1, [low, high], pass_zero=False, window='kaiser')
            
            filters.append(fir)
        
        return filters
    
    def split(self, audio):
        """Split audio into frequency bands using linear-phase filters."""
        bands = []
        
        for fir in self.filters:
            # FFT convolution is faster for long filters
            filtered = fftconvolve(audio, fir, mode='same')
            bands.append(filtered)
        
        return bands
    
    def reconstruct(self, bands):
        """Sum bands - should perfectly reconstruct original."""
        return sum(bands)
```

### A.2 High-Performance Band Compressor with Numba

```python
import numpy as np
from numba import jit, prange

@jit(nopython=True, parallel=True)
def process_multiband_fast(bands, thresholds, ratios, attacks, releases, 
                           makeups, sample_rate):
    """
    Process multiple bands in parallel using Numba.
    
    This is significantly faster than the pure Python implementation.
    """
    num_bands = len(bands)
    processed = []
    
    for b in prange(num_bands):
        band = bands[b]
        threshold = thresholds[b]
        ratio = ratios[b]
        attack_coeff = np.exp(-1.0 / (attacks[b] * sample_rate / 1000.0))
        release_coeff = np.exp(-1.0 / (releases[b] * sample_rate / 1000.0))
        makeup = 10.0 ** (makeups[b] / 20.0)
        
        n = len(band)
        output = np.zeros(n)
        env_state = 0.0
        
        for i in range(n):
            # Envelope follower
            rect = abs(band[i])
            if rect > env_state:
                env_state = attack_coeff * env_state + (1.0 - attack_coeff) * rect
            else:
                env_state = release_coeff * env_state + (1.0 - release_coeff) * rect
            
            # Gain computer
            level_db = 20.0 * np.log10(env_state + 1e-10)
            
            if level_db > threshold:
                over_db = level_db - threshold
                gr_db = over_db * (1.0 - 1.0 / ratio)
                gain = 10.0 ** (-gr_db / 20.0)
            else:
                gain = 1.0
            
            output[i] = band[i] * gain * makeup
        
        processed.append(output)
    
    return processed
```

---

*Document Version: 1.0*  
*Research Date: January 2026*  
*Author: Multimodal AI Music Generator Research Agent*
