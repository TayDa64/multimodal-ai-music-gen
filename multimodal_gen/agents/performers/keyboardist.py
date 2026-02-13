"""
KeyboardistAgent - Masterclass Keyboard Performer

This module implements a professional keyboardist agent with deep knowledge of:
- Voicing Theory: Root position, inversions, shell voicings, drop 2, open/close
- Voice Leading: Minimal movement between chords for smooth transitions
- Chord Types: Triads, 7ths, extended chords (9th, 11th, 13th), suspensions
- Comping Styles: Genre-specific patterns from trap to jazz to Ethiopian
- Rhythmic Patterns: Whole note pads, quarter comping, syncopated stabs, arpeggios

The KeyboardistAgent understands harmonic context and generates musically-informed
keyboard parts that complement the rhythm section while adding harmonic color.

Architecture Notes:
    This is a Stage 1 (offline) implementation with comprehensive music theory.
    Stage 2 will add API-backed generation capabilities for creative variation.

Musical Reference:
    Standard keyboard MIDI channel: 0 (Piano)
    Common ranges:
    - Piano low: C2-C4 (left hand voicings)
    - Piano mid: C3-C5 (comping range)
    - Piano high: C4-C6 (melodic fills, runs)
    - Rhodes/Keys: C3-C5 (warm zone)

Example:
    ```python
    from multimodal_gen.agents.performers import KeyboardistAgent
    from multimodal_gen.agents import PerformanceContext, KEYIST_PRESETS
    
    keyboardist = KeyboardistAgent()
    keyboardist.set_personality(KEYIST_PRESETS['jazz_voicings'])
    
    result = keyboardist.perform(context, section)
    print(f"Generated {len(result.notes)} keyboard notes")
    print(f"Decisions: {result.decisions_made}")
    ```
"""

from typing import List, Optional, Dict, Any, Tuple
import random
import logging
from copy import deepcopy

from ..base import IPerformerAgent, AgentRole, PerformanceResult
from ..context import PerformanceContext
from ..personality import AgentPersonality, KEYIST_PRESETS, get_personality_for_role

# Import existing infrastructure
from ...arranger import SongSection, SectionType
from ...midi_generator import NoteEvent
from ...utils import (
    TICKS_PER_BEAT,
    TICKS_PER_8TH,
    TICKS_PER_16TH,
    TICKS_PER_BAR_4_4,
    ScaleType,
    humanize_velocity,
    humanize_timing,
    beats_to_ticks,
    get_scale_notes,
    note_name_to_midi,
    midi_to_note_name,
    get_chord_notes,
)

logger = logging.getLogger(__name__)


# =============================================================================
# VOICING THEORY KNOWLEDGE BASE
# =============================================================================

class VoicingTheory:
    """
    Masterclass voicing theory knowledge.
    
    Contains all voicing types with MIDI note calculations:
    - Root position (1-3-5)
    - First inversion (3-5-1)
    - Second inversion (5-1-3)
    - Shell voicings (1-3-7) for jazz
    - Drop 2 voicings (spread across octaves)
    - Open voicings vs close voicings
    
    Voice leading principles are applied to minimize movement
    between successive chords.
    """
    
    # Voicing types and their characteristics
    VOICING_TYPES = {
        'root_position': {
            'description': 'Standard closed voicing with root in bass',
            'complexity': 0.2,
            'spread': 'close',
            'use_cases': ['pop', 'rock', 'simple'],
        },
        'first_inversion': {
            'description': '3rd in bass, smoother voice leading',
            'complexity': 0.3,
            'spread': 'close',
            'use_cases': ['pop', 'ballad', 'transitional'],
        },
        'second_inversion': {
            'description': '5th in bass, creates tension/resolution',
            'complexity': 0.3,
            'spread': 'close',
            'use_cases': ['cadence', 'passing', 'pedal_point'],
        },
        'shell_voicing': {
            'description': 'Just root, 3rd, 7th - clean jazz sound',
            'complexity': 0.5,
            'spread': 'open',
            'use_cases': ['jazz', 'lofi', 'neo_soul'],
        },
        'drop_2': {
            'description': 'Second-highest note dropped an octave - wide, rich',
            'complexity': 0.6,
            'spread': 'open',
            'use_cases': ['jazz', 'r&b', 'neo_soul'],
        },
        'drop_3': {
            'description': 'Third-highest note dropped - very wide spread',
            'complexity': 0.7,
            'spread': 'wide',
            'use_cases': ['big_band', 'orchestral'],
        },
        'quartal': {
            'description': 'Built in 4ths - modern, ambiguous',
            'complexity': 0.7,
            'spread': 'open',
            'use_cases': ['jazz', 'fusion', 'modern'],
        },
        'cluster': {
            'description': 'Close seconds/thirds - dense, tension',
            'complexity': 0.8,
            'spread': 'very_close',
            'use_cases': ['jazz', 'avant_garde', 'tension'],
        },
    }
    
    # Optimal octave ranges for different voicing types
    VOICING_RANGES = {
        'close': (48, 72),      # C3-C5: Warm, clear
        'open': (36, 72),       # C2-C5: Wide, full
        'wide': (36, 84),       # C2-C6: Very wide
        'very_close': (55, 67), # G3-G4: Cluster range
    }
    
    @classmethod
    def get_root_position(cls, root: int, intervals: List[int]) -> List[int]:
        """
        Get root position voicing.
        
        Args:
            root: Root note MIDI number
            intervals: Chord intervals from root
            
        Returns:
            List of MIDI notes in root position
        """
        return [root + i for i in intervals]
    
    @classmethod
    def get_first_inversion(cls, root: int, intervals: List[int]) -> List[int]:
        """
        Get first inversion (3rd in bass).
        
        Args:
            root: Root note MIDI number
            intervals: Chord intervals from root
            
        Returns:
            List of MIDI notes with 3rd in bass
        """
        if len(intervals) < 2:
            return cls.get_root_position(root, intervals)
        
        # Move root up an octave, keep 3rd at bottom
        notes = cls.get_root_position(root, intervals)
        notes[0] += 12  # Root up an octave
        return sorted(notes)
    
    @classmethod
    def get_second_inversion(cls, root: int, intervals: List[int]) -> List[int]:
        """
        Get second inversion (5th in bass).
        
        Args:
            root: Root note MIDI number
            intervals: Chord intervals from root
            
        Returns:
            List of MIDI notes with 5th in bass
        """
        if len(intervals) < 3:
            return cls.get_first_inversion(root, intervals)
        
        # Move root and 3rd up an octave
        notes = cls.get_root_position(root, intervals)
        notes[0] += 12
        notes[1] += 12
        return sorted(notes)
    
    @classmethod
    def get_shell_voicing(cls, root: int, intervals: List[int]) -> List[int]:
        """
        Get shell voicing (root, 3rd, 7th only).
        
        Shell voicings omit the 5th for clarity, keeping only
        the essential chord tones that define quality.
        
        Args:
            root: Root note MIDI number
            intervals: Chord intervals from root
            
        Returns:
            List of MIDI notes for shell voicing
        """
        # Find 3rd and 7th intervals
        third = None
        seventh = None
        
        for i in intervals:
            if i in [3, 4]:  # minor/major 3rd
                third = i
            elif i in [10, 11]:  # minor/major 7th
                seventh = i
        
        notes = [root]
        if third is not None:
            notes.append(root + third)
        if seventh is not None:
            notes.append(root + seventh)
        
        # If no 7th, add the 5th back
        if seventh is None and 7 in intervals:
            notes.append(root + 7)
        
        return sorted(notes)
    
    @classmethod
    def get_drop_2_voicing(cls, root: int, intervals: List[int]) -> List[int]:
        """
        Get drop 2 voicing.
        
        In a drop 2 voicing, the second-highest note is dropped
        down an octave, creating a wider spread with the bass
        note separated from the upper structure.
        
        Args:
            root: Root note MIDI number  
            intervals: Chord intervals from root
            
        Returns:
            List of MIDI notes in drop 2 voicing
        """
        if len(intervals) < 4:
            # For triads, use open position instead
            return cls.get_open_voicing(root, intervals)
        
        # Get close position first
        notes = cls.get_root_position(root, intervals)
        notes = sorted(notes)
        
        # Drop second-highest note down an octave
        if len(notes) >= 2:
            notes[-2] -= 12
        
        return sorted(notes)
    
    @classmethod
    def get_open_voicing(cls, root: int, intervals: List[int]) -> List[int]:
        """
        Get open voicing (spread across octaves).
        
        Open voicings distribute notes more widely, creating
        a fuller, more orchestral sound.
        
        Args:
            root: Root note MIDI number
            intervals: Chord intervals from root
            
        Returns:
            List of MIDI notes in open position
        """
        notes = []
        notes.append(root)  # Bass note
        
        for i, interval in enumerate(intervals[1:], 1):
            # Alternate octave placement
            octave_offset = 12 if i % 2 == 0 else 0
            notes.append(root + interval + octave_offset)
        
        return sorted(notes)
    
    @classmethod
    def get_quartal_voicing(cls, root: int, num_notes: int = 4) -> List[int]:
        """
        Get quartal voicing (built in perfect 4ths).
        
        Quartal voicings create a modern, ambiguous sound that
        works well in jazz, fusion, and contemporary styles.
        
        Args:
            root: Root note MIDI number
            num_notes: Number of notes in the voicing
            
        Returns:
            List of MIDI notes in quartal stack
        """
        notes = [root]
        for i in range(1, num_notes):
            notes.append(root + (5 * i))  # Perfect 4th = 5 semitones
        return notes
    
    @classmethod
    def apply_voicing(
        cls,
        root: int,
        intervals: List[int],
        voicing_type: str,
        target_octave: int = 4
    ) -> List[int]:
        """
        Apply a voicing type to a chord.
        
        Args:
            root: Root note (just the pitch class, will be placed in octave)
            intervals: Chord intervals from root
            voicing_type: One of the VOICING_TYPES keys
            target_octave: Target octave for the voicing
            
        Returns:
            List of MIDI notes with voicing applied
        """
        # Place root in target octave
        root_in_octave = (root % 12) + (target_octave + 1) * 12
        
        voicing_methods = {
            'root_position': cls.get_root_position,
            'first_inversion': cls.get_first_inversion,
            'second_inversion': cls.get_second_inversion,
            'shell_voicing': cls.get_shell_voicing,
            'drop_2': cls.get_drop_2_voicing,
            'open': cls.get_open_voicing,
            'quartal': lambda r, i: cls.get_quartal_voicing(r, len(i)),
        }
        
        method = voicing_methods.get(voicing_type, cls.get_root_position)
        return method(root_in_octave, intervals)


