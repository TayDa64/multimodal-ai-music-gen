"""
Reference Analyzer - Analyze YouTube/audio references to guide music generation

This module extracts musical characteristics from reference tracks:
- BPM detection (tempo)
- Key/mode detection (harmonic content)
- Drum pattern analysis (rhythm density, swing)
- Spectral profile (brightness, sub-bass presence)
- Groove characteristics (swing amount, feel)

Usage:
    analyzer = ReferenceAnalyzer()
    analysis = analyzer.analyze_url("https://youtube.com/watch?v=...")
    # Use analysis to inform generation parameters
"""

import os
import re
import tempfile
import subprocess
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any
from enum import Enum
import json

import numpy as np

# Lazy imports for optional dependencies
_librosa = None
_yt_dlp = None


def _get_librosa():
    """Lazy load librosa for audio analysis."""
    global _librosa
    if _librosa is None:
        try:
            import librosa
            _librosa = librosa
        except ImportError:
            raise ImportError(
                "librosa is required for reference analysis. "
                "Install with: pip install librosa"
            )
    return _librosa


def _get_yt_dlp():
    """Lazy load yt-dlp for video download."""
    global _yt_dlp
    if _yt_dlp is None:
        try:
            import yt_dlp
            _yt_dlp = yt_dlp
        except ImportError:
            raise ImportError(
                "yt-dlp is required for YouTube analysis. "
                "Install with: pip install yt-dlp"
            )
    return _yt_dlp


class GrooveFeel(Enum):
    """Groove feel classification."""
    STRAIGHT = "straight"
    LIGHT_SWING = "light_swing"
    MEDIUM_SWING = "medium_swing"
    HEAVY_SWING = "heavy_swing"
    TRIPLET = "triplet"
    SHUFFLE = "shuffle"


@dataclass
class DrumAnalysis:
    """Analysis of drum/percussion characteristics."""
    density: float  # 0.0-1.0, how busy the drums are
    kick_pattern: List[float]  # Normalized kick positions in a bar
    snare_pattern: List[float]  # Normalized snare positions
    hihat_density: float  # Hi-hat activity level
    has_rolls: bool  # Detected hi-hat/snare rolls
    four_on_floor: bool  # House-style kick pattern
    trap_hihats: bool  # Rapid hi-hat patterns typical of trap
    boom_bap_feel: bool  # Classic hip-hop swing feel
    compound_meter: bool = False  # 6/8, 12/8 feel (Ethiopian, Afrobeat)


@dataclass
class SpectralProfile:
    """Spectral characteristics of the audio."""
    brightness: float  # 0.0-1.0, spectral centroid normalized
    warmth: float  # 0.0-1.0, low-mid presence
    sub_bass_presence: float  # 0.0-1.0, 20-80Hz energy
    has_808: bool  # Detected 808-style sub-bass
    lofi_character: float  # 0.0-1.0, lo-fi aesthetic markers
    clarity: float  # 0.0-1.0, high frequency detail
    pentatonic: bool = False  # Pentatonic scale detected (Ethiopian, Asian)


@dataclass
class GrooveAnalysis:
    """Groove and timing characteristics."""
    swing_amount: float  # 0.0-1.0, amount of swing
    groove_feel: GrooveFeel
    pulse_strength: float  # How strong the rhythmic pulse is
    micro_timing_variance: float  # Human feel / looseness
    downbeat_emphasis: float  # Emphasis on beat 1


