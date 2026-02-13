"""Sprint 10 Batch A — Genre normalization + drum panning + sub_bass_target (Tasks 10.1-10.3)."""
import pytest

# ── Guards ──────────────────────────────────────────────────────────────
try:
    from multimodal_gen.audio_renderer import AudioRenderer
    _HAS_RENDERER = True
except ImportError:
    _HAS_RENDERER = False

try:
    from multimodal_gen.style_policy import MixPolicy, compile_policy
    _HAS_POLICY = True
except ImportError:
    _HAS_POLICY = False

try:
    from multimodal_gen.arranger import Arranger
    _HAS_ARRANGER = True
except ImportError:
    _HAS_ARRANGER = False

try:
    from multimodal_gen.prompt_parser import PromptParser
    _HAS_PARSER = True
except ImportError:
    _HAS_PARSER = False


@pytest.mark.skipif(not (_HAS_ARRANGER and _HAS_PARSER),
                    reason="Arranger or PromptParser not available")
class TestArrangerGenreNormalization:
    """Task 10.1: Arranger normalizes genre for template lookup."""

    def test_hyphenated_genre_gets_template(self):
        """'Hip-Hop' should match arrangement template."""
        parser = PromptParser()
        parsed = parser.parse("hip-hop beat at 90 bpm")
        arr = Arranger(target_duration_seconds=30.0).create_arrangement(parsed)
        assert len(arr.sections) > 0

    def test_spaced_genre_gets_template(self):
        """'Lo Fi' should match lofi arrangement template."""
        parser = PromptParser()
        parsed = parser.parse("lo fi beat at 80 bpm")
        arr = Arranger(target_duration_seconds=30.0).create_arrangement(parsed)
        assert len(arr.sections) > 0

    def test_none_genre_no_crash(self):
        """None genre doesn't crash arranger."""
        parser = PromptParser()
        parsed = parser.parse("instrumental beat at 120 bpm")
        # parsed.genre might be None or empty for generic prompts
        arr = Arranger(target_duration_seconds=30.0).create_arrangement(parsed)
        assert len(arr.sections) > 0


@pytest.mark.skipif(not _HAS_POLICY, reason="StylePolicy not available")
class TestStylePolicyNoneGuard:
    """Task 10.1: StylePolicy compile methods handle None genre."""

    def test_compile_policy_with_none_genre(self):
        """compile_policy handles parsed prompt with None genre."""
        parser = PromptParser() if _HAS_PARSER else None
        if not parser:
            pytest.skip("PromptParser not available")
        parsed = parser.parse("beat at 120 bpm")
        # Force genre to None to test guard
        original_genre = parsed.genre
        parsed.genre = None
        try:
            ctx = compile_policy(parsed)
            assert ctx is not None
        except AttributeError:
            pytest.fail("compile_policy crashed on None genre")
        finally:
            parsed.genre = original_genre


@pytest.mark.skipif(not (_HAS_RENDERER and _HAS_POLICY),
                    reason="Renderer or MixPolicy not available")
class TestDrumPanning:
    """Task 10.2: MixPolicy drum panning influences _compute_pan()."""

    def test_drum_track_default_center(self):
        """Drums default to center (0.0) without mix policy."""
        r = AudioRenderer(use_fluidsynth=False, use_bwf=False, genre='trap')
        r._mix_policy = None
        assert r._compute_pan('Drums', is_drums=True, index=0) == 0.0

    def test_drum_track_with_hihat_pan(self):
        """Drums get subtle hihat_pan offset when MixPolicy has it."""
        r = AudioRenderer(use_fluidsynth=False, use_bwf=False, genre='trap')
        r.set_mix_policy(MixPolicy(hihat_pan=0.5))
        pan = r._compute_pan('Drums', is_drums=True, index=0)
        assert 0.1 <= pan <= 0.2  # 0.5 * 0.3 = 0.15

    def test_kick_track_gets_kick_pan(self):
        """Separate kick track gets kick_pan from MixPolicy."""
        r = AudioRenderer(use_fluidsynth=False, use_bwf=False, genre='trap')
        r.set_mix_policy(MixPolicy(kick_pan=-0.1))
        pan = r._compute_pan('Kick', is_drums=False, index=0)
        assert pan == pytest.approx(-0.1)

    def test_snare_track_gets_snare_pan(self):
        """Separate snare track gets snare_pan from MixPolicy."""
        r = AudioRenderer(use_fluidsynth=False, use_bwf=False, genre='jazz')
        r.set_mix_policy(MixPolicy(snare_pan=0.1))
        pan = r._compute_pan('Snare', is_drums=False, index=0)
        assert pan == pytest.approx(0.1)

    def test_hihat_track_gets_hihat_pan(self):
        """Separate hihat track gets hihat_pan from MixPolicy."""
        r = AudioRenderer(use_fluidsynth=False, use_bwf=False, genre='house')
        r.set_mix_policy(MixPolicy(hihat_pan=0.3))
        pan = r._compute_pan('Hi-Hat', is_drums=False, index=0)
        assert pan == pytest.approx(0.3)

    def test_lead_track_still_alternates(self):
        """Non-drum/bass/kick/snare/hihat tracks still alternate L/R."""
        r = AudioRenderer(use_fluidsynth=False, use_bwf=False, genre='pop')
        r.set_mix_policy(MixPolicy())
        pan_even = r._compute_pan('Synth Lead', is_drums=False, index=0)
        pan_odd = r._compute_pan('Pad', is_drums=False, index=1)
        assert pan_even == pytest.approx(0.2)
        assert pan_odd == pytest.approx(-0.2)


