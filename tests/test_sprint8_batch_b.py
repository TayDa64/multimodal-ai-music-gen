"""Sprint 8 Batch B tests — reference profile bridge + MixPolicy panning wiring."""

import pytest
import numpy as np
from unittest.mock import patch, MagicMock, PropertyMock

# Guarded imports
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
class TestReferenceProfileBridge:
    """Task 8.3: Reference profile bridge from main.py to renderer."""

    def test_set_reference_profile_exists(self):
        """AudioRenderer exposes set_reference_profile method."""
        renderer = AudioRenderer(genre="trap", mood="dark", require_soundfont=False, use_fluidsynth=False)
        assert hasattr(renderer, 'set_reference_profile')
        assert callable(renderer.set_reference_profile)

    def test_set_reference_profile_stores_profile(self):
        """set_reference_profile stores the profile and creates matcher when available."""
        renderer = AudioRenderer(genre="trap", mood="dark", require_soundfont=False, use_fluidsynth=False)
        mock_profile = MagicMock()
        renderer.set_reference_profile(mock_profile)
        assert renderer._reference_profile is mock_profile

    def test_set_reference_profile_none_clears(self):
        """Passing None deactivates reference matching."""
        renderer = AudioRenderer(genre="trap", mood="dark", require_soundfont=False, use_fluidsynth=False)
        mock_profile = MagicMock()
        renderer.set_reference_profile(mock_profile)
        renderer.set_reference_profile(None)
        assert renderer._reference_profile is None
        assert renderer._reference_matcher is None


@pytest.mark.skipif(not _HAS_RENDERER, reason="AudioRenderer not available")
class TestMixPolicyPanning:
    """Task 8.4: MixPolicy panning wiring."""

    def test_set_mix_policy_exists(self):
        """AudioRenderer exposes set_mix_policy method."""
        renderer = AudioRenderer(genre="trap", mood="dark", require_soundfont=False, use_fluidsynth=False)
        assert hasattr(renderer, 'set_mix_policy')
        assert callable(renderer.set_mix_policy)

    def test_set_mix_policy_stores(self):
        """set_mix_policy stores the policy object."""
        renderer = AudioRenderer(genre="trap", mood="dark", require_soundfont=False, use_fluidsynth=False)
        mock_policy = MagicMock()
        renderer.set_mix_policy(mock_policy)
        assert renderer._mix_policy is mock_policy

    def test_mix_policy_default_none(self):
        """_mix_policy defaults to None on fresh renderer."""
        renderer = AudioRenderer(genre="trap", mood="dark", require_soundfont=False, use_fluidsynth=False)
        assert renderer._mix_policy is None

    @pytest.mark.skipif(not _HAS_MIX_POLICY, reason="MixPolicy not available")
    def test_mix_policy_panning_bass_uses_policy(self):
        """When MixPolicy is set, bass tracks use bass_pan from policy."""
        renderer = AudioRenderer(genre="trap", mood="dark", require_soundfont=False, use_fluidsynth=False)
        policy = MixPolicy(bass_pan=-0.1, kick_pan=0.0, snare_pan=0.05, hihat_pan=0.3)
        renderer.set_mix_policy(policy)
        pan = renderer._compute_pan("808 Bass", is_drums=False, index=0)
        assert pan == -0.1, f"Expected bass_pan=-0.1 from MixPolicy, got {pan}"

    def test_mix_policy_drums_subtle_offset(self):
        """Drums get subtle hihat_pan offset from MixPolicy (Sprint 10.2)."""
        renderer = AudioRenderer(genre="trap", mood="dark", require_soundfont=False, use_fluidsynth=False)
        renderer.set_mix_policy(MixPolicy(kick_pan=0.5, snare_pan=0.3, hihat_pan=0.0))
        pan = renderer._compute_pan("Drums", is_drums=True, index=0)
        assert pan == 0.0, "Drums with hihat_pan=0 should pan center"

    def test_mix_policy_fallback_when_none(self):
        """Without MixPolicy, default hardcoded panning applies."""
        renderer = AudioRenderer(genre="jazz", mood="smooth", require_soundfont=False, use_fluidsynth=False)
        assert renderer._mix_policy is None
        pan = renderer._compute_pan("Piano", is_drums=False, index=0)
        assert pan == 0.2, "Default panning should be 0.2 for even index"
