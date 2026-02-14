"""
Prompt Parser Module

Extracts musical parameters from natural language prompts using
regex patterns and keyword dictionaries. No heavy ML dependencies.

Supported extractions:
- BPM (tempo)
- Key (root note + scale type)
- Genre/style
- Instruments and elements
- Texture keywords (vinyl, rain, etc.)
- Section hints (drop, breakdown, switch-up)

Enhanced with Genre Intelligence:
- Genre template validation (mandatory/forbidden elements)
- FX chain recommendations
- Spectral profile hints
- Humanization profile selection
"""

import re
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Tuple, Set, Any
from enum import Enum

from .utils import ScaleType, GENRE_DEFAULTS, DEFAULT_CONFIG

# Import genre intelligence for template-based validation
try:
    from .genre_intelligence import (
        get_genre_intelligence, 
        GenreIntelligence, 
        GenreTemplate,
        DrumConfig,
        SpectralProfile,
        HumanizationProfile
    )
    HAS_GENRE_INTELLIGENCE = True
except ImportError:
    HAS_GENRE_INTELLIGENCE = False
    GenreIntelligence = None
    GenreTemplate = None

# Optional instrument resolution service for expansion instrument support
try:
    from .instrument_resolution import InstrumentResolutionService, DEFAULT_GENRE_INSTRUMENTS
    HAS_INSTRUMENT_SERVICE = True
except ImportError:
    HAS_INSTRUMENT_SERVICE = False
    InstrumentResolutionService = None  # type: ignore
    DEFAULT_GENRE_INSTRUMENTS = {}  # type: ignore

# Module-level instrument service (can be set by orchestrator)
_instrument_service: 'InstrumentResolutionService' = None  # type: ignore


# ── Sprint 5: Preference-driven defaults ──

def _get_preferred_bpm():
    """Get BPM from user preferences if enough data exists."""
    try:
        from multimodal_gen.intelligence.preferences import PreferenceTracker
        tracker = PreferenceTracker()
        prefs = tracker.preferences
        if prefs.signal_count >= 5 and prefs.confidence >= 0.4:
            low, high = prefs.tempo_range
            return (low + high) / 2
    except Exception:
        pass
    return None


def _get_preferred_key():
    """Get key from user preferences if enough data exists."""
    try:
        from multimodal_gen.intelligence.preferences import PreferenceTracker
        tracker = PreferenceTracker()
        prefs = tracker.preferences
        if prefs.key_preferences and prefs.signal_count >= 5:
            return prefs.key_preferences[0]  # Most common key
    except Exception:
        pass
    return None


def set_instrument_service(service: 'InstrumentResolutionService') -> None:
    """
    Set the module-level InstrumentResolutionService.
    
    Called by the orchestrator to inject the service for use in
    prompt parsing and default instrument resolution.
    """
    global _instrument_service
    _instrument_service = service


