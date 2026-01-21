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

from .registry import (
    AgentRegistry,
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
    # Conductor
    "IConductorAgent",
    # Registry
    "AgentRegistry",
]
