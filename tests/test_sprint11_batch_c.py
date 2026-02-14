"""Sprint 11 Batch C — Dead module flags + midi_generator logging (Tasks 11.7-11.8)."""
import pytest


class TestDeadModuleFlags:
    """Task 11.7: Dead modules archived to _deprecated/ directory."""

    def test_spatial_audio_archived(self):
        """spatial_audio.py moved to _deprecated/ and has UNREFERENCED notice."""
        import multimodal_gen._deprecated.spatial_audio as mod
        assert "[UNREFERENCED]" in (mod.__doc__ or "")

    def test_instrument_registry_archived(self):
        """instrument_registry.py moved to _deprecated/ and has UNREFERENCED notice."""
        import multimodal_gen._deprecated.instrument_registry as mod
        assert "[UNREFERENCED]" in (mod.__doc__ or "")

    def test_instrument_index_archived(self):
        """instrument_index.py moved to _deprecated/ and has UNREFERENCED notice."""
        import multimodal_gen._deprecated.instrument_index as mod
        assert "[UNREFERENCED]" in (mod.__doc__ or "")


class TestMidiGeneratorLogging:
    """Task 11.8: midi_generator has logging for silent except blocks."""

    def test_midi_generator_has_logger(self):
        """midi_generator module has a logger configured."""
        import multimodal_gen.midi_generator as mod
        assert hasattr(mod, '_midi_logger')

    def test_logger_is_proper_type(self):
        """Logger is a standard logging.Logger instance."""
        import logging
        import multimodal_gen.midi_generator as mod
        assert isinstance(mod._midi_logger, logging.Logger)
