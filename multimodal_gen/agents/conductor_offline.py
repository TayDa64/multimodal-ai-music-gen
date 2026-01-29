"""
OfflineConductor - Stage 1 Conductor Implementation

This module implements the IConductorAgent interface using existing
procedural modules (PromptParser, Arranger, MidiGenerator). No external
API calls are required - everything runs locally.

The OfflineConductor orchestrates the full music generation pipeline:
1. Parse prompt with existing PromptParser
2. Research style with GenreIntelligence
3. Create score with Arranger
4. Assemble performer agents
5. Conduct performance by coordinating agents

This is the foundation for Stage 2's API-backed conductor.

Example:
    ```python
    from multimodal_gen.agents.conductor_offline import OfflineConductor
    
    conductor = OfflineConductor()
    tracks = conductor.generate("ethiopian eskista dance with kebero and krar")
    
    # Or step-by-step:
    parsed = conductor.interpret_prompt(prompt)
    style = conductor.research_style(parsed)
    score = conductor.create_score(parsed, style)
    ensemble = conductor.assemble_ensemble(parsed, style)
    tracks = conductor.conduct_performance(score, ensemble)
    ```
"""

from typing import Dict, List, Optional, Any, TYPE_CHECKING
import logging

from .conductor import IConductorAgent
from .base import AgentRole, IPerformerAgent, PerformanceResult
from .context import PerformanceContext, PerformanceScore
from .registry import AgentRegistry
from .personality import get_personality_for_role, GENRE_PERSONALITY_MAP

# Performer agents
from .performers import (
    DrummerAgent, BassistAgent, KeyboardistAgent,
    MasenqoAgent, WashintAgent, KrarAgent, BegenaAgent, KeberoAgent,
)

if TYPE_CHECKING:
    from ..prompt_parser import ParsedPrompt
    from ..arranger import SongSection

logger = logging.getLogger(__name__)


# =============================================================================
# ETHIOPIAN INSTRUMENT DETECTION
# =============================================================================

ETHIOPIAN_INSTRUMENTS = {'krar', 'masenqo', 'washint', 'begena', 'kebero', 'atamo'}


# =============================================================================
# AGENT FACTORY MAPPING
# =============================================================================

# Map instrument names to agent classes
AGENT_CLASSES = {
    # Ethiopian instruments
    'kebero': KeberoAgent,
    'atamo': KeberoAgent,  # Use kebero agent for atamo
    'krar': KrarAgent,
    'masenqo': MasenqoAgent,
    'washint': WashintAgent,
    'begena': BegenaAgent,
    
    # Standard instruments (mapped to existing agents)
    'drums': DrummerAgent,
    'drum_kit': DrummerAgent,
    'bass': BassistAgent,
    '808': BassistAgent,
    'keys': KeyboardistAgent,
    'piano': KeyboardistAgent,
    'organ': KeyboardistAgent,
    'synth': KeyboardistAgent,
}

# Map roles to agent classes (fallback)
ROLE_AGENT_CLASSES = {
    AgentRole.DRUMS: DrummerAgent,
    AgentRole.BASS: BassistAgent,
    AgentRole.KEYS: KeyboardistAgent,
}


# =============================================================================
# OFFLINE CONDUCTOR IMPLEMENTATION
# =============================================================================