# =============================================================================
# CHORD BUILDER
# =============================================================================

class ChordBuilder:
    """
    Constructs any chord type from root note.
    
    Supports:
    - Major/minor triads
    - 7th chords (maj7, min7, dom7, dim7, m7b5)
    - Extended chords (9th, 11th, 13th)
    - Suspended chords (sus2, sus4)
    - Add chords (add9, add11)
    - Altered chords (7#9, 7b9, etc.)
    """
    
    # Comprehensive chord intervals from root
    CHORD_INTERVALS = {
        # Triads
        'major': [0, 4, 7],
        'minor': [0, 3, 7],
        'dim': [0, 3, 6],
        'aug': [0, 4, 8],
        
        # Suspended
        'sus2': [0, 2, 7],
        'sus4': [0, 5, 7],
        '7sus4': [0, 5, 7, 10],
        
        # Seventh chords
        'maj7': [0, 4, 7, 11],
        'min7': [0, 3, 7, 10],
        'm7': [0, 3, 7, 10],
        'dom7': [0, 4, 7, 10],
        '7': [0, 4, 7, 10],
        'dim7': [0, 3, 6, 9],
        'm7b5': [0, 3, 6, 10],  # Half-diminished
        'minmaj7': [0, 3, 7, 11],
        
        # Extended chords
        'maj9': [0, 4, 7, 11, 14],
        'min9': [0, 3, 7, 10, 14],
        'm9': [0, 3, 7, 10, 14],
        '9': [0, 4, 7, 10, 14],  # Dominant 9
        'add9': [0, 4, 7, 14],
        'madd9': [0, 3, 7, 14],
        
        # 11th chords
        'maj11': [0, 4, 7, 11, 14, 17],
        'min11': [0, 3, 7, 10, 14, 17],
        'm11': [0, 3, 7, 10, 14, 17],
        '11': [0, 4, 7, 10, 14, 17],
        'add11': [0, 4, 7, 17],
        
        # 13th chords
        'maj13': [0, 4, 7, 11, 14, 21],
        'min13': [0, 3, 7, 10, 14, 21],
        '13': [0, 4, 7, 10, 14, 21],
        
        # Altered dominants
        '7b9': [0, 4, 7, 10, 13],
        '7#9': [0, 4, 7, 10, 15],
        '7#11': [0, 4, 7, 10, 18],
        '7alt': [0, 4, 6, 10, 13, 15],
        
        # Special voicings
        '6': [0, 4, 7, 9],
        'm6': [0, 3, 7, 9],
        '69': [0, 4, 7, 9, 14],
        'm69': [0, 3, 7, 9, 14],
        'power': [0, 7],  # Power chord (rock)
    }
    
    # Chord quality parsing
    QUALITY_ALIASES = {
        'M': 'major',
        'm': 'minor',
        '-': 'minor',
        '+': 'aug',
        'o': 'dim',
        'ø': 'm7b5',
        'Δ': 'maj7',
        'Δ7': 'maj7',
    }
    
    @classmethod
    def parse_chord_symbol(cls, chord_symbol: str) -> Tuple[str, str]:
        """
        Parse a chord symbol into root and quality.
        
        Args:
            chord_symbol: Chord symbol like "Cm7", "F#maj9", "Bb7"
            
        Returns:
            Tuple of (root_name, quality)
        """
        if not chord_symbol:
            return ('C', 'minor')
        
        # Extract root note (first letter + optional accidental)
        root = chord_symbol[0].upper()
        rest = chord_symbol[1:]
        
        if rest and rest[0] in '#b':
            root += rest[0]
            rest = rest[1:]
        
        # Normalize quality
        quality = rest.lower() if rest else 'major'
        
        # Handle aliases
        if quality in cls.QUALITY_ALIASES:
            quality = cls.QUALITY_ALIASES[quality]
        elif quality in ['', 'maj']:
            quality = 'major'
        elif quality in ['min']:
            quality = 'minor'
        
        return (root, quality)
    
    @classmethod
    def get_intervals(cls, quality: str) -> List[int]:
        """
        Get intervals for a chord quality.
        
        Args:
            quality: Chord quality string
            
        Returns:
            List of semitone intervals from root
        """
        # Direct lookup
        if quality in cls.CHORD_INTERVALS:
            return cls.CHORD_INTERVALS[quality]
        
        # Try lowercase
        quality_lower = quality.lower()
        if quality_lower in cls.CHORD_INTERVALS:
            return cls.CHORD_INTERVALS[quality_lower]
        
        # Default to minor triad
        return cls.CHORD_INTERVALS['minor']
    
    @classmethod
    def build_chord(
        cls,
        root_name: str,
        quality: str,
        octave: int = 4
    ) -> Tuple[int, List[int], List[int]]:
        """
        Build a chord from root name and quality.
        
        Args:
            root_name: Root note name (e.g., 'C', 'F#')
            quality: Chord quality
            octave: Base octave
            
        Returns:
            Tuple of (root_midi, intervals, notes)
        """
        root_midi = note_name_to_midi(root_name, octave)
        intervals = cls.get_intervals(quality)
        notes = [root_midi + i for i in intervals]
        return (root_midi, intervals, notes)
    
    @classmethod
    def build_from_symbol(
        cls,
        chord_symbol: str,
        octave: int = 4
    ) -> Tuple[int, List[int], List[int]]:
        """
        Build a chord from a chord symbol.
        
        Args:
            chord_symbol: Full chord symbol (e.g., "Dm7", "Gmaj9")
            octave: Base octave
            
        Returns:
            Tuple of (root_midi, intervals, notes)
        """
        root_name, quality = cls.parse_chord_symbol(chord_symbol)
        return cls.build_chord(root_name, quality, octave)


