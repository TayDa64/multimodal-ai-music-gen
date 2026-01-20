"""Factory for creating synthesizer instances."""
from typing import Optional, List, Type, Dict, Any

from .base import ISynthesizer


class SynthesizerFactory:
    """
    Factory for creating and managing synthesizer instances.
    
    Supports:
    - Creating synthesizers by name
    - Auto-detection of available synthesizers
    - Prioritized fallback selection
    - Custom synthesizer registration
    
    Usage:
        # Get best available synthesizer
        synth = SynthesizerFactory.get_best_available(prefer_soundfont=True)
        
        # Create specific synthesizer
        synth = SynthesizerFactory.create('fluidsynth', soundfont_path='/path/to/sf2')
        
        # Register custom synthesizer
        SynthesizerFactory.register('custom', CustomSynthesizer)
    """
    
    _registry: Dict[str, Type[ISynthesizer]] = {}
    
    @classmethod
    def register(cls, name: str, synth_class: Type[ISynthesizer]) -> None:
        """
        Register a synthesizer class.
        
        Args:
            name: Name to register under (case-insensitive)
            synth_class: ISynthesizer subclass
        """
        cls._registry[name.lower()] = synth_class
    
    @classmethod
    def unregister(cls, name: str) -> bool:
        """
        Unregister a synthesizer class.
        
        Args:
            name: Name to unregister (case-insensitive)
            
        Returns:
            True if removed, False if not found
        """
        name_lower = name.lower()
        if name_lower in cls._registry:
            del cls._registry[name_lower]
            return True
        return False
    
    @classmethod
    def create(cls, name: str, **kwargs) -> Optional[ISynthesizer]:
        """
        Create a synthesizer by name.
        
        Args:
            name: Synthesizer name (case-insensitive)
            **kwargs: Passed to synthesizer constructor
            
        Returns:
            ISynthesizer instance or None if not found
        """
        synth_class = cls._registry.get(name.lower())
        if synth_class:
            return synth_class(**kwargs)
        return None
    
    @classmethod
    def get_registered(cls) -> List[str]:
        """
        List all registered synthesizer names.
        
        Returns:
            List of registered names
        """
        return list(cls._registry.keys())
    
    @classmethod
    def get_available(cls) -> List[str]:
        """
        List names of available (installed/working) synthesizers.
        
        Returns:
            List of available synthesizer names
        """
        available = []
        for name, synth_class in cls._registry.items():
            try:
                instance = synth_class()
                if instance.is_available:
                    available.append(name)
            except Exception:
                pass
        return available
    
    @classmethod
    def get_all_info(cls) -> Dict[str, Dict[str, Any]]:
        """
        Get info for all registered synthesizers.
        
        Returns:
            Dict mapping name to synthesizer info
        """
        info = {}
        for name, synth_class in cls._registry.items():
            try:
                instance = synth_class()
                info[name] = instance.get_info()
            except Exception as e:
                info[name] = {
                    'name': name,
                    'available': False,
                    'error': str(e),
                }
        return info
    
    @classmethod
    def get_best_available(
        cls,
        prefer_soundfont: bool = True,
        **kwargs
    ) -> Optional[ISynthesizer]:
        """
        Get the best available synthesizer.
        
        Priority (if prefer_soundfont=True):
        1. FluidSynth (if available with soundfont)
        2. Procedural (always available)
        
        Priority (if prefer_soundfont=False):
        1. Procedural
        2. FluidSynth
        
        Args:
            prefer_soundfont: Prefer FluidSynth if available
            **kwargs: Passed to synthesizer constructor
            
        Returns:
            Best available ISynthesizer instance
        """
        if prefer_soundfont:
            # Try FluidSynth first
            fluid = cls.create('fluidsynth', **kwargs)
            if fluid and fluid.is_available:
                # Also check if soundfont is available
                soundfont_path = kwargs.get('soundfont_path')
                if soundfont_path or fluid.get_capabilities().get('soundfonts', False):
                    return fluid
        
        # Try Procedural (always available)
        procedural = cls.create('procedural', **kwargs)
        if procedural and procedural.is_available:
            return procedural
        
        # If prefer_soundfont is False but Procedural somehow unavailable,
        # fall back to FluidSynth
        if not prefer_soundfont:
            fluid = cls.create('fluidsynth', **kwargs)
            if fluid and fluid.is_available:
                return fluid
        
        # Return first available as last resort
        for name in cls._registry:
            synth = cls.create(name, **kwargs)
            if synth and synth.is_available:
                return synth
        
        return None


# =============================================================================
# Register built-in synthesizers
# =============================================================================

def _register_builtins():
    """Register built-in synthesizer implementations."""
    from .fluidsynth_synth import FluidSynthSynthesizer
    from .procedural_synth import ProceduralSynthesizer
    
    SynthesizerFactory.register('fluidsynth', FluidSynthSynthesizer)
    SynthesizerFactory.register('procedural', ProceduralSynthesizer)


# Auto-register on import
_register_builtins()
