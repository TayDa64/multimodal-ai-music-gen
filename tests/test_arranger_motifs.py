"""
Unit tests for Motif-Aware Arranger Integration

Tests the integration of motif engine with arranger for thematic coherence
across sections.
"""

import pytest
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from multimodal_gen.arranger import (
    Arrangement,
    MotifAssignment,
    generate_arrangement_with_motifs,
    get_section_motif,
    get_default_motif_mapping,
    GENRE_MOTIF_MAPPINGS,
    create_arrangement,
)
from multimodal_gen.motif_engine import Motif
from multimodal_gen.prompt_parser import ParsedPrompt, ScaleType


class TestMotifAssignment:
    """Tests for MotifAssignment dataclass."""
    
    def test_motif_assignment_creation_basic(self):
        """Test basic MotifAssignment creation."""
        assignment = MotifAssignment(
            motif_index=0,
            transformation="original"
        )
        
        assert assignment.motif_index == 0
        assert assignment.transformation == "original"
        assert assignment.transform_params == {}
    
    def test_motif_assignment_with_params(self):
        """Test MotifAssignment with transformation parameters."""
        assignment = MotifAssignment(
            motif_index=1,
            transformation="invert",
            transform_params={"pivot": 60}
        )
        
        assert assignment.motif_index == 1
        assert assignment.transformation == "invert"
        assert assignment.transform_params == {"pivot": 60}
    
    def test_motif_assignment_sequence_params(self):
        """Test MotifAssignment with sequence transformation."""
        assignment = MotifAssignment(
            motif_index=0,
            transformation="sequence",
            transform_params={"steps": 3}
        )
        
        assert assignment.transformation == "sequence"
        assert assignment.transform_params["steps"] == 3


class TestArrangementExtension:
    """Tests for Arrangement class motif extensions."""
    
    def test_arrangement_has_motif_fields(self):
        """Test that Arrangement has motif fields."""
        parsed = ParsedPrompt(
            bpm=87.0,
            genre="trap_soul",
            key="C",
            scale_type=ScaleType.MINOR
        )
        
        arrangement = create_arrangement(parsed)
        
        # Check that new fields exist and have correct types
        assert hasattr(arrangement, 'motifs')
        assert hasattr(arrangement, 'motif_assignments')
        assert isinstance(arrangement.motifs, list)
        assert isinstance(arrangement.motif_assignments, dict)
    
    def test_arrangement_backward_compatible(self):
        """Test that existing arrangement creation still works."""
        parsed = ParsedPrompt(
            bpm=87.0,
            genre="trap_soul",
            key="C"
        )
        
        # Old function should still work
        arrangement = create_arrangement(parsed)
        
        # Should have sections
        assert len(arrangement.sections) > 0
        assert arrangement.total_bars > 0
        assert arrangement.bpm == 87.0
        
        # Motif fields should be empty by default
        assert len(arrangement.motifs) == 0
        assert len(arrangement.motif_assignments) == 0


