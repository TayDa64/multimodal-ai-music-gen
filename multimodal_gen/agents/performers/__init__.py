"""
Performer Agents Package

This package contains concrete implementations of IPerformerAgent
for different musical roles. Each performer is a domain expert
in their instrument with genre-aware pattern generation.

Available Performers:
    - DrummerAgent: Masterclass drummer with kit knowledge and fill theory
    - BassistAgent: 808/bass specialist with groove locking and slide techniques
    - KeyboardistAgent: Chord voicings, voice leading, and harmonic accompaniment
    - MasenqoAgent: Ethiopian bowed fiddle with qenet modes and azmari phrases
    - WashintAgent: Ethiopian bamboo flute with breath phrasing and ornaments
    - KrarAgent: Ethiopian lyre with arpeggios and drone accompaniment
    - BegenaAgent: Ethiopian bass lyre with meditative drone patterns
    - KeberoAgent: Ethiopian drum with eskista and traditional rhythms

Future Performers:
    - LeadAgent: Melodic lead lines and runs
    - StringsAgent: Orchestral string arrangements

Usage:
    from multimodal_gen.agents.performers import (
        DrummerAgent, BassistAgent, KeyboardistAgent,
        MasenqoAgent, WashintAgent, KrarAgent, BegenaAgent, KeberoAgent
    )
    
    drummer = DrummerAgent()
    bassist = BassistAgent()
    keyboardist = KeyboardistAgent()
    masenqo = MasenqoAgent()
    washint = WashintAgent()
    krar = KrarAgent()
    begena = BegenaAgent()
    kebero = KeberoAgent()
    
    # Each agent can perform with context, section, and personality
    result = krar.perform(context, section, personality)
"""

from .drummer import DrummerAgent
from .bassist import BassistAgent
from .keyboardist import KeyboardistAgent
from .masenqo import MasenqoAgent, MASENQO_PRESETS
from .washint import WashintAgent, WASHINT_PRESETS
from .krar import KrarAgent, KRAR_PRESETS
from .begena import BegenaAgent, BEGENA_PRESETS
from .kebero import KeberoAgent, KEBERO_PRESETS

# Re-export personality presets from parent module for convenience
from ..personality import (
    DRUMMER_PRESETS,
    BASSIST_PRESETS,
    KEYIST_PRESETS,
)

__all__ = [
    # Standard Agents
    "DrummerAgent",
    "BassistAgent",
    "KeyboardistAgent",
    # Ethiopian Agents
    "MasenqoAgent",
    "WashintAgent",
    "KrarAgent",
    "BegenaAgent",
    "KeberoAgent",
    # Standard Presets
    "DRUMMER_PRESETS",
    "BASSIST_PRESETS",
    "KEYIST_PRESETS",
    # Ethiopian Presets
    "MASENQO_PRESETS",
    "WASHINT_PRESETS",
    "KRAR_PRESETS",
    "BEGENA_PRESETS",
    "KEBERO_PRESETS",
]
