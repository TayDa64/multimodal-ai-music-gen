"""
Conductor Agent Interface

The Conductor orchestrates all performer agents, handling:
- Prompt interpretation
- Style research
- Score creation (arrangement)
- Ensemble assembly
- Performance coordination

This module defines the abstract interface. Implementations include:
- OfflineConductor (Stage 1): Uses existing procedural modules
- APIConductor (Stage 2): Integrates with Copilot/Gemini APIs

Design Philosophy:
    The Conductor is like a real orchestra conductor - they interpret
    the score, give cues, manage dynamics, and coordinate all performers.
    They don't play an instrument themselves.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from .base import AgentRole, IPerformerAgent
    from .context import PerformanceScore
    from ..prompt_parser import ParsedPrompt
    from ..midi_generator import NoteEvent


class IConductorAgent(ABC):
    """
    Abstract interface for Conductor agents.
    
    The Conductor orchestrates all performer agents, handling the
    high-level flow of music generation from prompt to final tracks.
    
    Workflow:
        1. interpret_prompt() - Parse user intent
        2. research_style() - Gather style intelligence
        3. create_score() - Build arrangement structure
        4. assemble_ensemble() - Create and configure performers
        5. conduct_performance() - Coordinate all performers
    
    Implementation Notes:
        - Stage 1 (Offline): Wrap existing PromptParser, Arranger, etc.
        - Stage 2 (API): Use LLM APIs for interpretation and decisions
    
    Example:
        ```python
        conductor = OfflineConductor()
        parsed = conductor.interpret_prompt("dark trap beat 140bpm")
        style = conductor.research_style(parsed)
        score = conductor.create_score(parsed, style)
        ensemble = conductor.assemble_ensemble(parsed, style)
        tracks = conductor.conduct_performance(score, ensemble)
        ```
    """
    
    @abstractmethod
    def interpret_prompt(self, prompt: str) -> 'ParsedPrompt':
        """
        Parse natural language into musical parameters.
        
        This is the first step in the generation pipeline. The conductor
        extracts BPM, key, genre, instruments, mood, and other musical
        parameters from the user's free-form text prompt.
        
        Args:
            prompt: Natural language description of desired music.
                   Examples:
                   - "dark trap beat 140bpm in F minor"
                   - "chill lofi with vinyl crackle and jazzy chords"
                   - "ethiopian eskista dance music with kebero drums"
        
        Returns:
            ParsedPrompt dataclass with extracted parameters.
            Unknown/unspecified values will have sensible defaults.
        
        Implementation Notes:
            - Stage 1: Use existing PromptParser
            - Stage 2: Use LLM for more nuanced understanding
        """
        pass
    
    @abstractmethod
    def research_style(
        self,
        parsed: 'ParsedPrompt',
        reference_audio: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Research the target style and build intelligence.
        
        Gathers information about the requested style/genre:
        - Genre templates (mandatory/forbidden elements)
        - FX chain recommendations
        - Recommended personality presets
        - Reference audio analysis (if provided)
        
        Args:
            parsed: ParsedPrompt from interpret_prompt()
            reference_audio: Optional path to reference audio file
                           for style matching
        
        Returns:
            Dictionary with style intelligence:
            {
                "template": GenreTemplate,
                "mandatory_elements": List[str],
                "forbidden_elements": List[str],
                "personality_map": Dict[AgentRole, str],
                "fx_chains": Dict[str, List[str]],
                "reference_features": Optional[Dict]
            }
        
        Implementation Notes:
            - Use GenreIntelligence for template lookup
            - Use ReferenceAnalyzer for audio analysis
            - This data informs ensemble assembly and personality selection
        """
        pass
    
    @abstractmethod
    def create_score(
        self,
        parsed: 'ParsedPrompt',
        style_intel: Dict[str, Any]
    ) -> 'PerformanceScore':
        """
        Create the performance score (structure + cues).
        
        This is like writing the sheet music and conductor's notes.
        Defines the song structure, tempo map, chord progression,
        tension curve, and cue points.
        
        Args:
            parsed: ParsedPrompt with musical parameters
            style_intel: Style intelligence from research_style()
        
        Returns:
            PerformanceScore containing:
            - sections: Ordered list of SongSections
            - tempo_map: Tick -> BPM mapping
            - key_map: Tick -> Key mapping
            - chord_map: Tick -> Chord mapping
            - tension_curve: Per-beat tension values
            - cue_points: Fill/drop/build cue locations
        
        Implementation Notes:
            - Use existing Arranger for section generation
            - Use TensionArcGenerator for tension curve
            - Identify cue points (section boundaries, builds, drops)
        """
        pass
    
    @abstractmethod
    def assemble_ensemble(
        self,
        parsed: 'ParsedPrompt',
        style_intel: Dict[str, Any]
    ) -> Dict['AgentRole', 'IPerformerAgent']:
        """
        Create and configure performer agents for this piece.
        
        Selects appropriate agents and configures their personalities
        based on the style requirements. This is like hiring musicians
        for a session - you choose players whose style fits the music.
        
        Args:
            parsed: ParsedPrompt with instrument requirements
            style_intel: Style intelligence with personality recommendations
        
        Returns:
            Dictionary mapping AgentRole to configured IPerformerAgent.
            Not all roles will necessarily have agents (depends on
            instruments requested/excluded).
        
        Implementation Notes:
            - Check parsed.instruments and parsed.excluded_instruments
            - Use GENRE_PERSONALITY_MAP from style_intel
            - Create agents via AgentFactory or AgentRegistry
            - Configure personalities based on genre
        """
        pass
    
    @abstractmethod
    def conduct_performance(
        self,
        score: 'PerformanceScore',
        ensemble: Dict['AgentRole', 'IPerformerAgent']
    ) -> Dict[str, List['NoteEvent']]:
        """
        Coordinate all performers to generate the full piece.
        
        This is the main performance loop. The Conductor:
        1. Iterates through sections in the score
        2. Builds PerformanceContext for each section
        3. Calls each performer's perform() method
        4. Updates context with inter-agent data (kick positions, etc.)
        5. Processes cue points (fills, drops)
        6. Collects all notes by track
        
        Args:
            score: PerformanceScore from create_score()
            ensemble: Dict of configured performers from assemble_ensemble()
        
        Returns:
            Dictionary mapping track name to list of NoteEvents.
            Track names typically match role names: "drums", "bass", etc.
        
        Implementation Notes:
            - Process sections in order
            - Build context with tension, chords, energy from score
            - Call performers in dependency order (drums before bass)
            - Pass kick/snare positions to bass for locking
            - Handle cue points by calling react_to_cue()
        
        Example return:
            {
                "drums": [NoteEvent(...), NoteEvent(...), ...],
                "bass": [NoteEvent(...), NoteEvent(...), ...],
                "chords": [NoteEvent(...), NoteEvent(...), ...],
            }
        """
        pass
    
    def generate(
        self,
        prompt: str,
        reference_audio: Optional[str] = None
    ) -> Dict[str, List['NoteEvent']]:
        """
        Convenience method for full generation pipeline.
        
        Runs the complete workflow:
        interpret_prompt -> research_style -> create_score ->
        assemble_ensemble -> conduct_performance
        
        Args:
            prompt: Natural language prompt
            reference_audio: Optional reference audio path
            
        Returns:
            Dictionary mapping track names to NoteEvent lists
        """
        parsed = self.interpret_prompt(prompt)
        style_intel = self.research_style(parsed, reference_audio)
        score = self.create_score(parsed, style_intel)
        ensemble = self.assemble_ensemble(parsed, style_intel)
        return self.conduct_performance(score, ensemble)