class TestGenerateArrangementWithMotifs:
    """Tests for generate_arrangement_with_motifs function."""
    
    def test_generate_arrangement_with_motifs_basic(self):
        """Test basic motif arrangement generation."""
        parsed = ParsedPrompt(
            bpm=87.0,
            genre="trap_soul",
            key="C",
            scale_type=ScaleType.MINOR
        )
        
        arrangement = generate_arrangement_with_motifs(parsed, num_motifs=2)
        
        # Should have sections
        assert len(arrangement.sections) > 0
        
        # Should have motifs
        assert len(arrangement.motifs) == 2
        
        # Should have assignments
        assert len(arrangement.motif_assignments) > 0
        
        # Each section should have an assignment
        for section in arrangement.sections:
            section_type = section.section_type.value
            # Check if any assignment matches this section type
            has_assignment = any(
                section_type in key 
                for key in arrangement.motif_assignments.keys()
            )
            assert has_assignment
    
    def test_generate_with_different_num_motifs(self):
        """Test generating with different numbers of motifs."""
        parsed = ParsedPrompt(
            bpm=87.0,
            genre="pop",
            key="C"
        )
        
        # Test with 1 motif
        arr1 = generate_arrangement_with_motifs(parsed, num_motifs=1)
        assert len(arr1.motifs) == 1
        
        # Test with 2 motifs
        arr2 = generate_arrangement_with_motifs(parsed, num_motifs=2)
        assert len(arr2.motifs) == 2
        
        # Test with 3 motifs
        arr3 = generate_arrangement_with_motifs(parsed, num_motifs=3)
        assert len(arr3.motifs) == 3
    
    def test_generate_clamps_motif_count(self):
        """Test that motif count is clamped to valid range (1-3)."""
        parsed = ParsedPrompt(
            bpm=87.0,
            genre="trap_soul",
            key="C"
        )
        
        # Test below minimum
        arr_low = generate_arrangement_with_motifs(parsed, num_motifs=0)
        assert len(arr_low.motifs) == 1
        
        # Test above maximum
        arr_high = generate_arrangement_with_motifs(parsed, num_motifs=10)
        assert len(arr_high.motifs) == 3
    
    def test_generate_with_seed_reproducibility(self):
        """Test that using same seed produces same results."""
        parsed = ParsedPrompt(
            bpm=87.0,
            genre="trap_soul",
            key="C",
            scale_type=ScaleType.MINOR
        )
        
        # Generate with seed
        arr1 = generate_arrangement_with_motifs(parsed, num_motifs=2, seed=42)
        arr2 = generate_arrangement_with_motifs(parsed, num_motifs=2, seed=42)
        
        # Should have same structure
        assert len(arr1.sections) == len(arr2.sections)
        assert len(arr1.motifs) == len(arr2.motifs)
        assert len(arr1.motif_assignments) == len(arr2.motif_assignments)
        
        # Motif assignments should match
        for key in arr1.motif_assignments.keys():
            assert key in arr2.motif_assignments
            assert arr1.motif_assignments[key].motif_index == arr2.motif_assignments[key].motif_index
            assert arr1.motif_assignments[key].transformation == arr2.motif_assignments[key].transformation
    
    def test_generate_assigns_valid_motif_indices(self):
        """Test that all assignments have valid motif indices."""
        parsed = ParsedPrompt(
            bpm=87.0,
            genre="jazz",
            key="C"
        )
        
        arrangement = generate_arrangement_with_motifs(parsed, num_motifs=2)
        
        # All assignments should reference valid motif indices
        for assignment in arrangement.motif_assignments.values():
            assert 0 <= assignment.motif_index < len(arrangement.motifs)
    
    def test_generate_with_different_genres(self):
        """Test generation with different genres."""
        genres = ["trap", "jazz", "lofi", "boom_bap", "house", "rnb"]
        
        for genre in genres:
            parsed = ParsedPrompt(
                bpm=87.0,
                genre=genre,
                key="C"
            )
            
            arrangement = generate_arrangement_with_motifs(parsed, num_motifs=2)
            
            # Should have motifs and assignments
            assert len(arrangement.motifs) > 0
            assert len(arrangement.motif_assignments) > 0


