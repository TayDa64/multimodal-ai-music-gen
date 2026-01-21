# Agents-as-Performers Architecture Implementation Plan

**Version**: 1.1  
**Date**: January 21, 2026  
**Status**: PLANNING PHASE  

---

## Executive Summary

This document defines a comprehensive architectural transformation from the current procedural music generation system to an **agent-based performer model**. The architecture treats each musical role (drums, bass, keys, etc.) as an autonomous agent with its own personality, style, and decision-making capability—coordinated by a Conductor Agent.

### Key Innovation: Dynamic Agent Spawning

The Conductor can **dynamically spawn performer agents** for any requested instrument, enabling:
- **Grand Orchestrations**: Full string sections, brass ensembles, choirs
- **Arbitrary Combinations**: Ethiopian kebero + trap 808s + jazz piano
- **Extensible Architecture**: New instrument agents added without code changes

### Two-Stage Roadmap

| Stage | Focus | Backend | Timeline |
|-------|-------|---------|----------|
| **Stage 1** | Offline Base Model | Rule-based + ML-free | 4-6 weeks |
| **Stage 2** | API-Integrated Agentic System | Copilot/Gemini APIs | TBD |

---

## 1. Current State Analysis

### 1.1 Existing Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                          main.py                                 │
│        (Orchestrates the entire generation pipeline)             │
└─────────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        ▼                     ▼                     ▼
┌──────────────┐    ┌──────────────────┐    ┌─────────────┐
│ PromptParser │    │    Arranger      │    │ MidiGenerator│
│              │───▶│   (Structure)    │───▶│   (Notes)    │
└──────────────┘    └──────────────────┘    └─────────────┘
                                                   │
                    ┌──────────────────────────────┼─────────────┐
                    ▼                              ▼             ▼
            ┌─────────────┐               ┌─────────────┐  ┌──────────┐
            │  Strategies │               │TakeGenerator│  │AudioRender│
            │ (Genre-spec)│               │  (Variants) │  │(Synthesis)│
            └─────────────┘               └─────────────┘  └──────────┘