@dataclass 
class ReferenceAnalysis:
    """Complete analysis of a reference track."""
    # Source info
    source_url: str
    title: str = ""
    duration_seconds: float = 0.0
    
    # Core musical parameters
    bpm: float = 120.0
    bpm_confidence: float = 0.0
    key: str = "C"
    mode: str = "minor"  # "major" or "minor"
    key_confidence: float = 0.0
    time_signature: Tuple[int, int] = (4, 4)
    
    # Detailed analysis
    drums: Optional[DrumAnalysis] = None
    spectral: Optional[SpectralProfile] = None
    groove: Optional[GrooveAnalysis] = None
    
    # Genre estimation
    estimated_genre: str = "hip_hop"
    genre_confidence: float = 0.0
    
    # Style tags extracted from analysis
    style_tags: List[str] = field(default_factory=list)
    
    # Raw features for advanced use
    raw_features: Dict[str, Any] = field(default_factory=dict)
    
    def to_prompt_hints(self) -> str:
        """Convert analysis to natural language hints for prompt enhancement."""
        hints = []
        
        # BPM
        hints.append(f"at {self.bpm:.0f} BPM")
        
        # Key
        hints.append(f"in {self.key} {self.mode}")
        
        # Genre
        if self.estimated_genre:
            hints.append(f"{self.estimated_genre.replace('_', ' ')} style")
        
        # Groove
        if self.groove:
            if self.groove.swing_amount > 0.3:
                hints.append("with swing")
            if self.groove.groove_feel == GrooveFeel.SHUFFLE:
                hints.append("shuffle feel")
        
        # Spectral characteristics
        if self.spectral:
            if self.spectral.has_808:
                hints.append("with 808 bass")
            if self.spectral.lofi_character > 0.5:
                hints.append("lo-fi character")
            if self.spectral.brightness < 0.3:
                hints.append("warm/mellow tone")
            elif self.spectral.brightness > 0.7:
                hints.append("bright/crisp tone")
        
        # Drums
        if self.drums:
            if self.drums.trap_hihats:
                hints.append("trap hi-hat patterns")
            if self.drums.four_on_floor:
                hints.append("four-on-floor kick")
            if self.drums.boom_bap_feel:
                hints.append("boom bap drums")
        
        # Style tags
        if self.style_tags:
            hints.extend(self.style_tags[:3])  # Top 3 tags
        
        return ", ".join(hints)
    
    def to_generation_params(self) -> Dict[str, Any]:
        """Convert analysis to generation parameters."""
        params = {
            "bpm": self.bpm,
            "key": self.key,
            "mode": self.mode,
            "time_signature": self.time_signature,
            "genre": self.estimated_genre,
        }
        
        if self.groove:
            params["swing"] = self.groove.swing_amount
            params["humanize"] = self.groove.micro_timing_variance
        
        if self.spectral:
            params["has_808"] = self.spectral.has_808
            params["brightness"] = self.spectral.brightness
            params["lofi"] = self.spectral.lofi_character > 0.5
        
        if self.drums:
            params["drum_density"] = self.drums.density
            params["trap_hihats"] = self.drums.trap_hihats
        
        return params


