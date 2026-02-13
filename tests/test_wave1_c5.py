"""Wave 1 Category C5: Polish & Presets tests."""
import pytest
from pathlib import Path


class TestPresetYAMLFiles:
    def test_presets_directory_exists(self):
        presets_dir = Path(__file__).parent.parent / "configs" / "presets"
        assert presets_dir.exists(), "configs/presets/ directory should exist"

    def test_at_least_10_presets(self):
        presets_dir = Path(__file__).parent.parent / "configs" / "presets"
        yaml_files = list(presets_dir.glob("*.yaml"))
        assert len(yaml_files) >= 10, f"Expected >=10 preset files, got {len(yaml_files)}"

    def test_each_preset_has_required_sections(self):
        """Each YAML preset must have name, timing, dynamics, mix sections."""
        try:
            import yaml
        except ImportError:
            pytest.skip("PyYAML not installed")
        presets_dir = Path(__file__).parent.parent / "configs" / "presets"
        required_keys = {"name", "timing", "dynamics", "mix"}
        for f in presets_dir.glob("*.yaml"):
            with open(f) as fh:
                data = yaml.safe_load(fh)
            missing = required_keys - set(data.keys())
            assert not missing, f"{f.name} missing sections: {missing}"

    def test_timing_values_valid(self):
        try:
            import yaml
        except ImportError:
            pytest.skip("PyYAML not installed")
        presets_dir = Path(__file__).parent.parent / "configs" / "presets"
        valid_feels = {"straight", "swing", "push", "laid_back", "drunk"}
        for f in presets_dir.glob("*.yaml"):
            with open(f) as fh:
                data = yaml.safe_load(fh)
            timing = data.get("timing", {})
            if "feel" in timing:
                assert timing["feel"] in valid_feels, f"{f.name}: invalid feel '{timing['feel']}'"
            if "swing_amount" in timing:
                assert 0.0 <= timing["swing_amount"] <= 1.0, f"{f.name}: swing out of range"


class TestPresetLoader:
    def test_import(self):
        from multimodal_gen.preset_loader import PresetLoader, load_preset, list_presets

    def test_list_presets(self):
        from multimodal_gen.preset_loader import list_presets
        presets = list_presets()
        assert len(presets) >= 10
        for p in presets:
            assert p.name
            assert p.category

    def test_load_preset_by_filename(self):
        from multimodal_gen.preset_loader import load_preset
        preset = load_preset("trap_atlanta")
        assert preset["name"] == "trap_atlanta"
        assert "timing" in preset
        assert "mix" in preset

    def test_load_preset_mix_section(self):
        from multimodal_gen.preset_loader import load_preset
        preset = load_preset("lofi_chill")
        mix = preset.get("mix", {})
        assert "warmth_target" in mix or "brightness_target" in mix

    def test_load_nonexistent_raises(self):
        from multimodal_gen.preset_loader import load_preset
        with pytest.raises(FileNotFoundError):
            load_preset("nonexistent_genre_xyz")

    def test_mastering_chain(self):
        from multimodal_gen.preset_loader import PresetLoader
        loader = PresetLoader()
        chain = loader.get_mastering_chain("trap_atlanta")
        assert "target_lufs" in chain
        assert isinstance(chain["target_lufs"], (int, float))

    def test_preset_cache(self):
        from multimodal_gen.preset_loader import PresetLoader
        loader = PresetLoader()
        p1 = loader.load_preset("boom_bap_classic")
        p2 = loader.load_preset("boom_bap_classic")
        assert p1 is p2  # Same object from cache

    def test_clear_cache(self):
        from multimodal_gen.preset_loader import PresetLoader
        loader = PresetLoader()
        loader.load_preset("house_deep")
        loader.clear_cache()
        assert len(loader._cache) == 0

    def test_all_presets_load_without_error(self):
        """Every YAML in configs/presets/ should load cleanly."""
        from multimodal_gen.preset_loader import PresetLoader
        loader = PresetLoader()
        presets = loader.list_available_presets()
        for p in presets:
            data = loader.load_preset(p.name)
            assert isinstance(data, dict)
            assert "name" in data