# =============================================================================
# VOICE LEADER
# =============================================================================

class VoiceLeader:
    """
    Smooth transitions between chords using voice leading principles.
    
    Voice leading minimizes the movement of individual voices between
    chords, creating smoother, more professional-sounding progressions.
    
    Principles applied:
    - Minimize total distance (sum of semitone movements)
    - Prefer common tones (notes that stay the same)
    - Avoid parallel fifths/octaves where possible
    - Keep voices in singable ranges
    """
    
    MAX_VOICE_MOVEMENT = 7  # Max semitones a single voice should move
    
    @classmethod
    def calculate_movement_cost(
        cls,
        from_notes: List[int],
        to_notes: List[int]
    ) -> float:
        """
        Calculate the voice leading cost between two chords.
        
        Lower cost = smoother voice leading.
        
        Args:
            from_notes: Source chord notes
            to_notes: Target chord notes
            
        Returns:
            Voice leading cost (lower is better)
        """
        if not from_notes or not to_notes:
            return 100.0
        
        # Calculate centroid distance
        from_center = sum(from_notes) / len(from_notes)
        to_center = sum(to_notes) / len(to_notes)
        center_cost = abs(to_center - from_center) * 0.5
        
        # Calculate nearest-neighbor cost
        nn_cost = 0.0
        for note in to_notes:
            nearest_dist = min(abs(note - f) for f in from_notes)
            # Penalize large jumps more heavily
            if nearest_dist > cls.MAX_VOICE_MOVEMENT:
                nn_cost += nearest_dist * 2
            else:
                nn_cost += nearest_dist
        
        # Bonus for common tones
        common_tones = len(set(from_notes) & set(to_notes))
        common_bonus = common_tones * 2
        
        return center_cost + nn_cost - common_bonus
    
    @classmethod
    def find_best_voicing(
        cls,
        prev_notes: List[int],
        target_root: int,
        target_intervals: List[int],
        octave_range: Tuple[int, int] = (3, 5)
    ) -> List[int]:
        """
        Find the best voicing of a chord given the previous chord.
        
        Tries different inversions and octave placements to find
        the smoothest voice leading.
        
        Args:
            prev_notes: Previous chord notes
            target_root: Target chord root (pitch class 0-11)
            target_intervals: Target chord intervals
            octave_range: Range of octaves to try
            
        Returns:
            Best voiced chord notes
        """
        if not prev_notes:
            # No previous chord, use root position in middle octave
            mid_octave = (octave_range[0] + octave_range[1]) // 2
            root_midi = (target_root % 12) + (mid_octave + 1) * 12
            return [root_midi + i for i in target_intervals]
        
        best_notes = None
        best_cost = float('inf')
        
        # Try each octave in range
        for octave in range(octave_range[0], octave_range[1] + 1):
            root_midi = (target_root % 12) + (octave + 1) * 12
            
            # Try different voicing types
            voicings = [
                VoicingTheory.get_root_position(root_midi, target_intervals),
                VoicingTheory.get_first_inversion(root_midi, target_intervals),
                VoicingTheory.get_second_inversion(root_midi, target_intervals),
            ]
            
            for voicing in voicings:
                cost = cls.calculate_movement_cost(prev_notes, voicing)
                if cost < best_cost:
                    best_cost = cost
                    best_notes = voicing
        
        return best_notes or [target_root + i for i in target_intervals]
    
    @classmethod
    def voice_lead_progression(
        cls,
        chord_symbols: List[str],
        base_octave: int = 4
    ) -> List[List[int]]:
        """
        Apply voice leading to an entire chord progression.
        
        Args:
            chord_symbols: List of chord symbols
            base_octave: Starting octave
            
        Returns:
            List of voiced chords (each is a list of MIDI notes)
        """
        if not chord_symbols:
            return []
        
        voiced_chords = []
        prev_notes = None
        
        for symbol in chord_symbols:
            root_midi, intervals, _ = ChordBuilder.build_from_symbol(symbol, base_octave)
            
            if prev_notes is None:
                # First chord: use root position
                notes = VoicingTheory.get_root_position(root_midi, intervals)
            else:
                # Subsequent chords: voice lead from previous
                notes = cls.find_best_voicing(
                    prev_notes,
                    root_midi,
                    intervals,
                    octave_range=(base_octave - 1, base_octave + 1)
                )
            
            voiced_chords.append(notes)
            prev_notes = notes
        
        return voiced_chords


# =============================================================================
# COMPING PATTERNS
# =============================================================================

