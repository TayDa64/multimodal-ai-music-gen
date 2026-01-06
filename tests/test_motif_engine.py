"""
Unit tests for Motif Generation Engine

Tests the core motif classes, jazz motif patterns, and integration capabilities.
"""

import pytest
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from multimodal_gen.motif_engine import (
    Motif,
    MotifLibrary,
    MotifGenerator,
    create_motif
)
from multimodal_gen.motifs.jazz_motifs import get_jazz_motifs
from multimodal_gen.motifs.common_motifs import get_common_motifs


class TestMotifClass:
    """Tests for the Motif class."""
    
    def test_motif_creation_basic(self):
        """Test basic motif creation."""
        motif = Motif(
            name="Test Motif",
            intervals=[0, 2, 4],
            rhythm=[0.5, 0.5, 1.0],
            genre_tags=["test"]
        )
        
        assert motif.name == "Test Motif"
        assert motif.intervals == [0, 2, 4]
        assert motif.rhythm == [0.5, 0.5, 1.0]
        assert len(motif.accent_pattern) == 3  # Auto-generated
        assert motif.accent_pattern == [1.0, 1.0, 1.0]
    
    def test_motif_creation_with_accents(self):
        """Test motif creation with custom accent pattern."""
        motif = Motif(
            name="Accented Motif",
            intervals=[0, 2, 4],
            rhythm=[0.5, 0.5, 1.0],
            accent_pattern=[1.0, 0.8, 0.9],
            genre_tags=["test"]
        )
        
        assert motif.accent_pattern == [1.0, 0.8, 0.9]
    
    def test_motif_validation_empty_intervals(self):
        """Test that empty intervals raises error."""
        with pytest.raises(ValueError, match="must have at least one interval"):
            Motif(
                name="Empty",
                intervals=[],
                rhythm=[1.0]
            )
    
    def test_motif_validation_empty_rhythm(self):
        """Test that empty rhythm raises error."""
        with pytest.raises(ValueError, match="must have rhythm pattern"):
            Motif(
                name="No Rhythm",
                intervals=[0, 2],
                rhythm=[]
            )
    
    def test_motif_validation_length_mismatch(self):
        """Test that intervals and rhythm must have same length."""
        with pytest.raises(ValueError, match="must have same length"):
            Motif(
                name="Mismatch",
                intervals=[0, 2, 4],
                rhythm=[0.5, 0.5]  # Too short
            )
    
    def test_motif_to_midi_notes(self):
        """Test MIDI note conversion."""
        motif = Motif(
            name="Simple",
            intervals=[0, 2, 4],
            rhythm=[1.0, 1.0, 1.0],
            accent_pattern=[1.0, 0.8, 0.9],
            genre_tags=["test"]
        )
        
        # Convert to MIDI starting at C4 (60)
        notes = motif.to_midi_notes(root_pitch=60, start_tick=0, base_velocity=100)
        
        assert len(notes) == 3
        
        # Check first note: C4, tick 0
        tick, dur, pitch, vel = notes[0]
        assert tick == 0
        assert dur == 480  # 1 beat at 480 ticks/beat
        assert pitch == 60  # C4
        assert vel == 100  # 1.0 * 100
        
        # Check second note: D4, tick 480
        tick, dur, pitch, vel = notes[1]
        assert tick == 480
        assert pitch == 62  # D4 (C + 2 semitones)
        assert vel == 80  # 0.8 * 100
        
        # Check third note: E4, tick 960
        tick, dur, pitch, vel = notes[2]
        assert tick == 960
        assert pitch == 64  # E4 (C + 4 semitones)
        assert vel == 90  # 0.9 * 100
    
    def test_motif_transpose(self):
        """Test motif transposition."""
        motif = Motif(
            name="Original",
            intervals=[0, 2, 4],
            rhythm=[1.0, 1.0, 1.0],
            genre_tags=["test"]
        )
        
        # Transpose up 5 semitones
        transposed = motif.transpose(5)
        
        assert transposed.intervals == [5, 7, 9]
        assert transposed.rhythm == motif.rhythm
        assert "transposed" in transposed.name.lower()
    
    def test_motif_get_total_duration(self):
        """Test total duration calculation."""
        motif = Motif(
            name="Duration Test",
            intervals=[0, 2, 4],
            rhythm=[0.5, 1.0, 1.5],
            genre_tags=["test"]
        )
        
        assert motif.get_total_duration() == 3.0
    
    def test_motif_serialization(self):
        """Test serialization and deserialization."""
        original = Motif(
            name="Serialize Test",
            intervals=[0, 2, 4, 5],
            rhythm=[0.5, 0.5, 0.5, 0.5],
            accent_pattern=[1.0, 0.8, 0.9, 0.85],
            genre_tags=["jazz", "test"],
            chord_context="dominant7",
            description="Test motif"
        )
        
        # Serialize
        data = original.to_dict()
        
        # Deserialize
        restored = Motif.from_dict(data)
        
        assert restored.name == original.name
        assert restored.intervals == original.intervals
        assert restored.rhythm == original.rhythm
        assert restored.accent_pattern == original.accent_pattern
        assert restored.genre_tags == original.genre_tags
        assert restored.chord_context == original.chord_context
        assert restored.description == original.description


