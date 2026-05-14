"""Tests for Synthesizer Interface."""
import pytest
import numpy as np


class TestSynthesizerBase:
    """Test suite for synthesizer base classes."""
    
    def test_import_base(self):
        """Test base classes can be imported."""
        from multimodal_gen.synthesizers import (
            ISynthesizer,
            SynthNote,
            SynthTrack,
            SynthResult,
        )
        
        assert ISynthesizer is not None
        assert SynthNote is not None
        assert SynthTrack is not None
        assert SynthResult is not None
    
    def test_synth_note_dataclass(self):
        """Test SynthNote dataclass creation."""
        from multimodal_gen.synthesizers import SynthNote
        
        note = SynthNote(
            pitch=60,
            start_sample=0,
            duration_samples=48000,
            velocity=0.8,
            channel=0,
            program=0,
        )
        
        assert note.pitch == 60
        assert note.velocity == 0.8
        assert note.duration_samples == 48000
    
    def test_synth_track_dataclass(self):
        """Test SynthTrack dataclass creation."""
        from multimodal_gen.synthesizers import SynthTrack, SynthNote
        
        notes = [
            SynthNote(pitch=60, start_sample=0, duration_samples=24000, velocity=0.8, channel=0),
            SynthNote(pitch=64, start_sample=24000, duration_samples=24000, velocity=0.7, channel=0),
        ]
        
        track = SynthTrack(name="Test", notes=notes, is_drums=False)
        
        assert track.name == "Test"
        assert len(track.notes) == 2
        assert track.is_drums == False
    
    def test_synth_result_dataclass(self):
        """Test SynthResult dataclass creation."""
        from multimodal_gen.synthesizers import SynthResult
        
        result = SynthResult(
            audio=np.zeros(48000),
            sample_rate=48000,
            success=True,
            message="OK",
        )
        
        assert result.success == True
        assert result.sample_rate == 48000


class TestSynthesizerFactory:
    """Test suite for SynthesizerFactory."""
    
    def test_import(self):
        """Test synthesizer package can be imported."""
        from multimodal_gen.synthesizers import SynthesizerFactory
        assert SynthesizerFactory is not None
    
    def test_get_registered(self):
        """Test listing registered synthesizers."""
        from multimodal_gen.synthesizers import SynthesizerFactory
        
        registered = SynthesizerFactory.get_registered()
        
        assert isinstance(registered, list)
        assert 'procedural' in registered
    
    def test_get_available(self):
        """Test listing available synthesizers."""
        from multimodal_gen.synthesizers import SynthesizerFactory
        
        available = SynthesizerFactory.get_available()
        
        assert isinstance(available, list)
        # Procedural should always be available
        assert 'procedural' in available
    
    def test_create_procedural(self):
        """Test creating procedural synthesizer."""
        from multimodal_gen.synthesizers import SynthesizerFactory
        
        synth = SynthesizerFactory.create('procedural')
        
        assert synth is not None
        assert synth.is_available == True
        assert synth.name == 'Procedural'
    
    def test_create_unknown(self):
        """Test creating unknown synthesizer returns None."""
        from multimodal_gen.synthesizers import SynthesizerFactory
        
        synth = SynthesizerFactory.create('unknown_synth_xyz')
        
        assert synth is None
    
    def test_get_best_available(self):
        """Test getting best available synthesizer."""
        from multimodal_gen.synthesizers import SynthesizerFactory
        
        synth = SynthesizerFactory.get_best_available()
        
        assert synth is not None
        assert synth.is_available == True
    
    def test_get_all_info(self):
        """Test getting info for all synthesizers."""
        from multimodal_gen.synthesizers import SynthesizerFactory
        
        info = SynthesizerFactory.get_all_info()
        
        assert isinstance(info, dict)
        assert 'procedural' in info
        assert 'name' in info['procedural']


class TestProceduralSynthesizer:
    """Test suite for ProceduralSynthesizer."""
    
    def test_import(self):
        """Test ProceduralSynthesizer can be imported."""
        from multimodal_gen.synthesizers import ProceduralSynthesizer
        assert ProceduralSynthesizer is not None
    
    def test_instantiation(self):
        """Test creating ProceduralSynthesizer instance."""
        from multimodal_gen.synthesizers import ProceduralSynthesizer
        
        synth = ProceduralSynthesizer()
        
        assert synth.name == 'Procedural'
        assert synth.is_available == True
    
    def test_render_notes(self, sample_rate):
        """Test rendering notes produces audio."""
        from multimodal_gen.synthesizers import SynthesizerFactory, SynthNote
        
        synth = SynthesizerFactory.create('procedural')
        
        notes = [
            SynthNote(
                pitch=60,
                start_sample=0,
                duration_samples=sample_rate // 2,
                velocity=0.8,
                channel=0,
                program=0,
            )
        ]
        
        audio = synth.render_notes(
            notes=notes,
            total_samples=sample_rate,
            is_drums=False,
            sample_rate=sample_rate,
        )
        
        assert isinstance(audio, np.ndarray)
        assert len(audio) == sample_rate
    
    def test_render_drums(self, sample_rate):
        """Test rendering drum notes."""
        from multimodal_gen.synthesizers import SynthesizerFactory, SynthNote
        
        synth = SynthesizerFactory.create('procedural')
        
        notes = [
            SynthNote(
                pitch=36,  # Kick drum
                start_sample=0,
                duration_samples=sample_rate // 4,
                velocity=1.0,
                channel=9,  # Drum channel
                program=0,
            )
        ]
        
        audio = synth.render_notes(
            notes=notes,
            total_samples=sample_rate // 2,
            is_drums=True,
            sample_rate=sample_rate,
        )
        
        assert isinstance(audio, np.ndarray)
        assert len(audio) > 0
    
    def test_capabilities(self):
        """Test synthesizer reports correct capabilities."""
        from multimodal_gen.synthesizers import SynthesizerFactory
        
        synth = SynthesizerFactory.create('procedural')
        caps = synth.get_capabilities()
        
        assert isinstance(caps, dict)
        assert caps.get('render_notes') == True
        assert caps.get('drums') == True
    
    def test_get_info(self):
        """Test synthesizer get_info method."""
        from multimodal_gen.synthesizers import ProceduralSynthesizer
        
        synth = ProceduralSynthesizer()
        info = synth.get_info()
        
        assert isinstance(info, dict)
        assert info['name'] == 'Procedural'
        assert info['available'] == True
        assert 'capabilities' in info


