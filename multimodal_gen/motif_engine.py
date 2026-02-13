"""
Motif Generation Engine - Foundation for Jazz and extensible to other genres

This module provides a motif-based melodic/rhythmic phrase generation system
that creates short, memorable musical ideas that can be developed throughout
a composition.

A motif is represented as:
- intervals: Relative pitch intervals (not absolute pitches) for transposition
- rhythm: Note durations in beats
- accent_pattern: Velocity weights for expression
- genre_tags: Classification tags for retrieval

Core Classes:
    Motif: Represents a single musical motif
    MotifGenerator: Generates motifs based on genre and context
    MotifLibrary: Stores and retrieves motifs by genre/style

Usage:
    from multimodal_gen.motif_engine import MotifGenerator, Motif
    
    # Generate a jazz motif
    generator = MotifGenerator()
    motif = generator.generate_motif("jazz", {"chord_type": "dominant7"})
    
    # Apply motif to a key
    notes = motif.to_midi_notes(root_pitch=60, start_tick=0)
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Any
from enum import Enum
import random
import json
from pathlib import Path


# =============================================================================
# CORE DATA STRUCTURES
# =============================================================================

@dataclass
class Motif:
    """
    Represents a musical motif with intervals, rhythm, and metadata.
    
    A motif is interval-based (not pitch-based) so it can be transposed
    to any key or starting note.
    
    Attributes:
        name: Human-readable motif name
        intervals: List of semitone intervals from root (e.g., [0, 2, 4, 5])
        rhythm: List of note durations in beats (e.g., [0.5, 0.5, 1.0, 1.0])
        accent_pattern: Velocity weights 0.0-1.0 for each note
        genre_tags: Tags for filtering (e.g., ["jazz", "bebop", "ii-V-I"])
        chord_context: Optional chord type this works over (e.g., "dominant7")
        description: Human-readable description of the motif
    """
    name: str
    intervals: List[int]  # Semitone intervals from root
    rhythm: List[float]   # Durations in beats
    accent_pattern: List[float] = field(default_factory=list)
    genre_tags: List[str] = field(default_factory=list)
    chord_context: Optional[str] = None
    description: str = ""
    
    def __post_init__(self):
        """Validate and initialize defaults."""
        if not self.intervals:
            raise ValueError("Motif must have at least one interval")
        
        if not self.rhythm:
            raise ValueError("Motif must have rhythm pattern")
        
        if len(self.intervals) != len(self.rhythm):
            raise ValueError(f"Intervals ({len(self.intervals)}) and rhythm ({len(self.rhythm)}) must have same length")
        
        # Initialize accent pattern if empty (default to equal accents)
        if not self.accent_pattern:
            self.accent_pattern = [1.0] * len(self.intervals)
        
        if len(self.accent_pattern) != len(self.intervals):
            raise ValueError("Accent pattern must match intervals length")
    
    def to_midi_notes(
        self,
        root_pitch: int,
        start_tick: int,
        ticks_per_beat: int = 480,
        base_velocity: int = 90
    ) -> List[Tuple[int, int, int, int]]:
        """
        Convert motif to MIDI notes starting from a root pitch.
        
        Args:
            root_pitch: MIDI note number to start from (e.g., 60 for C4)
            start_tick: Starting tick position
            ticks_per_beat: Ticks per beat (default 480)
            base_velocity: Base velocity for notes (modified by accent_pattern)
            
        Returns:
            List of (tick, duration_ticks, pitch, velocity) tuples
        """
        notes = []
        current_tick = start_tick
        
        for interval, duration, accent in zip(self.intervals, self.rhythm, self.accent_pattern):
            pitch = root_pitch + interval
            duration_ticks = int(duration * ticks_per_beat)
            velocity = int(base_velocity * accent)
            
            # Clamp values to valid MIDI ranges
            pitch = max(0, min(127, pitch))
            velocity = max(1, min(127, velocity))
            
            notes.append((current_tick, duration_ticks, pitch, velocity))
            current_tick += duration_ticks
        
        return notes
    
    def transpose(self, semitones: int) -> 'Motif':
        """
        Transpose motif by semitones.
        
        Returns a new Motif with transposed intervals.
        """
        new_intervals = [i + semitones for i in self.intervals]
        return Motif(
            name=f"{self.name} (transposed {semitones:+d})",
            intervals=new_intervals,
            rhythm=self.rhythm.copy(),
            accent_pattern=self.accent_pattern.copy(),
            genre_tags=self.genre_tags.copy(),
            chord_context=self.chord_context,
            description=self.description
        )
    
    def invert(self, pivot: int = 0) -> 'Motif':
        """
        Invert the motif (mirror intervals around pivot point).
        
        Example: [0, 2, 4, 7] inverted around 0 becomes [0, -2, -4, -7]
        
        Args:
            pivot: The interval to invert around (default 0 = root)
            
        Returns:
            New Motif with inverted intervals
        """
        # Inversion formula: pivot - (interval - pivot) = 2*pivot - interval
        new_intervals = [2 * pivot - interval for interval in self.intervals]
        return Motif(
            name=f"{self.name} (inverted)",
            intervals=new_intervals,
            rhythm=self.rhythm.copy(),
            accent_pattern=self.accent_pattern.copy(),
            genre_tags=self.genre_tags.copy(),
            chord_context=self.chord_context,
            description=self.description
        )
    
    def retrograde(self) -> 'Motif':
        """
        Reverse the motif (play backwards).
        
        Example: intervals [0, 2, 4, 7], rhythm [0.5, 0.5, 0.5, 1.0]
                 becomes [7, 4, 2, 0], rhythm [1.0, 0.5, 0.5, 0.5]
        
        Returns:
            New Motif with reversed intervals and rhythm
        """
        return Motif(
            name=f"{self.name} (retrograde)",
            intervals=self.intervals[::-1],
            rhythm=self.rhythm[::-1],
            accent_pattern=self.accent_pattern[::-1],
            genre_tags=self.genre_tags.copy(),
            chord_context=self.chord_context,
            description=self.description
        )
    
    def augment(self, factor: float = 2.0) -> 'Motif':
        """
        Augment the motif (stretch rhythm by factor).
        
        Example: rhythm [0.5, 0.5, 1.0] with factor 2.0
                 becomes [1.0, 1.0, 2.0]
        
        Args:
            factor: Multiplication factor for durations (>1 = slower, <1 = faster)
            
        Returns:
            New Motif with augmented rhythm
        """
        new_rhythm = [duration * factor for duration in self.rhythm]
        return Motif(
            name=f"{self.name} (augmented x{factor})",
            intervals=self.intervals.copy(),
            rhythm=new_rhythm,
            accent_pattern=self.accent_pattern.copy(),
            genre_tags=self.genre_tags.copy(),
            chord_context=self.chord_context,
            description=self.description
        )
    
    def diminish(self, factor: float = 2.0) -> 'Motif':
        """
        Diminish the motif (compress rhythm by factor).
        
        Shorthand for augment(1/factor).
        
        Args:
            factor: Division factor for durations
            
        Returns:
            New Motif with diminished rhythm
        """
        return self.augment(1.0 / factor)
    
    def sequence(self, steps: List[int], scale_intervals: Optional[List[int]] = None) -> List['Motif']:
        """
        Create a sequence of the motif at different pitch levels.
        
        Example: motif sequenced at steps [0, 2, 4] creates 3 copies
                 transposed by those intervals
        
        Args:
            steps: List of transposition intervals (semitones if chromatic,
                   scale degrees if scale_intervals is provided)
            scale_intervals: Optional scale interval pattern for diatonic sequences
                           (e.g., [2,2,1,2,2,2,1] for major scale).
                           When provided, steps are interpreted as scale degrees
                           and transposition follows the scale structure.
            
        Returns:
            List of transposed Motif instances
        """
        result = []
        if scale_intervals is not None:
            # Diatonic sequencing: interpret steps as scale degrees
            cumulative = [0]
            for si in scale_intervals:
                cumulative.append(cumulative[-1] + si)
            octave_size = cumulative[-1]  # typically 12
            degree_count = len(scale_intervals)
            for step in steps:
                # Convert scale-degree step to semitone transposition
                abs_step = abs(step)
                full_octaves, remainder = divmod(abs_step, degree_count)
                semitone_shift = full_octaves * octave_size + cumulative[remainder]
                if step < 0:
                    semitone_shift = -semitone_shift
                result.append(self.transpose(semitone_shift))
        else:
            # Chromatic: exact semitone transposition
            for step in steps:
                result.append(self.transpose(step))
        return result
    
    def retrograde_inversion(self, pivot: int = 0) -> 'Motif':
        """Retrograde inversion: reverse note order then mirror intervals."""
        return self.retrograde().invert(pivot)

    def fragment(self, start: int = 0, length: Optional[int] = None) -> 'Motif':
        """Extract a fragment of the motif from start index for length notes."""
        end = (start + length) if length is not None else len(self.intervals)
        end = min(end, len(self.intervals))
        start = max(0, start)
        if start >= end:
            return Motif(intervals=[0], rhythm=[1.0], name=f"{self.name}_frag")
        return Motif(
            intervals=list(self.intervals[start:end]),
            rhythm=list(self.rhythm[start:end]),
            accent_pattern=list(self.accent_pattern[start:end]) if self.accent_pattern else None,
            name=f"{self.name}_frag",
            genre_tags=self.genre_tags,
            chord_context=self.chord_context,
        )

    def ornament(self, density: float = 0.3, seed: Optional[int] = None) -> 'Motif':
        """Add passing tones and neighbor notes between intervals."""
        import random
        rng = random.Random(seed)
        new_intervals = []
        new_rhythm = []
        new_accents = []
        for i, (interval, dur) in enumerate(zip(self.intervals, self.rhythm)):
            new_intervals.append(interval)
            accent = self.accent_pattern[i] if self.accent_pattern and i < len(self.accent_pattern) else 1.0
            new_accents.append(accent)
            if rng.random() < density and dur >= 0.5:
                # Split duration: original gets 2/3, ornament gets 1/3
                main_dur = dur * 2 / 3
                orn_dur = dur / 3
                new_rhythm.append(main_dur)
                # Add neighbor tone (step up or down)
                direction = rng.choice([-1, 1])
                new_intervals.append(interval + direction)
                new_rhythm.append(orn_dur)
                new_accents.append(accent * 0.6)  # Softer ornament
            else:
                new_rhythm.append(dur)
        return Motif(
            intervals=new_intervals,
            rhythm=new_rhythm,
            accent_pattern=new_accents,
            name=f"{self.name}_orn",
            genre_tags=self.genre_tags,
            chord_context=self.chord_context,
        )

    def displace(self, offset: float = 0.5) -> 'Motif':
        """Rhythmic displacement: shift start by offset beats.

        Prepends a rest (interval=0) of ``offset`` duration and trims the last note.
        """
        offset = max(0.125, offset)  # guard against negative/zero
        new_rhythm = [offset] + list(self.rhythm)
        new_intervals = [0] + list(self.intervals)  # Rest note
        new_accents = [0.0] + (list(self.accent_pattern) if self.accent_pattern else [1.0] * len(self.intervals))
        # Trim to preserve total duration: shorten last note
        total_original = sum(self.rhythm)
        total_new = sum(new_rhythm)
        if total_new > total_original and len(new_rhythm) > 1:
            excess = total_new - total_original
            new_rhythm[-1] = max(0.25, new_rhythm[-1] - excess)
        return Motif(
            intervals=new_intervals,
            rhythm=new_rhythm,
            accent_pattern=new_accents,
            name=f"{self.name}_disp",
            genre_tags=self.genre_tags,
            chord_context=self.chord_context,
        )

    def get_related_motifs(self, count: int = 4, seed: Optional[int] = None) -> List['Motif']:
        """Return count varied but thematically connected motifs."""
        import random
        rng = random.Random(seed)
        transforms = [
            lambda m: m.invert(),
            lambda m: m.retrograde(),
            lambda m: m.augment(1.5),
            lambda m: m.diminish(1.5),
            lambda m: m.transpose(rng.choice([-3, -2, 2, 3, 5, 7])),
            lambda m: m.fragment(0, max(2, len(m.intervals) // 2)),
            lambda m: m.ornament(0.3, seed=rng.randint(0, 9999)),
            lambda m: m.retrograde_inversion(),
            lambda m: m.displace(0.5),
        ]
        rng.shuffle(transforms)
        results = []
        for i in range(min(count, len(transforms))):
            try:
                result = transforms[i](self)
                results.append(result)
            except Exception:
                continue
        return results

    def get_total_duration(self) -> float:
        """Get total duration of motif in beats."""
        return sum(self.rhythm)
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            'name': self.name,
            'intervals': self.intervals,
            'rhythm': self.rhythm,
            'accent_pattern': self.accent_pattern,
            'genre_tags': self.genre_tags,
            'chord_context': self.chord_context,
            'description': self.description
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Motif':
        """Deserialize from dictionary."""
        return cls(
            name=data['name'],
            intervals=data['intervals'],
            rhythm=data['rhythm'],
            accent_pattern=data.get('accent_pattern', []),
            genre_tags=data.get('genre_tags', []),
            chord_context=data.get('chord_context'),
            description=data.get('description', '')
        )


# =============================================================================
# MOTIF LIBRARY
# =============================================================================

class MotifLibrary:
    """
    Storage and retrieval system for motifs.
    
    Provides filtering by genre, chord type, and tags.
    """
    
    def __init__(self):
        self.motifs: List[Motif] = []
        self._index_by_genre: Dict[str, List[Motif]] = {}
        self._index_by_chord: Dict[str, List[Motif]] = {}
    
    def add_motif(self, motif: Motif) -> None:
        """Add a motif to the library."""
        self.motifs.append(motif)
        
        # Update genre index
        for tag in motif.genre_tags:
            if tag not in self._index_by_genre:
                self._index_by_genre[tag] = []
            self._index_by_genre[tag].append(motif)
        
        # Update chord index
        if motif.chord_context:
            if motif.chord_context not in self._index_by_chord:
                self._index_by_chord[motif.chord_context] = []
            self._index_by_chord[motif.chord_context].append(motif)
    
    def get_motifs_for_genre(self, genre: str) -> List[Motif]:
        """Get all motifs tagged with a specific genre."""
        return self._index_by_genre.get(genre, [])
    
    def get_motifs_for_chord(self, chord_type: str) -> List[Motif]:
        """Get all motifs that work over a specific chord type."""
        return self._index_by_chord.get(chord_type, [])
    
    def get_motifs_with_tags(self, tags: List[str]) -> List[Motif]:
        """Get motifs that have ALL specified tags."""
        if not tags:
            return self.motifs.copy()
        
        result = []
        for motif in self.motifs:
            if all(tag in motif.genre_tags for tag in tags):
                result.append(motif)
        return result
    
    def get_random_motif(
        self,
        genre: Optional[str] = None,
        chord_type: Optional[str] = None,
        tags: Optional[List[str]] = None
    ) -> Optional[Motif]:
        """
        Get a random motif matching the criteria.
        
        Args:
            genre: Optional genre filter
            chord_type: Optional chord type filter
            tags: Optional tag filter (must match all)
            
        Returns:
            Random matching motif, or None if no matches
        """
        candidates = self.motifs.copy()
        
        # Filter by genre
        if genre:
            candidates = [m for m in candidates if genre in m.genre_tags]
        
        # Filter by chord
        if chord_type:
            candidates = [m for m in candidates if m.chord_context == chord_type]
        
        # Filter by tags
        if tags:
            candidates = [m for m in candidates if all(t in m.genre_tags for t in tags)]
        
        if not candidates:
            return None
        
        return random.choice(candidates)
    
    def save_to_file(self, path: str) -> None:
        """Save library to JSON file."""
        data = {
            'motifs': [m.to_dict() for m in self.motifs]
        }
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
    
    @classmethod
    def load_from_file(cls, path: str) -> 'MotifLibrary':
        """Load library from JSON file."""
        library = cls()
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        for motif_data in data.get('motifs', []):
            motif = Motif.from_dict(motif_data)
            library.add_motif(motif)
        
        return library
    
    def __len__(self) -> int:
        """Return number of motifs in library."""
        return len(self.motifs)


# =============================================================================
# MOTIF GENERATOR
# =============================================================================

class MotifGenerator:
    """
    Generates motifs based on genre rules and musical context.
    
    The generator can create new motifs algorithmically or select
    from a library of pre-defined patterns.
    """
    
    def __init__(self, library: Optional[MotifLibrary] = None):
        """
        Initialize motif generator.
        
        Args:
            library: Optional MotifLibrary to draw from. If None, uses built-in patterns.
        """
        self.library = library or self._create_default_library()
    
    def generate_motif(
        self,
        genre: str,
        context: Dict[str, Any]
    ) -> Motif:
        """
        Generate a motif for the given genre and context.
        
        Args:
            genre: Genre identifier (e.g., "jazz", "hip-hop")
            context: Musical context dict with optional keys:
                - chord_type: Chord type (e.g., "dominant7", "minor7", "major7")
                - scale: Scale to use (e.g., "major", "minor", "dorian")
                - mood: Mood descriptor (e.g., "bright", "dark", "tense")
                - complexity: Complexity level 0.0-1.0
                
        Returns:
            Generated or selected Motif
        """
        chord_type = context.get('chord_type')
        
        # Try to get motif from library first
        motif = self.library.get_random_motif(
            genre=genre,
            chord_type=chord_type
        )
        
        if motif:
            return motif
        
        # Fallback: generate algorithmically based on genre
        if genre == "jazz":
            return self._generate_jazz_motif(context)
        else:
            # Generic motif for unsupported genres
            return self._generate_generic_motif(context)
    
    def get_jazz_motifs(self) -> List[Motif]:
        """Get all jazz-specific motifs from the library."""
        return self.library.get_motifs_for_genre("jazz")
    
    def _generate_jazz_motif(self, context: Dict[str, Any]) -> Motif:
        """
        Generate a jazz-style motif algorithmically.
        
        This is a fallback when no pre-defined motif matches.
        """
        chord_type = context.get('chord_type', 'major7')
        
        # Simple bebop-style ascending pattern
        if chord_type in ['dominant7', 'dom7']:
            # Dominant: root, 3rd, 5th, b7
            intervals = [0, 4, 7, 10]
            rhythm = [0.5, 0.5, 0.5, 0.5]
            accents = [1.0, 0.8, 0.9, 0.85]
        elif chord_type in ['minor7', 'm7']:
            # Minor7: root, b3, 5th, b7
            intervals = [0, 3, 7, 10]
            rhythm = [0.5, 0.5, 0.5, 0.5]
            accents = [1.0, 0.8, 0.9, 0.85]
        else:
            # Major7: root, 3rd, 5th, 7th
            intervals = [0, 4, 7, 11]
            rhythm = [0.5, 0.5, 0.5, 0.5]
            accents = [1.0, 0.8, 0.9, 0.85]
        
        return Motif(
            name=f"Jazz {chord_type} arpeggio",
            intervals=intervals,
            rhythm=rhythm,
            accent_pattern=accents,
            genre_tags=["jazz"],
            chord_context=chord_type,
            description=f"Algorithmically generated jazz motif over {chord_type}"
        )
    
    def _generate_generic_motif(self, context: Dict[str, Any]) -> Motif:
        """Generate a generic motif when genre is not specifically supported."""
        # Simple scalar pattern
        intervals = [0, 2, 4, 5]
        rhythm = [1.0, 0.5, 0.5, 1.0]
        accents = [1.0, 0.8, 0.8, 0.9]
        
        return Motif(
            name="Generic motif",
            intervals=intervals,
            rhythm=rhythm,
            accent_pattern=accents,
            genre_tags=["generic"],
            description="Generic melodic motif"
        )
    
    def _create_default_library(self) -> MotifLibrary:
        """
        Create default motif library with built-in patterns.
        
        This loads motifs from the motifs/ submodule.
        """
        library = MotifLibrary()
        
        # Try to load jazz motifs
        try:
            from .motifs import jazz_motifs
            for motif in jazz_motifs.get_jazz_motifs():
                library.add_motif(motif)
        except ImportError:
            # If jazz_motifs module doesn't exist yet, that's okay
            # We'll still have the algorithmic fallback
            pass
        
        # Try to load common motifs
        try:
            from .motifs import common_motifs
            for motif in common_motifs.get_common_motifs():
                library.add_motif(motif)
        except ImportError:
            pass
        
        return library


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def create_motif(
    name: str,
    intervals: List[int],
    rhythm: List[float],
    genre_tags: List[str],
    accent_pattern: Optional[List[float]] = None,
    chord_context: Optional[str] = None,
    description: str = ""
) -> Motif:
    """
    Convenience function to create a motif.
    
    Args:
        name: Motif name
        intervals: Semitone intervals from root
        rhythm: Beat durations
        genre_tags: Genre classification tags
        accent_pattern: Optional velocity weights (auto-generated if None)
        chord_context: Optional chord type
        description: Optional description
        
    Returns:
        New Motif instance
    """
    return Motif(
        name=name,
        intervals=intervals,
        rhythm=rhythm,
        accent_pattern=accent_pattern or [1.0] * len(intervals),
        genre_tags=genre_tags,
        chord_context=chord_context,
        description=description
    )


# =============================================================================
# MODULE TEST
# =============================================================================

if __name__ == '__main__':
    print("=== Motif Engine Test ===\n")
    
    # Test Motif class
    print("1. Creating a bebop motif...")
    bebop_motif = Motif(
        name="Bebop enclosure",
        intervals=[0, 2, 1, 0],  # Chromatic enclosure
        rhythm=[0.25, 0.25, 0.25, 0.25],
        accent_pattern=[0.9, 0.7, 0.8, 1.0],
        genre_tags=["jazz", "bebop"],
        description="Chromatic enclosure approaching target note"
    )
    print(f"   Name: {bebop_motif.name}")
    print(f"   Duration: {bebop_motif.get_total_duration()} beats")
    print(f"   Tags: {bebop_motif.genre_tags}")
    
    # Test MIDI conversion
    print("\n2. Converting to MIDI notes (root: C4 = 60)...")
    notes = bebop_motif.to_midi_notes(root_pitch=60, start_tick=0)
    for tick, dur, pitch, vel in notes:
        print(f"   Tick {tick:4d}: pitch {pitch:3d}, duration {dur:3d}, velocity {vel:3d}")
    
    # Test MotifLibrary
    print("\n3. Testing MotifLibrary...")
    library = MotifLibrary()
    library.add_motif(bebop_motif)
    
    # Add another motif
    ii_v_motif = Motif(
        name="ii-V approach",
        intervals=[0, 2, 4, 7],
        rhythm=[0.5, 0.5, 0.5, 0.5],
        genre_tags=["jazz", "ii-V-I"],
        chord_context="minor7",
        description="Classic ii-V approach pattern"
    )
    library.add_motif(ii_v_motif)
    
    print(f"   Library size: {len(library)} motifs")
    print(f"   Jazz motifs: {len(library.get_motifs_for_genre('jazz'))}")
    
    # Test MotifGenerator
    print("\n4. Testing MotifGenerator...")
    generator = MotifGenerator(library)
    
    # Generate jazz motif
    jazz_motif = generator.generate_motif("jazz", {"chord_type": "dominant7"})
    print(f"   Generated: {jazz_motif.name}")
    print(f"   Intervals: {jazz_motif.intervals}")
    print(f"   Rhythm: {jazz_motif.rhythm}")
    
    # Get all jazz motifs
    all_jazz = generator.get_jazz_motifs()
    print(f"   Total jazz motifs available: {len(all_jazz)}")
    
    print("\n✅ Motif engine test complete!")
