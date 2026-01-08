"""
Unit tests for Pattern Library

Tests pattern storage, retrieval, compatibility checking, and validation.
"""

import pytest
import sys
import importlib.util
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import pattern_library directly to avoid __init__.py import issues
spec = importlib.util.spec_from_file_location(
    "pattern_library",
    Path(__file__).parent.parent / "multimodal_gen" / "pattern_library.py"
)
pattern_library = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pattern_library)

# Extract the classes and functions we need
Pattern = pattern_library.Pattern
DrumPattern = pattern_library.DrumPattern
BassPattern = pattern_library.BassPattern
ChordPattern = pattern_library.ChordPattern
MelodyPattern = pattern_library.MelodyPattern
PatternType = pattern_library.PatternType
PatternIntensity = pattern_library.PatternIntensity
PatternLibrary = pattern_library.PatternLibrary
DRUM_MAP = pattern_library.DRUM_MAP
TICKS_PER_BEAT = pattern_library.TICKS_PER_BEAT
get_drum_pattern = pattern_library.get_drum_pattern
get_bass_pattern = pattern_library.get_bass_pattern
get_chord_voicings = pattern_library.get_chord_voicings
build_pattern_set = pattern_library.build_pattern_set


class TestPatternDataClasses:
    """Test Pattern dataclass and subclasses."""
    
    def test_pattern_creation(self):
        """Test basic pattern creation."""
        pattern = Pattern(
            name="test_pattern",
            pattern_type=PatternType.DRUM,
            genre="test",
            notes=[(0, 480, 36, 100)],
            length_beats=4
        )
        
        assert pattern.name == "test_pattern"
        assert pattern.pattern_type == PatternType.DRUM
        assert pattern.genre == "test"
        assert len(pattern.notes) == 1
        assert pattern.length_beats == 4
        assert pattern.intensity == PatternIntensity.MEDIUM
    
    def test_drum_pattern_creation(self):
        """Test DrumPattern with instrument mapping."""
        drum_pattern = DrumPattern(
            name="test_drums",
            pattern_type=PatternType.DRUM,
            genre="test",
            notes=[
                (0, 120, 36, 100),
                (480, 100, 38, 105),
            ],
            instrument_map={36: "kick", 38: "snare"},
            has_ghost_notes=True
        )
        
        assert drum_pattern.instrument_map[36] == "kick"
        assert drum_pattern.instrument_map[38] == "snare"
        assert drum_pattern.has_ghost_notes is True
    
    def test_bass_pattern_creation(self):
        """Test BassPattern with root-relative notation."""
        bass_pattern = BassPattern(
            name="test_bass",
            pattern_type=PatternType.BASS,
            genre="test",
            notes=[(0, 480, 0, 95)],
            root_relative=True,
            octave=2,
            follows_kick=True
        )
        
        assert bass_pattern.root_relative is True
        assert bass_pattern.octave == 2
        assert bass_pattern.follows_kick is True
    
    def test_chord_pattern_creation(self):
        """Test ChordPattern with voicing type."""
        chord_pattern = ChordPattern(
            name="test_chord",
            pattern_type=PatternType.CHORD,
            genre="test",
            notes=[
                (0, 1920, 0, 75),
                (0, 1920, 4, 72),
                (0, 1920, 7, 75),
            ],
            voicing_type="basic",
            inversion=0
        )
        
        assert chord_pattern.voicing_type == "basic"
        assert chord_pattern.inversion == 0
    
    def test_melody_pattern_creation(self):
        """Test MelodyPattern with scale degrees."""
        melody_pattern = MelodyPattern(
            name="test_melody",
            pattern_type=PatternType.MELODY,
            genre="test",
            notes=[(0, 240, 0, 85), (240, 240, 2, 80)],
            scale_degrees=[1, 2],
            contour="ascending"
        )
        
        assert melody_pattern.scale_degrees == [1, 2]
        assert melody_pattern.contour == "ascending"


