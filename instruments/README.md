# 🎹 Instruments Directory

This directory is for your custom audio samples. The AI will **analyze** each sample's sonic characteristics and **intelligently select** the best fit for each genre/mood.

## Directory Structure

```
instruments/
├── drums/
│   ├── kicks/      # Kick drums, bass drums
│   ├── snares/     # Snares, rimshots
│   ├── hihats/     # Hi-hats (open/closed)
│   ├── claps/      # Claps, snaps
│   └── 808s/       # 808 bass/sub kicks
├── bass/           # Bass instruments
├── keys/           # Piano, Rhodes, organ
├── synths/         # Synth leads, plucks
├── brass/          # Brass, horns
├── strings/        # Strings, orchestral
└── fx/             # FX, risers, impacts
```

## How It Works

### 1. Sample Analysis
When you run with `--instruments ./instruments`, the system:
- Scans all `.wav`, `.aif`, `.mp3`, `.flac` files
- Analyzes each sample's **sonic profile**:
  - **Brightness** (spectral centroid)
  - **Warmth** (low-frequency energy)
  - **Punch** (attack sharpness)
  - **Decay** (envelope characteristics)
  - **Pitch** (detected fundamental frequency)
- Caches results in `.instrument_cache.json`

### 2. Intelligent Matching
Based on the genre and mood:
- **Trap**: Prefers punchy kicks, bright hi-hats, deep 808s
- **Lofi**: Prefers warm, soft drums with longer decay
- **Boom Bap**: Prefers mid-punch kicks, crispy snares
- **House**: Prefers tight, punchy drums
- **G-Funk**: Prefers warm 808s, moderate punch

### 3. Automatic Selection
The best-matching samples are automatically loaded for audio rendering:
```
[4.5/6] Discovering and analyzing instruments...
✓  Discovered 167 instruments
ℹ  Instrument recommendations:
ℹ    kick: 808 Kick 3 (91% match)
ℹ    snare: 808 Snr 2 (81% match)
```

## Usage

### Basic
```bash
python main.py "trap beat" --instruments ./instruments
```

### With Your MPC Samples
```bash
python main.py "trap beat" --instruments "path/to/MPC/Samples"
```

### Verbose Mode (shows match scores)
```bash
python main.py "trap beat" --instruments ./instruments -v
```

## Supported Formats
- `.wav` (recommended)
- `.aif` / `.aiff`
- `.mp3`
- `.flac`

## Tips

1. **Organize by category** - Put kicks in `drums/kicks/`, snares in `drums/snares/`
2. **Use descriptive names** - `808_kick_hard.wav` helps with detection
3. **Quality matters** - 44.1kHz, 16-bit or higher recommended
4. **First run is slower** - Analysis is cached for subsequent runs

## Genre Profiles

| Genre | Kick | Snare | Hi-Hat | 808 |
|-------|------|-------|--------|-----|
| Trap | Punchy, Warm | Bright, Noisy | Bright, Short | Deep, Long |
| Lofi | Soft, Warm | Warm, Noisy | Dark, Soft | Warm |
| Boom Bap | Punchy | Crispy | Bright | - |
| House | Tight, Punchy | Punchy | Bright | - |
| G-Funk | Warm | Moderate | Moderate | Warm, Long |

---
*Powered by the InstrumentManager module with librosa analysis*
