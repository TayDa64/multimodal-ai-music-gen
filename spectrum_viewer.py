#!/usr/bin/env python3
"""
Simple Spectrum Analyzer for debugging Ethiopian instrument sounds.
Shows real-time frequency analysis of generated audio samples.
"""

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from scipy import signal
import sys
import os

# Add project to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from multimodal_gen.assets_gen import (
    generate_krar_tone,
    generate_masenqo_tone,
    generate_begena_tone
)


def midi_to_freq(midi_note: int) -> float:
    """Convert MIDI note number to frequency in Hz."""
    return 440.0 * (2 ** ((midi_note - 69) / 12))


def analyze_instrument(name: str, generator_func, note: int = 60, duration: float = 2.0, sample_rate: int = 44100):
    """Generate and analyze a single instrument tone."""
    print(f"\nGenerating {name} (MIDI note {note})...")
    
    # Convert MIDI note to frequency
    frequency = midi_to_freq(note)
    print(f"  Frequency: {frequency:.2f} Hz")
    
    # Generate the tone with correct arguments:
    # (frequency, duration, velocity, sample_rate)
    audio = generator_func(
        frequency=frequency, 
        duration=duration, 
        velocity=0.75,
        sample_rate=sample_rate
    )
    
    print(f"  Generated {len(audio)} samples, RMS: {np.sqrt(np.mean(audio**2)):.4f}")
    
    # Normalize for visualization
    if np.max(np.abs(audio)) > 0:
        audio = audio / np.max(np.abs(audio))
    
    return audio


def plot_spectrum(audio: np.ndarray, sample_rate: int, title: str, ax_wave, ax_spec, ax_spectrogram):
    """Plot waveform, spectrum, and spectrogram for an audio sample."""
    
    # Time axis
    t = np.linspace(0, len(audio) / sample_rate, len(audio))
    
    # Waveform
    ax_wave.clear()
    ax_wave.plot(t, audio, color='cyan', linewidth=0.5)
    ax_wave.set_xlabel('Time (s)')
    ax_wave.set_ylabel('Amplitude')
    ax_wave.set_title(f'{title} - Waveform')
    ax_wave.set_xlim(0, len(audio) / sample_rate)
    ax_wave.grid(True, alpha=0.3)
    
    # FFT Spectrum
    ax_spec.clear()
    
    # Use a window to reduce spectral leakage
    window = signal.windows.hann(len(audio))
    audio_windowed = audio * window
    
    # Compute FFT
    fft = np.fft.rfft(audio_windowed)
    freqs = np.fft.rfftfreq(len(audio), 1/sample_rate)
    magnitude = 20 * np.log10(np.abs(fft) + 1e-10)  # dB scale
    
    # Plot spectrum
    ax_spec.plot(freqs, magnitude, color='lime', linewidth=0.8)
    ax_spec.set_xlabel('Frequency (Hz)')
    ax_spec.set_ylabel('Magnitude (dB)')
    ax_spec.set_title(f'{title} - Frequency Spectrum')
    ax_spec.set_xlim(20, 8000)  # Focus on audible range
    ax_spec.set_ylim(-60, 60)
    ax_spec.grid(True, alpha=0.3)
    
    # Mark common problem frequencies
    problem_freqs = [
        (2000, 'harsh/tinny'),
        (4000, 'digital artifacts'),
        (6000, 'scratchy'),
    ]
    for freq, desc in problem_freqs:
        ax_spec.axvline(x=freq, color='red', linestyle='--', alpha=0.3)
        ax_spec.text(freq, 50, f'{freq}Hz\n{desc}', fontsize=7, color='red', alpha=0.7)
    
    # Mark fundamental and harmonics (assuming note 60 = C4 = 261.63 Hz)
    fundamental = 261.63
    for i in range(1, 8):
        ax_spec.axvline(x=fundamental * i, color='yellow', linestyle=':', alpha=0.3)
    
    # Spectrogram
    ax_spectrogram.clear()
    f, t_spec, Sxx = signal.spectrogram(audio, sample_rate, nperseg=2048, noverlap=1024)
    
    # Limit to 8kHz
    freq_mask = f <= 8000
    f = f[freq_mask]
    Sxx = Sxx[freq_mask, :]
    
    ax_spectrogram.pcolormesh(t_spec, f, 10 * np.log10(Sxx + 1e-10), shading='gouraud', cmap='magma')
    ax_spectrogram.set_xlabel('Time (s)')
    ax_spectrogram.set_ylabel('Frequency (Hz)')
    ax_spectrogram.set_title(f'{title} - Spectrogram')


def main():
    """Main function to display spectrum analysis of Ethiopian instruments."""
    
    sample_rate = 44100
    duration = 2.0
    note = 60  # Middle C
    
    # Generate all instruments
    instruments = {
        'Krar (Lyre)': generate_krar_tone,
        'Masenqo (Fiddle)': generate_masenqo_tone,
        'Begena (Bass Lyre)': generate_begena_tone,
    }
    
    print("=" * 60)
    print("Ethiopian Instrument Spectrum Analyzer")
    print("=" * 60)
    print("\nThis tool shows frequency content of each instrument.")
    print("Look for:")
    print("  - Sharp spikes at high frequencies (2-6kHz) = digital/harsh sound")
    print("  - Smooth harmonic series = natural sound")
    print("  - Jagged/noisy spectrum = scratchy artifacts")
    print()
    
    # Create figure with subplots for each instrument
    fig, axes = plt.subplots(3, 3, figsize=(16, 12))
    fig.suptitle('Ethiopian Instrument Analysis\n(Red lines = potential problem frequencies, Yellow lines = harmonic series)', 
                 fontsize=14, fontweight='bold')
    
    plt.style.use('dark_background')
    fig.patch.set_facecolor('#1a1a2e')
    
    for idx, (name, gen_func) in enumerate(instruments.items()):
        audio = analyze_instrument(name, gen_func, note, duration, sample_rate)
        
        ax_wave = axes[idx, 0]
        ax_spec = axes[idx, 1]
        ax_spectrogram = axes[idx, 2]
        
        for ax in [ax_wave, ax_spec, ax_spectrogram]:
            ax.set_facecolor('#16213e')
        
        plot_spectrum(audio, sample_rate, name, ax_wave, ax_spec, ax_spectrogram)
    
    plt.tight_layout()
    plt.subplots_adjust(top=0.92)
    
    # Save the plot
    output_path = os.path.join(os.path.dirname(__file__), 'output', 'spectrum_analysis.png')
    plt.savefig(output_path, dpi=150, facecolor='#1a1a2e')
    print(f"\nSpectrum analysis saved to: {output_path}")
    
    # Show interactive plot
    print("\nDisplaying spectrum analyzer... (close window to exit)")
    plt.show()


if __name__ == "__main__":
    main()