class CompingPatterns:
    """
    Genre-specific rhythm templates for keyboard comping.
    
    Each pattern defines when chords should be played within a bar,
    along with velocity and duration hints.
    
    Pattern format:
        List of (beat_position, velocity_mult, duration_mult, is_accent)
        
    Beat positions are 0-indexed (0 = beat 1, 1 = beat 2, etc.)
    """
    
    PATTERNS = {
        # Trap: Sparse piano stabs, dark minor chords
        'trap_sparse': {
            'description': 'Sparse stabs, let notes ring',
            'positions': [
                (0, 1.0, 2.0, True),      # Downbeat, sustain 2 beats
            ],
            'density': 0.2,
            'swing': 0.0,
        },
        'trap_zaytoven': {
            'description': 'Churchy piano runs, Zaytoven style',
            'positions': [
                (0, 0.95, 0.5, True),
                (0.5, 0.8, 0.5, False),
                (2, 0.9, 0.5, True),
                (2.5, 0.75, 0.5, False),
            ],
            'density': 0.5,
            'swing': 0.0,
        },
        
        # Lofi: Jazzy 7th chords with swing
        'lofi_jazzy': {
            'description': 'Swung 7th chords, Rhodes warmth',
            'positions': [
                (0, 0.85, 1.5, True),
                (2.5, 0.75, 1.0, False),
            ],
            'density': 0.4,
            'swing': 0.12,
        },
        'lofi_dusty': {
            'description': 'Mellow, sparse, nostalgic',
            'positions': [
                (0, 0.8, 3.0, True),
                (3.5, 0.6, 0.5, False),
            ],
            'density': 0.25,
            'swing': 0.08,
        },
        
        # R&B: Neo-soul voicings, 9th chords
        'rnb_neosoul': {
            'description': 'Rich extended chords, smooth transitions',
            'positions': [
                (0, 0.9, 1.0, True),
                (1.5, 0.7, 0.5, False),
                (2, 0.85, 1.0, True),
                (3.5, 0.65, 0.5, False),
            ],
            'density': 0.5,
            'swing': 0.05,
        },
        'rnb_slow': {
            'description': 'Sustained pads, emotional',
            'positions': [
                (0, 0.9, 4.0, True),
            ],
            'density': 0.2,
            'swing': 0.0,
        },
        
        # House: Stab chords, pumping 16ths
        'house_stab': {
            'description': 'Classic house piano stabs',
            'positions': [
                (0, 1.0, 0.25, True),
                (0.5, 0.8, 0.25, False),
                (1, 0.85, 0.25, False),
                (1.5, 0.8, 0.25, False),
                (2, 0.9, 0.25, True),
                (2.5, 0.75, 0.25, False),
                (3, 0.85, 0.25, False),
                (3.5, 0.8, 0.25, False),
            ],
            'density': 0.7,
            'swing': 0.0,
        },
        'house_offbeat': {
            'description': 'Offbeat chord stabs',
            'positions': [
                (0.5, 0.9, 0.4, True),
                (1.5, 0.85, 0.4, False),
                (2.5, 0.9, 0.4, True),
                (3.5, 0.85, 0.4, False),
            ],
            'density': 0.5,
            'swing': 0.0,
        },
        
        # G-Funk: Moog-style pads, whine leads
        'gfunk_pad': {
            'description': 'Sustained Moog pad, West Coast vibe',
            'positions': [
                (0, 0.85, 4.0, True),
            ],
            'density': 0.2,
            'swing': 0.1,
        },
        'gfunk_funk': {
            'description': 'Funky clavinet-style comping',
            'positions': [
                (0, 0.9, 0.5, True),
                (1.5, 0.8, 0.5, False),
                (2, 0.85, 0.5, True),
                (2.75, 0.7, 0.25, False),
                (3.5, 0.8, 0.5, False),
            ],
            'density': 0.55,
            'swing': 0.15,
        },
        
        # Ethiopian: Pentatonic krar-style
        'ethiopian_krar': {
            'description': 'Krar-style pentatonic strumming',
            'positions': [
                (0, 0.9, 0.5, True),
                (0.33, 0.7, 0.25, False),  # Compound meter feel
                (0.66, 0.75, 0.25, False),
                (1, 0.85, 0.5, True),
                (1.33, 0.7, 0.25, False),
                (1.66, 0.75, 0.25, False),
            ],
            'density': 0.6,
            'swing': 0.0,
        },
        'ethiopian_drone': {
            'description': 'Sustained drone with embellishments',
            'positions': [
                (0, 0.9, 3.5, True),
            ],
            'density': 0.15,
            'swing': 0.0,
        },
        
        # Jazz: Comping patterns
        'jazz_comp': {
            'description': 'Standard jazz comping',
            'positions': [
                (0, 0.8, 1.0, False),
                (2.5, 0.9, 1.0, True),
            ],
            'density': 0.4,
            'swing': 0.2,
        },
        'jazz_charleston': {
            'description': 'Charleston rhythm comping',
            'positions': [
                (0, 0.9, 0.75, True),
                (1.5, 0.85, 0.5, True),
            ],
            'density': 0.35,
            'swing': 0.18,
        },
        
        # Pad: Whole note sustained
        'pad_sustained': {
            'description': 'Full bar sustained pad',
            'positions': [
                (0, 0.7, 4.0, True),
            ],
            'density': 0.1,
            'swing': 0.0,
        },
        
        # Arpeggiated patterns
        'arp_16th': {
            'description': '16th note arpeggio',
            'positions': [
                (i * 0.25, 0.7 + (0.1 if i % 4 == 0 else 0), 0.2, i % 4 == 0)
                for i in range(16)
            ],
            'density': 0.9,
            'swing': 0.0,
            'is_arpeggio': True,
        },
        'arp_8th': {
            'description': '8th note arpeggio',
            'positions': [
                (i * 0.5, 0.75 + (0.15 if i % 2 == 0 else 0), 0.4, i % 2 == 0)
                for i in range(8)
            ],
            'density': 0.7,
            'swing': 0.0,
            'is_arpeggio': True,
        },
    }
    
    # Genre to pattern mapping
    GENRE_PATTERNS = {
        'trap': ['trap_sparse', 'trap_zaytoven'],
        'trap_soul': ['trap_sparse', 'rnb_neosoul'],
        'drill': ['trap_sparse'],
        'lofi': ['lofi_jazzy', 'lofi_dusty'],
        'rnb': ['rnb_neosoul', 'rnb_slow'],
        'house': ['house_stab', 'house_offbeat'],
        'g_funk': ['gfunk_pad', 'gfunk_funk'],
        'gfunk': ['gfunk_pad', 'gfunk_funk'],
        'ethiopian': ['ethiopian_krar', 'ethiopian_drone'],
        'ethiopian_traditional': ['ethiopian_krar', 'ethiopian_drone'],
        'ethio_jazz': ['ethiopian_krar', 'jazz_comp'],
        'eskista': ['ethiopian_krar'],
        'jazz': ['jazz_comp', 'jazz_charleston'],
        'gospel': ['rnb_neosoul', 'jazz_comp'],
        'default': ['pad_sustained', 'lofi_jazzy'],
    }
    
    @classmethod
    def get_pattern(cls, pattern_name: str) -> Dict[str, Any]:
        """Get a specific pattern by name."""
        return cls.PATTERNS.get(pattern_name, cls.PATTERNS['pad_sustained'])
    
    @classmethod
    def get_patterns_for_genre(cls, genre: str) -> List[str]:
        """Get available pattern names for a genre."""
        genre_lower = genre.lower().strip().replace('-', '_').replace(' ', '_')
        return cls.GENRE_PATTERNS.get(genre_lower, cls.GENRE_PATTERNS['default'])
    
    @classmethod
    def select_pattern_for_context(
        cls,
        genre: str,
        section_type: SectionType,
        complexity: float
    ) -> Dict[str, Any]:
        """
        Select the best pattern for the musical context.
        
        Args:
            genre: Genre string
            section_type: Type of section (intro, verse, chorus, etc.)
            complexity: Personality complexity (0-1)
            
        Returns:
            Selected pattern dictionary
        """
        available = cls.get_patterns_for_genre(genre)
        
        if not available:
            return cls.PATTERNS['pad_sustained']
        
        # Section-based selection
        if section_type in [SectionType.INTRO, SectionType.OUTRO]:
            # Prefer sparser patterns for intros/outros
            sparse_patterns = [p for p in available 
                            if cls.PATTERNS.get(p, {}).get('density', 1) < 0.4]
            if sparse_patterns:
                return cls.PATTERNS[random.choice(sparse_patterns)]
        
        elif section_type in [SectionType.DROP, SectionType.CHORUS]:
            # Prefer denser patterns for high-energy sections
            dense_patterns = [p for p in available 
                           if cls.PATTERNS.get(p, {}).get('density', 0) > 0.4]
            if dense_patterns:
                return cls.PATTERNS[random.choice(dense_patterns)]
        
        # Complexity-based filtering
        if complexity < 0.4:
            simple_patterns = [p for p in available 
                            if cls.PATTERNS.get(p, {}).get('density', 1) < 0.5]
            if simple_patterns:
                return cls.PATTERNS[random.choice(simple_patterns)]
        
        # Default: random from available
        return cls.PATTERNS[random.choice(available)]


# =============================================================================
# KEYBOARD RUN GENERATOR  
# =============================================================================

