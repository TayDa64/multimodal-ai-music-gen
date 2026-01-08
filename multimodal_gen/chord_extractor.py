"""
Chord Progression Extraction - Analyze audio to extract harmonic content.

Uses chromagram analysis to detect chords and progressions from reference audio.
"""

from dataclasses import dataclass
from typing import List, Dict, Tuple, Optional
import numpy as np
from scipy import signal
from pathlib import Path


@dataclass
class ChordEvent:
    """A detected chord at a specific time."""
    chord: str              # Chord name (e.g., "Cmaj", "Am7", "F#dim")
    root: str               # Root note (e.g., "C", "A", "F#")
    quality: str            # Quality (e.g., "maj", "min", "dim", "aug", "7", "maj7", "min7")
    start_time: float       # Start time in seconds
    end_time: float         # End time in seconds
    confidence: float       # Detection confidence (0-1)


@dataclass
class ChordProgression:
    """Extracted chord progression."""
    chords: List[ChordEvent]
    key: str                        # Detected key (e.g., "C", "Am")
    mode: str                       # "major" or "minor"
    tempo: Optional[float] = None   # BPM if detected
    time_signature: str = "4/4"


# Chord quality templates (relative to root = 0)
CHORD_TEMPLATES = {
    "maj": [1, 0, 0, 0, 1, 0, 0, 1, 0, 0, 0, 0],     # Root, M3, P5
    "min": [1, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 0],     # Root, m3, P5
    "dim": [1, 0, 0, 1, 0, 0, 1, 0, 0, 0, 0, 0],     # Root, m3, dim5
    "aug": [1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0],     # Root, M3, aug5
    "7": [1, 0, 0, 0, 1, 0, 0, 1, 0, 0, 1, 0],       # Dominant 7
    "maj7": [1, 0, 0, 0, 1, 0, 0, 1, 0, 0, 0, 1],    # Major 7
    "min7": [1, 0, 0, 1, 0, 0, 0, 1, 0, 0, 1, 0],    # Minor 7
    "dim7": [1, 0, 0, 1, 0, 0, 1, 0, 0, 1, 0, 0],    # Diminished 7
    "sus4": [1, 0, 0, 0, 0, 1, 0, 1, 0, 0, 0, 0],    # Suspended 4
    "sus2": [1, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0],    # Suspended 2
}


# Common chord progression patterns for detection
COMMON_PROGRESSIONS = {
    "I-IV-V-I": ["I", "IV", "V", "I"],
    "I-V-vi-IV": ["I", "V", "vi", "IV"],  # Pop progression
    "ii-V-I": ["ii", "V", "I"],            # Jazz cadence
    "I-vi-IV-V": ["I", "vi", "IV", "V"],   # 50s progression
    "i-VII-VI-VII": ["i", "VII", "VI", "VII"],  # Andalusian
    "I-IV-I-V": ["I", "IV", "I", "V"],     # Blues turnaround
    "12_bar_blues": ["I", "I", "I", "I", "IV", "IV", "I", "I", "V", "IV", "I", "V"],
}


# Note names
NOTE_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']

# Krumhansl-Schmuckler key profiles
MAJOR_PROFILE = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 
                          2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
MINOR_PROFILE = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53,
                          2.54, 4.75, 3.98, 2.69, 3.34, 3.17])