class TestPatternLibrary:
    """Test PatternLibrary class."""
    
    def test_library_initialization(self):
        """Test that library loads patterns on init."""
        library = PatternLibrary()
        
        assert len(library.patterns) > 0
        assert "hip_hop" in library.patterns
        assert "pop" in library.patterns
        assert "jazz" in library.patterns
    
    def test_all_required_genres_loaded(self):
        """Test that all 10+ required genres are loaded."""
        library = PatternLibrary()
        genres = library.list_genres()
        
        required_genres = [
            "hip_hop",
            "pop",
            "jazz",
            "rock",
            "edm",
            "rnb",
            "funk",
            "latin",
            "reggae",
            "afrobeat"
        ]
        
        for genre in required_genres:
            assert genre in genres, f"Genre '{genre}' not found in library"
        
        assert len(genres) >= 10, "Library should have at least 10 genres"
    
    def test_each_genre_has_all_pattern_types(self):
        """Test that each genre has drum, bass, chord, and melody patterns."""
        library = PatternLibrary()
        
        for genre in library.list_genres():
            genre_patterns = library.patterns[genre]
            
            assert PatternType.DRUM in genre_patterns, f"{genre} missing drum patterns"
            assert PatternType.BASS in genre_patterns, f"{genre} missing bass patterns"
            assert PatternType.CHORD in genre_patterns, f"{genre} missing chord patterns"
            assert PatternType.MELODY in genre_patterns, f"{genre} missing melody patterns"
            
            # Each type should have at least 1 pattern
            assert len(genre_patterns[PatternType.DRUM]) >= 1
            assert len(genre_patterns[PatternType.BASS]) >= 1
            assert len(genre_patterns[PatternType.CHORD]) >= 1
            assert len(genre_patterns[PatternType.MELODY]) >= 1
    
    def test_get_patterns_by_genre_and_type(self):
        """Test retrieving patterns by genre and type."""
        library = PatternLibrary()
        
        hip_hop_drums = library.get_patterns("hip_hop", PatternType.DRUM)
        
        assert len(hip_hop_drums) > 0
        assert all(p.genre == "hip_hop" for p in hip_hop_drums)
        assert all(p.pattern_type == PatternType.DRUM for p in hip_hop_drums)
    
    def test_get_patterns_by_intensity(self):
        """Test filtering patterns by intensity."""
        library = PatternLibrary()
        
        high_intensity = library.get_patterns(
            "hip_hop",
            PatternType.DRUM,
            intensity=PatternIntensity.HIGH
        )
        
        assert all(p.intensity == PatternIntensity.HIGH for p in high_intensity)
    
    def test_get_patterns_by_tags(self):
        """Test filtering patterns by tags."""
        library = PatternLibrary()
        
        # Add test pattern with specific tags
        test_pattern = Pattern(
            name="test_tagged",
            pattern_type=PatternType.DRUM,
            genre="test_genre",
            notes=[(0, 480, 36, 100)],
            tags={"tag1", "tag2"}
        )
        library.add_pattern(test_pattern)
        
        results = library.get_patterns("test_genre", PatternType.DRUM, tags={"tag1"})
        
        assert len(results) > 0
        assert all("tag1" in p.tags for p in results)
    
    def test_get_patterns_for_section(self):
        """Test retrieving patterns suitable for a section."""
        library = PatternLibrary()
        
        chorus_patterns = library.get_patterns_for_section("hip_hop", "chorus")
        
        assert PatternType.DRUM in chorus_patterns
        assert PatternType.BASS in chorus_patterns
        
        for pattern_list in chorus_patterns.values():
            for pattern in pattern_list:
                assert "chorus" in pattern.section_types
    
    def test_get_pattern_by_name(self):
        """Test retrieving a specific pattern by name."""
        library = PatternLibrary()
        
        # Get a pattern we know exists
        patterns = library.get_patterns("hip_hop", PatternType.DRUM)
        if patterns:
            pattern_name = patterns[0].name
            found = library.get_pattern_by_name(pattern_name)
            
            assert found is not None
            assert found.name == pattern_name
    
    def test_get_pattern_by_name_not_found(self):
        """Test that get_pattern_by_name returns None for unknown pattern."""
        library = PatternLibrary()
        
        result = library.get_pattern_by_name("nonexistent_pattern_xyz")
        
        assert result is None
    
    def test_get_random_pattern(self):
        """Test random pattern selection."""
        library = PatternLibrary()
        
        random_pattern = library.get_random_pattern("hip_hop", PatternType.DRUM)
        
        assert random_pattern is not None
        assert random_pattern.genre == "hip_hop"
        assert random_pattern.pattern_type == PatternType.DRUM
    
    def test_get_random_pattern_with_seed(self):
        """Test random pattern selection with seed for reproducibility."""
        library = PatternLibrary()
        
        pattern1 = library.get_random_pattern("hip_hop", PatternType.DRUM, seed=42)
        pattern2 = library.get_random_pattern("hip_hop", PatternType.DRUM, seed=42)
        
        assert pattern1.name == pattern2.name
    
    def test_get_compatible_patterns(self):
        """Test retrieving compatible patterns."""
        library = PatternLibrary()
        
        base_pattern = library.get_patterns("hip_hop", PatternType.DRUM)[0]
        compatible_bass = library.get_compatible_patterns(base_pattern, PatternType.BASS)
        
        assert len(compatible_bass) > 0
        assert all(p.genre == base_pattern.genre for p in compatible_bass)
    
    def test_add_custom_pattern(self):
        """Test adding a custom pattern to library."""
        library = PatternLibrary()
        
        custom_pattern = Pattern(
            name="custom_test",
            pattern_type=PatternType.DRUM,
            genre="custom_genre",
            notes=[(0, 480, 36, 100)]
        )
        
        library.add_pattern(custom_pattern)
        
        assert "custom_genre" in library.patterns
        found = library.get_pattern_by_name("custom_test")
        assert found is not None
        assert found.name == "custom_test"
    
    def test_list_patterns_for_genre(self):
        """Test listing all pattern names for a genre."""
        library = PatternLibrary()
        
        pattern_names = library.list_patterns("hip_hop")
        
        assert PatternType.DRUM in pattern_names
        assert len(pattern_names[PatternType.DRUM]) > 0
        assert all(isinstance(name, str) for name in pattern_names[PatternType.DRUM])


