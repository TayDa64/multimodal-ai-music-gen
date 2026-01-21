"""
Test suite for the agents package.

Verifies:
1. All agent interfaces are correctly defined
2. AgentRegistry can spawn agents for all registered instruments
3. Section spawning works correctly
4. Personality presets are properly structured
5. No regressions in existing functionality
"""

import pytest
from multimodal_gen.agents import (
    AgentRole,
    IPerformerAgent,
    PerformanceResult,
    PerformanceContext,
    PerformanceScore,
    IConductorAgent,
    AgentRegistry,
    AgentPersonality,
    DRUMMER_PRESETS,
    BASSIST_PRESETS,
    KEYIST_PRESETS,
    GENRE_PERSONALITY_MAP,
    get_personality_for_role,
)


class TestAgentRole:
    """Test AgentRole enum."""
    
    def test_all_roles_defined(self):
        """Ensure all expected roles exist."""
        expected_roles = [
            'drums', 'bass', 'keys', 'lead', 'pad', 
            'strings', 'brass', 'percussion', 'fx', 'section'
        ]
        actual_roles = [r.value for r in AgentRole]
        assert set(expected_roles) == set(actual_roles)
    
    def test_role_values_are_strings(self):
        """Roles should have string values."""
        for role in AgentRole:
            assert isinstance(role.value, str)


class TestPerformanceResult:
    """Test PerformanceResult dataclass."""
    
    def test_default_construction(self):
        """Default construction should work."""
        result = PerformanceResult()
        assert result.notes == []
        assert result.agent_role == AgentRole.DRUMS
        assert result.decisions_made == []
        assert result.patterns_used == []
        assert result.fill_locations == []
    
    def test_custom_construction(self):
        """Custom values should be set correctly."""
        result = PerformanceResult(
            notes=[1, 2, 3],  # Simplified for test
            agent_role=AgentRole.BASS,
            agent_name="Test Bass",
            decisions_made=["Used pocket pattern"],
        )
        assert result.notes == [1, 2, 3]
        assert result.agent_role == AgentRole.BASS
        assert result.agent_name == "Test Bass"
        assert "Used pocket pattern" in result.decisions_made


class TestAgentPersonality:
    """Test AgentPersonality dataclass."""
    
    def test_default_values(self):
        """Default personality should have reasonable values."""
        p = AgentPersonality()
        assert 0.0 <= p.aggressiveness <= 1.0
        assert 0.0 <= p.complexity <= 1.0
        assert 0.0 <= p.consistency <= 1.0
        assert -1.0 <= p.push_pull <= 1.0
        assert p.signature_patterns == []
        assert p.avoided_patterns == []
    
    def test_preset_drummers_valid(self):
        """Drummer presets should have valid values."""
        for name, preset in DRUMMER_PRESETS.items():
            assert isinstance(preset, AgentPersonality), f"Preset {name} not AgentPersonality"
            assert 0.0 <= preset.aggressiveness <= 1.0
            assert 0.0 <= preset.complexity <= 1.0
            assert 0.0 <= preset.fill_frequency <= 1.0
    
    def test_preset_bassists_valid(self):
        """Bassist presets should have valid values."""
        for name, preset in BASSIST_PRESETS.items():
            assert isinstance(preset, AgentPersonality)
            assert 0.0 <= preset.aggressiveness <= 1.0
    
    def test_genre_personality_map(self):
        """Genre personality map should have proper structure."""
        for genre, role_map in GENRE_PERSONALITY_MAP.items():
            assert isinstance(genre, str)
            assert isinstance(role_map, dict)
            for role_key, preset_name in role_map.items():
                # role_key can be AgentRole or str
                assert isinstance(preset_name, str)


class TestGetPersonalityForRole:
    """Test get_personality_for_role function."""
    
    def test_known_genre_role(self):
        """Known genre and role should return personality."""
        p = get_personality_for_role("trap", AgentRole.DRUMS)
        assert isinstance(p, AgentPersonality)
    
    def test_unknown_genre(self):
        """Unknown genre should return default personality."""
        p = get_personality_for_role("nonexistent_genre", AgentRole.DRUMS)
        assert isinstance(p, AgentPersonality)
    
    def test_unknown_role(self):
        """Unknown role in known genre should return default."""
        p = get_personality_for_role("trap", AgentRole.FX)
        assert isinstance(p, AgentPersonality)


