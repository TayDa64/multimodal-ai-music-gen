"""
Instrument Registry - Intelligent Sample Organization

Manages sample packs, their metadata, and provides smart import functionality.
Prevents samples from getting "lost in the sea" by:
1. Tracking pack origins and characteristics
2. Auto-tagging samples based on pack metadata
3. Providing search and discovery tools
"""

import os
import json
import hashlib
import shutil
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Set
from datetime import datetime
from enum import Enum


class PackOrigin(Enum):
    """Where the sample pack came from."""
    EXPANSION = "expansion"      # Official expansion pack
    USER_IMPORT = "user_import"  # User imported pack
    RECORDED = "recorded"        # User recorded samples
    GENERATED = "generated"      # AI/synth generated
    UNKNOWN = "unknown"


@dataclass
class SamplePackInfo:
    """Information about a sample pack."""
    name: str
    origin: PackOrigin = PackOrigin.UNKNOWN
    import_date: str = ""
    source_path: str = ""
    total_samples: int = 0
    
    # Genre characteristics
    primary_genres: List[str] = field(default_factory=list)
    secondary_genres: List[str] = field(default_factory=list)
    
    # Sonic characteristics (aggregate of all samples)
    avg_warmth: float = 0.5
    avg_brightness: float = 0.5
    avg_energy: float = 0.5
    
    # Content breakdown
    categories: Dict[str, int] = field(default_factory=dict)
    
    # User notes
    description: str = ""
    tags: List[str] = field(default_factory=list)
    rating: int = 0  # 1-5 stars
    
    def to_dict(self) -> Dict:
        d = asdict(self)
        d['origin'] = self.origin.value
        return d
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'SamplePackInfo':
        data['origin'] = PackOrigin(data.get('origin', 'unknown'))
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class InstrumentRegistryEntry:
    """A registered instrument/sample."""
    path: str
    filename: str
    pack_name: str = ""
    category: str = "unknown"
    subcategory: str = ""
    
    # Identification
    file_hash: str = ""  # SHA256 for duplicate detection
    
    # Musical properties
    key: Optional[str] = None
    bpm: Optional[int] = None
    
    # Genre fitness (0-1 scores)
    genre_fitness: Dict[str, float] = field(default_factory=dict)
    
    # User customization
    user_tags: List[str] = field(default_factory=list)
    user_rating: int = 0
    favorite: bool = False
    hidden: bool = False  # User can hide samples they don't want
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'InstrumentRegistryEntry':
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


