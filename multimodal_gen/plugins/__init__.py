"""
Instrument Plugins Package

Provides a plugin architecture for cultural instruments.
Enables dynamic loading of synthesized instruments without
modifying core audio_renderer.py code.

Usage:
    from multimodal_gen.plugins import get_registry, load_builtin_plugins
    
    # Load built-in plugins (Ethiopian, etc.)
    load_builtin_plugins()
    
    # Get registry
    registry = get_registry()
    
    # Synthesize using plugin
    audio = registry.synthesize(
        program=110,  # Krar
        pitch=60,
        duration_samples=48000,
        velocity=0.8,
    )
"""

from .base import (
    IInstrumentPlugin,
    PluginManifest,
    InstrumentDefinition,
)
from .registry import PluginRegistry, get_registry
from .loader import load_builtin_plugins, scan_plugins

__all__ = [
    'IInstrumentPlugin',
    'PluginManifest',
    'InstrumentDefinition',
    'PluginRegistry',
    'get_registry',
    'load_builtin_plugins',
    'scan_plugins',
]
