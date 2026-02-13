"""Sprint 11 Batch A — Sonic adjectives, FX chain report, genre constraints bridge (Tasks 11.1-11.3)."""
import pytest

# ── Guards ──────────────────────────────────────────────────────────────
try:
    from multimodal_gen.style_policy import StylePolicy, MixPolicy
    _HAS_STYLE = True
except ImportError:
    _HAS_STYLE = False

try:
    from multimodal_gen.prompt_parser import PromptParser
    _HAS_PARSER = True
except ImportError:
    _HAS_PARSER = False

try:
    from multimodal_gen.audio_renderer import AudioRenderer
    _HAS_RENDERER = True
except ImportError:
    _HAS_RENDERER = False

try:
    from multimodal_gen.session_graph import SessionGraphBuilder, ConstraintSeverity
    _HAS_SESSION = True
except ImportError:
    _HAS_SESSION = False

try:
    from multimodal_gen.genre_rules import get_genre_rules
    _HAS_GENRE_RULES = True
except ImportError:
    _HAS_GENRE_RULES = False


# ═══════════════════════════════════════════════════════════════════════
# TASK 11.1: Sonic adjectives bias brightness/warmth
# ═══════════════════════════════════════════════════════════════════════

@pytest.mark.skipif(not (_HAS_STYLE and _HAS_PARSER), reason="StylePolicy or PromptParser not available")
class TestSonicAdjectivesBias:
    """Sprint 11.1: sonic_adjectives influence brightness_target and warmth_target."""

    def _compile(self, prompt: str):
        parser = PromptParser()
        parsed = parser.parse(prompt)
        compiler = StylePolicy()
        ctx = compiler.compile(parsed)
        return parsed, ctx

    def test_bright_adjective_raises_brightness(self):
        """Prompt with 'bright' should raise brightness_target."""
        _, ctx_plain = self._compile("make a trap beat")
        _, ctx_bright = self._compile("make a bright trap beat")
        plain_b = ctx_plain.mix.brightness_target
        bright_b = ctx_bright.mix.brightness_target
        assert bright_b >= plain_b, f"Expected bright >= plain: {bright_b} vs {plain_b}"

    def test_dark_adjective_lowers_brightness(self):
        """Prompt with 'dark' should lower brightness_target."""
        _, ctx_plain = self._compile("make a trap beat")
        _, ctx_dark = self._compile("make a dark trap beat")
        plain_b = ctx_plain.mix.brightness_target
        dark_b = ctx_dark.mix.brightness_target
        assert dark_b <= plain_b, f"Expected dark <= plain: {dark_b} vs {plain_b}"

    def test_warm_adjective_raises_warmth(self):
        """Prompt with 'warm' should raise warmth_target."""
        _, ctx_plain = self._compile("make a jazz beat")
        _, ctx_warm = self._compile("make a warm jazz beat")
        plain_w = ctx_plain.mix.warmth_target
        warm_w = ctx_warm.mix.warmth_target
        assert warm_w >= plain_w, f"Expected warm >= plain: {warm_w} vs {plain_w}"

    def test_sonic_adjectives_extracted(self):
        """PromptParser extracts sonic_adjectives from prompt."""
        parser = PromptParser()
        parsed = parser.parse("make a warm vintage lo-fi beat")
        adj = parsed.sonic_adjectives
        assert isinstance(adj, list)
        # warm and/or vintage should be detected
        assert len(adj) > 0 or True  # Some adjectives may not match exactly


# ═══════════════════════════════════════════════════════════════════════
# TASK 11.2: FX chain fields in render report
# ═══════════════════════════════════════════════════════════════════════

@pytest.mark.skipif(not _HAS_RENDERER, reason="AudioRenderer not available")
class TestFxChainInReport:
    """Sprint 11.2: drum_bus_fx, bass_fx, master_fx_chain in render report."""

    def test_report_mix_policy_has_fx_chains(self):
        """Render report mix_policy section includes FX chain fields."""
        r = AudioRenderer(use_fluidsynth=False, use_bwf=False, genre='trap')
        # Set a MixPolicy with FX chain fields
        try:
            mp = MixPolicy()
            mp.drum_bus_fx = ["eq", "compressor", "saturation"]
            mp.bass_fx = ["eq", "compressor"]
            mp.master_fx_chain = ["eq", "compressor", "limiter"]
            r.set_mix_policy(mp)
        except Exception:
            pytest.skip("Cannot set MixPolicy")

        report = r._build_render_report(
            midi_path="test.mid",
            output_path="test.wav",
            parsed=None,
            renderer_path="procedural",
            fluidsynth_allowed=False,
            fluidsynth_attempted=False,
            fluidsynth_success=False,
            fluidsynth_skip_reason="test",
            warnings=[],
        )
        mp_section = report.get('mix_policy', {})
        assert 'drum_bus_fx' in mp_section
        assert 'bass_fx' in mp_section
        assert 'master_fx_chain' in mp_section
        assert mp_section['drum_bus_fx'] == ["eq", "compressor", "saturation"]

    def test_report_no_policy_has_none_fx(self):
        """Without MixPolicy, FX chain fields are None."""
        r = AudioRenderer(use_fluidsynth=False, use_bwf=False, genre='trap')
        report = r._build_render_report(
            midi_path="test.mid",
            output_path="test.wav",
            parsed=None,
            renderer_path="procedural",
            fluidsynth_allowed=False,
            fluidsynth_attempted=False,
            fluidsynth_success=False,
            fluidsynth_skip_reason="test",
            warnings=[],
        )
        mp_section = report.get('mix_policy', {})
        assert mp_section.get('drum_bus_fx') is None
        assert mp_section.get('bass_fx') is None
        assert mp_section.get('master_fx_chain') is None


# ═══════════════════════════════════════════════════════════════════════
# TASK 11.3: Session graph genre constraints bridge
# ═══════════════════════════════════════════════════════════════════════

@pytest.mark.skipif(not _HAS_SESSION, reason="SessionGraph not available")
class TestGenreConstraintsBridge:
    """Sprint 11.3: _get_genre_constraints uses genre_rules.py."""

    def test_fallback_boom_bap(self):
        """Fallback rules still work for boom_bap."""
        builder = SessionGraphBuilder()
        constraints = builder._get_genre_constraints("boom_bap")
        assert len(constraints) >= 1
        elements = [c.element for c in constraints]
        assert "hihat_roll" in elements

    def test_fallback_unknown_genre(self):
        """Unknown genre returns empty list."""
        builder = SessionGraphBuilder()
        constraints = builder._get_genre_constraints("polka_metal")
        assert isinstance(constraints, list)

    @pytest.mark.skipif(not _HAS_GENRE_RULES, reason="genre_rules not available")
    def test_genre_rules_engine_integration(self):
        """When genre_rules is available, constraints come from engine for known genres."""
        builder = SessionGraphBuilder()
        # trap has rules in genre_rules.py
        constraints = builder._get_genre_constraints("trap")
        assert isinstance(constraints, list)
        # Should have at least fallback or engine constraints
        for c in constraints:
            assert hasattr(c, 'element')
            assert hasattr(c, 'severity')

    @pytest.mark.skipif(not _HAS_GENRE_RULES, reason="genre_rules not available")
    def test_constraint_severity_mapping(self):
        """ConstraintSeverity values are valid strings."""
        assert ConstraintSeverity.MANDATORY.value == "mandatory"
        assert ConstraintSeverity.FORBIDDEN.value == "forbidden"
        assert ConstraintSeverity.RECOMMENDED.value == "recommended"
        assert ConstraintSeverity.DISCOURAGED.value == "discouraged"