class TestGetSectionMotif:
    """Tests for get_section_motif function."""
    
    def test_get_section_motif_original(self):
        """Test retrieving original motif for a section."""
        parsed = ParsedPrompt(
            bpm=87.0,
            genre="trap_soul",
            key="C"
        )
        
        arrangement = generate_arrangement_with_motifs(parsed, num_motifs=2)
        
        # Get first section name
        if arrangement.motif_assignments:
            section_name = list(arrangement.motif_assignments.keys())[0]
            motif = get_section_motif(arrangement, section_name)
            
            # Should return a Motif
            assert motif is not None
            assert isinstance(motif, Motif)
    
    def test_get_section_motif_transformations(self):
        """Test retrieving motifs with different transformations."""
        parsed = ParsedPrompt(
            bpm=87.0,
            genre="jazz",
            key="C"
        )
        
        arrangement = generate_arrangement_with_motifs(parsed, num_motifs=2)
        
        # Test various transformations
        transformations_tested = set()
        
        for section_name, assignment in arrangement.motif_assignments.items():
            motif = get_section_motif(arrangement, section_name)
            
            assert motif is not None
            assert isinstance(motif, Motif)
            transformations_tested.add(assignment.transformation)
        
        # Should have tested at least some transformations
        assert len(transformations_tested) > 0
    
    def test_get_section_motif_invert(self):
        """Test inversion transformation."""
        parsed = ParsedPrompt(
            bpm=87.0,
            genre="trap_soul",
            key="C"
        )
        
        arrangement = generate_arrangement_with_motifs(parsed, num_motifs=1)
        
        # Manually add an inverted assignment
        arrangement.motif_assignments["test_invert"] = MotifAssignment(
            motif_index=0,
            transformation="invert",
            transform_params={"pivot": 0}
        )
        
        motif = get_section_motif(arrangement, "test_invert")
        
        assert motif is not None
        # Inverted motif should have different intervals
        base_motif = arrangement.motifs[0]
        # Check that name indicates transformation
        assert "inverted" in motif.name.lower()
    
    def test_get_section_motif_retrograde(self):
        """Test retrograde transformation."""
        parsed = ParsedPrompt(
            bpm=87.0,
            genre="trap_soul",
            key="C"
        )
        
        arrangement = generate_arrangement_with_motifs(parsed, num_motifs=1)
        
        # Manually add a retrograde assignment
        arrangement.motif_assignments["test_retrograde"] = MotifAssignment(
            motif_index=0,
            transformation="retrograde",
            transform_params=None
        )
        
        motif = get_section_motif(arrangement, "test_retrograde")
        
        assert motif is not None
        assert "retrograde" in motif.name.lower()
    
    def test_get_section_motif_augment(self):
        """Test augmentation transformation."""
        parsed = ParsedPrompt(
            bpm=87.0,
            genre="trap_soul",
            key="C"
        )
        
        arrangement = generate_arrangement_with_motifs(parsed, num_motifs=1)
        
        # Manually add an augmented assignment
        arrangement.motif_assignments["test_augment"] = MotifAssignment(
            motif_index=0,
            transformation="augment",
            transform_params={"factor": 2.0}
        )
        
        motif = get_section_motif(arrangement, "test_augment")
        
        assert motif is not None
        assert "augmented" in motif.name.lower()
    
    def test_get_section_motif_diminish(self):
        """Test diminution transformation."""
        parsed = ParsedPrompt(
            bpm=87.0,
            genre="trap_soul",
            key="C"
        )
        
        arrangement = generate_arrangement_with_motifs(parsed, num_motifs=1)
        
        # Manually add a diminished assignment
        arrangement.motif_assignments["test_diminish"] = MotifAssignment(
            motif_index=0,
            transformation="diminish",
            transform_params={"factor": 2.0}
        )
        
        motif = get_section_motif(arrangement, "test_diminish")
        
        assert motif is not None
        # Diminish uses augment internally with 1/factor
        assert "augmented" in motif.name.lower()
    
    def test_get_section_motif_sequence(self):
        """Test sequence transformation."""
        parsed = ParsedPrompt(
            bpm=87.0,
            genre="trap_soul",
            key="C"
        )
        
        arrangement = generate_arrangement_with_motifs(parsed, num_motifs=1)
        
        # Manually add a sequence assignment
        arrangement.motif_assignments["test_sequence"] = MotifAssignment(
            motif_index=0,
            transformation="sequence",
            transform_params={"steps": 3}
        )
        
        motif = get_section_motif(arrangement, "test_sequence")
        
        assert motif is not None
        assert "transposed" in motif.name.lower()
    
    def test_get_section_motif_invalid_section(self):
        """Test retrieving motif for non-existent section."""
        parsed = ParsedPrompt(
            bpm=87.0,
            genre="trap_soul",
            key="C"
        )
        
        arrangement = generate_arrangement_with_motifs(parsed, num_motifs=1)
        
        motif = get_section_motif(arrangement, "invalid_section_99")
        
        # Should return None for invalid section
        assert motif is None
    
    def test_get_section_motif_invalid_index(self):
        """Test retrieving motif with invalid motif index."""
        parsed = ParsedPrompt(
            bpm=87.0,
            genre="trap_soul",
            key="C"
        )
        
        arrangement = generate_arrangement_with_motifs(parsed, num_motifs=1)
        
        # Manually add assignment with invalid index
        arrangement.motif_assignments["test_invalid"] = MotifAssignment(
            motif_index=99,  # Invalid - only have 1 motif
            transformation="original"
        )
        
        motif = get_section_motif(arrangement, "test_invalid")
        
        # Should return None for invalid index
        assert motif is None


