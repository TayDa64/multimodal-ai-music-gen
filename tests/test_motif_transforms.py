"""Sprint 6: Motif transformation tests.

Verifies the new Motif methods added in Sprint 6.1:
    retrograde_inversion, fragment, ornament, displace, get_related_motifs
"""
import pytest
from multimodal_gen.motif_engine import Motif


class TestNewTransformations:
    @pytest.fixture
    def base_motif(self):
        return Motif(
            intervals=[0, 2, 4, 5, 7],
            rhythm=[1.0, 0.5, 0.5, 1.0, 1.0],
            name="test_motif",
        )

    # -- retrograde_inversion -----------------------------------------------

    def test_retrograde_inversion_length(self, base_motif):
        ri = base_motif.retrograde_inversion()
        assert len(ri.intervals) == len(base_motif.intervals)
        assert len(ri.rhythm) == len(base_motif.rhythm)

    def test_retrograde_inversion_differs(self, base_motif):
        ri = base_motif.retrograde_inversion()
        assert ri.intervals != list(base_motif.intervals)

    # -- fragment -----------------------------------------------------------

    def test_fragment_subset(self, base_motif):
        frag = base_motif.fragment(1, 3)
        assert len(frag.intervals) == 3
        assert frag.intervals == list(base_motif.intervals[1:4])
        assert frag.rhythm == list(base_motif.rhythm[1:4])

    def test_fragment_out_of_range_returns_single_note(self, base_motif):
        frag = base_motif.fragment(10, 5)  # start beyond length
        assert len(frag.intervals) >= 1

    def test_fragment_from_zero(self, base_motif):
        frag = base_motif.fragment(0, 2)
        assert frag.intervals == list(base_motif.intervals[:2])

    # -- ornament -----------------------------------------------------------

    def test_ornament_adds_notes(self, base_motif):
        orn = base_motif.ornament(density=1.0, seed=42)
        assert len(orn.intervals) >= len(base_motif.intervals)
        assert len(orn.intervals) == len(orn.rhythm)

    def test_ornament_preserves_some_original_pitches(self, base_motif):
        orn = base_motif.ornament(density=0.5, seed=42)
        orig_set = set(base_motif.intervals)
        overlap = orig_set & set(orn.intervals)
        assert len(overlap) > 0

    def test_ornament_zero_density_preserves_length(self, base_motif):
        orn = base_motif.ornament(density=0.0, seed=42)
        assert len(orn.intervals) == len(base_motif.intervals)

    # -- displace -----------------------------------------------------------

    def test_displace_shifts_timing(self, base_motif):
        disp = base_motif.displace(0.5)
        # Prepends a rest note
        assert len(disp.intervals) == len(base_motif.intervals) + 1
        assert disp.intervals[0] == 0  # Rest note
        assert disp.rhythm[0] == 0.5

    def test_displace_preserves_intervals(self, base_motif):
        disp = base_motif.displace(0.25)
        # Original intervals appear starting at index 1
        assert disp.intervals[1:] == list(base_motif.intervals)

    # -- get_related_motifs -------------------------------------------------

    def test_get_related_motifs_count(self, base_motif):
        related = base_motif.get_related_motifs(count=4, seed=42)
        assert len(related) == 4
        for m in related:
            assert isinstance(m, Motif)
            assert len(m.intervals) == len(m.rhythm)

    def test_get_related_motifs_differ_from_original(self, base_motif):
        related = base_motif.get_related_motifs(count=3, seed=42)
        for m in related:
            differs = (
                m.intervals != list(base_motif.intervals)
                or m.rhythm != list(base_motif.rhythm)
            )
            assert differs

    def test_get_related_motifs_deterministic(self, base_motif):
        r1 = base_motif.get_related_motifs(count=3, seed=99)
        r2 = base_motif.get_related_motifs(count=3, seed=99)
        for a, b in zip(r1, r2):
            assert a.intervals == b.intervals
            assert a.rhythm == b.rhythm

    # -- chainability -------------------------------------------------------

    def test_transform_chainable(self, base_motif):
        """Transformations should be chainable."""
        result = (
            base_motif
            .retrograde()
            .invert()
            .fragment(0, 3)
            .ornament(0.2, seed=42)
        )
        assert isinstance(result, Motif)
        assert len(result.intervals) == len(result.rhythm)

    # -- to_midi_notes on transformed motifs --------------------------------

    def test_to_midi_notes_on_fragment(self, base_motif):
        frag = base_motif.fragment(0, 3)
        # Returns (tick, dur, pitch, vel)
        notes = frag.to_midi_notes(root_pitch=60, start_tick=0)
        assert len(notes) >= 1
        for tick, dur, pitch, vel in notes:
            assert 0 <= pitch <= 127
            assert vel > 0

    # -- Bug-fix edge cases -------------------------------------------------

    def test_fragment_length_zero(self, base_motif):
        """fragment(0, 0) must return a single-note fallback, not the full motif."""
        result = base_motif.fragment(0, 0)
        assert len(result.intervals) <= 1

    def test_displace_negative_clamps(self, base_motif):
        """displace(-0.5) must clamp offset so all durations stay non-negative."""
        result = base_motif.displace(-0.5)
        assert all(d >= 0 for d in result.rhythm)