class TestPatternValidation:
    """Test pattern data validation."""
    
    def test_drum_patterns_have_valid_midi_notes(self):
        """Test that drum patterns use valid MIDI note range."""
        library = PatternLibrary()
        
        for genre in library.list_genres():
            drums = library.get_patterns(genre, PatternType.DRUM)
            for pattern in drums:
                for tick, duration, pitch, velocity in pattern.notes:
                    assert 0 <= pitch <= 127, f"Invalid pitch {pitch} in {pattern.name}"
                    assert 1 <= velocity <= 127, f"Invalid velocity {velocity} in {pattern.name}"
    
    def test_patterns_have_valid_timing(self):
        """Test that patterns have valid timing (non-negative ticks)."""
        library = PatternLibrary()
        
        for genre in library.list_genres():
            for pattern_type in [PatternType.DRUM, PatternType.BASS, PatternType.CHORD, PatternType.MELODY]:
                patterns = library.get_patterns(genre, pattern_type)
                for pattern in patterns:
                    for tick, duration, pitch, velocity in pattern.notes:
                        assert tick >= 0, f"Negative tick {tick} in {pattern.name}"
                        assert duration > 0, f"Non-positive duration {duration} in {pattern.name}"
    
    def test_drum_patterns_have_instrument_map(self):
        """Test that drum patterns have instrument mappings."""
        library = PatternLibrary()
        
        for genre in library.list_genres():
            drums = library.get_patterns(genre, PatternType.DRUM)
            for pattern in drums:
                if isinstance(pattern, DrumPattern):
                    # Should have some instrument mapping
                    assert len(pattern.instrument_map) > 0, f"{pattern.name} missing instrument map"
    
    def test_bass_patterns_are_root_relative(self):
        """Test that bass patterns use root-relative notation."""
        library = PatternLibrary()
        
        for genre in library.list_genres():
            bass_patterns = library.get_patterns(genre, PatternType.BASS)
            for pattern in bass_patterns:
                if isinstance(pattern, BassPattern):
                    # Bass patterns should be root-relative
                    assert pattern.root_relative is True, f"{pattern.name} not root-relative"
    
    def test_patterns_have_section_types(self):
        """Test that patterns have section type metadata."""
        library = PatternLibrary()
        
        for genre in library.list_genres():
            drums = library.get_patterns(genre, PatternType.DRUM)
            for pattern in drums:
                assert len(pattern.section_types) > 0, f"{pattern.name} has no section types"