class TestMotifLibrary:
    """Tests for the MotifLibrary class."""
    
    def test_library_creation(self):
        """Test creating empty library."""
        library = MotifLibrary()
        assert len(library) == 0
    
    def test_library_add_motif(self):
        """Test adding motifs to library."""
        library = MotifLibrary()
        
        motif1 = Motif(
            name="Test 1",
            intervals=[0, 2, 4],
            rhythm=[1.0, 1.0, 1.0],
            genre_tags=["jazz"]
        )
        
        motif2 = Motif(
            name="Test 2",
            intervals=[0, 3, 7],
            rhythm=[1.0, 1.0, 1.0],
            genre_tags=["blues"],
            chord_context="minor7"
        )
        
        library.add_motif(motif1)
        library.add_motif(motif2)
        
        assert len(library) == 2
    
    def test_library_get_by_genre(self):
        """Test retrieving motifs by genre."""
        library = MotifLibrary()
        
        jazz_motif = Motif(
            name="Jazz",
            intervals=[0, 2, 4],
            rhythm=[1.0, 1.0, 1.0],
            genre_tags=["jazz"]
        )
        
        blues_motif = Motif(
            name="Blues",
            intervals=[0, 3, 5],
            rhythm=[1.0, 1.0, 1.0],
            genre_tags=["blues"]
        )
        
        library.add_motif(jazz_motif)
        library.add_motif(blues_motif)
        
        jazz_results = library.get_motifs_for_genre("jazz")
        assert len(jazz_results) == 1
        assert jazz_results[0].name == "Jazz"
        
        blues_results = library.get_motifs_for_genre("blues")
        assert len(blues_results) == 1
        assert blues_results[0].name == "Blues"
    
    def test_library_get_by_chord(self):
        """Test retrieving motifs by chord type."""
        library = MotifLibrary()
        
        dom7_motif = Motif(
            name="Dominant",
            intervals=[0, 4, 7, 10],
            rhythm=[1.0, 1.0, 1.0, 1.0],
            genre_tags=["jazz"],
            chord_context="dominant7"
        )
        
        library.add_motif(dom7_motif)
        
        results = library.get_motifs_for_chord("dominant7")
        assert len(results) == 1
        assert results[0].chord_context == "dominant7"
    
    def test_library_get_with_tags(self):
        """Test retrieving motifs with multiple tags."""
        library = MotifLibrary()
        
        motif1 = Motif(
            name="Bebop",
            intervals=[0, 2, 4],
            rhythm=[1.0, 1.0, 1.0],
            genre_tags=["jazz", "bebop"]
        )
        
        motif2 = Motif(
            name="Blues",
            intervals=[0, 3, 5],
            rhythm=[1.0, 1.0, 1.0],
            genre_tags=["jazz", "blues"]
        )
        
        library.add_motif(motif1)
        library.add_motif(motif2)
        
        # Get motifs with both jazz and bebop tags
        results = library.get_motifs_with_tags(["jazz", "bebop"])
        assert len(results) == 1
        assert results[0].name == "Bebop"
    
    def test_library_get_random_motif(self):
        """Test getting random motif with filters."""
        library = MotifLibrary()
        
        for i in range(5):
            motif = Motif(
                name=f"Jazz {i}",
                intervals=[0, 2, 4],
                rhythm=[1.0, 1.0, 1.0],
                genre_tags=["jazz"]
            )
            library.add_motif(motif)
        
        # Get random jazz motif
        random_motif = library.get_random_motif(genre="jazz")
        assert random_motif is not None
        assert "jazz" in random_motif.genre_tags
        
        # Try to get non-existent genre
        no_motif = library.get_random_motif(genre="nonexistent")
        assert no_motif is None