class TestAgentRegistry:
    """Test AgentRegistry functionality."""
    
    def test_core_agents_registered(self):
        """Core instruments should be registered."""
        core_instruments = ["drums", "bass", "piano", "keys", "synth", "pad"]
        for inst in core_instruments:
            role = AgentRegistry.get_agent_role(inst)
            assert isinstance(role, AgentRole)
    
    def test_orchestral_agents_registered(self):
        """Orchestral instruments should be registered."""
        orchestral = ["violin", "cello", "trumpet", "trombone", "flute", "clarinet"]
        for inst in orchestral:
            role = AgentRegistry.get_agent_role(inst)
            assert isinstance(role, AgentRole)
    
    def test_ethiopian_agents_registered(self):
        """Ethiopian instruments should be registered."""
        ethiopian = ["masenqo", "krar", "begena", "washint", "kebero"]
        for inst in ethiopian:
            role = AgentRegistry.get_agent_role(inst)
            assert isinstance(role, AgentRole)
    
    def test_world_agents_registered(self):
        """World instruments should be registered."""
        world = ["sitar", "tabla", "koto", "djembe", "oud"]
        for inst in world:
            role = AgentRegistry.get_agent_role(inst)
            assert isinstance(role, AgentRole)
    
    def test_spawn_agent_returns_config(self):
        """spawn_agent should return proper config dict."""
        config = AgentRegistry.spawn_agent("drums", "trap")
        assert "instrument" in config
        assert "role" in config
        assert "genre" in config
        assert "personality" in config
        assert "name" in config
        assert config["instrument"] == "drums"
        assert config["role"] == AgentRole.DRUMS
        assert config["genre"] == "trap"
    
    def test_spawn_agent_with_personality(self):
        """spawn_agent should accept personality override."""
        custom_p = AgentPersonality(aggressiveness=0.9)
        config = AgentRegistry.spawn_agent("bass", "lofi", personality=custom_p)
        assert config["personality"].aggressiveness == 0.9
    
    def test_spawn_section_strings(self):
        """spawn_section should create string quartet."""
        configs = AgentRegistry.spawn_section("strings", 4)
        assert len(configs) == 4
        # Should have violin, violin, viola, cello voices
        voice_names = [c["name"] for c in configs]
        assert "Violin I" in voice_names
        assert "Violin II" in voice_names
        assert "Viola" in voice_names
        assert "Cello" in voice_names
    
    def test_spawn_section_brass(self):
        """spawn_section should create brass section."""
        configs = AgentRegistry.spawn_section("brass")
        assert len(configs) >= 4
        for config in configs:
            assert config["role"] == AgentRole.BRASS
    
    def test_spawn_section_ethiopian_ensemble(self):
        """spawn_section should create Ethiopian ensemble."""
        configs = AgentRegistry.spawn_section("ethiopian_ensemble")
        assert len(configs) == 4
        instruments = [c["instrument"] for c in configs]
        assert "kebero" in instruments
        assert "krar" in instruments
        assert "masenqo" in instruments
        assert "washint" in instruments
    
    def test_is_section_type(self):
        """is_section_type should correctly identify sections."""
        assert AgentRegistry.is_section_type("strings")
        assert AgentRegistry.is_section_type("brass")
        assert AgentRegistry.is_section_type("ethiopian_ensemble")
        assert not AgentRegistry.is_section_type("piano")
        assert not AgentRegistry.is_section_type("drums")
    
    def test_get_all_instruments(self):
        """get_all_instruments should return comprehensive list."""
        instruments = AgentRegistry.get_all_instruments()
        assert len(instruments) > 50  # Should have many instruments
        assert "drums" in instruments
        assert "piano" in instruments
        assert "violin" in instruments
        assert "masenqo" in instruments
    
    def test_get_instruments_for_role(self):
        """get_instruments_for_role should filter correctly."""
        drums = AgentRegistry.get_instruments_for_role(AgentRole.DRUMS)
        assert "drums" in drums or "drum_kit" in drums
        assert "kebero" in drums  # Ethiopian drum
        
        strings = AgentRegistry.get_instruments_for_role(AgentRole.STRINGS)
        assert "violin" in strings
        assert "masenqo" in strings


