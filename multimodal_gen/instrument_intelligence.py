"""
Instrument Intelligence Engine

Provides semantic understanding of instruments and intelligent selection
based on genre, mood, and song requirements.

The goal: Never randomly select instruments. Always make deliberate,
musically-informed choices that match the user's creative intent.
"""

import os
import re
import json
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple
from enum import Enum


class InstrumentCategory(Enum):
    """High-level instrument categories."""
    DRUMS = "drums"
    BASS = "bass"
    KEYS = "keys"
    SYNTHS = "synths"
    STRINGS = "strings"
    BRASS = "brass"
    FX = "fx"
    VOCALS = "vocals"
    UNKNOWN = "unknown"


class DrumType(Enum):
    """Drum subcategories."""
    KICK = "kick"
    SNARE = "snare"
    CLAP = "clap"
    HIHAT = "hihat"
    HIHAT_OPEN = "hihat_open"
    CYMBAL = "cymbal"
    TOM = "tom"
    PERCUSSION = "percussion"
    SHAKER = "shaker"
    RIM = "rim"
    FULL_KIT = "full_kit"


class SynthType(Enum):
    """Synth subcategories."""
    PAD = "pad"
    LEAD = "lead"
    BASS = "bass"
    PLUCK = "pluck"
    ARP = "arp"
    STAB = "stab"


class FXType(Enum):
    """FX subcategories."""
    RISER = "riser"
    DOWNLIFTER = "downlifter"
    IMPACT = "impact"
    VOCAL_CHOP = "vocal_chop"
    WHISTLE = "whistle"  # Special case - use sparingly!
    TRANSITION = "transition"
    ATMOSPHERE = "atmosphere"


@dataclass
class InstrumentMetadata:
    """
    Comprehensive metadata for an instrument sample.
    
    This is the key to intelligent selection - each sample is tagged
    with semantic information about what it IS and when to use it.
    """
    path: str
    filename: str
    category: InstrumentCategory
    subcategory: str  # DrumType, SynthType, etc as string
    
    # Musical characteristics
    key: Optional[str] = None  # "C", "F#", "Gm", etc.
    bpm: Optional[int] = None  # For loops
    
    # Genre affinity scores (0.0 to 1.0)
    genre_affinity: Dict[str, float] = field(default_factory=dict)
    
    # Mood/sentiment tags
    mood_tags: List[str] = field(default_factory=list)
    
    # When to use this sample
    use_cases: List[str] = field(default_factory=list)
    
    # When NOT to use this sample (critical for avoiding bad choices)
    exclude_contexts: List[str] = field(default_factory=list)
    
    # Sonic characteristics
    brightness: float = 0.5  # 0=dark, 1=bright
    energy: float = 0.5  # 0=mellow, 1=aggressive
    warmth: float = 0.5  # 0=cold/digital, 1=warm/analog
    
    # Quality score (can be manually curated)
    quality_score: float = 0.5  # 0=low quality, 1=professional
    
    # Pack/collection info
    pack_name: str = ""
    style_hint: str = ""  # "Thick", "GrvIt", "Fnkafd", etc.


# =============================================================================
# GENRE PROFILES - Define ideal instrument characteristics per genre
# =============================================================================

