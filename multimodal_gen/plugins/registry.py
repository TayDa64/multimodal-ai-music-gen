"""Plugin registry for dynamic plugin management."""
from typing import Dict, List, Optional, Any
import numpy as np

from .base import IInstrumentPlugin, PluginManifest


class PluginRegistry:
    """
    Registry for managing instrument plugins.
    
    Supports:
    - Registering plugins programmatically
    - Loading plugins from directories
    - Finding plugins by MIDI program
    - Enabling/disabling plugins
    """
    
    _instance: Optional['PluginRegistry'] = None
    
    def __init__(self) -> None:
        self._plugins: Dict[str, IInstrumentPlugin] = {}
        self._enabled: Dict[str, bool] = {}
        self._by_program: Dict[int, str] = {}  # program -> plugin_id
    
    @classmethod
    def get_instance(cls) -> 'PluginRegistry':
        """Get singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    @classmethod
    def reset_instance(cls) -> None:
        """Reset the singleton instance (mainly for testing)."""
        cls._instance = None
    
    def register(self, plugin: IInstrumentPlugin) -> bool:
        """
        Register a plugin.
        
        Args:
            plugin: Plugin instance to register
            
        Returns:
            True if registered successfully
        """
        plugin_id = plugin.manifest.id
        
        if plugin_id in self._plugins:
            print(f"Plugin {plugin_id} already registered")
            return False
        
        self._plugins[plugin_id] = plugin
        self._enabled[plugin_id] = True
        
        # Index by MIDI program
        for inst in plugin.manifest.instruments.values():
            self._by_program[inst.midi_program] = plugin_id
        
        return True
    
    def unregister(self, plugin_id: str) -> bool:
        """Unregister a plugin."""
        if plugin_id not in self._plugins:
            return False
        
        plugin = self._plugins[plugin_id]
        
        # Remove from program index
        for inst in plugin.manifest.instruments.values():
            if self._by_program.get(inst.midi_program) == plugin_id:
                del self._by_program[inst.midi_program]
        
        del self._plugins[plugin_id]
        del self._enabled[plugin_id]
        
        return True
    
    def enable(self, plugin_id: str, enabled: bool = True) -> None:
        """Enable or disable a plugin."""
        if plugin_id in self._enabled:
            self._enabled[plugin_id] = enabled
    
    def is_enabled(self, plugin_id: str) -> bool:
        """Check if a plugin is enabled."""
        return self._enabled.get(plugin_id, False)
    
    def get_plugin(self, plugin_id: str) -> Optional[IInstrumentPlugin]:
        """Get a plugin by ID."""
        if plugin_id in self._plugins and self._enabled.get(plugin_id, False):
            return self._plugins[plugin_id]
        return None
    
    def get_plugin_for_program(self, program: int) -> Optional[IInstrumentPlugin]:
        """Get the plugin that handles a MIDI program number."""
        plugin_id = self._by_program.get(program)
        if plugin_id and self._enabled.get(plugin_id, False):
            return self._plugins.get(plugin_id)
        return None
    
    def list_plugins(self) -> List[Dict[str, Any]]:
        """List all registered plugins."""
        return [
            {
                **plugin.get_info(),
                'enabled': self._enabled.get(plugin_id, False),
            }
            for plugin_id, plugin in self._plugins.items()
        ]
    
    def list_instruments(self) -> List[Dict[str, Any]]:
        """List all instruments across enabled plugins."""
        instruments: List[Dict[str, Any]] = []
        for plugin_id, plugin in self._plugins.items():
            if not self._enabled.get(plugin_id, False):
                continue
            for inst in plugin.list_instruments():
                instruments.append({
                    'id': inst.id,
                    'name': inst.name,
                    'display_name': inst.display_name,
                    'midi_program': inst.midi_program,
                    'category': inst.category,
                    'plugin': plugin_id,
                })
        return instruments
    
    def synthesize(
        self,
        program: int,
        pitch: int,
        duration_samples: int,
        velocity: float,
        sample_rate: int = 48000,
        **kwargs: Any
    ) -> Optional[np.ndarray]:
        """
        Synthesize a note using the appropriate plugin.
        
        Returns:
            Audio array or None if no plugin handles this program
        """
        plugin = self.get_plugin_for_program(program)
        if plugin is None:
            return None
        
        inst = plugin.get_instrument_for_program(program)
        if inst is None:
            return None
        
        return plugin.synthesize(
            inst.id,
            pitch,
            duration_samples,
            velocity,
            sample_rate,
            **kwargs
        )


def get_registry() -> PluginRegistry:
    """Get the global plugin registry."""
    return PluginRegistry.get_instance()
