"""
Genre Strategy Pattern for drum generation.

This module provides a Strategy Pattern implementation for genre-specific
drum pattern generation, allowing the system to be extended with new genres
without modifying existing code (Open/Closed Principle).

Usage:
    from .strategies import StrategyRegistry
    
    strategy = StrategyRegistry.get_or_default(genre)
    drum_notes = strategy.generate_drums(section, parsed, tension)
"""

from .base import GenreStrategy, DrumConfig
from .registry import StrategyRegistry

__all__ = [
    'GenreStrategy',
    'DrumConfig', 
    'StrategyRegistry',
]