GENRE_PROFILES: Dict[str, Dict] = {
    "g_funk": {
        "description": "West Coast hip-hop: smooth, laid-back, funky",
        "tempo_range": (88, 100),
        "preferred_drums": {
            "kick": {"energy": (0.3, 0.6), "warmth": (0.6, 1.0), "tags": ["deep", "808", "smooth"]},
            "snare": {"energy": (0.3, 0.6), "brightness": (0.4, 0.7), "tags": ["crisp", "snappy"]},
            "hihat": {"energy": (0.2, 0.5), "brightness": (0.3, 0.6), "tags": ["smooth", "groovy"]},
            "clap": {"energy": (0.3, 0.5), "tags": ["layered", "tight"]},
        },
        "preferred_bass": {
            "tags": ["synth", "moog", "smooth", "sub"],
            "warmth": (0.6, 1.0),
            "energy": (0.3, 0.6),
        },
        "preferred_keys": {
            "tags": ["rhodes", "wurlitzer", "electric_piano", "smooth"],
            "warmth": (0.7, 1.0),
        },
        "preferred_synths": {
            "tags": ["pad", "warm", "smooth", "lush"],
            "exclude": ["aggressive", "harsh", "whistle", "screech"],
        },
        "preferred_brass": {
            "tags": ["soft", "muted", "smooth", "horn"],
        },
        "excluded_sounds": ["whistle", "harsh", "aggressive", "metal", "distorted"],
        "mood_keywords": ["smooth", "laid-back", "funky", "groovy", "chill", "west_coast"],
    },
    
    "boom_bap": {
        "description": "East Coast hip-hop: gritty, sample-based, head-nodding",
        "tempo_range": (85, 95),
        "preferred_drums": {
            "kick": {"energy": (0.5, 0.8), "warmth": (0.5, 0.8), "tags": ["punchy", "boom"]},
            "snare": {"energy": (0.6, 0.9), "brightness": (0.5, 0.8), "tags": ["crack", "snappy", "hard"]},
            "hihat": {"energy": (0.3, 0.6), "tags": ["crispy", "chopped"]},
        },
        "preferred_bass": {
            "tags": ["upright", "sampled", "warm"],
            "warmth": (0.5, 0.9),
        },
        "preferred_keys": {
            "tags": ["piano", "sampled", "dusty", "vinyl"],
        },
        "excluded_sounds": ["whistle", "modern", "edm", "trance"],
        "mood_keywords": ["gritty", "raw", "dusty", "golden_era", "head_nod"],
    },
    
    "trap": {
        "description": "Modern hip-hop: 808s, rolling hihats, dark",
        "tempo_range": (130, 170),  # Half-time feel at 65-85
        "preferred_drums": {
            "kick": {"energy": (0.7, 1.0), "tags": ["808", "sub", "booming"]},
            "snare": {"energy": (0.6, 0.9), "tags": ["trap", "snap", "rim"]},
            "hihat": {"energy": (0.4, 0.8), "tags": ["rolling", "triplet", "fast"]},
        },
        "preferred_bass": {
            "tags": ["808", "sub", "distorted"],
            "energy": (0.6, 1.0),
        },
        "preferred_synths": {
            "tags": ["dark", "pad", "atmospheric", "bells"],
        },
        "excluded_sounds": ["acoustic", "jazz", "smooth", "mellow"],
        "mood_keywords": ["dark", "hard", "aggressive", "trap", "modern"],
    },
    
    "lofi": {
        "description": "Lo-fi hip-hop: dusty, nostalgic, relaxing",
        "tempo_range": (70, 90),
        "preferred_drums": {
            "kick": {"energy": (0.2, 0.5), "warmth": (0.7, 1.0), "tags": ["dusty", "vinyl", "soft"]},
            "snare": {"energy": (0.2, 0.5), "tags": ["vinyl", "tape", "muted"]},
            "hihat": {"energy": (0.1, 0.4), "tags": ["soft", "brushed", "tape"]},
        },
        "preferred_bass": {
            "tags": ["warm", "muted", "smooth"],
            "warmth": (0.7, 1.0),
            "energy": (0.1, 0.4),
        },
        "preferred_keys": {
            "tags": ["piano", "rhodes", "vinyl", "dusty", "jazzy"],
        },
        "excluded_sounds": ["bright", "harsh", "modern", "edm", "whistle"],
        "mood_keywords": ["chill", "study", "nostalgic", "cozy", "relaxing"],
    },
    
    "jazz": {
        "description": "Jazz: sophisticated, improvisational, warm",
        "tempo_range": (80, 180),
        "preferred_drums": {
            "kick": {"energy": (0.2, 0.5), "tags": ["acoustic", "jazz", "brush"]},
            "snare": {"energy": (0.2, 0.5), "tags": ["brush", "jazz", "acoustic"]},
            "hihat": {"energy": (0.2, 0.4), "tags": ["ride", "brush", "swing"]},
        },
        "preferred_bass": {
            "tags": ["upright", "acoustic", "walking"],
        },
        "preferred_keys": {
            "tags": ["piano", "rhodes", "jazz", "acoustic"],
        },
        "preferred_brass": {
            "tags": ["trumpet", "saxophone", "trombone", "jazz"],
        },
        "excluded_sounds": ["electronic", "808", "synth", "whistle", "edm"],
        "mood_keywords": ["sophisticated", "smooth", "swing", "improvisational"],
    },
    
    "rnb": {
        "description": "R&B: soulful, smooth, emotional",
        "tempo_range": (60, 100),
        "preferred_drums": {
            "kick": {"energy": (0.3, 0.6), "warmth": (0.6, 1.0), "tags": ["smooth", "tight"]},
            "snare": {"energy": (0.3, 0.6), "tags": ["tight", "crisp", "layered"]},
            "hihat": {"energy": (0.2, 0.5), "tags": ["smooth", "tight"]},
        },
        "preferred_bass": {
            "tags": ["smooth", "warm", "synth", "round"],
        },
        "preferred_keys": {
            "tags": ["rhodes", "piano", "organ", "soulful"],
        },
        "preferred_synths": {
            "tags": ["pad", "warm", "lush", "smooth"],
        },
        "excluded_sounds": ["harsh", "aggressive", "metal", "whistle"],
        "mood_keywords": ["soulful", "smooth", "emotional", "romantic"],
    },
    
    "pop": {
        "description": "Pop: catchy, polished, radio-friendly",
        "tempo_range": (100, 130),
        "preferred_drums": {
            "kick": {"energy": (0.5, 0.8), "tags": ["punchy", "tight", "modern"]},
            "snare": {"energy": (0.5, 0.8), "tags": ["snappy", "big", "layered"]},
            "hihat": {"energy": (0.4, 0.7), "tags": ["crisp", "tight"]},
        },
        "preferred_bass": {
            "tags": ["synth", "punchy", "modern"],
        },
        "preferred_synths": {
            "tags": ["lead", "pad", "bright", "modern"],
        },
        "excluded_sounds": ["lo-fi", "dusty", "extreme"],
        "mood_keywords": ["catchy", "bright", "energetic", "radio"],
    },
    
    "funk": {
        "description": "Funk: groovy, rhythmic, tight pocket",
        "tempo_range": (95, 120),
        "preferred_drums": {
            "kick": {"energy": (0.5, 0.7), "tags": ["tight", "punchy", "groove"]},
            "snare": {"energy": (0.5, 0.8), "tags": ["crack", "funky", "ghost"]},
            "hihat": {"energy": (0.4, 0.7), "tags": ["16th", "groove", "tight"]},
        },
        "preferred_bass": {
            "tags": ["slap", "funky", "groove", "synth"],
        },
        "preferred_keys": {
            "tags": ["clavinet", "organ", "rhodes", "funky"],
        },
        "preferred_brass": {
            "tags": ["stab", "horn", "funky", "tight"],
        },
        "excluded_sounds": ["whistle", "ambient", "slow"],
        "mood_keywords": ["groovy", "funky", "tight", "dance"],
    },

    "cinematic": {
        "description": "Cinematic/orchestral: epic, dramatic, sweeping",
        "tempo_range": (60, 130),
        "preferred_drums": {
            "kick": {"energy": (0.5, 0.8), "warmth": (0.6, 0.9), "tags": ["orchestral", "timpani", "deep", "acoustic"]},
            "snare": {"energy": (0.4, 0.7), "tags": ["orchestral", "acoustic", "snare_roll"]},
            "hihat": {"energy": (0.2, 0.4), "tags": ["ride", "cymbal", "orchestral"]},
        },
        "preferred_bass": {
            "tags": ["contrabass", "orchestral", "acoustic", "deep", "cello"],
            "warmth": (0.6, 1.0),
        },
        "preferred_keys": {
            "tags": ["piano", "grand", "concert", "acoustic"],
        },
        "preferred_strings": {
            "tags": ["ensemble", "orchestral", "strings", "violin", "cello", "legato"],
        },
        "preferred_brass": {
            "tags": ["french_horn", "trumpet", "orchestral", "horn"],
        },
        "preferred_synths": {
            "tags": ["pad", "atmospheric", "warm", "orchestral"],
            "exclude": ["aggressive", "harsh", "whistle", "screech", "808", "electronic"],
        },
        "excluded_sounds": ["808", "trap", "electronic", "whistle", "lo-fi", "dusty", "distort", "screech"],
        "mood_keywords": ["epic", "dramatic", "sweeping", "majestic", "cinematic", "orchestral"],
    },

    "classical": {
        "description": "Classical: acoustic, elegant, refined",
        "tempo_range": (50, 180),
        "preferred_drums": {
            "kick": {"energy": (0.3, 0.6), "tags": ["timpani", "orchestral", "acoustic"]},
            "snare": {"energy": (0.3, 0.5), "tags": ["orchestral", "acoustic"]},
        },
        "preferred_bass": {
            "tags": ["contrabass", "acoustic", "cello", "orchestral"],
            "warmth": (0.6, 1.0),
        },
        "preferred_keys": {
            "tags": ["piano", "grand", "concert", "acoustic", "classical"],
        },
        "preferred_strings": {
            "tags": ["violin", "cello", "viola", "strings", "orchestral", "ensemble"],
        },
        "preferred_brass": {
            "tags": ["french_horn", "trumpet", "trombone", "orchestral"],
        },
        "preferred_synths": {
            "tags": ["pad", "orchestral"],
            "exclude": ["electronic", "808", "synth", "aggressive", "whistle"],
        },
        "excluded_sounds": ["808", "trap", "electronic", "whistle", "lo-fi", "dusty", "distort", "edm", "synth"],
        "mood_keywords": ["elegant", "refined", "classical", "acoustic", "concert"],
    },
}