class KeyboardRunGenerator:
    """
    Generates keyboard runs, fills, and ornaments.
    
    Run Types:
    - Scale runs (ascending/descending)
    - Chord arpeggios
    - Grace note ornaments
    - Gospel/churchy runs
    - Jazz lines
    """
    
    @staticmethod
    def generate_scale_run(
        start_tick: int,
        start_pitch: int,
        scale_notes: List[int],
        direction: int = 1,
        num_notes: int = 8,
        duration_ticks: int = TICKS_PER_16TH,
        base_velocity: int = 85
    ) -> List[NoteEvent]:
        """
        Generate a scalar run.
        
        Args:
            start_tick: Starting tick position
            start_pitch: Starting note
            scale_notes: Available scale notes
            direction: 1 for ascending, -1 for descending
            num_notes: Number of notes in run
            duration_ticks: Duration per note
            base_velocity: Base velocity
            
        Returns:
            List of NoteEvents
        """
        notes = []
        
        # Find scale notes in direction from start
        if direction > 0:
            path = sorted([n for n in scale_notes if n >= start_pitch])
        else:
            path = sorted([n for n in scale_notes if n <= start_pitch], reverse=True)
        
        if len(path) < num_notes:
            # Extend with octave transpositions
            base_path = path.copy() if path else scale_notes.copy()
            if not base_path:
                return notes  # No scale notes available
            iterations = 0
            while len(path) < num_notes and iterations < 10:
                extension = [n + (12 * direction) for n in base_path]
                path.extend(extension)
                path = sorted(set(path), reverse=(direction < 0))[:num_notes * 2]
                iterations += 1
        
        path = path[:num_notes]
        
        for i, pitch in enumerate(path):
            tick = start_tick + (i * duration_ticks)
            # Crescendo/decrescendo based on direction
            vel_progress = i / max(1, num_notes - 1)
            if direction > 0:
                vel = base_velocity + int(15 * vel_progress)  # Crescendo up
            else:
                vel = base_velocity + int(15 * (1 - vel_progress))  # Decrescendo down
            
            vel = humanize_velocity(min(127, vel), variation=0.08)
            
            notes.append(NoteEvent(
                pitch=pitch,
                start_tick=tick,
                duration_ticks=duration_ticks,
                velocity=vel,
                channel=0
            ))
        
        return notes
    
    @staticmethod
    def generate_arpeggio(
        start_tick: int,
        chord_notes: List[int],
        pattern: str = 'up',
        num_cycles: int = 1,
        duration_ticks: int = TICKS_PER_8TH,
        base_velocity: int = 80
    ) -> List[NoteEvent]:
        """
        Generate an arpeggiated chord pattern.
        
        Args:
            start_tick: Starting tick position
            chord_notes: Chord notes to arpeggiate
            pattern: 'up', 'down', 'up_down', 'random'
            num_cycles: Number of times to cycle through
            duration_ticks: Duration per note
            base_velocity: Base velocity
            
        Returns:
            List of NoteEvents
        """
        notes = []
        
        if not chord_notes:
            return notes
        
        # Build arpeggio sequence based on pattern
        sequence = []
        sorted_notes = sorted(chord_notes)
        
        for _ in range(num_cycles):
            if pattern == 'up':
                sequence.extend(sorted_notes)
            elif pattern == 'down':
                sequence.extend(sorted_notes[::-1])
            elif pattern == 'up_down':
                sequence.extend(sorted_notes + sorted_notes[-2:0:-1])
            elif pattern == 'random':
                shuffled = sorted_notes.copy()
                random.shuffle(shuffled)
                sequence.extend(shuffled)
            else:
                sequence.extend(sorted_notes)
        
        for i, pitch in enumerate(sequence):
            tick = start_tick + (i * duration_ticks)
            # Accent pattern (first of each chord cycle)
            is_accent = (i % len(chord_notes)) == 0
            vel = base_velocity + 10 if is_accent else base_velocity
            vel = humanize_velocity(min(127, vel), variation=0.1)
            
            notes.append(NoteEvent(
                pitch=pitch,
                start_tick=tick,
                duration_ticks=duration_ticks,
                velocity=vel,
                channel=0
            ))
        
        return notes
    
    @staticmethod
    def generate_gospel_run(
        start_tick: int,
        chord_notes: List[int],
        scale_notes: List[int],
        duration_beats: float = 1.0,
        base_velocity: int = 90
    ) -> List[NoteEvent]:
        """
        Generate a gospel/churchy piano run.
        
        Gospel runs typically combine scale tones with chord tones,
        often with chromatic approaches and rhythmic variation.
        
        Args:
            start_tick: Starting tick position
            chord_notes: Current chord notes
            scale_notes: Available scale notes
            duration_beats: Total duration in beats
            base_velocity: Base velocity
            
        Returns:
            List of NoteEvents
        """
        notes = []
        
        if not chord_notes or not scale_notes:
            return notes
        
        # Build a gospel run pattern
        # Mix chord tones with passing scale tones and chromatic approaches
        total_ticks = int(duration_beats * TICKS_PER_BEAT)
        
        # Start from top of chord range
        high_note = max(chord_notes)
        low_note = min(chord_notes)
        
        # Create a run that descends with some embellishment
        current_tick = start_tick
        current_pitch = high_note
        
        while current_tick < start_tick + total_ticks and current_pitch >= low_note:
            # Decide: chord tone, scale tone, or chromatic
            roll = random.random()
            
            if roll < 0.4:
                # Chord tone
                nearest_chord = min(chord_notes, key=lambda n: abs(n - current_pitch))
                pitch = nearest_chord
            elif roll < 0.7:
                # Scale tone
                scale_below = [n for n in scale_notes if n <= current_pitch]
                if scale_below:
                    pitch = max(scale_below)
                else:
                    pitch = current_pitch - 2
            else:
                # Chromatic approach
                pitch = current_pitch - 1
            
            # Duration varies for rhythmic interest
            dur = random.choice([TICKS_PER_16TH, TICKS_PER_8TH, TICKS_PER_16TH])
            vel = humanize_velocity(base_velocity, variation=0.12)
            
            notes.append(NoteEvent(
                pitch=max(36, pitch),
                start_tick=current_tick,
                duration_ticks=dur,
                velocity=vel,
                channel=0
            ))
            
            current_tick += dur
            current_pitch = pitch - random.randint(1, 3)
        
        return notes
    
    @staticmethod
    def generate_chord_stab(
        tick: int,
        chord_notes: List[int],
        base_velocity: int = 95,
        duration_ticks: int = TICKS_PER_8TH
    ) -> List[NoteEvent]:
        """
        Generate a chord stab (all notes together, short duration).
        
        Args:
            tick: Tick position
            chord_notes: Notes in the chord
            base_velocity: Base velocity
            duration_ticks: Note duration
            
        Returns:
            List of NoteEvents
        """
        notes = []
        
        for i, pitch in enumerate(chord_notes):
            # Slight velocity variation within chord
            vel_offset = random.randint(-5, 5)
            vel = humanize_velocity(base_velocity + vel_offset, variation=0.05)
            
            notes.append(NoteEvent(
                pitch=pitch,
                start_tick=tick,
                duration_ticks=duration_ticks,
                velocity=vel,
                channel=0
            ))
        
        return notes


# =============================================================================
# KEYBOARDIST AGENT
# =============================================================================