class TestPerformanceContext:
    """Test PerformanceContext dataclass."""
    
    def test_construction(self):
        """PerformanceContext should construct properly."""
        ctx = PerformanceContext(
            bpm=120.0,
            time_signature=(4, 4),
            current_section=None,
            key="C",
            scale_notes=[0, 2, 4, 5, 7, 9, 11],
            tension=0.5,
            energy_level=0.7,
            density_target=0.6,
        )
        assert ctx.bpm == 120.0
        assert ctx.key == "C"
        assert ctx.tension == 0.5


class TestPerformanceScore:
    """Test PerformanceScore dataclass."""
    
    def test_construction(self):
        """PerformanceScore should construct properly."""
        score = PerformanceScore(
            sections=[],
            tempo_map={0: 120.0},
            key_map={0: "C"},
            chord_map={},
            tension_curve=[0.3, 0.5, 0.7],
            cue_points=[],
        )
        assert score.tempo_map[0] == 120.0
        assert score.key_map[0] == "C"


class TestInterfaceAbstractness:
    """Test that interfaces are properly abstract."""
    
    def test_iperformer_is_abstract(self):
        """IPerformerAgent should be abstract."""
        with pytest.raises(TypeError):
            IPerformerAgent()
    
    def test_iconductor_is_abstract(self):
        """IConductorAgent should be abstract."""
        with pytest.raises(TypeError):
            IConductorAgent()


class TestNoRegressions:
    """Ensure no regressions in existing functionality."""
    
    def test_prompt_parser_still_works(self):
        """PromptParser should still work correctly."""
        from multimodal_gen.prompt_parser import PromptParser
        parser = PromptParser()
        parsed = parser.parse("trap beat 140 bpm D minor")
        assert parsed.bpm == 140.0
        assert parsed.genre == "trap"
    
    def test_arranger_still_works(self):
        """Arranger should still work correctly."""
        from multimodal_gen.prompt_parser import PromptParser
        from multimodal_gen.arranger import Arranger
        
        parser = PromptParser()
        parsed = parser.parse("lofi beat 75 bpm")
        
        arranger = Arranger()
        arrangement = arranger.create_arrangement(parsed)
        assert len(arrangement.sections) > 0
    
    def test_midi_generator_still_works(self):
        """MidiGenerator should still work correctly."""
        from multimodal_gen.prompt_parser import PromptParser
        from multimodal_gen.arranger import Arranger
        from multimodal_gen.midi_generator import MidiGenerator
        
        parser = PromptParser()
        parsed = parser.parse("house beat 125 bpm G major")
        
        arranger = Arranger()
        arrangement = arranger.create_arrangement(parsed)
        
        gen = MidiGenerator()
        midi_data = gen.generate(arrangement, parsed)
        assert len(midi_data.tracks) > 0
    
    def test_ethiopian_synthesis_still_works(self):
        """Ethiopian instrument synthesis should still work."""
        from multimodal_gen.plugins.ethiopian.plugin import EthiopianPlugin
        import numpy as np
        
        plugin = EthiopianPlugin()
        sample_rate = 44100
        
        # Test krar
        krar_audio = plugin.synthesize(
            instrument_id='krar',
            pitch=60,  # Middle C
            duration_samples=sample_rate,  # 1 second
            velocity=0.8,
            sample_rate=sample_rate,
        )
        assert isinstance(krar_audio, np.ndarray)
        assert len(krar_audio) > 0
        
        # Test masenqo  
        masenqo_audio = plugin.synthesize(
            instrument_id='masenqo',
            pitch=62,  # D
            duration_samples=sample_rate,
            velocity=0.8,
            sample_rate=sample_rate,
        )
        assert isinstance(masenqo_audio, np.ndarray)
        assert len(masenqo_audio) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
