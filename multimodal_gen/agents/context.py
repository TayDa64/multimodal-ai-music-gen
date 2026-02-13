"""
Performance Context and Score Data Structures

This module defines the shared state that all performer agents react to:

- PerformanceContext: Real-time state during generation
- PerformanceScore: The "musical score" prepared by the Conductor

Design Philosophy:
    PerformanceContext is like "sheet music + conductor gestures" - it
    contains everything a performer needs to make musically-informed
    decisions in the moment. Unlike static sheet music, it includes
    inter-agent communication (where the kick landed, melody notes, etc.)
    so agents can lock to each other.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any, Tuple, TYPE_CHECKING
import logging

if TYPE_CHECKING:
    from ..arranger import SongSection
    from ..intelligence.harmonic_brain import VoicingConstraints

logger = logging.getLogger(__name__)


@dataclass
class PerformanceContext:
    """
    Shared state passed to all agents for coherent performance.
    
    This is the "sheet music" + "conductor gestures" that all
    performers react to in real-time. It's updated by the Conductor
    as the performance progresses.
    
    Attributes:
        Temporal:
            bpm: Current tempo in beats per minute
            time_signature: Tuple of (numerator, denominator)
            current_section: The SongSection being performed
            section_position_beats: Position within the section in beats
            
        Harmonic:
            key: Root key (e.g., "C", "F#")
            scale_notes: List of MIDI note numbers in the scale
            current_chord: Current chord symbol (e.g., "Cm7")
            chord_progression: List of chord symbols for the section
            
        Energy/Dynamics:
            tension: Tension value from 0.0 (relaxed) to 1.0 (intense)
            energy_level: Overall energy level (0-1)
            density_target: Target note density (0-1)
            
        Performance Cues:
            fill_opportunity: True if a fill would be appropriate here
            breakdown_mode: True if in a breakdown (sparse playing)
            build_mode: True if building to a drop (crescendo)
            
        Inter-Agent Communication:
            last_kick_tick: Tick of the most recent kick drum
            last_snare_tick: Tick of the most recent snare
            melody_notes: Recent melody notes for harmonization
            
        Analysis:
            reference_features: Features from reference audio analysis
    """
    # Temporal
    bpm: float = 120.0
    time_signature: Tuple[int, int] = (4, 4)
    current_section: Optional['SongSection'] = None
    section_position_beats: float = 0.0
    
    # Mood / Genre Feel
    mood: str = "neutral"
    
    # Harmonic
    key: str = "C"
    scale_notes: List[int] = field(default_factory=list)
    current_chord: Optional[str] = None
    chord_progression: List[str] = field(default_factory=list)
    
    # Energy/Dynamics
    tension: float = 0.5
    energy_level: float = 0.5
    density_target: float = 0.5
    
    # Performance cues
    fill_opportunity: bool = False
    breakdown_mode: bool = False
    build_mode: bool = False
    
    # Inter-agent communication
    last_kick_tick: Optional[int] = None
    last_snare_tick: Optional[int] = None
    melody_notes: List[int] = field(default_factory=list)
    
    # Reference analysis (from audio)
    reference_features: Optional[Dict[str, Any]] = None
    
    # MUSE Intelligence Fields
    voicing_constraints: Optional['VoicingConstraints'] = None
    groove_template: Optional[Dict[str, Any]] = None
    genre_dna: Optional[Dict[str, float]] = None
    tension_curve: List[float] = field(default_factory=list)
    orchestration_map: Dict[str, bool] = field(default_factory=dict)
    previous_voicing: Optional[List[int]] = None
    genre: str = ""
    
    # Sprint 2: Enhanced context fields
    harmonic_rhythm: List[str] = field(default_factory=list)
    bass_kick_alignment: float = 0.0
    kick_ticks: List[int] = field(default_factory=list)
    section_density: float = 0.5
    active_instruments: List[str] = field(default_factory=list)
    arrangement_density_curve: List[float] = field(default_factory=list)
    critic_results: Optional[Dict[str, Any]] = None
    regeneration_count: int = 0
    
    def __post_init__(self):
        """Ensure mutable defaults are properly initialized."""
        if self.scale_notes is None:
            self.scale_notes = []
        if self.chord_progression is None:
            self.chord_progression = []
        if self.melody_notes is None:
            self.melody_notes = []
        if self.tension_curve is None:
            self.tension_curve = []
        if self.orchestration_map is None:
            self.orchestration_map = {}
        if self.harmonic_rhythm is None:
            self.harmonic_rhythm = []
        if self.active_instruments is None:
            self.active_instruments = []
        if self.arrangement_density_curve is None:
            self.arrangement_density_curve = []
    
    def update_from_performance(
        self,
        kick_ticks: Optional[List[int]] = None,
        snare_ticks: Optional[List[int]] = None,
        melody: Optional[List[int]] = None
    ) -> None:
        """
        Update inter-agent communication data from recent performance.
        
        Called by the Conductor after each agent performs to update
        the context for subsequent agents.
        
        Args:
            kick_ticks: List of tick positions where kick drum hit
            snare_ticks: List of tick positions where snare hit
            melody: List of MIDI note numbers in recent melody
        """
        if kick_ticks and len(kick_ticks) > 0:
            self.last_kick_tick = kick_ticks[-1]
        if snare_ticks and len(snare_ticks) > 0:
            self.last_snare_tick = snare_ticks[-1]
        if melody:
            self.melody_notes = melody[-8:]  # Keep last 8 notes
    
    def get_beats_per_bar(self) -> float:
        """Calculate beats per bar from time signature."""
        num, denom = self.time_signature
        return num * (4 / denom)
    
    def is_downbeat(self, beat: float) -> bool:
        """Check if a beat position is a downbeat (beat 1)."""
        beats_per_bar = self.get_beats_per_bar()
        return (beat % beats_per_bar) < 0.01
    
    def is_backbeat(self, beat: float) -> bool:
        """Check if a beat position is a backbeat (beats 2 and 4 in 4/4)."""
        num, _ = self.time_signature
        if num == 4:
            beat_in_bar = beat % 4
            return 1.9 < beat_in_bar < 2.1 or 3.9 < beat_in_bar < 4.1
        return False
    
    def update_harmonic_rhythm(
        self, chord_map: Dict[int, str], ticks_per_beat: int
    ) -> None:
        """Convert a tick-to-chord mapping into a per-beat harmonic rhythm list.
        
        Args:
            chord_map: Mapping of tick positions to chord symbols.
            ticks_per_beat: Number of ticks per beat.
        """
        if not chord_map:
            self.harmonic_rhythm = []
            return
        
        sorted_ticks = sorted(chord_map.keys())
        max_tick = sorted_ticks[-1] + ticks_per_beat  # at least one beat after last chord
        total_beats = max(1, max_tick // ticks_per_beat)
        
        result: List[str] = []
        for beat_idx in range(total_beats):
            beat_tick = beat_idx * ticks_per_beat
            # Find the most recent chord at or before this beat
            active_chord = ""
            for t in sorted_ticks:
                if t <= beat_tick:
                    active_chord = chord_map[t]
                else:
                    break
            result.append(active_chord)
        
        self.harmonic_rhythm = result
    
    def compute_section_density(
        self, notes: List[Any], section_bars: int, ticks_per_beat: int = 480
    ) -> float:
        """Compute note density for a section, normalised to 0-1.
        
        8 notes/beat = 1.0 (maximum density).
        
        Args:
            notes: List of note objects (any type with length).
            section_bars: Number of bars in the section.
            ticks_per_beat: Ticks per beat (default 480).
            
        Returns:
            Normalised density value between 0.0 and 1.0.
        """
        num_beats = section_bars * self.get_beats_per_bar()
        if num_beats <= 0:
            return 0.0
        notes_per_beat = len(notes) / num_beats
        # 8 notes per beat = 1.0 (saturation point)
        density = min(1.0, notes_per_beat / 8.0)
        self.section_density = density
        return density


@dataclass
class PerformanceScore:
    """
    The "musical score" that the conductor prepares.
    
    Contains all the information performers need to play
    together coherently. This is generated by the Conductor
    from the parsed prompt and arrangement.
    
    Attributes:
        sections: Ordered list of SongSection objects
        tempo_map: Mapping of tick position to BPM (for tempo changes)
        key_map: Mapping of tick position to key (for key changes)
        chord_map: Mapping of tick position to chord symbol
        tension_curve: Per-beat tension values (0-1)
        cue_points: List of cue dictionaries with type and position
    
    Example:
        ```python
        score = PerformanceScore(
            sections=[intro, verse, chorus],
            tempo_map={0: 130.0},
            key_map={0: "C"},
            chord_map={0: "Cm", 1920: "Ab", 3840: "Eb"},
            tension_curve=[0.2, 0.3, 0.5, 0.8, ...],
            cue_points=[
                {"type": "fill", "tick": 7680},
                {"type": "drop", "tick": 15360}
            ]
        )
        ```
    """
    sections: List['SongSection'] = field(default_factory=list)
    tempo_map: Dict[int, float] = field(default_factory=dict)
    key_map: Dict[int, str] = field(default_factory=dict)
    chord_map: Dict[int, str] = field(default_factory=dict)
    tension_curve: List[float] = field(default_factory=list)
    cue_points: List[Dict[str, Any]] = field(default_factory=list)
    genre: str = ""
    mood: str = "neutral"
    
    def __post_init__(self):
        """Ensure mutable defaults are properly initialized."""
        if self.sections is None:
            self.sections = []
        if self.tempo_map is None:
            self.tempo_map = {}
        if self.key_map is None:
            self.key_map = {}
        if self.chord_map is None:
            self.chord_map = {}
        if self.tension_curve is None:
            self.tension_curve = []
        if self.cue_points is None:
            self.cue_points = []
    
    def get_tempo_at(self, tick: int) -> float:
        """
        Get the tempo at a given tick position.
        
        Args:
            tick: Tick position to query
            
        Returns:
            BPM at that position (uses most recent tempo change)
        """
        if not self.tempo_map:
            return 120.0  # Default tempo
        
        # Find the most recent tempo change before this tick
        active_tick = 0
        for t in sorted(self.tempo_map.keys()):
            if t <= tick:
                active_tick = t
            else:
                break
        return self.tempo_map.get(active_tick, 120.0)
    
    def get_key_at(self, tick: int) -> str:
        """
        Get the key at a given tick position.
        
        Args:
            tick: Tick position to query
            
        Returns:
            Key string at that position (uses most recent key change)
        """
        if not self.key_map:
            return "C"  # Default key
        
        active_tick = 0
        for t in sorted(self.key_map.keys()):
            if t <= tick:
                active_tick = t
            else:
                break
        return self.key_map.get(active_tick, "C")
    
    def get_chord_at(self, tick: int) -> Optional[str]:
        """
        Get the chord at a given tick position.
        
        Args:
            tick: Tick position to query
            
        Returns:
            Chord symbol at that position, or None if no chord defined
        """
        if not self.chord_map:
            return None
        
        active_tick = 0
        for t in sorted(self.chord_map.keys()):
            if t <= tick:
                active_tick = t
            else:
                break
        return self.chord_map.get(active_tick)
    
    def get_tension_at(self, beat: int) -> float:
        """
        Get the tension value at a given beat.
        
        Args:
            beat: Beat index (0-based)
            
        Returns:
            Tension value (0-1) at that beat
        """
        if not self.tension_curve:
            return 0.5  # Default tension
        
        if beat < 0:
            return self.tension_curve[0]
        if beat >= len(self.tension_curve):
            return self.tension_curve[-1]
        return self.tension_curve[beat]
    
    def get_cues_in_range(self, start_tick: int, end_tick: int) -> List[Dict[str, Any]]:
        """
        Get all cue points within a tick range.
        
        Args:
            start_tick: Start of range (inclusive)
            end_tick: End of range (exclusive)
            
        Returns:
            List of cue dictionaries in the range
        """
        return [
            cue for cue in self.cue_points
            if start_tick <= cue.get("tick", 0) < end_tick
        ]
    
    @property
    def total_bars(self) -> int:
        """Calculate total number of bars in the score."""
        return sum(s.bars for s in self.sections)
    
    @property
    def total_ticks(self) -> int:
        """Calculate total ticks in the score."""
        if not self.sections:
            return 0
        last_section = self.sections[-1]
        return last_section.end_tick
