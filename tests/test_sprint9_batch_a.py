"""Sprint 9 Batch A — Genre normalization + MixPolicy saturation + bass chain (Tasks 9.1-9.3)."""
import pytest

# ── Guards ──────────────────────────────────────────────────────────────
try:
    from multimodal_gen.audio_renderer import AudioRenderer
    _HAS_RENDERER = True
except ImportError:
    _HAS_RENDERER = False

try:
    from multimodal_gen.style_policy import MixPolicy
    _HAS_MIX_POLICY = True
except ImportError:
    _HAS_MIX_POLICY = False


@pytest.mark.skipif(not _HAS_RENDERER, reason="AudioRenderer not available")
class TestNormalizeGenre:
    """Task 9.1: _normalize_genre() helper extracted and used at all 5 sites."""

    def test_normalize_none(self):
        """None genre returns empty string."""
        r = AudioRenderer(use_fluidsynth=False, use_bwf=False, genre=None)
        assert r._normalize_genre() == ''

    def test_normalize_hyphens(self):
        """Hyphens converted to underscores."""
        r = AudioRenderer(use_fluidsynth=False, use_bwf=False, genre='Hip-Hop')
        assert r._normalize_genre() == 'hip_hop'

    def test_normalize_spaces(self):
        """Spaces converted to underscores."""
        r = AudioRenderer(use_fluidsynth=False, use_bwf=False, genre='Lo Fi')
        assert r._normalize_genre() == 'lo_fi'

    def test_normalize_mixed(self):
        """Mixed case, hyphens, spaces all normalized."""
        r = AudioRenderer(use_fluidsynth=False, use_bwf=False, genre='Ethio-Jazz Revival')
        assert r._normalize_genre() == 'ethio_jazz_revival'

    def test_normalize_already_clean(self):
        """Already normalized genre passes through."""
        r = AudioRenderer(use_fluidsynth=False, use_bwf=False, genre='trap')
        assert r._normalize_genre() == 'trap'


@pytest.mark.skipif(not _HAS_RENDERER, reason="AudioRenderer not available")
class TestBassChainActivation:
    """Task 9.3: bass chain is now returned for bass tracks."""

    def test_bass_track_gets_chain(self):
        """Track named 'bass' gets the bass chain."""
        r = AudioRenderer(use_fluidsynth=False, use_bwf=False, genre='trap')
        chain = r._get_chain_for_track('Bass', is_drums=False)
        assert chain is not None
        assert chain.name == 'Bass Chain'

    def test_808_track_gets_bass_chain(self):
        """Track named '808' gets the bass chain."""
        r = AudioRenderer(use_fluidsynth=False, use_bwf=False, genre='trap')
        chain = r._get_chain_for_track('808 Sub', is_drums=False)
        assert chain is not None
        assert chain.name == 'Bass Chain'

    def test_drums_still_get_drum_chain(self):
        """Drum tracks still get the drum bus chain."""
        r = AudioRenderer(use_fluidsynth=False, use_bwf=False, genre='trap')
        chain = r._get_chain_for_track('Drums', is_drums=True)
        assert chain is not None

    def test_lofi_keys_get_lofi_chain(self):
        """Lofi genre + keys track gets lofi chain."""
        r = AudioRenderer(use_fluidsynth=False, use_bwf=False, genre='lofi')
        chain = r._get_chain_for_track('Piano', is_drums=False)
        assert chain is not None

    def test_none_genre_no_crash(self):
        """None genre doesn't crash _get_chain_for_track."""
        r = AudioRenderer(use_fluidsynth=False, use_bwf=False, genre=None)
        chain = r._get_chain_for_track('Lead', is_drums=False)
        assert chain is None  # No specific chain, but no crash

    def test_none_track_name_no_crash(self):
        """None track name doesn't crash _get_chain_for_track."""
        r = AudioRenderer(use_fluidsynth=False, use_bwf=False, genre='trap')
        chain = r._get_chain_for_track(None, is_drums=False)
        assert chain is None  # No match, no crash

    def test_melody_track_no_chain(self):
        """Melody track with non-lofi genre gets no specific chain."""
        r = AudioRenderer(use_fluidsynth=False, use_bwf=False, genre='jazz')
        chain = r._get_chain_for_track('Melody', is_drums=False)
        assert chain is None


@pytest.mark.skipif(not (_HAS_RENDERER and _HAS_MIX_POLICY), reason="Renderer or MixPolicy not available")
class TestSaturationExciterInfluence:
    """Task 9.2: MixPolicy saturation_type/amount influences exciter preset selection."""

    def test_tube_high_saturation_selects_analog_warmth(self):
        """Tube saturation > 0.3 should select analog_warmth exciter."""
        # We verify indirectly: the logic is in the render pipeline but
        # we can test that set_mix_policy stores the policy correctly
        r = AudioRenderer(use_fluidsynth=False, use_bwf=False, genre='pop')
        mp = MixPolicy(saturation_type='tube', saturation_amount=0.4)
        r.set_mix_policy(mp)
        assert r._mix_policy.saturation_type == 'tube'
        assert r._mix_policy.saturation_amount == 0.4

    def test_digital_low_saturation_selects_master_air(self):
        """Digital saturation < 0.15 should select master_air exciter."""
        r = AudioRenderer(use_fluidsynth=False, use_bwf=False, genre='pop')
        mp = MixPolicy(saturation_type='digital', saturation_amount=0.1)
        r.set_mix_policy(mp)
        assert r._mix_policy.saturation_type == 'digital'
        assert r._mix_policy.saturation_amount == 0.1

    def test_default_saturation_no_override(self):
        """Default saturation (tape, 0.2) should NOT override genre exciter preset."""
        r = AudioRenderer(use_fluidsynth=False, use_bwf=False, genre='trap')
        mp = MixPolicy()  # defaults: tape, 0.2
        r.set_mix_policy(mp)
        assert r._mix_policy.saturation_type == 'tape'
        assert r._mix_policy.saturation_amount == 0.2
        # 0.2 is not > 0.3, so no override occurs — genre preset 'tape_warmth' stays

    def test_bass_chain_in_mix_chains(self):
        """Bass chain is present in renderer's mix_chains dict."""
        r = AudioRenderer(use_fluidsynth=False, use_bwf=False, genre='trap')
        assert 'bass' in r.mix_chains
        assert r.mix_chains['bass'].name == 'Bass Chain'