class TestGetDefaultMotifMapping:
    """Tests for get_default_motif_mapping function."""
    
    def test_get_mapping_for_known_genres(self):
        """Test getting motif mappings for known genres."""
        genres = ["pop", "hip_hop", "trap", "jazz", "classical", "lofi"]
        
        for genre in genres:
            mapping = get_default_motif_mapping(genre)
            
            # Should return a dict
            assert isinstance(mapping, dict)
            
            # Should have at least one mapping
            assert len(mapping) > 0
            
            # All values should be MotifAssignments
            for assignment in mapping.values():
                assert isinstance(assignment, MotifAssignment)
    
    def test_get_mapping_for_unknown_genre(self):
        """Test getting motif mapping for unknown genre."""
        mapping = get_default_motif_mapping("unknown_genre_xyz")
        
        # Should fall back to pop mapping
        pop_mapping = get_default_motif_mapping("pop")
        
        # Should have same keys
        assert set(mapping.keys()) == set(pop_mapping.keys())
    
    def test_genre_motif_mappings_structure(self):
        """Test that GENRE_MOTIF_MAPPINGS has correct structure."""
        # Should have mappings for at least 6 genres
        assert len(GENRE_MOTIF_MAPPINGS) >= 6
        
        required_genres = ["pop", "hip_hop", "trap", "jazz", "lofi", "boom_bap"]
        
        for genre in required_genres:
            assert genre in GENRE_MOTIF_MAPPINGS
            
            mapping = GENRE_MOTIF_MAPPINGS[genre]
            assert isinstance(mapping, dict)
            
            # Check structure of assignments
            for section_type, assignment in mapping.items():
                assert isinstance(section_type, str)
                assert isinstance(assignment, MotifAssignment)
                assert isinstance(assignment.motif_index, int)
                assert isinstance(assignment.transformation, str)
                assert assignment.motif_index >= 0


class TestGenreSpecificMappings:
    """Tests for genre-specific motif mapping behavior."""
    
    def test_classical_uses_complex_transformations(self):
        """Test that classical genre uses inversion, retrograde, augmentation."""
        mapping = get_default_motif_mapping("classical")
        
        transformations = [a.transformation for a in mapping.values()]
        
        # Classical should use complex transformations
        assert "invert" in transformations or "retrograde" in transformations or "augment" in transformations
    
    def test_pop_uses_simple_transformations(self):
        """Test that pop genre uses mostly original and sequence."""
        mapping = get_default_motif_mapping("pop")
        
        transformations = [a.transformation for a in mapping.values()]
        
        # Pop should be simpler
        assert "original" in transformations
        # May have sequence for variety
        assert "sequence" in transformations or "invert" in transformations
    
    def test_jazz_has_variety(self):
        """Test that jazz genre has varied transformations."""
        mapping = get_default_motif_mapping("jazz")
        
        transformations = set(a.transformation for a in mapping.values())
        
        # Jazz should have variety
        assert len(transformations) >= 2