# =============================================================================
# SAMPLE FILENAME PARSER
# =============================================================================

class SampleFilenameParser:
    """
    Parse instrument metadata from filenames.
    
    Funk o Rama naming convention:
    - RnB-{Category}-{Style} {Type} {Key/BPM}.WAV
    - Examples:
      - RnB-Kick-Thick Kik 1.WAV
      - RnB-Synth-GrvIt Bass F# 82.WAV
      - RnB-Perc-FrdHrd Whistle 80.WAV
      - Inst-Bass-Amphi Bass.xpm.wav
    """
    
    # Category detection patterns
    CATEGORY_PATTERNS = {
        InstrumentCategory.DRUMS: [
            r'kick', r'snare', r'snr', r'hat', r'hh', r'chh', r'ohh',
            r'clap', r'clp', r'cymbal', r'crsh', r'tom', r'rim',
            r'perc', r'drum', r'kit'
        ],
        InstrumentCategory.BASS: [r'bass'],
        InstrumentCategory.KEYS: [r'keys', r'piano', r'pno', r'organ', r'clav', r'rhodes', r'wurlitzer'],
        InstrumentCategory.SYNTHS: [r'synth', r'pad', r'lead', r'arp'],
        InstrumentCategory.STRINGS: [r'string', r'guitar', r'gtr', r'violin', r'cello'],
        InstrumentCategory.BRASS: [r'brass', r'horn', r'trumpet', r'flute', r'sax'],
        InstrumentCategory.FX: [r'fx', r'riser', r'impact', r'sweep', r'noise'],
        InstrumentCategory.VOCALS: [r'vocal', r'vox', r'voice'],
    }
    
    # Drum type patterns
    DRUM_PATTERNS = {
        DrumType.KICK: [r'kick', r'kik', r'kck', r'bd'],
        DrumType.SNARE: [r'snare', r'snr', r'sd'],
        DrumType.CLAP: [r'clap', r'clp'],
        DrumType.HIHAT: [r'chh', r'closed.*hat', r'hat(?!.*open)'],
        DrumType.HIHAT_OPEN: [r'ohh', r'open.*hat'],
        DrumType.CYMBAL: [r'cymbal', r'crsh', r'crash', r'ride'],
        DrumType.TOM: [r'tom'],
        DrumType.RIM: [r'rim'],
        DrumType.SHAKER: [r'shaker', r'shkr', r'tambourine', r'tamb'],
        DrumType.PERCUSSION: [r'perc'],
        DrumType.FULL_KIT: [r'kit', r'drum'],
    }
    
    # FX type patterns (important for excluding whistles!)
    FX_PATTERNS = {
        FXType.WHISTLE: [r'whistle'],
        FXType.RISER: [r'riser', r'rise', r'sweep.*up'],
        FXType.DOWNLIFTER: [r'downlifter', r'down', r'sweep.*down'],
        FXType.IMPACT: [r'impact', r'hit'],
        FXType.VOCAL_CHOP: [r'vocal', r'vox', r'chop'],
        FXType.TRANSITION: [r'transition', r'trans'],
        FXType.ATMOSPHERE: [r'atmosphere', r'atmos', r'ambient'],
    }
    
    # Key detection
    KEY_PATTERN = re.compile(r'\b([A-G][#b]?)\s*(?:m|min|minor|maj|major)?\b', re.IGNORECASE)
    
    # BPM detection
    BPM_PATTERN = re.compile(r'\b(\d{2,3})\b')
    
    # Style hints (from Funk o Rama naming)
    STYLE_MAP = {
        'thick': {'warmth': 0.8, 'energy': 0.6},
        'grvit': {'warmth': 0.7, 'energy': 0.5, 'tags': ['groovy']},
        'fnkafd': {'warmth': 0.6, 'energy': 0.6, 'tags': ['funky']},
        'frdhrd': {'warmth': 0.5, 'energy': 0.7, 'tags': ['hard']},
        'advtrus': {'warmth': 0.6, 'energy': 0.6, 'tags': ['adventurous']},
        'weout': {'warmth': 0.6, 'energy': 0.5},
        'smooth': {'warmth': 0.8, 'energy': 0.3, 'tags': ['smooth']},
        'dark': {'brightness': 0.3, 'energy': 0.6, 'tags': ['dark']},
        'bright': {'brightness': 0.8, 'energy': 0.6, 'tags': ['bright']},
    }
    
    @classmethod
    def parse(cls, filepath: str) -> InstrumentMetadata:
        """Parse a sample filepath into metadata."""
        path = Path(filepath)
        filename = path.name
        filename_lower = filename.lower()
        
        # Detect category
        category = cls._detect_category(filename_lower, path)
        
        # Detect subcategory - pass path for folder-based detection
        subcategory = cls._detect_subcategory(filename_lower, category, path)
        
        # Extract key
        key = cls._extract_key(filename)
        
        # Extract BPM
        bpm = cls._extract_bpm(filename)
        
        # Extract style hints
        style_hint, sonic_chars = cls._extract_style(filename_lower)
        
        # Determine mood tags and exclusions
        mood_tags, exclude_contexts = cls._determine_mood_and_exclusions(
            filename_lower, category, subcategory
        )
        
        # Set genre affinity based on pack name and style
        genre_affinity = cls._determine_genre_affinity(filename_lower, path)
        
        # Build metadata
        metadata = InstrumentMetadata(
            path=str(path),
            filename=filename,
            category=category,
            subcategory=subcategory,
            key=key,
            bpm=bpm,
            genre_affinity=genre_affinity,
            mood_tags=mood_tags,
            use_cases=cls._determine_use_cases(category, subcategory),
            exclude_contexts=exclude_contexts,
            brightness=sonic_chars.get('brightness', 0.5),
            energy=sonic_chars.get('energy', 0.5),
            warmth=sonic_chars.get('warmth', 0.5),
            quality_score=0.7,  # Default to decent quality
            pack_name=cls._extract_pack_name(path),
            style_hint=style_hint,
        )
        
        return metadata
    
    @classmethod
    def _detect_category(cls, filename_lower: str, path: Path) -> InstrumentCategory:
        """Detect instrument category from filename or path."""
        path_parts = [p.lower() for p in path.parts]
        
        # PRIORITY 1: FILENAME OVERRIDE - if filename clearly indicates a type,
        # trust that over folder location (handles misplaced samples)
        filename_category_hints = {
            'inst-bass-': InstrumentCategory.BASS,
            'inst-synth-': InstrumentCategory.SYNTHS,
            'inst-pad-': InstrumentCategory.SYNTHS,
            'inst-keys-': InstrumentCategory.KEYS,
            'inst-string': InstrumentCategory.STRINGS,
            'inst-brass': InstrumentCategory.BRASS,
        }
        for hint, cat in filename_category_hints.items():
            if hint in filename_lower:
                return cat
        
        # PRIORITY 2: Check immediate parent folder - this is the most reliable
        # because samples are organized into folders like drums/kicks, drums/hihats, etc.
        parent_folder = path.parent.name.lower() if path.parent else ""
        grandparent_folder = path.parent.parent.name.lower() if path.parent and path.parent.parent else ""
        
        # Direct folder mapping (most reliable)
        folder_category_map = {
            'drums': InstrumentCategory.DRUMS,
            'kicks': InstrumentCategory.DRUMS,
            'kick': InstrumentCategory.DRUMS,
            'snares': InstrumentCategory.DRUMS,
            'snare': InstrumentCategory.DRUMS,
            'hihats': InstrumentCategory.DRUMS,
            'hihat': InstrumentCategory.DRUMS,
            'claps': InstrumentCategory.DRUMS,
            'clap': InstrumentCategory.DRUMS,
            '808s': InstrumentCategory.DRUMS,
            'bass': InstrumentCategory.BASS,
            'keys': InstrumentCategory.KEYS,
            'synths': InstrumentCategory.SYNTHS,
            'synth': InstrumentCategory.SYNTHS,
            'strings': InstrumentCategory.STRINGS,
            'brass': InstrumentCategory.BRASS,
            'fx': InstrumentCategory.FX,
        }
        
        # Check parent folder first
        if parent_folder in folder_category_map:
            return folder_category_map[parent_folder]
        
        # Check grandparent folder
        if grandparent_folder in folder_category_map:
            return folder_category_map[grandparent_folder]
        
        # PRIORITY 3: Check filename patterns
        for cat, patterns in cls.CATEGORY_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, filename_lower):
                    return cat
        
        return InstrumentCategory.UNKNOWN
    
    @classmethod
    def _detect_subcategory(cls, filename_lower: str, category: InstrumentCategory, path: Path = None) -> str:
        """Detect specific subcategory within category."""
        
        # PRIORITY 1: Filename prefix override (handles misplaced samples)
        if 'inst-bass-' in filename_lower:
            return 'bass'
        if 'inst-synth-' in filename_lower:
            return 'synth'
        if 'inst-pad-' in filename_lower:
            return 'pad'
        if 'inst-keys-' in filename_lower:
            return 'keys'
        
        # PRIORITY 2: Check folder name (most reliable for properly organized samples)
        if path:
            parent_folder = path.parent.name.lower() if path.parent else ""
            folder_subcategory_map = {
                'kicks': 'kick',
                'kick': 'kick',
                'snares': 'snare',
                'snare': 'snare',
                'hihats': 'hihat',
                'hihat': 'hihat',
                'claps': 'clap',
                'clap': 'clap',
                '808s': 'kick',  # 808s are typically kicks
            }
            if parent_folder in folder_subcategory_map:
                return folder_subcategory_map[parent_folder]
        
        # PRIORITY 3: Filename pattern matching
        if category == InstrumentCategory.DRUMS:
            for drum_type, patterns in cls.DRUM_PATTERNS.items():
                for pattern in patterns:
                    if re.search(pattern, filename_lower):
                        return drum_type.value
            return "percussion"
        
        elif category == InstrumentCategory.FX:
            for fx_type, patterns in cls.FX_PATTERNS.items():
                for pattern in patterns:
                    if re.search(pattern, filename_lower):
                        return fx_type.value
            return "fx"
        
        elif category == InstrumentCategory.SYNTHS:
            if 'pad' in filename_lower:
                return "pad"
            elif 'lead' in filename_lower:
                return "lead"
            elif 'bass' in filename_lower:
                return "bass"
            return "synth"
        
        return category.value
    
    @classmethod
    def _extract_key(cls, filename: str) -> Optional[str]:
        """Extract musical key from filename."""
        match = cls.KEY_PATTERN.search(filename)
        if match:
            key = match.group(1).upper()
            # Check for minor
            if 'm' in filename.lower() and 'maj' not in filename.lower():
                key += 'm'
            return key
        return None
    
    @classmethod
    def _extract_bpm(cls, filename: str) -> Optional[int]:
        """Extract BPM from filename."""
        matches = cls.BPM_PATTERN.findall(filename)
        for match in matches:
            bpm = int(match)
            if 60 <= bpm <= 200:  # Reasonable BPM range
                return bpm
        return None
    
    @classmethod
    def _extract_style(cls, filename_lower: str) -> Tuple[str, Dict]:
        """Extract style hint and sonic characteristics."""
        sonic_chars = {'brightness': 0.5, 'energy': 0.5, 'warmth': 0.5}
        style_hint = ""
        
        for style, chars in cls.STYLE_MAP.items():
            if style in filename_lower:
                style_hint = style
                sonic_chars.update({k: v for k, v in chars.items() if k in sonic_chars})
                break
        
        return style_hint, sonic_chars
    
    @classmethod
    def _determine_mood_and_exclusions(
        cls, 
        filename_lower: str, 
        category: InstrumentCategory,
        subcategory: str
    ) -> Tuple[List[str], List[str]]:
        """Determine mood tags and contexts to exclude from."""
        mood_tags = []
        exclude_contexts = []
        
        # CRITICAL: Whistle detection
        if 'whistle' in filename_lower:
            mood_tags.extend(['bright', 'attention-grabbing', 'special'])
            exclude_contexts.extend([
                'main_melody', 'harmony', 'sustained', 'verse', 'chorus',
                'g_funk', 'lofi', 'jazz', 'rnb', 'smooth', 'chill'
            ])
        
        # Vocal samples need careful placement
        if 'vocal' in filename_lower or 'vox' in filename_lower:
            mood_tags.append('vocal')
            if 'chop' not in filename_lower:
                exclude_contexts.extend(['instrumental', 'background'])
        
        # FX sounds are for transitions
        if category == InstrumentCategory.FX:
            exclude_contexts.extend(['main', 'sustained', 'melody'])
            mood_tags.append('transition')
        
        # Style-based moods
        if 'smooth' in filename_lower:
            mood_tags.append('smooth')
        if 'hard' in filename_lower:
            mood_tags.append('hard')
        if 'dark' in filename_lower:
            mood_tags.append('dark')
        if 'bright' in filename_lower:
            mood_tags.append('bright')
        
        return mood_tags, exclude_contexts
    
    @classmethod
    def _determine_genre_affinity(cls, filename_lower: str, path: Path) -> Dict[str, float]:
        """
        Determine genre affinity scores.
        
        Key insight: Sample packs like "Funk o Rama" contain samples that work
        for MANY genres, not just funk. The folder name (e.g., "funk") indicates
        the pack's origin/style, NOT that they should only be used for funk.
        
        A warm, smooth bass can work for: G-Funk, R&B, Lo-fi, Neo-Soul, Pop
        A punchy kick can work for: G-Funk, Trap, Boom-Bap, Pop, EDM
        """
        affinity = {}
        path_str = str(path).lower()
        
        # BASE AFFINITY: All samples get reasonable affinity for all genres
        # This prevents samples from being "invisible" to certain genres
        base_genres = ['g_funk', 'funk', 'rnb', 'boom_bap', 'lofi', 'pop', 'jazz', 'trap', 'cinematic', 'classical']
        for genre in base_genres:
            affinity[genre] = 0.4  # Base - can be used but not preferred
        
        # PACK-BASED BOOST: Samples from funk/R&B packs get affinity boost
        # for genres that benefit from warm, groovy sounds
        if 'rnb' in filename_lower or 'funk' in path_str:
            # Boost for warm/groovy genres
            affinity['g_funk'] = 0.9
            affinity['funk'] = 0.9
            affinity['rnb'] = 0.85
            affinity['neo_soul'] = 0.8
            affinity['lofi'] = 0.7  # Lo-fi loves warm samples
            affinity['boom_bap'] = 0.7  # Classic hip-hop uses funk samples
            affinity['pop'] = 0.6
            affinity['jazz'] = 0.55
            # Still usable for other genres, just not optimal
            affinity['trap'] = 0.5  # Trap can use warm 808s and synths
        
        # FILENAME-BASED REFINEMENT: Certain keywords boost specific genres
        # 808 samples work great for trap
        if '808' in filename_lower:
            affinity['trap'] = max(affinity.get('trap', 0), 0.85)
            affinity['g_funk'] = max(affinity.get('g_funk', 0), 0.8)
        
        # Hard/aggressive sounds boost trap/drill
        if any(word in filename_lower for word in ['hard', 'aggressive', 'distort']):
            affinity['trap'] = max(affinity.get('trap', 0), 0.8)
            affinity['drill'] = max(affinity.get('drill', 0), 0.75)
        
        # Smooth/warm sounds boost chill genres
        if any(word in filename_lower for word in ['smooth', 'warm', 'soft', 'mellow']):
            affinity['lofi'] = max(affinity.get('lofi', 0), 0.85)
            affinity['jazz'] = max(affinity.get('jazz', 0), 0.75)
            affinity['neo_soul'] = max(affinity.get('neo_soul', 0), 0.8)
        
        # Electric piano / Rhodes boost soul/jazz genres
        if any(word in filename_lower for word in ['rhodes', 'elecpno', 'wurli', 'epiano']):
            affinity['jazz'] = max(affinity.get('jazz', 0), 0.9)
            affinity['neo_soul'] = max(affinity.get('neo_soul', 0), 0.9)
            affinity['rnb'] = max(affinity.get('rnb', 0), 0.9)
            affinity['g_funk'] = max(affinity.get('g_funk', 0), 0.85)
        
        # Pad sounds are universal for atmosphere
        if 'pad' in filename_lower:
            for genre in affinity:
                affinity[genre] = max(affinity[genre], 0.6)
        
        # Acoustic/orchestral sounds boost cinematic/classical
        if any(word in filename_lower for word in ['piano', 'pno', 'grand', 'acoustic', 'concert']):
            affinity['classical'] = max(affinity.get('classical', 0), 0.9)
            affinity['cinematic'] = max(affinity.get('cinematic', 0), 0.8)
        
        if any(word in filename_lower for word in ['string', 'violin', 'cello', 'orchestra', 'ensemble']):
            affinity['cinematic'] = max(affinity.get('cinematic', 0), 0.9)
            affinity['classical'] = max(affinity.get('classical', 0), 0.85)
        
        if any(word in filename_lower for word in ['horn', 'trumpet', 'brass', 'timpani']):
            affinity['cinematic'] = max(affinity.get('cinematic', 0), 0.85)
            affinity['classical'] = max(affinity.get('classical', 0), 0.8)
        
        return affinity
    
    @classmethod
    def _determine_use_cases(cls, category: InstrumentCategory, subcategory: str) -> List[str]:
        """Determine appropriate use cases."""
        use_cases = []
        
        if category == InstrumentCategory.DRUMS:
            if subcategory in ['kick', 'snare', 'hihat']:
                use_cases.extend(['main', 'groove', 'backbone'])
            elif subcategory in ['clap', 'rim']:
                use_cases.extend(['accent', 'layer'])
            elif subcategory == 'percussion':
                use_cases.extend(['fill', 'accent', 'texture'])
            elif subcategory == 'cymbal':
                use_cases.extend(['transition', 'accent', 'crash'])
        
        elif category == InstrumentCategory.BASS:
            use_cases.extend(['main', 'groove', 'foundation'])
        
        elif category == InstrumentCategory.KEYS:
            use_cases.extend(['harmony', 'melody', 'chords'])
        
        elif category == InstrumentCategory.SYNTHS:
            if subcategory == 'pad':
                use_cases.extend(['atmosphere', 'harmony', 'background'])
            elif subcategory == 'lead':
                use_cases.extend(['melody', 'hook', 'main'])
        
        elif category == InstrumentCategory.FX:
            use_cases.extend(['transition', 'accent', 'intro', 'outro'])
        
        return use_cases
    
    @classmethod
    def _extract_pack_name(cls, path: Path) -> str:
        """Extract sample pack name from path."""
        for part in path.parts:
            if 'funk' in part.lower():
                return "Funk o Rama"
        return ""


