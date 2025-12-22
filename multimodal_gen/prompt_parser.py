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
"""

import re
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Tuple, Set
from enum import Enum

from .utils import ScaleType, GENRE_DEFAULTS, DEFAULT_CONFIG


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class ParsedPrompt:
    """
    Structured result from parsing a natural language music prompt.
    
    All fields have sensible defaults for when extraction fails.
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
    
    # Instrumentation
    instruments: List[str] = field(default_factory=list)
    drum_elements: List[str] = field(default_factory=list)
    
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
    
    # Raw prompt for reference
    raw_prompt: str = ''
    
    def __post_init__(self):
        """Apply defaults based on detected genre."""
        if not self.instruments:
            self.instruments = self._get_genre_instruments()
        if not self.drum_elements:
            self.drum_elements = self._get_genre_drums()
    
    def _get_genre_instruments(self) -> List[str]:
        """Get default instruments for detected genre."""
        genre_instruments = {
            'trap': ['808', 'synth_lead'],
            'trap_soul': ['808', 'piano', 'rhodes', 'strings'],
            'lofi': ['piano', 'rhodes', 'guitar'],
            'boom_bap': ['piano', 'bass', 'brass'],
            'house': ['bass', 'synth', 'pad'],
            'ambient': ['pad', 'strings', 'piano'],
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
            'lofi': ['kick', 'snare', 'hihat'],
            'boom_bap': ['kick', 'snare', 'hihat', 'crash'],
            'house': ['kick', 'clap', 'hihat_open', 'hihat'],
            'ambient': ['kick', 'snare', 'cymbal'],
            # Ethiopian genres - kebero-based patterns
            'ethiopian': ['kebero', 'kick', 'snare', 'shaker'],
            'ethio_jazz': ['kick', 'snare', 'hihat', 'ride', 'perc'],
            'ethiopian_traditional': ['kebero', 'atamo', 'clap'],
            'eskista': ['kebero', 'kick', 'snare', 'clap', 'shaker'],
        }
        return genre_drums.get(self.genre, ['kick', 'snare', 'hihat'])


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
    'trap_soul': [
        'trap soul', 'trapsoul', 'rnb trap', 'r&b trap', 'soul trap',
        'emotional trap', 'melodic trap', 'bryson', 'sza', '6lack'
    ],
    'lofi': [
        'lofi', 'lo-fi', 'lo fi', 'chillhop', 'jazzhop', 'study',
        'chill beats', 'nujabes', 'lofi hip hop', 'lofi hiphop'
    ],
    'boom_bap': [
        'boom bap', 'boombap', '90s', 'golden era', 'old school',
        'classic hip hop', 'east coast', 'ny', 'pete rock', 'dilla'
    ],
    'house': [
        'house', 'deep house', 'tech house', 'future house',
        'progressive house', 'disco house'
    ],
    'ambient': [
        'ambient', 'atmospheric', 'cinematic', 'soundscape',
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
        'rhodes', 'fender rhodes', 'electric piano', 'ep', 'wurly',
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
        prompt_lower = prompt.lower().strip()
        
        # Extract each parameter
        bpm = self._extract_bpm(prompt_lower)
        key, scale_type = self._extract_key(prompt_lower)
        genre = self._extract_genre(prompt_lower)
        instruments = self._extract_instruments(prompt_lower)
        drum_elements = self._extract_drums(prompt_lower)
        textures = self._extract_textures(prompt_lower)
        mood = self._extract_mood(prompt_lower)
        sections = self._extract_sections(prompt_lower)
        
        # Apply genre defaults if BPM not specified
        if bpm is None:
            genre_config = GENRE_DEFAULTS.get(genre, {})
            bpm = genre_config.get('default_bpm', DEFAULT_CONFIG.default_bpm)
        
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
            key=key,
            scale_type=scale_type,
            genre=genre,
            instruments=instruments,
            drum_elements=drum_elements,
            textures=textures,
            mood=mood,
            section_hints=sections,
            use_sidechain=use_sidechain,
            use_swing=use_swing,
            swing_amount=swing_amount,
            raw_prompt=prompt,
        )
    
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
        
        return ('C', ScaleType.MINOR)
    
    def _extract_genre(self, prompt: str) -> str:
        """Extract genre from prompt.
        
        Priority order: more specific genres are checked first (e.g., 'eskista' 
        before 'ethiopian_traditional') to avoid false matches.
        """
        # Define priority order - more specific genres first
        priority_order = [
            'eskista',  # Specific Ethiopian dance style
            'ethio_jazz',  # Specific Ethiopian fusion
            'ethiopian_traditional',  # Traditional with instruments
            'ethiopian',  # General Ethiopian
            'trap_soul',  # More specific than trap
            'trap',
            'lofi',
            'boom_bap',
            'house',
            'ambient',
        ]
        
        # Check genres in priority order
        for genre in priority_order:
            if genre in GENRE_KEYWORDS:
                for keyword in GENRE_KEYWORDS[genre]:
                    if keyword in prompt:
                        return genre
        
        # Check any remaining genres not in priority list
        for genre, keywords in GENRE_KEYWORDS.items():
            if genre not in priority_order:
                for keyword in keywords:
                    if keyword in prompt:
                        return genre
        
        # Default based on other hints
        if '808' in prompt or 'hihat roll' in prompt:
            return 'trap_soul'
        if 'vinyl' in prompt or 'study' in prompt:
            return 'lofi'
        if 'four on' in prompt or '4/4 kick' in prompt:
            return 'house'
        
        return 'trap_soul'  # Safe default
    
    def _extract_instruments(self, prompt: str) -> List[str]:
        """Extract instruments from prompt."""
        found = []
        for instrument, keywords in INSTRUMENT_KEYWORDS.items():
            for keyword in keywords:
                if keyword in prompt:
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
    ]
    
    parser = PromptParser()
    for prompt in test_prompts:
        print(f"\nPrompt: {prompt}")
        result = parser.parse(prompt)
        print(f"  BPM: {result.bpm}")
        print(f"  Key: {result.key} {result.scale_type.name}")
        print(f"  Genre: {result.genre}")
        print(f"  Instruments: {result.instruments}")
        print(f"  Drums: {result.drum_elements}")
        print(f"  Textures: {result.textures}")
        print(f"  Mood: {result.mood}")
