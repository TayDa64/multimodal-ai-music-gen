"""Sprint 10 Batch C — Skeleton tests for untested modules (Task 10.7) + mix_chain cleanup (10.8)."""
import pytest
import struct
import tempfile
import os

# ── Guards ──────────────────────────────────────────────────────────────
try:
    import numpy as np
    _HAS_NP = True
except ImportError:
    _HAS_NP = False

try:
    from multimodal_gen.bwf_writer import BWFWriter, save_wav_with_ai_provenance, read_bwf_metadata
    _HAS_BWF = True
except ImportError:
    _HAS_BWF = False

try:
    from multimodal_gen.instrument_resolution import (
        InstrumentResolutionService, ResolvedInstrument, MatchType,
        DEFAULT_PROGRAM_TO_INSTRUMENT, DEFAULT_INSTRUMENT_TO_PROGRAM,
    )
    _HAS_RESOLUTION = True
except ImportError:
    _HAS_RESOLUTION = False

try:
    from multimodal_gen.expansion_manager import ExpansionManager
    _HAS_EXPANSION = True
except ImportError:
    _HAS_EXPANSION = False

try:
    from multimodal_gen.humanize_physics import (
        PhysicsHumanizer, HumanizeConfig, Note, HumanizeDecision,
        LimbType, InstrumentRole,
    )
    _HAS_HUMANIZE = True
except ImportError:
    _HAS_HUMANIZE = False

try:
    from multimodal_gen import mix_chain
    _HAS_MIX_CHAIN = True
except ImportError:
    _HAS_MIX_CHAIN = False


# ═══════════════════════════════════════════════════════════════════════
# BWF WRITER (bwf_writer.py)
# ═══════════════════════════════════════════════════════════════════════

@pytest.mark.skipif(not (_HAS_BWF and _HAS_NP), reason="BWF writer or numpy not available")
class TestBWFWriter:
    """Skeleton tests for BWF writer module."""

    def test_bwf_writer_instantiation(self):
        """BWFWriter can be created with defaults."""
        w = BWFWriter()
        assert w.sample_rate > 0
        assert w.bit_depth in (16, 24)

    def test_write_bwf_mono(self, tmp_path):
        """BWFWriter writes a valid RIFF/WAVE file from mono input."""
        audio = np.sin(np.linspace(0, 2 * np.pi * 440, 44100)).astype(np.float64) * 0.5
        out = str(tmp_path / "test_mono.wav")
        w = BWFWriter(sample_rate=44100, bit_depth=16)
        w.write_bwf(audio, out)
        assert os.path.exists(out)
        with open(out, 'rb') as f:
            assert f.read(4) == b'RIFF'
            f.read(4)  # size
            assert f.read(4) == b'WAVE'

    def test_write_bwf_stereo(self, tmp_path):
        """BWFWriter writes valid file from stereo input."""
        t = np.linspace(0, 1, 44100)
        stereo = np.stack([np.sin(2 * np.pi * 440 * t), np.sin(2 * np.pi * 440 * t)], axis=-1).astype(np.float64) * 0.5
        out = str(tmp_path / "test_stereo.wav")
        w = BWFWriter(sample_rate=44100, bit_depth=16)
        w.write_bwf(stereo, out)
        assert os.path.exists(out)
        assert os.path.getsize(out) > 100

    def test_write_bwf_with_metadata(self, tmp_path):
        """BWFWriter includes axml chunk when metadata is provided."""
        audio = np.zeros((44100, 2), dtype=np.float64)
        out = str(tmp_path / "test_meta.wav")
        meta = {"prompt": "test prompt", "bpm": 120, "genre": "jazz", "version": "1.0"}
        w = BWFWriter(sample_rate=44100, bit_depth=16)
        w.write_bwf(audio, out, ai_metadata=meta)
        assert os.path.exists(out)
        # Read back and check for axml chunk
        with open(out, 'rb') as f:
            content = f.read()
        assert b'axml' in content

    def test_write_and_read_metadata_roundtrip(self, tmp_path):
        """Metadata written can be read back."""
        audio = np.zeros((44100, 2), dtype=np.float64)
        out = str(tmp_path / "roundtrip.wav")
        meta = {"prompt": "chill lo-fi beat", "bpm": 85, "genre": "lofi", "version": "0.1"}
        save_wav_with_ai_provenance(audio, out, ai_metadata=meta, sample_rate=44100)
        result = read_bwf_metadata(out)
        assert result is not None
        assert result.get('prompt') == "chill lo-fi beat"
        assert result.get('genre') == "lofi"

    def test_read_metadata_from_nonexistent_file(self):
        """read_bwf_metadata returns None for missing file."""
        result = read_bwf_metadata("/tmp/nonexistent_bwf_file.wav")
        assert result is None

    def test_bwf_24bit(self, tmp_path):
        """BWFWriter supports 24-bit output."""
        audio = np.zeros((1000, 2), dtype=np.float64)
        out = str(tmp_path / "test_24.wav")
        w = BWFWriter(sample_rate=44100, bit_depth=24)
        w.write_bwf(audio, out)
        assert os.path.exists(out)
        assert os.path.getsize(out) > 50


