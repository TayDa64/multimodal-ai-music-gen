"""Plugin-based synthesizer adapter — bridges PluginRegistry to ISynthesizer interface."""
from typing import List, Dict, Optional, Any
import numpy as np

try:
    from .base import ISynthesizer, SynthNote, SynthResult
    _HAS_SYNTH_BASE = True
except ImportError:
    _HAS_SYNTH_BASE = False

try:
    from ..plugins.registry import PluginRegistry
    _HAS_PLUGINS = True
except ImportError:
    _HAS_PLUGINS = False


class PluginSynthesizer(ISynthesizer if _HAS_SYNTH_BASE else object):  # type: ignore[misc]
    """ISynthesizer adapter that delegates to registered instrument plugins.

    Lower-priority synthesizer that checks the PluginRegistry for a plugin
    matching the requested MIDI program number.  Falls back gracefully
    (returns silence) when no plugin is registered.
    """

    def __init__(self) -> None:
        self._registry = PluginRegistry.get_instance() if _HAS_PLUGINS else None

    # -- ISynthesizer interface ------------------------------------------------

    @property
    def name(self) -> str:
        return "plugin_synthesizer"

    @property
    def is_available(self) -> bool:
        return _HAS_PLUGINS and self._registry is not None

    def render_notes(
        self,
        notes: List['SynthNote'],
        total_samples: int = 0,
        is_drums: bool = False,
        sample_rate: int = 48000,
    ) -> np.ndarray:
        """Render notes using registered plugins.

        Iterates notes and delegates each to `PluginRegistry.synthesize`.
        Notes whose program has no matching plugin produce silence.
        """
        if not self._registry or not notes:
            return np.zeros(max(total_samples, 1), dtype=np.float32)

        # Determine output length
        if total_samples <= 0 and notes:
            total_samples = max(n.start_sample + n.duration_samples for n in notes)
        out = np.zeros(max(total_samples, 1), dtype=np.float32)

        for note in notes:
            audio = self._registry.synthesize(
                program=note.program,
                pitch=note.pitch,
                duration_samples=note.duration_samples,
                velocity=note.velocity,
                sample_rate=sample_rate,
            )
            if audio is not None:
                end = min(note.start_sample + len(audio), len(out))
                seg_len = end - note.start_sample
                if seg_len > 0:
                    out[note.start_sample:end] += audio[:seg_len]

        return out

    def get_capabilities(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "has_plugins": _HAS_PLUGINS,
            "registered_count": (
                len(self._registry._plugins) if self._registry else 0
            ),
            "render_midi_file": False,
            "render_notes": True,
            "drums": True,
            "soundfonts": False,
            "intelligent_selection": False,
        }

    def configure(self, **kwargs: Any) -> None:
        """No-op — plugin configuration is handled by the registry."""
        pass