class TestISynthesizerInterface:
    """Test ISynthesizer abstract interface."""
    
    def test_interface_is_abstract(self):
        """Test interface is abstract base class."""
        from multimodal_gen.synthesizers import ISynthesizer
        from abc import ABC
        
        assert issubclass(ISynthesizer, ABC)
    
    def test_cannot_instantiate_interface(self):
        """Test interface cannot be instantiated."""
        from multimodal_gen.synthesizers import ISynthesizer
        
        with pytest.raises(TypeError):
            ISynthesizer()
    
    def test_interface_has_abstract_methods(self):
        """Test interface defines required abstract methods."""
        from multimodal_gen.synthesizers import ISynthesizer
        
        # Check abstract methods exist
        abstract_methods = getattr(ISynthesizer, '__abstractmethods__', set())
        
        assert 'name' in str(abstract_methods) or hasattr(ISynthesizer, 'name')
        assert 'is_available' in str(abstract_methods) or hasattr(ISynthesizer, 'is_available')
        assert 'render_notes' in str(abstract_methods) or hasattr(ISynthesizer, 'render_notes')


class TestFluidSynthSynthesizer:
    """Test suite for FluidSynthSynthesizer."""
    
    def test_import(self):
        """Test FluidSynthSynthesizer can be imported."""
        from multimodal_gen.synthesizers import FluidSynthSynthesizer
        assert FluidSynthSynthesizer is not None
    
    def test_instantiation(self):
        """Test creating FluidSynthSynthesizer instance."""
        from multimodal_gen.synthesizers import FluidSynthSynthesizer
        
        synth = FluidSynthSynthesizer()
        
        assert synth.name == 'FluidSynth'
        # is_available depends on FluidSynth installation
        assert isinstance(synth.is_available, bool)
    
    def test_capabilities(self):
        """Test FluidSynth reports capabilities."""
        from multimodal_gen.synthesizers import FluidSynthSynthesizer
        
        synth = FluidSynthSynthesizer()
        caps = synth.get_capabilities()
        
        assert isinstance(caps, dict)
        assert 'soundfonts' in caps

    def test_version_detection_falls_back_to_short_option(self, monkeypatch):
        """Windows portable FluidSynth may reject --version but accept -V."""
        from multimodal_gen.synthesizers import FluidSynthSynthesizer
        import subprocess

        calls = []

        def fake_run(cmd, **kwargs):
            calls.append(cmd)
            if '--version' in cmd:
                return subprocess.CompletedProcess(args=cmd, returncode=1, stdout='', stderr='no getopt')
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout='FluidSynth 2.4.7\n', stderr='')

        monkeypatch.setattr('subprocess.run', fake_run)

        synth = FluidSynthSynthesizer()

        assert synth.is_available is True
        assert synth.version == 'FluidSynth 2.4.7'
        assert calls == [['fluidsynth', '--version'], ['fluidsynth', '-V']]

    def test_render_midi_file_uses_options_before_files(self, monkeypatch, tmp_path):
        """FluidSynthSynthesizer should use no-getopt-safe option ordering."""
        from multimodal_gen.synthesizers import FluidSynthSynthesizer
        import os
        import subprocess
        import sys
        import types
        import numpy as np

        captured = {}
        midi_path = str(tmp_path / 'song.mid')
        wav_path = str(tmp_path / 'song.wav')
        sf_path = str(tmp_path / 'FluidR3Mono_GM.sf3')

        def fake_exists(path):
            return path in {midi_path, wav_path, sf_path}

        def fake_run(cmd, **kwargs):
            captured.setdefault('cmds', []).append(cmd)
            captured.setdefault('kwargs', []).append(kwargs)
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout='FluidSynth 2.4.7\n', stderr='')

        fake_soundfile = types.SimpleNamespace(read=lambda path: (np.zeros((8, 2), dtype=np.float32), 48000))

        monkeypatch.setattr(os.path, 'exists', fake_exists)
        monkeypatch.setattr('subprocess.run', fake_run)
        monkeypatch.setitem(sys.modules, 'soundfile', fake_soundfile)

        synth = FluidSynthSynthesizer(soundfont_path=sf_path)
        result = synth.render_midi_file(midi_path, wav_path, sample_rate=48000)

        assert result.success is True
        render_cmd = captured['cmds'][-1]
        assert '-ni' not in render_cmd
        assert render_cmd[:7] == ['fluidsynth', '-n', '-i', '-F', wav_path, '-r', '48000']
        assert render_cmd[-2:] == [sf_path, midi_path]
        assert captured['kwargs'][-1]['timeout'] == 60
