"""Plugin loader for discovering and loading plugins."""
from typing import List, Optional
from pathlib import Path
import importlib
import importlib.util
import sys
import json

from .base import IInstrumentPlugin
from .registry import get_registry


def load_builtin_plugins() -> List[str]:
    """
    Load all built-in plugins.
    
    Returns:
        List of loaded plugin IDs
    """
    loaded: List[str] = []
    
    # Ethiopian plugin
    try:
        from .ethiopian.plugin import register as register_ethiopian
        plugin = register_ethiopian()
        loaded.append(plugin.manifest.id)
    except ImportError as e:
        print(f"Could not load Ethiopian plugin: {e}")
    
    # Add more built-in plugins here as they are created
    # Example:
    # try:
    #     from .west_african.plugin import register as register_west_african
    #     plugin = register_west_african()
    #     loaded.append(plugin.manifest.id)
    # except ImportError as e:
    #     print(f"Could not load West African plugin: {e}")
    
    return loaded


def load_external_plugin(plugin_dir: Path) -> Optional[str]:
    """
    Load an external plugin from a directory.
    
    The directory should contain:
    - manifest.json: Plugin manifest
    - plugin.py: Plugin implementation with IInstrumentPlugin subclass
    
    Args:
        plugin_dir: Path to plugin directory
        
    Returns:
        Plugin ID if loaded, None if failed
    """
    manifest_path = plugin_dir / "manifest.json"
    plugin_path = plugin_dir / "plugin.py"
    
    if not manifest_path.exists():
        print(f"No manifest.json in {plugin_dir}")
        return None
    
    if not plugin_path.exists():
        print(f"No plugin.py in {plugin_dir}")
        return None
    
    original_path: List[str] = []
    
    try:
        # Load manifest (for validation/logging)
        with open(manifest_path, 'r', encoding='utf-8') as f:
            manifest_data = json.load(f)
        
        plugin_name = manifest_data.get('id', plugin_dir.name)
        
        # Import plugin module dynamically
        original_path = sys.path.copy()
        sys.path.insert(0, str(plugin_dir.parent))
        
        # Use importlib.util for cleaner dynamic loading
        spec = importlib.util.spec_from_file_location(
            f"external_plugin_{plugin_name}",
            plugin_path
        )
        
        if spec is None or spec.loader is None:
            print(f"Could not create module spec for {plugin_path}")
            return None
        
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        
        # Find plugin class
        for name in dir(module):
            obj = getattr(module, name)
            if (isinstance(obj, type) and 
                issubclass(obj, IInstrumentPlugin) and 
                obj is not IInstrumentPlugin):
                
                # Instantiate and register
                plugin = obj()
                get_registry().register(plugin)
                print(f"Loaded external plugin: {plugin.manifest.name}")
                return plugin.manifest.id
        
        print(f"No IInstrumentPlugin subclass found in {plugin_path}")
        return None
        
    except json.JSONDecodeError as e:
        print(f"Invalid manifest.json in {plugin_dir}: {e}")
        return None
    except Exception as e:
        print(f"Error loading plugin from {plugin_dir}: {e}")
        return None
    finally:
        # Restore sys.path
        if original_path:
            sys.path = original_path


def scan_plugins(plugins_dir: Path) -> List[str]:
    """
    Scan a directory for plugins and load them.
    
    Each subdirectory in plugins_dir that contains a manifest.json
    and plugin.py will be loaded as a plugin.
    
    Args:
        plugins_dir: Directory containing plugin subdirectories
        
    Returns:
        List of loaded plugin IDs
    """
    loaded: List[str] = []
    
    if not plugins_dir.exists():
        print(f"Plugins directory does not exist: {plugins_dir}")
        return loaded
    
    if not plugins_dir.is_dir():
        print(f"Not a directory: {plugins_dir}")
        return loaded
    
    for item in plugins_dir.iterdir():
        if item.is_dir() and not item.name.startswith('.') and not item.name.startswith('__'):
            plugin_id = load_external_plugin(item)
            if plugin_id:
                loaded.append(plugin_id)
    
    return loaded


def discover_and_load_all(
    external_dirs: Optional[List[Path]] = None,
    load_builtins: bool = True
) -> List[str]:
    """
    Discover and load all plugins (built-in and external).
    
    Args:
        external_dirs: List of directories to scan for external plugins
        load_builtins: Whether to load built-in plugins
        
    Returns:
        List of all loaded plugin IDs
    """
    loaded: List[str] = []
    
    # Load built-in plugins first
    if load_builtins:
        loaded.extend(load_builtin_plugins())
    
    # Scan external directories
    if external_dirs:
        for ext_dir in external_dirs:
            loaded.extend(scan_plugins(ext_dir))
    
    return loaded
