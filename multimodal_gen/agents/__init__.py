"""
Agents Package - Agent-based Performer Architecture

This package implements the agents-as-performers architecture for music generation,
where each musical role (drums, bass, keys, etc.) is handled by an autonomous agent
with its own personality, style, and decision-making capability.

Architecture Overview:
    - Conductor Agent: Orchestrates all performer agents, interprets prompts
    - Performer Agents: Generate notes for specific musical roles
    - Performance Context: Shared state all agents react to
    - Personality System: Makes each agent instance unique

Stage 1: Offline (rule-based) implementations
Stage 2: API-backed implementations (Copilot/Gemini)

Available Performers:
    Standard:
        - DrummerAgent: Kit drums with fills and grooves
        - BassistAgent: 808/synth bass with groove locking
        - KeyboardistAgent: Chords and harmonic accompaniment
    
    Ethiopian:
        - KeberoAgent: Double-headed drum with eskista rhythms
        - KrarAgent: 5-string lyre with arpeggios and drones
        - MasenqoAgent: Bowed fiddle with qenet modes
        - WashintAgent: Bamboo flute with breath phrasing
        - BegenaAgent: Bass lyre with meditative drones

Usage:
    ```python
    from multimodal_gen.agents import OfflineConductor
    
    conductor = OfflineConductor()
    tracks = conductor.generate("ethiopian eskista with kebero and krar")
    ```
"""

from .base import (
    AgentRole,
    IPerformerAgent,
    PerformanceResult,
)

from .context import (
    PerformanceContext,
    PerformanceScore,
)

from .personality import (
    AgentPersonality,
    DRUMMER_PRESETS,
    BASSIST_PRESETS,
    KEYIST_PRESETS,
    GENRE_PERSONALITY_MAP,
    get_personality_for_role,
)

from .conductor import (
    IConductorAgent,
)

from .conductor_offline import (
    OfflineConductor,
)

from .registry import (
    AgentRegistry,
)

# Import performer agents for convenience
from .performers import (
    DrummerAgent,
    BassistAgent,
    KeyboardistAgent,
    MasenqoAgent,
    WashintAgent,
    KrarAgent,
    BegenaAgent,
    KeberoAgent,
    MASENQO_PRESETS,
    WASHINT_PRESETS,
    KRAR_PRESETS,
    BEGENA_PRESETS,
    KEBERO_PRESETS,
)

__all__ = [
    # Base classes
    "AgentRole",
    "IPerformerAgent",
    "PerformanceResult",
    # Context
    "PerformanceContext",
    "PerformanceScore",
    # Personality
    "AgentPersonality",
    "DRUMMER_PRESETS",
    "BASSIST_PRESETS",
    "KEYIST_PRESETS",
    "GENRE_PERSONALITY_MAP",
    "get_personality_for_role",
    # Conductors
    "IConductorAgent",
    "OfflineConductor",
    # Registry
    "AgentRegistry",
    # Standard Performers
    "DrummerAgent",
    "BassistAgent",
    "KeyboardistAgent",
    # Ethiopian Performers
    "MasenqoAgent",
    "WashintAgent",
    "KrarAgent",
    "BegenaAgent",
    "KeberoAgent",
    # Ethiopian Presets
    "MASENQO_PRESETS",
    "WASHINT_PRESETS",
    "KRAR_PRESETS",
    "BEGENA_PRESETS",
    "KEBERO_PRESETS",
]