@pytest.mark.skipif(not (_HAS_RENDERER and _HAS_POLICY),
                    reason="Renderer or MixPolicy not available")
class TestSubBassTarget:
    """Task 10.3: MixPolicy.sub_bass_target modulates bass chain EQ."""

    def test_high_sub_target_boosts_eq(self):
        """sub_bass_target=0.8 should produce higher sub boost."""
        r = AudioRenderer(use_fluidsynth=False, use_bwf=False, genre='trap')
        r.set_mix_policy(MixPolicy(sub_bass_target=0.8))
        chain = r._get_chain_for_track('Bass', is_drums=False)
        assert chain is not None
        # The 60Hz band should have been boosted above default 2dB
        first_fx = chain.effects[0]
        fx_params = first_fx[1] if isinstance(first_fx, tuple) else first_fx
        sub_band = [b for b in fx_params.bands if isinstance(b, dict) and b.get('frequency') == 60][0]
        assert sub_band['gain_db'] > 2.0

    def test_low_sub_target_reduces_eq(self):
        """sub_bass_target=0.2 should produce zero sub boost."""
        r = AudioRenderer(use_fluidsynth=False, use_bwf=False, genre='lofi')
        r.set_mix_policy(MixPolicy(sub_bass_target=0.2))
        chain = r._get_chain_for_track('Bass', is_drums=False)
        assert chain is not None
        first_fx = chain.effects[0]
        fx_params = first_fx[1] if isinstance(first_fx, tuple) else first_fx
        sub_band = [b for b in fx_params.bands if isinstance(b, dict) and b.get('frequency') == 60][0]
        assert sub_band['gain_db'] == pytest.approx(0.0, abs=0.1)

    def test_default_sub_target_gives_2db(self):
        """sub_bass_target=0.5 (default) should give ~2dB sub boost."""
        r = AudioRenderer(use_fluidsynth=False, use_bwf=False, genre='pop')
        r.set_mix_policy(MixPolicy(sub_bass_target=0.5))
        chain = r._get_chain_for_track('Bass', is_drums=False)
        assert chain is not None
        first_fx = chain.effects[0]
        fx_params = first_fx[1] if isinstance(first_fx, tuple) else first_fx
        sub_band = [b for b in fx_params.bands if isinstance(b, dict) and b.get('frequency') == 60][0]
        assert sub_band['gain_db'] == pytest.approx(2.0, abs=0.1)

    def test_no_policy_keeps_default_boost(self):
        """Without MixPolicy, bass chain keeps default +2dB sub boost."""
        r = AudioRenderer(use_fluidsynth=False, use_bwf=False, genre='trap')
        r._mix_policy = None
        chain = r._get_chain_for_track('Bass', is_drums=False)
        assert chain is not None
        first_fx = chain.effects[0]
        fx_params = first_fx[1] if isinstance(first_fx, tuple) else first_fx
        sub_band = [b for b in fx_params.bands if isinstance(b, dict) and b.get('frequency') == 60][0]
        assert sub_band['gain_db'] == 2  # Original hardcoded value
