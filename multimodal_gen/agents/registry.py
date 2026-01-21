"""
Agent Registry - Dynamic Agent Spawning

This module provides the AgentRegistry class for dynamically spawning
performer agents based on instrument names. The registry allows the
Conductor to request any instrument and get an appropriate agent.

Key Features:
- Core agents: drums, bass, keys, lead, pad
- Orchestral agents: strings, brass, woodwinds
- World/ethnic agents: Ethiopian instruments, sitar, tabla, etc.
- Section agents: Coordinate multiple sub-performers (string section, etc.)

Design Philosophy:
    The registry decouples instrument requests from agent implementations.
    This allows adding new instrument support without changing the Conductor
    or other parts of the system.
"""

from typing import Dict, List, Type, Optional, TYPE_CHECKING

from .base import AgentRole, IPerformerAgent

if TYPE_CHECKING:
    from .personality import AgentPersonality


class AgentRegistry:
    """
    Registry of instrument -> agent type mappings.
    
    Allows the Conductor to spawn appropriate agents for any
    instrument requested in the prompt. Supports:
    - Core instruments (drums, bass, keys, etc.)
    - Orchestral instruments (strings, brass, woodwinds)
    - World/ethnic instruments (Ethiopian, Indian, Japanese)
    - Section agents (coordinate multiple performers)
    
    Usage:
        ```python
        # Get agent class for an instrument
        agent_class = AgentRegistry.get_agent_class("masenqo")
        
        # Spawn a configured agent
        agent = AgentRegistry.spawn_agent("masenqo", "ethiopian")
        
        # Spawn a section (multiple coordinated agents)
        strings = AgentRegistry.spawn_section("strings", 4, "orchestral")
        ```
    
    Note:
        The registry returns role types and agent configurations.
        Actual agent implementations are in the performers/ subpackage.
        Until those are implemented, spawn_agent returns placeholder
        configs that can be used with the existing MidiGenerator.
    """
    
    # =========================================================================
    # AGENT TYPE MAPPINGS
    # =========================================================================
    
    # Core role mappings (always available)
    CORE_AGENTS: Dict[str, AgentRole] = {
        "drums": AgentRole.DRUMS,
        "drum_kit": AgentRole.DRUMS,
        "percussion": AgentRole.PERCUSSION,
        "bass": AgentRole.BASS,
        "808": AgentRole.BASS,
        "synth_bass": AgentRole.BASS,
        "piano": AgentRole.KEYS,
        "keys": AgentRole.KEYS,
        "keyboard": AgentRole.KEYS,
        "rhodes": AgentRole.KEYS,
        "organ": AgentRole.KEYS,
        "synth": AgentRole.KEYS,
        "synth_lead": AgentRole.LEAD,
        "lead": AgentRole.LEAD,
        "guitar_lead": AgentRole.LEAD,
        "pad": AgentRole.PAD,
        "ambient": AgentRole.PAD,
        "texture": AgentRole.PAD,
        "fx": AgentRole.FX,
        "effects": AgentRole.FX,
    }
    
    # Orchestral instruments
    ORCHESTRAL_AGENTS: Dict[str, AgentRole] = {
        # Strings
        "violin": AgentRole.STRINGS,
        "viola": AgentRole.STRINGS,
        "cello": AgentRole.STRINGS,
        "contrabass": AgentRole.STRINGS,
        "double_bass": AgentRole.STRINGS,
        "strings": AgentRole.SECTION,  # Section agent for full string section
        "string_section": AgentRole.SECTION,
        
        # Woodwinds
        "flute": AgentRole.LEAD,
        "clarinet": AgentRole.LEAD,
        "oboe": AgentRole.LEAD,
        "bassoon": AgentRole.BASS,
        "woodwinds": AgentRole.SECTION,
        
        # Brass
        "trumpet": AgentRole.BRASS,
        "trombone": AgentRole.BRASS,
        "french_horn": AgentRole.BRASS,
        "horn": AgentRole.BRASS,
        "tuba": AgentRole.BRASS,
        "brass": AgentRole.SECTION,  # Section agent for brass section
        "brass_section": AgentRole.SECTION,
    }
    
    # World/Ethnic instruments
    WORLD_AGENTS: Dict[str, AgentRole] = {
        # Ethiopian instruments
        "masenqo": AgentRole.STRINGS,      # Single-string bowed fiddle
        "krar": AgentRole.KEYS,            # 6-string lyre (chordal)
        "begena": AgentRole.KEYS,          # Large 10-string lyre
        "washint": AgentRole.LEAD,         # Bamboo flute (melodic)
        "kebero": AgentRole.DRUMS,         # Double-headed drum
        "atamo": AgentRole.PERCUSSION,     # Small hand drum
        
        # Indian instruments
        "sitar": AgentRole.LEAD,
        "tabla": AgentRole.DRUMS,
        "tanpura": AgentRole.PAD,
        "sarangi": AgentRole.STRINGS,
        "bansuri": AgentRole.LEAD,         # Bamboo flute
        
        # Japanese instruments
        "koto": AgentRole.KEYS,
        "shamisen": AgentRole.STRINGS,
        "shakuhachi": AgentRole.LEAD,      # Bamboo flute
        "taiko": AgentRole.DRUMS,
        
        # African instruments (non-Ethiopian)
        "djembe": AgentRole.DRUMS,
        "talking_drum": AgentRole.DRUMS,
        "balafon": AgentRole.KEYS,
        "kora": AgentRole.KEYS,
        "mbira": AgentRole.KEYS,
        
        # Latin/Caribbean
        "congas": AgentRole.PERCUSSION,
        "bongos": AgentRole.PERCUSSION,
        "timbales": AgentRole.PERCUSSION,
        "steel_drum": AgentRole.KEYS,
        
        # Middle Eastern
        "oud": AgentRole.KEYS,
        "qanun": AgentRole.KEYS,
        "ney": AgentRole.LEAD,
        "darbuka": AgentRole.PERCUSSION,
    }
    
    # Section configurations for spawning multiple performers
    SECTION_CONFIGS: Dict[str, Dict] = {
        "strings": {
            "instruments": ["violin", "violin", "viola", "cello"],
            "roles": [AgentRole.STRINGS] * 4,
            "voice_names": ["Violin I", "Violin II", "Viola", "Cello"],
        },
        "string_quartet": {
            "instruments": ["violin", "violin", "viola", "cello"],
            "roles": [AgentRole.STRINGS] * 4,
            "voice_names": ["Violin I", "Violin II", "Viola", "Cello"],
        },
        "string_orchestra": {
            "instruments": ["violin", "violin", "violin", "violin", "viola", "viola", "cello", "cello", "contrabass"],
            "roles": [AgentRole.STRINGS] * 9,
            "voice_names": ["Violin I-1", "Violin I-2", "Violin II-1", "Violin II-2", 
                          "Viola I", "Viola II", "Cello I", "Cello II", "Bass"],
        },
        "brass": {
            "instruments": ["trumpet", "trumpet", "horn", "trombone"],
            "roles": [AgentRole.BRASS] * 4,
            "voice_names": ["Trumpet I", "Trumpet II", "Horn", "Trombone"],
        },
        "brass_quintet": {
            "instruments": ["trumpet", "trumpet", "horn", "trombone", "tuba"],
            "roles": [AgentRole.BRASS] * 5,
            "voice_names": ["Trumpet I", "Trumpet II", "Horn", "Trombone", "Tuba"],
        },
        "woodwinds": {
            "instruments": ["flute", "oboe", "clarinet", "bassoon"],
            "roles": [AgentRole.LEAD, AgentRole.LEAD, AgentRole.LEAD, AgentRole.BASS],
            "voice_names": ["Flute", "Oboe", "Clarinet", "Bassoon"],
        },
        "choir": {
            "instruments": ["voice", "voice", "voice", "voice"],
            "roles": [AgentRole.LEAD] * 4,
            "voice_names": ["Soprano", "Alto", "Tenor", "Bass"],
        },
        "ethiopian_ensemble": {
            "instruments": ["kebero", "krar", "masenqo", "washint"],
            "roles": [AgentRole.DRUMS, AgentRole.KEYS, AgentRole.STRINGS, AgentRole.LEAD],
            "voice_names": ["Kebero", "Krar", "Masenqo", "Washint"],
        },
    }
    
    # =========================================================================
    # CLASS METHODS
    # =========================================================================
    
    @classmethod
    def get_agent_role(cls, instrument: str) -> AgentRole:
        """
        Get the AgentRole for an instrument.
        
        Args:
            instrument: Instrument name (case-insensitive, spaces become underscores)
            
        Returns:
            AgentRole enum value for the instrument
        """
        instrument = instrument.lower().strip().replace(" ", "_")
        
        # Check all registries in order
        for registry in [cls.CORE_AGENTS, cls.ORCHESTRAL_AGENTS, cls.WORLD_AGENTS]:
            if instrument in registry:
                return registry[instrument]
        
        # Fallback to generic melodic role
        return AgentRole.LEAD
    
    @classmethod
    def get_all_instruments(cls) -> List[str]:
        """
        Get list of all registered instruments.
        
        Returns:
            List of instrument name strings
        """
        all_instruments = []
        for registry in [cls.CORE_AGENTS, cls.ORCHESTRAL_AGENTS, cls.WORLD_AGENTS]:
            all_instruments.extend(registry.keys())
        return sorted(set(all_instruments))
    
    @classmethod
    def get_instruments_for_role(cls, role: AgentRole) -> List[str]:
        """
        Get all instruments that map to a given role.
        
        Args:
            role: AgentRole to filter by
            
        Returns:
            List of instrument names for that role
        """
        instruments = []
        for registry in [cls.CORE_AGENTS, cls.ORCHESTRAL_AGENTS, cls.WORLD_AGENTS]:
            for instrument, inst_role in registry.items():
                if inst_role == role:
                    instruments.append(instrument)
        return sorted(set(instruments))
    
    @classmethod
    def spawn_agent(
        cls,
        instrument: str,
        genre: str = "default",
        personality: Optional['AgentPersonality'] = None
    ) -> Dict:
        """
        Create an agent configuration for the given instrument.
        
        This returns a configuration dictionary that can be used to
        instantiate an agent. Full agent implementations are in the
        performers/ subpackage.
        
        Args:
            instrument: Instrument name
            genre: Genre for personality selection
            personality: Optional personality override
            
        Returns:
            Dictionary with agent configuration:
            {
                "instrument": str,
                "role": AgentRole,
                "genre": str,
                "personality": AgentPersonality or None,
                "name": str  # Human-readable name
            }
        """
        from .personality import get_personality_for_role
        
        instrument = instrument.lower().strip().replace(" ", "_")
        role = cls.get_agent_role(instrument)
        
        # Get personality if not provided
        if personality is None:
            personality = get_personality_for_role(genre, role)
        
        # Create readable name
        instrument_display = instrument.replace("_", " ").title()
        genre_display = genre.replace("_", " ").title()
        name = f"{genre_display} {instrument_display}"
        
        return {
            "instrument": instrument,
            "role": role,
            "genre": genre,
            "personality": personality,
            "name": name,
        }
    
    @classmethod
    def spawn_section(
        cls,
        section_type: str,
        size: Optional[int] = None,
        genre: str = "default"
    ) -> List[Dict]:
        """
        Spawn a section of performers (e.g., string quartet, brass quintet).
        
        Args:
            section_type: Type of section ("strings", "brass", "choir", etc.)
            size: Optional size override (uses default if not specified)
            genre: Genre for personality selection
            
        Returns:
            List of agent configuration dictionaries
            
        Example:
            ```python
            # Spawn a string quartet
            configs = AgentRegistry.spawn_section("strings", 4, "classical")
            # Returns 4 configs: Violin I, Violin II, Viola, Cello
            ```
        """
        section_type = section_type.lower().strip().replace(" ", "_")
        
        # Get section configuration
        if section_type not in cls.SECTION_CONFIGS:
            # Unknown section type - spawn generic agents
            size = size or 4
            return [cls.spawn_agent(section_type, genre) for _ in range(size)]
        
        config = cls.SECTION_CONFIGS[section_type]
        instruments = config["instruments"]
        roles = config["roles"]
        names = config["voice_names"]
        
        # Optionally limit size
        if size is not None and size < len(instruments):
            instruments = instruments[:size]
            roles = roles[:size]
            names = names[:size]
        
        # Spawn agents for each voice
        agents = []
        for i, (inst, role, voice_name) in enumerate(zip(instruments, roles, names)):
            from .personality import get_personality_for_role
            
            personality = get_personality_for_role(genre, role)
            
            agents.append({
                "instrument": inst,
                "role": role,
                "genre": genre,
                "personality": personality,
                "name": voice_name,
                "voice_index": i,
                "section": section_type,
            })
        
        return agents
    
    @classmethod
    def is_section_type(cls, instrument: str) -> bool:
        """
        Check if an instrument name refers to a section type.
        
        Args:
            instrument: Instrument name to check
            
        Returns:
            True if this is a section type (spawns multiple performers)
        """
        instrument = instrument.lower().strip().replace(" ", "_")
        
        # Check if it's in section configs
        if instrument in cls.SECTION_CONFIGS:
            return True
        
        # Check if it maps to SECTION role
        role = cls.get_agent_role(instrument)
        return role == AgentRole.SECTION
    
    @classmethod
    def get_section_size(cls, section_type: str) -> int:
        """
        Get the default size for a section type.
        
        Args:
            section_type: Type of section
            
        Returns:
            Number of performers in the section
        """
        section_type = section_type.lower().strip().replace(" ", "_")
        
        if section_type in cls.SECTION_CONFIGS:
            return len(cls.SECTION_CONFIGS[section_type]["instruments"])
        
        return 4  # Default section size