class KeyboardistAgent(IPerformerAgent):
    """
    Masterclass keyboardist performer agent.
    
    A professional-level keyboardist that understands:
    - Voicing theory (root position, inversions, shell, drop 2)
    - Voice leading (minimal movement between chords)
    - Chord types (triads, 7ths, extensions, alterations)
    - Genre-specific comping styles
    - Rhythmic patterns (pads, stabs, arpeggios)
    - Harmonic context from chord progressions
    
    The agent generates musically-informed keyboard parts that
    complement the rhythm section while adding harmonic color and texture.
    
    Attributes:
        _name: Human-readable agent name
        _voicing_theory: Reference to voicing theory knowledge
        _comping_patterns: Reference to comping pattern library
        _decisions: Log of creative decisions per perform call
        
    Example:
        ```python
        keyboardist = KeyboardistAgent()
        keyboardist.set_personality(KEYIST_PRESETS['jazz_voicings'])
        
        result = keyboardist.perform(context, section)
        # result.notes contains the keyboard MIDI events
        # result.decisions_made contains reasoning log
        ```
    """
    
    def __init__(self, name: str = "Master Keyboardist"):
        """
        Initialize the keyboardist agent.
        
        Args:
            name: Human-readable name for this agent instance
        """
        super().__init__()
        self._name = name
        self._voicing_theory = VoicingTheory
        self._chord_builder = ChordBuilder
        self._voice_leader = VoiceLeader
        self._comping_patterns = CompingPatterns
        self._decisions: List[str] = []
    
    @property
    def role(self) -> AgentRole:
        """This agent fulfills the KEYS role."""
        return AgentRole.KEYS
    
    @property
    def name(self) -> str:
        """Human-readable agent name."""
        return self._name
    
    def perform(
        self,
        context: PerformanceContext,
        section: SongSection,
        personality: Optional[AgentPersonality] = None
    ) -> PerformanceResult:
        """
        Generate keyboard notes for the given section.
        
        This is the main entry point for keyboard generation. The agent:
        1. Analyzes context (chord progression, key, tension)
        2. Selects appropriate voicing complexity based on personality
        3. Applies voice leading between chords
        4. Generates rhythmic pattern based on genre
        5. Adds fills and runs based on section type
        6. Applies swing and timing adjustments
        7. Logs all creative decisions
        
        Args:
            context: Shared performance state (tempo, key, tension, etc.)
            section: The song section to generate for
            personality: Optional personality override
            
        Returns:
            PerformanceResult containing generated notes and metadata
        """
        # Reset decision log for this performance
        self._decisions = []
        
        # Resolve personality
        effective_personality = personality or self._personality
        if effective_personality is None:
            genre = self._extract_genre_from_context(context)
            effective_personality = get_personality_for_role(genre, AgentRole.KEYS)
            self._log_decision(f"Using default personality for genre '{genre}'")
        else:
            self._log_decision(f"Using provided personality (complexity={effective_personality.complexity:.2f})")
        
        # Scale personality by tension
        scaled_personality = effective_personality.apply_tension_scaling(context.tension)
        self._log_decision(f"Applied tension scaling ({context.tension:.2f}) to personality")
        
        # Get genre and harmonic info
        genre = self._extract_genre_from_context(context)
        chord_progression = self._get_chord_progression(context, section)
        scale_notes = self._get_scale_notes(context)
        
        self._log_decision(f"Chord progression: {chord_progression}")
        
        # Select voicing type based on complexity
        voicing_type = self._select_voicing_type(scaled_personality.complexity, genre)
        self._log_decision(f"Selected voicing type: {voicing_type}")
        
        # Select comping pattern based on context
        comping_pattern = self._comping_patterns.select_pattern_for_context(
            genre,
            section.section_type,
            scaled_personality.complexity
        )
        self._log_decision(f"Selected comping pattern: {comping_pattern.get('description', 'unknown')}")
        
        # Generate voiced chords with voice leading
        voiced_chords = self._generate_voiced_progression(
            chord_progression,
            voicing_type,
            scaled_personality.complexity,
            context=context
        )
        
        # Generate notes using the comping pattern
        base_notes = self._generate_comped_notes(
            section,
            context,
            voiced_chords,
            comping_pattern,
            scaled_personality
        )
        self._log_decision(f"Generated {len(base_notes)} base notes")
        
        patterns_used = [comping_pattern.get('description', 'comping').split()[0]]
        
        # Add fills based on section type and personality
        fill_locations = []
        if context.fill_opportunity or self._should_add_fill(section, scaled_personality):
            fill_notes, fill_tick = self._generate_section_fill(
                section,
                context,
                scaled_personality,
                voiced_chords,
                scale_notes
            )
            if fill_notes:
                base_notes.extend(fill_notes)
                fill_locations.append(fill_tick)
                self._log_decision(f"Added fill at tick {fill_tick} ({len(fill_notes)} notes)")
                patterns_used.append('fill')
        
        # Apply swing from pattern and personality
        pattern_swing = comping_pattern.get('swing', 0.0)
        effective_swing = pattern_swing * (0.5 + 0.5 * scaled_personality.swing_affinity)
        if effective_swing > 0.01:
            base_notes = self._apply_swing(base_notes, effective_swing)
            self._log_decision(f"Applied swing: {effective_swing:.3f}")
        
        # Sort notes by time
        base_notes.sort(key=lambda n: (n.start_tick, n.pitch))
        
        # Build result
        result = PerformanceResult(
            notes=base_notes,
            agent_role=self.role,
            agent_name=self.name,
            personality_applied=scaled_personality,
            decisions_made=self._decisions.copy(),
            patterns_used=patterns_used,
            fill_locations=fill_locations
        )
        
        self._log_decision(f"Performance complete: {len(base_notes)} total notes")
        
        return result
    
    def react_to_cue(
        self,
        cue_type: str,
        context: PerformanceContext
    ) -> List[NoteEvent]:
        """
        React to a performance cue with an immediate response.
        
        Supported cues:
        - "fill": Chord run or arpeggio
        - "stop": Return empty (silence/break)
        - "build": Rising arpeggio or chord climb
        - "drop": Dramatic chord stab
        
        Args:
            cue_type: The type of cue to react to
            context: Current performance context
            
        Returns:
            List of NoteEvent for the cue response
        """
        cue_type = cue_type.lower().strip()
        genre = self._extract_genre_from_context(context)
        
        # Get current tick from context
        current_tick = int(context.section_position_beats * TICKS_PER_BEAT)
        
        personality = self._personality or get_personality_for_role(genre, AgentRole.KEYS)
        
        # Get current chord
        chord_notes = self._get_current_chord_notes(context)
        scale_notes = self._get_scale_notes(context)
        
        base_velocity = int(90 * (0.8 + 0.4 * personality.aggressiveness))
        
        if cue_type == 'fill':
            # Generate chord run or arpeggio
            return self._generate_cue_fill(
                current_tick, chord_notes, scale_notes, base_velocity, personality
            )
        
        elif cue_type == 'stop':
            # Return empty for silence/break
            return []
        
        elif cue_type == 'build':
            # Rising arpeggio or chord climb
            return self._generate_build_cue(
                current_tick, chord_notes, scale_notes, base_velocity
            )
        
        elif cue_type == 'drop':
            # Dramatic chord stab
            return self._generate_drop_cue(current_tick, chord_notes, base_velocity)
        
        else:
            logger.warning(f"Unknown cue type: {cue_type}")
            return []
    
    # =========================================================================
    # PRIVATE HELPER METHODS
    # =========================================================================
    
    def _log_decision(self, decision: str) -> None:
        """Log a creative decision for transparency."""
        self._decisions.append(decision)
        logger.debug(f"[{self.name}] {decision}")
    
    def _extract_genre_from_context(self, context: PerformanceContext) -> str:
        """Extract genre string from context, with fallback."""
        if context.reference_features and 'genre' in context.reference_features:
            return context.reference_features['genre']
        return 'lofi'  # Default to lofi for keyboard-friendly sound
    
    def _get_chord_progression(
        self,
        context: PerformanceContext,
        section: SongSection
    ) -> List[str]:
        """
        Get chord progression for the section.
        
        Args:
            context: Performance context
            section: Current section
            
        Returns:
            List of chord symbols
        """
        if context.chord_progression:
            return context.chord_progression
        
        # Generate default progression based on key
        key = context.key or 'C'
        
        # Determine if minor or major based on context
        if 'm' in key.lower() or (context.scale_notes and 3 in [n % 12 for n in context.scale_notes]):
            # Minor key progressions
            return [f"{key}m", f"{key}m", f"Ab", f"Eb"]  # i-i-VI-III
        else:
            # Major key progressions
            return [key, f"{key}maj7", "Am7", "Fmaj7"]  # I-Imaj7-vi-IV
    
    def _get_scale_notes(self, context: PerformanceContext) -> List[int]:
        """Get scale notes extended to keyboard range."""
        if context.scale_notes:
            # Extend to full keyboard range
            base_notes = context.scale_notes
            extended = []
            for octave_offset in range(-2, 3):
                for note in base_notes:
                    transposed = note + (octave_offset * 12)
                    if 36 <= transposed <= 96:  # C2-C7
                        extended.append(transposed)
            return sorted(set(extended))
        
        # Generate default minor scale
        key = context.key or 'C'
        try:
            return get_scale_notes(key, ScaleType.MINOR, octave=3, num_octaves=4)
        except Exception:
            # Fallback
            root = note_name_to_midi(key, 4)
            return [root + i for i in range(25)]  # 2 octaves chromatic
    
    def _get_current_chord_notes(self, context: PerformanceContext) -> List[int]:
        """Get notes for the current chord from context."""
        if context.current_chord:
            _, _, notes = self._chord_builder.build_from_symbol(context.current_chord, 4)
            return notes
        
        # Default to key minor chord
        key = context.key or 'C'
        return get_chord_notes(key, 'minor', 4)
    
    def _select_voicing_type(self, complexity: float, genre: str) -> str:
        """
        Select voicing type based on complexity and genre.
        
        Args:
            complexity: Personality complexity (0-1)
            genre: Genre string
            
        Returns:
            Voicing type name
        """
        genre_lower = genre.lower()
        
        # Genre-specific preferences
        if genre_lower in ['jazz', 'ethio_jazz']:
            if complexity > 0.7:
                return 'drop_2'
            elif complexity > 0.4:
                return 'shell_voicing'
            else:
                return 'root_position'
        
        elif genre_lower in ['lofi', 'rnb', 'neo_soul']:
            if complexity > 0.6:
                return 'shell_voicing'
            elif complexity > 0.3:
                return 'first_inversion'
            else:
                return 'root_position'
        
        elif genre_lower in ['house', 'trap', 'drill']:
            # Simpler voicings for electronic genres
            if complexity > 0.7:
                return 'first_inversion'
            else:
                return 'root_position'
        
        elif genre_lower in ['gospel']:
            if complexity > 0.5:
                return 'drop_2'
            else:
                return 'open'
        
        elif genre_lower in ['ethiopian', 'ethiopian_traditional', 'eskista']:
            # Ethiopian music uses specific voicings
            return 'open'  # Open voicings for krar-like sound
        
        else:
            # General complexity-based selection
            if complexity > 0.7:
                return 'drop_2'
            elif complexity > 0.5:
                return 'shell_voicing'
            elif complexity > 0.3:
                return 'first_inversion'
            else:
                return 'root_position'
    
    def _generate_voiced_progression(
        self,
        chord_symbols: List[str],
        voicing_type: str,
        complexity: float,
        context: Optional[PerformanceContext] = None,
    ) -> List[List[int]]:
        """
        Generate voiced chords with voice leading.
        
        If the PerformanceContext carries ``voicing_constraints`` and the
        ``HarmonicBrain`` intelligence module is available, it is used for
        higher-quality voice leading.  Otherwise the existing
        ``VoiceLeader`` is used as a fallback.
        
        Args:
            chord_symbols: List of chord symbols
            voicing_type: Selected voicing type
            complexity: Personality complexity
            context: Optional PerformanceContext for intelligence-path
            
        Returns:
            List of voiced chords (each is a list of MIDI notes)
        """
        if not chord_symbols:
            return [[60, 64, 67]]  # Default C major
        
        # ------------------------------------------------------------------
        # Intelligence path: prefer HarmonicBrain when available
        # ------------------------------------------------------------------
        if (
            context is not None
            and getattr(context, "voicing_constraints", None) is not None
        ):
            try:
                from ...intelligence.harmonic_brain import HarmonicBrain
                brain = HarmonicBrain()
                key = getattr(context, "key", "C") or "C"
                constraints = context.voicing_constraints
                prev = getattr(context, "previous_voicing", None)

                voiced_chords: List[List[int]] = []
                for symbol in chord_symbols:
                    notes = brain.voice_lead(prev, symbol, key, constraints)
                    voiced_chords.append(notes)
                    prev = notes

                self._log_decision(
                    "Used HarmonicBrain for voice leading (intelligence path)"
                )
                return voiced_chords
            except Exception as exc:  # pragma: no cover
                logger.debug(
                    "HarmonicBrain unavailable, falling back to VoiceLeader: %s", exc
                )
                self._log_decision(
                    f"HarmonicBrain fallback: {exc}"
                )
        
        # ------------------------------------------------------------------
        # Fallback path: existing VoiceLeader
        # ------------------------------------------------------------------
        voiced_chords = []
        prev_notes = None
        
        for symbol in chord_symbols:
            root_midi, intervals, _ = self._chord_builder.build_from_symbol(symbol, 4)
            
            # Apply voicing type
            voicing_info = self._voicing_theory.VOICING_TYPES.get(voicing_type, {})
            
            if voicing_type == 'shell_voicing' and len(intervals) >= 3:
                notes = self._voicing_theory.get_shell_voicing(root_midi, intervals)
            elif voicing_type == 'drop_2' and len(intervals) >= 4:
                notes = self._voicing_theory.get_drop_2_voicing(root_midi, intervals)
            elif voicing_type == 'first_inversion':
                notes = self._voicing_theory.get_first_inversion(root_midi, intervals)
            elif voicing_type == 'second_inversion':
                notes = self._voicing_theory.get_second_inversion(root_midi, intervals)
            elif voicing_type == 'open':
                notes = self._voicing_theory.get_open_voicing(root_midi, intervals)
            else:
                notes = self._voicing_theory.get_root_position(root_midi, intervals)
            
            # Apply voice leading if we have a previous chord
            if prev_notes and complexity > 0.4:
                notes = self._voice_leader.find_best_voicing(
                    prev_notes,
                    root_midi,
                    intervals,
                    octave_range=(3, 5)
                )
            
            voiced_chords.append(notes)
            prev_notes = notes
        
        return voiced_chords
    
    def _generate_comped_notes(
        self,
        section: SongSection,
        context: PerformanceContext,
        voiced_chords: List[List[int]],
        pattern: Dict[str, Any],
        personality: AgentPersonality
    ) -> List[NoteEvent]:
        """
        Generate keyboard notes using the comping pattern.
        
        Args:
            section: Song section
            context: Performance context
            voiced_chords: Pre-voiced chord progression
            pattern: Comping pattern dictionary
            personality: Scaled personality
            
        Returns:
            List of NoteEvents
        """
        notes = []
        
        positions = pattern.get('positions', [(0, 1.0, 1.0, True)])
        is_arpeggio = pattern.get('is_arpeggio', False)
        
        # Determine bars per chord
        num_chords = len(voiced_chords)
        bars_per_chord = max(1, section.bars // num_chords) if num_chords > 0 else 1
        
        # Base velocity from personality
        base_velocity = int(85 * (0.7 + 0.3 * personality.aggressiveness))
        
        for bar in range(section.bars):
            bar_offset = section.start_tick + (bar * TICKS_PER_BAR_4_4)
            
            # Determine which chord to use
            chord_index = (bar // bars_per_chord) % num_chords if num_chords > 0 else 0
            chord_notes = voiced_chords[chord_index] if voiced_chords else [60, 64, 67]
            
            if is_arpeggio:
                # Generate arpeggiated pattern
                arp_notes = self._generate_bar_arpeggio(
                    bar_offset,
                    chord_notes,
                    positions,
                    base_velocity,
                    personality
                )
                notes.extend(arp_notes)
            else:
                # Generate chord comping
                comp_notes = self._generate_bar_comping(
                    bar_offset,
                    chord_notes,
                    positions,
                    base_velocity,
                    personality
                )
                notes.extend(comp_notes)
            
            # Add variation based on personality
            if personality.variation_tendency > 0.5 and random.random() < personality.variation_tendency * 0.3:
                # Occasionally add a grace note or embellishment
                if random.random() < 0.3:
                    grace_tick = bar_offset + random.randint(0, TICKS_PER_BAR_4_4 - TICKS_PER_8TH)
                    grace_pitch = random.choice(chord_notes) + random.choice([-1, 1, 2, -2])
                    notes.append(NoteEvent(
                        pitch=grace_pitch,
                        start_tick=grace_tick,
                        duration_ticks=TICKS_PER_16TH,
                        velocity=int(base_velocity * 0.6),
                        channel=0
                    ))
        
        return notes
    
    def _generate_bar_comping(
        self,
        bar_offset: int,
        chord_notes: List[int],
        positions: List[Tuple],
        base_velocity: int,
        personality: AgentPersonality
    ) -> List[NoteEvent]:
        """
        Generate chord comping for one bar.
        
        Args:
            bar_offset: Starting tick of bar
            chord_notes: Notes in the chord
            positions: Pattern positions
            base_velocity: Base velocity
            personality: Scaled personality
            
        Returns:
            List of NoteEvents
        """
        notes = []
        
        for pos_data in positions:
            beat_pos, vel_mult, dur_mult, is_accent = pos_data[:4]
            
            tick = bar_offset + beats_to_ticks(beat_pos)
            
            # Calculate velocity
            vel = int(base_velocity * vel_mult)
            if is_accent:
                vel = int(vel * 1.1)
            vel = humanize_velocity(min(127, vel), variation=0.08 * (1 - personality.consistency))
            
            # Calculate duration
            duration = int(TICKS_PER_BEAT * dur_mult)
            
            # Add all chord notes
            for pitch in chord_notes:
                # Slight velocity variation within chord
                note_vel = vel + random.randint(-3, 3)
                note_vel = max(30, min(127, note_vel))
                
                notes.append(NoteEvent(
                    pitch=pitch,
                    start_tick=tick,
                    duration_ticks=duration,
                    velocity=note_vel,
                    channel=0
                ))
        
        return notes
    
    def _generate_bar_arpeggio(
        self,
        bar_offset: int,
        chord_notes: List[int],
        positions: List[Tuple],
        base_velocity: int,
        personality: AgentPersonality
    ) -> List[NoteEvent]:
        """
        Generate arpeggiated pattern for one bar.
        
        Args:
            bar_offset: Starting tick of bar
            chord_notes: Notes in the chord
            positions: Pattern positions
            base_velocity: Base velocity
            personality: Scaled personality
            
        Returns:
            List of NoteEvents
        """
        notes = []
        sorted_chord = sorted(chord_notes)
        
        for i, pos_data in enumerate(positions):
            beat_pos, vel_mult, dur_mult, is_accent = pos_data[:4]
            
            tick = bar_offset + beats_to_ticks(beat_pos)
            
            # Pick which chord note to play (cycle through)
            note_index = i % len(sorted_chord)
            pitch = sorted_chord[note_index]
            
            # Calculate velocity
            vel = int(base_velocity * vel_mult)
            if is_accent:
                vel = int(vel * 1.15)
            vel = humanize_velocity(min(127, vel), variation=0.1 * (1 - personality.consistency))
            
            # Calculate duration
            duration = int(TICKS_PER_BEAT * dur_mult)
            
            notes.append(NoteEvent(
                pitch=pitch,
                start_tick=tick,
                duration_ticks=duration,
                velocity=vel,
                channel=0
            ))
        
        return notes
    
    def _should_add_fill(
        self,
        section: SongSection,
        personality: AgentPersonality
    ) -> bool:
        """Decide if a fill should be added based on section and personality."""
        # Always add fill before high-energy sections
        if section.section_type in [SectionType.DROP, SectionType.CHORUS]:
            return True
        
        # Personality-based random chance
        fill_chance = personality.fill_frequency * 0.5
        
        # Boost chance for transition sections
        if section.section_type in [SectionType.PRE_CHORUS, SectionType.BUILDUP]:
            fill_chance += 0.3
        
        return random.random() < fill_chance
    
    def _generate_section_fill(
        self,
        section: SongSection,
        context: PerformanceContext,
        personality: AgentPersonality,
        voiced_chords: List[List[int]],
        scale_notes: List[int]
    ) -> Tuple[List[NoteEvent], int]:
        """
        Generate a fill for the end of the section.
        
        Args:
            section: Current section
            context: Performance context
            personality: Scaled personality
            voiced_chords: Voiced chord progression
            scale_notes: Available scale notes
            
        Returns:
            Tuple of (fill notes, fill start tick)
        """
        fill_duration = 1.0 if personality.complexity < 0.5 else 2.0
        fill_start = section.end_tick - int(fill_duration * TICKS_PER_BEAT)
        
        base_velocity = int(90 * (0.8 + 0.4 * personality.aggressiveness))
        
        # Get the last chord for fill context
        last_chord = voiced_chords[-1] if voiced_chords else [60, 64, 67]
        
        # Select fill type based on complexity and genre
        genre = self._extract_genre_from_context(context)
        
        if personality.complexity > 0.7 or genre in ['gospel', 'jazz']:
            # Gospel-style run
            notes = KeyboardRunGenerator.generate_gospel_run(
                fill_start, last_chord, scale_notes,
                duration_beats=fill_duration, base_velocity=base_velocity
            )
        elif personality.complexity > 0.4:
            # Scale run
            start_pitch = max(last_chord)
            notes = KeyboardRunGenerator.generate_scale_run(
                fill_start, start_pitch, scale_notes,
                direction=-1, num_notes=int(fill_duration * 4),
                duration_ticks=TICKS_PER_16TH, base_velocity=base_velocity
            )
        else:
            # Simple arpeggio
            notes = KeyboardRunGenerator.generate_arpeggio(
                fill_start, last_chord, pattern='up_down',
                num_cycles=1, duration_ticks=TICKS_PER_8TH,
                base_velocity=base_velocity
            )
        
        return notes, fill_start
    
    def _apply_swing(
        self,
        notes: List[NoteEvent],
        swing_amount: float
    ) -> List[NoteEvent]:
        """
        Apply swing timing to notes.
        
        Swing delays every other 8th/16th note.
        
        Args:
            notes: List of notes to swing
            swing_amount: Amount of swing (0-0.3 typical)
            
        Returns:
            Notes with swing applied
        """
        swing_offset = int(TICKS_PER_8TH * swing_amount)
        
        for note in notes:
            # Determine if this is an offbeat (every other 8th note)
            position_in_beat = note.start_tick % TICKS_PER_BEAT
            is_offbeat = TICKS_PER_8TH - 10 < position_in_beat < TICKS_PER_8TH + 10 or \
                        TICKS_PER_8TH * 3 - 10 < position_in_beat < TICKS_PER_8TH * 3 + 10
            
            if is_offbeat:
                note.start_tick += swing_offset
        
        return notes
    
    def _generate_cue_fill(
        self,
        start_tick: int,
        chord_notes: List[int],
        scale_notes: List[int],
        base_velocity: int,
        personality: AgentPersonality
    ) -> List[NoteEvent]:
        """Generate a fill for the 'fill' cue."""
        if personality.complexity > 0.6:
            return KeyboardRunGenerator.generate_gospel_run(
                start_tick, chord_notes, scale_notes,
                duration_beats=2.0, base_velocity=base_velocity
            )
        else:
            return KeyboardRunGenerator.generate_arpeggio(
                start_tick, chord_notes, pattern='up_down',
                num_cycles=2, duration_ticks=TICKS_PER_8TH,
                base_velocity=base_velocity
            )
    
    def _generate_build_cue(
        self,
        start_tick: int,
        chord_notes: List[int],
        scale_notes: List[int],
        base_velocity: int
    ) -> List[NoteEvent]:
        """Generate a rising arpeggio/climb for the 'build' cue."""
        notes = []
        
        # Ascending arpeggio
        arp_notes = KeyboardRunGenerator.generate_arpeggio(
            start_tick, chord_notes, pattern='up',
            num_cycles=2, duration_ticks=TICKS_PER_8TH,
            base_velocity=base_velocity
        )
        notes.extend(arp_notes)
        
        # Then scale climb
        if chord_notes:
            top_note = max(chord_notes)
            climb_start = start_tick + (len(chord_notes) * 2 * TICKS_PER_8TH)
            climb_notes = KeyboardRunGenerator.generate_scale_run(
                climb_start, top_note, scale_notes,
                direction=1, num_notes=6,
                duration_ticks=TICKS_PER_16TH, base_velocity=base_velocity + 10
            )
            notes.extend(climb_notes)
        
        return notes
    
    def _generate_drop_cue(
        self,
        start_tick: int,
        chord_notes: List[int],
        base_velocity: int
    ) -> List[NoteEvent]:
        """Generate a dramatic chord stab for the 'drop' cue."""
        # Big chord stab with all notes
        stab_notes = KeyboardRunGenerator.generate_chord_stab(
            start_tick, chord_notes,
            base_velocity=min(127, base_velocity + 20),
            duration_ticks=TICKS_PER_BEAT * 2
        )
        
        # Add octave below for weight
        low_notes = [n - 12 for n in chord_notes if n - 12 >= 36]
        if low_notes:
            low_stab = KeyboardRunGenerator.generate_chord_stab(
                start_tick, low_notes,
                base_velocity=min(127, base_velocity + 10),
                duration_ticks=TICKS_PER_BEAT * 2
            )
            stab_notes.extend(low_stab)
        
        return stab_notes
