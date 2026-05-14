# SoundFonts

This project can render MIDI to audio in two ways:

- **FluidSynth + SoundFont (.sf2/.sf3)** (recommended): higher-quality, realistic timbres
- **Procedural fallback**: offline-first, no external assets, but noticeably less realistic

---

## Installation

### 1. Install FluidSynth

#### Windows

**Option A: Chocolatey** (recommended)
```powershell
choco install fluidsynth
```

**Option B: Official release**
- Download from [FluidSynth GitHub Releases](https://github.com/FluidSynth/fluidsynth/releases)
- Extract to a folder (e.g., `C:\Program Files\FluidSynth`)
- Add the `bin` directory to your system PATH

#### macOS

```bash
brew install fluid-synth
```

#### Linux (Ubuntu/Debian)

```bash
sudo apt update
sudo apt install fluidsynth
```

#### Linux (Fedora/RHEL)

```bash
sudo dnf install fluidsynth
```

### 2. Verify FluidSynth Installation

Run:

```bash
fluidsynth --version
```

On some official Windows portable builds, long options are unavailable because
the binary was compiled without getopt support. If `--version` fails, use:

```powershell
fluidsynth -V
```

Expected output:
```
FluidSynth runtime version X.X.X
```

---

## SoundFont Setup

### No Bundled SoundFonts

This repo intentionally does **not** ship any SoundFont binaries.
Download a SoundFont you have rights to use, then place it in this folder.

### Where to Place SoundFonts

Place your `.sf2` or `.sf3` file(s) in:

```
assets/soundfonts/
```

The renderer auto-searches common names:
- `FluidR3Mono_GM.sf3`
- `MS Basic.sf3`
- `default.sf3`
- `FluidR3_GM.sf2`
- `GeneralUser_GS.sf2`
- `default.sf2`

Or pass an explicit path:

```bash
python main.py "g_funk at 94 bpm" --soundfont "C:\Path\To\Your.sf2"
```

### Recommended SoundFonts

#### FluidR3_GM (free, MIT license)
- **Source**: [MuseScore SoundFont Repository](https://github.com/musescore/MuseScore/tree/master/share/sound)
- **License**: MIT
- **Size**: ~148 MB
- **Quality**: Balanced, general-purpose

#### FluidR3Mono_GM.sf3 (free, MIT license; compact)
- **Source**: [MuseScore SoundFont Repository](https://github.com/musescore/MuseScore/tree/master/share/sound)
- **License**: MIT / FluidR3-derived notices in the upstream repository
- **Size**: ~23 MB
- **Quality**: Compact General MIDI proof asset; useful for local validation

#### GeneralUser GS (free, custom license)
- **Source**: [GeneralUser GS Official Site](http://schristiancollins.com/generaluser.php)
- **License**: GeneralUser GS License (free for most uses, read terms)
- **Size**: ~30 MB
- **Quality**: Lightweight, good coverage

#### Timbres Of Heaven (free, custom license)
- **Source**: [Timbres Of Heaven on SourceForge](https://sourceforge.net/projects/timbres-of-heaven/)
- **License**: Read license.txt in archive
- **Size**: ~369 MB (full version)
- **Quality**: High-quality, expressive

**Important**: Always verify the license of any SoundFont you download. The above are commonly used for personal/educational projects.

---

## Verification

### Diagnose Your Setup

Run:

```bash
python main.py --diagnose-audio
```

Expected output (FluidSynth + SoundFont installed):

```json
{
  "schema_version": 1,
  "fluidsynth": {
    "available": true,
    "version": "FluidSynth runtime version 2.4.7..."
  },
  "soundfont": {
    "cli_arg": null,
    "discovered": "./assets/soundfonts/FluidR3Mono_GM.sf3",
    "soundfonts_dir": "C:\\dev\\MUSE-ai\\MUSE\\assets\\soundfonts",
    "soundfonts_dir_exists": true
  },
  "instruments": {
    "default_dir": "C:\\dev\\MUSE-ai\\MUSE\\instruments",
    "default_dir_exists": true,
    "default_audio_file_count": 42,
    "cli_paths": []
  },
  "expansions": {
    "default_dir": "C:\\dev\\MUSE-ai\\expansions",
    "default_dir_exists": true
  }
}
```

**If FluidSynth is not found**:
- `fluidsynth.available` will be `false`
- Audio will fall back to procedural synthesis (lower quality)

**If SoundFont is not found**:
- `soundfont.discovered` will be `null`
- FluidSynth will be skipped even if installed

---

## Strict Studio Mode (Optional)

If you want to **fail** when a SoundFont render isn't possible:

```bash
python main.py "ethiopian groove" --require-soundfont
```

This disables procedural fallback for the final WAV render (MIDI will still be generated).

**Use cases**:
- CI/CD quality gates
- Production environments where procedural synthesis quality is unacceptable
- Debugging FluidSynth/SoundFont configuration issues

**When `--require-soundfont` is set**:
- Render fails immediately if FluidSynth is unavailable
- Render fails immediately if no SoundFont is discovered
- Exit code is non-zero
- `render_report.json` shows `renderer_path: "none"` and `skip_reason: "require_soundfont"`
