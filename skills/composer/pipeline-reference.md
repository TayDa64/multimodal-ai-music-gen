# Pipeline Reference (Composer)

This project already has an orchestration specification in:
- docs/muse-specs/tasks/TASK-DECOMPOSITION-P6.md

Use the Score Plan schema as the interface between Copilot and the deterministic renderer.
The renderer (PromptParser, Arranger, MidiGenerator, AudioRenderer) should not change behavior.

## Mapping Notes
- Score Plan `sections` map to Arrangement sections and PerformanceScore sections.
- Score Plan `chord_map` can be injected into PerformanceScore chord_map.
- Score Plan `tracks` map to agent roles and instrument selection.
- Score Plan `seed` (if provided) should be used for reproducibility.

## Defaults
- If no chord_map provided, the Arranger generates chords as usual.
- If no tension_curve provided, the Arranger generates it as usual.
- If track activation is missing, use standard section activation rules.
