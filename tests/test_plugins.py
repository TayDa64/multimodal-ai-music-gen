"""Tests for Instrument Plugin System."""
import pytest
import numpy as np


class TestPluginBase:
    """Test suite for plugin base classes."""
    
    def test_import_base(self):
        """Test base classes can be imported."""
        from multimodal_gen.plugins import (
            IInstrumentPlugin,
            PluginManifest,
            InstrumentDefinition,
        )
        
        assert IInstrumentPlugin is not None
        assert PluginManifest is not None
        assert InstrumentDefinition is not None
    
    def test_instrument_definition(self):
        """Test InstrumentDefinition dataclass."""
        from multimodal_gen.plugins import InstrumentDefinition
        
        inst = InstrumentDefinition(
            id='test',
            name='Test Instrument',
            display_name='Test',
            midi_program=0,
            category='melodic',
        )
        
        assert inst.id == 'test'
        assert inst.midi_program == 0
        assert inst.category == 'melodic'
    
    def test_plugin_manifest(self):
        """Test PluginManifest dataclass."""
        from multimodal_gen.plugins import PluginManifest
        
        manifest = PluginManifest(
            id='test_plugin',
            name='Test Plugin',
            version='1.0.0',
            culture='test',
        )
        
        assert manifest.id == 'test_plugin'
        assert manifest.version == '1.0.0'


class TestPluginRegistry:
    """Test suite for PluginRegistry."""
    
    def test_import(self):
        """Test plugin package can be imported."""
        from multimodal_gen.plugins import get_registry
        assert get_registry is not None
    
    def test_singleton(self):
        """Test registry is singleton."""
        from multimodal_gen.plugins import get_registry
        from multimodal_gen.plugins.registry import PluginRegistry
        
        # Reset to ensure clean state
        PluginRegistry.reset_instance()
        
        reg1 = get_registry()
        reg2 = get_registry()
        
        assert reg1 is reg2
    
    def test_list_plugins(self):
        """Test listing plugins."""
        from multimodal_gen.plugins import get_registry
        from multimodal_gen.plugins.registry import PluginRegistry
        
        PluginRegistry.reset_instance()
        registry = get_registry()
        
        plugins = registry.list_plugins()
        
        assert isinstance(plugins, list)
    
    def test_list_instruments(self):
        """Test listing instruments."""
        from multimodal_gen.plugins import get_registry
        from multimodal_gen.plugins.registry import PluginRegistry
        
        PluginRegistry.reset_instance()
        registry = get_registry()
        
        instruments = registry.list_instruments()
        
        assert isinstance(instruments, list)


class TestPluginLoader:
    """Test suite for plugin loader."""
    
    def test_import_loader(self):
        """Test loader functions can be imported."""
        from multimodal_gen.plugins import load_builtin_plugins, scan_plugins
        
        assert load_builtin_plugins is not None
        assert scan_plugins is not None
    
    def test_load_builtin_plugins(self):
        """Test loading built-in plugins."""
        from multimodal_gen.plugins import load_builtin_plugins, get_registry
        from multimodal_gen.plugins.registry import PluginRegistry
        
        # Reset registry
        PluginRegistry.reset_instance()
        
        loaded = load_builtin_plugins()
        
        assert isinstance(loaded, list)
        # Ethiopian plugin should be loaded
        assert len(loaded) > 0
        assert 'ethiopian_traditional' in loaded