class TestMotifGenerator:
    """Tests for the MotifGenerator class."""
    
    def test_generator_creation_default(self):
        """Test creating generator with default library."""
        generator = MotifGenerator()
        assert generator.library is not None
    
    def test_generator_creation_custom_library(self):
        """Test creating generator with custom library."""
        library = MotifLibrary()
        library.add_motif(Motif(
            name="Custom",
            intervals=[0, 2],
            rhythm=[1.0, 1.0],
            genre_tags=["test"]
        ))
        
        generator = MotifGenerator(library=library)
        assert len(generator.library) == 1
    
    def test_generate_jazz_motif(self):
        """Test generating jazz motif."""
        generator = MotifGenerator()
        
        # Generate jazz motif
        motif = generator.generate_motif("jazz", {})
        
        assert motif is not None
        assert isinstance(motif, Motif)
        assert "jazz" in motif.genre_tags
    
    def test_generate_jazz_motif_with_chord_context(self):
        """Test generating jazz motif with chord context."""
        generator = MotifGenerator()
        
        # Generate dominant7 motif
        motif = generator.generate_motif("jazz", {"chord_type": "dominant7"})
        
        assert motif is not None
        assert isinstance(motif, Motif)
    
    def test_get_jazz_motifs(self):
        """Test getting all jazz motifs."""
        generator = MotifGenerator()
        
        jazz_motifs = generator.get_jazz_motifs()
        
        # Should have multiple jazz motifs from jazz_motifs.py
        assert len(jazz_motifs) > 0
        for motif in jazz_motifs:
            assert "jazz" in motif.genre_tags


class TestJazzMotifs:
    """Tests for jazz motif patterns."""
    
    def test_jazz_motifs_count(self):
        """Test that we have at least 20 jazz motif patterns."""
        motifs = get_jazz_motifs()
        assert len(motifs) >= 20, f"Expected at least 20 jazz motifs, got {len(motifs)}"
    
    def test_jazz_motifs_all_valid(self):
        """Test that all jazz motifs are valid."""
        motifs = get_jazz_motifs()
        
        for motif in motifs:
            # Check required attributes
            assert motif.name
            assert len(motif.intervals) > 0
            assert len(motif.rhythm) > 0
            assert len(motif.intervals) == len(motif.rhythm)
            assert len(motif.accent_pattern) == len(motif.intervals)
            assert "jazz" in motif.genre_tags
    
    def test_jazz_motifs_bebop_patterns(self):
        """Test bebop-specific patterns exist."""
        motifs = get_jazz_motifs()
        
        bebop_motifs = [m for m in motifs if "bebop" in m.genre_tags]
        assert len(bebop_motifs) > 0, "Should have bebop patterns"
    
    def test_jazz_motifs_ii_v_i_patterns(self):
        """Test ii-V-I patterns exist."""
        motifs = get_jazz_motifs()
        
        ii_v_motifs = [m for m in motifs if "ii-V-I" in m.genre_tags]
        assert len(ii_v_motifs) > 0, "Should have ii-V-I patterns"
    
    def test_jazz_motifs_blues_patterns(self):
        """Test blues lick patterns exist."""
        motifs = get_jazz_motifs()
        
        blues_motifs = [m for m in motifs if "blues" in m.genre_tags]
        assert len(blues_motifs) > 0, "Should have blues patterns"
    
    def test_jazz_motifs_rhythmic_patterns(self):
        """Test rhythmic motif patterns exist."""
        motifs = get_jazz_motifs()
        
        rhythmic_motifs = [m for m in motifs if "rhythmic" in m.genre_tags or "swing" in m.genre_tags]
        assert len(rhythmic_motifs) > 0, "Should have rhythmic patterns"
    
    def test_jazz_motifs_call_response_patterns(self):
        """Test call-and-response patterns exist."""
        motifs = get_jazz_motifs()
        
        call_response_motifs = [m for m in motifs if "call-response" in m.genre_tags]
        assert len(call_response_motifs) > 0, "Should have call-response patterns"
    
    def test_jazz_motifs_transposable(self):
        """Test that jazz motifs can be transposed to any key."""
        motifs = get_jazz_motifs()
        
        # Take first motif and transpose it
        motif = motifs[0]
        
        # Transpose to all 12 keys
        for semitones in range(-6, 6):
            transposed = motif.transpose(semitones)
            assert len(transposed.intervals) == len(motif.intervals)
            
            # Convert to MIDI to verify valid range
            notes = transposed.to_midi_notes(root_pitch=60, start_tick=0)
            assert len(notes) == len(motif.intervals)