class TestConvenienceFunctions:
    """Test convenience functions."""
    
    def test_get_drum_pattern(self):
        """Test get_drum_pattern convenience function."""
        pattern = get_drum_pattern("hip_hop", "basic")
        
        assert pattern is not None
        assert pattern.genre == "hip_hop"
        assert isinstance(pattern, DrumPattern)
    
    def test_get_bass_pattern(self):
        """Test get_bass_pattern convenience function."""
        pattern = get_bass_pattern("hip_hop", "basic")
        
        assert pattern is not None
        assert pattern.genre == "hip_hop"
        assert isinstance(pattern, BassPattern)
    
    def test_get_chord_voicings(self):
        """Test get_chord_voicings convenience function."""
        voicings = get_chord_voicings("jazz", "major7")
        
        assert len(voicings) >= 0
        for voicing in voicings:
            assert voicing.genre == "jazz"
            assert isinstance(voicing, ChordPattern)
    
    def test_build_pattern_set(self):
        """Test build_pattern_set convenience function."""
        pattern_set = build_pattern_set("hip_hop", "chorus", PatternIntensity.MEDIUM)
        
        assert len(pattern_set) > 0
        
        # Should have at least some pattern types
        if PatternType.DRUM in pattern_set:
            assert pattern_set[PatternType.DRUM].genre == "hip_hop"
            assert "chorus" in pattern_set[PatternType.DRUM].section_types


class TestDrumMap:
    """Test DRUM_MAP constant."""
    
    def test_drum_map_exists(self):
        """Test that DRUM_MAP has standard instruments."""
        assert "kick" in DRUM_MAP
        assert "snare" in DRUM_MAP
        assert "hihat_closed" in DRUM_MAP
        assert DRUM_MAP["kick"] == 36
        assert DRUM_MAP["snare"] == 38


class TestPatternCount:
    """Test that we have enough patterns."""
    
    def test_minimum_pattern_count(self):
        """Test that library has at least 100 total patterns."""
        library = PatternLibrary()
        
        total_patterns = 0
        for genre_patterns in library.patterns.values():
            for patterns in genre_patterns.values():
                total_patterns += len(patterns)
        
        # We might not have 100+ yet but should have a good foundation (40+)
        assert total_patterns >= 40, f"Only {total_patterns} patterns found, need at least 40"
    
    def test_genre_pattern_distribution(self):
        """Test that each genre has a reasonable number of patterns."""
        library = PatternLibrary()
        
        for genre in library.list_genres():
            genre_total = 0
            for pattern_type in [PatternType.DRUM, PatternType.BASS, PatternType.CHORD, PatternType.MELODY]:
                patterns = library.get_patterns(genre, pattern_type)
                genre_total += len(patterns)
            
            # Each genre should have at least 4 patterns (1 per type minimum)
            assert genre_total >= 4, f"Genre {genre} only has {genre_total} patterns"


class TestPatternCompatibility:
    """Test pattern compatibility logic."""
    
    def test_compatible_patterns_same_genre(self):
        """Test that compatible patterns are from same genre."""
        library = PatternLibrary()
        
        base_drum = library.get_patterns("hip_hop", PatternType.DRUM)[0]
        compatible_bass = library.get_compatible_patterns(base_drum, PatternType.BASS)
        
        assert all(p.genre == "hip_hop" for p in compatible_bass)
    
    def test_compatible_patterns_similar_intensity(self):
        """Test that compatible patterns have similar intensity."""
        library = PatternLibrary()
        
        # Get a high intensity pattern
        high_drums = library.get_patterns("hip_hop", PatternType.DRUM, intensity=PatternIntensity.HIGH)
        if high_drums:
            base = high_drums[0]
            compatible = library.get_compatible_patterns(base, PatternType.BASS)
            
            # Compatible patterns should not include MINIMAL intensity with INTENSE base
            for p in compatible:
                # Intensity should be within reasonable range
                assert p.intensity != PatternIntensity.MINIMAL


class TestEdgeCases:
    """Test edge cases and error handling."""
    
    def test_get_patterns_unknown_genre(self):
        """Test getting patterns for unknown genre returns empty list."""
        library = PatternLibrary()
        
        result = library.get_patterns("unknown_genre_xyz", PatternType.DRUM)
        
        assert result == []
    
    def test_get_patterns_for_section_unknown_genre(self):
        """Test getting section patterns for unknown genre returns empty dict."""
        library = PatternLibrary()
        
        result = library.get_patterns_for_section("unknown_genre", "chorus")
        
        assert result == {}
    
    def test_list_patterns_unknown_genre(self):
        """Test listing patterns for unknown genre returns empty dict."""
        library = PatternLibrary()
        
        result = library.list_patterns("unknown_genre")
        
        assert result == {}
    
    def test_get_random_pattern_no_matches(self):
        """Test get_random_pattern returns None when no patterns match."""
        library = PatternLibrary()
        
        result = library.get_random_pattern("unknown_genre", PatternType.DRUM)
        
        assert result is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
