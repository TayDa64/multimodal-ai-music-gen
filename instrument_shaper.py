#!/usr/bin/env python3
"""
INSTRUMENT SHAPER v4.0 - FabFilter Pro-Q3 Style
================================================
Single interactive graph where the spectrum IS the control surface.
Drag nodes directly on the frequency response to shape instrument sound.

Features:
- Single main spectrum view (like Pro-Q3)
- Draggable harmonic nodes on the spectrum
- Real-time sound preview as you drag
- Keyboard shortcuts for efficiency
- Dark professional theme
"""

import numpy as np
import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, FancyBboxPatch
from matplotlib.lines import Line2D
from scipy import signal
from scipy.io import wavfile
from dataclasses import dataclass, field
from typing import Optional, Callable
import sys
import os
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from multimodal_gen.assets_gen import (
    generate_krar_tone,
    generate_masenqo_tone, 
    generate_begena_tone,
    SAMPLE_RATE
)

# =============================================================================
# CONFIGURATION
# =============================================================================

COLORS = {
    'bg': '#0d0d0d',
    'panel': '#1a1a1a',
    'grid': '#2a2a2a',
    'text': '#e0e0e0',
    'text_dim': '#808080',
    'spectrum_fill': '#00ff8855',
    'spectrum_line': '#00ff88',
    'node_krar': '#ff6b6b',
    'node_masenqo': '#4ecdc4',
    'node_begena': '#ffe66d',
    'node_hover': '#ffffff',
    'node_active': '#ff00ff',
    'reference': '#ffffff33',
    'cursor': '#ffffff88',
}

INSTRUMENTS = {
    'Krar': {
        'generator': generate_krar_tone,
        'color': COLORS['node_krar'],
        'description': 'Plucked lyre - bright, clear harmonics',
        'base_note': 60,  # Middle C
    },
    'Masenqo': {
        'generator': generate_masenqo_tone,
        'color': COLORS['node_masenqo'],
        'description': 'Bowed fiddle - rich, expressive',
        'base_note': 60,
    },
    'Begena': {
        'generator': generate_begena_tone,
        'color': COLORS['node_begena'],
        'description': 'Bass lyre - deep with buzz',
        'base_note': 48,  # Lower octave
    },
}


@dataclass
class HarmonicNode:
    """A draggable node representing a harmonic."""
    harmonic: int  # 1 = fundamental, 2 = 2nd harmonic, etc.
    freq: float    # Current frequency in Hz
    gain: float    # Gain in dB (-60 to +12)
    q: float = 1.0 # Resonance/Q factor
    active: bool = True
    
    @property
    def x(self) -> float:
        return self.freq
    
    @property 
    def y(self) -> float:
        return self.gain


@dataclass
class InstrumentState:
    """Current state of an instrument's harmonic structure."""
    name: str
    fundamental: float = 261.63  # C4
    nodes: list = field(default_factory=list)
    attack_ms: float = 10.0
    decay_ms: float = 200.0
    sustain: float = 0.7
    release_ms: float = 300.0
    brightness: float = 1.0
    
    def __post_init__(self):
        if not self.nodes:
            self._init_default_harmonics()
    
    def _init_default_harmonics(self):
        """Initialize default harmonic series."""
        # Natural harmonic decay for plucked strings
        for h in range(1, 9):
            freq = self.fundamental * h
            if freq > 3000:
                break
            # Natural rolloff: -6dB per octave
            gain = -6 * np.log2(h) if h > 1 else 0
            self.nodes.append(HarmonicNode(h, freq, gain))


