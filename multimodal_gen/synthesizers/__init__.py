"""
Synthesizer Interface Package

Provides an abstraction layer for audio synthesis backends.
Enables swapping synth engines (FluidSynth, Procedural, VST, etc.)
without modifying the AudioRenderer.

Usage:
    from multimodal_gen.synthesizers import (
        ISynthesizer,
        SynthesizerFactory,
        SynthNote,
        SynthTrack,
        SynthResult,
    )
    
    # Get best available synthesizer
    synth = SynthesizerFactory.get_best_available(prefer_soundfont=True)
    
    # Or create specific synthesizer
    synth = SynthesizerFactory.create('procedural', genre='trap')
"""

from .base import (
    ISynthesizer,
    SynthNote,
    SynthTrack,
    SynthResult,
)
from .factory import SynthesizerFactory
from .fluidsynth_synth import FluidSynthSynthesizer
from .procedural_synth import ProceduralSynthesizer

__all__ = [
    # Base interface
    'ISynthesizer',
    'SynthNote',
    'SynthTrack',
    'SynthResult',
    # Factory
    'SynthesizerFactory',
    # Implementations
    'FluidSynthSynthesizer',
    'ProceduralSynthesizer',
]