def get_genre_instruments_via_service(genre: str) -> list:
    """
    Get instruments for a genre using InstrumentResolutionService if available.
    
    Falls back to DEFAULT_GENRE_INSTRUMENTS from instrument_resolution module,
    or a hardcoded minimal default.
    """
    if _instrument_service is not None:
        return _instrument_service.get_instruments_for_genre(genre)
    elif HAS_INSTRUMENT_SERVICE:
        return DEFAULT_GENRE_INSTRUMENTS.get(genre.lower(), ['piano', 'bass'])
    else:
        # Minimal hardcoded fallback
        return ['piano', 'bass']


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class ParsedPrompt:
    """
    Structured result from parsing a natural language music prompt.
    
    All fields have sensible defaults for when extraction fails.
    Enhanced with genre intelligence template data.
    """
    # Timing
    bpm: float = DEFAULT_CONFIG.default_bpm
    time_signature: Tuple[int, int] = (4, 4)
    
    # Key/Scale
    key: str = 'C'
    scale_type: ScaleType = ScaleType.MINOR
    
    # Genre & Style
    genre: str = 'trap_soul'
    style_modifiers: List[str] = field(default_factory=list)
    
    # Sonic Adjectives (for intelligent instrument selection)
    # These describe the desired sound character (warm, vintage, bright, etc.)
    sonic_adjectives: List[str] = field(default_factory=list)
    
    # Instrumentation
    instruments: List[str] = field(default_factory=list)
    drum_elements: List[str] = field(default_factory=list)
    
    # Negative/exclusion elements (from negative prompts)
    excluded_drums: List[str] = field(default_factory=list)
    excluded_instruments: List[str] = field(default_factory=list)
    
    # Textures & FX
    textures: List[str] = field(default_factory=list)
    
    # Arrangement hints
    section_hints: List[str] = field(default_factory=list)
    
    # Mood/Energy
    mood: str = 'neutral'
    energy: str = 'medium'
    
    # Processing flags
    use_sidechain: bool = False
    use_swing: bool = False
    swing_amount: float = 0.0

    # Preset system (explicit opt-in only; None means no preset requested)
    preset: Optional[str] = None
    style_preset: Optional[str] = None
    production_preset: Optional[str] = None

    # Optional tension arc overrides (used by Arranger)
    tension_arc_shape: Optional[str] = None
    tension_intensity: Optional[float] = None
    
    # Raw prompt for reference
    raw_prompt: str = ''
    negative_prompt: str = ''
    
    # Duration
    target_duration_seconds: Optional[float] = None  # None = auto (2-4 minutes based on genre)
    
    # === GENRE INTELLIGENCE ENHANCEMENTS ===
    
    # FX chain recommendations from genre template
    fx_chain_master: List[str] = field(default_factory=list)
    fx_chain_drums: List[str] = field(default_factory=list)
    fx_chain_bass: List[str] = field(default_factory=list)
    fx_chain_melodic: List[str] = field(default_factory=list)
    
    # Humanization settings from genre template
    velocity_variation: float = 0.12
    timing_humanization: float = 0.02
    humanization_profile: str = 'natural'
    
    # Drum pattern configuration
    hihat_density: str = '8th'
    use_hihat_rolls: bool = True
    use_half_time_snare: bool = False
    
    # Spectral profile hints
    sub_bass_presence: float = 0.5
    brightness: float = 0.5
    warmth: float = 0.5
    character_808: str = 'clean'
    
    # === REFERENCE ANALYSIS PARAMS ===
    # These are populated when a reference track is analyzed to influence generation
    # None means "use genre defaults", a value means "override from reference"
    reference_drum_density: Optional[float] = None  # 0.0-1.0, from DrumAnalysis.density
    reference_trap_hihats: Optional[bool] = None    # True = enable dense 16th/32nd hi-hats
    reference_has_808: Optional[bool] = None        # True = prefer 808-style bass/kick
    
    # Validation results
    validation_warnings: List[str] = field(default_factory=list)
    forbidden_elements_used: List[str] = field(default_factory=list)
    mandatory_elements_missing: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        """Apply defaults based on detected genre and filter exclusions."""
        if not self.instruments:
            self.instruments = self._get_genre_instruments()
        if not self.drum_elements:
            self.drum_elements = self._get_genre_drums()
        
        # Apply exclusions from negative prompt
        if self.excluded_drums:
            self.drum_elements = [d for d in self.drum_elements if d not in self.excluded_drums]
        if self.excluded_instruments:
            self.instruments = [i for i in self.instruments if i not in self.excluded_instruments]
        
        # Apply genre intelligence if available
        self._apply_genre_intelligence()
    
    def _get_genre_instruments(self) -> List[str]:
        """
        Get default instruments for detected genre.
        
        Uses InstrumentResolutionService if available (set via set_instrument_service),
        otherwise falls back to hardcoded genre mappings.
        """
        # Try using the service first (allows expansion instruments)
        if _instrument_service is not None:
            return _instrument_service.get_instruments_for_genre(self.genre)
        
        # Fallback to hardcoded mappings
        genre_instruments = {
            'trap': ['808', 'synth_lead'],
            'trap_soul': ['808', 'piano', 'rhodes', 'strings'],
            'rnb': ['piano', 'rhodes', 'bass', 'strings', 'pad'],
            'g_funk': ['synth', 'bass', 'piano', 'pad', 'brass'],  # G-Funk: synths, bass, keys
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
        return genre_instruments.get(self.genre, ['piano', 'bass'])
    
    def _get_genre_drums(self) -> List[str]:
        """Get default drum elements for detected genre."""
        genre_drums = {
            'trap': ['kick', '808', 'snare', 'clap', 'hihat', 'hihat_roll'],
            'trap_soul': ['kick', '808', 'snare', 'clap', 'hihat'],
            'rnb': ['kick', 'snare', 'hihat', 'rim'],  # Smoother, no hi-hat rolls
            'g_funk': ['kick', 'snare', 'hihat', 'clap'],  # G-Funk: clean, groovy drums
            'lofi': ['kick', 'snare', 'hihat'],
            'boom_bap': ['kick', 'snare', 'hihat', 'crash'],
            'house': ['kick', 'clap', 'hihat_open', 'hihat'],
            'ambient': ['kick', 'snare', 'cymbal'],
            # Cinematic / Classical genres - orchestral percussion
            'cinematic': ['timpani', 'crash', 'ride', 'triangle'],
            'classical': ['timpani', 'crash', 'triangle'],
            # Ethiopian genres - kebero-based patterns
            'ethiopian': ['kebero', 'kick', 'snare', 'shaker'],
            'ethio_jazz': ['kick', 'snare', 'hihat', 'ride', 'perc'],
            'ethiopian_traditional': ['kebero', 'atamo', 'clap'],
            'eskista': ['kebero', 'kick', 'snare', 'clap', 'shaker'],
        }
        return genre_drums.get(self.genre, ['kick', 'snare', 'hihat'])
    
    def _apply_genre_intelligence(self) -> None:
        """
        Apply genre intelligence template to enhance parsed prompt.
        
        This method loads the genre template and applies:
        - FX chain recommendations
        - Humanization settings
        - Drum configuration
        - Spectral profile hints
        - Validation against mandatory/forbidden elements
        """
        if not HAS_GENRE_INTELLIGENCE:
            return
        
        try:
            gi = get_genre_intelligence()
            template = gi.get_genre_template(self.genre)
            
            if template is None:
                return
            
            # Apply FX chains
            self.fx_chain_master = template.fx_chain.master
            self.fx_chain_drums = template.fx_chain.drums
            self.fx_chain_bass = template.fx_chain.bass
            self.fx_chain_melodic = template.fx_chain.melodic
            
            # Apply drum configuration
            self.hihat_density = template.drums.hihat_density
            self.use_hihat_rolls = template.drums.hihat_rolls
            self.use_half_time_snare = template.drums.half_time_snare
            
            # Apply humanization from template (unless already specified)
            if self.velocity_variation == 0.12:  # Default, not user-specified
                self.velocity_variation = template.drums.velocity_variation
            if self.timing_humanization == 0.02:  # Default
                self.timing_humanization = template.drums.timing_humanization
            
            # Get humanization profile name
            humanization = gi.get_humanization_for_genre(self.genre)
            if humanization:
                self.humanization_profile = humanization.name
            
            # Apply spectral profile
            self.sub_bass_presence = template.spectral_profile.sub_bass_presence
            self.brightness = template.spectral_profile.brightness
            self.warmth = template.spectral_profile.warmth
            self.character_808 = template.spectral_profile.character_808.value
            
            # Apply swing from template if not already set
            if not self.use_swing and template.tempo.swing_amount > 0:
                self.use_swing = True
                self.swing_amount = template.tempo.swing_amount
            
            # Validate prompt against genre rules
            validation = gi.validate_prompt_against_genre(
                self.genre,
                self.instruments,
                self.drum_elements
            )
            
            self.forbidden_elements_used = validation.get('forbidden_used', [])
            self.mandatory_elements_missing = validation.get('mandatory_missing', [])
            self.validation_warnings = validation.get('warnings', [])
            
            # Warn if forbidden elements are used
            if self.forbidden_elements_used:
                warning = f"Genre '{self.genre}' typically doesn't use: {', '.join(self.forbidden_elements_used)}"
                if warning not in self.validation_warnings:
                    self.validation_warnings.append(warning)
            
            # Remove hi-hat rolls if genre forbids them
            if not self.use_hihat_rolls and 'hihat_roll' in self.drum_elements:
                self.drum_elements = [d for d in self.drum_elements if d != 'hihat_roll']
            
        except Exception as e:
            # Don't fail parsing if genre intelligence has issues
            print(f"Warning: Genre intelligence error: {e}")
    
    def get_fx_chain(self, bus: str = 'master') -> List[str]:
        """Get FX chain for a specific bus."""
        chains = {
            'master': self.fx_chain_master,
            'drums': self.fx_chain_drums,
            'bass': self.fx_chain_bass,
            'melodic': self.fx_chain_melodic,
        }
        return chains.get(bus, [])
    
    def get_humanization_params(self) -> Dict[str, Any]:
        """Get humanization parameters as a dictionary."""
        return {
            'velocity_variation': self.velocity_variation,
            'timing_humanization': self.timing_humanization,
            'profile': self.humanization_profile,
        }
    
    def get_spectral_profile(self) -> Dict[str, Any]:
        """Get spectral profile as a dictionary."""
        return {
            'sub_bass_presence': self.sub_bass_presence,
            'brightness': self.brightness,
            'warmth': self.warmth,
            '808_character': self.character_808,
        }
    
    def has_validation_issues(self) -> bool:
        """Check if there are any validation issues."""
        return bool(self.forbidden_elements_used or self.mandatory_elements_missing)
    
    def get_validation_summary(self) -> str:
        """Get a human-readable validation summary."""
        issues = []
        
        if self.forbidden_elements_used:
            issues.append(f"Unusual for {self.genre}: {', '.join(self.forbidden_elements_used)}")
        
        if self.mandatory_elements_missing:
            issues.append(f"Consider adding: {', '.join(self.mandatory_elements_missing)}")
        
        if self.validation_warnings:
            issues.extend(self.validation_warnings)
        
        return "; ".join(issues) if issues else "Valid configuration"


# =============================================================================
# KEYWORD DICTIONARIES
# =============================================================================

# BPM extraction patterns
BPM_PATTERNS = [
    r'(\d{2,3})\s*(?:bpm|BPM)',           # "140 BPM", "87bpm"
    r'(?:at|@)\s*(\d{2,3})',               # "at 140", "@ 87"
    r'tempo\s*(?:of|:)?\s*(\d{2,3})',      # "tempo 140", "tempo: 87"
]

# Key extraction patterns
KEY_PATTERNS = [
    r'(?:in|key\s*(?:of)?)\s*([A-Ga-g][#b♯♭]?)\s*(major|minor|maj|min|m)?',
    r'([A-Ga-g][#b♯♭]?)\s*(major|minor|maj|min|m)\s*(?:key)?',
]

# Genre keywords mapped to genre type
GENRE_KEYWORDS: Dict[str, List[str]] = {
    'trap': [
        'trap', 'atlanta', 'drill', 'uk drill', 'phonk', 'rage',
        'hard trap', 'dark trap'
    ],
    'rnb': [
        'rnb', 'r&b', 'r and b', 'r n b', 'rhythm and blues', 'neo soul', 'neo-soul',
        'contemporary rnb', 'modern rnb', 'soul', 'soulful', 'usher',
        'the weeknd', 'frank ocean', 'daniel caesar', 'h.e.r', 'summer walker',
        'slow jam', 'slow jams', 'groove', 'groovy'
    ],
    'trap_soul': [
        'trap soul', 'trap-soul', 'trapsoul', 'rnb trap', 'r&b trap', 'soul trap',
        'emotional trap', 'melodic trap', 'bryson', 'sza', '6lack'
    ],
    'g_funk': [
        'g_funk', 'g-funk', 'g funk', 'gfunk', 'west coast', 'west-coast', 'westcoast', 'dr dre',
        'snoop', 'snoop dogg', 'warren g', 'nate dogg', 'death row',
        'california', 'la hip hop', 'gangsta funk', '213', 'doggystyle',
        'the chronic', 'regulate', 'long beach'
    ],
    'lofi': [
        'lofi', 'lo-fi', 'lo fi', 'chillhop', 'jazzhop', 'study',
        'chill beats', 'nujabes', 'lofi hip hop', 'lofi hiphop'
    ],
    'boom_bap': [
        'boom bap', 'boom-bap', 'boombap', '90s', 'golden era', 'old school',
        'classic hip hop', 'east coast', 'ny', 'pete rock', 'dilla'
    ],
    'house': [
        'house',
        'deep house', 'deep-house', 'deephouse',
        'tech house', 'tech-house', 'techhouse',
        'future house', 'future-house', 'futurehouse',
        'progressive house', 'progressive-house',
        'disco house', 'disco-house'
    ],
    'cinematic': [
        'cinematic', 'epic', 'orchestral', 'film score', 'film_score',
        'soundtrack', 'symphonic', 'filmic', 'movie score', 'epic orchestral',
        'sweeping', 'cinematic orchestral'
    ],
    'classical': [
        'classical', 'symphony', 'concerto', 'sonata', 'baroque',
        'romantic era', 'chamber music', 'philharmonic', 'overture',
        'opus', 'orchestral suite'
    ],
    'ambient': [
        'ambient', 'atmospheric', 'soundscape',
        'meditation', 'calm', 'peaceful', 'drone'
    ],
    # Ethiopian music genres
    'ethiopian': [
        'ethiopian', 'ethiopia', 'habesha', 'amharic', 'tigrinya',
        'oromo', 'gurage', 'wollo', 'gondar', 'gonder', 'addis',
        'azmari', 'tizita', 'bati', 'ambassel', 'anchihoye'
    ],
    'ethio_jazz': [
        'ethio jazz', 'ethio-jazz', 'ethiopian jazz', 'mulatu',
        'mulatu astatke', 'astatke', 'swinging addis', 'ethiopiques',
        'addis jazz', 'ethiopian funk'
    ],
    'ethiopian_traditional': [
        'traditional ethiopian', 'ethiopian traditional', 'azmari music',
        'masenqo', 'krar', 'washint', 'begena', 'kebero',
        'cultural ethiopian', 'folk ethiopian'
    ],
    'eskista': [
        'eskista', 'shoulder dance', 'ethiopian dance', 'habesha dance',
        'amhara dance', 'tigray dance'
    ],
}

# Instrument keywords mapped to instrument type
INSTRUMENT_KEYWORDS: Dict[str, List[str]] = {
    '808': [
        '808', '808s', 'eight oh eight', 'sub bass', 'trap bass',
        'sliding 808', 'gliding 808'
    ],
    'piano': [
        'piano', 'keys', 'keyboard', 'grand piano', 'upright'
    ],
    'rhodes': [
        'rhodes', 'fender rhodes', 'electric piano', 'wurly',
        'wurlitzer'
    ],
    'synth': [
        'synth', 'synthesizer', 'analog', 'digital synth', 'lead synth'
    ],
    'pad': [
        'pad', 'pads', 'synth pad', 'ambient pad', 'warm pad',
        'string pad'
    ],
    'strings': [
        'strings', 'orchestral', 'violin', 'cello', 'viola',
        'string section', 'orchestra'
    ],
    'brass': [
        'brass', 'horns', 'trumpet', 'sax', 'saxophone', 'trombone'
    ],
    'guitar': [
        'guitar', 'acoustic guitar', 'electric guitar', 'nylon',
        'fingerpick'
    ],
    'bass': [
        'bass', 'bass guitar', 'electric bass', 'upright bass',
        'standup bass'
    ],
    'vocal': [
        'vocal', 'vocals', 'voice', 'vocal chop', 'vox', 'choir',
        'chops'
    ],
    'flute': [
        'flute', 'pan flute', 'bamboo flute', 'shakuhachi'
    ],
    # Ethiopian instruments
    'krar': [
        'krar', 'kirar', 'ethiopian lyre', 'ethiopian harp'
    ],
    'masenqo': [
        'masenqo', 'masinko', 'masenko', 'ethiopian fiddle', 'one string'
    ],
    'washint': [
        'washint', 'ethiopian flute', 'bamboo flute ethiopian'
    ],
    'begena': [
        'begena', 'ethiopian harp', 'david harp', 'meditation harp'
    ],
    # Orchestral instruments
    'timpani': [
        'timpani', 'kettledrum', 'kettledrums', 'orchestral timpani'
    ],
    'harp': [
        'harp', 'concert harp', 'pedal harp', 'harp arpeggios',
        'arpeggiated harp'
    ],
    'contrabass': [
        'contrabass', 'double bass', 'string bass', 'orchestral bass'
    ],
    'french_horn': [
        'french horn', 'horn', 'french horns'
    ],
    'oboe': [
        'oboe', 'english horn', 'cor anglais'
    ],
    'clarinet': [
        'clarinet', 'bass clarinet'
    ],
    'tuba': [
        'tuba', 'sousaphone'
    ],
    'choir': [
        'choir', 'chorus', 'choral', 'voices', 'soprano',
        'alto', 'tenor', 'baritone'
    ],
    'woodwinds': [
        'woodwinds', 'woodwind', 'wind section', 'wind ensemble'
    ],
}

# Drum element keywords
DRUM_KEYWORDS: Dict[str, List[str]] = {
    'kick': ['kick', 'bass drum', 'bd'],
    '808': ['808', 'sub', '808 bass'],
    'snare': ['snare', 'snares', 'sd'],
    'clap': ['clap', 'claps', 'handclap'],
    'hihat': ['hihat', 'hi-hat', 'hi hat', 'hats', 'closed hat'],
    'hihat_open': ['open hat', 'open hihat', 'open hi-hat'],
    'hihat_roll': ['hihat roll', 'hat roll', 'roll', 'triplet hats'],
    'crash': ['crash', 'cymbal'],
    'ride': ['ride', 'ride cymbal'],
    'perc': ['perc', 'percussion', 'shaker', 'tambourine'],
    'rim': ['rim', 'rimshot', 'sidestick'],
    # Ethiopian drums
    'kebero': ['kebero', 'kebaro', 'ethiopian drum', 'habesha drum'],
    'atamo': ['atamo', 'ethiopian percussion'],
    'tom': ['tom', 'toms', 'floor tom'],
    # Orchestral percussion
    'timpani_drum': ['timpani', 'kettledrum', 'kettledrums'],
    'cymbal_crash': ['crash cymbal', 'orchestral cymbal', 'suspended cymbal'],
    'triangle': ['triangle'],
    'gong': ['gong', 'tam tam', 'tam-tam'],
    'chimes': ['chimes', 'tubular bells', 'orchestral chimes'],
}

# Texture/FX keywords
TEXTURE_KEYWORDS: Dict[str, List[str]] = {
    'vinyl': [
        'vinyl', 'vinyl crackle', 'record', 'dust', 'crackle',
        'vinyl noise', 'tape hiss'
    ],
    'rain': [
        'rain', 'rainfall', 'storm', 'thunder', 'weather'
    ],
    'tape': [
        'tape', 'cassette', 'warble', 'tape saturation', 'lo-fi tape'
    ],
    'reverb': [
        'reverb', 'reverby', 'spacious', 'cathedral', 'hall',
        'wet', 'drenched'
    ],
    'distortion': [
        'distorted', 'distortion', 'saturated', 'gritty', 'dirty',
        'crushed'
    ],
    'sidechain': [
        'sidechain', 'sidechained', 'ducking', 'pumping', 'pump'
    ],
}

# Mood keywords
MOOD_KEYWORDS: Dict[str, List[str]] = {
    'dark': [
        'dark', 'moody', 'brooding', 'melancholic', 'sad', 'somber',
        'minor', 'eerie', 'haunting', 'sinister'
    ],
    'bright': [
        'bright', 'happy', 'uplifting', 'positive', 'cheerful',
        'major', 'sunny', 'joyful'
    ],
    'aggressive': [
        'aggressive', 'hard', 'intense', 'heavy', 'powerful',
        'angry', 'rage', 'harsh'
    ],
    'chill': [
        'chill', 'relaxed', 'mellow', 'smooth', 'laid back',
        'easy', 'calm', 'peaceful'
    ],
    'emotional': [
        'emotional', 'heartfelt', 'soulful', 'passionate',
        'expressive', 'deep'
    ],
}

# Section/arrangement hints
SECTION_KEYWORDS: Dict[str, List[str]] = {
    'intro': ['intro', 'introduction', 'start'],
    'drop': ['drop', 'main', 'hook', 'chorus'],
    'breakdown': ['breakdown', 'break', 'bridge'],
    'buildup': ['buildup', 'build', 'rise', 'tension'],
    'outro': ['outro', 'ending', 'end', 'fade'],
    'switch': ['switch', 'switch-up', 'switchup', 'change'],
    'verse': ['verse', 'verses'],
}


# Style modifiers (non-genre, performance/aesthetic cues)
STYLE_KEYWORDS: Dict[str, List[str]] = {
    'church': ['church', 'praise', 'worship', 'gospel', 'choir', 'hymn'],
    'gospel': ['gospel', 'praise', 'worship'],
    'zaytoven': ['zaytoven'],
    'staccato_keys': ['staccato piano', 'staccato keys', 'staccato'],
}


# =============================================================================
# SONIC ADJECTIVES - For Intelligent Instrument Selection
# =============================================================================
# These adjectives describe the desired sonic character and help the AI
# match instruments from expansion packs based on their tonal qualities.
# Organized by category with synonyms for robust matching.

SONIC_ADJECTIVES: Dict[str, List[str]] = {
    # Temperature / Warmth
    'warm': ['warm', 'warmth', 'cozy', 'toasty', 'mellow'],
    'cold': ['cold', 'icy', 'frozen', 'sterile', 'clinical'],
    'hot': ['hot', 'sizzling', 'burning', 'fiery'],
    
    # Age / Character
    'vintage': ['vintage', 'retro', 'classic', 'old school', 'oldschool', 'throwback', '70s', '80s', '90s'],
    'modern': ['modern', 'contemporary', 'current', 'fresh', 'new'],
    'futuristic': ['futuristic', 'sci-fi', 'space', 'alien', 'cyber'],
    'analog': ['analog', 'analogue', 'tape', 'tube', 'valve'],
    'digital': ['digital', 'clean digital', 'pristine'],
    
    # Texture / Surface
    'dusty': ['dusty', 'dirty', 'gritty', 'lo-fi', 'lofi', 'crusty'],
    'clean': ['clean', 'pristine', 'polished', 'crystal', 'pure'],
    'rough': ['rough', 'raw', 'unpolished', 'harsh'],
    'smooth': ['smooth', 'silky', 'buttery', 'creamy', 'velvety'],
    'crunchy': ['crunchy', 'crispy', 'bitcrushed', 'crushed'],
    
    # Weight / Body
    'fat': ['fat', 'thick', 'chunky', 'meaty', 'beefy', 'heavy'],
    'thin': ['thin', 'light', 'airy', 'delicate', 'wispy'],
    'deep': ['deep', 'subby', 'low', 'rumbling', 'thunderous'],
    'punchy': ['punchy', 'tight', 'snappy', 'attack', 'transient'],
    
    # Brightness / Frequency
    'bright': ['bright', 'brilliant', 'sparkly', 'shimmering', 'glittery'],
    'dark': ['dark', 'murky', 'shadowy', 'dim', 'moody'],
    'dull': ['dull', 'muted', 'soft', 'filtered'],
    'present': ['present', 'forward', 'upfront', 'in your face'],
    
    # Saturation / Harmonic Content
    'saturated': ['saturated', 'driven', 'overdriven', 'pushed'],
    'distorted': ['distorted', 'fuzz', 'fuzzy', 'clipped'],
    'compressed': ['compressed', 'squashed', 'pumping'],
    
    # Space / Ambience
    'dry': ['dry', 'dead', 'close', 'intimate'],
    'wet': ['wet', 'reverberant', 'spacious', 'ambient'],
    'roomy': ['roomy', 'hall', 'chamber', 'cathedral'],
    
    # Movement / Modulation
    'lush': ['lush', 'detuned', 'thick chorus', 'wide'],
    'wobbly': ['wobbly', 'warped', 'tape wobble', 'wow', 'flutter'],
    'pulsing': ['pulsing', 'pumping', 'sidechain', 'breathing'],
    
    # Emotional / Aesthetic
    'soulful': ['soulful', 'soul', 'emotional', 'expressive', 'heartfelt'],
    'aggressive': ['aggressive', 'angry', 'hard', 'intense'],
    'dreamy': ['dreamy', 'ethereal', 'floaty', 'hazy', 'foggy'],
    'nostalgic': ['nostalgic', 'memory', 'reminiscent', 'wistful'],
    
    # Genre-associated textures
    'funky': ['funky', 'funk', 'groovy', 'bouncy'],
    'jazzy': ['jazzy', 'jazz', 'sophisticated', 'complex'],
    'cinematic': ['cinematic', 'epic', 'orchestral', 'filmic', 'movie'],
    'organic': ['organic', 'natural', 'acoustic', 'live'],
    'synthetic': ['synthetic', 'synth', 'electronic', 'artificial'],
    
    # Specific sonic descriptors (producer slang)
    'plucky': ['plucky', 'plucked', 'staccato'],
    'sustained': ['sustained', 'pad', 'long', 'held', 'legato'],
    'glassy': ['glassy', 'glass', 'crystalline', 'bell-like'],
    'woody': ['woody', 'wood', 'acoustic', 'resonant'],
    'metallic': ['metallic', 'metal', 'tinny', 'bell'],
    'breathy': ['breathy', 'airy', 'whispered', 'soft attack'],
}


# =============================================================================
# PARSER CLASS
# =============================================================================

class PromptParser:
    """
    Parses natural language music prompts into structured parameters.
    
    Uses regex patterns and keyword dictionaries - no ML required.
    """
    
    def __init__(self, strict_mode: bool = False):
        """
        Initialize the parser.
        
        Args:
            strict_mode: If True, raise errors on parse failures.
                        If False (default), use sensible defaults.
        """
        self.strict_mode = strict_mode
    
    def parse(self, prompt: str) -> ParsedPrompt:
        """
        Parse a natural language prompt into structured parameters.
        
        Args:
            prompt: Natural language music description
        
        Returns:
            ParsedPrompt with extracted parameters
        """
        # Extract negative prompt section first
        main_prompt, negative_prompt = self._extract_negative_prompt(prompt)
        prompt_lower = main_prompt.lower().strip()
        
        # Parse negative elements (what to exclude)
        excluded_drums, excluded_instruments = self._parse_negative_elements(negative_prompt)
        
        # Extract each parameter from main prompt
        bpm = self._extract_bpm(prompt_lower)
        key, scale_type = self._extract_key(prompt_lower)
        genre = self._extract_genre(prompt_lower)
        instruments = self._extract_instruments(prompt_lower)
        drum_elements = self._extract_drums(prompt_lower)
        textures = self._extract_textures(prompt_lower)
        mood = self._extract_mood(prompt_lower)
        sections = self._extract_sections(prompt_lower)
        style_modifiers = self._extract_style_modifiers(prompt_lower)
        sonic_adjectives = self._extract_sonic_adjectives(prompt_lower)
        duration = self._extract_duration(prompt_lower)

        preset, style_preset, production_preset = self._extract_presets(prompt_lower)
        
        # Apply genre defaults if BPM not specified
        if bpm is None:
            # Sprint 5: Preference-driven BPM default
            _pref_bpm = _get_preferred_bpm()
            if _pref_bpm is not None:
                bpm = _pref_bpm
            else:
                genre_config = GENRE_DEFAULTS.get(genre, {})
                bpm = genre_config.get('default_bpm', DEFAULT_CONFIG.default_bpm)
        
        # Extract time_signature from genre defaults (critical for Ethiopian 6/8, 12/8)
        genre_config = GENRE_DEFAULTS.get(genre, {})
        time_sig = genre_config.get('time_signature', (4, 4))
        
        # Check for sidechain keywords
        use_sidechain = any(
            kw in prompt_lower 
            for kw in TEXTURE_KEYWORDS.get('sidechain', [])
        )
        
        # Determine swing from genre
        genre_config = GENRE_DEFAULTS.get(genre, {})
        swing_amount = genre_config.get('swing', 0.0)
        use_swing = swing_amount > 0
        
        # If explicit swing mentioned, enable it
        if 'swing' in prompt_lower or 'swung' in prompt_lower:
            use_swing = True
            swing_amount = max(swing_amount, 0.08)
        
        return ParsedPrompt(
            bpm=bpm,
            time_signature=time_sig,
            key=key,
            scale_type=scale_type,
            genre=genre,
            style_modifiers=style_modifiers,
            sonic_adjectives=sonic_adjectives,
            instruments=instruments,
            drum_elements=drum_elements,
            excluded_drums=excluded_drums,
            excluded_instruments=excluded_instruments,
            textures=textures,
            mood=mood,
            section_hints=sections,
            use_sidechain=use_sidechain,
            use_swing=use_swing,
            swing_amount=swing_amount,
            preset=preset,
            style_preset=style_preset,
            production_preset=production_preset,
            raw_prompt=prompt,
            negative_prompt=negative_prompt,
            target_duration_seconds=duration,
        )

    def _extract_presets(self, prompt: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """Extract explicit preset requests.

        Supported explicit forms:
          - "preset: edm_house" / "preset edm_house"
          - "style preset: chill" / "style_preset chill"
          - "production preset: polished" / "production_preset polished"
        """
        def _norm(name: str) -> str:
            return name.strip().lower().replace('-', '_')

        preset = None
        style_preset = None
        production_preset = None

        m = re.search(r'\bpreset\s*(?::|=)?\s*([a-z0-9_\-]+)\b', prompt)
        if m:
            preset = _norm(m.group(1))

        m = re.search(r'\bstyle\s*(?:preset|_preset)\s*(?::|=)?\s*([a-z0-9_\-]+)\b', prompt)
        if m:
            style_preset = _norm(m.group(1))

        m = re.search(r'\bproduction\s*(?:preset|_preset)\s*(?::|=)?\s*([a-z0-9_\-]+)\b', prompt)
        if m:
            production_preset = _norm(m.group(1))

        return preset, style_preset, production_preset

    def _extract_style_modifiers(self, prompt: str) -> List[str]:
        """Extract style modifiers (e.g., church/gospel performance cues)."""
        modifiers: List[str] = []
        for name, keywords in STYLE_KEYWORDS.items():
            if any(kw in prompt for kw in keywords):
                modifiers.append(name)
        # De-duplicate while preserving order
        seen = set()
        out: List[str] = []
        for m in modifiers:
            if m not in seen:
                out.append(m)
                seen.add(m)
        return out
    
    def _extract_sonic_adjectives(self, prompt: str) -> List[str]:
        """
        Extract sonic adjectives for intelligent instrument selection.
        
        These adjectives describe the desired sound character:
        - Temperature: warm, cold, hot
        - Age: vintage, modern, analog
        - Texture: dusty, clean, crunchy
        - Weight: fat, punchy, deep
        - Brightness: bright, dark, present
        - etc.
        
        The extracted adjectives are used by InstrumentResolver to match
        instruments from expansion packs based on their tonal qualities.
        """
        adjectives: List[str] = []
        
        for name, keywords in SONIC_ADJECTIVES.items():
            # Check if any keyword variant appears in the prompt
            for kw in keywords:
                # Use word boundary matching to avoid false positives
                # e.g., "warm" shouldn't match "warming"
                if kw in prompt:
                    adjectives.append(name)
                    break  # Only add each category once
        
        # De-duplicate while preserving order (already unique due to break)
        seen = set()
        out: List[str] = []
        for adj in adjectives:
            if adj not in seen:
                out.append(adj)
                seen.add(adj)
        
        return out
    
    def _extract_bpm(self, prompt: str) -> Optional[float]:
        """Extract BPM from prompt."""
        for pattern in BPM_PATTERNS:
            match = re.search(pattern, prompt, re.IGNORECASE)
            if match:
                try:
                    bpm = float(match.group(1))
                    # Validate reasonable range
                    if 40 <= bpm <= 220:
                        return bpm
                except (ValueError, IndexError):
                    continue
        return None
    
    def _extract_duration(self, prompt: str) -> Optional[float]:
        """
        Extract target duration from prompt.
        
        Supports formats like:
        - "2 minute song", "2 minutes", "2 min"
        - "4 minute track", "4 minutes long"  
        - "120 seconds", "120s"
        - "2:30" (mm:ss format)
        - "short" (~1:30), "long" (~4:00), "extended" (~5:00)
        
        Returns:
            Duration in seconds, or None for auto/default
        """
        # Minutes patterns: "2 minute", "2 minutes", "2min", "2-minute"
        minutes_patterns = [
            r'(\d+(?:\.\d+)?)\s*(?:-?\s*)?(?:minute|minutes|min)\b',
            r'(\d+(?:\.\d+)?)\s*(?:-?\s*)?(?:minute|minutes|min)\s+(?:song|track|beat|instrumental)',
        ]
        for pattern in minutes_patterns:
            match = re.search(pattern, prompt, re.IGNORECASE)
            if match:
                try:
                    minutes = float(match.group(1))
                    if 0.5 <= minutes <= 10:  # Reasonable range: 30sec to 10min
                        return minutes * 60
                except (ValueError, IndexError):
                    continue
        
        # Seconds patterns: "120 seconds", "120s", "90 sec"
        seconds_patterns = [
            r'(\d+)\s*(?:seconds?|secs?|s)\b',
        ]
        for pattern in seconds_patterns:
            match = re.search(pattern, prompt, re.IGNORECASE)
            if match:
                try:
                    seconds = float(match.group(1))
                    if 30 <= seconds <= 600:  # 30sec to 10min
                        return seconds
                except (ValueError, IndexError):
                    continue
        
        # Time format: "2:30" or "3:00"
        time_pattern = r'\b(\d+):(\d{2})\b'
        match = re.search(time_pattern, prompt)
        if match:
            try:
                minutes = int(match.group(1))
                seconds = int(match.group(2))
                total = minutes * 60 + seconds
                if 30 <= total <= 600:
                    return float(total)
            except (ValueError, IndexError):
                pass
        
        # Keyword-based duration hints
        if any(kw in prompt for kw in ['short', 'quick', 'brief', 'snippet']):
            return 90.0  # 1:30
        if any(kw in prompt for kw in ['extended', 'long version', 'full length']):
            return 300.0  # 5:00
        if 'long' in prompt and 'song' in prompt:
            return 240.0  # 4:00
        
        # No duration specified - return None for auto
        return None

    def _extract_key(self, prompt: str) -> Tuple[str, ScaleType]:
        """Extract musical key and scale type from prompt."""
        for pattern in KEY_PATTERNS:
            match = re.search(pattern, prompt, re.IGNORECASE)
            if match:
                root = match.group(1).upper()
                # Normalize flats/sharps
                root = root.replace('♯', '#').replace('♭', 'b')
                
                # Determine scale type
                scale_str = match.group(2) if match.lastindex >= 2 else None
                if scale_str:
                    scale_str = scale_str.lower()
                    if scale_str in ['major', 'maj']:
                        scale_type = ScaleType.MAJOR
                    elif scale_str in ['minor', 'min', 'm']:
                        scale_type = ScaleType.MINOR
                    else:
                        scale_type = ScaleType.MINOR
                else:
                    # Default to minor for most electronic/hip-hop
                    scale_type = ScaleType.MINOR
                
                return (root, scale_type)
        
        # Check mood for scale hint
        if any(kw in prompt for kw in ['dark', 'moody', 'sad', 'minor']):
            return ('C', ScaleType.MINOR)
        if any(kw in prompt for kw in ['bright', 'happy', 'major', 'uplifting']):
            return ('C', ScaleType.MAJOR)

        # Sprint 5: Preference-driven key default
        _pref_key = _get_preferred_key()
        if _pref_key:
            return (_pref_key, ScaleType.MINOR)

        return ('C', ScaleType.MINOR)
    
    def _extract_genre(self, prompt: str) -> str:
        """Extract genre from prompt.
        
        Priority order: more specific genres are checked first (e.g., 'eskista' 
        before 'ethiopian_traditional') to avoid false matches.
        """
        def _keyword_matches(kw: str) -> bool:
            kw = kw.strip().lower()
            if not kw:
                return False
            # If the keyword is a phrase or contains punctuation, use a simple substring match.
            # For single-word keywords, use word boundaries to reduce false positives
            # (e.g., avoid matching "in-house" as the genre "house").
            if any(ch in kw for ch in [' ', '-', '&', '/']):
                return kw in prompt
            return re.search(rf'\b{re.escape(kw)}\b', prompt) is not None

        def _keyword_weight(genre_name: str, kw: str) -> int:
            kw = kw.strip().lower()
            if not kw:
                return 0
            # Strong signal: keyword is essentially the genre name.
            genre_variants = {
                genre_name,
                genre_name.replace('_', ' '),
                genre_name.replace('_', '-'),
            }
            if kw in genre_variants:
                return 10

            # Strong signal: multi-token genre phrase is explicitly present.
            # Example: genre_name='ethiopian_traditional', kw='traditional ethiopian'
            genre_tokens = [t for t in genre_name.replace('_', ' ').split() if t]
            if len(genre_tokens) >= 2 and all(t in kw for t in genre_tokens):
                return 11
            # Generic words that appear in many prompts/genres.
            generic = {
                'groove', 'groovy', 'vibe', 'vibes', 'smooth', 'chill', 'club',
                'dance', 'beat', 'track', 'song', 'instrumental',
            }
            if kw in generic:
                return 1
            # Phrases are usually more specific than single words.
            if any(ch in kw for ch in [' ', '-', '&', '/']):
                return 6
            return 3

        # Define priority order - more specific genres first
        # IMPORTANT: trap_soul MUST come before rnb because 'soul' is in both
        priority_order = [
            'g_funk',  # G-Funk / West Coast - check before trap
            'eskista',  # Specific Ethiopian dance style
            'ethio_jazz',  # Specific Ethiopian fusion
            'ethiopian_traditional',  # Traditional with instruments
            'ethiopian',  # General Ethiopian
            'trap_soul',  # MUST be before rnb (both have 'soul' keyword)
            'house',
            'rnb',  # R&B
            'trap',
            'lofi',
            'boom_bap',
            'ambient',
            'cinematic',  # After ambient: when both match, count tiebreaker decides
            'classical',  # After ambient: keyword counting disambiguates
        ]

        # Score all matching genres, then break ties by match count and priority.
        scores: Dict[str, int] = {}
        match_counts: Dict[str, int] = {}

        for genre_name, keywords in GENRE_KEYWORDS.items():
            best = 0
            count = 0
            for keyword in keywords:
                if _keyword_matches(keyword):
                    best = max(best, _keyword_weight(genre_name, keyword))
                    count += 1
            if best > 0:
                scores[genre_name] = best
                match_counts[genre_name] = count

        if scores:
            def _priority_index(g: str) -> int:
                return priority_order.index(g) if g in priority_order else 10_000

            # Highest score wins; if tied, more keyword matches wins; then priority.
            return sorted(scores.items(), key=lambda item: (-item[1], -match_counts.get(item[0], 0), _priority_index(item[0]), item[0]))[0][0]
        
        # Default based on other hints
        if '808' in prompt or 'hihat roll' in prompt:
            return 'trap_soul'
        if 'vinyl' in prompt or 'study' in prompt:
            return 'lofi'
        if 'four on' in prompt or '4/4 kick' in prompt:
            return 'house'
        
        return 'trap_soul'  # Safe default
    
    def _extract_instruments(self, prompt: str) -> List[str]:
        """Extract instruments from prompt using word-boundary matching."""
        import re
        found = []
        for instrument, keywords in INSTRUMENT_KEYWORDS.items():
            for keyword in keywords:
                # Use word boundaries to avoid substring false positives
                # e.g. 'ep' matching inside 'epic', 'bass' matching inside 'bassoon'
                pattern = r'\b' + re.escape(keyword) + r'\b'
                if re.search(pattern, prompt, re.IGNORECASE):
                    if instrument not in found:
                        found.append(instrument)
                    break
        return found
    
    def _extract_drums(self, prompt: str) -> List[str]:
        """Extract drum elements from prompt."""
        found = []
        for element, keywords in DRUM_KEYWORDS.items():
            for keyword in keywords:
                if keyword in prompt:
                    if element not in found:
                        found.append(element)
                    break
        return found
    
    def _extract_negative_prompt(self, full_prompt: str) -> Tuple[str, str]:
        """
        Extract negative prompt section from full prompt.
        
        Supports formats:
        - "positive prompt negative prompt: no rolling notes"
        - "positive prompt --no rolling notes"
        - "positive prompt | no rolling notes"
        
        Returns:
            Tuple of (main_prompt, negative_prompt)
        """
        # Pattern: "negative prompt:" or "negative:" followed by content
        neg_pattern = r'(?:negative\s*prompt\s*:|negative:|--no|--neg)\s*(.+?)(?:$|positive\s*prompt\s*:)'
        match = re.search(neg_pattern, full_prompt, re.IGNORECASE)
        
        if match:
            negative = match.group(1).strip()
            # Remove the negative prompt part from main prompt
            main = re.sub(neg_pattern, '', full_prompt, flags=re.IGNORECASE).strip()
            return main, negative
        
        # Alternative: pipe separator
        if '|' in full_prompt:
            parts = full_prompt.split('|', 1)
            if len(parts) == 2:
                return parts[0].strip(), parts[1].strip()
        
        return full_prompt, ''
    
    def _parse_negative_elements(self, negative_prompt: str) -> Tuple[List[str], List[str]]:
        """
        Parse negative prompt to find excluded drums and instruments.
        
        Supports patterns like:
        - "no rolling notes"
        - "no hihat roll"
        - "without 808"
        - "exclude hi-hat rolls"
        
        Returns:
            Tuple of (excluded_drums, excluded_instruments)
        """
        if not negative_prompt:
            return [], []
        
        neg_lower = negative_prompt.lower()
        excluded_drums: List[str] = []
        excluded_instruments: List[str] = []
        
        # Patterns that indicate exclusion
        exclusion_patterns = [
            r'(?:no|without|exclude|remove|avoid|skip|dont|don\'t|not)\s+(.+?)(?:$|,|\s+and\s+)',
        ]
        
        # Find all exclusion targets
        targets: List[str] = []
        for pattern in exclusion_patterns:
            matches = re.findall(pattern, neg_lower)
            targets.extend(matches)
        
        # If no pattern matched, treat entire negative prompt as exclusion list
        if not targets:
            targets = [t.strip() for t in neg_lower.replace(',', ' ').split()]
        
        # Map targets to drum elements
        roll_keywords = ['roll', 'rolls', 'rolling', 'rapid', 'triplet', 'double']
        hihat_roll_keywords = ['hihat roll', 'hi-hat roll', 'hat roll', 'rolling note', 
                              'rolling notes', 'hihat rolls', 'rolling hats']
        
        for target in targets:
            target = target.strip()
            
            # Check for hi-hat roll exclusion (most common request)
            if any(kw in target for kw in hihat_roll_keywords) or \
               ('roll' in target and any(h in target for h in ['hi', 'hat', 'hh'])):
                if 'hihat_roll' not in excluded_drums:
                    excluded_drums.append('hihat_roll')
                continue
            
            # Check for general roll exclusion
            if any(kw in target for kw in roll_keywords):
                if 'hihat_roll' not in excluded_drums:
                    excluded_drums.append('hihat_roll')
                continue
            
            # Check against drum keywords
            for drum_type, keywords in DRUM_KEYWORDS.items():
                if any(kw in target for kw in keywords) or drum_type in target:
                    if drum_type not in excluded_drums:
                        excluded_drums.append(drum_type)
                    break
            
            # Check against instrument keywords
            for inst_type, keywords in INSTRUMENT_KEYWORDS.items():
                if any(kw in target for kw in keywords) or inst_type in target:
                    if inst_type not in excluded_instruments:
                        excluded_instruments.append(inst_type)
                    break
        
        return excluded_drums, excluded_instruments
    
    def _extract_textures(self, prompt: str) -> List[str]:
        """Extract texture/FX keywords from prompt."""
        found = []
        for texture, keywords in TEXTURE_KEYWORDS.items():
            if texture == 'sidechain':  # Handled separately
                continue
            for keyword in keywords:
                if keyword in prompt:
                    if texture not in found:
                        found.append(texture)
                    break
        return found
    
    def _extract_mood(self, prompt: str) -> str:
        """Extract mood from prompt."""
        for mood, keywords in MOOD_KEYWORDS.items():
            for keyword in keywords:
                if keyword in prompt:
                    return mood
        return 'neutral'
    
    def _extract_sections(self, prompt: str) -> List[str]:
        """Extract section hints from prompt."""
        found = []
        for section, keywords in SECTION_KEYWORDS.items():
            for keyword in keywords:
                if keyword in prompt:
                    if section not in found:
                        found.append(section)
                    break
        return found


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def parse_prompt(prompt: str) -> ParsedPrompt:
    """Quick function to parse a prompt without instantiating parser."""
    return PromptParser().parse(prompt)


def get_default_prompt() -> str:
    """Return the 'avocado' default prompt for testing."""
    return (
        "lofi hip hop beat with rhodes and rain at 87 BPM in C minor "
        "with sidechained 808, moody piano chords, and vinyl crackle"
    )


# =============================================================================
# VALIDATION & TESTING
# =============================================================================

def validate_prompt(prompt: str) -> Dict[str, bool]:
    """
    Validate what can be extracted from a prompt.
    
    Returns dict of what was successfully extracted.
    """
    parsed = parse_prompt(prompt)
    
    return {
        'has_bpm': parsed.bpm != DEFAULT_CONFIG.default_bpm,
        'has_key': parsed.key != 'C' or parsed.scale_type != ScaleType.MINOR,
        'has_genre': parsed.genre != 'trap_soul',
        'has_instruments': len(parsed.instruments) > 0,
        'has_drums': len(parsed.drum_elements) > 0,
        'has_textures': len(parsed.textures) > 0,
        'has_mood': parsed.mood != 'neutral',
        'has_sections': len(parsed.section_hints) > 0,
    }


if __name__ == '__main__':
    # Quick test
    test_prompts = [
        "dark trap soul at 87 BPM in C minor with sidechained 808",
        "lofi hip hop beat with rhodes and vinyl at 85bpm",
        "hard trap beat 140 BPM with hihat rolls and 808 slides",
        "chill ambient pad in F major with reverb",
        "boom bap beat 92 BPM with piano chops and punchy drums",
        "g-funk west coast beat with smooth synths",
        "ethiopian eskista dance beat with kebero drums",
    ]
    
    parser = PromptParser()
    for prompt in test_prompts:
        print(f"\n{'='*60}")
        print(f"Prompt: {prompt}")
        print(f"{'='*60}")
        result = parser.parse(prompt)
        print(f"  BPM: {result.bpm}")
        print(f"  Key: {result.key} {result.scale_type.name}")
        print(f"  Genre: {result.genre}")
        print(f"  Instruments: {result.instruments}")
        print(f"  Drums: {result.drum_elements}")
        print(f"  Textures: {result.textures}")
        print(f"  Mood: {result.mood}")
        
        # Genre Intelligence enhancements
        if HAS_GENRE_INTELLIGENCE:
            print(f"\n  [Genre Intelligence]")
            print(f"  Hi-hat rolls: {'✓' if result.use_hihat_rolls else '✗'}")
            print(f"  Hi-hat density: {result.hihat_density}")
            print(f"  Half-time snare: {'✓' if result.use_half_time_snare else '✗'}")
            print(f"  Swing: {result.swing_amount * 100:.0f}%")
            print(f"  Humanization: {result.humanization_profile} (vel: {result.velocity_variation:.2f}, time: {result.timing_humanization:.3f})")
            print(f"  Spectral: sub={result.sub_bass_presence:.1f} bright={result.brightness:.1f} warm={result.warmth:.1f}")
            print(f"  808 character: {result.character_808}")
            print(f"  FX chain (master): {result.fx_chain_master}")
            print(f"  FX chain (drums): {result.fx_chain_drums}")
            
            if result.has_validation_issues():
                print(f"  ⚠️  Validation: {result.get_validation_summary()}")
            else:
                print(f"  ✓ Validation: {result.get_validation_summary()}")