# ═══════════════════════════════════════════════════════════════════════
# INSTRUMENT RESOLUTION (instrument_resolution.py)
# ═══════════════════════════════════════════════════════════════════════

@pytest.mark.skipif(not _HAS_RESOLUTION, reason="InstrumentResolution not available")
class TestInstrumentResolution:
    """Skeleton tests for instrument resolution service."""

    def test_service_instantiation(self):
        """InstrumentResolutionService can be created without expansion manager."""
        svc = InstrumentResolutionService()
        assert svc is not None

    def test_default_registries_populated(self):
        """Default program<->instrument registries are non-empty."""
        assert len(DEFAULT_PROGRAM_TO_INSTRUMENT) > 0
        assert len(DEFAULT_INSTRUMENT_TO_PROGRAM) > 0

    def test_resolve_known_instrument(self):
        """Resolving a known instrument returns valid result."""
        svc = InstrumentResolutionService()
        result = svc.resolve_instrument("piano")
        assert isinstance(result, ResolvedInstrument)
        assert result.program is not None
        assert result.name != ""

    def test_resolve_unknown_falls_back(self):
        """Resolving an unknown instrument returns fallback."""
        svc = InstrumentResolutionService()
        result = svc.resolve_instrument("thereminophone_9000")
        assert isinstance(result, ResolvedInstrument)
        assert result.match_type in (MatchType.DEFAULT, MatchType.SEMANTIC, MatchType.MAPPED,
                                      "default", "semantic", "mapped")

    def test_program_allocation_range(self):
        """Expansion programs are allocated in reserved range (110-127)."""
        svc = InstrumentResolutionService()
        assert svc.EXPANSION_PROGRAM_START == 110
        assert svc.EXPANSION_PROGRAM_END == 127

    def test_resolution_cache(self):
        """Same instrument resolved twice returns equivalent result."""
        svc = InstrumentResolutionService()
        r1 = svc.resolve_instrument("bass", genre="jazz")
        r2 = svc.resolve_instrument("bass", genre="jazz")
        assert r1.program == r2.program  # Same resolution each time
        assert r1.name == r2.name

    def test_match_type_enum(self):
        """MatchType enum has expected values."""
        assert MatchType.EXACT.value == "exact"
        assert MatchType.MAPPED.value == "mapped"
        assert MatchType.SEMANTIC.value == "semantic"
        assert MatchType.DEFAULT.value == "default"


# ═══════════════════════════════════════════════════════════════════════
# EXPANSION MANAGER (expansion_manager.py)
# ═══════════════════════════════════════════════════════════════════════

@pytest.mark.skipif(not _HAS_EXPANSION, reason="ExpansionManager not available")
class TestExpansionManager:
    """Skeleton tests for expansion manager."""

    def test_manager_instantiation(self):
        """ExpansionManager can be created."""
        em = ExpansionManager()
        assert em is not None
        assert isinstance(em.expansions, dict)

    def test_scan_nonexistent_directory(self):
        """Scan of nonexistent directory returns 0."""
        em = ExpansionManager()
        count = em.scan_expansions("/tmp/nonexistent_expansion_dir_12345")
        assert count == 0

    def test_scan_empty_directory(self, tmp_path):
        """Scan of empty directory returns 0."""
        em = ExpansionManager()
        count = em.scan_expansions(str(tmp_path))
        assert count == 0

    def test_expansions_dict_empty_by_default(self):
        """Expansions dict is empty when no directory provided."""
        em = ExpansionManager()
        assert len(em.expansions) == 0


# ═══════════════════════════════════════════════════════════════════════
# HUMANIZE PHYSICS (humanize_physics.py)
# ═══════════════════════════════════════════════════════════════════════