# =============================================================================
# INSTRUMENT INTELLIGENCE ENGINE
# =============================================================================

class InstrumentIntelligence:
    """
    Main engine for intelligent instrument selection.
    
    Given a genre, mood, and track requirements, selects the most
    appropriate instruments from the available library.
    """
    
    def __init__(self):
        self.instruments: List[InstrumentMetadata] = []
        self.by_category: Dict[InstrumentCategory, List[InstrumentMetadata]] = {
            cat: [] for cat in InstrumentCategory
        }
        self.by_subcategory: Dict[str, List[InstrumentMetadata]] = {}
        self._indexed = False
    
    def index_directory(self, instruments_dir: str) -> int:
        """
        Scan and index all instruments in a directory.
        
        Returns the number of instruments indexed.
        """
        instruments_path = Path(instruments_dir)
        if not instruments_path.exists():
            print(f"Warning: Instruments directory not found: {instruments_dir}")
            return 0
        
        extensions = {'.wav', '.WAV', '.aif', '.aiff', '.mp3', '.flac'}
        count = 0
        
        for filepath in instruments_path.rglob('*'):
            if filepath.suffix in extensions:
                try:
                    metadata = SampleFilenameParser.parse(str(filepath))
                    self.instruments.append(metadata)
                    self.by_category[metadata.category].append(metadata)
                    
                    if metadata.subcategory not in self.by_subcategory:
                        self.by_subcategory[metadata.subcategory] = []
                    self.by_subcategory[metadata.subcategory].append(metadata)
                    
                    count += 1
                except Exception as e:
                    print(f"Warning: Failed to parse {filepath}: {e}")
        
        self._indexed = True
        print(f"Indexed {count} instruments")
        return count
    
    def select_instrument_palette(
        self,
        genre: str,
        mood_keywords: List[str] = None,
        required_tracks: List[str] = None
    ) -> Dict[str, InstrumentMetadata]:
        """
        Select a complete instrument palette for a song.
        
        Args:
            genre: Target genre (e.g., "g_funk", "lofi", "trap")
            mood_keywords: Additional mood descriptors from prompt
            required_tracks: List of track types needed (e.g., ["kick", "snare", "bass", "keys"])
        
        Returns:
            Dictionary mapping track type to selected instrument
        """
        if not self._indexed:
            print("Warning: No instruments indexed. Call index_directory first.")
            return {}
        
        mood_keywords = mood_keywords or []
        required_tracks = required_tracks or ['kick', 'snare', 'hihat', 'clap', 'bass', 'keys', 'pad']
        
        profile = GENRE_PROFILES.get(genre, GENRE_PROFILES.get('pop', {}))
        palette = {}
        
        for track_type in required_tracks:
            instrument = self._select_best_instrument(
                track_type, genre, profile, mood_keywords
            )
            if instrument:
                palette[track_type] = instrument
        
        return palette
    
    def _select_best_instrument(
        self,
        track_type: str,
        genre: str,
        profile: Dict,
        mood_keywords: List[str]
    ) -> Optional[InstrumentMetadata]:
        """Select the best instrument for a specific track type."""
        
        # Get candidates based on track type
        candidates = self._get_candidates_for_track(track_type)
        if not candidates:
            return None
        
        # Score each candidate
        scored = []
        for inst in candidates:
            score = self._score_instrument(inst, genre, profile, mood_keywords, track_type)
            if score > 0:  # Only include non-excluded instruments
                scored.append((score, inst))
        
        if not scored:
            return None
        
        # Sort by score (highest first) and return best
        scored.sort(key=lambda x: x[0], reverse=True)
        return scored[0][1]
    
    def _get_candidates_for_track(self, track_type: str) -> List[InstrumentMetadata]:
        """Get candidate instruments for a track type."""
        track_type_lower = track_type.lower()
        
        # Direct subcategory match
        if track_type_lower in self.by_subcategory:
            candidates = self.by_subcategory[track_type_lower]
            if candidates:
                return candidates
        
        # Category mapping
        category_map = {
            'kick': (InstrumentCategory.DRUMS, 'kick'),
            'snare': (InstrumentCategory.DRUMS, 'snare'),
            'hihat': (InstrumentCategory.DRUMS, 'hihat'),
            'clap': (InstrumentCategory.DRUMS, 'clap'),
            'bass': (InstrumentCategory.BASS, None),
            'keys': (InstrumentCategory.KEYS, None),
            'piano': (InstrumentCategory.KEYS, None),
            'synth': (InstrumentCategory.SYNTHS, None),
            'pad': (InstrumentCategory.SYNTHS, 'pad'),
            'lead': (InstrumentCategory.SYNTHS, 'lead'),
            'strings': (InstrumentCategory.STRINGS, None),
            'guitar': (InstrumentCategory.STRINGS, None),
            'brass': (InstrumentCategory.BRASS, None),
            'horn': (InstrumentCategory.BRASS, None),
            'fx': (InstrumentCategory.FX, None),
        }
        
        if track_type_lower in category_map:
            category, subcategory_filter = category_map[track_type_lower]
            all_in_category = self.by_category.get(category, [])
            
            # If we need to filter by subcategory
            if subcategory_filter:
                filtered = [
                    i for i in all_in_category 
                    if i.subcategory == subcategory_filter 
                    or subcategory_filter in i.filename.lower()
                    or subcategory_filter in i.path.lower()
                ]
                if filtered:
                    return filtered
            
            return all_in_category
        
        return []
    
    def _score_instrument(
        self,
        instrument: InstrumentMetadata,
        genre: str,
        profile: Dict,
        mood_keywords: List[str],
        track_type: str
    ) -> float:
        """
        Score an instrument based on how well it matches requirements.
        
        Returns 0 if instrument should be excluded.
        """
        score = 0.5  # Base score
        
        # CHECK EXCLUSIONS FIRST
        excluded_sounds = profile.get('excluded_sounds', [])
        for excluded in excluded_sounds:
            if excluded in instrument.filename.lower():
                return 0  # Hard exclude
        
        for excluded_context in instrument.exclude_contexts:
            if excluded_context == genre or excluded_context in mood_keywords:
                return 0  # Hard exclude
        
        # Genre affinity bonus
        if genre in instrument.genre_affinity:
            score += instrument.genre_affinity[genre] * 0.3
        
        # Mood match bonus
        for mood in mood_keywords:
            if mood.lower() in instrument.mood_tags:
                score += 0.1
        
        # Track-specific preferences
        pref_key = f'preferred_{track_type}'
        if track_type in ['kick', 'snare', 'hihat', 'clap']:
            pref_key = 'preferred_drums'
        
        preferences = profile.get(pref_key, {})
        if isinstance(preferences, dict):
            # Check sonic characteristic ranges
            for char, value in preferences.items():
                if char in ('tags', 'exclude'):
                    continue
                # Value should be a tuple (min, max) for sonic characteristics
                if isinstance(value, tuple) and len(value) == 2:
                    min_val, max_val = value
                    inst_val = getattr(instrument, char, 0.5)
                    if isinstance(min_val, (int, float)) and isinstance(max_val, (int, float)):
                        if min_val <= inst_val <= max_val:
                            score += 0.1
                        else:
                            score -= 0.05
            
            # Check tag matches
            pref_tags = preferences.get('tags', [])
            for tag in pref_tags:
                if tag in instrument.filename.lower() or tag in instrument.mood_tags:
                    score += 0.15
            
            # Check exclusions
            exclude_tags = preferences.get('exclude', [])
            for tag in exclude_tags:
                if tag in instrument.filename.lower() or tag in instrument.mood_tags:
                    return 0  # Hard exclude
        
        # Quality bonus
        score += instrument.quality_score * 0.1
        
        # Variety bonus (prefer instruments from our indexed pack)
        if instrument.pack_name:
            score += 0.05
        
        return score
    
    def get_excluded_samples(self, genre: str) -> List[str]:
        """Get list of samples that should be excluded for a genre."""
        profile = GENRE_PROFILES.get(genre, {})
        excluded = profile.get('excluded_sounds', [])
        
        excluded_files = []
        for inst in self.instruments:
            for exc in excluded:
                if exc in inst.filename.lower():
                    excluded_files.append(inst.filename)
                    break
        
        return excluded_files
    
    def explain_selection(
        self, 
        instrument: InstrumentMetadata, 
        genre: str,
        track_type: str
    ) -> str:
        """Explain why an instrument was selected (for debugging/transparency)."""
        profile = GENRE_PROFILES.get(genre, {})
        
        reasons = []
        
        if genre in instrument.genre_affinity:
            reasons.append(f"Genre affinity: {instrument.genre_affinity[genre]:.0%} match for {genre}")
        
        if instrument.mood_tags:
            reasons.append(f"Mood: {', '.join(instrument.mood_tags)}")
        
        if instrument.style_hint:
            reasons.append(f"Style: {instrument.style_hint}")
        
        return f"Selected {instrument.filename} for {track_type}: " + "; ".join(reasons)


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def create_instrument_intelligence(instruments_dir: str) -> InstrumentIntelligence:
    """Create and initialize an InstrumentIntelligence instance."""
    engine = InstrumentIntelligence()
    engine.index_directory(instruments_dir)
    return engine


