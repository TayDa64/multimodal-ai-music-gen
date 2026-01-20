"""
Configuration loader for arrangement templates and section configs.

Provides centralized loading of YAML configuration files with caching
for efficient runtime performance. Supports hot-reloading for development.
"""

from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple, Union
import logging

# Optional YAML support - fallback gracefully if not available
try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False

logger = logging.getLogger(__name__)


class ConfigLoadError(Exception):
    """Raised when configuration loading fails."""
    pass


class ConfigLoader:
    """
    Loads arrangement configs from YAML/JSON files with caching.
    
    This class provides a unified interface for loading arrangement
    configuration files including section configs, motif mappings,
    and genre-specific arrangement templates.
    
    Attributes:
        config_dir: Base directory for configuration files
    """
    
    def __init__(self, config_dir: Optional[Path] = None):
        """
        Initialize the configuration loader.
        
        Args:
            config_dir: Base directory for config files. 
                       Defaults to ../configs relative to this module.
        """
        if config_dir is None:
            # Default to multimodal_gen/../configs
            self.config_dir = Path(__file__).parent.parent / "configs"
        else:
            self.config_dir = Path(config_dir)
        
        self._cache: Dict[str, Any] = {}
        self._template_cache: Dict[str, List[Dict[str, Any]]] = {}
        
    def _load_yaml(self, path: Path) -> Dict[str, Any]:
        """
        Load a YAML file and return its contents.
        
        Args:
            path: Path to the YAML file
            
        Returns:
            Dictionary with the parsed YAML content
            
        Raises:
            ConfigLoadError: If the file cannot be loaded or parsed
        """
        if not YAML_AVAILABLE:
            raise ConfigLoadError("PyYAML is not installed. Cannot load YAML configs.")
        
        if not path.exists():
            raise ConfigLoadError(f"Configuration file not found: {path}")
        
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f) or {}
        except yaml.YAMLError as e:
            raise ConfigLoadError(f"Failed to parse YAML file {path}: {e}")
        except Exception as e:
            raise ConfigLoadError(f"Failed to load configuration file {path}: {e}")
    
    def load_section_configs(self) -> Dict[str, Dict[str, Any]]:
        """
        Load section configurations from YAML.
        
        Returns:
            Dictionary mapping section type names to their configurations.
            Each config contains keys like: typical_bars, energy_level,
            drum_density, etc.
            
        Raises:
            ConfigLoadError: If the configuration cannot be loaded
        """
        cache_key = "section_configs"
        
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        config_path = self.config_dir / "arrangements" / "section_configs.yaml"
        
        try:
            data = self._load_yaml(config_path)
            self._cache[cache_key] = data
            logger.debug(f"Loaded section configs from {config_path}")
            return data
        except ConfigLoadError:
            raise
        except Exception as e:
            raise ConfigLoadError(f"Failed to load section configs: {e}")
    
    def load_arrangement_template(self, genre: str) -> List[Dict[str, Any]]:
        """
        Load arrangement template for a specific genre.
        
        Args:
            genre: Genre name (e.g., 'trap_soul', 'rnb', 'house')
            
        Returns:
            List of section dictionaries with 'type' and 'bars' keys.
            Each dict may also contain an optional 'label' key.
            
        Raises:
            ConfigLoadError: If the template cannot be loaded
        """
        if genre in self._template_cache:
            return self._template_cache[genre]
        
        template_path = self.config_dir / "arrangements" / "templates" / f"{genre}.yaml"
        
        try:
            data = self._load_yaml(template_path)
            sections = data.get("sections", [])
            
            if not sections:
                raise ConfigLoadError(f"No sections found in template for genre: {genre}")
            
            self._template_cache[genre] = sections
            logger.debug(f"Loaded arrangement template for {genre} from {template_path}")
            return sections
            
        except ConfigLoadError:
            raise
        except Exception as e:
            raise ConfigLoadError(f"Failed to load arrangement template for {genre}: {e}")
    
    def load_motif_mappings(self, genre: str) -> Dict[str, Dict[str, Any]]:
        """
        Load motif mappings for a specific genre.
        
        Args:
            genre: Genre name to load mappings for
            
        Returns:
            Dictionary mapping section names to motif assignments.
            Each assignment contains: motif_index, transformation, transform_params
            
        Raises:
            ConfigLoadError: If the mappings cannot be loaded
        """
        cache_key = "motif_mappings"
        
        if cache_key not in self._cache:
            config_path = self.config_dir / "arrangements" / "motif_mappings.yaml"
            try:
                data = self._load_yaml(config_path)
                self._cache[cache_key] = data
                logger.debug(f"Loaded motif mappings from {config_path}")
            except ConfigLoadError:
                raise
            except Exception as e:
                raise ConfigLoadError(f"Failed to load motif mappings: {e}")
        
        mappings = self._cache[cache_key]
        
        if genre in mappings:
            return mappings[genre]
        
        # Return default (pop) if genre not found
        if "pop" in mappings:
            logger.warning(f"No motif mappings for genre '{genre}', using 'pop' defaults")
            return mappings["pop"]
        
        return {}
    
    def load_all_motif_mappings(self) -> Dict[str, Dict[str, Dict[str, Any]]]:
        """
        Load all motif mappings for all genres.
        
        Returns:
            Dictionary mapping genre names to their section-motif mappings
            
        Raises:
            ConfigLoadError: If the mappings cannot be loaded
        """
        cache_key = "motif_mappings"
        
        if cache_key not in self._cache:
            config_path = self.config_dir / "arrangements" / "motif_mappings.yaml"
            try:
                data = self._load_yaml(config_path)
                self._cache[cache_key] = data
                logger.debug(f"Loaded all motif mappings from {config_path}")
            except ConfigLoadError:
                raise
            except Exception as e:
                raise ConfigLoadError(f"Failed to load motif mappings: {e}")
        
        return self._cache[cache_key]
    
    def get_available_templates(self) -> List[str]:
        """
        List all available template names.
        
        Returns:
            List of genre names that have templates available
        """
        templates_dir = self.config_dir / "arrangements" / "templates"
        
        if not templates_dir.exists():
            return []
        
        templates = []
        for path in templates_dir.glob("*.yaml"):
            templates.append(path.stem)
        
        return sorted(templates)
    
    def get_template_metadata(self, genre: str) -> Dict[str, Any]:
        """
        Get metadata for a specific template.
        
        Args:
            genre: Genre name
            
        Returns:
            Dictionary with template metadata (template_id, display_name, etc.)
            
        Raises:
            ConfigLoadError: If the template cannot be loaded
        """
        template_path = self.config_dir / "arrangements" / "templates" / f"{genre}.yaml"
        
        try:
            data = self._load_yaml(template_path)
            # Return everything except sections
            metadata = {k: v for k, v in data.items() if k != "sections"}
            return metadata
        except ConfigLoadError:
            raise
        except Exception as e:
            raise ConfigLoadError(f"Failed to load template metadata for {genre}: {e}")
    
    def has_template(self, genre: str) -> bool:
        """
        Check if a template exists for a genre.
        
        Args:
            genre: Genre name to check
            
        Returns:
            True if template file exists, False otherwise
        """
        template_path = self.config_dir / "arrangements" / "templates" / f"{genre}.yaml"
        return template_path.exists()
    
    def has_section_configs(self) -> bool:
        """
        Check if section configs file exists.
        
        Returns:
            True if section_configs.yaml exists, False otherwise
        """
        config_path = self.config_dir / "arrangements" / "section_configs.yaml"
        return config_path.exists()
    
    def has_motif_mappings(self) -> bool:
        """
        Check if motif mappings file exists.
        
        Returns:
            True if motif_mappings.yaml exists, False otherwise
        """
        config_path = self.config_dir / "arrangements" / "motif_mappings.yaml"
        return config_path.exists()
    
    def reload(self) -> None:
        """
        Clear all caches for hot-reloading.
        
        Call this method when configuration files have been modified
        and you want to reload them on next access.
        """
        self._cache.clear()
        self._template_cache.clear()
        logger.info("Configuration cache cleared")
    
    def is_available(self) -> bool:
        """
        Check if the configuration system is available.
        
        Returns:
            True if YAML support is available and config directory exists
        """
        return YAML_AVAILABLE and self.config_dir.exists()


# Module-level singleton for convenience
_default_loader: Optional[ConfigLoader] = None


def get_config_loader(config_dir: Optional[Path] = None) -> ConfigLoader:
    """
    Get the default ConfigLoader instance.
    
    Creates a singleton instance on first call. Subsequent calls
    return the same instance unless a different config_dir is specified.
    
    Args:
        config_dir: Optional custom config directory
        
    Returns:
        ConfigLoader instance
    """
    global _default_loader
    
    if config_dir is not None:
        # Return new loader with custom directory
        return ConfigLoader(config_dir)
    
    if _default_loader is None:
        _default_loader = ConfigLoader()
    
    return _default_loader