class TestEdgeCases:
    """Tests for edge cases and error handling."""
    
    def test_empty_motif_list(self):
        """Test handling of arrangement with no motifs."""
        parsed = ParsedPrompt(
            bpm=87.0,
            genre="trap_soul",
            key="C"
        )
        
        arrangement = create_arrangement(parsed)
        # Manually create empty motif setup
        arrangement.motifs = []
        arrangement.motif_assignments = {"test": MotifAssignment(0, "original")}
        
        motif = get_section_motif(arrangement, "test")
        
        # Should return None when no motifs available
        assert motif is None
    
    def test_unknown_transformation(self):
        """Test handling of unknown transformation type."""
        parsed = ParsedPrompt(
            bpm=87.0,
            genre="trap_soul",
            key="C"
        )
        
        arrangement = generate_arrangement_with_motifs(parsed, num_motifs=1)
        
        # Add assignment with unknown transformation
        arrangement.motif_assignments["test_unknown"] = MotifAssignment(
            motif_index=0,
            transformation="unknown_transform_xyz"
        )
        
        motif = get_section_motif(arrangement, "test_unknown")
        
        # Should fall back to original
        assert motif is not None
        assert motif == arrangement.motifs[0]
    
    def test_section_naming_with_duplicates(self):
        """Test that sections with same type get unique names."""
        parsed = ParsedPrompt(
            bpm=87.0,
            genre="trap_soul",
            key="C"
        )
        
        arrangement = generate_arrangement_with_motifs(parsed, num_motifs=2)
        
        # Check for unique section names
        section_names = list(arrangement.motif_assignments.keys())
        
        # Should have unique names
        assert len(section_names) == len(set(section_names))
        
        # Should have numbered sections like "verse_1", "verse_2"
        verse_sections = [s for s in section_names if s.startswith("verse_")]
        if len(verse_sections) > 1:
            # Check they're numbered
            for i, section in enumerate(verse_sections):
                assert f"_{i+1}" in section


class TestIntegration:
    """Integration tests combining multiple features."""
    
    def test_full_workflow(self):
        """Test complete workflow from prompt to section motifs."""
        # Create prompt
        parsed = ParsedPrompt(
            bpm=87.0,
            genre="jazz",
            key="Eb",
            scale_type=ScaleType.MINOR
        )
        
        # Generate arrangement with motifs
        arrangement = generate_arrangement_with_motifs(
            parsed,
            num_motifs=2,
            seed=42
        )
        
        # Verify structure
        assert len(arrangement.sections) > 0
        assert len(arrangement.motifs) == 2
        assert len(arrangement.motif_assignments) > 0
        
        # Get motif for each section
        for section_name in arrangement.motif_assignments.keys():
            motif = get_section_motif(arrangement, section_name)
            assert motif is not None
            
            # Motif should be playable
            notes = motif.to_midi_notes(root_pitch=60, start_tick=0)
            assert len(notes) > 0
    
    def test_motif_metadata_export(self):
        """Test that motif metadata could be exported."""
        parsed = ParsedPrompt(
            bpm=87.0,
            genre="trap_soul",
            key="C"
        )
        
        arrangement = generate_arrangement_with_motifs(parsed, num_motifs=2)
        
        # Should be able to extract metadata
        metadata = {
            "num_motifs": len(arrangement.motifs),
            "motif_names": [m.name for m in arrangement.motifs],
            "assignments": {
                name: {
                    "motif_index": a.motif_index,
                    "transformation": a.transformation,
                    "params": a.transform_params
                }
                for name, a in arrangement.motif_assignments.items()
            }
        }
        
        # Metadata should be valid
        assert metadata["num_motifs"] == 2
        assert len(metadata["motif_names"]) == 2
        assert len(metadata["assignments"]) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