```

### 1.2 Current Module Responsibilities

| Module | Current Role | Lines | Coupling |
|--------|--------------|-------|----------|
| `prompt_parser.py` | NLP → musical parameters | 1313 | Low |
| `arranger.py` | Song structure, sections, motifs | 1076 | Medium |
| `midi_generator.py` | Note generation, humanization | 2660 | **High** |
| `strategies/*.py` | Genre-specific drum patterns | ~150 each | Medium |
| `take_generator.py` | Multi-take variations | 1840 | Low |
| `audio_renderer.py` | MIDI → Audio synthesis | 1994 | Medium |
| `synthesizers/*.py` | Synth engine abstraction | ~300 total | **Clean** |

### 1.3 Key Observations

**Strengths to Preserve:**
- Clean `ISynthesizer` interface pattern in `synthesizers/`
- Strategy pattern in `strategies/` for drum generation
- `TakeGenerator` for variation generation
- `GenreIntelligence` for style-aware decisions
- `InstrumentResolutionService` for dynamic instrument mapping

**Problems to Solve:**
- `MidiGenerator` is monolithic (2660 lines, handles ALL roles)
- No per-instrument "personality" or style coherence
- Strategies only cover drums, not full instrument suite
- No shared performance context between instruments
- Difficult to swap offline ↔ API-backed generation

---

## 2. Target Architecture

### 2.1 High-Level Design

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           CONDUCTOR AGENT                                    │
│  ┌─────────────┐  ┌───────────────┐  ┌─────────────┐  ┌────────────────┐   │
│  │   Parser    │  │   Researcher  │  │  Arranger   │  │  Agent Spawner │   │
│  │ (NLP→Music) │  │ (Style Intel) │  │ (Structure) │  │ (Dynamic Ens.) │   │
│  └─────────────┘  └───────────────┘  └─────────────┘  └────────────────┘   │
└───────────────────────────────┬─────────────────────────────────────────────┘
                                │
                    ┌───────────┴───────────┐
                    │   AGENT REGISTRY      │
                    │  ┌─────────────────┐  │
                    │  │ Instrument→Agent│  │
                    │  │    Mappings     │  │
                    │  └─────────────────┘  │
                    └───────────┬───────────┘
                                │ spawn_agent(instrument)
          ┌────────────┬────────┴────────┬────────────┬────────────┐
          ▼            ▼                 ▼            ▼            ▼
    ┌──────────┐ ┌──────────┐    ┌──────────┐ ┌──────────┐ ┌──────────┐
    │ DRUMMER  │ │ BASSIST  │    │ VIOLINS  │ │  MASENQO │ │  CHOIR   │
    │  Agent   │ │  Agent   │    │ Section  │ │  Agent   │ │  Agent   │
    └──────────┘ └──────────┘    └──────────┘ └──────────┘ └──────────┘
          │            │                 │            │            │
          └────────────┴─────────────────┴────────────┴────────────┘
                                │
    ┌─────────────────────────────────────────────────────────────────────┐
    │                    PERFORMANCE CONTEXT (Shared State)                │
    │  ┌─────────┐  ┌────────┐  ┌─────────┐  ┌────────────┐  ┌────────┐  │
    │  │ Tempo   │  │  Key   │  │ Section │  │TensionCurve│  │ Cues   │  │
    │  │ + Swing │  │+ Scale │  │+ Energy │  │  + Phase   │  │+ Fills │  │
    │  └─────────┘  └────────┘  └─────────┘  └────────────┘  └────────┘  │
    └─────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
    ┌─────────────────────────────────────────────────────────────────────┐
    │                      SYNTHESIS LAYER                                 │
    │  ┌──────────────┐  ┌────────────────┐  ┌─────────────────────────┐ │
    │  │ Offline Synth│  │ SoundFont Synth │  │   API Synth (Stage 2)  │ │
    │  │ (Procedural) │  │  (FluidSynth)   │  │ (Copilot/Gemini Audio) │ │
    │  └──────────────┘  └────────────────┘  └─────────────────────────┘ │
    └─────────────────────────────────────────────────────────────────────┘
```

### 2.2 Dynamic Agent Spawning

The Conductor dynamically spawns performer agents based on the prompt analysis:

```python
# multimodal_gen/agents/registry.py

class AgentRegistry:
    """
    Registry of instrument → agent type mappings.
    
    Allows the Conductor to spawn appropriate agents for any
    instrument requested in the prompt.
    """
    
    # Core role mappings (always available)
    CORE_AGENTS = {
        "drums": DrummerAgent,
        "bass": BassistAgent,
        "piano": KeyboardistAgent,
        "keys": KeyboardistAgent,
        "synth": SynthAgent,
        "lead": MelodistAgent,
        "pad": PadAgent,
    }
    
    # Orchestral instruments
    ORCHESTRAL_AGENTS = {
        # Strings
        "violin": StringAgent,
        "viola": StringAgent,
        "cello": StringAgent,
        "contrabass": StringAgent,
        "strings": StringSectionAgent,  # Spawns multiple string agents
        
        # Woodwinds
        "flute": WoodwindAgent,
        "clarinet": WoodwindAgent,
        "oboe": WoodwindAgent,
        "bassoon": WoodwindAgent,
        
        # Brass
        "trumpet": BrassAgent,
        "trombone": BrassAgent,
        "french_horn": BrassAgent,
        "tuba": BrassAgent,
        "brass": BrassSectionAgent,  # Spawns multiple brass agents
    }
    
    # World/Ethnic instruments
    WORLD_AGENTS = {
        # Ethiopian
        "masenqo": MasenqoAgent,      # Single-string fiddle
        "krar": KrarAgent,            # 6-string lyre
        "begena": BegenaAgent,        # Large lyre
        "washint": WashintAgent,      # Bamboo flute
        "kebero": KeberoAgent,        # Double-headed drum
        
        # Other world
        "sitar": SitarAgent,
        "tabla": TablaAgent,
        "koto": KotoAgent,
        "shamisen": ShamisenAgent,
    }
    
    # Section agents (spawn multiple performers)
    SECTION_AGENTS = {
        "string_section": StringSectionAgent,
        "brass_section": BrassSectionAgent,
        "choir": ChoirAgent,
        "woodwind_section": WoodwindSectionAgent,
    }
    
    @classmethod
    def get_agent_class(cls, instrument: str) -> type:
        """Get the agent class for an instrument."""
        instrument = instrument.lower().replace(" ", "_")
        
        # Check all registries
        for registry in [cls.CORE_AGENTS, cls.ORCHESTRAL_AGENTS, 
                         cls.WORLD_AGENTS, cls.SECTION_AGENTS]:
            if instrument in registry:
                return registry[instrument]
        
        # Fallback to generic melodic agent
        return GenericMelodicAgent
    
    @classmethod
    def spawn_agent(
        cls,
        instrument: str,
        genre: str,
        personality: AgentPersonality = None
    ) -> IPerformerAgent:
        """
        Spawn an agent for the given instrument.
        
        This is the main factory method used by the Conductor.
        """
        agent_class = cls.get_agent_class(instrument)
        return agent_class(
            instrument_name=instrument,
            genre=genre,
            personality=personality or cls._get_default_personality(instrument, genre)
        )
    
    @classmethod
    def spawn_section(
        cls,
        section_type: str,
        size: int,
        genre: str
    ) -> List[IPerformerAgent]:
        """
        Spawn a section of performers (e.g., string quartet, brass quintet).
        
        Example:
            spawn_section("strings", 4, "classical") →
                [Violin1Agent, Violin2Agent, ViolaAgent, CelloAgent]
        """
        if section_type == "strings":
            return cls._spawn_string_section(size, genre)
        elif section_type == "brass":
            return cls._spawn_brass_section(size, genre)
        elif section_type == "choir":
            return cls._spawn_choir(size, genre)
        else:
            return [cls.spawn_agent(section_type, genre) for _ in range(size)]


class SectionAgent(IPerformerAgent):
    """
    Meta-agent that coordinates multiple sub-performers.
    
    For example, a StringSectionAgent contains Violin1, Violin2,
    Viola, and Cello agents and coordinates their voicings.
    """
    
    def __init__(self, section_name: str, sub_agents: List[IPerformerAgent]):
        self._section_name = section_name
        self._sub_agents = sub_agents
    
    @property
    def role(self) -> AgentRole:
        return AgentRole.SECTION
    
    @property
    def name(self) -> str:
        return f"{self._section_name} ({len(self._sub_agents)} performers)"
    
    def perform(
        self,
        context: PerformanceContext,
        section: 'SongSection',
        personality: Optional[AgentPersonality] = None
    ) -> PerformanceResult:
        """
        Coordinate all sub-agents to perform together.
        
        Handles voice leading, part distribution, and ensemble balance.
        """
        all_notes = []
        decisions = [f"Section {self._section_name} coordinating {len(self._sub_agents)} performers"]
        
        # Distribute chord voicings across instruments
        voicings = self._distribute_voicings(context)
        
        for agent, voicing in zip(self._sub_agents, voicings):
            # Give each agent their voice assignment
            agent_context = self._create_agent_context(context, voicing)
            result = agent.perform(agent_context, section, personality)
            all_notes.extend(result.notes)
            decisions.extend(result.decisions_made)
        
        return PerformanceResult(
            notes=all_notes,
            agent_role=self.role,
            agent_name=self.name,
            personality_applied=personality or AgentPersonality(),
            decisions_made=decisions,
            patterns_used=[],
            fill_locations=[]
        )
```

#### Grand Orchestration Example

```python
# User prompt: "Epic orchestral piece with full strings, brass, and Ethiopian instruments"

# Conductor analysis:
parsed = conductor.interpret_prompt(prompt)
# parsed.instruments = ["strings", "brass", "masenqo", "kebero"]

# Conductor spawns appropriate agents:
ensemble = {
    # String section (4 agents: 2 violins, viola, cello)
    "strings": AgentRegistry.spawn_section("strings", 4, "orchestral"),
    
    # Brass section (4 agents: 2 trumpets, horn, trombone)
    "brass": AgentRegistry.spawn_section("brass", 4, "orchestral"),
    
    # Ethiopian instruments (individual agents)
    "masenqo": AgentRegistry.spawn_agent("masenqo", "ethiopian"),
    "kebero": AgentRegistry.spawn_agent("kebero", "ethiopian"),
}

# Total: 10 performer agents coordinated by 1 conductor
```

### 2.3 Core Interfaces

#### 2.2.1 `IPerformerAgent` (Abstract Base)

```python
# multimodal_gen/agents/base.py

from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from enum import Enum

class AgentRole(Enum):
    """Musical roles that agents can fulfill."""
    DRUMS = "drums"
    BASS = "bass"
    KEYS = "keys"
    LEAD = "lead"
    PAD = "pad"
    STRINGS = "strings"
    BRASS = "brass"
    PERCUSSION = "percussion"
    FX = "fx"


@dataclass
class PerformanceContext:
    """
    Shared state passed to all agents for coherent performance.
    
    This is the "sheet music" + "conductor gestures" that all
    performers react to in real-time.
    """
    # Temporal
    bpm: float
    time_signature: tuple
    current_section: 'SongSection'
    section_position_beats: float  # Where we are in the section
    
    # Harmonic
    key: str
    scale_notes: List[int]
    current_chord: Optional[str]
    chord_progression: List[str]
    
    # Energy/Dynamics
    tension: float  # 0.0 - 1.0
    energy_level: float
    density_target: float
    
    # Performance cues
    fill_opportunity: bool
    breakdown_mode: bool
    build_mode: bool
    
    # Inter-agent communication
    last_kick_tick: Optional[int]  # For bass to lock to
    last_snare_tick: Optional[int]
    melody_notes: List[int]  # For harmonization
    
    # Reference analysis (from audio)
    reference_features: Optional[Dict[str, Any]] = None


@dataclass
class AgentPersonality:
    """
    Configuration that makes each agent instance unique.
    
    Think of this as the "musician's style" - two drummers
    given the same chart will play differently based on personality.
    """
    # Core style
    aggressiveness: float = 0.5      # 0=laid-back, 1=intense
    complexity: float = 0.5          # 0=simple, 1=intricate
    consistency: float = 0.7         # 0=wild, 1=metronomic
    
    # Timing feel
    push_pull: float = 0.0           # -1=behind, 0=on, 1=ahead
    swing_affinity: float = 0.0      # How much they like swing
    
    # Creative tendencies
    fill_frequency: float = 0.3      # How often they add fills
    ghost_note_density: float = 0.5  # Subtlety of ghost notes
    variation_tendency: float = 0.4  # How much they vary patterns
    
    # Signature elements
    signature_patterns: List[str] = None  # Pattern names they favor
    avoided_patterns: List[str] = None    # Patterns they never use
    
    def __post_init__(self):
        self.signature_patterns = self.signature_patterns or []
        self.avoided_patterns = self.avoided_patterns or []


@dataclass
class PerformanceResult:
    """Output from a performer agent."""
    notes: List['NoteEvent']
    agent_role: AgentRole
    agent_name: str
    personality_applied: AgentPersonality
    
    # Metadata for debugging/learning
    decisions_made: List[str]  # Log of creative choices
    patterns_used: List[str]
    fill_locations: List[int]  # Ticks where fills occurred


class IPerformerAgent(ABC):
    """
    Abstract interface for all performer agents.
    
    Each performer is responsible for generating notes for their
    instrument role, reacting to the shared PerformanceContext.
    
    Stage 1: Offline implementations using current procedural methods
    Stage 2: API-backed implementations calling Copilot/Gemini
    """
    
    @property
    @abstractmethod
    def role(self) -> AgentRole:
        """The musical role this agent fulfills."""
        pass
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable name for this agent instance."""
        pass
    
    @abstractmethod
    def perform(
        self,
        context: PerformanceContext,
        section: 'SongSection',
        personality: Optional[AgentPersonality] = None
    ) -> PerformanceResult:
        """
        Generate notes for the given section and context.
        
        Args:
            context: Shared performance state
            section: The song section to generate for
            personality: Optional personality override
            
        Returns:
            PerformanceResult with generated notes
        """
        pass
    
    @abstractmethod
    def react_to_cue(
        self,
        cue_type: str,
        context: PerformanceContext
    ) -> List['NoteEvent']:
        """
        React to a performance cue (fill, stop, accent, etc.)
        
        Args:
            cue_type: Type of cue ("fill", "stop", "build", "drop")
            context: Current performance context
            
        Returns:
            Notes for the cue response
        """
        pass
    
    def set_personality(self, personality: AgentPersonality) -> None:
        """Update the agent's personality configuration."""
        self._personality = personality
    
    def get_personality(self) -> AgentPersonality:
        """Get current personality configuration."""
        return getattr(self, '_personality', AgentPersonality())
```

#### 2.2.2 `IConductorAgent` (Orchestrator)

```python
# multimodal_gen/agents/conductor.py

from abc import ABC, abstractmethod
from typing import List, Dict, Optional
from dataclasses import dataclass

@dataclass
class PerformanceScore:
    """
    The "musical score" that the conductor prepares.
    
    Contains all the information performers need to play
    together coherently.
    """
    sections: List['SongSection']
    tempo_map: Dict[int, float]  # tick -> bpm
    key_map: Dict[int, str]      # tick -> key
    chord_map: Dict[int, str]    # tick -> chord
    tension_curve: List[float]   # Per-beat tension values
    cue_points: List[Dict]       # Fills, drops, builds


class IConductorAgent(ABC):
    """
    The Conductor orchestrates all performer agents.
    
    Responsibilities:
    1. Parse user prompt into musical parameters
    2. Research style/genre requirements
    3. Create arrangement structure (sections)
    4. Coordinate performer agents
    5. Ensure musical coherence
    """
    
    @abstractmethod
    def interpret_prompt(self, prompt: str) -> 'ParsedPrompt':
        """Parse natural language into musical parameters."""
        pass
    
    @abstractmethod
    def research_style(
        self,
        parsed: 'ParsedPrompt',
        reference_audio: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Research the target style and build intelligence.
        
        Returns:
            Style dictionary with genre rules, recommended
            instruments, FX chains, etc.
        """
        pass
    
    @abstractmethod
    def create_score(
        self,
        parsed: 'ParsedPrompt',
        style_intel: Dict[str, Any]
    ) -> PerformanceScore:
        """
        Create the performance score (structure + cues).
        
        This is like writing the sheet music and conductor's notes.
        """
        pass
    
    @abstractmethod
    def assemble_ensemble(
        self,
        parsed: 'ParsedPrompt',
        style_intel: Dict[str, Any]
    ) -> Dict[AgentRole, IPerformerAgent]:
        """
        Create and configure performer agents for this piece.
        
        Selects appropriate agents and configures their personalities
        based on the style requirements.
        """
        pass
    
    @abstractmethod
    def conduct_performance(
        self,
        score: PerformanceScore,
        ensemble: Dict[AgentRole, IPerformerAgent]
    ) -> Dict[str, List['NoteEvent']]:
        """
        Coordinate all performers to generate the full piece.
        
        Iterates through sections, updates context, collects
        performances from all agents.
        
        Returns:
            Dict mapping track name to notes
        """
        pass
```

---

## 3. Detailed Implementation Plan

### 3.1 Phase 1: Foundation (Week 1-2)

#### Task 1.1: Create Agent Package Structure

```
multimodal_gen/
├── agents/
│   ├── __init__.py          # Package exports
│   ├── base.py              # IPerformerAgent, AgentRole, etc.
│   ├── conductor.py         # IConductorAgent
│   ├── context.py           # PerformanceContext, PerformanceScore
│   ├── personality.py       # AgentPersonality, PersonalityPresets
│   │
│   ├── performers/          # Performer implementations
│   │   ├── __init__.py
│   │   ├── base_performer.py    # Common performer utilities
│   │   ├── drummer.py           # DrummerAgent
│   │   ├── bassist.py           # BassistAgent
│   │   ├── keyist.py            # KeyboardistAgent
│   │   ├── melodist.py          # MelodistAgent (lead)
│   │   ├── padist.py            # PadAgent (ambient)
│   │   └── percussionist.py     # PercussionAgent
│   │
│   ├── strategies/          # Strategy adapters (bridge to existing)
│   │   ├── __init__.py
│   │   └── strategy_adapter.py  # Wraps GenreStrategy for agents
│   │
│   └── factory.py           # AgentFactory for creating ensembles
```

**Files to Create:**
| File | Purpose | Priority |
|------|---------|----------|
| `agents/__init__.py` | Package exports | P0 |
| `agents/base.py` | Core interfaces | P0 |
| `agents/context.py` | Shared state classes | P0 |
| `agents/personality.py` | Personality system | P1 |
| `agents/conductor.py` | Conductor interface | P0 |
| `agents/factory.py` | Agent instantiation | P1 |

#### Task 1.2: Extract PerformanceContext from Existing Code

**Source mapping:**
| Current Location | Becomes | Notes |
|------------------|---------|-------|
| `ParsedPrompt.bpm, key, scale_type` | `PerformanceContext.bpm/key/scale_notes` | Direct map |
| `SongSection.config.energy_level` | `PerformanceContext.energy_level` | Direct map |
| `TensionArc.get_tension_at()` | `PerformanceContext.tension` | Compute per-beat |
| `SectionConfig.drum_density` | `PerformanceContext.density_target` | Direct map |
| (NEW) | `PerformanceContext.last_kick_tick` | Inter-agent sync |

#### Task 1.3: Define Personality Presets

```python
# agents/personality.py

DRUMMER_PRESETS = {
    "session_pro": AgentPersonality(
        aggressiveness=0.4,
        complexity=0.5,
        consistency=0.9,
        push_pull=0.0,
        fill_frequency=0.2,
        ghost_note_density=0.6
    ),
    "jazz_master": AgentPersonality(
        aggressiveness=0.3,
        complexity=0.8,
        consistency=0.5,
        push_pull=-0.1,  # Slightly behind
        swing_affinity=0.8,
        fill_frequency=0.4,
        ghost_note_density=0.8
    ),
    "trap_producer": AgentPersonality(
        aggressiveness=0.7,
        complexity=0.6,
        consistency=0.8,
        push_pull=0.0,
        fill_frequency=0.15,
        ghost_note_density=0.4,
        signature_patterns=["trap_hihat_roll", "808_slide"]
    ),
    "punk_energy": AgentPersonality(
        aggressiveness=0.9,
        complexity=0.3,
        consistency=0.6,
        push_pull=0.15,  # Slightly ahead
        fill_frequency=0.5,
        ghost_note_density=0.2
    ),
}

BASSIST_PRESETS = {
    "pocket_player": AgentPersonality(
        aggressiveness=0.3,
        complexity=0.4,
        consistency=0.95,
        push_pull=-0.05,  # Sits in the pocket
    ),
    "melodic_explorer": AgentPersonality(
        aggressiveness=0.5,
        complexity=0.7,
        consistency=0.7,
        variation_tendency=0.6,
    ),
    "808_specialist": AgentPersonality(
        aggressiveness=0.6,
        complexity=0.5,
        consistency=0.8,
        signature_patterns=["808_glide", "sub_octave"]
    ),
}

# Genre -> Role -> Preset name mapping
GENRE_PERSONALITY_MAP = {
    "trap": {
        AgentRole.DRUMS: "trap_producer",
        AgentRole.BASS: "808_specialist",
        AgentRole.KEYS: "pad_specialist",
    },
    "lofi": {
        AgentRole.DRUMS: "session_pro",  # With swing
        AgentRole.BASS: "pocket_player",
        AgentRole.KEYS: "jazz_voicings",
    },
    "jazz": {
        AgentRole.DRUMS: "jazz_master",
        AgentRole.BASS: "melodic_explorer",
        AgentRole.KEYS: "jazz_voicings",
    },
}
```

---

### 3.2 Phase 2: Performer Agents (Week 2-3)

#### Task 2.1: Create DrummerAgent

**Implementation approach:** Wrap existing `GenreStrategy` implementations.

```python
# agents/performers/drummer.py

from typing import List, Optional
from ..base import IPerformerAgent, AgentRole, PerformanceContext, PerformanceResult, AgentPersonality
from ...strategies.registry import StrategyRegistry


class DrummerAgent(IPerformerAgent):
    """
    Drummer agent - wraps existing GenreStrategy implementations.
    
    Stage 1: Uses rule-based strategies from strategies/*.py
    Stage 2: Can be swapped for API-backed implementation
    """
    
    def __init__(
        self,
        name: str = "Session Drummer",
        genre: str = "default",
        personality: AgentPersonality = None
    ):
        self._name = name
        self._genre = genre
        self._personality = personality or AgentPersonality()
        self._strategy = StrategyRegistry.get_strategy(genre)
        self._decisions_log: List[str] = []
    
    @property
    def role(self) -> AgentRole:
        return AgentRole.DRUMS
    
    @property
    def name(self) -> str:
        return self._name
    
    def perform(
        self,
        context: PerformanceContext,
        section: 'SongSection',
        personality: Optional[AgentPersonality] = None
    ) -> PerformanceResult:
        """Generate drum notes for the section."""
        pers = personality or self._personality
        self._decisions_log = []
        
        # Apply personality to strategy config
        self._apply_personality_to_context(context, pers)
        
        # Use existing strategy to generate drums
        notes = self._strategy.generate_drums(
            section=section,
            parsed=self._build_parsed_stub(context),
            tension=context.tension
        )
        
        # Apply personality-based post-processing
        notes = self._apply_personality_to_notes(notes, pers, context)
        
        return PerformanceResult(
            notes=notes,
            agent_role=self.role,
            agent_name=self.name,
            personality_applied=pers,
            decisions_made=self._decisions_log,
            patterns_used=self._get_patterns_used(),
            fill_locations=self._get_fill_locations(notes, section)
        )
    
    def react_to_cue(
        self,
        cue_type: str,
        context: PerformanceContext
    ) -> List['NoteEvent']:
        """React to performance cues with fills or stops."""
        if cue_type == "fill":
            return self._generate_fill(context)
        elif cue_type == "stop":
            return []  # Silence
        elif cue_type == "build":
            return self._generate_build(context)
        elif cue_type == "drop":
            return self._generate_drop_hit(context)
        return []
    
    def _apply_personality_to_notes(
        self,
        notes: List['NoteEvent'],
        personality: AgentPersonality,
        context: PerformanceContext
    ) -> List['NoteEvent']:
        """Apply personality-based modifications to generated notes."""
        result = []
        
        for note in notes:
            # Timing: push/pull based on personality
            timing_offset = int(personality.push_pull * 20)  # ±20 ticks
            modified = note
            modified.start_tick += timing_offset
            
            # Velocity: aggressiveness affects dynamics
            vel_mult = 0.8 + (personality.aggressiveness * 0.4)  # 0.8-1.2
            modified.velocity = min(127, int(modified.velocity * vel_mult))
            
            # Ghost notes: based on density preference
            # (existing notes kept, ghost addition handled elsewhere)
            
            result.append(modified)
            
        self._decisions_log.append(
            f"Applied {personality.aggressiveness:.1%} aggressiveness, "
            f"{personality.push_pull:+.2f} timing push"
        )
        
        return result
```

#### Task 2.2: Create BassistAgent

```python
# agents/performers/bassist.py

class BassistAgent(IPerformerAgent):
    """
    Bassist agent - generates bass lines that lock with drums.
    
    Key behaviors:
    - Locks to kick drum pattern
    - Follows chord roots
    - Applies groove variations based on personality
    """
    
    def __init__(
        self,
        name: str = "Session Bassist",
        genre: str = "default",
        personality: AgentPersonality = None
    ):
        self._name = name
        self._genre = genre
        self._personality = personality or AgentPersonality()
    
    def perform(
        self,
        context: PerformanceContext,
        section: 'SongSection',
        personality: Optional[AgentPersonality] = None
    ) -> PerformanceResult:
        """Generate bass notes that lock with the drums."""
        pers = personality or self._personality
        
        # Get chord progression for this section
        chord_roots = self._extract_chord_roots(context)
        
        # Lock to kick pattern if available
        kick_ticks = self._get_kick_alignment_points(context)
        
        # Generate bass line
        notes = self._generate_bass_line(
            section=section,
            chord_roots=chord_roots,
            kick_ticks=kick_ticks,
            context=context,
            personality=pers
        )
        
        return PerformanceResult(
            notes=notes,
            agent_role=self.role,
            agent_name=self.name,
            personality_applied=pers,
            decisions_made=self._decisions_log,
            patterns_used=[],
            fill_locations=[]
        )
    
    def _generate_bass_line(
        self,
        section: 'SongSection',
        chord_roots: List[int],
        kick_ticks: List[int],
        context: PerformanceContext,
        personality: AgentPersonality
    ) -> List['NoteEvent']:
        """Generate the actual bass notes."""
        # This wraps existing midi_generator._generate_bass()
        # but adds personality-based variations
        pass
```

#### Task 2.3: Create KeyboardistAgent, MelodistAgent, etc.

Similar pattern for each role, wrapping existing generation logic.

---

### 3.3 Phase 3: Conductor Implementation (Week 3-4)

#### Task 3.1: Create OfflineConductor

```python
# agents/conductor_offline.py

from typing import Dict, List, Any, Optional
from .base import AgentRole, IPerformerAgent
from .conductor import IConductorAgent, PerformanceScore
from .context import PerformanceContext
from .factory import AgentFactory


class OfflineConductor(IConductorAgent):
    """
    Conductor implementation for Stage 1 (offline).
    
    Uses existing modules:
    - PromptParser for interpretation
    - GenreIntelligence for style research
    - Arranger for score creation
    - AgentFactory for ensemble assembly
    """
    
    def __init__(
        self,
        agent_factory: AgentFactory = None,
        instrument_service: 'InstrumentResolutionService' = None
    ):
        self._factory = agent_factory or AgentFactory()
        self._instrument_service = instrument_service
        self._parser = PromptParser()
        self._arranger = Arranger()
    
    def interpret_prompt(self, prompt: str) -> 'ParsedPrompt':
        """Parse natural language into musical parameters."""
        return self._parser.parse(prompt)
    
    def research_style(
        self,
        parsed: 'ParsedPrompt',
        reference_audio: Optional[str] = None
    ) -> Dict[str, Any]:
        """Research style using GenreIntelligence + ReferenceAnalyzer."""
        style_intel = {}
        
        # Get genre template
        if HAS_GENRE_INTELLIGENCE:
            gi = get_genre_intelligence()
            template = gi.get_template(parsed.genre)
            style_intel['template'] = template
            style_intel['mandatory_elements'] = template.mandatory_elements
            style_intel['forbidden_elements'] = template.forbidden_elements
        
        # Analyze reference if provided
        if reference_audio:
            from .reference_analyzer import ReferenceAnalyzer
            analyzer = ReferenceAnalyzer()
            features = analyzer.analyze(reference_audio)
            style_intel['reference_features'] = features.to_generation_params()
        
        # Select personality presets based on genre
        style_intel['personality_map'] = GENRE_PERSONALITY_MAP.get(
            parsed.genre, 
            GENRE_PERSONALITY_MAP.get('default', {})
        )
        
        return style_intel
    
    def create_score(
        self,
        parsed: 'ParsedPrompt',
        style_intel: Dict[str, Any]
    ) -> PerformanceScore:
        """Create arrangement using existing Arranger."""
        arrangement = self._arranger.arrange(parsed)
        
        # Convert to PerformanceScore
        return PerformanceScore(
            sections=arrangement.sections,
            tempo_map={0: parsed.bpm},  # Static tempo for now
            key_map={0: parsed.key},
            chord_map=self._build_chord_map(arrangement),
            tension_curve=self._extract_tension_curve(arrangement),
            cue_points=self._identify_cue_points(arrangement)
        )
    
    def assemble_ensemble(
        self,
        parsed: 'ParsedPrompt',
        style_intel: Dict[str, Any]
    ) -> Dict[AgentRole, IPerformerAgent]:
        """Create performer agents with appropriate personalities."""
        ensemble = {}
        personality_map = style_intel.get('personality_map', {})
        
        # Always create drummer
        drum_personality = personality_map.get(
            AgentRole.DRUMS,
            DRUMMER_PRESETS['session_pro']
        )
        ensemble[AgentRole.DRUMS] = self._factory.create_performer(
            role=AgentRole.DRUMS,
            genre=parsed.genre,
            personality=drum_personality
        )
        
        # Create bass
        if 'bass' not in parsed.excluded_instruments:
            bass_personality = personality_map.get(
                AgentRole.BASS,
                BASSIST_PRESETS['pocket_player']
            )
            ensemble[AgentRole.BASS] = self._factory.create_performer(
                role=AgentRole.BASS,
                genre=parsed.genre,
                personality=bass_personality
            )
        
        # Create keys/chords
        if parsed.instruments or 'piano' in str(parsed.genre):
            ensemble[AgentRole.KEYS] = self._factory.create_performer(
                role=AgentRole.KEYS,
                genre=parsed.genre
            )
        
        return ensemble
    
    def conduct_performance(
        self,
        score: PerformanceScore,
        ensemble: Dict[AgentRole, IPerformerAgent]
    ) -> Dict[str, List['NoteEvent']]:
        """Coordinate all performers through the score."""
        all_tracks: Dict[str, List['NoteEvent']] = {}
        
        for section in score.sections:
            # Build context for this section
            context = self._build_context(section, score)
            
            # Conductor decides if fills should happen
            context.fill_opportunity = self._should_fill(section, score)
            
            # Each performer plays their part
            for role, agent in ensemble.items():
                result = agent.perform(
                    context=context,
                    section=section
                )
                
                # Collect notes
                track_name = self._get_track_name(role)
                if track_name not in all_tracks:
                    all_tracks[track_name] = []
                all_tracks[track_name].extend(result.notes)
                
                # Update context with this performance info
                # (for inter-agent awareness)
                self._update_context_from_performance(context, result)
        
        return all_tracks
```

---

### 3.4 Phase 4: Integration (Week 4-5)

#### Task 4.1: Create `main.py` Integration Path

```python
# In main.py - new entry point

def generate_music_agentic(
    prompt: str,
    output_path: str,
    reference_audio: str = None,
    use_agents: bool = True,  # Feature flag
    **kwargs
) -> Dict:
    """
    Generate music using the agent-based architecture.
    
    This is the new entry point that uses Conductor + Performers.
    """
    from multimodal_gen.agents import OfflineConductor, AgentFactory
    
    # Create conductor
    factory = AgentFactory()
    conductor = OfflineConductor(agent_factory=factory)
    
    # Step 1: Interpret prompt
    parsed = conductor.interpret_prompt(prompt)
    
    # Step 2: Research style
    style_intel = conductor.research_style(parsed, reference_audio)
    
    # Step 3: Create score (arrangement)
    score = conductor.create_score(parsed, style_intel)
    
    # Step 4: Assemble ensemble
    ensemble = conductor.assemble_ensemble(parsed, style_intel)
    
    # Step 5: Conduct performance
    tracks = conductor.conduct_performance(score, ensemble)
    
    # Step 6: Convert to MIDI and render
    midi_path = _tracks_to_midi(tracks, parsed, output_path)
    audio_path = _render_midi(midi_path, parsed)
    
    return {
        'midi_path': midi_path,
        'audio_path': audio_path,
        'tracks': list(tracks.keys()),
        'ensemble': {r.name: a.name for r, a in ensemble.items()},
    }
```

#### Task 4.2: Bridge Existing Strategies

```python
# agents/strategies/strategy_adapter.py

class StrategyToAgentAdapter(IPerformerAgent):
    """
    Adapts existing GenreStrategy to IPerformerAgent interface.
    
    This allows gradual migration - strategies can be used as agents
    until proper agent implementations are complete.
    """
    
    def __init__(self, strategy: GenreStrategy, role: AgentRole):
        self._strategy = strategy
        self._role = role
    
    @property
    def role(self) -> AgentRole:
        return self._role
    
    @property
    def name(self) -> str:
        return f"Strategy:{self._strategy.genre_name}"
    
    def perform(
        self,
        context: PerformanceContext,
        section: 'SongSection',
        personality: Optional[AgentPersonality] = None
    ) -> PerformanceResult:
        """Delegate to strategy's generate method."""
        # Build a ParsedPrompt stub from context
        parsed_stub = self._context_to_parsed(context)
        
        if self._role == AgentRole.DRUMS:
            notes = self._strategy.generate_drums(section, parsed_stub, context.tension)
        elif self._role == AgentRole.BASS:
            notes = self._strategy.generate_bass(section, parsed_stub, context.tension)
        elif self._role == AgentRole.KEYS:
            notes = self._strategy.generate_chords(section, parsed_stub, context.tension)
        else:
            notes = []
        
        return PerformanceResult(
            notes=notes,
            agent_role=self._role,
            agent_name=self.name,
            personality_applied=personality or AgentPersonality(),
            decisions_made=["Delegated to GenreStrategy"],
            patterns_used=[],
            fill_locations=[]
        )
```

---

### 3.5 Phase 5: Stage 2 Preparation (Week 5-6)

#### Task 5.1: Define API Agent Interface

```python
# agents/performers/api_performer.py

from abc import ABC
import asyncio
from typing import List, Optional, Dict, Any


class APIPerformerBase(IPerformerAgent, ABC):
    """
    Base class for API-backed performer agents (Stage 2).
    
    Subclass this for Copilot, Gemini, or other API providers.
    """
    
    def __init__(
        self,
        api_key: str,
        model: str,
        role: AgentRole,
        name: str
    ):
        self._api_key = api_key
        self._model = model
        self._role = role
        self._name = name
        self._personality = AgentPersonality()
    
    @property
    def role(self) -> AgentRole:
        return self._role
    
    @property
    def name(self) -> str:
        return self._name
    
    async def perform_async(
        self,
        context: PerformanceContext,
        section: 'SongSection',
        personality: Optional[AgentPersonality] = None
    ) -> PerformanceResult:
        """Async perform method for API calls."""
        prompt = self._build_prompt(context, section, personality)
        response = await self._call_api(prompt)
        notes = self._parse_response(response)
        return PerformanceResult(
            notes=notes,
            agent_role=self.role,
            agent_name=self.name,
            personality_applied=personality or self._personality,
            decisions_made=[f"API call to {self._model}"],
            patterns_used=[],
            fill_locations=[]
        )
    
    def perform(
        self,
        context: PerformanceContext,
        section: 'SongSection',
        personality: Optional[AgentPersonality] = None
    ) -> PerformanceResult:
        """Sync wrapper for async perform."""
        return asyncio.run(self.perform_async(context, section, personality))
    
    @abstractmethod
    def _build_prompt(
        self,
        context: PerformanceContext,
        section: 'SongSection',
        personality: Optional[AgentPersonality]
    ) -> str:
        """Build the prompt for the API call."""
        pass
    
    @abstractmethod
    async def _call_api(self, prompt: str) -> Dict[str, Any]:
        """Make the API call."""
        pass
    
    @abstractmethod
    def _parse_response(self, response: Dict[str, Any]) -> List['NoteEvent']:
        """Parse API response into NoteEvents."""
        pass


class CopilotPerformer(APIPerformerBase):
    """Performer backed by GitHub Copilot API."""
    
    def _build_prompt(
        self,
        context: PerformanceContext,
        section: 'SongSection',
        personality: Optional[AgentPersonality]
    ) -> str:
        """Build prompt for Copilot."""
        return f"""
You are a professional {self._role.value} musician.
Generate MIDI notes for a {section.type.value} section.

Context:
- BPM: {context.bpm}
- Key: {context.key}
- Tension: {context.tension:.2f}
- Energy: {context.energy_level:.2f}
- Bars: {section.bars}

Personality:
- Aggressiveness: {personality.aggressiveness if personality else 0.5}
- Complexity: {personality.complexity if personality else 0.5}

Output format: JSON array of notes
[{{"pitch": 60, "start_beat": 0.0, "duration_beats": 1.0, "velocity": 100}}]
"""
    
    async def _call_api(self, prompt: str) -> Dict[str, Any]:
        """Call Copilot API."""
        # Implementation depends on actual API availability
        pass
    
    def _parse_response(self, response: Dict[str, Any]) -> List['NoteEvent']:
        """Parse Copilot response."""
        pass
```

#### Task 5.2: Factory Support for API Agents

```python
# agents/factory.py

class AgentFactory:
    """Factory for creating performer and conductor agents."""
    
    def __init__(self, use_api: bool = False, api_config: Dict = None):
        self._use_api = use_api
        self._api_config = api_config or {}
    
    def create_performer(
        self,
        role: AgentRole,
        genre: str = "default",
        personality: AgentPersonality = None
    ) -> IPerformerAgent:
        """Create a performer agent for the given role."""
        
        if self._use_api:
            # Stage 2: API-backed agents
            return self._create_api_performer(role, genre, personality)
        else:
            # Stage 1: Offline agents
            return self._create_offline_performer(role, genre, personality)
    
    def _create_offline_performer(
        self,
        role: AgentRole,
        genre: str,
        personality: AgentPersonality
    ) -> IPerformerAgent:
        """Create offline (rule-based) performer."""
        if role == AgentRole.DRUMS:
            return DrummerAgent(
                name=f"{genre.title()} Drummer",
                genre=genre,
                personality=personality
            )
        elif role == AgentRole.BASS:
            return BassistAgent(
                name=f"{genre.title()} Bassist",
                genre=genre,
                personality=personality
            )
        # ... etc
    
    def _create_api_performer(
        self,
        role: AgentRole,
        genre: str,
        personality: AgentPersonality
    ) -> IPerformerAgent:
        """Create API-backed performer (Stage 2)."""
        provider = self._api_config.get('provider', 'copilot')
        
        if provider == 'copilot':
            return CopilotPerformer(
                api_key=self._api_config['api_key'],
                model=self._api_config.get('model', 'gpt-4'),
                role=role,
                name=f"Copilot {role.value.title()}"
            )
        elif provider == 'gemini':
            return GeminiPerformer(...)
        else:
            raise ValueError(f"Unknown API provider: {provider}")
```

---

## 4. Migration Strategy

### 4.1 Parallel Operation

During migration, both systems run in parallel:

```python
# main.py

def generate_music(prompt: str, **kwargs):
    """Main entry point - routes to appropriate implementation."""
    
    use_agents = kwargs.pop('use_agents', False)
    
    if use_agents:
        return generate_music_agentic(prompt, **kwargs)
    else:
        return generate_music_legacy(prompt, **kwargs)  # Current system
```

### 4.2 Feature Flags

```python
# multimodal_gen/config.py

class FeatureFlags:
    # Agent system
    USE_AGENT_ARCHITECTURE = False  # Toggle entire system
    USE_API_AGENTS = False          # Stage 2 only
    
    # Per-role flags (gradual migration)
    USE_DRUMMER_AGENT = False
    USE_BASSIST_AGENT = False
    USE_KEYIST_AGENT = False
    
    # Debugging
    LOG_AGENT_DECISIONS = True
    COMPARE_AGENT_VS_LEGACY = False  # Generate both, compare
```

### 4.3 Testing Strategy

| Test Type | Purpose | Coverage |
|-----------|---------|----------|
| Unit | Test individual agents | 100% of agents |
| Integration | Test conductor + ensemble | Full workflow |
| Comparison | Agent output vs legacy | Quality parity |
| Performance | Latency, memory | < 2x legacy |

---

## 5. Success Criteria

### 5.1 Stage 1 Complete When:

- [ ] All performer agents implemented (drums, bass, keys, lead, pad)
- [ ] OfflineConductor coordinates full song generation
- [ ] Personality system affects output audibly
- [ ] Feature parity with legacy system
- [ ] All existing tests pass
- [ ] New agent tests achieve 80%+ coverage
- [ ] Documentation complete

### 5.2 Stage 2 Ready When:

- [ ] API agent interfaces defined and tested (with mocks)
- [ ] Factory supports hot-swapping offline ↔ API
- [ ] Prompt engineering documented for each role
- [ ] Rate limiting and error handling in place
- [ ] Cost estimation available

---

## 6. Appendix

### A. File Change Summary

| File | Action | Complexity |
|------|--------|------------|
| `agents/__init__.py` | CREATE | Low |
| `agents/base.py` | CREATE | Medium |
| `agents/context.py` | CREATE | Medium |
| `agents/personality.py` | CREATE | Medium |
| `agents/conductor.py` | CREATE | Medium |
| `agents/conductor_offline.py` | CREATE | High |
| `agents/factory.py` | CREATE | Medium |
| `agents/performers/drummer.py` | CREATE | Medium |
| `agents/performers/bassist.py` | CREATE | Medium |
| `agents/performers/keyist.py` | CREATE | Medium |
| `agents/performers/melodist.py` | CREATE | Medium |
| `agents/strategies/strategy_adapter.py` | CREATE | Low |
| `main.py` | MODIFY | Low |
| `midi_generator.py` | MINOR MODIFY | Low |

### B. Dependency Graph

```
agents/base.py
    └── agents/context.py
    └── agents/personality.py
        └── agents/performers/*.py
            └── strategies/strategy_adapter.py
        └── agents/conductor.py
            └── agents/conductor_offline.py
                └── agents/factory.py
                    └── main.py integration
```

### C. Glossary

| Term | Definition |
|------|------------|
| **Performer Agent** | Autonomous unit that generates notes for one musical role |
| **Conductor Agent** | Orchestrator that coordinates all performers |
| **Performance Context** | Shared state all agents react to |
| **Personality** | Configuration that makes agent output unique |
| **Score** | The arrangement + cues the conductor creates |
| **Ensemble** | Collection of performer agents for a piece |

---

**Document Status**: READY FOR IMPLEMENTATION  
**Next Action**: Create `agents/` package with core interfaces  
**Owner**: Builder Agent  
**Estimated LOC**: ~2,500 new lines