def select_instruments_for_prompt(
    instruments_dir: str,
    genre: str,
    mood_keywords: List[str] = None,
    tracks: List[str] = None
) -> Dict[str, str]:
    """
    High-level function to select instruments based on a prompt.
    
    Returns a dictionary mapping track type to filepath.
    """
    engine = create_instrument_intelligence(instruments_dir)
    palette = engine.select_instrument_palette(genre, mood_keywords, tracks)
    
    return {track: inst.path for track, inst in palette.items()}


# =============================================================================
# MAIN - Testing
# =============================================================================

if __name__ == "__main__":
    import sys
    
    # Test the instrument intelligence
    instruments_dir = Path(__file__).parent.parent / "instruments"
    
    print("="*60)
    print("INSTRUMENT INTELLIGENCE ENGINE TEST")
    print("="*60)
    
    engine = InstrumentIntelligence()
    count = engine.index_directory(str(instruments_dir))
    
    print(f"\nIndexed {count} instruments")
    print(f"Categories: {[(c.value, len(v)) for c, v in engine.by_category.items() if v]}")
    print(f"Subcategories: {[(k, len(v)) for k, v in engine.by_subcategory.items()]}")
    
    # Test palette selection for G-Funk
    print("\n" + "="*60)
    print("G-FUNK PALETTE SELECTION")
    print("="*60)
    
    palette = engine.select_instrument_palette(
        genre="g_funk",
        mood_keywords=["smooth", "warm", "funky"],
        required_tracks=['kick', 'snare', 'hihat', 'clap', 'bass', 'keys', 'pad']
    )
    
    for track, inst in palette.items():
        print(f"\n{track.upper()}:")
        print(f"  Selected: {inst.filename}")
        print(f"  {engine.explain_selection(inst, 'g_funk', track)}")
    
    # Show excluded samples
    print("\n" + "="*60)
    print("EXCLUDED SAMPLES FOR G-FUNK")
    print("="*60)
    
    excluded = engine.get_excluded_samples("g_funk")
    for f in excluded[:10]:  # Show first 10
        print(f"  - {f}")
    if len(excluded) > 10:
        print(f"  ... and {len(excluded) - 10} more")