class OfflineConductor(IConductorAgent):
    """
    Stage 1 Conductor using existing procedural modules.
    
    Wraps PromptParser, Arranger, and performer agents to provide
    a unified orchestration interface. All processing is local -
    no API calls required.
    
    Attributes:
        _verbose: Enable detailed logging
        _use_agents: If True, use performer agents; if False, fallback to MidiGenerator
    """
    
    def __init__(self, verbose: bool = False, use_agents: bool = True):
        """
        Initialize OfflineConductor.
        
        Args:
            verbose: Enable detailed logging
            use_agents: Use performer agents (True) or fallback to MidiGenerator (False)
        """
        self._verbose = verbose
        self._use_agents = use_agents
        
        if verbose:
            logging.basicConfig(level=logging.INFO)
    
    def interpret_prompt(self, prompt: str) -> 'ParsedPrompt':
        """
        Parse natural language prompt into musical parameters.
        
        Uses the existing PromptParser module.
        
        Args:
            prompt: Natural language description
            
        Returns:
            ParsedPrompt with extracted parameters
        """
        from ..prompt_parser import parse_prompt
        
        parsed = parse_prompt(prompt)
        
        if self._verbose:
            logger.info(f"Interpreted prompt: genre={parsed.genre}, bpm={parsed.bpm}, "
                       f"key={parsed.key}, instruments={parsed.instruments}")
        
        return parsed
    
    def research_style(
        self,
        parsed: 'ParsedPrompt',
        reference_audio: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Research style and build intelligence.
        
        Uses GenreIntelligence for template lookup and
        ReferenceAnalyzer for audio analysis if provided.
        
        Args:
            parsed: ParsedPrompt from interpret_prompt()
            reference_audio: Optional path to reference audio
            
        Returns:
            Style intelligence dictionary
        """
        style_intel = {
            "genre": parsed.genre,
            "mood": parsed.mood,
            "personality_map": {},
            "mandatory_elements": [],
            "forbidden_elements": [],
            "fx_chains": {},
            "reference_features": None,
            "is_ethiopian": False,
        }
        
        # Check for Ethiopian instruments
        all_instruments = set(parsed.instruments + parsed.drum_elements)
        ethiopian_detected = all_instruments.intersection(ETHIOPIAN_INSTRUMENTS)
        
        if ethiopian_detected or parsed.genre in ['eskista', 'ethiopian', 'ethio_jazz']:
            style_intel["is_ethiopian"] = True
            style_intel["mandatory_elements"] = list(ethiopian_detected)
            if self._verbose:
                logger.info(f"Ethiopian style detected: {ethiopian_detected}")
        
        # Try to get genre template
        try:
            from ..genre_intelligence import GenreIntelligence
            intel = GenreIntelligence()
            template = intel.get_genre_template(parsed.genre)
            if template:
                style_intel["template"] = template
                style_intel["mandatory_elements"].extend(template.instruments.mandatory)
                style_intel["forbidden_elements"] = template.instruments.forbidden
        except (ImportError, AttributeError):
            pass  # GenreIntelligence not available or template structure different
        
        # Build personality map for agents
        genre_key = parsed.genre.lower().replace("-", "_").replace(" ", "_")
        for role in AgentRole:
            style_intel["personality_map"][role] = get_personality_for_role(genre_key, role)
        
        # Analyze reference audio if provided
        if reference_audio:
            try:
                from ..reference_analyzer import analyze_reference
                features = analyze_reference(reference_audio)
                style_intel["reference_features"] = features
                if self._verbose:
                    logger.info(f"Reference analysis: bpm={features.get('bpm')}, "
                               f"brightness={features.get('brightness')}")
            except Exception as e:
                logger.warning(f"Reference analysis failed: {e}")
        
        return style_intel
    
    def create_score(
        self,
        parsed: 'ParsedPrompt',
        style_intel: Dict[str, Any]
    ) -> PerformanceScore:
        """
        Create performance score from arrangement.
        
        Uses existing Arranger for section generation.
        
        Args:
            parsed: ParsedPrompt with musical parameters
            style_intel: Style intelligence
            
        Returns:
            PerformanceScore with sections, tempo, chords, etc.
        """
        from ..arranger import create_arrangement
        from ..utils import TICKS_PER_BAR_4_4, TICKS_PER_BEAT
        
        arrangement = create_arrangement(parsed)
        
        # Build score from arrangement
        score = PerformanceScore()
        
        # Add sections
        score.sections = arrangement.sections
        
        # Set tempo map (constant tempo for now)
        bpm = parsed.bpm or 120.0
        score.tempo_map = {0: bpm}
        
        # Set key map
        key = parsed.key or "C"
        score.key_map = {0: key}
        
        # Build chord map from arrangement chord progressions
        tick = 0
        for section in arrangement.sections:
            if hasattr(section, 'chords') and section.chords:
                chords_per_bar = len(section.chords)
                ticks_per_chord = TICKS_PER_BAR_4_4 // max(1, chords_per_bar)
                
                for bar in range(section.bars):
                    bar_tick = tick + (bar * TICKS_PER_BAR_4_4)
                    for i, chord in enumerate(section.chords):
                        chord_tick = bar_tick + (i * ticks_per_chord)
                        score.chord_map[chord_tick] = chord
            
            tick += section.bars * TICKS_PER_BAR_4_4
        
        # Generate tension curve (beat-level)
        total_beats = sum(s.bars * 4 for s in arrangement.sections)
        score.tension_curve = self._generate_tension_curve(arrangement.sections, total_beats)
        
        # Generate cue points (fills, drops)
        score.cue_points = self._generate_cue_points(arrangement.sections)
        
        if self._verbose:
            logger.info(f"Created score: {len(score.sections)} sections, "
                       f"{score.total_bars} bars, {len(score.cue_points)} cues")
        
        return score
    
    def assemble_ensemble(
        self,
        parsed: 'ParsedPrompt',
        style_intel: Dict[str, Any]
    ) -> Dict[AgentRole, IPerformerAgent]:
        """
        Create and configure performer agents.
        
        Args:
            parsed: ParsedPrompt with instrument requirements
            style_intel: Style intelligence with personalities
            
        Returns:
            Dictionary mapping AgentRole to configured agent
        """
        ensemble: Dict[AgentRole, IPerformerAgent] = {}
        
        # Determine which instruments to use
        instruments = set(parsed.instruments)
        drum_elements = set(parsed.drum_elements)
        
        # Check for Ethiopian instruments
        is_ethiopian = style_intel.get("is_ethiopian", False)
        
        # Create agents for each instrument
        for instrument in instruments:
            instrument_lower = instrument.lower()
            
            # Get agent class
            agent_class = AGENT_CLASSES.get(instrument_lower)
            
            if agent_class:
                agent = agent_class()
                
                # Get personality from style intel
                role = AgentRegistry.get_agent_role(instrument_lower)
                personality = style_intel["personality_map"].get(role)
                
                if personality:
                    agent.set_personality(personality)
                
                # Use the agent's declared role
                ensemble[agent.role] = agent
                
                if self._verbose:
                    logger.info(f"Created {agent_class.__name__} for {instrument}")
        
        # Handle drum elements
        if drum_elements:
            # Check for Ethiopian drums
            if 'kebero' in drum_elements or 'atamo' in drum_elements:
                if AgentRole.DRUMS not in ensemble:
                    agent = KeberoAgent()
                    personality = style_intel["personality_map"].get(AgentRole.DRUMS)
                    if personality:
                        agent.set_personality(personality)
                    ensemble[AgentRole.DRUMS] = agent
                    
                    if self._verbose:
                        logger.info("Created KeberoAgent for drums")
            else:
                # Use standard drummer
                if AgentRole.DRUMS not in ensemble:
                    agent = DrummerAgent()
                    personality = style_intel["personality_map"].get(AgentRole.DRUMS)
                    if personality:
                        agent.set_personality(personality)
                    ensemble[AgentRole.DRUMS] = agent
        
        # Ensure we have essential roles for the genre
        if is_ethiopian:
            # Ethiopian ensemble defaults
            if AgentRole.DRUMS not in ensemble and not drum_elements:
                ensemble[AgentRole.DRUMS] = KeberoAgent()
            if AgentRole.KEYS not in ensemble and 'krar' not in instruments:
                ensemble[AgentRole.KEYS] = KrarAgent()
        
        if self._verbose:
            roles = [r.name for r in ensemble.keys()]
            logger.info(f"Assembled ensemble: {roles}")
        
        return ensemble
    
    def conduct_performance(
        self,
        score: PerformanceScore,
        ensemble: Dict[AgentRole, IPerformerAgent]
    ) -> Dict[str, List['NoteEvent']]:
        """
        Coordinate all performers to generate the piece.
        
        Args:
            score: PerformanceScore from create_score()
            ensemble: Dict of configured performers
            
        Returns:
            Dictionary mapping track name to NoteEvent list
        """
        from ..midi_generator import NoteEvent
        from ..utils import TICKS_PER_BAR_4_4
        
        tracks: Dict[str, List[NoteEvent]] = {}
        
        # Initialize context
        context = PerformanceContext(
            bpm=score.get_tempo_at(0),
            key=score.get_key_at(0),
        )
        
        # Process each section
        section_tick = 0
        
        for section in score.sections:
            # Update context for this section
            context.current_section = section
            context.tension = score.get_tension_at(section_tick // int(context.bpm))
            
            # Get chord progression if available
            if hasattr(section, 'chords'):
                context.chord_progression = section.chords
            
            # Determine energy level from section type
            context.energy_level = self._get_section_energy(section)
            
            # Check for cues in this section
            section_end_tick = section_tick + (section.bars * TICKS_PER_BAR_4_4)
            cues = score.get_cues_in_range(section_tick, section_end_tick)
            context.fill_opportunity = any(c.get("type") == "fill" for c in cues)
            context.build_mode = any(c.get("type") == "build" for c in cues)
            context.breakdown_mode = any(c.get("type") == "breakdown" for c in cues)
            
            # Have each performer play this section
            # Process in dependency order: drums -> bass -> keys -> lead
            performer_order = [
                AgentRole.DRUMS,
                AgentRole.BASS,
                AgentRole.KEYS,
                AgentRole.LEAD,
                AgentRole.STRINGS,
            ]
            
            for role in performer_order:
                if role not in ensemble:
                    continue
                
                performer = ensemble[role]
                
                try:
                    # Perform the section
                    result = performer.perform(context, section)
                    
                    # Get track name from role
                    track_name = self._get_track_name(performer, role)
                    
                    # Initialize track if needed
                    if track_name not in tracks:
                        tracks[track_name] = []
                    
                    # Offset notes to section position and add to track
                    for note in result.notes:
                        offset_note = NoteEvent(
                            tick=note.tick + section_tick,
                            pitch=note.pitch,
                            velocity=note.velocity,
                            duration=note.duration,
                            channel=note.channel
                        )
                        tracks[track_name].append(offset_note)
                    
                    # Update context with performance data for next performers
                    self._update_context_from_result(context, result, role)
                    
                    if self._verbose:
                        logger.info(f"  {track_name}: {len(result.notes)} notes")
                
                except Exception as e:
                    logger.warning(f"Performer {role.name} failed: {e}")
            
            # Move to next section
            section_tick = section_end_tick
        
        return tracks
    
    # =========================================================================
    # HELPER METHODS
    # =========================================================================
    
    def _generate_tension_curve(
        self,
        sections: List['SongSection'],
        total_beats: int
    ) -> List[float]:
        """Generate per-beat tension values."""
        from ..arranger import SectionType
        
        curve = []
        
        for section in sections:
            section_type = section.type if hasattr(section, 'type') else SectionType.VERSE
            section_beats = section.bars * 4
            
            # Base tension by section type
            base_tension = {
                SectionType.INTRO: 0.3,
                SectionType.VERSE: 0.5,
                SectionType.PRECHORUS: 0.65,
                SectionType.CHORUS: 0.8,
                SectionType.DROP: 0.9,
                SectionType.BRIDGE: 0.4,
                SectionType.BREAKDOWN: 0.3,
                SectionType.OUTRO: 0.25,
            }.get(section_type, 0.5)
            
            # Add variation within section
            for beat in range(section_beats):
                # Slight build within section
                progress = beat / max(1, section_beats - 1)
                tension = base_tension + (progress * 0.1)
                curve.append(min(1.0, max(0.0, tension)))
        
        return curve
    
    def _generate_cue_points(self, sections: List['SongSection']) -> List[Dict[str, Any]]:
        """Generate cue points for fills and transitions."""
        from ..arranger import SectionType
        from ..utils import TICKS_PER_BAR_4_4, TICKS_PER_BEAT
        
        cues = []
        tick = 0
        
        for i, section in enumerate(sections):
            section_type = section.type if hasattr(section, 'type') else SectionType.VERSE
            section_end = tick + (section.bars * TICKS_PER_BAR_4_4)
            
            # Fill opportunity before section change
            if i < len(sections) - 1:
                next_section = sections[i + 1]
                next_type = next_section.type if hasattr(next_section, 'type') else SectionType.VERSE
                
                # Fill at end of phrase (4 bars before section end)
                if section.bars >= 4:
                    fill_tick = section_end - TICKS_PER_BAR_4_4
                    cues.append({
                        "type": "fill",
                        "tick": fill_tick,
                        "section": section_type.name if hasattr(section_type, 'name') else str(section_type),
                    })
                
                # Build before chorus/drop
                if next_type in [SectionType.CHORUS, SectionType.DROP]:
                    build_tick = section_end - (2 * TICKS_PER_BAR_4_4)
                    cues.append({
                        "type": "build",
                        "tick": build_tick,
                        "target_section": next_type.name if hasattr(next_type, 'name') else str(next_type),
                    })
                
                # Drop at chorus/drop start
                if next_type in [SectionType.CHORUS, SectionType.DROP]:
                    cues.append({
                        "type": "drop",
                        "tick": section_end,
                        "intensity": 0.9 if next_type == SectionType.DROP else 0.8,
                    })
            
            tick = section_end
        
        return cues
    
    def _get_section_energy(self, section: 'SongSection') -> float:
        """Get energy level for a section."""
        from ..arranger import SectionType
        
        section_type = section.type if hasattr(section, 'type') else SectionType.VERSE
        
        energy_map = {
            SectionType.INTRO: 0.4,
            SectionType.VERSE: 0.6,
            SectionType.PRECHORUS: 0.75,
            SectionType.CHORUS: 0.85,
            SectionType.DROP: 0.95,
            SectionType.BRIDGE: 0.5,
            SectionType.BREAKDOWN: 0.35,
            SectionType.OUTRO: 0.3,
        }
        
        return energy_map.get(section_type, 0.6)
    
    def _get_track_name(self, performer: IPerformerAgent, role: AgentRole) -> str:
        """Get human-readable track name for a performer."""
        # Try to get instrument name from performer class
        class_name = performer.__class__.__name__
        
        # Map agent class names to track names
        track_names = {
            "KeberoAgent": "Kebero",
            "KrarAgent": "Krar",
            "MasenqoAgent": "Masenqo",
            "WashintAgent": "Washint",
            "BegenaAgent": "Begena",
            "DrummerAgent": "Drums",
            "BassistAgent": "Bass",
            "KeyboardistAgent": "Keys",
        }
        
        return track_names.get(class_name, role.name.title())
    
    def _update_context_from_result(
        self,
        context: PerformanceContext,
        result: PerformanceResult,
        role: AgentRole
    ) -> None:
        """Update context with performance data for subsequent performers."""
        if role == AgentRole.DRUMS:
            # Extract kick/snare positions for bass locking
            kick_ticks = []
            snare_ticks = []
            
            for note in result.notes:
                # Common kick pitches: 35, 36, 50 (kebero bass)
                if note.pitch in [35, 36, 50]:
                    kick_ticks.append(note.tick)
                # Common snare pitches: 38, 40, 51 (kebero slap)
                elif note.pitch in [38, 40, 51]:
                    snare_ticks.append(note.tick)
            
            context.update_from_performance(kick_ticks=kick_ticks, snare_ticks=snare_ticks)
        
        elif role in [AgentRole.LEAD, AgentRole.STRINGS]:
            # Extract melody notes for harmonization
            melody = [note.pitch for note in result.notes]
            context.update_from_performance(melody=melody)


# =============================================================================
# MODULE EXPORTS
# =============================================================================

__all__ = [
    "OfflineConductor",
    "ETHIOPIAN_INSTRUMENTS",
    "AGENT_CLASSES",
]