class InstrumentRegistry:
    """
    Central registry for all instruments/samples.
    
    Features:
    - Track sample pack origins
    - Prevent duplicates
    - Smart organization
    - User customization (favorites, ratings, tags)
    - Search and discovery
    """
    
    def __init__(self, instruments_dir: str):
        self.instruments_dir = Path(instruments_dir)
        self.registry_file = self.instruments_dir / "registry.json"
        
        self.packs: Dict[str, SamplePackInfo] = {}
        self.instruments: Dict[str, InstrumentRegistryEntry] = {}  # path -> entry
        self.hash_index: Dict[str, str] = {}  # hash -> path (for duplicate detection)
        
        self._load_registry()
    
    def _load_registry(self):
        """Load registry from disk."""
        if self.registry_file.exists():
            try:
                with open(self.registry_file, 'r') as f:
                    data = json.load(f)
                
                for pack_data in data.get('packs', []):
                    pack = SamplePackInfo.from_dict(pack_data)
                    self.packs[pack.name] = pack
                
                for entry_data in data.get('instruments', []):
                    entry = InstrumentRegistryEntry.from_dict(entry_data)
                    self.instruments[entry.path] = entry
                    if entry.file_hash:
                        self.hash_index[entry.file_hash] = entry.path
                        
            except Exception as e:
                print(f"Warning: Failed to load registry: {e}")
    
    def save(self):
        """Save registry to disk."""
        data = {
            'version': '1.0',
            'last_updated': datetime.now().isoformat(),
            'packs': [pack.to_dict() for pack in self.packs.values()],
            'instruments': [entry.to_dict() for entry in self.instruments.values()],
        }
        
        with open(self.registry_file, 'w') as f:
            json.dump(data, f, indent=2)
    
    def import_pack(
        self,
        source_dir: str,
        pack_name: str,
        description: str = "",
        primary_genres: List[str] = None,
        tags: List[str] = None
    ) -> Dict[str, int]:
        """
        Import a sample pack intelligently.
        
        Returns dict with import statistics.
        """
        source_path = Path(source_dir)
        if not source_path.exists():
            raise ValueError(f"Source directory not found: {source_dir}")
        
        stats = {
            'total_found': 0,
            'imported': 0,
            'duplicates': 0,
            'errors': 0,
            'by_category': {},
        }
        
        # Create pack info
        pack_info = SamplePackInfo(
            name=pack_name,
            origin=PackOrigin.USER_IMPORT,
            import_date=datetime.now().isoformat(),
            source_path=str(source_path),
            description=description,
            primary_genres=primary_genres or [],
            tags=tags or [],
        )
        
        # Scan for audio files
        audio_extensions = {'.wav', '.WAV', '.aif', '.aiff', '.mp3', '.flac'}
        
        for filepath in source_path.rglob('*'):
            if filepath.suffix in audio_extensions:
                stats['total_found'] += 1
                
                try:
                    result = self._import_single_file(filepath, pack_name)
                    
                    if result == 'imported':
                        stats['imported'] += 1
                        # Track category
                        entry = self.instruments.get(str(filepath))
                        if entry:
                            cat = entry.category
                            stats['by_category'][cat] = stats['by_category'].get(cat, 0) + 1
                    elif result == 'duplicate':
                        stats['duplicates'] += 1
                        
                except Exception as e:
                    stats['errors'] += 1
                    print(f"Error importing {filepath}: {e}")
        
        # Update pack info
        pack_info.total_samples = stats['imported']
        pack_info.categories = stats['by_category']
        self.packs[pack_name] = pack_info
        
        self.save()
        return stats
    
    def _import_single_file(self, filepath: Path, pack_name: str) -> str:
        """Import a single file. Returns 'imported', 'duplicate', or 'error'."""
        # Calculate hash
        file_hash = self._calculate_hash(filepath)
        
        # Check for duplicate
        if file_hash in self.hash_index:
            return 'duplicate'
        
        # Detect category from path
        category = self._detect_category(filepath)
        subcategory = self._detect_subcategory(filepath, category)
        
        # Determine destination
        dest_dir = self.instruments_dir / category / "imported"
        dest_dir.mkdir(parents=True, exist_ok=True)
        
        # Copy file (preserve original, don't move)
        dest_path = dest_dir / filepath.name
        
        # Handle name collision
        counter = 1
        while dest_path.exists():
            stem = filepath.stem
            suffix = filepath.suffix
            dest_path = dest_dir / f"{stem}_{counter}{suffix}"
            counter += 1
        
        shutil.copy2(filepath, dest_path)
        
        # Create registry entry
        entry = InstrumentRegistryEntry(
            path=str(dest_path),
            filename=dest_path.name,
            pack_name=pack_name,
            category=category,
            subcategory=subcategory,
            file_hash=file_hash,
        )
        
        # Auto-detect key/bpm from filename
        entry.key = self._detect_key(filepath.name)
        entry.bpm = self._detect_bpm(filepath.name)
        
        # Set genre fitness based on pack info
        pack = self.packs.get(pack_name)
        if pack and pack.primary_genres:
            for genre in pack.primary_genres:
                entry.genre_fitness[genre] = 0.9
        
        self.instruments[str(dest_path)] = entry
        self.hash_index[file_hash] = str(dest_path)
        
        return 'imported'
    
    def _calculate_hash(self, filepath: Path) -> str:
        """Calculate SHA256 hash of file."""
        hasher = hashlib.sha256()
        with open(filepath, 'rb') as f:
            for chunk in iter(lambda: f.read(65536), b''):
                hasher.update(chunk)
        return hasher.hexdigest()
    
    def _detect_category(self, filepath: Path) -> str:
        """Detect category from path/filename."""
        path_lower = str(filepath).lower()
        filename_lower = filepath.name.lower()
        
        category_keywords = {
            'drums': ['kick', 'snare', 'hat', 'clap', 'drum', 'perc', '808'],
            'bass': ['bass'],
            'keys': ['keys', 'piano', 'rhodes', 'organ'],
            'synths': ['synth', 'lead', 'pad'],
            'strings': ['string', 'violin', 'cello'],
            'brass': ['brass', 'trumpet', 'horn', 'sax'],
            'fx': ['fx', 'riser', 'impact', 'sweep'],
        }
        
        for category, keywords in category_keywords.items():
            for keyword in keywords:
                if keyword in path_lower or keyword in filename_lower:
                    return category
        
        return 'misc'
    
    def _detect_subcategory(self, filepath: Path, category: str) -> str:
        """Detect subcategory."""
        filename_lower = filepath.name.lower()
        
        if category == 'drums':
            if 'kick' in filename_lower or 'kik' in filename_lower:
                return 'kick'
            elif 'snare' in filename_lower or 'snr' in filename_lower:
                return 'snare'
            elif 'hat' in filename_lower:
                return 'hihat'
            elif 'clap' in filename_lower:
                return 'clap'
            elif '808' in filename_lower:
                return '808'
        
        return category
    
    def _detect_key(self, filename: str) -> Optional[str]:
        """Detect musical key from filename."""
        import re
        match = re.search(r'\b([A-G][#b]?)\s*(?:m|min|minor|maj|major)?\b', filename, re.IGNORECASE)
        if match:
            return match.group(1).upper()
        return None
    
    def _detect_bpm(self, filename: str) -> Optional[int]:
        """Detect BPM from filename."""
        import re
        matches = re.findall(r'\b(\d{2,3})\b', filename)
        for match in matches:
            bpm = int(match)
            if 60 <= bpm <= 200:
                return bpm
        return None
    
    # =========================================================================
    # SEARCH AND DISCOVERY
    # =========================================================================
    
    def search(
        self,
        query: str = None,
        category: str = None,
        genre: str = None,
        pack_name: str = None,
        favorites_only: bool = False,
        exclude_hidden: bool = True,
        min_rating: int = 0
    ) -> List[InstrumentRegistryEntry]:
        """Search instruments with filters."""
        results = []
        
        for entry in self.instruments.values():
            # Apply filters
            if exclude_hidden and entry.hidden:
                continue
            
            if favorites_only and not entry.favorite:
                continue
            
            if min_rating > 0 and entry.user_rating < min_rating:
                continue
            
            if category and entry.category != category:
                continue
            
            if pack_name and entry.pack_name != pack_name:
                continue
            
            if genre:
                if genre not in entry.genre_fitness or entry.genre_fitness[genre] < 0.5:
                    continue
            
            if query:
                query_lower = query.lower()
                if query_lower not in entry.filename.lower():
                    if not any(query_lower in tag.lower() for tag in entry.user_tags):
                        continue
            
            results.append(entry)
        
        return results
    
    def get_by_genre(self, genre: str, limit: int = 50) -> List[InstrumentRegistryEntry]:
        """Get top instruments for a genre."""
        results = []
        
        for entry in self.instruments.values():
            if entry.hidden:
                continue
            
            fitness = entry.genre_fitness.get(genre, 0.4)  # Default moderate fitness
            results.append((fitness, entry))
        
        # Sort by fitness
        results.sort(key=lambda x: x[0], reverse=True)
        
        return [entry for _, entry in results[:limit]]
    
    def get_favorites(self) -> List[InstrumentRegistryEntry]:
        """Get all favorited instruments."""
        return [e for e in self.instruments.values() if e.favorite and not e.hidden]
    
    def get_by_pack(self, pack_name: str) -> List[InstrumentRegistryEntry]:
        """Get all instruments from a specific pack."""
        return [e for e in self.instruments.values() if e.pack_name == pack_name]
    
    def get_statistics(self) -> Dict:
        """Get registry statistics."""
        stats = {
            'total_packs': len(self.packs),
            'total_instruments': len(self.instruments),
            'by_category': {},
            'by_pack': {},
            'favorites_count': 0,
            'hidden_count': 0,
        }
        
        for entry in self.instruments.values():
            cat = entry.category
            stats['by_category'][cat] = stats['by_category'].get(cat, 0) + 1
            
            pack = entry.pack_name or 'Unknown'
            stats['by_pack'][pack] = stats['by_pack'].get(pack, 0) + 1
            
            if entry.favorite:
                stats['favorites_count'] += 1
            if entry.hidden:
                stats['hidden_count'] += 1
        
        return stats
    
    # =========================================================================
    # USER CUSTOMIZATION
    # =========================================================================
    
    def set_favorite(self, path: str, favorite: bool = True):
        """Mark instrument as favorite."""
        if path in self.instruments:
            self.instruments[path].favorite = favorite
            self.save()
    
    def set_hidden(self, path: str, hidden: bool = True):
        """Hide instrument from selection."""
        if path in self.instruments:
            self.instruments[path].hidden = hidden
            self.save()
    
    def set_rating(self, path: str, rating: int):
        """Set user rating (1-5)."""
        if path in self.instruments:
            self.instruments[path].user_rating = max(0, min(5, rating))
            self.save()
    
    def add_tag(self, path: str, tag: str):
        """Add user tag to instrument."""
        if path in self.instruments:
            if tag not in self.instruments[path].user_tags:
                self.instruments[path].user_tags.append(tag)
                self.save()
    
    def set_genre_fitness(self, path: str, genre: str, fitness: float):
        """Override genre fitness for an instrument."""
        if path in self.instruments:
            self.instruments[path].genre_fitness[genre] = max(0.0, min(1.0, fitness))
            self.save()


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def create_registry(instruments_dir: str) -> InstrumentRegistry:
    """Create and return an InstrumentRegistry."""
    return InstrumentRegistry(instruments_dir)


def import_sample_pack(
    instruments_dir: str,
    source_dir: str,
    pack_name: str,
    genres: List[str] = None
) -> Dict:
    """Convenience function to import a sample pack."""
    registry = InstrumentRegistry(instruments_dir)
    return registry.import_pack(
        source_dir=source_dir,
        pack_name=pack_name,
        primary_genres=genres or []
    )


# =============================================================================
# CLI
# =============================================================================

if __name__ == "__main__":
    import sys
    
    instruments_dir = Path(__file__).parent.parent / "instruments"
    registry = InstrumentRegistry(str(instruments_dir))
    
    print("="*60)
    print("INSTRUMENT REGISTRY")
    print("="*60)
    
    stats = registry.get_statistics()
    print(f"\nTotal Packs: {stats['total_packs']}")
    print(f"Total Instruments: {stats['total_instruments']}")
    print(f"Favorites: {stats['favorites_count']}")
    print(f"Hidden: {stats['hidden_count']}")
    
    print("\nBy Category:")
    for cat, count in sorted(stats['by_category'].items()):
        print(f"  {cat}: {count}")
    
    print("\nBy Pack:")
    for pack, count in sorted(stats['by_pack'].items()):
        print(f"  {pack}: {count}")
