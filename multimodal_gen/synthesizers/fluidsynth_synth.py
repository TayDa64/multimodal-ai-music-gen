"""FluidSynth synthesizer backend."""
from typing import List, Dict, Optional, Any
import numpy as np
import subprocess
import os

from .base import ISynthesizer, SynthNote, SynthResult


class FluidSynthSynthesizer(ISynthesizer):
    """
    FluidSynth-based synthesizer using external command.
    
    Renders MIDI to audio using FluidSynth and SoundFont files.
    This is a thin wrapper that delegates to the FluidSynth CLI.
    
    FluidSynth works best for complete MIDI file rendering rather than
    individual note synthesis, so render_notes returns silence and
    render_midi_file should be used instead.
    """
    
    def __init__(
        self,
        soundfont_path: Optional[str] = None,
        sample_rate: int = 48000,
        **kwargs
    ):
        """
        Initialize FluidSynth synthesizer.
        
        Args:
            soundfont_path: Path to SoundFont (.sf2) file
            sample_rate: Output sample rate
            **kwargs: Additional options (ignored for forward compatibility)
        """
        self._soundfont_path = soundfont_path
        self._sample_rate = sample_rate
        self._fluidsynth_available: Optional[bool] = None
        self._version: Optional[str] = None
    
    @property
    def name(self) -> str:
        return "FluidSynth"
    
    @property
    def is_available(self) -> bool:
        """Check if FluidSynth is installed and a SoundFont is available."""
        if self._fluidsynth_available is None:
            self._check_availability()
        return bool(self._fluidsynth_available)
    
    @property
    def version(self) -> Optional[str]:
        """Get FluidSynth version string."""
        if self._fluidsynth_available is None:
            self._check_availability()
        return self._version
    
    def _check_availability(self) -> None:
        """Check if FluidSynth is installed."""
        try:
            result = subprocess.run(
                ['fluidsynth', '--version'],
                capture_output=True,
                text=True
            )
            self._fluidsynth_available = result.returncode == 0
            self._version = (result.stdout or result.stderr).strip()
        except FileNotFoundError:
            self._fluidsynth_available = False
            self._version = None
    
    def configure(
        self,
        soundfont_path: Optional[str] = None,
        sample_rate: Optional[int] = None,
        **kwargs
    ) -> None:
        """
        Update configuration.
        
        Args:
            soundfont_path: Path to SoundFont file
            sample_rate: Output sample rate
            **kwargs: Additional options (ignored)
        """
        if soundfont_path is not None:
            self._soundfont_path = soundfont_path
        if sample_rate is not None:
            self._sample_rate = sample_rate
    
    def render_notes(
        self,
        notes: List[SynthNote],
        total_samples: int,
        is_drums: bool = False,
        sample_rate: int = 48000
    ) -> np.ndarray:
        """
        FluidSynth doesn't support note-by-note rendering via CLI.
        
        Returns silence. Use render_midi_file for full MIDI rendering.
        """
        return np.zeros(total_samples, dtype=np.float32)
    
    def render_midi_file(
        self,
        midi_path: str,
        output_path: str,
        sample_rate: int = 48000
    ) -> SynthResult:
        """
        Render MIDI file using FluidSynth.
        
        Args:
            midi_path: Path to input MIDI file
            output_path: Path for output audio file (WAV)
            sample_rate: Output sample rate
            
        Returns:
            SynthResult with success status and loaded audio
        """
        if not self.is_available:
            return SynthResult(
                audio=np.array([]),
                sample_rate=sample_rate,
                success=False,
                message="FluidSynth is not installed or not in PATH"
            )
        
        # Find SoundFont if not configured
        soundfont = self._soundfont_path
        if not soundfont:
            soundfont = self._find_soundfont()
            if not soundfont:
                return SynthResult(
                    audio=np.array([]),
                    sample_rate=sample_rate,
                    success=False,
                    message="No SoundFont (.sf2) file found"
                )
        
        # Verify SoundFont exists
        if not os.path.exists(soundfont):
            return SynthResult(
                audio=np.array([]),
                sample_rate=sample_rate,
                success=False,
                message=f"SoundFont not found: {soundfont}"
            )
        
        # Verify MIDI file exists
        if not os.path.exists(midi_path):
            return SynthResult(
                audio=np.array([]),
                sample_rate=sample_rate,
                success=False,
                message=f"MIDI file not found: {midi_path}"
            )
        
        try:
            cmd = [
                'fluidsynth',
                '-ni',                      # No interactive mode
                soundfont,                  # SoundFont
                midi_path,                  # Input MIDI
                '-F', output_path,          # Output file
                '-r', str(sample_rate),     # Sample rate
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0 and os.path.exists(output_path):
                # Load the rendered audio
                try:
                    import soundfile as sf
                    audio, sr = sf.read(output_path)
                    
                    return SynthResult(
                        audio=audio,
                        sample_rate=sr,
                        success=True,
                        message="Rendered successfully with FluidSynth",
                        metadata={
                            'version': self._version,
                            'soundfont': soundfont,
                        }
                    )
                except ImportError:
                    # soundfile not available, but file was created
                    return SynthResult(
                        audio=np.array([]),
                        sample_rate=sample_rate,
                        success=True,
                        message="Rendered successfully (soundfile not available to load)",
                        metadata={
                            'version': self._version,
                            'soundfont': soundfont,
                            'output_path': output_path,
                        }
                    )
            else:
                error_msg = result.stderr.strip() if result.stderr else "Unknown error"
                return SynthResult(
                    audio=np.array([]),
                    sample_rate=sample_rate,
                    success=False,
                    message=f"FluidSynth failed: {error_msg}"
                )
        except Exception as e:
            return SynthResult(
                audio=np.array([]),
                sample_rate=sample_rate,
                success=False,
                message=f"FluidSynth error: {str(e)}"
            )
    
    def _find_soundfont(self) -> Optional[str]:
        """Find a SoundFont file in common locations."""
        search_paths = [
            # Project assets
            './assets/soundfonts/',
            # User home
            os.path.expanduser('~/.fluidsynth/'),
            # Linux common
            '/usr/share/sounds/sf2/',
            '/usr/share/soundfonts/',
            # macOS
            '/Library/Audio/Sounds/Banks/',
        ]
        
        soundfont_names = [
            'default_sound_font.sf2',
            'FluidR3_GM.sf2',
            'GeneralUser_GS.sf2',
            'default.sf2',
        ]
        
        for path in search_paths:
            for name in soundfont_names:
                full_path = os.path.join(path, name)
                if os.path.exists(full_path):
                    return full_path
        
        return None
    
    def get_capabilities(self) -> Dict[str, bool]:
        """Return FluidSynth capabilities."""
        return {
            'render_midi_file': True,
            'render_notes': False,  # FluidSynth needs full MIDI file
            'drums': True,
            'soundfonts': True,
            'intelligent_selection': False,
        }
    
    def get_info(self) -> Dict[str, Any]:
        """Get detailed FluidSynth information."""
        info = super().get_info()
        info.update({
            'version': self.version,
            'soundfont_path': self._soundfont_path,
            'sample_rate': self._sample_rate,
        })
        return info