class ChordExtractor:
    """
    Extract chord progressions from audio using chromagram analysis.
    
    Usage:
        extractor = ChordExtractor(sample_rate=44100)
        progression = extractor.analyze(audio)
        print(progression.chords)
        print(f"Key: {progression.key} {progression.mode}")
    """
    
    def __init__(self, sample_rate: int = 44100, hop_length: int = 512):
        self.sample_rate = sample_rate
        self.hop_length = hop_length
        
        # Chord templates for matching
        self._chord_templates = self._build_chord_templates()
    
    def _build_chord_templates(self) -> Dict[str, np.ndarray]:
        """
        Build chromagram templates for chord matching.
        
        Templates for: major, minor, diminished, augmented, 
        dominant 7, major 7, minor 7, etc.
        """
        templates = {}
        for quality, pattern in CHORD_TEMPLATES.items():
            # Normalize the template
            template = np.array(pattern, dtype=np.float64)
            if template.sum() > 0:
                template = template / template.sum()
            templates[quality] = template
        return templates
    
    def analyze(
        self,
        audio: np.ndarray,
        min_chord_duration: float = 0.25  # Minimum chord length in seconds
    ) -> ChordProgression:
        """
        Analyze audio and extract chord progression.
        
        Args:
            audio: Audio array (mono or stereo, will be converted to mono)
            min_chord_duration: Minimum duration for a chord to be detected
            
        Returns:
            ChordProgression with detected chords and key
        """
        # Convert to mono if stereo
        if audio.ndim > 1:
            audio = np.mean(audio, axis=1)
        
        # Compute chromagram
        chromagram = self.compute_chromagram(audio)
        
        # Detect key
        key, mode = self.detect_key(chromagram)
        
        # Detect chords
        min_duration_frames = int(min_chord_duration * self.sample_rate / self.hop_length)
        chords = self.detect_chords(chromagram, min_duration_frames)
        
        return ChordProgression(
            chords=chords,
            key=key,
            mode=mode,
            tempo=None,  # Tempo detection not implemented yet
            time_signature="4/4"
        )
    
    def compute_chromagram(
        self,
        audio: np.ndarray,
        n_chroma: int = 12
    ) -> np.ndarray:
        """
        Compute chromagram (pitch class energy over time).
        
        Uses STFT and maps to 12 pitch classes.
        
        Args:
            audio: Mono audio array
            n_chroma: Number of chroma bins (12 for standard)
            
        Returns:
            Chromagram array (12, num_frames)
        """
        # Handle very short audio
        nperseg = min(2048, len(audio))
        noverlap = max(0, nperseg - self.hop_length)
        
        # Ensure noverlap is less than nperseg
        if noverlap >= nperseg:
            noverlap = nperseg // 2
        
        # Compute STFT
        f, t, Zxx = signal.stft(
            audio,
            fs=self.sample_rate,
            nperseg=nperseg,
            noverlap=noverlap
        )
        
        # Get magnitude spectrum
        mag = np.abs(Zxx)
        
        # Initialize chromagram
        chromagram = np.zeros((n_chroma, mag.shape[1]))
        
        # Map frequencies to pitch classes
        # A4 = 440 Hz = pitch class A = 9
        for i, freq in enumerate(f):
            if freq < 20:  # Skip very low frequencies
                continue
            
            # Convert frequency to MIDI note number
            # MIDI 69 = A4 = 440 Hz
            if freq > 0:
                midi_note = 69 + 12 * np.log2(freq / 440.0)
                pitch_class = int(round(midi_note)) % 12
                
                # Add to chromagram
                if 0 <= pitch_class < n_chroma:
                    chromagram[pitch_class, :] += mag[i, :]
        
        # Normalize each frame
        for i in range(chromagram.shape[1]):
            total = chromagram[:, i].sum()
            if total > 0:
                chromagram[:, i] /= total
        
        return chromagram
    
    def detect_chords(
        self,
        chromagram: np.ndarray,
        min_duration_frames: int
    ) -> List[ChordEvent]:
        """
        Detect chords from chromagram using template matching.
        
        Args:
            chromagram: Chromagram array
            min_duration_frames: Minimum frames for a chord
            
        Returns:
            List of detected ChordEvents
        """
        chords = []
        num_frames = chromagram.shape[1]
        
        i = 0
        while i < num_frames:
            # Match current frame to chord template
            chord_name, root, quality, confidence = self.match_chord_template(
                chromagram[:, i]
            )
            
            # Find duration of this chord (look ahead for similar chroma)
            start_frame = i
            j = i + 1
            
            while j < num_frames:
                # Check if this frame is similar enough to be the same chord
                next_chord, next_root, _, next_conf = self.match_chord_template(
                    chromagram[:, j]
                )
                
                # Same chord if root and quality match
                if next_chord == chord_name:
                    j += 1
                else:
                    break
            
            end_frame = j
            duration_frames = end_frame - start_frame
            
            # Only add if meets minimum duration
            if duration_frames >= min_duration_frames:
                start_time = start_frame * self.hop_length / self.sample_rate
                end_time = end_frame * self.hop_length / self.sample_rate
                
                chords.append(ChordEvent(
                    chord=chord_name,
                    root=root,
                    quality=quality,
                    start_time=start_time,
                    end_time=end_time,
                    confidence=confidence
                ))
            
            i = j if j > i else i + 1
        
        return chords
    
    def match_chord_template(
        self,
        chroma_frame: np.ndarray
    ) -> Tuple[str, str, str, float]:
        """
        Match a chroma frame to chord templates.
        
        Args:
            chroma_frame: Single chroma vector (12,)
            
        Returns:
            (chord_name, root, quality, confidence)
        """
        best_score = -1
        best_root = 0
        best_quality = "maj"
        
        # Try all root notes and chord qualities
        for root_idx in range(12):
            for quality, template in self._chord_templates.items():
                # Rotate chroma to align with this root
                rotated_chroma = np.roll(chroma_frame, -root_idx)
                
                # Compute correlation with template
                score = np.dot(rotated_chroma, template)
                
                if score > best_score:
                    best_score = score
                    best_root = root_idx
                    best_quality = quality
        
        root_name = NOTE_NAMES[best_root]
        chord_name = f"{root_name}{best_quality}"
        
        # Normalize confidence to 0-1
        confidence = float(np.clip(best_score, 0, 1))
        
        return chord_name, root_name, best_quality, confidence
    
    def detect_key(
        self,
        chromagram: np.ndarray
    ) -> Tuple[str, str]:
        """
        Detect the key of the audio.
        
        Uses Krumhansl-Schmuckler key-finding algorithm.
        
        Args:
            chromagram: Chromagram array
            
        Returns:
            (key, mode) e.g., ("C", "major") or ("A", "minor")
        """
        # Average chromagram over time
        chroma_avg = np.mean(chromagram, axis=1)
        
        # Correlate with all keys
        major_corrs = []
        minor_corrs = []
        
        for i in range(12):
            # Rotate profiles to each key
            major_rotated = np.roll(MAJOR_PROFILE, i)
            minor_rotated = np.roll(MINOR_PROFILE, i)
            
            # Normalize profiles
            major_rotated = major_rotated / major_rotated.sum()
            minor_rotated = minor_rotated / minor_rotated.sum()
            
            # Compute correlation
            major_corrs.append(np.corrcoef(chroma_avg, major_rotated)[0, 1])
            minor_corrs.append(np.corrcoef(chroma_avg, minor_rotated)[0, 1])
        
        # Find best match
        max_major_idx = int(np.argmax(major_corrs))
        max_minor_idx = int(np.argmax(minor_corrs))
        max_major = major_corrs[max_major_idx]
        max_minor = minor_corrs[max_minor_idx]
        
        if max_major > max_minor:
            key = NOTE_NAMES[max_major_idx]
            mode = "major"
        else:
            key = NOTE_NAMES[max_minor_idx]
            mode = "minor"
        
        return key, mode
    
    def simplify_progression(
        self,
        chords: List[ChordEvent],
        to_roman: bool = False
    ) -> List[str]:
        """
        Simplify chord progression to common patterns.
        
        Args:
            chords: List of ChordEvents
            to_roman: Convert to Roman numerals (I, IV, V, etc.)
            
        Returns:
            Simplified chord list
        """
        if not chords:
            return []
        
        if to_roman:
            # Get key from first chord or use C major as default
            # For simplicity, we'll need to know the key of the progression
            # This is a simplified implementation
            return [self._chord_to_roman(chord.root, chord.quality, "C", "major") 
                    for chord in chords]
        else:
            return [chord.chord for chord in chords]
    
    def _chord_to_roman(self, root: str, quality: str, key: str, mode: str) -> str:
        """Convert a chord to Roman numeral notation."""
        # Simplified implementation
        # Map root to scale degree
        try:
            key_idx = NOTE_NAMES.index(key)
            root_idx = NOTE_NAMES.index(root)
            degree = (root_idx - key_idx) % 12
            
            # Map to Roman numerals (simplified, assuming diatonic)
            degree_map = {
                0: "I", 2: "ii", 4: "iii", 5: "IV", 
                7: "V", 9: "vi", 11: "vii"
            }
            
            roman = degree_map.get(degree, "I")
            
            # Adjust case based on quality
            if quality in ["min", "min7", "dim", "dim7"]:
                roman = roman.lower()
            
            return roman
        except (ValueError, KeyError):
            return "I"
    
    def find_progression_pattern(
        self,
        chords: List[ChordEvent]
    ) -> Optional[str]:
        """
        Identify common progression patterns.
        
        Patterns: I-IV-V-I, ii-V-I, I-V-vi-IV, 12-bar blues, etc.
        
        Returns:
            Pattern name if recognized, None otherwise
        """
        if len(chords) < 2:
            return None
        
        # Convert to simplified form for pattern matching
        # This is a simplified implementation
        chord_names = [chord.chord for chord in chords]
        
        # Check for exact matches with common patterns
        for pattern_name, pattern in COMMON_PROGRESSIONS.items():
            if len(chord_names) >= len(pattern):
                # Check if the beginning matches
                matches = True
                for i, p_chord in enumerate(pattern):
                    if i >= len(chord_names):
                        matches = False
                        break
                    # This is a very simplified check
                    # In reality, we'd need to convert to Roman numerals first
                
        return None  # Simplified implementation