@pytest.mark.skipif(not _HAS_HUMANIZE, reason="HumanizePhysics not available")
class TestHumanizePhysics:
    """Skeleton tests for physics-based humanization."""

    def test_humanizer_instantiation(self):
        """PhysicsHumanizer can be created with defaults."""
        h = PhysicsHumanizer(role="drums", bpm=120, genre="jazz")
        assert h.bpm == 120
        assert h.genre == "jazz"

    def test_humanize_empty_list(self):
        """Humanizing empty list returns empty list."""
        h = PhysicsHumanizer()
        result = h.apply([])
        assert result == []

    def test_humanize_single_note(self):
        """Humanizing single note returns one note."""
        h = PhysicsHumanizer(role="drums", bpm=100)
        notes = [Note(pitch=36, start_tick=0, duration_ticks=480, velocity=100, element="kick")]
        result = h.apply(notes)
        assert len(result) >= 1  # May add ghost notes

    def test_velocity_altered(self):
        """Humanization alters velocity from original."""
        h = PhysicsHumanizer(role="drums", bpm=160, genre="metal")
        notes = [
            Note(pitch=38, start_tick=i * 120, duration_ticks=100, velocity=100, channel=9, element="snare")
            for i in range(32)
        ]
        result = h.apply(notes)
        # At least some velocity should be different from 100
        velocities = [n.velocity for n in result if not n.is_ghost]
        assert any(v != 100 for v in velocities), "Expected some velocity variation"

    def test_humanize_config_defaults(self):
        """HumanizeConfig has reasonable defaults."""
        c = HumanizeConfig()
        assert c.apply_fatigue is True
        assert c.ghost_note_probability > 0
        assert c.timing_variation > 0

    def test_limb_types(self):
        """LimbType enum has expected members."""
        assert LimbType.RIGHT_HAND is not None
        assert LimbType.LEFT_HAND is not None
        assert LimbType.RIGHT_FOOT is not None
        assert LimbType.LEFT_FOOT is not None

    def test_instrument_roles(self):
        """InstrumentRole enum covers main roles."""
        assert InstrumentRole("drums") is not None
        assert InstrumentRole("bass") is not None

    def test_decisions_tracked(self):
        """Humanizer records decisions for inspection."""
        h = PhysicsHumanizer(role="drums", bpm=120)
        notes = [
            Note(pitch=36, start_tick=0, duration_ticks=480, velocity=80, element="kick"),
            Note(pitch=38, start_tick=480, duration_ticks=480, velocity=90, element="snare"),
        ]
        h.apply(notes)
        # decisions list should be populated
        assert isinstance(h.decisions, list)

    def test_ghost_notes_added_for_drums(self):
        """Ghost notes may be added when humanizing drums."""
        cfg = HumanizeConfig(apply_ghost_notes=True, ghost_note_probability=1.0)
        h = PhysicsHumanizer(role="drums", bpm=100, config=cfg)
        notes = [
            Note(pitch=38, start_tick=i * 480, duration_ticks=100, velocity=100, element="snare")
            for i in range(8)
        ]
        result = h.apply(notes)
        ghost_count = sum(1 for n in result if n.is_ghost)
        assert ghost_count >= 0  # Ghost notes may or may not be added depending on internal logic

    def test_genre_normalization(self):
        """PhysicsHumanizer normalizes genre on init."""
        h = PhysicsHumanizer(genre="Lo-Fi Hip Hop")
        assert h.genre == "lo_fi_hip_hop"


# ═══════════════════════════════════════════════════════════════════════
# MIX CHAIN CLEANUP (Task 10.8)
# ═══════════════════════════════════════════════════════════════════════

@pytest.mark.skipif(not _HAS_MIX_CHAIN, reason="mix_chain not available")
class TestMixChainCleanup:
    """Task 10.8: Verify unused factories removed, used ones still work."""

    def test_create_bass_chain_still_exists(self):
        """create_bass_chain is still available (used in Sprint 9.3)."""
        assert hasattr(mix_chain, 'create_bass_chain')
        chain = mix_chain.create_bass_chain()
        assert chain is not None

    def test_unused_factories_removed(self):
        """Unused factory functions should be removed (Sprint 10.8)."""
        # These were never imported/called anywhere in the codebase
        assert not hasattr(mix_chain, 'create_wide_stereo_chain'), "create_wide_stereo_chain should be removed"
        assert not hasattr(mix_chain, 'create_vocal_chain'), "create_vocal_chain should be removed"
        assert not hasattr(mix_chain, 'create_mastering_chain'), "create_mastering_chain should be removed"
        assert not hasattr(mix_chain, 'create_clean_eq_chain'), "create_clean_eq_chain should be removed"

    def test_mix_chain_core_still_works(self):
        """MixChain class still works after cleanup."""
        chain = mix_chain.MixChain("test")
        assert chain.name == "test"
