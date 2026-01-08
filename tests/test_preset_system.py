"""
Unit tests for Preset System

Tests preset loading, application, provenance tracking, and "no trap defaults" principles.
"""

import pytest
import sys
import json
import tempfile
import importlib.util
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import preset_system directly to avoid __init__.py import issues
spec = importlib.util.spec_from_file_location(
    "preset_system",
    Path(__file__).parent.parent / "multimodal_gen" / "preset_system.py"
)
preset_system = importlib.util.module_from_spec(spec)
spec.loader.exec_module(preset_system)

# Extract the classes and functions we need
PresetCategory = preset_system.PresetCategory
PresetValue = preset_system.PresetValue
PresetConfig = preset_system.PresetConfig
PresetManager = preset_system.PresetManager
GENRE_PRESETS = preset_system.GENRE_PRESETS
STYLE_PRESETS = preset_system.STYLE_PRESETS
PRODUCTION_PRESETS = preset_system.PRODUCTION_PRESETS
apply_genre_preset = preset_system.apply_genre_preset
get_preset_for_prompt = preset_system.get_preset_for_prompt
combine_presets = preset_system.combine_presets


class TestPresetValue:
    """Test PresetValue dataclass."""
    
    def test_preset_value_creation(self):
        """Test creating a PresetValue."""
        pv = PresetValue(value=0.5, source="preset:test", locked=False)
        assert pv.value == 0.5
        assert pv.source == "preset:test"
        assert pv.locked is False
    
    def test_preset_value_override(self):
        """Test overriding a PresetValue."""
        pv = PresetValue(value=0.5, source="preset:test", locked=False)
        new_pv = pv.override(0.7, "user")
        assert new_pv.value == 0.7
        assert new_pv.source == "user"
        assert new_pv.locked is True
        # Original should be unchanged
        assert pv.value == 0.5


class TestPresetConfig:
    """Test PresetConfig dataclass."""
    
    def test_preset_config_creation(self):
        """Test creating a preset config."""
        config = PresetConfig(
            name="test_preset",
            category=PresetCategory.GENRE,
            description="Test preset",
            swing_amount=0.5,
            humanize_amount=0.3
        )
        assert config.name == "test_preset"
        assert config.category == PresetCategory.GENRE
        assert config.swing_amount == 0.5
        assert config.humanize_amount == 0.3
        assert config.velocity_range is None  # Not set
    
    def test_get_non_none_fields(self):
        """Test getting only explicitly set fields."""
        config = PresetConfig(
            name="test",
            category=PresetCategory.GENRE,
            description="Test",
            swing_amount=0.5,
            humanize_amount=None,
            velocity_range=(60, 100)
        )
        fields = config.get_non_none_fields()
        assert "swing_amount" in fields
        assert "velocity_range" in fields
        assert "humanize_amount" not in fields
        assert "name" not in fields  # Metadata excluded
        assert "description" not in fields
    
    def test_merge_with(self):
        """Test merging two preset configs."""
        config1 = PresetConfig(
            name="preset1",
            category=PresetCategory.GENRE,
            description="First preset",
            swing_amount=0.5,
            humanize_amount=0.3,
            tags={"tag1", "tag2"}
        )
        config2 = PresetConfig(
            name="preset2",
            category=PresetCategory.STYLE,
            description="Second preset",
            humanize_amount=0.7,
            velocity_range=(50, 90),
            tags={"tag3"}
        )
        
        merged = config1.merge_with(config2)
        
        # Keeps original name/category
        assert merged.name == "preset1"
        assert merged.category == PresetCategory.GENRE
        
        # config2 values take precedence
        assert merged.humanize_amount == 0.7
        assert merged.velocity_range == (50, 90)
        
        # config1 values retained where config2 has None
        assert merged.swing_amount == 0.5
        
        # Tags merged
        assert "tag1" in merged.tags
        assert "tag2" in merged.tags
        assert "tag3" in merged.tags


