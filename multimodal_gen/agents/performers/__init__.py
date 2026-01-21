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

Future Performers:
    - LeadAgent: Melodic lead lines and runs
    - StringsAgent: Orchestral string arrangements
    - KrarAgent: Ethiopian lyre

Usage:
    from multimodal_gen.agents.performers import (
        DrummerAgent, BassistAgent, KeyboardistAgent, MasenqoAgent, WashintAgent
    )
    
    drummer = DrummerAgent()
    bassist = BassistAgent()
    keyboardist = KeyboardistAgent()
    masenqo = MasenqoAgent()
    washint = WashintAgent()
    
    drum_result = drummer.perform(context, section, personality)
    bass_result = bassist.perform(context, section, personality)
    keys_result = keyboardist.perform(context, section, personality)
    masenqo_result = masenqo.perform(context, section, personality)
    washint_result = washint.perform(context, section, personality)
"""

from .drummer import DrummerAgent
from .bassist import BassistAgent
from .keyboardist import KeyboardistAgent
from .masenqo import MasenqoAgent, MASENQO_PRESETS
from .washint import WashintAgent, WASHINT_PRESETS

# Re-export personality presets from parent module for convenience
from ..personality import (
    DRUMMER_PRESETS,
    BASSIST_PRESETS,
    KEYIST_PRESETS,
)

__all__ = [
    # Agents
    "DrummerAgent",
    "BassistAgent",
    "KeyboardistAgent",
    "MasenqoAgent",
    "WashintAgent",
    # Presets
    "DRUMMER_PRESETS",
    "BASSIST_PRESETS",
    "KEYIST_PRESETS",
    "MASENQO_PRESETS",
    "WASHINT_PRESETS",
]