class TestEthiopianPlugin:
    """Test suite for Ethiopian Plugin."""
    
    def test_import(self):
        """Test Ethiopian plugin can be imported."""
        from multimodal_gen.plugins.ethiopian.plugin import EthiopianPlugin
        assert EthiopianPlugin is not None
    
    def test_instantiation(self):
        """Test creating Ethiopian plugin instance."""
        from multimodal_gen.plugins.ethiopian.plugin import EthiopianPlugin
        
        plugin = EthiopianPlugin()
        
        assert plugin is not None
        assert plugin.is_available == True
    
    def test_manifest(self):
        """Test plugin manifest is valid."""
        from multimodal_gen.plugins.ethiopian.plugin import EthiopianPlugin
        
        plugin = EthiopianPlugin()
        manifest = plugin.manifest
        
        assert manifest.id == 'ethiopian_traditional'
        assert manifest.culture == 'ethiopian'
        assert len(manifest.instruments) == 5
    
    def test_manifest_instruments(self):
        """Test manifest contains correct instruments."""
        from multimodal_gen.plugins.ethiopian.plugin import EthiopianPlugin
        
        plugin = EthiopianPlugin()
        instruments = plugin.manifest.instruments
        
        assert 'krar' in instruments
        assert 'masenqo' in instruments
        assert 'washint' in instruments
        assert 'begena' in instruments
        assert 'kebero' in instruments
    
    def test_list_instruments(self):
        """Test list_instruments method."""
        from multimodal_gen.plugins.ethiopian.plugin import EthiopianPlugin
        
        plugin = EthiopianPlugin()
        instruments = plugin.list_instruments()
        
        instrument_ids = [i.id for i in instruments]
        assert 'krar' in instrument_ids
        assert 'masenqo' in instrument_ids
        assert 'washint' in instrument_ids
        assert 'begena' in instrument_ids
        assert 'kebero' in instrument_ids
    
    def test_synthesize_krar(self, sample_rate):
        """Test synthesizing krar note."""
        from multimodal_gen.plugins.ethiopian.plugin import EthiopianPlugin
        
        plugin = EthiopianPlugin()
        
        audio = plugin.synthesize(
            instrument_id='krar',
            pitch=60,
            duration_samples=sample_rate,
            velocity=0.8,
            sample_rate=sample_rate,
        )
        
        assert isinstance(audio, np.ndarray)
        assert len(audio) > 0
        assert not np.isnan(audio).any()
    
    def test_synthesize_masenqo(self, sample_rate):
        """Test synthesizing masenqo note."""
        from multimodal_gen.plugins.ethiopian.plugin import EthiopianPlugin
        
        plugin = EthiopianPlugin()
        
        audio = plugin.synthesize(
            instrument_id='masenqo',
            pitch=62,
            duration_samples=sample_rate,
            velocity=0.7,
            sample_rate=sample_rate,
        )
        
        assert isinstance(audio, np.ndarray)
        assert len(audio) > 0
    
    def test_synthesize_washint(self, sample_rate):
        """Test synthesizing washint note."""
        from multimodal_gen.plugins.ethiopian.plugin import EthiopianPlugin
        
        plugin = EthiopianPlugin()
        
        audio = plugin.synthesize(
            instrument_id='washint',
            pitch=67,
            duration_samples=sample_rate // 2,
            velocity=0.6,
            sample_rate=sample_rate,
        )
        
        assert isinstance(audio, np.ndarray)
        assert len(audio) > 0
    
    def test_synthesize_begena(self, sample_rate):
        """Test synthesizing begena note."""
        from multimodal_gen.plugins.ethiopian.plugin import EthiopianPlugin
        
        plugin = EthiopianPlugin()
        
        audio = plugin.synthesize(
            instrument_id='begena',
            pitch=48,
            duration_samples=sample_rate,
            velocity=0.8,
            sample_rate=sample_rate,
        )
        
        assert isinstance(audio, np.ndarray)
        assert len(audio) > 0
    
    def test_synthesize_kebero(self, sample_rate):
        """Test synthesizing kebero hit."""
        from multimodal_gen.plugins.ethiopian.plugin import EthiopianPlugin
        
        plugin = EthiopianPlugin()
        
        audio = plugin.synthesize(
            instrument_id='kebero',
            pitch=50,  # Bass hit
            duration_samples=sample_rate // 2,
            velocity=1.0,
            sample_rate=sample_rate,
        )
        
        assert isinstance(audio, np.ndarray)
        assert len(audio) > 0
    
    def test_synthesize_unknown_instrument(self, sample_rate):
        """Test synthesizing unknown instrument returns silence."""
        from multimodal_gen.plugins.ethiopian.plugin import EthiopianPlugin
        
        plugin = EthiopianPlugin()
        
        audio = plugin.synthesize(
            instrument_id='unknown_instrument',
            pitch=60,
            duration_samples=sample_rate,
            velocity=0.8,
            sample_rate=sample_rate,
        )
        
        # Should return zeros (silence)
        assert isinstance(audio, np.ndarray)
        assert np.all(audio == 0)
    
    def test_midi_program_mapping(self):
        """Test MIDI programs are correctly mapped."""
        from multimodal_gen.plugins.ethiopian.plugin import EthiopianPlugin
        
        plugin = EthiopianPlugin()
        
        assert plugin.handles_program(110)  # Krar
        assert plugin.handles_program(111)  # Masenqo
        assert plugin.handles_program(112)  # Washint
        assert plugin.handles_program(113)  # Begena
        assert plugin.handles_program(114)  # Kebero
        
        assert not plugin.handles_program(0)
        assert not plugin.handles_program(127)
    
    def test_get_instrument_for_program(self):
        """Test getting instrument by program number."""
        from multimodal_gen.plugins.ethiopian.plugin import EthiopianPlugin
        
        plugin = EthiopianPlugin()
        
        krar = plugin.get_instrument_for_program(110)
        assert krar is not None
        assert krar.id == 'krar'
        
        masenqo = plugin.get_instrument_for_program(111)
        assert masenqo is not None
        assert masenqo.id == 'masenqo'
    
    def test_get_info(self):
        """Test plugin get_info method."""
        from multimodal_gen.plugins.ethiopian.plugin import EthiopianPlugin
        
        plugin = EthiopianPlugin()
        info = plugin.get_info()
        
        assert isinstance(info, dict)
        assert info['id'] == 'ethiopian_traditional'
        assert info['available'] == True
        assert 'instruments' in info