class TestPresetManager:
    """Test PresetManager core functionality."""
    
    def test_manager_initialization(self):
        """Test manager loads built-in presets."""
        manager = PresetManager()
        assert len(manager.presets) > 0
        assert "hip_hop_boom_bap" in manager.presets
        assert "chill" in manager.presets
        assert "polished" in manager.presets
    
    def test_apply_preset(self):
        """Test applying a preset."""
        manager = PresetManager()
        result = manager.apply_preset("hip_hop_boom_bap")
        
        assert len(result) > 0
        assert "swing_amount" in result
        assert result["swing_amount"].value == 0.15
        assert result["swing_amount"].source == "preset:hip_hop_boom_bap"
        assert result["swing_amount"].locked is False
        assert manager.active_preset == "hip_hop_boom_bap"
    
    def test_apply_preset_not_found(self):
        """Test applying non-existent preset raises error."""
        manager = PresetManager()
        with pytest.raises(ValueError, match="not found"):
            manager.apply_preset("nonexistent_preset")
    
    def test_partial_preset_application(self):
        """Test partial preset application with only_fields."""
        manager = PresetManager()
        result = manager.apply_preset(
            "hip_hop_boom_bap",
            only_fields={"swing_amount", "humanize_amount"}
        )
        
        assert "swing_amount" in result
        assert "humanize_amount" in result
        # Should not include other fields from preset
        assert "velocity_range" not in result
    
    def test_exclude_fields(self):
        """Test preset application with exclude_fields."""
        manager = PresetManager()
        result = manager.apply_preset(
            "hip_hop_boom_bap",
            exclude_fields={"swing_amount"}
        )
        
        assert "swing_amount" not in result
        assert "humanize_amount" in result
    
    def test_override_value(self):
        """Test overriding a specific value."""
        manager = PresetManager()
        manager.apply_preset("hip_hop_boom_bap")
        
        # Override a value
        pv = manager.override_value("swing_amount", 0.8)
        assert pv.value == 0.8
        assert pv.source == "user"
        assert pv.locked is True
    
    def test_get_value(self):
        """Test getting current value."""
        manager = PresetManager()
        manager.apply_preset("hip_hop_boom_bap")
        
        value = manager.get_value("swing_amount")
        assert value == 0.15
        
        # Non-existent field returns default
        value = manager.get_value("nonexistent", default=0.5)
        assert value == 0.5
    
    def test_get_provenance(self):
        """Test getting value provenance."""
        manager = PresetManager()
        manager.apply_preset("hip_hop_boom_bap")
        
        assert manager.get_provenance("swing_amount") == "preset:hip_hop_boom_bap"
        
        manager.override_value("swing_amount", 0.9)
        assert manager.get_provenance("swing_amount") == "user"
        
        assert manager.get_provenance("nonexistent") == "default"
    
    def test_get_user_overrides(self):
        """Test getting only user-set values."""
        manager = PresetManager()
        manager.apply_preset("hip_hop_boom_bap")
        manager.override_value("swing_amount", 0.8)
        manager.override_value("velocity_range", (40, 100))
        
        overrides = manager.get_user_overrides()
        assert len(overrides) == 2
        assert overrides["swing_amount"] == 0.8
        assert overrides["velocity_range"] == (40, 100)
    
    def test_get_preset_values(self):
        """Test getting only preset values (not user-overridden)."""
        manager = PresetManager()
        manager.apply_preset("hip_hop_boom_bap")
        manager.override_value("swing_amount", 0.8)
        
        preset_values = manager.get_preset_values()
        # swing_amount should not be in preset values (it's user-overridden)
        assert "swing_amount" not in preset_values
        # Other preset values should be present
        assert "humanize_amount" in preset_values
    
    def test_reset_to_defaults(self):
        """Test resetting to defaults."""
        manager = PresetManager()
        manager.apply_preset("hip_hop_boom_bap")
        manager.override_value("swing_amount", 0.8)
        
        # Reset all
        manager.reset_to_defaults()
        assert len(manager.current_values) == 0
        assert manager.active_preset is None
    
    def test_reset_to_defaults_specific_fields(self):
        """Test resetting specific fields to defaults."""
        manager = PresetManager()
        manager.apply_preset("hip_hop_boom_bap")
        
        # Reset only swing_amount
        manager.reset_to_defaults(fields={"swing_amount"})
        assert "swing_amount" not in manager.current_values
        assert "humanize_amount" in manager.current_values
    
    def test_reset_to_preset(self):
        """Test resetting user overrides to preset values."""
        manager = PresetManager()
        manager.apply_preset("hip_hop_boom_bap")
        original_swing = manager.get_value("swing_amount")
        
        # Override a value
        manager.override_value("swing_amount", 0.9)
        assert manager.get_value("swing_amount") == 0.9
        
        # Reset to preset
        manager.reset_to_preset()
        assert manager.get_value("swing_amount") == original_swing
        assert manager.get_provenance("swing_amount") == "preset:hip_hop_boom_bap"
    
    def test_clear_preset(self):
        """Test clearing preset but keeping user overrides."""
        manager = PresetManager()
        manager.apply_preset("hip_hop_boom_bap")
        manager.override_value("swing_amount", 0.9)
        
        # Clear preset
        manager.clear_preset()
        
        # User override should remain
        assert manager.get_value("swing_amount") == 0.9
        assert manager.get_provenance("swing_amount") == "user"
        
        # Preset values should be gone
        assert "humanize_amount" not in manager.current_values
        assert manager.active_preset is None
    
    def test_list_presets(self):
        """Test listing all presets."""
        manager = PresetManager()
        presets = manager.list_presets()
        assert len(presets) > 0
    
    def test_list_presets_by_category(self):
        """Test filtering presets by category."""
        manager = PresetManager()
        genre_presets = manager.list_presets(category=PresetCategory.GENRE)
        assert all(p.category == PresetCategory.GENRE for p in genre_presets)
        assert len(genre_presets) >= 10
    
    def test_list_presets_by_tags(self):
        """Test filtering presets by tags."""
        manager = PresetManager()
        hip_hop_presets = manager.list_presets(tags={"hip_hop"})
        assert len(hip_hop_presets) >= 3  # boom_bap, trap, lofi
        assert all("hip_hop" in p.tags for p in hip_hop_presets)
    
    def test_get_preset(self):
        """Test getting a specific preset."""
        manager = PresetManager()
        preset = manager.get_preset("hip_hop_boom_bap")
        assert preset is not None
        assert preset.name == "hip_hop_boom_bap"
        
        # Non-existent preset
        preset = manager.get_preset("nonexistent")
        assert preset is None
    
    def test_create_preset_from_current(self):
        """Test creating a new preset from current values."""
        manager = PresetManager()
        manager.apply_preset("hip_hop_boom_bap")
        manager.override_value("swing_amount", 0.8)
        
        new_preset = manager.create_preset_from_current(
            name="my_custom_preset",
            description="My custom preset",
            category=PresetCategory.EXPERIMENTAL,
            tags={"custom", "test"}
        )
        
        assert new_preset.name == "my_custom_preset"
        assert new_preset.swing_amount == 0.8
        assert "my_custom_preset" in manager.presets
    
    def test_export_import_preset(self):
        """Test exporting and importing presets as JSON."""
        manager = PresetManager()
        
        # Export
        json_data = manager.export_preset("hip_hop_boom_bap")
        assert isinstance(json_data, str)
        data = json.loads(json_data)
        assert data["name"] == "hip_hop_boom_bap"
        assert "swing_amount" in data
        
        # Import
        manager2 = PresetManager()
        imported = manager2.import_preset(json_data)
        assert imported.name == "hip_hop_boom_bap"
        assert imported.swing_amount == 0.15
    
    def test_save_load_user_presets(self):
        """Test saving and loading user presets to/from file."""
        manager = PresetManager()
        manager.create_preset_from_current(
            name="user_preset_1",
            description="User preset 1",
            category=PresetCategory.EXPERIMENTAL
        )
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            filepath = f.name
        
        try:
            # Save
            manager.save_user_presets(filepath)
            
            # Load in new manager
            manager2 = PresetManager()
            manager2.load_user_presets(filepath)
            
            # Should have the user preset
            assert "user_preset_1" in manager2.presets
        finally:
            Path(filepath).unlink()