class ReferenceAnalyzer:
    """Analyzes reference tracks to extract musical characteristics."""
    
    # Key mappings for chroma analysis
    KEY_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
    
    # Genre detection heuristics
    GENRE_PROFILES = {
        "trap": {
            "bpm_range": (130, 170),
            "has_808": True,
            "trap_hihats": True,
            "brightness": (0.3, 0.7),
        },
        "lofi": {
            "bpm_range": (60, 95),
            "brightness": (0.1, 0.4),
            "lofi_character": 0.5,
            "swing": 0.2,
        },
        "boom_bap": {
            "bpm_range": (80, 100),
            "boom_bap_feel": True,
            "swing": 0.15,
        },
        "house": {
            "bpm_range": (118, 132),
            "four_on_floor": True,
            "brightness": (0.5, 0.8),
        },
        "trap_soul": {
            "bpm_range": (60, 95),
            "has_808": True,
            "brightness": (0.2, 0.5),
        },
        # Ethiopian music genres
        "ethiopian": {
            "bpm_range": (90, 130),
            "brightness": (0.4, 0.7),
            "compound_meter": True,
            "pentatonic": True,
        },
        "ethio_jazz": {
            "bpm_range": (85, 120),
            "brightness": (0.5, 0.8),
            "swing": 0.2,
            "compound_meter": True,
            "pentatonic": True,
        },
        "ethiopian_traditional": {
            "bpm_range": (80, 120),
            "brightness": (0.3, 0.6),
            "compound_meter": True,
            "pentatonic": True,
        },
        "eskista": {
            "bpm_range": (110, 145),
            "brightness": (0.5, 0.8),
            "compound_meter": True,
        },
    }
    
    def __init__(
        self,
        cache_dir: Optional[str] = None,
        verbose: bool = False,
    ):
        """Initialize reference analyzer.
        
        Args:
            cache_dir: Directory to cache downloaded audio (default: temp)
            verbose: Print analysis progress
        """
        self.cache_dir = Path(cache_dir) if cache_dir else Path(tempfile.gettempdir()) / "music_gen_cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.verbose = verbose
    
    def analyze_url(self, url: str) -> ReferenceAnalysis:
        """Analyze a YouTube or audio URL.
        
        Args:
            url: YouTube URL or direct audio file URL
            
        Returns:
            ReferenceAnalysis with extracted musical features
        """
        if self.verbose:
            print(f"Analyzing reference: {url}")
        
        # Download audio
        audio_path, metadata = self._download_audio(url)
        
        try:
            # Load audio
            librosa = _get_librosa()
            if self.verbose:
                print("Loading audio...")
            
            # Load at 22050 Hz for analysis (standard for librosa)
            y, sr = librosa.load(str(audio_path), sr=22050, mono=True)
            duration = len(y) / sr
            
            if self.verbose:
                print(f"Audio loaded: {duration:.1f}s at {sr}Hz")
            
            # Run all analyses
            if self.verbose:
                print("Detecting BPM...")
            bpm, bpm_confidence = self._detect_bpm(y, sr)
            
            if self.verbose:
                print("Detecting key...")
            key, mode, key_confidence = self._detect_key(y, sr)
            
            if self.verbose:
                print("Analyzing drums...")
            drums = self._analyze_drums(y, sr, bpm)
            
            if self.verbose:
                print("Analyzing spectral profile...")
            spectral = self._analyze_spectral(y, sr)
            
            if self.verbose:
                print("Analyzing groove...")
            groove = self._analyze_groove(y, sr, bpm)
            
            # Estimate genre
            genre, genre_conf = self._estimate_genre(bpm, drums, spectral, groove)
            
            # Generate style tags
            style_tags = self._generate_style_tags(bpm, key, mode, drums, spectral, groove)
            
            analysis = ReferenceAnalysis(
                source_url=url,
                title=metadata.get("title", "Unknown"),
                duration_seconds=duration,
                bpm=bpm,
                bpm_confidence=bpm_confidence,
                key=key,
                mode=mode,
                key_confidence=key_confidence,
                drums=drums,
                spectral=spectral,
                groove=groove,
                estimated_genre=genre,
                genre_confidence=genre_conf,
                style_tags=style_tags,
            )
            
            if self.verbose:
                print(f"\nAnalysis complete:")
                print(f"  BPM: {bpm:.1f} (confidence: {bpm_confidence:.2f})")
                print(f"  Key: {key} {mode} (confidence: {key_confidence:.2f})")
                print(f"  Genre: {genre} (confidence: {genre_conf:.2f})")
                print(f"  Style: {', '.join(style_tags[:5])}")
            
            return analysis
            
        finally:
            # Clean up temp file if not caching
            if audio_path.parent == Path(tempfile.gettempdir()):
                try:
                    audio_path.unlink()
                except:
                    pass
    
    def analyze_file(self, file_path: str) -> ReferenceAnalysis:
        """Analyze a local audio file.
        
        Args:
            file_path: Path to audio file (WAV, MP3, etc.)
            
        Returns:
            ReferenceAnalysis with extracted features
        """
        librosa = _get_librosa()
        
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Audio file not found: {file_path}")
        
        y, sr = librosa.load(str(path), sr=22050, mono=True)
        duration = len(y) / sr
        
        bpm, bpm_conf = self._detect_bpm(y, sr)
        key, mode, key_conf = self._detect_key(y, sr)
        drums = self._analyze_drums(y, sr, bpm)
        spectral = self._analyze_spectral(y, sr)
        groove = self._analyze_groove(y, sr, bpm)
        genre, genre_conf = self._estimate_genre(bpm, drums, spectral, groove)
        style_tags = self._generate_style_tags(bpm, key, mode, drums, spectral, groove)
        
        return ReferenceAnalysis(
            source_url=f"file://{path.absolute()}",
            title=path.stem,
            duration_seconds=duration,
            bpm=bpm,
            bpm_confidence=bpm_conf,
            key=key,
            mode=mode,
            key_confidence=key_conf,
            drums=drums,
            spectral=spectral,
            groove=groove,
            estimated_genre=genre,
            genre_confidence=genre_conf,
            style_tags=style_tags,
        )
    
    def _download_audio(self, url: str) -> Tuple[Path, Dict[str, Any]]:
        """Download audio from URL using yt-dlp.
        
        Returns:
            Tuple of (audio_path, metadata_dict)
        """
        yt_dlp = _get_yt_dlp()
        
        # Generate cache filename from URL
        url_hash = str(hash(url) & 0xFFFFFFFF)
        output_path = self.cache_dir / f"ref_{url_hash}.wav"
        
        # Check cache
        if output_path.exists():
            if self.verbose:
                print(f"Using cached audio: {output_path}")
            # Try to load cached metadata
            meta_path = output_path.with_suffix(".json")
            metadata = {}
            if meta_path.exists():
                try:
                    metadata = json.loads(meta_path.read_text())
                except:
                    pass
            return output_path, metadata
        
        if self.verbose:
            print(f"Downloading audio from: {url}")
        
        # yt-dlp options for audio extraction
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': str(output_path.with_suffix('.%(ext)s')),
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'wav',
                'preferredquality': '192',
            }],
            'quiet': not self.verbose,
            'no_warnings': not self.verbose,
        }
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                metadata = {
                    "title": info.get("title", "Unknown"),
                    "duration": info.get("duration", 0),
                    "uploader": info.get("uploader", "Unknown"),
                    "url": url,
                }
                
                # Save metadata cache
                meta_path = output_path.with_suffix(".json")
                meta_path.write_text(json.dumps(metadata, indent=2))
                
                return output_path, metadata
                
        except Exception as e:
            raise RuntimeError(f"Failed to download audio: {e}")
    
    def _detect_bpm(self, y: np.ndarray, sr: int) -> Tuple[float, float]:
        """Detect BPM using multiple methods for accuracy.
        
        Returns:
            Tuple of (bpm, confidence)
        """
        librosa = _get_librosa()
        
        # Method 1: librosa beat tracker
        tempo1, beats = librosa.beat.beat_track(y=y, sr=sr)
        # Handle both scalar and array returns from different librosa versions
        tempo1 = float(np.atleast_1d(tempo1)[0])
        
        # Method 2: Onset-based tempo estimation
        onset_env = librosa.onset.onset_strength(y=y, sr=sr)
        tempo2 = librosa.feature.tempo(onset_envelope=onset_env, sr=sr)
        tempo2 = float(np.atleast_1d(tempo2)[0])
        
        # Method 3: Autocorrelation-based
        # Use tempogram for more detailed analysis
        tempogram = librosa.feature.tempogram(onset_envelope=onset_env, sr=sr)
        tempo3 = librosa.feature.tempo(onset_envelope=onset_env, sr=sr, aggregate=None)
        if len(tempo3) > 0:
            tempo3 = float(np.median(tempo3))
        else:
            tempo3 = tempo1
        
        # Combine estimates
        tempos = [tempo1, tempo2, tempo3]
        
        # Handle half/double time detection
        # Hip-hop often detected at double time
        adjusted_tempos = []
        for t in tempos:
            adjusted_tempos.append(t)
            if t > 150:  # Might be double time
                adjusted_tempos.append(t / 2)
            if t < 80:  # Might be half time
                adjusted_tempos.append(t * 2)
        
        # Find consensus (cluster similar tempos)
        final_tempo = np.median(tempos)
        
        # Calculate confidence based on agreement
        tempo_std = np.std(tempos)
        confidence = max(0.0, 1.0 - (tempo_std / 20.0))  # Lower std = higher confidence
        
        # Round to common BPM values
        common_bpms = [60, 65, 70, 75, 80, 85, 87, 90, 92, 95, 100, 105, 110, 
                       115, 120, 124, 128, 130, 135, 140, 145, 150, 155, 160]
        closest_bpm = min(common_bpms, key=lambda x: abs(x - final_tempo))
        
        # Only snap to common BPM if close enough
        if abs(closest_bpm - final_tempo) < 3:
            final_tempo = float(closest_bpm)
        
        return final_tempo, confidence
    
    def _detect_key(self, y: np.ndarray, sr: int) -> Tuple[str, str, float]:
        """Detect musical key using chroma analysis.
        
        Returns:
            Tuple of (key, mode, confidence)
        """
        librosa = _get_librosa()
        
        # Compute chroma features
        chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
        
        # Average chroma over time
        chroma_avg = np.mean(chroma, axis=1)
        
        # Major and minor key profiles (Krumhansl-Schmuckler)
        major_profile = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 
                                   2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
        minor_profile = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53,
                                   2.54, 4.75, 3.98, 2.69, 3.34, 3.17])
        
        # Correlate with all keys
        major_corrs = []
        minor_corrs = []
        
        for i in range(12):
            # Rotate profiles to each key
            major_rotated = np.roll(major_profile, i)
            minor_rotated = np.roll(minor_profile, i)
            
            major_corrs.append(np.corrcoef(chroma_avg, major_rotated)[0, 1])
            minor_corrs.append(np.corrcoef(chroma_avg, minor_rotated)[0, 1])
        
        # Find best match
        max_major_idx = np.argmax(major_corrs)
        max_minor_idx = np.argmax(minor_corrs)
        max_major = major_corrs[max_major_idx]
        max_minor = minor_corrs[max_minor_idx]
        
        if max_major > max_minor:
            key = self.KEY_NAMES[max_major_idx]
            mode = "major"
            confidence = float(max_major)
        else:
            key = self.KEY_NAMES[max_minor_idx]
            mode = "minor"
            confidence = float(max_minor)
        
        # Normalize confidence to 0-1
        confidence = (confidence + 1) / 2  # Correlation is -1 to 1
        
        return key, mode, confidence
    
    def _analyze_drums(
        self, 
        y: np.ndarray, 
        sr: int, 
        bpm: float
    ) -> DrumAnalysis:
        """Analyze drum patterns and characteristics."""
        librosa = _get_librosa()
        
        # Separate percussive component
        y_harm, y_perc = librosa.effects.hpss(y)
        
        # Onset detection on percussive component
        onset_env = librosa.onset.onset_strength(y=y_perc, sr=sr)
        onsets = librosa.onset.onset_detect(
            onset_envelope=onset_env, 
            sr=sr, 
            units='time'
        )
        
        # Calculate drum density (onsets per beat)
        duration = len(y) / sr
        beats_total = (duration / 60) * bpm
        density = len(onsets) / max(1, beats_total)
        density_normalized = min(1.0, density / 4)  # Normalize to 0-1
        
        # Analyze frequency bands for kick/snare/hihat detection
        # Low frequency for kick (60-150 Hz)
        y_low = librosa.effects.preemphasis(y_perc, coef=-0.97)
        
        # High frequency for hi-hats (5000-15000 Hz)  
        y_high = librosa.effects.preemphasis(y_perc, coef=0.97)
        
        # Onset patterns in different frequency bands
        onset_low = librosa.onset.onset_strength(y=y_low, sr=sr)
        onset_high = librosa.onset.onset_strength(y=y_high, sr=sr)
        
        # Hi-hat density (high frequency activity)
        hihat_density = float(np.mean(onset_high) / max(0.01, np.mean(onset_env)))
        hihat_density = min(1.0, hihat_density)
        
        # Detect trap-style hi-hat rolls (rapid successive hits)
        high_onset_times = librosa.onset.onset_detect(
            onset_envelope=onset_high, 
            sr=sr, 
            units='time'
        )
        
        # Check for rapid hi-hat patterns (< 0.1s between hits)
        if len(high_onset_times) > 2:
            intervals = np.diff(high_onset_times)
            rapid_hits = np.sum(intervals < 0.1) / len(intervals)
            trap_hihats = rapid_hits > 0.2  # More than 20% rapid hits
            has_rolls = rapid_hits > 0.3
        else:
            trap_hihats = False
            has_rolls = False
        
        # Detect four-on-floor (kick on every beat)
        beat_frames = librosa.time_to_frames(
            librosa.beat.beat_track(y=y_perc, sr=sr)[1] * 512 / sr,
            sr=sr
        )
        if len(beat_frames) > 4:
            # Check low frequency energy on beats
            low_on_beats = [onset_low[min(f, len(onset_low)-1)] for f in beat_frames[:16]]
            low_consistency = np.std(low_on_beats) / max(0.01, np.mean(low_on_beats))
            four_on_floor = low_consistency < 0.5  # Consistent kick on beats
        else:
            four_on_floor = False
        
        # Detect boom-bap feel (swing + emphasis on 2 and 4)
        # Calculate swing by looking at 8th note timing
        boom_bap_feel = (
            density_normalized > 0.3 and 
            density_normalized < 0.7 and
            not trap_hihats and
            not four_on_floor
        )
        
        # Detect compound meter (6/8, 12/8) - Ethiopian, Afrobeat
        # Compound meters have accents in groups of 3 rather than 2 or 4
        compound_meter = False
        try:
            # Get beat positions
            tempo, beats = librosa.beat.beat_track(y=y_perc, sr=sr)
            if len(beats) > 12:
                # Analyze accent pattern - compound meters have different energy distribution
                beat_times = librosa.frames_to_time(beats, sr=sr)
                intervals = np.diff(beat_times)
                if len(intervals) > 6:
                    # Check for triplet-like groupings (every 3rd beat stronger)
                    # In 6/8 or 12/8, there's typically emphasis every 3 subdivisions
                    beat_energies = [onset_env[min(b, len(onset_env)-1)] for b in beats[:24]]
                    if len(beat_energies) >= 12:
                        # Compare energy of 1st vs 2nd vs 3rd positions in groups of 3
                        first = np.mean(beat_energies[::3])
                        second = np.mean(beat_energies[1::3])
                        third = np.mean(beat_energies[2::3])
                        # Compound meter: 1st position is significantly stronger
                        if first > second * 1.2 and first > third * 1.2:
                            compound_meter = True
        except Exception:
            pass  # If detection fails, default to False
        
        return DrumAnalysis(
            density=density_normalized,
            kick_pattern=[],  # Would need beat-aligned analysis
            snare_pattern=[],
            hihat_density=hihat_density,
            has_rolls=has_rolls,
            four_on_floor=four_on_floor,
            trap_hihats=trap_hihats,
            boom_bap_feel=boom_bap_feel,
            compound_meter=compound_meter,
        )
    
    def _analyze_spectral(self, y: np.ndarray, sr: int) -> SpectralProfile:
        """Analyze spectral characteristics."""
        librosa = _get_librosa()
        
        # Spectral centroid (brightness)
        centroid = librosa.feature.spectral_centroid(y=y, sr=sr)
        brightness = float(np.mean(centroid)) / (sr / 2)  # Normalize to Nyquist
        brightness = min(1.0, brightness * 4)  # Scale up for useful range
        
        # Spectral rolloff
        rolloff = librosa.feature.spectral_rolloff(y=y, sr=sr, roll_percent=0.85)
        clarity = float(np.mean(rolloff)) / (sr / 2)
        clarity = min(1.0, clarity * 2)
        
        # Low frequency analysis for warmth and sub-bass
        # Compute STFT
        D = np.abs(librosa.stft(y))
        freqs = librosa.fft_frequencies(sr=sr)
        
        # Sub-bass (20-80 Hz)
        sub_mask = (freqs >= 20) & (freqs <= 80)
        sub_energy = np.mean(D[sub_mask, :]) if np.any(sub_mask) else 0
        
        # Low-mid (80-300 Hz) for warmth
        low_mid_mask = (freqs >= 80) & (freqs <= 300)
        low_mid_energy = np.mean(D[low_mid_mask, :]) if np.any(low_mid_mask) else 0
        
        # Total energy for normalization
        total_energy = np.mean(D)
        
        sub_bass_presence = min(1.0, (sub_energy / max(0.01, total_energy)) * 10)
        warmth = min(1.0, (low_mid_energy / max(0.01, total_energy)) * 5)
        
        # Detect 808-style sub-bass (sustained sub frequencies)
        # 808s have long sustained sub-bass notes
        sub_variance = np.var(D[sub_mask, :]) if np.any(sub_mask) else 0
        has_808 = sub_bass_presence > 0.3 and sub_variance < np.mean(D) * 0.5
        
        # Lo-fi character detection
        # Lo-fi typically has: reduced high frequencies, some noise, warmth
        high_mask = freqs > 8000
        high_energy = np.mean(D[high_mask, :]) if np.any(high_mask) else 0
        high_ratio = high_energy / max(0.01, total_energy)
        
        # Lo-fi = warm + not too bright + some high-frequency roll-off
        lofi_character = (
            warmth * 0.4 + 
            (1 - brightness) * 0.3 + 
            (1 - min(1.0, high_ratio * 20)) * 0.3
        )
        
        # Pentatonic detection using chroma analysis
        # Pentatonic scales use only 5 notes (vs 7 in diatonic)
        # Ethiopian qenet scales are pentatonic variants
        pentatonic = False
        try:
            chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
            chroma_mean = np.mean(chroma, axis=1)
            
            # Sort chroma values to find dominant notes
            sorted_indices = np.argsort(chroma_mean)[::-1]
            
            # Pentatonic: top 5 notes should have significantly more energy
            # than the remaining 7 notes
            top_5_energy = np.sum(chroma_mean[sorted_indices[:5]])
            bottom_7_energy = np.sum(chroma_mean[sorted_indices[5:]])
            
            # If top 5 notes dominate, likely pentatonic
            if top_5_energy > bottom_7_energy * 2.5:
                pentatonic = True
        except Exception:
            pass  # If detection fails, default to False
        
        return SpectralProfile(
            brightness=brightness,
            warmth=warmth,
            sub_bass_presence=sub_bass_presence,
            has_808=has_808,
            lofi_character=lofi_character,
            clarity=clarity,
            pentatonic=pentatonic,
        )
    
    def _analyze_groove(
        self, 
        y: np.ndarray, 
        sr: int, 
        bpm: float
    ) -> GrooveAnalysis:
        """Analyze groove and timing characteristics."""
        librosa = _get_librosa()
        
        # Get beat times
        tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr)
        beat_times = librosa.frames_to_time(beat_frames, sr=sr)
        
        if len(beat_times) < 4:
            return GrooveAnalysis(
                swing_amount=0.0,
                groove_feel=GrooveFeel.STRAIGHT,
                pulse_strength=0.5,
                micro_timing_variance=0.0,
                downbeat_emphasis=0.5,
            )
        
        # Calculate inter-beat intervals
        intervals = np.diff(beat_times)
        expected_interval = 60.0 / bpm
        
        # Micro-timing variance (humanization)
        interval_variance = np.std(intervals) / expected_interval
        micro_timing = min(1.0, interval_variance * 10)
        
        # Swing detection
        # Analyze 8th note positions relative to beats
        onset_env = librosa.onset.onset_strength(y=y, sr=sr)
        onset_times = librosa.onset.onset_detect(
            onset_envelope=onset_env, 
            sr=sr, 
            units='time'
        )
        
        # Calculate swing ratio from 8th note timing
        eighth_duration = expected_interval / 2
        swing_ratios = []
        
        for beat_time in beat_times[:-1]:
            # Find onsets near the expected 8th note position
            offbeat_time = beat_time + eighth_duration
            nearby = onset_times[(onset_times > beat_time) & 
                                  (onset_times < beat_time + expected_interval)]
            
            if len(nearby) > 0:
                # Find closest onset to expected offbeat
                closest = nearby[np.argmin(np.abs(nearby - offbeat_time))]
                actual_ratio = (closest - beat_time) / expected_interval
                if 0.4 < actual_ratio < 0.7:  # Reasonable range
                    swing_ratios.append(actual_ratio)
        
        if swing_ratios:
            avg_swing_ratio = np.mean(swing_ratios)
            # Convert ratio to swing amount (0.5 = straight, 0.67 = full swing)
            swing_amount = (avg_swing_ratio - 0.5) / 0.17  # Normalize
            swing_amount = max(0.0, min(1.0, swing_amount))
        else:
            swing_amount = 0.0
        
        # Determine groove feel
        if swing_amount > 0.7:
            groove_feel = GrooveFeel.HEAVY_SWING
        elif swing_amount > 0.5:
            groove_feel = GrooveFeel.SHUFFLE
        elif swing_amount > 0.3:
            groove_feel = GrooveFeel.MEDIUM_SWING
        elif swing_amount > 0.1:
            groove_feel = GrooveFeel.LIGHT_SWING
        else:
            groove_feel = GrooveFeel.STRAIGHT
        
        # Pulse strength (how prominent the beat is)
        pulse_strength = float(np.mean(onset_env[beat_frames]) / 
                               max(0.01, np.mean(onset_env)))
        pulse_strength = min(1.0, pulse_strength / 2)
        
        # Downbeat emphasis (beat 1 vs other beats)
        if len(beat_frames) >= 8:
            downbeats = beat_frames[::4][:4]  # Every 4th beat
            other_beats = beat_frames[:16]
            downbeat_strength = np.mean([onset_env[min(b, len(onset_env)-1)] 
                                         for b in downbeats])
            other_strength = np.mean([onset_env[min(b, len(onset_env)-1)] 
                                      for b in other_beats])
            downbeat_emphasis = downbeat_strength / max(0.01, other_strength)
            downbeat_emphasis = min(1.0, downbeat_emphasis / 1.5)
        else:
            downbeat_emphasis = 0.5
        
        return GrooveAnalysis(
            swing_amount=swing_amount,
            groove_feel=groove_feel,
            pulse_strength=pulse_strength,
            micro_timing_variance=micro_timing,
            downbeat_emphasis=downbeat_emphasis,
        )
    
    def _estimate_genre(
        self,
        bpm: float,
        drums: DrumAnalysis,
        spectral: SpectralProfile,
        groove: GrooveAnalysis,
    ) -> Tuple[str, float]:
        """Estimate genre from extracted features."""
        scores = {}
        
        for genre, profile in self.GENRE_PROFILES.items():
            score = 0.0
            factors = 0
            
            # BPM range match
            if "bpm_range" in profile:
                low, high = profile["bpm_range"]
                if low <= bpm <= high:
                    score += 1.0
                elif abs(bpm - low) < 15 or abs(bpm - high) < 15:
                    score += 0.5
                factors += 1
            
            # 808 presence
            if "has_808" in profile:
                if spectral.has_808 == profile["has_808"]:
                    score += 1.0
                factors += 1
            
            # Trap hi-hats
            if "trap_hihats" in profile:
                if drums.trap_hihats == profile["trap_hihats"]:
                    score += 1.0
                factors += 1
            
            # Four-on-floor
            if "four_on_floor" in profile:
                if drums.four_on_floor == profile["four_on_floor"]:
                    score += 1.0
                factors += 1
            
            # Boom-bap feel
            if "boom_bap_feel" in profile:
                if drums.boom_bap_feel == profile["boom_bap_feel"]:
                    score += 1.0
                factors += 1
            
            # Brightness range
            if "brightness" in profile:
                low, high = profile["brightness"]
                if low <= spectral.brightness <= high:
                    score += 1.0
                factors += 1
            
            # Lo-fi character
            if "lofi_character" in profile:
                if spectral.lofi_character >= profile["lofi_character"]:
                    score += 1.0
                factors += 1
            
            # Swing
            if "swing" in profile:
                if groove.swing_amount >= profile["swing"]:
                    score += 0.8
                factors += 1
            
            # Compound meter (6/8, 12/8) - Ethiopian, Afrobeat
            if "compound_meter" in profile:
                if drums.compound_meter == profile["compound_meter"]:
                    score += 1.2  # Strong indicator for Ethiopian
                factors += 1
            
            # Pentatonic scale detection
            if "pentatonic" in profile:
                if spectral.pentatonic == profile["pentatonic"]:
                    score += 1.0
                factors += 1
            
            # Normalize score
            if factors > 0:
                scores[genre] = score / factors
        
        if not scores:
            return "hip_hop", 0.5
        
        best_genre = max(scores, key=scores.get)
        return best_genre, scores[best_genre]
    
    def _generate_style_tags(
        self,
        bpm: float,
        key: str,
        mode: str,
        drums: DrumAnalysis,
        spectral: SpectralProfile,
        groove: GrooveAnalysis,
    ) -> List[str]:
        """Generate descriptive style tags from analysis."""
        tags = []
        
        # BPM-based tags
        if bpm < 80:
            tags.append("slow")
        elif bpm > 140:
            tags.append("uptempo")
        
        # Key/mode tags
        if mode == "minor":
            tags.append("dark")
            tags.append("moody")
        else:
            tags.append("bright")
            tags.append("uplifting")
        
        # Spectral tags
        if spectral.has_808:
            tags.append("808")
            tags.append("sub-heavy")
        if spectral.lofi_character > 0.5:
            tags.append("lo-fi")
            tags.append("dusty")
            tags.append("vintage")
        if spectral.brightness < 0.3:
            tags.append("warm")
            tags.append("mellow")
        elif spectral.brightness > 0.7:
            tags.append("crisp")
            tags.append("bright")
        if spectral.warmth > 0.6:
            tags.append("analog")
        
        # Drum tags
        if drums.trap_hihats:
            tags.append("trap")
            tags.append("hi-hat rolls")
        if drums.four_on_floor:
            tags.append("four-on-floor")
            tags.append("dance")
        if drums.boom_bap_feel:
            tags.append("boom bap")
            tags.append("classic hip-hop")
        if drums.density > 0.7:
            tags.append("busy drums")
        elif drums.density < 0.3:
            tags.append("minimal")
            tags.append("sparse")
        
        # Groove tags
        if groove.swing_amount > 0.3:
            tags.append("swing")
            tags.append("groovy")
        if groove.micro_timing_variance > 0.3:
            tags.append("humanized")
            tags.append("live feel")
        
        return tags


# Convenience functions
def analyze_reference(url: str, verbose: bool = False) -> ReferenceAnalysis:
    """Quick function to analyze a reference URL.
    
    Args:
        url: YouTube URL or audio file path
        verbose: Print progress
        
    Returns:
        ReferenceAnalysis with extracted features
    """
    analyzer = ReferenceAnalyzer(verbose=verbose)
    
    if url.startswith(("http://", "https://")):
        return analyzer.analyze_url(url)
    else:
        return analyzer.analyze_file(url)


def reference_to_prompt(url: str, base_prompt: str = "") -> str:
    """Analyze reference and combine with base prompt.
    
    Args:
        url: Reference URL to analyze
        base_prompt: Optional base prompt to enhance
        
    Returns:
        Enhanced prompt string
    """
    analysis = analyze_reference(url, verbose=True)
    hints = analysis.to_prompt_hints()
    
    if base_prompt:
        return f"{base_prompt}, {hints}"
    else:
        return f"beat {hints}"
