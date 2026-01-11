# SoundFonts

This project can render MIDI to audio in two ways:

- **FluidSynth + SoundFont (.sf2)** (recommended): higher-quality, realistic timbres
- **Procedural fallback**: offline-first, no external assets, but noticeably less realistic

## Where to put SoundFonts

Place your `.sf2` file(s) in this folder:

- `assets/soundfonts/`

The renderer auto-searches common names such as:
- `FluidR3_GM.sf2`
- `GeneralUser_GS.sf2`
- `default.sf2`

Or you can pass an explicit path:

- `python main.py "g_funk at 94 bpm" --soundfont "C:\\Path\\To\\Your.sf2"`

## No bundled SoundFonts

This repo intentionally does **not** ship any SoundFont binaries.
Download a SoundFont you have rights to use, then place it here.

## Diagnose your setup

Run:

- `python main.py --diagnose-audio`

That prints a JSON report showing:
- whether `fluidsynth` is available
- which `.sf2` was discovered (if any)
- whether instrument/sample folders are present

## Strict studio mode (optional)

If you want to **fail** when a SoundFont render isn’t possible:

- `python main.py "ethiopian groove" --require-soundfont`

This disables procedural fallback for the final WAV render (MIDI will still be generated).