class TestNoTrapDefaults:
    """Test that presets don't create trap defaults."""
    
    def test_user_override_persists_on_preset_reapply(self):
        """User overrides should not be lost when preset is reapplied."""
        manager = PresetManager()
        manager.apply_preset("hip_hop_boom_bap")
        manager.override_value("swing_amount", 0.9)
        
        # Reapply the same preset
        manager.apply_preset("hip_hop_boom_bap")
        
        # User override should still be there
        assert manager.get_value("swing_amount") == 0.9
        assert manager.get_provenance("swing_amount") == "user"
    
    def test_partial_preset_doesnt_affect_unrelated_fields(self):
        """Applying partial preset shouldn't touch unrelated fields."""
        manager = PresetManager()
        manager.override_value("custom_field", "my_value")
        
        # Apply preset with only specific fields
        manager.apply_preset("hip_hop_boom_bap", only_fields={"swing_amount"})
        
        # Custom field should be untouched
        assert manager.get_value("custom_field") == "my_value"
    
    def test_none_values_dont_override_existing(self):
        """None values in preset shouldn't override existing values."""
        manager = PresetManager()
        
        # Set a value
        manager.override_value("motif_density", 0.8)
        
        # Apply a preset that has motif_density=None
        manager.apply_preset("chill")  # Style preset with limited fields
        
        # Value should be unchanged (chill preset doesn't set motif_density)
        assert manager.get_value("motif_density") == 0.8
    
    def test_clear_preset_keeps_user_overrides(self):
        """Clearing preset should keep user overrides."""
        manager = PresetManager()
        manager.apply_preset("hip_hop_boom_bap")
        manager.override_value("swing_amount", 0.9)
        
        preset_value = manager.get_value("humanize_amount")
        
        # Clear preset
        manager.clear_preset()
        
        # User override kept
        assert manager.get_value("swing_amount") == 0.9
        
        # Preset value removed
        assert manager.get_value("humanize_amount") is None
    
    def test_reset_to_defaults_clears_everything(self):
        """Reset to defaults should clear all values."""
        manager = PresetManager()
        manager.apply_preset("hip_hop_boom_bap")
        manager.override_value("swing_amount", 0.9)
        
        manager.reset_to_defaults()
        
        assert len(manager.current_values) == 0
        assert manager.active_preset is None
    
    def test_reset_to_preset_only_affects_preset_values(self):
        """Reset to preset should only reset user overrides, not new user values."""
        manager = PresetManager()
        manager.apply_preset("hip_hop_boom_bap")
        
        # Override a preset value
        manager.override_value("swing_amount", 0.9)
        
        # Add a new user value not in preset
        manager.override_value("custom_field", "custom_value")
        
        manager.reset_to_preset()
        
        # Preset value should be restored
        assert manager.get_value("swing_amount") == 0.15
        
        # Custom field should be removed (not in preset)
        assert manager.get_value("custom_field") is None