# Convenience functions
def extract_chords(
    audio: np.ndarray,
    sample_rate: int = 44100
) -> ChordProgression:
    """
    Quick chord extraction from audio.
    
    Args:
        audio: Audio array
        sample_rate: Sample rate
        
    Returns:
        Detected ChordProgression
    """
    extractor = ChordExtractor(sample_rate=sample_rate)
    return extractor.analyze(audio)


def extract_chords_from_file(
    file_path: str
) -> ChordProgression:
    """
    Extract chords from an audio file.
    
    Args:
        file_path: Path to audio file (WAV, MP3, etc.)
        
    Returns:
        Detected ChordProgression
    """
    # Try to load with soundfile
    try:
        import soundfile as sf
        audio, sr = sf.read(file_path)
        if audio.ndim > 1:
            audio = np.mean(audio, axis=1)
        return extract_chords(audio, sr)
    except ImportError:
        pass
    
    # Fallback to librosa if available
    try:
        # Lazy import librosa
        import librosa
        audio, sr = librosa.load(file_path, sr=None, mono=True)
        return extract_chords(audio, sr)
    except ImportError:
        raise ImportError(
            "Either soundfile or librosa is required for audio file loading. "
            "Install with: pip install soundfile"
        )


def chords_to_midi(
    progression: ChordProgression,
    ticks_per_beat: int = 480
) -> List[Tuple[int, int, int, int]]:
    """
    Convert chord progression to MIDI notes.
    
    Args:
        progression: ChordProgression to convert
        ticks_per_beat: MIDI ticks per beat
        
    Returns:
        List of (tick, duration, pitch, velocity) for chord notes
    """
    midi_notes = []
    
    # Assume 4/4 time and 120 BPM if not specified
    bpm = progression.tempo if progression.tempo else 120.0
    seconds_per_beat = 60.0 / bpm
    
    for chord in progression.chords:
        # Convert time to ticks
        start_tick = int(chord.start_time / seconds_per_beat * ticks_per_beat)
        end_tick = int(chord.end_time / seconds_per_beat * ticks_per_beat)
        duration = end_tick - start_tick
        
        # Convert root to MIDI note (middle C = 60)
        try:
            root_idx = NOTE_NAMES.index(chord.root)
            root_midi = 60 + root_idx  # C4 = 60
        except ValueError:
            root_midi = 60
        
        # Add notes based on chord quality
        chord_notes = _get_chord_notes(root_midi, chord.quality)
        
        # Add all notes in the chord
        velocity = int(chord.confidence * 100)  # Use confidence as velocity
        velocity = max(40, min(100, velocity))  # Clamp to reasonable range
        
        for pitch in chord_notes:
            midi_notes.append((start_tick, duration, pitch, velocity))
    
    return midi_notes


def _get_chord_notes(root_midi: int, quality: str) -> List[int]:
    """Get MIDI note numbers for a chord."""
    # Get the chord template
    template = CHORD_TEMPLATES.get(quality, CHORD_TEMPLATES["maj"])
    
    # Convert template to MIDI notes
    notes = []
    for i, active in enumerate(template):
        if active:
            notes.append(root_midi + i)
    
    return notes