class InstrumentShaper:
    """FabFilter Pro-Q3 style instrument shaping interface."""
    
    def __init__(self):
        self.sample_rate = SAMPLE_RATE
        self.current_instrument = 'Krar'
        self.instruments: dict[str, InstrumentState] = {}
        self.audio_cache: dict[str, np.ndarray] = {}
        
        # Interaction state
        self.dragging_node: Optional[HarmonicNode] = None
        self.hover_node: Optional[HarmonicNode] = None
        self.cursor_freq: float = 0
        self.cursor_db: float = 0
        self.show_cursor = False
        
        # View state
        self.freq_range = (20, 3000)  # Ethiopian instruments range
        self.db_range = (-60, 12)
        
        # Audio playback
        self.playing = False
        self.play_thread: Optional[threading.Thread] = None
        
        self._init_instruments()
        self._setup_ui()
    
    def _init_instruments(self):
        """Initialize all instruments with their default states."""
        for name, config in INSTRUMENTS.items():
            base_freq = 261.63 * (2 ** ((config['base_note'] - 60) / 12))
            self.instruments[name] = InstrumentState(name, fundamental=base_freq)
            self._generate_audio(name)
    
    def _generate_audio(self, instrument_name: str):
        """Generate audio for an instrument."""
        config = INSTRUMENTS[instrument_name]
        state = self.instruments[instrument_name]
        
        try:
            if instrument_name == 'Masenqo':
                audio = config['generator'](
                    state.fundamental, 
                    duration=2.0, 
                    velocity=0.8,
                    expressiveness=0.7
                )
            else:
                audio = config['generator'](
                    state.fundamental,
                    duration=2.0,
                    velocity=0.8
                )
            
            # Normalize
            if np.max(np.abs(audio)) > 0:
                audio = audio / np.max(np.abs(audio)) * 0.9
            
            self.audio_cache[instrument_name] = audio
            
        except Exception as e:
            print(f"Error generating {instrument_name}: {e}")
            self.audio_cache[instrument_name] = np.zeros(int(2.0 * self.sample_rate))
    
    def _compute_spectrum(self, audio: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Compute frequency spectrum of audio."""
        if len(audio) == 0:
            return np.array([20, 3000]), np.array([-60, -60])
        
        # Window and FFT
        n = min(8192, len(audio))
        window = signal.windows.hann(n)
        audio_windowed = audio[:n] * window
        
        fft = np.fft.rfft(audio_windowed)
        freqs = np.fft.rfftfreq(n, 1/self.sample_rate)
        
        # Magnitude in dB
        magnitude = np.abs(fft) * 2 / n
        magnitude_db = 20 * np.log10(magnitude + 1e-10)
        
        # Smooth for display
        if len(magnitude_db) > 100:
            kernel_size = max(3, len(magnitude_db) // 100)
            kernel = np.ones(kernel_size) / kernel_size
            magnitude_db = np.convolve(magnitude_db, kernel, mode='same')
        
        return freqs, magnitude_db
    
    def _setup_ui(self):
        """Create the main UI."""
        # Create figure with dark theme
        plt.style.use('dark_background')
        
        self.fig = plt.figure(figsize=(14, 8), facecolor=COLORS['bg'])
        self.fig.canvas.manager.set_window_title('Ethiopian Instrument Shaper v4.0')
        
        # Main spectrum axes (most of the window)
        self.ax_main = self.fig.add_axes([0.08, 0.15, 0.84, 0.75])
        self.ax_main.set_facecolor(COLORS['panel'])
        
        # Info bar at bottom
        self.ax_info = self.fig.add_axes([0.08, 0.02, 0.84, 0.08])
        self.ax_info.set_facecolor(COLORS['bg'])
        self.ax_info.axis('off')
        
        self._setup_main_axes()
        self._draw_instrument_tabs()
        self._connect_events()
        self._update_display()
    
    def _setup_main_axes(self):
        """Configure the main spectrum axes."""
        ax = self.ax_main
        
        # Logarithmic frequency axis
        ax.set_xscale('log')
        ax.set_xlim(self.freq_range)
        ax.set_ylim(self.db_range)
        
        # Grid
        ax.grid(True, which='major', color=COLORS['grid'], linewidth=0.8, alpha=0.5)
        ax.grid(True, which='minor', color=COLORS['grid'], linewidth=0.3, alpha=0.3)
        
        # Labels
        ax.set_xlabel('Frequency (Hz)', color=COLORS['text'], fontsize=10)
        ax.set_ylabel('Level (dB)', color=COLORS['text'], fontsize=10)
        
        # Frequency ticks
        freq_ticks = [20, 50, 100, 200, 500, 1000, 2000, 3000]
        ax.set_xticks(freq_ticks)
        ax.set_xticklabels([f'{f}' for f in freq_ticks], color=COLORS['text_dim'])
        
        # dB ticks
        db_ticks = [-60, -48, -36, -24, -12, 0, 12]
        ax.set_yticks(db_ticks)
        ax.set_yticklabels([f'{d}' for d in db_ticks], color=COLORS['text_dim'])
        
        # Style spines
        for spine in ax.spines.values():
            spine.set_color(COLORS['grid'])
    
    def _draw_instrument_tabs(self):
        """Draw instrument selector tabs at the top."""
        tab_y = 0.92
        tab_width = 0.12
        tab_height = 0.05
        start_x = 0.08
        
        self.tab_patches = {}
        self.tab_texts = {}
        
        for i, (name, config) in enumerate(INSTRUMENTS.items()):
            x = start_x + i * (tab_width + 0.02)
            
            # Tab background
            is_active = name == self.current_instrument
            color = config['color'] if is_active else COLORS['panel']
            alpha = 1.0 if is_active else 0.5
            
            patch = FancyBboxPatch(
                (x, tab_y), tab_width, tab_height,
                boxstyle="round,pad=0.01,rounding_size=0.01",
                facecolor=color, edgecolor=COLORS['text_dim'],
                alpha=alpha, transform=self.fig.transFigure,
                figure=self.fig
            )
            self.fig.patches.append(patch)
            self.tab_patches[name] = patch
            
            # Tab text
            text = self.fig.text(
                x + tab_width/2, tab_y + tab_height/2,
                name, ha='center', va='center',
                fontsize=10, fontweight='bold',
                color='#000000' if is_active else COLORS['text']
            )
            self.tab_texts[name] = text
    
    def _update_tabs(self):
        """Update tab appearance."""
        for name, config in INSTRUMENTS.items():
            is_active = name == self.current_instrument
            
            self.tab_patches[name].set_facecolor(
                config['color'] if is_active else COLORS['panel']
            )
            self.tab_patches[name].set_alpha(1.0 if is_active else 0.5)
            self.tab_texts[name].set_color(
                '#000000' if is_active else COLORS['text']
            )
    
    def _connect_events(self):
        """Connect mouse and keyboard events."""
        self.fig.canvas.mpl_connect('button_press_event', self._on_click)
        self.fig.canvas.mpl_connect('button_release_event', self._on_release)
        self.fig.canvas.mpl_connect('motion_notify_event', self._on_motion)
        self.fig.canvas.mpl_connect('key_press_event', self._on_key)
        self.fig.canvas.mpl_connect('scroll_event', self._on_scroll)
    
    def _on_click(self, event):
        """Handle mouse click."""
        if event.inaxes == self.ax_main:
            # Check if clicking on a node
            state = self.instruments[self.current_instrument]
            for node in state.nodes:
                if self._is_near_node(event, node):
                    self.dragging_node = node
                    return
            
            # Double-click to add node
            if event.dblclick and event.button == 1:
                self._add_node_at(event.xdata, event.ydata)
                return
            
            # Right-click on node to delete
            if event.button == 3 and self.hover_node:
                self._remove_node(self.hover_node)
                return
        
        # Check tab clicks
        elif event.inaxes is None:
            self._check_tab_click(event)
    
    def _on_release(self, event):
        """Handle mouse release."""
        if self.dragging_node:
            self.dragging_node = None
            self._generate_audio(self.current_instrument)
            self._update_display()
    
    def _on_motion(self, event):
        """Handle mouse motion."""
        if event.inaxes == self.ax_main:
            self.show_cursor = True
            self.cursor_freq = event.xdata if event.xdata else 0
            self.cursor_db = event.ydata if event.ydata else 0
            
            if self.dragging_node:
                # Move the node
                if event.xdata and event.ydata:
                    # Constrain frequency to valid range
                    self.dragging_node.freq = np.clip(event.xdata, 20, 3000)
                    self.dragging_node.gain = np.clip(event.ydata, -60, 12)
                    self._update_display()
            else:
                # Check for hover
                self.hover_node = None
                state = self.instruments[self.current_instrument]
                for node in state.nodes:
                    if self._is_near_node(event, node):
                        self.hover_node = node
                        break
                self._update_display()
        else:
            self.show_cursor = False
            self._update_display()
    
    def _on_key(self, event):
        """Handle keyboard input."""
        key = event.key.lower() if event.key else ''
        
        if key == ' ':  # Space - play/stop
            self._toggle_play()
        elif key == '1':
            self._switch_instrument('Krar')
        elif key == '2':
            self._switch_instrument('Masenqo')
        elif key == '3':
            self._switch_instrument('Begena')
        elif key == 'r':  # Reset
            self._reset_current()
        elif key == 's':  # Save
            self._save_audio()
        elif key == 'a':  # Add node at cursor
            if self.show_cursor:
                self._add_node_at(self.cursor_freq, self.cursor_db)
        elif key == 'delete' or key == 'backspace':
            if self.hover_node:
                self._remove_node(self.hover_node)
        elif key == 'escape':
            plt.close(self.fig)
    
    def _on_scroll(self, event):
        """Handle scroll wheel for Q adjustment."""
        if self.hover_node and event.inaxes == self.ax_main:
            delta = 0.1 if event.button == 'up' else -0.1
            self.hover_node.q = np.clip(self.hover_node.q + delta, 0.1, 10.0)
            self._update_display()
    
    def _is_near_node(self, event, node: HarmonicNode, threshold: float = 0.05) -> bool:
        """Check if mouse is near a node."""
        if not event.xdata or not event.ydata:
            return False
        
        # Use log scale for x
        log_x = np.log10(event.xdata) if event.xdata > 0 else 0
        log_node_x = np.log10(node.freq) if node.freq > 0 else 0
        
        # Normalize to axes range
        x_range = np.log10(self.freq_range[1]) - np.log10(self.freq_range[0])
        y_range = self.db_range[1] - self.db_range[0]
        
        dx = (log_x - log_node_x) / x_range
        dy = (event.ydata - node.gain) / y_range
        
        return np.sqrt(dx**2 + dy**2) < threshold
    
    def _check_tab_click(self, event):
        """Check if a tab was clicked."""
        for name in INSTRUMENTS:
            patch = self.tab_patches[name]
            bbox = patch.get_bbox()
            if bbox.contains(event.x / self.fig.dpi / self.fig.get_figwidth(),
                           event.y / self.fig.dpi / self.fig.get_figheight()):
                self._switch_instrument(name)
                return
    
    def _switch_instrument(self, name: str):
        """Switch to a different instrument."""
        if name in INSTRUMENTS:
            self.current_instrument = name
            self.hover_node = None
            self.dragging_node = None
            self._update_tabs()
            self._update_display()
    
    def _add_node_at(self, freq: float, gain: float):
        """Add a new harmonic node."""
        state = self.instruments[self.current_instrument]
        harmonic = len(state.nodes) + 1
        node = HarmonicNode(harmonic, freq, gain)
        state.nodes.append(node)
        self._generate_audio(self.current_instrument)
        self._update_display()
    
    def _remove_node(self, node: HarmonicNode):
        """Remove a harmonic node."""
        state = self.instruments[self.current_instrument]
        if node in state.nodes and len(state.nodes) > 1:
            state.nodes.remove(node)
            self._generate_audio(self.current_instrument)
            self._update_display()
    
    def _reset_current(self):
        """Reset current instrument to defaults."""
        state = self.instruments[self.current_instrument]
        state.nodes.clear()
        state._init_default_harmonics()
        self._generate_audio(self.current_instrument)
        self._update_display()
    
    def _toggle_play(self):
        """Toggle audio playback."""
        if self.playing:
            self.playing = False
        else:
            self.playing = True
            self._play_current()
    
    def _play_current(self):
        """Play current instrument audio."""
        try:
            import sounddevice as sd
            audio = self.audio_cache.get(self.current_instrument)
            if audio is not None and len(audio) > 0:
                sd.play(audio, self.sample_rate)
        except ImportError:
            print("Install sounddevice for audio playback: pip install sounddevice")
        except Exception as e:
            print(f"Playback error: {e}")
    
    def _save_audio(self):
        """Save current instrument audio to file."""
        audio = self.audio_cache.get(self.current_instrument)
        if audio is not None:
            filename = f"output/{self.current_instrument.lower()}_shaped.wav"
            wavfile.write(filename, self.sample_rate, (audio * 32767).astype(np.int16))
            print(f"Saved: {filename}")
    
    def _update_display(self):
        """Update the main display."""
        ax = self.ax_main
        
        # Clear previous dynamic elements
        while ax.lines:
            ax.lines[0].remove()
        while ax.collections:
            ax.collections[0].remove()
        
        # Remove old scatter plots (nodes)
        for child in ax.get_children():
            if isinstance(child, matplotlib.collections.PathCollection):
                child.remove()
        
        config = INSTRUMENTS[self.current_instrument]
        state = self.instruments[self.current_instrument]
        audio = self.audio_cache.get(self.current_instrument, np.zeros(1000))
        
        # Compute and plot spectrum
        freqs, magnitude_db = self._compute_spectrum(audio)
        
        # Fill under curve
        ax.fill_between(freqs, magnitude_db, self.db_range[0],
                       color=config['color'], alpha=0.2)
        
        # Spectrum line
        ax.plot(freqs, magnitude_db, color=config['color'], linewidth=1.5, alpha=0.9)
        
        # Draw harmonic nodes
        for node in state.nodes:
            # Node circle
            is_hover = node == self.hover_node
            is_drag = node == self.dragging_node
            
            if is_drag:
                color = COLORS['node_active']
                size = 150
            elif is_hover:
                color = COLORS['node_hover']
                size = 120
            else:
                color = config['color']
                size = 80
            
            ax.scatter([node.freq], [node.gain], s=size, c=[color],
                      edgecolors='white', linewidths=2, zorder=10)
            
            # Node label
            label = f"H{node.harmonic}" if node.harmonic <= 8 else "+"
            ax.annotate(label, (node.freq, node.gain),
                       textcoords="offset points", xytext=(0, 12),
                       ha='center', fontsize=8, color=COLORS['text'],
                       fontweight='bold')
        
        # Cursor crosshair
        if self.show_cursor and self.cursor_freq > 0:
            ax.axvline(self.cursor_freq, color=COLORS['cursor'], linewidth=0.5, linestyle='--')
            ax.axhline(self.cursor_db, color=COLORS['cursor'], linewidth=0.5, linestyle='--')
        
        # Update info bar
        self._update_info_bar()
        
        self.fig.canvas.draw_idle()
    
    def _update_info_bar(self):
        """Update the info bar at the bottom."""
        self.ax_info.clear()
        self.ax_info.axis('off')
        
        config = INSTRUMENTS[self.current_instrument]
        state = self.instruments[self.current_instrument]
        
        # Instrument info
        info_left = f"{self.current_instrument}: {config['description']}"
        self.ax_info.text(0, 0.7, info_left, transform=self.ax_info.transAxes,
                         fontsize=9, color=config['color'])
        
        # Cursor info
        if self.show_cursor:
            cursor_info = f"Cursor: {self.cursor_freq:.0f} Hz / {self.cursor_db:.1f} dB"
        else:
            cursor_info = ""
        self.ax_info.text(0.5, 0.7, cursor_info, transform=self.ax_info.transAxes,
                         fontsize=9, color=COLORS['text'], ha='center')
        
        # Keyboard shortcuts
        shortcuts = "Keys: [1-3] Switch • [Space] Play • [R] Reset • [S] Save • [A] Add Node • [Del] Remove"
        self.ax_info.text(0.5, 0.2, shortcuts, transform=self.ax_info.transAxes,
                         fontsize=8, color=COLORS['text_dim'], ha='center')
        
        # Node count and hover info
        if self.hover_node:
            node_info = f"Node H{self.hover_node.harmonic}: {self.hover_node.freq:.0f}Hz @ {self.hover_node.gain:.1f}dB (Q={self.hover_node.q:.1f}) • Scroll to adjust Q"
        else:
            node_info = f"Harmonics: {len(state.nodes)} • Double-click to add • Right-click to remove"
        self.ax_info.text(1.0, 0.7, node_info, transform=self.ax_info.transAxes,
                         fontsize=9, color=COLORS['text_dim'], ha='right')
    
    def run(self):
        """Start the application."""
        print("=" * 60)
        print("  ETHIOPIAN INSTRUMENT SHAPER v4.0")
        print("  FabFilter Pro-Q3 Style Interface")
        print("=" * 60)
        print()
        print("  Controls:")
        print("    • Click & drag nodes to shape harmonics")
        print("    • Double-click to add new harmonic")
        print("    • Right-click node to delete")
        print("    • Scroll on node to adjust Q")
        print()
        print("  Keyboard:")
        print("    [1] Krar  [2] Masenqo  [3] Begena")
        print("    [Space] Play  [R] Reset  [S] Save  [Esc] Quit")
        print()
        print("=" * 60)
        
        plt.show()


def main():
    """Main entry point."""
    shaper = InstrumentShaper()
    shaper.run()


if __name__ == "__main__":
    main()