class TestBuiltinPresets:
    """Test built-in preset validity."""
    
    def test_all_genre_presets_load(self):
        """All genre presets should load correctly."""
        assert len(GENRE_PRESETS) >= 10
        for name, preset in GENRE_PRESETS.items():
            assert preset.name == name
            assert preset.category == PresetCategory.GENRE
            assert len(preset.description) > 0
            assert len(preset.tags) > 0
    
    def test_all_style_presets_load(self):
        """All style presets should load correctly."""
        assert len(STYLE_PRESETS) >= 5
        for name, preset in STYLE_PRESETS.items():
            assert preset.name == name
            assert preset.category == PresetCategory.STYLE
            assert len(preset.description) > 0
            assert len(preset.tags) > 0
    
    def test_all_production_presets_load(self):
        """All production presets should load correctly."""
        assert len(PRODUCTION_PRESETS) >= 3
        for name, preset in PRODUCTION_PRESETS.items():
            assert preset.name == name
            assert preset.category == PresetCategory.PRODUCTION
            assert len(preset.description) > 0
            assert len(preset.tags) > 0
    
    def test_preset_values_in_valid_ranges(self):
        """Preset values should be in valid ranges."""
        all_presets = {**GENRE_PRESETS, **STYLE_PRESETS, **PRODUCTION_PRESETS}
        
        for preset in all_presets.values():
            # Check float values are in 0-1 range
            if preset.swing_amount is not None:
                assert 0.0 <= preset.swing_amount <= 1.0
            if preset.humanize_amount is not None:
                assert 0.0 <= preset.humanize_amount <= 1.0
            if preset.tension_intensity is not None:
                assert 0.0 <= preset.tension_intensity <= 1.0
            
            # Check velocity_range is valid
            if preset.velocity_range is not None:
                min_vel, max_vel = preset.velocity_range
                assert 0 <= min_vel <= 127
                assert 0 <= max_vel <= 127
                assert min_vel < max_vel
    
    def test_required_genre_presets_exist(self):
        """Test that all required genre presets exist."""
        required = [
            "hip_hop_boom_bap", "hip_hop_trap", "hip_hop_lofi",
            "pop_modern", "pop_80s",
            "jazz_swing", "jazz_modal",
            "rock_classic", "rock_indie",
            "edm_house", "edm_techno",
            "rnb_neosoul",
            "funk_classic"
        ]
        for name in required:
            assert name in GENRE_PRESETS
    
    def test_required_style_presets_exist(self):
        """Test that all required style presets exist."""
        required = ["chill", "energetic", "aggressive", "dreamy", "groovy"]
        for name in required:
            assert name in STYLE_PRESETS
    
    def test_required_production_presets_exist(self):
        """Test that all required production presets exist."""
        required = ["demo_rough", "polished", "experimental"]
        for name in required:
            assert name in PRODUCTION_PRESETS


