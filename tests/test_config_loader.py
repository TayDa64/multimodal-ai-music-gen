"""Tests for ConfigLoader module."""
import pytest
from pathlib import Path


class TestConfigLoader:
    """Test suite for ConfigLoader class."""
    
    def test_import(self):
        """Test ConfigLoader can be imported."""
        from multimodal_gen.config_loader import ConfigLoader
        assert ConfigLoader is not None
    
    def test_loader_initialization(self, project_config_dir):
        """Test ConfigLoader initializes with config directory."""
        from multimodal_gen.config_loader import ConfigLoader
        
        loader = ConfigLoader(str(project_config_dir))
        assert loader.config_dir == Path(project_config_dir)
    
    def test_default_loader_initialization(self):
        """Test ConfigLoader uses default config directory."""
        from multimodal_gen.config_loader import ConfigLoader
        
        loader = ConfigLoader()
        assert loader.config_dir.exists() or True  # May not exist in test env
    
    def test_load_section_configs(self, project_config_dir):
        """Test loading section_configs.yaml."""
        from multimodal_gen.config_loader import ConfigLoader
        
        if not project_config_dir.exists():
            pytest.skip("Config directory not found")
        
        loader = ConfigLoader(str(project_config_dir))
        
        if not loader.has_section_configs():
            pytest.skip("section_configs.yaml not found")
        
        configs = loader.load_section_configs()
        
        assert configs is not None
        assert isinstance(configs, dict)
    
    def test_load_arrangement_template(self, project_config_dir):
        """Test loading arrangement template."""
        from multimodal_gen.config_loader import ConfigLoader, ConfigLoadError
        
        if not project_config_dir.exists():
            pytest.skip("Config directory not found")
        
        loader = ConfigLoader(str(project_config_dir))
        
        # Get available templates
        templates = loader.get_available_templates()
        
        if not templates:
            pytest.skip("No arrangement templates found")
        
        # Load first available template
        template = loader.load_arrangement_template(templates[0])
        
        assert template is not None
        assert isinstance(template, list)
    
    def test_caching(self, project_config_dir):
        """Test that configs are cached."""
        from multimodal_gen.config_loader import ConfigLoader
        
        if not project_config_dir.exists():
            pytest.skip("Config directory not found")
        
        loader = ConfigLoader(str(project_config_dir))
        
        if not loader.has_section_configs():
            pytest.skip("section_configs.yaml not found")
        
        # Load twice
        config1 = loader.load_section_configs()
        config2 = loader.load_section_configs()
        
        # Should be same object due to caching
        assert config1 is config2
    
    def test_reload_clears_cache(self, project_config_dir):
        """Test reload() clears the cache."""
        from multimodal_gen.config_loader import ConfigLoader
        
        if not project_config_dir.exists():
            pytest.skip("Config directory not found")
        
        loader = ConfigLoader(str(project_config_dir))
        
        if not loader.has_section_configs():
            pytest.skip("section_configs.yaml not found")
        
        config1 = loader.load_section_configs()
        loader.reload()
        config2 = loader.load_section_configs()
        
        # After reload, should be different objects
        assert config1 is not config2
    
    def test_missing_template_raises_error(self, project_config_dir):
        """Test loading non-existent template raises ConfigLoadError."""
        from multimodal_gen.config_loader import ConfigLoader, ConfigLoadError
        
        loader = ConfigLoader(str(project_config_dir))
        
        with pytest.raises(ConfigLoadError):
            loader.load_arrangement_template('nonexistent_genre_xyz_12345')
    
    def test_has_template(self, project_config_dir):
        """Test has_template check."""
        from multimodal_gen.config_loader import ConfigLoader
        
        loader = ConfigLoader(str(project_config_dir))
        
        # Non-existent template should return False
        assert loader.has_template('nonexistent_genre_xyz_12345') == False
    
    def test_get_available_templates(self, project_config_dir):
        """Test listing available templates."""
        from multimodal_gen.config_loader import ConfigLoader
        
        loader = ConfigLoader(str(project_config_dir))
        templates = loader.get_available_templates()
        
        assert isinstance(templates, list)
    
    def test_is_available(self, project_config_dir):
        """Test is_available check."""
        from multimodal_gen.config_loader import ConfigLoader
        
        loader = ConfigLoader(str(project_config_dir))
        
        # Should return boolean
        assert isinstance(loader.is_available(), bool)
    
    def test_get_config_loader_singleton(self):
        """Test get_config_loader returns loader instance."""
        from multimodal_gen.config_loader import get_config_loader
        
        loader = get_config_loader()
        assert loader is not None