class TestCommonMotifs:
    """Tests for common motif patterns."""
    
    def test_common_motifs_exist(self):
        """Test that common motifs are defined."""
        motifs = get_common_motifs()
        assert len(motifs) > 0
    
    def test_common_motifs_all_valid(self):
        """Test that all common motifs are valid."""
        motifs = get_common_motifs()
        
        for motif in motifs:
            assert motif.name
            assert len(motif.intervals) > 0
            assert len(motif.rhythm) > 0
            assert len(motif.intervals) == len(motif.rhythm)
            assert "common" in motif.genre_tags


class TestCreateMotifHelper:
    """Tests for create_motif convenience function."""
    
    def test_create_motif_basic(self):
        """Test creating motif with helper function."""
        motif = create_motif(
            name="Test",
            intervals=[0, 2, 4],
            rhythm=[1.0, 1.0, 1.0],
            genre_tags=["test"]
        )
        
        assert motif.name == "Test"
        assert motif.intervals == [0, 2, 4]
        assert motif.rhythm == [1.0, 1.0, 1.0]
        assert motif.genre_tags == ["test"]
        # Accent pattern should be auto-generated
        assert motif.accent_pattern == [1.0, 1.0, 1.0]
    
    def test_create_motif_with_all_params(self):
        """Test creating motif with all parameters."""
        motif = create_motif(
            name="Complete",
            intervals=[0, 2, 4],
            rhythm=[0.5, 0.5, 1.0],
            genre_tags=["jazz"],
            accent_pattern=[1.0, 0.8, 0.9],
            chord_context="dominant7",
            description="Test description"
        )
        
        assert motif.chord_context == "dominant7"
        assert motif.description == "Test description"
        assert motif.accent_pattern == [1.0, 0.8, 0.9]


class TestIntegration:
    """Integration tests for the complete motif system."""
    
    def test_full_workflow(self):
        """Test complete workflow: generate, transpose, convert to MIDI."""
        # Create generator with jazz motifs
        generator = MotifGenerator()
        
        # Generate a jazz motif
        motif = generator.generate_motif("jazz", {"chord_type": "dominant7"})
        
        # Transpose it
        transposed = motif.transpose(5)
        
        # Convert to MIDI notes
        notes = transposed.to_midi_notes(root_pitch=60, start_tick=0)
        
        # Verify we got notes
        assert len(notes) > 0
        
        # Verify all notes are valid MIDI
        for tick, dur, pitch, vel in notes:
            assert 0 <= pitch <= 127
            assert 1 <= vel <= 127
            assert dur > 0
            assert tick >= 0
    
    def test_library_persistence(self, tmp_path):
        """Test saving and loading motif library."""
        # Create library with motifs
        library = MotifLibrary()
        
        motif1 = Motif(
            name="Test 1",
            intervals=[0, 2, 4],
            rhythm=[1.0, 1.0, 1.0],
            genre_tags=["jazz"]
        )
        
        motif2 = Motif(
            name="Test 2",
            intervals=[0, 3, 7],
            rhythm=[0.5, 0.5, 1.0],
            genre_tags=["blues"],
            chord_context="minor7"
        )
        
        library.add_motif(motif1)
        library.add_motif(motif2)
        
        # Save to file
        save_path = tmp_path / "test_library.json"
        library.save_to_file(str(save_path))
        
        # Load from file
        loaded_library = MotifLibrary.load_from_file(str(save_path))
        
        # Verify
        assert len(loaded_library) == 2
        
        jazz_motifs = loaded_library.get_motifs_for_genre("jazz")
        assert len(jazz_motifs) == 1
        assert jazz_motifs[0].name == "Test 1"
        
        blues_motifs = loaded_library.get_motifs_for_genre("blues")
        assert len(blues_motifs) == 1
        assert blues_motifs[0].name == "Test 2"
        assert blues_motifs[0].chord_context == "minor7"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