class TestPresetCombination:
    """Test combining multiple presets."""
    
    def test_combine_presets_basic(self):
        """Test combining genre, style, and production presets."""
        result = combine_presets(
            genre_preset="hip_hop_boom_bap",
            style_preset="chill",
            production_preset="polished"
        )
        
        assert len(result) > 0
        # Should have values from all three presets
        assert "swing_amount" in result
        assert "humanize_amount" in result
    
    def test_combine_presets_precedence(self):
        """Test that later presets override earlier ones."""
        manager = PresetManager()
        
        # boom_bap has humanize_amount=0.4
        # chill has humanize_amount=0.5
        # polished has humanize_amount=0.25
        
        result = combine_presets(
            genre_preset="hip_hop_boom_bap",
            style_preset="chill",
            production_preset="polished",
            manager=manager
        )
        
        # polished should win (applied last)
        assert result["humanize_amount"].value == 0.25
    
    def test_combine_presets_partial_style(self):
        """Test that style preset doesn't override unrelated genre fields."""
        manager = PresetManager()
        
        result = combine_presets(
            genre_preset="hip_hop_boom_bap",
            style_preset="chill",
            manager=manager
        )
        
        # boom_bap has swing_amount=0.15
        # chill doesn't have swing_amount
        # Should keep boom_bap's value
        assert result["swing_amount"].value == 0.15


class TestConvenienceFunctions:
    """Test convenience functions."""
    
    def test_apply_genre_preset(self):
        """Test quick genre preset application."""
        values = apply_genre_preset("hip_hop_boom_bap")
        assert "swing_amount" in values
        assert values["swing_amount"] == 0.15
    
    def test_get_preset_for_prompt_by_name(self):
        """Test getting preset from prompt with preset name."""
        preset = get_preset_for_prompt("I want hip hop boom bap style")
        assert preset is not None
        assert preset.name == "hip_hop_boom_bap"
    
    def test_get_preset_for_prompt_by_tag(self):
        """Test getting preset from prompt with tag."""
        preset = get_preset_for_prompt("Make it chill and relaxed")
        assert preset is not None
        assert "chill" in preset.tags
    
    def test_get_preset_for_prompt_no_match(self):
        """Test getting preset from prompt with no match."""
        preset = get_preset_for_prompt("Something completely random xyz123")
        # Might return None or a default
        # Just verify it doesn't crash
        assert preset is None or isinstance(preset, PresetConfig)


if __name__ == "__main__":
    # Run with pytest
    pytest.main([__file__, "-v"])
