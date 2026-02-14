"""
Instrument Resolution Service

Bridges expansion instruments to the generation pipeline by providing:
1. Dynamic program↔instrument registry
2. Intelligent resolution with 5-tier fallback (EXACT, MAPPED, SEMANTIC, SPECTRAL, DEFAULT)
3. Genre-aware instrument selection
4. Auto-allocation of MIDI programs for expansion instruments

This service acts as a unified interface between:
- ExpansionManager (which has sophisticated instrument resolution)
- MidiGenerator (which generates MIDI with program changes)
- AudioRenderer (which maps programs to synthesis methods)
- assets_gen / prompt_parser (which define genre-instrument mappings)

Usage:
    from multimodal_gen.expansion_manager import ExpansionManager
    from multimodal_gen.instrument_resolution import InstrumentResolutionService
    
    expansion_manager = ExpansionManager()
    expansion_manager.scan_expansions("./expansions")
    
    service = InstrumentResolutionService(expansion_manager)
    
    # Resolve an instrument for a genre
    resolved = service.resolve_instrument("krar", genre="eskista")
    print(resolved.name, resolved.program, resolved.match_type)
    
    # Get instruments for a genre
    instruments = service.get_instruments_for_genre("trap")
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, TYPE_CHECKING
from enum import Enum
import threading

if TYPE_CHECKING:
    from .expansion_manager import ExpansionManager, ResolvedInstrument as ExpansionResolved


class MatchType(Enum):
    """How an instrument was resolved."""
    EXACT = "exact"           # Direct name match
    MAPPED = "mapped"         # Genre-specific mapping
    SEMANTIC = "semantic"     # Role-based matching
    SPECTRAL = "spectral"     # Sonic similarity
    DEFAULT = "default"       # Fallback to hardcoded


@dataclass
class ResolvedInstrument:
    """
    Result of instrument resolution with all metadata needed for MIDI/audio.
    
    This is the primary data structure returned by the resolution service.
    It contains everything needed to:
    1. Generate correct MIDI program changes
    2. Route to correct audio synthesis/samples
    3. Provide debug info about resolution path
    """
    name: str                           # Resolved instrument name
    program: int                        # MIDI program number (0-127, or 110+ for expansions)
    sample_paths: List[str] = field(default_factory=list)  # Audio file paths if available
    match_type: str = "default"         # How it was resolved (exact, mapped, semantic, spectral, default)
    confidence: float = 0.5             # Resolution confidence (0-1)
    
    # Additional metadata
    source: str = ""                    # Source expansion or "builtin"
    original_request: str = ""          # What was originally requested
    genre: str = ""                     # Genre context used in resolution
    note: str = ""                      # Human-readable explanation
    
    def __repr__(self) -> str:
        return f"ResolvedInstrument({self.name}, program={self.program}, match={self.match_type})"


# =============================================================================
# HARDCODED FALLBACK MAPPINGS (Used when no service available)
# =============================================================================

# Default instruments per genre (fallback when ExpansionManager not available)
DEFAULT_GENRE_INSTRUMENTS: Dict[str, List[str]] = {
    'trap': ['808', 'synth_lead'],
    'trap_soul': ['808', 'piano', 'rhodes', 'strings'],
    'rnb': ['piano', 'rhodes', 'bass', 'strings', 'pad'],
    'g_funk': ['synth', 'bass', 'piano', 'pad', 'brass'],
    'lofi': ['piano', 'rhodes', 'guitar'],
    'boom_bap': ['piano', 'bass', 'brass'],
    'house': ['bass', 'synth', 'pad'],
    'ambient': ['pad', 'strings', 'piano'],
    # Cinematic / Classical genres
    'cinematic': ['strings', 'brass', 'timpani', 'harp', 'choir', 'contrabass', 'french_horn'],
    'classical': ['strings', 'piano', 'oboe', 'clarinet', 'flute', 'contrabass', 'french_horn'],
    # Ethiopian genres
    'ethiopian': ['krar', 'masenqo', 'brass', 'piano'],
    'ethio_jazz': ['brass', 'piano', 'bass', 'organ'],
    'ethiopian_traditional': ['krar', 'masenqo', 'washint', 'begena'],
    'eskista': ['brass', 'krar', 'masenqo'],
}

# Standard GM MIDI program mapping (fallback)
DEFAULT_INSTRUMENT_TO_PROGRAM: Dict[str, int] = {
    # Pianos (0-7)
    'piano': 0,
    'acoustic_grand': 0,
    'electric_piano': 4,
    'rhodes': 4,
    'honky_tonk': 3,
    
    # Chromatic Percussion (8-15)
    'vibraphone': 11,
    'marimba': 12,
    'xylophone': 13,
    
    # Organ (16-23)
    'organ': 16,
    'drawbar_organ': 16,
    'church_organ': 19,
    
    # Guitar (24-31)
    'guitar': 25,
    'acoustic_guitar': 25,
    'electric_guitar': 27,
    'distortion_guitar': 30,
    
    # Bass (32-39)
    'bass': 33,
    'electric_bass': 33,
    'synth_bass': 38,
    '808': 38,  # 808 bass uses synth bass
    
    # Strings (40-47)
    'strings': 48,
    'string_ensemble': 48,
    'violin': 40,
    'viola': 41,
    'cello': 42,
    
    # Strings solo (40-47) — orchestral additions
    'harp': 46,
    'orchestral_harp': 46,
    'timpani': 47,
    'contrabass': 43,
    'double_bass': 43,
    
    # Ensemble (48-55)
    'choir': 52,
    'voice': 54,
    
    # Brass (56-63)
    'brass': 61,
    'trumpet': 56,
    'trombone': 57,
    'french_horn': 60,
    'tuba': 58,
    'brass_section': 61,
    
    # Reed (64-71)
    'sax': 65,
    'alto_sax': 65,
    'tenor_sax': 66,
    'oboe': 68,
    'bassoon': 70,
    'clarinet': 71,
    
    # Pipe (72-79)
    'flute': 73,
    'piccolo': 72,
    'recorder': 74,
    'pan_flute': 75,
    
    # Synth Lead (80-87)
    'synth': 81,
    'synth_lead': 81,
    'lead': 81,
    'square_lead': 80,
    'sawtooth_lead': 81,
    
    # Synth Pad (88-95)
    'pad': 89,
    'synth_pad': 89,
    'warm_pad': 89,
    'polysynth': 90,
    
    # Synth Effects (96-103)
    'fx': 99,
    'atmosphere': 99,
    
    # Ethnic (104-111) - GM standard
    'sitar': 104,
    'banjo': 105,
    'shamisen': 106,
    'koto': 107,
    'kalimba': 108,
    'bagpipe': 109,
    'fiddle': 110,
    'shanai': 111,
    
    # Ethiopian instruments (custom range starting at 110)
    # These override the GM ethnic instruments for Ethiopian genres
    'krar': 110,
    'masenqo': 111,
    'washint': 112,
    'begena': 113,
    'kebero': 114,
    'atamo': 115,
}

# Reverse mapping (program -> instrument name)
DEFAULT_PROGRAM_TO_INSTRUMENT: Dict[int, str] = {
    v: k for k, v in DEFAULT_INSTRUMENT_TO_PROGRAM.items()
}


# =============================================================================
# INSTRUMENT RESOLUTION SERVICE
# =============================================================================

class InstrumentResolutionService:
    """
    Unified service for resolving instruments across expansions and built-ins.
    
    This service bridges the gap between:
    - ExpansionManager's sophisticated 5-tier resolution
    - MidiGenerator's hardcoded program mappings
    - AudioRenderer's program-to-synthesis routing
    
    Key features:
    1. Auto-allocates MIDI programs for expansion instruments (starting at 110)
    2. Maintains bidirectional program↔instrument registry
    3. Provides genre-aware instrument lists
    4. Falls back gracefully when expansions unavailable
    
    Thread-safe: Uses locks for registry modifications.
    """
    
    # Program range for expansion instruments
    EXPANSION_PROGRAM_START = 110
    EXPANSION_PROGRAM_END = 127
    
    def __init__(
        self,
        expansion_manager: Optional['ExpansionManager'] = None,
        auto_register_expansions: bool = True
    ):
        """
        Initialize the InstrumentResolutionService.
        
        Args:
            expansion_manager: Optional ExpansionManager with loaded expansions
            auto_register_expansions: If True, auto-register expansion instruments
        """
        self._expansion_manager = expansion_manager
        self._lock = threading.Lock()
        
        # Dynamic registries (program ↔ instrument)
        self._program_to_instrument: Dict[int, str] = dict(DEFAULT_PROGRAM_TO_INSTRUMENT)
        self._instrument_to_program: Dict[str, int] = dict(DEFAULT_INSTRUMENT_TO_PROGRAM)
        
        # Track allocated expansion programs
        self._next_expansion_program = self.EXPANSION_PROGRAM_START
        self._allocated_expansion_programs: Set[int] = set()
        
        # Cache for resolved instruments
        self._resolution_cache: Dict[str, ResolvedInstrument] = {}
        
        # Register expansion instruments if manager provided
        if expansion_manager and auto_register_expansions:
            self._register_expansion_instruments()
    
    def _register_expansion_instruments(self) -> int:
        """
        Register all expansion instruments with auto-allocated programs.
        
        Returns:
            Number of instruments registered
        """
        if not self._expansion_manager:
            return 0
        
        count = 0
        
        # Get all instruments from all expansions
        for expansion in self._expansion_manager.expansions.values():
            if not expansion.enabled:
                continue
            
            for inst in expansion.instruments.values():
                # Skip if already registered
                inst_name_lower = inst.name.lower()
                if inst_name_lower in self._instrument_to_program:
                    continue
                
                # Allocate program
                program = self._allocate_expansion_program()
                if program is None:
                    print(f"  [!] No more MIDI programs available for {inst.name}")
                    continue
                
                # Register bidirectionally
                with self._lock:
                    self._instrument_to_program[inst_name_lower] = program
                    self._instrument_to_program[inst.id] = program
                    self._program_to_instrument[program] = inst_name_lower
                
                count += 1
        
        if count > 0:
            print(f"  [+] InstrumentResolutionService: Registered {count} expansion instruments")
        
        return count
    
    def _allocate_expansion_program(self) -> Optional[int]:
        """
        Allocate next available MIDI program for an expansion instrument.
        
        Programs 110-127 are reserved for expansion instruments.
        Programs 110-115 are pre-allocated for Ethiopian instruments.
        
        Returns:
            Allocated program number, or None if exhausted
        """
        with self._lock:
            # Find next available program
            while self._next_expansion_program <= self.EXPANSION_PROGRAM_END:
                program = self._next_expansion_program
                self._next_expansion_program += 1
                
                if program not in self._allocated_expansion_programs:
                    self._allocated_expansion_programs.add(program)
                    return program
            
            return None
    
    def resolve_instrument(
        self,
        name: str,
        genre: str = "",
        prefer_expansion: str = None
    ) -> ResolvedInstrument:
        """
        Resolve an instrument request to a concrete instrument with program.
        
        Resolution order (5-tier):
        1. EXACT: Direct name match in expansions
        2. MAPPED: Genre-specific mapping
        3. SEMANTIC: Role-based matching
        4. SPECTRAL: Sonic similarity matching
        5. DEFAULT: Fall back to hardcoded mappings
        
        Args:
            name: Instrument name/type requested
            genre: Target genre for affinity scoring
            prefer_expansion: Prefer instruments from this expansion
        
        Returns:
            ResolvedInstrument with program and metadata
        """
        # Check cache first
        cache_key = f"{name.lower()}:{genre.lower()}"
        if cache_key in self._resolution_cache:
            return self._resolution_cache[cache_key]
        
        # Try ExpansionManager resolution first
        if self._expansion_manager:
            exp_result = self._expansion_manager.resolve_instrument(
                name, 
                genre=genre,
                prefer_expansion=prefer_expansion
            )
            
            if exp_result and exp_result.path:
                # Get or allocate program for this instrument
                program = self.get_program_for_instrument(exp_result.name)
                
                resolved = ResolvedInstrument(
                    name=exp_result.name,
                    program=program,
                    sample_paths=exp_result.sample_paths if exp_result.sample_paths else [exp_result.path],
                    match_type=exp_result.match_type.value if hasattr(exp_result.match_type, 'value') else str(exp_result.match_type),
                    confidence=exp_result.confidence,
                    source=exp_result.source,
                    original_request=name,
                    genre=genre,
                    note=exp_result.note,
                )
                
                # Cache the result
                self._resolution_cache[cache_key] = resolved
                return resolved
        
        # Fall back to hardcoded mappings
        return self._resolve_from_hardcoded(name, genre)
    
    def _resolve_from_hardcoded(self, name: str, genre: str) -> ResolvedInstrument:
        """
        Resolve instrument using hardcoded mappings.
        
        Used as fallback when ExpansionManager unavailable or no match found.
        """
        name_lower = name.lower().strip()
        
        # Direct lookup
        if name_lower in self._instrument_to_program:
            program = self._instrument_to_program[name_lower]
            return ResolvedInstrument(
                name=name_lower,
                program=program,
                match_type="default",
                confidence=0.8,
                source="builtin",
                original_request=name,
                genre=genre,
                note="Resolved from built-in mapping",
            )
        
        # Partial matching
        for inst_name, program in self._instrument_to_program.items():
            if name_lower in inst_name or inst_name in name_lower:
                return ResolvedInstrument(
                    name=inst_name,
                    program=program,
                    match_type="default",
                    confidence=0.6,
                    source="builtin",
                    original_request=name,
                    genre=genre,
                    note=f"Partial match: {inst_name}",
                )
        
        # Default to piano
        return ResolvedInstrument(
            name="piano",
            program=0,
            match_type="default",
            confidence=0.3,
            source="builtin",
            original_request=name,
            genre=genre,
            note=f"No match for '{name}', defaulting to piano",
        )
    
    def get_program_for_instrument(self, instrument_name: str) -> int:
        """
        Get MIDI program number for an instrument name.
        
        Args:
            instrument_name: Instrument name
            
        Returns:
            MIDI program number (0-127)
        """
        name_lower = instrument_name.lower().strip()
        
        # Direct lookup
        if name_lower in self._instrument_to_program:
            return self._instrument_to_program[name_lower]
        
        # Partial matching
        for inst_name, program in self._instrument_to_program.items():
            if name_lower in inst_name or inst_name in name_lower:
                return program
        
        # Allocate new program for unknown expansion instrument
        program = self._allocate_expansion_program()
        if program is not None:
            with self._lock:
                self._instrument_to_program[name_lower] = program
                self._program_to_instrument[program] = name_lower
            return program
        
        # Fallback to piano
        return 0
    
    def get_instrument_for_program(self, program: int) -> Optional[str]:
        """
        Get instrument name for a MIDI program number.
        
        Args:
            program: MIDI program number (0-127)
            
        Returns:
            Instrument name or None if unknown
        """
        return self._program_to_instrument.get(program)
    
    def get_instruments_for_genre(self, genre: str) -> List[str]:
        """
        Get list of recommended instruments for a genre.
        
        Uses ExpansionManager if available, otherwise falls back to defaults.
        
        Args:
            genre: Genre name
            
        Returns:
            List of instrument names
        """
        genre_lower = genre.lower().strip()
        
        # Try ExpansionManager first
        if self._expansion_manager:
            instruments = self._expansion_manager.list_instruments()
            
            # Filter by genre-relevant instruments
            genre_relevant = []
            for inst_info in instruments:
                # Check if instrument's expansion targets this genre
                for expansion in self._expansion_manager.expansions.values():
                    if expansion.id == inst_info.get('expansion', '').lower().replace(' ', '_'):
                        if genre_lower in [g.lower() for g in expansion.target_genres]:
                            genre_relevant.append(inst_info['name'])
                            break
            
            if genre_relevant:
                # Merge with defaults
                defaults = DEFAULT_GENRE_INSTRUMENTS.get(genre_lower, [])
                combined = list(dict.fromkeys(genre_relevant + defaults))  # Preserve order, remove dupes
                return combined
        
        # Fall back to hardcoded defaults
        return DEFAULT_GENRE_INSTRUMENTS.get(genre_lower, ['piano', 'bass'])
    
    def register_instrument(
        self,
        name: str,
        program: Optional[int] = None,
        override: bool = False
    ) -> int:
        """
        Register a custom instrument with a program number.
        
        Args:
            name: Instrument name
            program: MIDI program (auto-allocated if None)
            override: If True, override existing registration
            
        Returns:
            Assigned program number
        """
        name_lower = name.lower().strip()
        
        # Check if already registered
        if name_lower in self._instrument_to_program and not override:
            return self._instrument_to_program[name_lower]
        
        # Use provided program or allocate new one
        if program is None:
            program = self._allocate_expansion_program()
            if program is None:
                raise ValueError("No MIDI programs available")
        
        # Register bidirectionally
        with self._lock:
            self._instrument_to_program[name_lower] = program
            self._program_to_instrument[program] = name_lower
        
        return program
    
    def clear_cache(self):
        """Clear the resolution cache."""
        self._resolution_cache.clear()
    
    def get_registry_stats(self) -> Dict:
        """
        Get statistics about the instrument registry.
        
        Returns:
            Dict with registry statistics
        """
        return {
            'total_instruments': len(self._instrument_to_program),
            'total_programs': len(self._program_to_instrument),
            'expansion_programs_allocated': len(self._allocated_expansion_programs),
            'expansion_programs_available': self.EXPANSION_PROGRAM_END - self._next_expansion_program + 1,
            'cache_size': len(self._resolution_cache),
            'expansion_manager_loaded': self._expansion_manager is not None,
        }
    
    def list_registered_instruments(self) -> List[Dict]:
        """
        List all registered instruments with their programs.
        
        Returns:
            List of dicts with instrument info
        """
        return [
            {
                'name': name,
                'program': program,
                'is_expansion': program >= self.EXPANSION_PROGRAM_START,
            }
            for name, program in sorted(
                self._instrument_to_program.items(),
                key=lambda x: x[1]
            )
        ]


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def create_instrument_service(
    expansions_dir: str = None,
    auto_scan: bool = True
) -> InstrumentResolutionService:
    """
    Create and configure an InstrumentResolutionService.
    
    Args:
        expansions_dir: Path to expansions directory
        auto_scan: Automatically scan for expansions
        
    Returns:
        Configured InstrumentResolutionService
    """
    expansion_manager = None
    
    if expansions_dir or auto_scan:
        try:
            from .expansion_manager import create_expansion_manager
            expansion_manager = create_expansion_manager(
                project_root=None,
                auto_scan=auto_scan
            )
            
            if expansions_dir:
                expansion_manager.scan_expansions(expansions_dir)
                
        except ImportError:
            print("  [!] ExpansionManager not available, using built-in mappings only")
    
    return InstrumentResolutionService(
        expansion_manager=expansion_manager,
        auto_register_expansions=True
    )


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    'InstrumentResolutionService',
    'ResolvedInstrument',
    'MatchType',
    'DEFAULT_GENRE_INSTRUMENTS',
    'DEFAULT_INSTRUMENT_TO_PROGRAM',
    'DEFAULT_PROGRAM_TO_INSTRUMENT',
    'create_instrument_service',
]
