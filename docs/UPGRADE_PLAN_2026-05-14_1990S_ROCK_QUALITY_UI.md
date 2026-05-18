# 1990s Rock Quality Degradation and UI Upgrade Plan — 2026-05-14

## Purpose

Document a source-grounded investigation plan for the 1990s rock quality regression and the related JUCE UI polish upgrade. This plan is intentionally documentation/state only: it records what the smoke run proved, what must be preserved, and the smallest future PR sequence to make a prompt for a 1990s rock band route through rock-aware parsing, arrangement, strategy, rendering, analysis, and UI affordances before judging musicality.

## Scope and guardrails

- **Plan status:** this document started as a documentation/state plan and now also records the implementation/proof milestones completed from it.
- **Primary quality goal:** the prompt below should produce a rock/band arrangement with guitars, bass guitar, live drums, verse/chorus/bridge structure, 100 BPM, E minor, and a rendered audio artifact.
- **Primary safety goal:** do not regress existing high-priority genres and workflows while adding rock coverage. The fix must connect all genre layers instead of making one isolated parser or renderer tweak.

## Smoke command summary and artifacts

### Prompt under investigation

```text
1990's era rock song with crunchy electric guitar, live drums, bass guitar, verse chorus bridge, energetic band performance, 100 BPM in E minor
```

### Exact FluidSynth smoke isolation implementation

Task `exact-rock-fluidsynth-smoke-isolation-046` adds a default-off proof path for the exact prompt without changing normal generation behavior:

- `main.py` now accepts `--skip-default-instruments` and `--skip-expansions` (also available as `run_generation(..., skip_default_instruments=True, skip_expansions=True)`). These switches prevent automatic `./instruments` loading and `../expansions` scanning/registration only when explicitly requested.
- `scripts/smoke_1990s_rock.ps1 -FluidSynthIsolation` passes those two skips plus `--require-soundfont`; `-SoundFont <path>` forwards an explicit SoundFont to `main.py`.
- Normal `-StrictAudio` still gates audio/render-analysis success only. The extra FluidSynth renderer proof is gated only when `-FluidSynthIsolation` is present and requires `renderer_diagnostics.renderer_path == "fluidsynth"`, `fluidsynth_attempted == true`, `fluidsynth_success == true`, empty `fluidsynth_skip_reason`, and a non-null `soundfont_path`.

Expected exact FluidSynth smoke command:

```powershell
Set-Location c:\dev\MUSE-ai\MUSE
.\scripts\smoke_1990s_rock.ps1 -StrictAudio -FluidSynthIsolation -SoundFont assets\soundfonts\FluidR3Mono_GM.sf3 -OutputRoot output\_diagnostics -DurationBars 16 -Seed 199001
```

The SoundFont is a local ignored artifact; do not stage or vendor it. A successful renderer-path proof writes `smoke_summary.json` with `fluidsynth_isolation_failed: false` and renderer diagnostics confirming the FluidSynth path.

Runtime proof from the first exact isolated smoke:

- Artifact directory: `output\_diagnostics\rock_1990s_20260514_160450`
- Summary: `smoke_summary.json`
- Render report: `rock_100.0bpm_Eminor_20260514_160452_render_report.json`
- Renderer diagnostics:
  - `renderer_path="fluidsynth"`
  - `require_soundfont=true`
  - `fluidsynth.available=true`
  - `fluidsynth.attempted=true`
  - `fluidsynth.success=true`
  - `fluidsynth.skip_reason=null`
  - `soundfont_path="C:\dev\MUSE-ai\MUSE\assets\soundfonts\FluidR3Mono_GM.sf3"`
  - `custom_audio.custom_drums_loaded=0`
  - `instrument_library.loaded=false`
  - `expansions.loaded=false`
  - `pipeline_stages.fluidsynth_file_mastering.status="applied"`

Important quality follow-up: the isolation proof succeeded, but the combined `-StrictAudio` quality gate still reported `strict_audio_failed=true` because the full SoundFont render failed rock audio analysis (`genre_match_score=0.58`, spectral centroid `5649 Hz` above the 1000–4500 Hz target, and `snare_or_clap` not detected). That is no longer a renderer-selection/bootstrap problem; it becomes the next mastering/analyzer/instrument-balance priority.

### FluidSynth strict rock quality fix — 2026-05-15

Task `fluidsynth-rock-strict-quality-047` fixed the exact isolated FluidSynth render quality gate without weakening the renderer-path proof:

- `multimodal_gen/output_analyzer.py` keeps the existing aggregate snare/clap energy rule, but adds an audio-only mid-band transient fallback for GM/SoundFont rock kits. This catches real snare backbeats when bright cymbal/air energy and kick lows dominate aggregate HPSS percussive energy. The fallback does **not** inspect MIDI metadata.
- `multimodal_gen/audio_renderer.py` adds rock-family-only FluidSynth file-mastering tone shaping before final soft clipping/gain staging: a conservative high shelf (`-6.0 dB @ 5000 Hz`) and low shelf (`-0.75 dB @ 90 Hz`). The render report records this as `pipeline_stages.fluidsynth_file_mastering.rock_tone_shaping`.
- Regression coverage was added for GM-style snare detection in hat-heavy live drum mixes, the no-snare kick/hat negative case, and the rock FluidSynth tone-shaping helper.

Pre-fix measurement on `output\_diagnostics\rock_1990s_20260514_160450` showed the quality failure was not missing MIDI drums: GM snare note 38 appeared 48 times with mean velocity `88.8`, and snare-aligned mid-band RMS averaged `0.091816`. The old detector still reported `has_snare_or_clap=false` because its full-file mid-band/percussive ratio was only `0.097` against the historical `>0.300` gate.

Post-fix exact isolated FluidSynth smoke proof:

- Command:

  ```powershell
  Set-Location C:\dev\MUSE-ai\MUSE
  $env:PATH = 'C:\dev\MUSE-ai\tools\fluidsynth-2.4.7-win10-x64\bin;' + $env:PATH
  .\scripts\smoke_1990s_rock.ps1 -StrictAudio -FluidSynthIsolation -SoundFont 'assets\soundfonts\FluidR3Mono_GM.sf3' -OutputRoot 'output\_diagnostics' -DurationBars 16 -Seed 199001
  ```

- Artifact directory: `output\_diagnostics\rock_1990s_20260514_223641`
- Summary: `smoke_summary.json`
- Render report: `rock_100.0bpm_Eminor_20260514_223643_render_report.json`
- Smoke gates:
  - `exit_code=0`
  - `strict_audio_failed=false`
  - `fluidsynth_isolation_failed=false`
  - `renderer_path="fluidsynth"`
  - `fluidsynth.success=true`
  - `fluidsynth.skip_reason=null`
  - `audio_analysis.passed=true`
  - `audio_analysis.genre_match_score=1.0`
- Rendered-audio analysis after the fix:
  - `spectral.centroid_hz=4461.1` within the rock target upper bound of `4500`
  - `spectral.sub_bass_energy_ratio=0.1585` below the rock ceiling of `0.16`
  - `drums.has_kick=true`
  - `drums.has_snare_or_clap=true`
  - `drums.has_hihats=true`
  - `drums.percussive_ratio=0.215`

Focused verification for the code slice: `tests/test_output_analyzer.py tests/test_audio_renderer.py tests/test_render_report_schema.py -q` passed (`103 passed`, with existing librosa/audioread warnings).

### FluidSynth renderer profile registry — 2026-05-15

Task `fluidsynth-renderer-profiles-048` moves the hard-coded rock FluidSynth tone shelves into `multimodal_gen/fluidsynth_profiles.py`, an immutable profile/genre registry used only by file-level FluidSynth mastering. Rock-family profiles keep the exact strict-quality shelf diagnostic `high_shelf=-6.0dB@5000Hz;low_shelf=-0.75dB@90Hz`, while initial classical, jazz, and trap/modern-beat profiles are discoverable no-ops. The integration is additive: it records a `fluidsynth_file_mastering.profile` diagnostic, does not make FluidSynth mandatory, does not vendor SoundFonts, and does not change SoundFont discovery, FluidSynth command ordering, renderer selection gates, or procedural/custom/expansion fallback behavior.

Profile-registry regression proof: focused tests passed (`35 passed, 2 existing warnings`), post-verifier returned `PASS`, and the exact strict FluidSynth smoke remained green on `output\_diagnostics\rock_1990s_20260515_084307` with `renderer_path=fluidsynth`, `strict_audio_failed=false`, `fluidsynth_isolation_failed=false`, `audio_analysis.passed=true`, `fluidsynth_file_mastering.profile=rock:rock`, and the preserved rock tone diagnostic `high_shelf=-6.0dB@5000Hz;low_shelf=-0.75dB@90Hz`.

### FluidSynth profile measurement matrix — 2026-05-15

Task `fluidsynth-genre-profile-policies-049` adds `scripts/smoke_fluidsynth_profile_matrix.ps1` as the safe baseline step before any non-rock FluidSynth tone shelves. The script runs explicit-SoundFont, isolated runtime cases with `--skip-default-instruments`, `--skip-expansions`, and `--require-soundfont`, using a rock control plus first-class cinematic/classical and trap/modern-beat routes. Each case captures stdout/stderr and parses `project_metadata.json`, the render report, renderer diagnostics, `audio_analysis` metrics, and `pipeline_stages.fluidsynth_file_mastering.profile` into `matrix_summary.json`.

The matrix's default failure policy gates only process/render-path/profile proof (`renderer_path="fluidsynth"`, `fluidsynth.attempted/success == true`, empty skip reason, present SoundFont path, expected profile diagnostics, and expected absence/presence of tone-shaping diagnostics). It records `audio_analysis.passed == false` as measurement data for later policy tuning rather than failing the whole matrix. At task 049 time, generic jazz was deferred in the summary because the registry had a jazz no-op profile, but the parser/runtime did not yet expose a first-class generic jazz route comparable to cinematic/classical or trap.

Runtime proof: `output\_diagnostics\fluidsynth_profile_matrix\matrix_20260515_090547\matrix_summary.json` completed with `proof_passed=true`, `failure_count=0`, and three explicit FluidSynth cases. The rock control parsed as `rock` with `profile=rock:rock` and the exact tone diagnostic, the cinematic/classical case parsed as `cinematic` with `profile=classical:classical` and no tone-shaping diagnostics, and the trap/modern-beat case parsed as `trap` with `profile=trap_modern_beat:modern_beat` and no tone-shaping diagnostics.

### Generic jazz runtime route — 2026-05-15

Task `generic-jazz-runtime-route-051` closes the deferred matrix route for `small-combo jazz quartet with walking bass, ride cymbal, piano comping, 120 BPM in Bb major`. Generic jazz now parses as `jazz`, uses combo-safe piano/bass/brass defaults with ride-led acoustic drums and no 808/hi-hat-roll defaults, has a dedicated `JazzStrategy` plus jazz arrangement template, and runs as a runtime FluidSynth matrix case expecting the existing no-op profile diagnostic `jazz:jazz` with no tone-shaping diagnostics. `ethio_jazz` priority and Ethiopian instrument semantics remain separate.

Runtime proof: `output\_diagnostics\fluidsynth_profile_matrix\matrix_20260515_101211\matrix_summary.json` completed with `aggregate.proof_passed=true`, `failure_count=0`, `case_count=4`, and `deferred_case_count=0`. The new `generic_jazz` case parsed as `jazz`, rendered through `renderer_path=fluidsynth` with `fluidsynth.attempted/success=true`, recorded `profile=jazz:jazz`, kept `actual_tone_shaping=null` and `actual_rock_tone_shaping=null`, and passed audio analysis with score `0.923`. Post-verifier also confirmed generic jazz `--no kick` / `--no hihat` exclusions are not reintroduced by combo-kit defaults.

### Jazz horn realism / sax lead polish - 2026-05-15

Task `jazz-horn-realism-sax-lead-polish-053` addresses the first generic-jazz listening artifact where `warm saxophone lead` collapsed to generic `brass`, produced a Melody track on GM program `56` (Trumpet), and allowed lead velocities to hit `127`. The code-level fix is intentionally semantic and local: parser horn keywords now keep explicit `sax`/`trumpet`/`trombone` identities while leaving `brass`/`horns`/`brass section` generic, instrument resolution has direct saxophone/alto/tenor sax aliases, and Melody routing checks explicit sax/trumpet/trombone before generic brass. Generic jazz still uses the existing no-op FluidSynth profile `jazz:jazz`; no renderer or FluidSynth profile shelves were added. A jazz-only horn melody velocity normalization/cap keeps explicit sax/trumpet/trombone/brass lead notes below clipping while preserving relative phrase dynamics.

Post-change sax listening/runtime proof:

- Summary: `output\_diagnostics\jazz_sax_lead_polish_20260515_120838\jazz_sax_lead_polish_summary.json`
- WAV: `output\_diagnostics\jazz_sax_lead_polish_20260515_120838\generic_jazz_sax_lead\jazz_120.0bpm_Bflatmajor_20260515_120840.wav`
- MIDI: `output\_diagnostics\jazz_sax_lead_polish_20260515_120838\generic_jazz_sax_lead\jazz_120.0bpm_Bflatmajor_20260515_120840.mid`
- Render report: `output\_diagnostics\jazz_sax_lead_polish_20260515_120838\generic_jazz_sax_lead\jazz_120.0bpm_Bflatmajor_20260515_120840_render_report.json`
- Runtime gates: `proof_passed=true`, `exit_code=0`, `renderer_path=fluidsynth`, `fluidsynth_success=true`, `skip_reason=null`, and `profile=jazz:jazz`.
- Sax routing proof: parsed instruments were `[piano, sax, bass]`; the Melody track used GM program `65`, marker `instrument:Sax`, and `velocity_max=112`.
- Listening/analysis proof: `audio_analysis.passed=true`, `genre_match_score=0.95`, and `spectral.centroid_hz=3404.3`; the remaining warning is brightness-related and no longer a failed render or trumpet-routing issue.
- Focused tests passed: `68 passed`, with `2` dependency warnings.
- Guardrails: `audio_renderer.py` and `fluidsynth_profiles.py` were unchanged, and no jazz FluidSynth shelves were added.

Task `jazz-sax-breath-range-mastering-054` keeps the first follow-up at MIDI level before final profile adjustment: the remaining brightness warning was traced to explicit sax leads using the piano fallback melody octave (`84-91` in the task-053 proof) plus high Melody CC74 brightness near `94`. Sax/alto-sax aliases now use warm jazz lead ranges and tenor sax sits lower, while the exact generic jazz sax route keeps GM program `65`, marker `instrument:Sax`, the velocity cap, preserved CC1/CC11 expression, and a jazz-sax-only CC74 ceiling. A second measured sub-slice initially adopted the jazz-only FluidSynth brightness policy after the offline candidate `high_shelf=-3.0dB@4000Hz` helped by reducing spectral centroid from `3367.0` to `2670.0`, produced score `1.0`, and removed analyzer issues; the profile diagnostic remained `jazz:jazz` and the provisional tone diagnostic was `high_shelf=-3.0dB@4000Hz`. The integrated `-3 dB` shelf proof still warned at centroid `3033.1` against the strict `2800` target and identified the remaining bright source as piano comping (`Chords` Piano program `0`, pitch max `87`, CC74 max `94`), so generic-jazz keyboard comping warmth then removed the high-tension octave lift for piano/rhodes/electric-piano chord comping and added a chord-track CC74 cap. After those sax range/CC and piano comping source controls were in place (Melody program `65`, pitch max `79`, CC74 max `78`; Chords Piano program `0`, pitch max `75`, CC74 max `78`), the next integrated render still warned at centroid `2973.9` against the strict `2800` jazz target. The first measured full-mix jazz profile candidate, `high_shelf=-4.5dB@4000Hz`, was supported by the offline full analyzer candidate at centroid `2468.2`, score `1.0`, `passed=true`, and `issues=null`, but the actual integrated FluidSynth render through the real nonlinear chain still warned at centroid `2808.8`, just `8.8 Hz` above the strict jazz ceiling. The final robust policy is therefore exactly `high_shelf=-5.0dB@4000Hz`: the smallest rounded 4 kHz margin from the integrated slope, still gentler than the rock `high_shelf=-6.0dB@5000Hz` shelf, and chosen without weakening the already-fixed sax/source controls or jazz ride performance. The profile diagnostic remains `jazz:jazz`, the tone diagnostic is now `high_shelf=-5.0dB@4000Hz`, and `audio_renderer.py` plus analyzer targets remain untouched. The final integrated FluidSynth proof then passed with summary `output\_diagnostics\jazz_sax_breath_range_mastering_final_profile5_20260515_164513\jazz_sax_breath_range_mastering_final_profile5_summary.json`, WAV `output\_diagnostics\jazz_sax_breath_range_mastering_final_profile5_20260515_164513\generic_jazz_sax_lead\jazz_120.0bpm_Bflatmajor_20260515_164516.wav`, MIDI `output\_diagnostics\jazz_sax_breath_range_mastering_final_profile5_20260515_164513\generic_jazz_sax_lead\jazz_120.0bpm_Bflatmajor_20260515_164516.mid`, render report `output\_diagnostics\jazz_sax_breath_range_mastering_final_profile5_20260515_164513\generic_jazz_sax_lead\jazz_120.0bpm_Bflatmajor_20260515_164516_render_report.json`, `proof_passed=true`, `renderer_path=fluidsynth`, `fluidsynth_success=true`, `profile=jazz:jazz`, `tone_shaping=high_shelf=-5.0dB@4000Hz`, `score=1.0`, `spectral.centroid_hz=2755.9`, and `issues=[]`; source guardrails also remained inside bounds (`Melody` program `65`, pitch max `79`, velocity max `112`, CC74 max `78`; `Chords` Piano program `0`, pitch max `75`, CC74 max `78`).

Task `rock-jazz-post054-cross-genre-listening-validation-055` is a measurement-only checkpoint after the task-054 jazz shelf: no source/profile code changed. The paired FluidSynth proof summary is `output\_diagnostics\rock_jazz_post054_validation_055\pair_20260515_230633\rock_jazz_post054_validation_summary.json` with `proof_passed=true` and `proof_failures=[]`. The exact rock control used seed `199001` and kept `renderer_path=fluidsynth`, `profile=rock:rock`, `tone_shaping=high_shelf=-6.0dB@5000Hz;low_shelf=-0.75dB@90Hz`, `score=1.0`, `spectral.centroid_hz=4461.1`, `sub_bass_energy_ratio=0.1585`, and live drum flags true; this is still passing but close to strict boundaries. The jazz sax guard used seed `54054` in `generic_jazz_sax_lead_retry2` after two interrupted retry folders, kept `profile=jazz:jazz`, `tone_shaping=high_shelf=-5.0dB@4000Hz`, `score=1.0`, `spectral.centroid_hz=2755.9`, and `issues=[]`, while preserving sax/comping source controls (`Melody` program `65`, pitch max `79`, velocity max `112`, CC74 max `78`; `Chords` Piano program `0`, pitch max `75`, CC74 max `78`). Because both paired gates passed, task 055 records the next risk as rock boundary proximity rather than making speculative implementation changes.


Task `rock-boundary-repeatability-validation-056` is a measurement-only repeatability checkpoint for the boundary-close exact-rock result from task 055: no source/profile/analyzer code changed. The fresh direct-`main.py` FluidSynth proof summary is `output\_diagnostics\rock_boundary_repeatability_056\repeat_20260516_002955\rock_boundary_repeatability_summary.json` with `proof_passed=true`, `proof_failures=[]`, and three regenerated seeds (`199001`, `199002`, `199003`) using the exact 1990s rock prompt, 16 bars, isolated default instruments/expansions, and `FluidR3Mono_GM.sf3`. Every run kept `renderer_path=fluidsynth`, `profile=rock:rock`, `tone_shaping=high_shelf=-6.0dB@5000Hz;low_shelf=-0.75dB@90Hz`, `score=1.0`, parsed `rock` at `100 BPM` in `E minor`, guitar/bass/live drum routing, and empty issues. The per-seed measurements were: seed `199001` centroid `4461.1` (margin `38.9` Hz) and sub-bass `0.1585` (margin `0.0015`); seed `199002` centroid `4214.4` (margin `285.6` Hz) and sub-bass `0.1579` (margin `0.0021`); seed `199003` centroid `4196.2` (margin `303.8` Hz) and sub-bass `0.1557` (margin `0.0043`). Aggregate worst case remains green but boundary-close (`centroid_max_hz=4461.1` vs `4500`, `sub_bass_max=0.1585` vs `0.16`), so task 056 closes without tuning and keeps future rock work scoped to a new measured failure if one appears.

Task `cross-genre-maturity-matrix-baseline-plan-057` adds the docs-only [cross-genre maturity matrix and baseline validation plan](CROSS_GENRE_MATURITY_MATRIX_2026-05-16.md): it records exact 1990s rock as stable v1 / `PASS-WATCH`, decomposes rock-family masterclass gaps, and defines the next measured runbook without source/profile/analyzer changes. The next runtime slice is Task 058, which should run the rock-family baseline measurement from that plan before any tuning.

Task `rock-family-baseline-measurement-058` records the completed measurement-only direct-`main.py` FluidSynth rock-family run in [the Task 058 aggregation report](ROCK_FAMILY_BASELINE_2026-05-16_TASK_058.md). The summary is `output\_diagnostics\rock_family_baseline_057\run_20260516_014229\rock_family_baseline_058_summary.json` from repo head `b2945a6`, with `preflight.proof_passed=true`, `renderer_path=fluidsynth`, `profile=rock:rock`, tone `high_shelf=-6.0dB@5000Hz;low_shelf=-0.75dB@90Hz`, isolated default instruments/expansions, and required `assets\soundfonts\FluidR3Mono_GM.sf3`. Aggregate status is `FAIL-MEASURED` across `5` planned cases and `13` runs (`1` pass, `0` watch, `4` measured failures, `blocked=false`): `grunge_baseline` passed on seed `57102`, while classic rock, punk rock, indie rock, and hard-rock-as-canonical-`rock` failed repeatably. The repeated failure is dominated by excess sub-bass, with centroid/brightness failures or boundary pressure in classic, indie, and hard-rock-as-rock. Task 058 made no source/profile/analyzer/parser/strategy/script/test/asset/output-diagnostic changes and performed no tuning; output diagnostics must remain ignored/uncommitted.

Task `rock-family-sub-bass-brightness-remediation-059` closes the first measured remediation slice with a profile-only rock FluidSynth change: `multimodal_gen/fluidsynth_profiles.py` now uses `high_shelf=-10.0dB@4000Hz;low_shelf=-4.0dB@90Hz` for `rock:rock`. Analyzer targets, parser/default routing, MIDI generation, rock strategy, arranger, scripts, assets, jazz `high_shelf=-5.0dB@4000Hz`, and no-op classical/trap/default profiles were preserved. Focused profile/renderer tests passed (`31 passed, 2 warnings`). The effective runtime proof is `output\_diagnostics\rock_family_remediation_059\effective_20260516_0742\rock_family_remediation_059_effective_summary.json`: `16` valid direct-`main.py`/FluidSynth rows passed (`failure_count=0`) across classic rock seeds `57101/57201/57301`, punk rock `57103/57203/57303`, indie rock `57104/57204/57304`, hard-rock-as-canonical-`rock` `57105/57205/57305`, grunge control `57102`, and exact 1990s rock controls `199001/199002/199003`. Every valid row kept `renderer_path=fluidsynth`, `fluidsynth.success=true`, `skip_reason=null`, `profile=rock:rock`, the exact tone diagnostic above, `audio_analysis.passed=true`, and no analyzer issues. The recovered aggregate spans centroid `3437.9–4337.2 Hz` and sub-bass `0.0944–0.1264`. An earlier full-matrix wrapper run produced six valid passes, then null/no-report process interruptions; those rows were rerun in smaller direct batches with an absolute SoundFont path, and a transient indie `require_soundfont` preflight row was replaced by a successful single-seed absolute retry.

Task `classic-rock-hammond-organ-workflow-060` started with the requested workflow prompt `classic rock anthem with crunchy electric guitar, Hammond organ, melodic bass guitar, live drums, verse chorus bridge, 108 BPM in A minor` before making further source changes. The pre-fix direct `main.py`/FluidSynth run (`output\_diagnostics\classic_rock_workflow_060\run_20260516_075337`) exited successfully and passed audio analysis with `renderer_path=fluidsynth`, `profile=rock:rock`, and the Task 059 tone diagnostic, but it exposed a semantic arrangement gap: the explicit `Hammond organ` cue was absent from parsed instruments and the MIDI had no GM organ program. The fix is intentionally narrow and semantic rather than another mastering change: `prompt_parser.py` now recognizes organ/Hammond/drawbar/tonewheel aliases, and `midi_generator.py` adds a raw-prompt-gated rock-family auxiliary organ bed while preserving the guitar chord track and electric bass routing. Focused parser/MIDI tests passed (`25 passed`), and the renderer/profile guard subset passed (`56 passed`, with the same dependency warnings). The post-fix proof is `output\_diagnostics\classic_rock_workflow_060\post_hammond_fix_60060\classic_rock_108.0bpm_Aminor_20260516_080241_render_report.json`: `exit_code=0`, parsed instruments `organ/guitar/bass`, MIDI tracks include Bass GM `34`, Chords GM `30` with `instrument:Guitar`, Organ GM `16` with `instrument:Organ`, and Melody GM `80`; the rendered WAV kept `renderer_path=fluidsynth`, `fluidsynth.success=true`, `skip_reason=null`, `profile=rock:rock`, `tone_shaping=high_shelf=-10.0dB@4000Hz;low_shelf=-4.0dB@90Hz`, `audio_analysis.passed=true`, `score=1.0`, centroid `3564.4 Hz`, sub-bass `0.1017`, and live drum flags true.

Task `classic-rock-session-graph-manifest-061` closes the metadata/UI parity gap discovered after Task 060: although the MIDI/audio proof was correct, the saved `session_manifest.json` still labeled the primary chords graph track as `Organ` and duplicated `Bass` as a lead because `SessionGraphBuilder._create_tracks` assigned roles by parsed-instrument order. The fix is session-graph-only: explicit rock-family guitar now owns the primary `Guitar`/`chords` track on channel `2`, bass aliases are not duplicated beyond the base `Bass` track, and explicit organ/Hammond cues become a separate `Organ`/`pad` track on channel `4`; the raw organ cue uses word-boundary matching so `organic` does not trigger an organ track. Focused tests passed (`3 passed`) and the guard subset passed (`35 passed`, with the same dependency warnings). The direct workflow proof is `output\_diagnostics\classic_rock_workflow_061\session_graph_manifest_60061\classic_rock_108.0bpm_Aminor_20260516_083341_render_report.json`: `exit_code=0`, `renderer_path=fluidsynth`, `profile=rock:rock`, unchanged tone diagnostic `high_shelf=-10.0dB@4000Hz;low_shelf=-4.0dB@90Hz`, `audio_analysis.passed=true`, score `1.0`, centroid `3534.1 Hz`, sub-bass `0.0936`, and live drum flags true. The corresponding `session_manifest.json` now records exactly `Drums`/`drums`/channel `9`, `Bass`/`bass`/channel `1`, `Guitar`/`chords`/channel `2`, and `Organ`/`pad`/channel `4`, with no `Bass` lead duplicate.

Task `classic-rock-filter-procedural-samples-062` closes the next side-artifact mismatch from the same real workflow: the rendered MIDI/audio and session manifest were correct, but `main.py` still generated the legacy full procedural drum kit and listed `808_kick.wav`/`clap.wav` in project metadata even though the parsed classic-rock drum elements excluded `808` and `clap`. The fix keeps fallback behavior while making workflow artifacts semantic: `AssetsGenerator.generate_drum_kit()` now accepts optional parsed drum elements, preserves the legacy full kit when called with no argument, preserves requested `808`/`clap` for trap or explicit prompts, and filters rock-family workflow sample generation to supported parsed elements. Focused tests passed (`13 passed`) and the Task 059-061 guard subset passed (`36 passed`, with the same dependency warnings). The direct proof is `output\_diagnostics\classic_rock_workflow_062\filtered_samples_60062\classic_rock_108.0bpm_Aminor_20260516_085202_render_report.json`: `exit_code=0`, `renderer_path=fluidsynth`, `profile=rock:rock`, unchanged tone diagnostic `high_shelf=-10.0dB@4000Hz;low_shelf=-4.0dB@90Hz`, `audio_analysis.passed=true`, score `1.0`, centroid `3517.2 Hz`, sub-bass `0.0983`, and live drum flags true. The corresponding `project_metadata.json` now lists only `kick.wav`, `snare.wav`, `hihat_closed.wav`, and `hihat_open.wav` under `current.outputs.samples`; the samples directory contains those same four files, with no `808_kick.wav` or `clap.wav`, while the Task 061 session manifest contract remains `Drums`/`Bass`/`Guitar chords`/`Organ pad`.

Task `cinematic-classical-orchestral-manifest-063` moves beyond rock into the cross-genre matrix's next Tier B priority: cinematic/classical. The pre-fix baseline for `cinematic orchestral film score with strings, brass, choir, timpani, evolving sections, 96 BPM in D minor` already parsed as `cinematic`, generated MIDI with explicit orchestral `Strings`/`Brass`/`Choir`/`Timpani`, rendered through FluidSynth with `profile=classical:classical`, and passed audio analysis, so the fix deliberately avoided renderer/profile/analyzer tuning. The gap was metadata and short-form structure: the saved session manifest omitted Choir/Timpani, added a phantom Bass track, and a 16-bar request inflated to 32 bars. `SessionGraphBuilder` now has an orchestral-family branch that preserves explicit orchestral tracks without role de-duplication, avoids Bass unless explicitly requested, and aligns session channels with the MIDI contract; `Arranger` now has a cinematic/classical <=16-bar short arc; and `CinematicStrategy` now owns pure `classical` prompts. Focused tests passed (`20 passed`), and the rock/profile/renderer guard subset passed (`33 passed`, with the same dependency warnings). The direct proof is `output\_diagnostics\cinematic_classical_workflow_063\post_orchestral_manifest_63063\cinematic_96.0bpm_Dminor_20260516_104540_render_report.json`: `exit_code=0`, `renderer_path=fluidsynth`, `fluidsynth.success=true`, `render_status.success=true`, `profile=classical:classical`, no `tone_shaping`/`rock_tone_shaping`, `audio_analysis.passed=true`, score `1.0`, centroid `2357.4 Hz`, and sub-bass `0.4504`. The corresponding metadata now records exactly four 4-bar sections (`intro`, `verse`, `buildup`, `chorus`) for `16` total bars, and `session_manifest.json` records `Drums`/`drums`/channel `9`, `Strings`/`pad`/channel `2`, `Brass`/`lead`/channel `5`, `Choir`/`pad`/channel `6`, and `Timpani`/`percussion`/channel `8`, with no Bass track.

Task `trap-modern-manifest-arrangement-064` continues the cross-genre rotation into Tier B priority #2: trap/modern beat. The pre-fix baseline for `dark trap modern beat with 808 bass, snare, hihat rolls, sparse melody, 140 BPM in C minor` already parsed as `trap`, preserved `808`/`bass` plus `808`/`snare`/`hihat`/`hihat_roll`, generated explicit requested samples (`808_kick.wav`, `snare.wav`, `hihat_closed.wav`), rendered through FluidSynth with `profile=trap_modern_beat:modern_beat`, and passed audio analysis, so the fix deliberately avoided analyzer, renderer, profile, parser, and MIDI tuning. The deterministic gap was metadata and short-form structure: a 16-bar request inflated to 28 bars, and `session_manifest.json` represented parsed `808` as a misleading lead track instead of the MIDI's Bass channel 1 plus Melody channel 3 contract. `Arranger` now has a trap/modern-beat <=16-bar compact arc (`intro`, `drop`, `variation`, `drop`, four bars each), and `SessionGraphBuilder` now has a trap/modern-beat branch that records `Drums`/`drums`/channel `9`, `Bass`/`bass`/channel `1`, and `Melody`/`lead`/channel `3`, with no `808` lead track. Focused tests passed (`24 passed`) and the profile/renderer/rock-Hammond guard subset passed (`33 passed`, with the same dependency warnings). The direct proof is `output\_diagnostics\trap_modern_workflow_064\post_manifest_64064\trap_140.0bpm_Cminor_20260518_085051_render_report.json`: `exit_code=0`, `renderer_path=fluidsynth`, `fluidsynth.success=true`, `render_status.success=true`, `profile=trap_modern_beat:modern_beat`, `audio_analysis.passed=true`, score `0.752`, centroid `5940.6 Hz`, sub-bass `0.7388`, percussive ratio `0.12`, and onset density `5.61`. The remaining brightness and drum-presence warnings are recorded measurement data for a later quality slice, not a reason to relax analyzer targets in this metadata/arrangement task.

Task `rnb-neosoul-manifest-midi-profile-065` continues the cross-genre rotation into Tier B priority #3: R&B / neo-soul / trap-soul. The pre-fix baseline for `neo-soul R&B groove with warm electric piano, bass, laid-back drums, lush chords, 82 BPM in F minor` already parsed as `neo_soul`, generated sensible laid-back drum samples (`kick.wav`, `snare.wav`, `hihat_closed.wav`) without trap 808/clap leakage, rendered through FluidSynth, and passed audio analysis, so the fix focused on deterministic semantics instead of analyzer relaxation. The baseline gaps were: a 16-bar request inflated to 32 bars; `session_manifest.json` named the chords track `Piano`, duplicated `Bass` as a lead, and implied a lead/melody that the prompt did not request; MIDI routed bass through synth-bass program `38` and added a default synth `Melody` track; and FluidSynth reported `profile=default:default` instead of an explicit R&B-family policy. `Arranger` now has an R&B-family <=16-bar arc (`verse`, `chorus`, `bridge`, `chorus`, four bars each); `SessionGraphBuilder` records only `Drums`/`drums`/channel `9`, `Bass`/`bass`/channel `1`, and `Rhodes`/`chords`/channel `2` for this prompt; `MidiGenerator` routes R&B-family bass to electric bass program `33` with an `instrument:Bass Guitar` marker and suppresses default melody unless a melody/lead/hook/vocal-chop cue is explicit; and `fluidsynth_profiles.py` adds a no-op `rnb_neosoul:neo_soul` profile family with no tone shelves. Focused tests passed (`18 passed`), and the recent cross-genre guard subset passed (`20 passed`). The direct proof is `output\_diagnostics\rnb_neosoul_workflow_065\post_contract_65065\neo_soul_82.0bpm_Fminor_20260518_102914_render_report.json`: `exit_code=0`, `renderer_path=fluidsynth`, `fluidsynth.success=true`, `render_status.success=true`, `profile=rnb_neosoul:neo_soul`, `audio_analysis.passed=true`, score `0.994`, centroid `2788.7 Hz`, sub-bass `0.7443`, percussive ratio `0.067`, and onset density `2.31`. The remaining low drum-presence warning is recorded as later quality data; no analyzer target was relaxed. The MIDI proof has `Drums`, `Bass` program `33`, and `Chords` program `4`, with no `Melody` track; the manifest has no duplicate `Bass` lead and no phantom lead.

Task `lofi-boom-bap-deterministic-parity-066` continues the cross-genre rotation into Tier B priority #4: lofi / boom_bap / g_funk. The measured baseline for `lofi boom bap groove with dusty drums, warm bass, mellow keys, vinyl texture, 88 BPM in C minor` parsed as `boom_bap` with piano, bass, kick/snare/hihat/crash, and vinyl texture, but exposed deterministic workflow gaps before quality tuning: a 16-bar request inflated to 24 bars and six sections, `AssetsGenerator` had no `generate_vinyl_crackle()` instance method for the CLI sample path, and the first post-fix proof showed MIDI still emitted an unrequested default `Melody` track while `session_manifest.json` correctly showed only Drums/Bass/Keys/Vinyl. The fix keeps analyzer targets and audio renderer behavior unchanged: `AssetsGenerator` now has backward-compatible vinyl/rain texture wrappers around the existing module-level generators; `Arranger` has a lofi/boom_bap/g_funk <=16-bar arc (`intro`, `verse`, `variation`, `verse`, four bars each); `SessionGraphBuilder` records stable UI tracks `Drums`/`drums`/channel `9`, `Bass`/`bass`/channel `1`, `Keys`/`chords`/channel `2`, and `Vinyl`/`texture`/channel `4`; `MidiGenerator` suppresses lofi-family default melody unless a melody/lead/hook cue is explicit; and `fluidsynth_profiles.py` adds a no-op `lofi_boom_bap:boom_bap` profile family. Focused and guard tests passed (`30 passed`). The direct proof is `output\_diagnostics\lofi_boombap_workflow_066\post_contract_66066c\boom_bap_88.0bpm_Cminor_20260518_110551_render_report.json`: `exit_code=0`, `renderer_path=fluidsynth`, `fluidsynth.success=true`, `render_status.success=true`, `profile=lofi_boom_bap:boom_bap`, `audio_analysis.passed=true`, score `0.857`, centroid `3651 Hz`, percussive ratio `0.083`, and samples `kick.wav`, `snare.wav`, `hihat_closed.wav`, and `vinyl_crackle.wav`. The remaining brightness and drum-presence warnings are recorded as later quality data; no analyzer target was relaxed. The final MIDI proof has only `Meta`, `Drums`, `Bass` program `38`, and `Chords` program `0`, with no unrequested `Melody` track.

Task `house-ambient-pop-deterministic-parity-067` continues the cross-genre rotation into Tier B priority #5: house / ambient / pop. The measured baseline for `atmospheric house pop track with pads, four-on-floor drums, bass, hook synth, 124 BPM in A minor` parsed as `house` and already rendered through FluidSynth with `audio_analysis.passed=true`, but exposed deterministic parity gaps: the 16-bar request inflated to 28 bars and seven sections, the render report used `profile=default:default`, and `session_manifest.json` labeled `Synth` as lead on channel `2` while `Pad` was on channel `3`, which did not align with the MIDI `Chords`/channel `3` and explicit hook `Melody`/channel `4` contract. The fix keeps analyzer targets, MIDI generation, and audio rendering unchanged: `Arranger` now has a house/ambient/pop <=16-bar arc (`intro`, `buildup`, `drop`, `outro`, four bars each); `SessionGraphBuilder` records stable UI tracks `Drums`/`drums`/channel `9`, `Bass`/`bass`/channel `1`, `Pad`/`pad`/channel `2`, and `Hook Synth`/`lead`/channel `3`; and `fluidsynth_profiles.py` adds a no-op `house_ambient_pop:house` profile family. Focused and guard tests passed (`39 passed`). The direct proof is `output\_diagnostics\house_ambient_pop_workflow_067\post_contract_67067\house_124.0bpm_Aminor_20260518_111543_render_report.json`: `exit_code=0`, `renderer_path=fluidsynth`, `fluidsynth.success=true`, `render_status.success=true`, `profile=house_ambient_pop:house`, `audio_analysis.passed=true`, score `0.857`, and centroid `6307 Hz`. The remaining brightness warning is recorded as later quality data; no analyzer target was relaxed and no house tone shelf was added. The MIDI proof still includes the expected explicit hook-synth `Melody` track (`program 80`) alongside `Drums`, `Bass` (`program 38`), and `Chords` (`program 89`).

Task `ethiopian-family-deterministic-parity-068` completes the Tier B backend rotation with Ethiopian / ethio_jazz / ethiopian_traditional / eskista deterministic parity. The measured baseline for `Ethiopian jazz inspired groove with pentatonic melody, bass, hand percussion feel, 104 BPM in G minor` parsed as `ethio_jazz` and rendered through FluidSynth with `audio_analysis.passed=true`, but exposed deterministic contract gaps: the 16-bar request inflated to 32 bars and eight sections, the render report used generic `profile=jazz:jazz` with the jazz high shelf, `session_manifest.json` duplicated `Bass` as a `lead` track instead of showing the explicit pentatonic melody, and parsed `perc` generated zero procedural sample artifacts. The fix keeps analyzer targets, MIDI generation, and audio rendering unchanged: `Arranger` now has an Ethiopian-family <=16-bar arc (`intro`, `verse`, `variation`, `outro`, four bars each); `SessionGraphBuilder` records stable UI tracks `Drums`/`drums`/channel `9`, `Bass`/`bass`/channel `1`, and explicit `Melody`/`lead`/channel `3` while preserving explicit krar/masenqo/begena/washint/kebero roles for future prompts; `fluidsynth_profiles.py` adds a no-op `ethiopian_family:ethio_jazz` profile and removes `ethio_jazz` from the generic jazz shelf family; and `AssetsGenerator.generate_drum_kit()` maps `perc`/hand-percussion cues to `shaker.wav` plus `kebero` cues to kebero hand-drum samples. Focused and guard tests passed (`77 passed`). The direct proof is `output\_diagnostics\ethiopian_workflow_068\post_contract_68068\ethio_jazz_104.0bpm_Gminor_20260518_112600_render_report.json`: `exit_code=0`, `renderer_path=fluidsynth`, `fluidsynth.success=true`, `render_status.success=true`, `profile=ethiopian_family:ethio_jazz`, no tone-shaping diagnostic, `audio_analysis.passed=true`, score `0.987`, and one remaining drum-presence warning (`0.053` below `0.08`) recorded as later quality data. The final manifest is 16 bars with `Drums`, `Bass`, and `Melody`; the MIDI proof has `Meta`, `Drums`, `Bass` program `38`, and explicit `Melody` program `80`; and generated samples include `shaker.wav`.

Post-Task-068 consolidation checkpoint verified the recent backend genre-family UI contract before UI/UX work begins. The focused checkpoint ran arranger/session graph contract tests for cinematic/classical, trap/modern beat, R&B/neo-soul, lofi/boom-bap/G-Funk, house/ambient/pop, and Ethiopian-family workflows (`25 passed`). This confirms stable UI-facing `session_manifest.json` track names, roles, and channels across the recent families without reintroducing 16-bar inflation. `git status --ignored --short output\_diagnostics assets\soundfonts` confirmed generated diagnostics and the local `FluidR3Mono_GM.sf3` SoundFont remain ignored/uncommitted.


### Failed runner attempt

- Artifact directory: `output/_diagnostics/rock_1990s_20260514_044251`
- Outcome: failed before generation; `generation.stdout.log` is empty.
- Error evidence: `generation.stderr.log` contains argparse exit text ending with:

  ```text
  main.py: error: unrecognized arguments: era rock song with crunchy electric guitar, live drums, bass guitar, verse chorus bridge, energetic band performance, 100 BPM in E minor
  ```

- Diagnosis: the PowerShell `Start-Process` call split the prompt instead of passing it as one positional argument, so argparse interpreted prompt words after `1990's` as unrecognized arguments and exited with code 2.

### Real smoke

- Artifact directory: `output/_diagnostics/rock_1990s_20260514_044327`
- Runner/process result: PID `31368` was polled to completion; process exit code was `0`.
- Key artifacts:
  - `output/_diagnostics/rock_1990s_20260514_044327/generation.stdout.log`
  - `output/_diagnostics/rock_1990s_20260514_044327/generation.stderr.log`
  - `output/_diagnostics/rock_1990s_20260514_044327/project_metadata.json`
  - `output/_diagnostics/rock_1990s_20260514_044327/session_manifest.json`
  - `output/_diagnostics/rock_1990s_20260514_044327/trap_soul_100bpm_Eminor_20260514_044333.mid`
  - `output/_diagnostics/rock_1990s_20260514_044327/trap_soul_100bpm_Eminor_20260514_044333_render_report.json`
  - `output/_diagnostics/rock_1990s_20260514_044327/trap_soul_100bpm_Eminor_20260514_044333_render_error.txt`
- Smoke classification:
  - **PASS for diagnostic evidence:** artifacts captured parser output, arrangement inflation, MIDI, session metadata, selected instruments, render report, and render error.
  - **FAIL for genre correctness:** prompt routed to `trap_soul`, not rock.
  - **FAIL for audio correctness:** audio output remained `null` and render diagnostics report `render_exception @ render_tracks`.

## Findings grounded in artifacts and source

### 1. The prompt parsed as `trap_soul`, not rock

- Artifact evidence:
  - `project_metadata.json` has `current.parsed.genre: "trap_soul"` and `current.outputs.genre: "trap_soul"`.
  - `generation.stdout.log` prints `Genre: trap_soul` in the parsed prompt block.
- Source evidence:
  - `multimodal_gen/prompt_parser.py` defines `GENRE_KEYWORDS` without a `rock`, `classic_rock`, `alternative_rock`, or `grunge` entry.
  - `PromptParser._extract_genre()` falls through to `return 'trap_soul'  # Safe default` when no keyword matches.
- Implication: a rock prompt cannot become rock in the current parser path; it reaches downstream layers already mislabeled.

### 2. The parser extracted `guitar`, `bass`, and `choir`; `chorus` likely cross-matched `choir`

- Artifact evidence:
  - `project_metadata.json` has `current.parsed.instruments: ["guitar", "bass", "choir"]`.
  - `generation.stdout.log` prints `Instruments: guitar, bass, choir`.
- Source evidence:
  - `multimodal_gen/prompt_parser.py` has `INSTRUMENT_KEYWORDS['guitar']` and `INSTRUMENT_KEYWORDS['bass']`, which explain the intended guitar/bass detections.
  - The same file has `INSTRUMENT_KEYWORDS['choir']` including `chorus`; `_extract_instruments()` uses word-boundary matching, so the arrangement word `chorus` is treated as the instrument `choir`.
- Implication: section language and instrument language are conflated. Future parser work must classify `chorus` as a section hint unless the prompt asks for `choir`, `choral`, or voices.

### 3. Rock drums inherited trap-soul 808 defaults

- Artifact evidence:
  - `project_metadata.json` has `current.parsed.drum_elements: ["kick", "808", "snare", "clap", "hihat"]`.
  - `generation.stdout.log` prints `Drums: kick, 808, snare, clap, hihat`.
- Source evidence:
  - `multimodal_gen/prompt_parser.py` hardcoded genre defaults include `_get_genre_drums()['trap_soul'] = ['kick', '808', 'snare', 'clap', 'hihat']`.
- Implication: the 808 is not a rock-specific choice; it is a symptom of the fallback genre. Rock needs its own default drum vocabulary, e.g. kick/snare/hihat_open/crash/ride/toms/fills without mandatory 808/clap.

### 4. No rock strategy is registered

- Source evidence:
  - `multimodal_gen/strategies/registry.py` imports and registers trap, trap_soul, rnb, lofi, g_funk, house, Ethiopian-family, default, drill, boom_bap, cinematic, and ambient strategies.
  - The registry does not import or register a `RockStrategy`.
- Smoke corroboration:
  - The diagnostic script that listed `StrategyRegistry.list_genres()` showed `rock`, `classic_rock`, and `alternative_rock` absent, while `trap_soul` was present.
- Implication: even if parsing starts returning `rock`, the generator would currently fall back to `DefaultStrategy` unless a rock strategy is added and registered.

### 5. Rock patterns, presets, microtiming, and dynamics exist but are orphaned from the main path

Existing rock-aware material is present:

- `multimodal_gen/pattern_library.py`
  - Loads rock patterns via `_load_rock_patterns()`.
  - Contains examples such as `rock_basic_beat`, `rock_hard_double_kick`, `rock_eighth_note_bass`, `rock_power_chord`, `rock_riff_pentatonic`, plus extended fill/transition examples like `rock_fill_crash_cymbal` and `rock_transition_buildup`.
- `multimodal_gen/preset_system.py`
  - Defines `rock_classic` and `rock_indie` preset configs.
- `multimodal_gen/microtiming.py`
  - Defines a `rock` microtiming config.
- `multimodal_gen/dynamics.py`
  - Defines `rock` dynamics/CC expression entries.

Why this is still orphaned:

- The parser cannot return `rock` from the smoke prompt.
- `StrategyRegistry` has no `RockStrategy`.
- `arranger.py` has no hardcoded `rock` template and falls back unknown templates to `trap_soul`.
- `output_analyzer.py` has no `rock` entry in `AUDIO_GENRE_TARGETS`, so rendered-audio validation would otherwise treat rock as unknown and return a neutral score.

### 6. The arrangement ignored the 16-bar smoke intent and inflated to 28 bars

- Artifact evidence:
  - `generation.stdout.log` prints `Target duration: 0.6 min -> 28 bars (~1.1 min)` and `Arrangement: 7 sections, 28 bars`.
  - `session_manifest.json` has `total_bars: 28` and `total_ticks: 53760`; at 480 PPQ and 4/4 this is exactly 28 bars.
  - `project_metadata.json` sections are seven 4-bar sections: intro, drop, variation, breakdown, buildup, drop, outro.
- Source evidence:
  - `main.py` forwards `--duration-bars` by setting `parsed.target_duration_seconds` and `parsed.target_bars`.
  - `multimodal_gen/arranger.py` selects the genre template through `_get_template()`. Unknown genres fall back to `ARRANGEMENT_TEMPLATES['trap_soul']`.
  - `ARRANGEMENT_TEMPLATES['trap_soul']` has seven sections.
  - `_adjust_to_duration()` scales each template section but clamps every section to at least 4 bars with `new_bars = max(4, ...)`.
- Implication: the duration override is forwarded, but the selected seven-section trap-soul template cannot compress below 28 bars. Rock needs a template and a bounded-duration policy that can preserve `verse chorus bridge` intent while fitting short smoke targets.

### 7. Audio render failed in `render_tracks` due an unguarded organ click array length

- Artifact evidence:
  - `*_render_error.txt` reports `failure_reason: render_exception`, `failure_stage: render_tracks`, `exception_type: ValueError`, and `exception_message: operands could not be broadcast together with shapes (100,) (220,) (100,)`.
  - `*_render_report.json` mirrors the same failure in `render_status.failure`.
  - `generation.stderr.log` contains the traceback.
- Source evidence:
  - Traceback path: `audio_renderer.py::render_midi_file` → `_render_procedural()` → `_render_track_procedural()` → `ProceduralSynthesizer.render_notes()` → `_synthesize_note()` → `assets_gen.py::generate_organ_tone()`.
  - `audio_renderer.py` dispatches GM organ programs 16-23 to `generate_organ_tone()`.
  - `assets_gen.py::generate_organ_tone()` creates `click_duration = int(0.005 * sample_rate)` and then does `audio[:click_duration] += click` without clamping the click to the actual audio length.
- Implication: short MIDI notes shorter than the organ key-click length can crash procedural rendering. This is renderer correctness, independent of rock genre quality.

### 8. CLI returned success and printed `Generation Complete` despite `audio: null`

- Artifact evidence:
  - Runner exit code was `0`.
  - `project_metadata.json` has `current.outputs.audio: null`.
  - `generation.stdout.log` prints `[!] Audio rendering returned no output (render_exception @ render_tracks)` and later `[v] Generation Complete!`.
- Source evidence:
  - `main.py` computes `require_soundfont_failed = bool(args.require_soundfont and not results.get('audio'))`.
  - The CLI return path is `return 2 if require_soundfont_failed else 0`.
- Implication: for smoke/CI, exit code alone is not a reliable audio-quality signal unless a strict audio flag exists. Future verification should assert audio presence via metadata/render reports, not just process exit.

### 9. Guitar loading gap: custom melodic mapping does not include guitar; GM guitar programs map to keys

- Artifact evidence:
  - `project_metadata.json` selected no custom `guitar` instrument in the final render report; `custom_audio.custom_melodic_loaded` reports `bass` and `pad` only.
  - `generation.stdout.log` says `Prompt-filtered instruments: bass, pad` even though the prompt asked for guitar.
- Source evidence:
  - `audio_renderer.py::_load_custom_instruments()` has `melodic_mappings` for synth, bass, keys, pad, brass, and strings, but no guitar mapping.
  - `_INSTRUMENT_TO_MELODIC` does not map `guitar` or `electric guitar` to a melodic cache key.
  - `audio_renderer.py::_synthesize_note()` maps GM guitar programs 24-31 to `keys` in `program_to_type`.
  - Expansion fallback mapping can map program 25 to `guitar`, but the custom melodic path checks the `keys` cache first for 24-31.
- Implication: even if the MIDI asks for guitar, sample loading and synthesis routing can still produce keys/pads or fallback timbres. Guitar needs a first-class cache/category/synthesis route.

### 10. Missing module warning in smart instrument selection

- Artifact evidence:
  - `generation.stdout.log` contains `[!]  Smart instrument selection: No module named 'multimodal_gen.instrument_index'`.
- Source evidence:
  - `main.py` imports `from multimodal_gen.instrument_index import InstrumentIndex, InstrumentResolver, create_instrument_index` inside the smart instrument selection path.
  - Repository search finds only `multimodal_gen/_deprecated/instrument_index.py`; no live `multimodal_gen/instrument_index.py` exists.
- Implication: the warning is expected under the current file layout. Future work should either restore a supported shim/module or remove/replace this stale import path.

## Preserve list for future implementation

Do not regress or remove these existing behaviors while adding rock support:

1. Existing genres, strategies, and golden prompts.
2. `trap_soul`, `rnb`, and `neo_soul` priority/order and their current routing semantics.
3. Preference-driven defaults and user overrides, including BPM, key, presets, production presets, style presets, duration-bars, and reference-derived settings.
4. Default fallback for unknown genres; add rock explicitly without making unknown prompts fail.
5. Existing render diagnostics: `*_render_report.json`, `*_render_error.txt`, `render_status`, warnings, tracebacks, and metadata links.
6. MPC export, stems, takes, comping, session manifest, project metadata, and BWF/session graph outputs.
7. Ethiopian instrument procedural paths and the protective skip of generic melodic loading when Ethiopian instruments are requested.
8. JUCE generate, analyze, tools, takes, mixer, arrangement/regenerate, controls, and mastering workflows.
9. Existing expansion-pack loading behavior and Funk o Rama / R&B sample compatibility.
10. The current ability to run without FluidSynth by using procedural rendering and diagnostic warnings.

## Phased generation fix plan

### Phase 0 — Baseline lock and smoke harness

**Goal:** make the current failure reproducible and enforce future acceptance with artifacts, not listening impressions alone.

**File targets:**

- `docs/UPGRADE_PLAN_2026-05-14_1990S_ROCK_QUALITY_UI.md` — this plan and artifact baseline.
- Future harness target: `scripts/smoke_1990s_rock.ps1` or `scripts/smoke_1990s_rock.py`.
- Future focused test target: `tests/test_smoke_1990s_rock_contract.py`.

**Work:**

- Capture the exact prompt, seed, output directory convention, and expected artifact names.
- Make the runner quote the prompt as one argument; do not use `Start-Process` argument splitting that reproduces the first failed attempt.
- Require the harness to parse `project_metadata.json`, `session_manifest.json`, and render report/error files.
- Record expected current baseline failures: parsed genre `trap_soul`, 28 bars, audio null, render exception.

**Focused tests / verification commands:**

```powershell
Set-Location c:\dev\MUSE-ai\MUSE
.\.venv\Scripts\python.exe -m pytest tests/test_smoke_1990s_rock_contract.py -q
.\scripts\smoke_1990s_rock.ps1 -OutputRoot output\_diagnostics
```

**Acceptance:** current baseline test can prove the failure before fixes and can later be flipped to assert `rock`, bounded bars, non-null audio, and rock analyzer pass.

### Phase 1 — Renderer correctness and CLI success semantics

**Goal:** a render exception should not be hidden by `Generation Complete`, and short organ notes must not crash rendering.

**File targets:**

- `multimodal_gen/assets_gen.py`
- `multimodal_gen/audio_renderer.py`
- `main.py`
- `tests/test_assets_gen.py` or `tests/test_audio_renderer.py`
- `tests/test_main_render_diagnostics.py`

**Work:**

- Clamp organ key-click length to `min(click_duration, len(audio))` before adding click noise.
- Add a strict smoke/CI audio-success option, e.g. additive `--require-audio`, or make render exceptions non-zero under an existing strict flag while preserving default ad hoc behavior.
- Ensure the human summary distinguishes `Generation Complete (MIDI only)` from full audio success when `results['audio']` is null.
- Preserve existing `--require-soundfont` semantics for the specific SoundFont-required path.

**Focused tests / verification commands:**

```powershell
Set-Location c:\dev\MUSE-ai\MUSE
.\.venv\Scripts\python.exe -m pytest tests/test_render_report_schema.py tests/test_main_render_diagnostics.py -q
.\.venv\Scripts\python.exe -m pytest tests/test_audio_renderer.py tests/test_assets_gen.py -q
```

**Acceptance:** short organ notes render without ValueError; render reports still persist; strict audio smoke exits non-zero on audio null/render_exception; default no-FluidSynth fallback remains documented and diagnostic-rich.

### Phase 2 — Rock parser, defaults, and genre intelligence

**Goal:** the investigated prompt becomes a rock-family parsed prompt with band defaults and no accidental choir/808 fallback.

**File targets:**

- `multimodal_gen/prompt_parser.py`
- `multimodal_gen/utils.py`
- `multimodal_gen/genre_rules.py` if rock-specific rules are needed
- `tests/test_prompt_parser.py`
- `tests/test_genre_normalization.py`

**Work:**

- Add `rock`, `classic_rock`, `alternative_rock`, and `grunge` keyword coverage, including `rock song`, `electric guitar`, `crunchy guitar`, `live drums`, `band performance`, `90s rock`, `1990s rock`, `alt rock`, `alternative rock`, and `grunge`.
- Put rock-family priority before `boom_bap` so `90s rock` does not become golden-era hip-hop, while preserving `boom_bap` for `90s hip hop`, `golden era`, and `old school` prompts.
- Add rock-family genre defaults: BPM bands, straight or subtle human feel, live drums, guitar/bass emphasis, no default 808/clap.
- Make `chorus` a section hint by default, not a choir instrument, unless the prompt contains explicit choir/choral/voices language.
- Keep unknown genre fallback to `trap_soul` or the current default so unsupported prompts remain fail-open.

**Focused tests / verification commands:**

```powershell
Set-Location c:\dev\MUSE-ai\MUSE
.\.venv\Scripts\python.exe -m pytest tests/test_prompt_parser.py tests/test_genre_normalization.py -q
```

**Acceptance:** the smoke prompt parses to `rock` or a canonical rock-family genre; instruments include guitar and bass but not choir; drums include live kit elements and exclude 808 unless explicitly requested; trap_soul/rnb/neo_soul existing parser tests still pass.

### Phase 3 — `RockStrategy` and PatternLibrary wiring

**Goal:** parsed rock must route to a real strategy that reuses existing rock pattern assets rather than falling back to `DefaultStrategy`.

**File targets:**

- `multimodal_gen/strategies/rock_strategy.py` (new)
- `multimodal_gen/strategies/registry.py`
- `multimodal_gen/pattern_library.py` only if adapters are needed; avoid rewriting existing patterns unnecessarily
- `multimodal_gen/arranger.py`
- `tests/test_strategy_registry.py` or new `tests/test_rock_strategy.py`
- `tests/test_arranger.py` or focused arranger tests

**Work:**

- Implement a minimal `RockStrategy` that supports `rock`, `classic_rock`, `alternative_rock`, and `grunge` aliases.
- Reuse existing `PatternLibrary` rock patterns for drums, bass, power chords, riffs, fills, and transitions.
- Add an arranger template for rock with verse/chorus/bridge semantics and a short-target path that can honor 16-bar smoke intent without expanding to seven mandatory sections.
- Keep strategy fallback behavior for unsupported genres.

**Focused tests / verification commands:**

```powershell
Set-Location c:\dev\MUSE-ai\MUSE
.\.venv\Scripts\python.exe -m pytest tests/test_strategy_registry.py tests/test_rock_strategy.py tests/test_arranger.py -q
```

**Acceptance:** `StrategyRegistry.get('rock')` returns `RockStrategy`; rock arrangements use verse/chorus/bridge labels when requested; 16-bar smoke targets produce a bounded arrangement rather than the trap-soul 28-bar minimum; existing strategy tests still pass.

### Phase 4 — Guitar/band instrumentation

**Goal:** rock MIDI and audio should sound like guitar/bass/drums rather than keys/pads/808 trap-soul fallback.

**File targets:**

- `multimodal_gen/instrument_manager.py`
- `multimodal_gen/audio_renderer.py`
- `multimodal_gen/assets_gen.py` if a procedural guitar fallback is added
- `multimodal_gen/midi_generator.py` if track/program selection needs explicit guitar programs
- `tests/test_instrument_manager.py`
- `tests/test_audio_renderer.py`
- `tests/test_midi_generator.py` or focused render-routing tests

**Work:**

- Add or expose a guitar category if the current instrument index can classify Funk o Rama / expansion guitar samples safely.
- Map prompt `guitar`, `electric guitar`, and `crunchy guitar` to a `guitar` melodic cache key.
- Map GM guitar programs 24-31 to `guitar`, not `keys`, in custom melodic lookup.
- Provide a procedural distorted/crunch guitar fallback only if no sample is available; keep it bounded and testable.
- Preserve Ethiopian instrument guardrails and existing expansion preload behavior.

**Focused tests / verification commands:**

```powershell
Set-Location c:\dev\MUSE-ai\MUSE
.\.venv\Scripts\python.exe -m pytest tests/test_instrument_manager.py tests/test_audio_renderer.py -q
```

**Acceptance:** guitar prompt causes guitar samples or guitar fallback to load; render report records `custom_melodic_loaded.guitar` when samples are available; GM 24-31 no longer route through keys first; Ethiopian procedural instruments still bypass generic melodic sample loading.

### Phase 5 — Output analyzer rock targets and repair loop

**Goal:** rendered-audio acceptance should know what rock is and should reject trap/808/pad-heavy outputs for rock prompts.

**File targets:**

- `multimodal_gen/output_analyzer.py`
- `tests/test_output_analyzer.py`
- `../copilot-Liku-cli/src/main/agents/producer.js` only if producer repair routing must react to rock-specific corrections
- `../copilot-Liku-cli/scripts/test-output-analysis-repair.js` only if producer repair routing changes

**Work:**

- Add conservative `rock` and optional rock-family entries to `AUDIO_GENRE_TARGETS`.
- Include expected timbres such as electric guitar/bass/drums and forbidden timbres such as 808/electronic trap drums for rock-family prompts.
- Ensure unknown-genre neutral score remains available for truly unsupported genres, but rock no longer uses that path.
- Add repair suggestions for too much sub-bass/808, missing live-drums, missing guitar-band timbre, and over-synthetic pads only when issues are measurable.

**Focused tests / verification commands:**

```powershell
Set-Location c:\dev\MUSE-ai\MUSE
.\.venv\Scripts\python.exe -m pytest tests/test_output_analyzer.py -q
node ..\copilot-Liku-cli\scripts\test-output-analysis-repair.js
```

**Acceptance:** rock gets a real analyzer target instead of neutral `0.75`; trap-soul-like 808 output fails rock validation; a guitar/bass/drums render can pass conservative rock thresholds; existing analyzer targets and repair routes remain stable.

### Phase 6 — Regression/golden prompts

**Goal:** lock the cross-layer rock fix without regressing current golden prompts.

**File targets:**

- `tests/test_prompt_parser.py`
- `tests/test_strategy_registry.py`
- `tests/test_output_analyzer.py`
- `tests/test_main_render_diagnostics.py`
- `output_cli_golden/`, `output_cli_golden_short/`, or a new documented diagnostics baseline if golden audio artifacts are intentionally not committed
- `docs/MASTERCLASS_MUSICALITY_IMPLEMENTATION_TRACKER.md` only if milestone tracking needs an accepted update

**Work:**

- Add golden prompt cases for:
  - the exact 1990s rock prompt in this document;
  - `90s boom bap hip hop` to preserve `boom_bap`;
  - `trap soul with 808 and rhodes` to preserve `trap_soul`;
  - `neo soul with rhodes and warm bass` to preserve `neo_soul`.
- Add a smoke assertion matrix: parsed genre, instruments, drums, sections/bars, render audio presence, render report success, analyzer score.
- Keep heavy audio golden artifacts optional; prefer deterministic metadata/render report assertions for CI speed.

**Focused tests / verification commands:**

```powershell
Set-Location c:\dev\MUSE-ai\MUSE
.\.venv\Scripts\python.exe -m pytest tests/test_prompt_parser.py tests/test_strategy_registry.py tests/test_output_analyzer.py tests/test_main_render_diagnostics.py -q
.\scripts\smoke_1990s_rock.ps1 -StrictAudio
```

**Acceptance:** exact prompt routes rock end-to-end; current trap_soul/rnb/neo_soul/boom_bap golden prompts retain prior classifications and critical artifacts; smoke is deterministic and does not rely on manual listening alone.

## Phased UI plan

### UI Phase A — Baseline checklist

**File targets:**

- `juce/Source/MainComponent.h`
- `juce/Source/MainComponent.cpp`
- `juce/Source/UI/GenreSelector.h`
- `juce/Source/UI/GenreSelector.cpp`
- `juce/Source/UI/InstrumentBrowserPanel.h`
- `juce/Source/UI/InstrumentBrowserPanel.cpp`
- `juce/Source/UI/ControlsPanel.h`
- `juce/Source/UI/ControlsPanel.cpp`
- `juce/Source/UI/Theme/ThemeManager.h`
- `juce/Source/UI/Theme/LayoutConstants.h`
- `juce/Source/UI/Visualization/GenreTheme.h`

**Checklist:**

- Build the current JUCE app before UI changes.
- Screenshot or checklist current main layout: transport, timeline, prompt panel, visualization, bottom panel, tools menu, instruments, FX, expansions, mixer, takes, controls, mastering.
- Verify generate/analyze/regenerate/takes/mixer workflows still open and close before any visual polish.

**Verification/build commands:**

```powershell
Set-Location c:\dev\MUSE-ai\MUSE
npm run build:debug
npm run build
```

### UI Phase B — Theme token unification

**Goal:** centralize visual constants before polishing individual panels.

**File targets:**

- `juce/Source/UI/Theme/ThemeManager.h`
- `juce/Source/UI/Theme/LayoutConstants.h`
- `juce/Source/UI/Visualization/GenreTheme.h`
- Panel files only where hardcoded colors/radii/padding need to be replaced.

**Work:**

- Add or reuse tokens for panel background, elevated surface, border, text primary/secondary, accent, warning, success, control radius, focus ring, row height, and standard gaps.
- Preserve existing genre theme behavior; tokens should be additive and low-risk.

**Verification:** app builds, panels retain layout, no component loses readability at default size.

### UI Phase C — `InstrumentBrowser`, `GenreSelector`, and `ControlsPanel` polish

**Goal:** improve the panels most relevant to genre/instrument intent without changing backend request semantics.

**File targets:**

- `juce/Source/UI/InstrumentBrowserPanel.cpp/.h`
- `juce/Source/UI/GenreSelector.cpp/.h`
- `juce/Source/UI/ControlsPanel.cpp/.h`

**Work:**

- InstrumentBrowser: clearer category chips, search/empty states, selected-state contrast, compact rows, and instrument source badges.
- GenreSelector: add rock-family choices only after generation backend supports them; ensure `auto` remains default and existing choices preserve IDs.
- ControlsPanel: clearer scope labels for global vs next generate/regenerate overrides; preserve `nextGenerateOverrides` and `nextRegenerateOverrides` wiring.

**Verification:** build plus manual checklist that selected genre/instrument changes still reach current UI state and do not break generate/regenerate payloads.

### UI Phase D — Tool-window and arrangement/takes preservation

**Goal:** avoid UI polish regressing tool-window behavior, bottom-panel behavior, arrangement edits, takes, and mixer.

**File targets:**

- `juce/Source/MainComponent.h/.cpp`
- `juce/Source/UI/FloatingToolWindow.h/.cpp`
- `juce/Source/UI/TakeLaneComponent.h/.cpp`
- `juce/Source/UI/Mixer/MixerComponent.h/.cpp`
- `juce/Source/UI/TimelineComponent.h/.cpp`

**Work:**

- Preserve existing tool IDs from `MainComponent::showToolWindow(int toolId)`.
- Preserve current bottom panel semantics for FX, Mixer, Takes, and any existing Instruments behavior unless intentionally changed in its own PR.
- Verify arrangement/regenerate controls, take audition/restore, take comp snapshots, and mixer binding remain intact.

**Verification:** build plus manual smoke of Tools menu, Takes, Mixer, and Generate/Analyze.

### UI Phase E — Optional genre accent

**Goal:** make genre identity visible without introducing hardcoded style forks that drift from backend support.

**File targets:**

- `juce/Source/UI/Visualization/GenreTheme.h`
- `juce/Source/MainComponent.cpp`
- `juce/Source/UI/GenreSelector.cpp`

**Work:**

- Add a subtle rock accent only after backend parser/strategy/analyzer support lands.
- Keep accent optional; if genre is `auto` or unsupported, use existing neutral theme.

**Verification/build commands:**

```powershell
Set-Location c:\dev\MUSE-ai\MUSE
npm run build:debug
npm run build
```

**UI acceptance:** visual improvements compile, preserve workflows, and do not ship rock UI choices that imply backend support before the generation path is ready.

## Next 10 PR-sized tasks

### PR 1 — Add strict 1990s rock smoke harness

- **Acceptance criteria:** one command reproduces the prompt, captures output under `output/_diagnostics`, records PID/exit/artifacts, and asserts current baseline failures before fixes.
- **Verification:**

  ```powershell
  .\.venv\Scripts\python.exe -m pytest tests/test_smoke_1990s_rock_contract.py -q
  .\scripts\smoke_1990s_rock.ps1 -OutputRoot output\_diagnostics
  ```

### PR 2 — Fix organ key-click crash for short notes

- **Acceptance criteria:** `generate_organ_tone()` handles durations shorter than 5 ms; no ValueError from click addition; render report schema remains unchanged.
- **Verification:**

  ```powershell
  .\.venv\Scripts\python.exe -m pytest tests/test_audio_renderer.py tests/test_render_report_schema.py -q
  ```

### PR 3 — Add strict audio success semantics for smoke/CI

- **Acceptance criteria:** strict flag or strict mode exits non-zero when audio is null or render status has `success: false`; default permissive no-FluidSynth behavior remains documented; summary no longer implies full success when only MIDI exists.
- **Verification:**

  ```powershell
  .\.venv\Scripts\python.exe -m pytest tests/test_main_render_diagnostics.py -q
  .\scripts\smoke_1990s_rock.ps1 -StrictAudio
  ```

### PR 4 — Add rock-family parser coverage and section-aware `chorus`

- **Acceptance criteria:** exact prompt parses to rock-family genre, instruments include guitar/bass and exclude choir, drums exclude 808 unless explicit; `90s boom bap hip hop` still parses to boom_bap.
- **Verification:**

  ```powershell
  .\.venv\Scripts\python.exe -m pytest tests/test_prompt_parser.py tests/test_genre_normalization.py -q
  ```

### PR 5 — Add rock defaults without disturbing soul/trap defaults

- **Acceptance criteria:** rock defaults include live-kit/band emphasis, reasonable BPM range, no hihat-roll/808 defaults; trap_soul/rnb/neo_soul parser/default tests still pass.
- **Verification:**

  ```powershell
  .\.venv\Scripts\python.exe -m pytest tests/test_prompt_parser.py tests/test_genre_normalization.py -q
  ```

### PR 6 — Add and register minimal `RockStrategy`

- **Acceptance criteria:** `StrategyRegistry.get('rock')`, `get('classic_rock')`, `get('alternative_rock')`, and `get('grunge')` return rock strategy; unknown genres still get default fallback.
- **Verification:**

  ```powershell
  .\.venv\Scripts\python.exe -m pytest tests/test_strategy_registry.py tests/test_rock_strategy.py -q
  ```

### PR 7 — Wire rock patterns and bounded rock arrangement

- **Acceptance criteria:** rock strategy uses existing rock patterns; exact 16-bar smoke target produces bounded verse/chorus/bridge-compatible sections instead of trap-soul seven-section minimum; existing arranger templates still pass.
- **Verification:**

  ```powershell
  .\.venv\Scripts\python.exe -m pytest tests/test_rock_strategy.py tests/test_arranger.py -q
  ```

### PR 8 — Make guitar first-class in instrument loading/render routing

- **Acceptance criteria:** guitar prompt loads guitar samples when available or uses a guitar fallback; GM guitar programs 24-31 route to guitar cache/type, not keys; Ethiopian procedural skip remains intact.
- **Verification:**

  ```powershell
  .\.venv\Scripts\python.exe -m pytest tests/test_instrument_manager.py tests/test_audio_renderer.py -q
  ```

### PR 9 — Add rock rendered-audio targets and repair signals

- **Acceptance criteria:** rock no longer uses unknown neutral analyzer score; trap/808-heavy output fails rock validation; rock-like guitar/bass/drums output can pass conservative thresholds; repair suggestions are concrete and bounded.
- **Verification:**

  ```powershell
  .\.venv\Scripts\python.exe -m pytest tests/test_output_analyzer.py -q
  node ..\copilot-Liku-cli\scripts\test-output-analysis-repair.js
  ```

### PR 10 — UI polish pass with workflow preservation

- **Acceptance criteria:** theme tokens unified; InstrumentBrowser, GenreSelector, and ControlsPanel polish compiles; Generate/Analyze/Tools/Takes/Mixer workflows preserved; optional rock accent appears only after backend rock support exists.
- **Verification:**

  ```powershell
  npm run build:debug
  npm run build
  ```

## Final readiness criteria

The 1990s rock prompt should not be judged musically until all of these are true in one smoke run:

1. Parser output genre is rock-family, not `trap_soul`.
2. Instruments include guitar and bass without accidental choir from `chorus`.
3. Drums are live-kit rock drums without default 808.
4. Strategy is `RockStrategy`, not `DefaultStrategy` or trap-soul.
5. Arrangement honors the requested compact smoke duration or explains any intentional expansion.
6. Renderer produces a non-null audio artifact or strict smoke fails non-zero with render diagnostics.
7. Render report is successful and includes expected guitar/bass/drum loading where available.
8. Output analyzer evaluates rock with real targets and passes conservatively.
9. Existing trap_soul/rnb/neo_soul/boom_bap/Ethiopian/JUCE workflows still pass their focused proofs.

## Implementation and validation results — 2026-05-14

This plan has now been implemented through the generation, analyzer, golden-regression, UI-polish, and app-validation milestones. The final validation used the running JUCE Release app plus the JSON-RPC gateway to exercise the same backend workflow from an opened desktop session.

### Source-control state observed during app validation

- Initial Source Control concern: VS Code showed pending/outgoing activity, but `git status --short --untracked-files=all` in `c:\dev\MUSE-ai\MUSE` was clean before the app-validation milestone.
- Branch state before this validation milestone: `master...origin/master [ahead 10]`; no local working-tree diff in the MUSE repo.
- After the final app-validation proof, one backend transport bug was fixed and documented in this milestone: JSON-RPC/OSC requests can send `key` and `mode` separately, but the worker previously forwarded only `key="E"`, which forced E major. `build_run_generation_kwargs()` now compacts `key="E", mode="minor"` into the `Em` key override expected by `main.run_generation()`.

### Backend/app launch validation

- Release app launched from:
  `juce\build\MultimodalMusicGen_artefacts\Release\AI Music Generator.exe`
- Gateway launched with:
  `.\.venv\Scripts\python.exe -m multimodal_gen.server --gateway --verbose`
- Stale hidden gateway PIDs were identified and stopped before the final E-minor validation so the running JSON-RPC server loaded the latest worker code.
- Final gateway health proof: JSON-RPC `ping` returned `status: ok` from the fresh backend process.

### Final rock request proof

Prompt:

```text
1990's era rock song with crunchy electric guitar, live drums, bass guitar, verse chorus bridge, energetic band performance, 100 BPM in E minor
```

Final artifact directory:

```text
output\ui_validation\rock_app_validation_20260514_eminor_fixed
```

Key proof from `generate_sync` request `ui-rock-eminor-fixed-20260514`:

- JSON-RPC success: `true`
- Task ID: `ff861647`
- MIDI: `output\ui_validation\rock_app_validation_20260514_eminor_fixed\rock_100bpm_Eminor_20260514_101946.mid` (`5151` bytes)
- WAV: `output\ui_validation\rock_app_validation_20260514_eminor_fixed\rock_100bpm_Eminor_20260514_101946.wav` (`7183920` bytes)
- The final WAV was opened in the default Windows audio player for listening review.

Metadata proof:

- Genre: `rock`
- BPM: `100`
- Key/scale: `E minor`
- Sections: `verse` 4 bars, `chorus` 4 bars, `bridge` 4 bars, `chorus` 4 bars (`16` bars total)

Render/audio-analysis proof:

- `render_status.success: true`
- `audio_analysis.target_genre: rock`
- `audio_analysis.passed: true`
- `genre_match_score: 0.997`
- `spectral.sub_bass_energy_ratio: 0.1245`
- `drums.percussive_ratio: 0.112`
- Required drum parts detected: `has_kick=true`, `has_snare_or_clap=true`, `has_hihats=true`
- `onset_density: 4.69`
- Remaining analyzer note is a warning, not a failure: live drum presence is slightly below the strict rock target but required drum parts are present, so the tolerance gate passes as intended.

MIDI proof:

- Bass track uses GM electric bass program `34` (0-based), not Synth Bass/808 routing.
- Chords track uses GM guitar program `25` (0-based), not Rhodes/keys.
- Clap pitch `39` is absent.

### Verification commands after the transport fix

```powershell
Set-Location c:\dev\MUSE-ai\MUSE
.\.venv\Scripts\python.exe -m pytest tests/test_protocol.py -q
.\.venv\Scripts\python.exe -m pytest tests/test_golden_prompts_smoke.py tests/test_smoke_1990s_rock_contract.py -q
git diff --check
```

Results:

- `tests/test_protocol.py`: `39 passed`
- Golden/rock smoke contracts: `26 passed`
- `git diff --check`: `PASS`

### Remaining caveats

- FluidSynth remains unavailable in this environment; final validation used the procedural renderer, which is the supported fallback path.
- Generated output directories under `output\ui_validation\...` are validation artifacts and are intentionally not staged.
- Source-control outgoing commits still need to be pushed separately if remote synchronization is desired; this validation milestone only stages/commits local repo progress.

## Natural instrument synthesis and app-mastering parity findings — 2026-05-14

This section grounds the later Gemini synthesis against the current codebase. The short version is: the saved WAV produced by the Python/backend render path is processed through a mastering-style chain, but the JUCE app currently plays the generated MIDI through its own internal synth/sampler path instead of playing that mastered WAV. FluidSynth/SoundFonts can improve instrument realism, but they are not the only gap; playback parity and a unified instrument/patch contract are also required.

### Immediate source-of-truth diagnosis: app playback is not the mastered backend WAV

Observed user finding: files opened directly from the workspace/output folder sound more mastered than the songs played inside the application.

Codebase grounding:

- Backend/Python rendered WAVs go through the offline render path in `multimodal_gen/audio_renderer.py::_render_procedural()`:
  - track-level RMS balancing and per-stem processing are applied before summing;
  - the master bus can apply `create_master_chain()` from `multimodal_gen/mix_chain.py`;
  - convolution reverb, multiband dynamics, spectral excitation/resonance suppression, auto-gain staging, normalization fallback, true-peak limiting, and dithered WAV save are all in the backend render path;
  - the final rock render report confirms this path was active: `pipeline_stages.convolution_reverb=plate`, `multiband_dynamics=mastering_glue`, `spectral_processing=radio_ready`, `auto_gain_staging=target=-14.0`, and `true_peak_limiter=ceiling=-1.0dBTP`.
- The JUCE completion path stores the generated audio path as the current output file, but then explicitly loads the generated MIDI for playback:
  - `juce/Source/MainComponent.cpp::onGenerationComplete()` chooses `result.audioPath` for `appState.setOutputFile(...)` and the Recent Files UI, then executes `audioEngine.loadMidiFile(midiFile)` when `result.midiPath` is present.
  - No equivalent `audioEngine.loadAudioFile(result.audioPath)` call is made for generated-song playback.
- The JUCE audio-file playback hook exists but is not implemented:
  - `juce/Source/Audio/AudioEngine.cpp::loadAudioFile()` is a TODO and currently logs the request, lists future implementation notes, and returns `false`.
- The JUCE real-time master/FX graph exists, but current playback does not route generated MIDI audio through it:
  - `juce/Source/Audio/MixerGraph.cpp::initializeGraph()` creates a master gain node and default `Input -> MasterGain -> Output` graph.
  - `juce/Source/MainComponent.cpp::fxChainChanged()` sends FX chains into `audioEngine.getMixerGraph().setFXChainForBus(...)`.
  - `juce/Source/Audio/AudioEngine.cpp::getNextAudioBlock()` renders `MidiPlayer`/track synth output directly into `bufferToFill.buffer` and computes meters, but the source scan shows no call to `mixerGraph.processBlock(...)` in the playback callback.
- The Mastering Suite UI is not yet wired to backend mastering:
  - `juce/Source/UI/Mastering/MasteringSuitePanel.h/.cpp` define limiter, transient, multiband, spectral, auto-gain, reference, spatial, and stem UI panels.
  - `juce/Source/MainComponent.cpp::applyMasteringRequested()` still has `// TODO: Send OSC message to backend for mastering processing` and the `oscBridge->sendMasteringProcess(...)` call is commented out.
- The app can also choose different instruments than the backend render:
  - `MainComponent::applyGeneratedInstrumentSamples()` uses `instruments_used` from the JSON response or `project_metadata.json` to map samples into JUCE tracks.
  - `preferredCategoriesForTrack("Chords")` currently prefers `{ "pad", "keys", "synth", "strings", "brass" }`, not `guitar`.
  - The final rock metadata `outputs.instruments_used` contains bass/keys/pad/synth/strings/brass and drum categories, while the backend render report separately shows `custom_melodic_loaded.guitar=3`. That means the backend can render the rock chord track as guitar, while the app may preview the chord track through pad/keys/synth-style samples or the simple synth.

Conclusion: the app-vs-workspace sound difference is not just a FluidSynth issue. The immediate parity gap is that the app previews MIDI through a separate real-time engine, while the saved WAV is the mastered backend render. Fixing app playback parity should come before judging the final song quality by the app preview.

### Grounding Gemini's natural-sound points in the current code

| Gemini point | Current codebase source of truth | Verdict / gap |
| --- | --- | --- |
| ADSR envelopes | Python has `ADSRParameters`, `SynthesisParameters`, `generate_tone_with_adsr()`, and `apply_envelope()` in `multimodal_gen/assets_gen.py`. JUCE's `DefaultSynthVoice` uses `juce::ADSR` in `juce/Source/Audio/AudioEngine.cpp`. | Partially implemented. Python instruments use envelopes, and the app default synth has attack/release. Gap: there is no unified patch object that gives each instrument a genre-aware amp ADSR plus filter ADSR across Python and JUCE. JUCE default synth sets decay to `0.0` and sustain to `1.0`, so it is still a simple envelope compared with the backend. |
| Harmonic overtones / additive synthesis | `assets_gen.py` already stacks harmonics for `generate_guitar_tone()`, `generate_piano_tone()`, `generate_washint_tone()`, `generate_brass_tone()`, `generate_strings_tone()`, `generate_harp_tone()`, `generate_choir_tone()`, and Hammond-style `generate_organ_tone()`. | Mostly present in backend procedural instruments. Gap: not centralized; each instrument owns its own ad hoc harmonic recipe. The app default synth remains one oscillator/waveform plus a simple low-pass, so app preview does not reproduce backend additive timbres. |
| Timbral evolution / filter envelopes | `assets_gen.py` exposes `lowpass_filter()`, `highpass_filter()`, `bandpass_filter()`. Backend guitar/piano/bass and master processing use static filtering. JUCE default synth has a one-pole low-pass controlled by `DefaultSynthParam::CutoffHz`. | Partially implemented. Gap: source search found no `velocity -> cutoff` or separate filter-envelope path. The current filters are mostly static per-note or master/stem processors, not instrument-level cutoff envelopes that brighten attacks and darken decays. |
| Body / warmth / low mids | Backend has `add_saturation()` in `assets_gen.py`, `soft_clip()` and master saturation in `audio_renderer.py`, `mix_chain.py::create_master_chain()`, and `track_processor.py` saturation/compression. `audio_renderer.py::_synthesize_rock_electric_bass()` adds harmonic body while high-passing sub energy for rock. | Partially implemented. Saturation is real. Generic sub-oscillator/body controls are not unified as instrument patch parameters, and rock deliberately avoids 808-style sub-bloom to satisfy the rock analyzer. Body should be genre-aware, not globally added. |
| Presence / clarity / noise layers | Backend instruments add transients/noise: piano hammer noise, guitar pick transient, drum noise bursts, washint breath noise. `spectral_processing.py::HarmonicExciterParams` and presets like `radio_ready`, `vocal_presence`, and `master_air` operate around 2.5–5 kHz+ for presence/air. | Implemented in backend pieces. Gap: app preview does not route through backend spectral processing, and per-instrument noise/exciter settings are not exposed as AI-controllable patch parameters. |
| Normalization, dynamics, velocity | Backend parses MIDI velocity into `SynthNote.velocity`, uses it in procedural render functions, balances stems by RMS, applies compressors, auto-gain staging, normalization fallback, and true-peak limiting. JUCE `DefaultSynthVoice::startNote()` maps velocity to level. | Implemented for loudness/level in backend and basic app synth. Gap: no velocity-to-filter mapping found, and app playback does not use the backend master loudness chain. The final render report had the mastering stages active, but measured `estimated_lufs=-18.9` and `peak_dbfs=-5.9`, so even backend loudness targeting should be validated rather than assumed perfect. |
| Cinematic/orchestral sample-based synthesis | `audio_renderer.py` has `check_fluidsynth_available()`, `find_soundfont()`, and `render_midi_with_fluidsynth()`. `assets/soundfonts/README.md` documents `assets/soundfonts/`, `FluidR3_GM.sf2`, `GeneralUser_GS.sf2`, `--soundfont`, `--require-soundfont`, and `--diagnose-audio`. | Recommendation is aligned with the codebase. Gap: no SoundFont binaries are bundled, final validation had `fluidsynth.available=false`, and the FluidSynth success path currently returns after `_post_process()` rather than running the full `_render_procedural()` master chain. FluidSynth should improve timbres, but still needs post-render mastering parity. |
| EDM / pop wavetable, unison, detune | Backend pads use detuned oscillators (`generate_pad_tone()`), leads use pulse/saw-like stacks (`generate_lead_tone()`), and `generate_hybrid_sound('pad')` layers detuned sine waves. | Partially present as detuned oscillators. Gap: no single-cycle wavetable loader, wavetable interpolation, or unison voice engine comparable to Serum/Massive exists in the runtime path. |
| Lo-fi degradation / wow/flutter / vinyl | `assets_gen.py` has `generate_vinyl_crackle()` and `generate_tape_hiss()`. `_post_process()` mixes vinyl/rain textures. `style_policy.py` has a `lofi` mix preset with tape saturation and darker targets. `genres.json` names `wow_flutter`, but runtime search shows no general wow/flutter DSP implementation in the render chain. | Partial. Vinyl/noise/tape-warmth concepts exist; a global tape wow/flutter pitch-modulation stage is not implemented as a first-class renderer effect. |
| Rock/acoustic physical modeling | `assets_gen.py` contains `_karplus_strong_pluck()` and uses Karplus-Strong-style modeling for Ethiopian plucked/string instruments such as `generate_krar_tone()` and `generate_begena_tone()`. Rock guitar currently uses `generate_guitar_tone()` with additive harmonics, pick transient, tanh drive, high-pass/low-pass, and ADSR. | Physical modeling exists, but not yet as the main rock guitar/bass engine. The Gemini recommendation fits: a future rock/acoustic slice should either route guitar/bass to Karplus-Strong/multisamples or SoundFonts/SFZ, then apply amp/overdrive and the same master path used by backend WAV exports. |
| Level 1: introduce SoundFonts | Already supported by CLI/backend flags and autodiscovery; documented in `assets/soundfonts/README.md`; `requirements.txt` includes `midi2audio` as an optional FluidSynth wrapper while requiring the external `fluidsynth` binary. | High-priority practical upgrade. Must add a licensed `.sf2`/`.sfz` and install FluidSynth, then validate reports show `renderer_path=fluidsynth` or selected SFZ/SF2 path. Also add post-FluidSynth mastering so SoundFont renders do not bypass the backend master chain. |
| Level 2: build an Instrument class / AI-controllable patches | Existing pieces are scattered: `ADSRParameters`/`SynthesisParameters`, `InstrumentCategory`, `SonicProfile`, `InstrumentLibrary`, `MixPolicy`, JUCE `DefaultSynthState`, SF2/SFZ instrument classes, and expansion samplers. | Needed. The repo has ingredients but no single cross-runtime `InstrumentPatch` contract with oscillator stack, amp ADSR, filter ADSR, LFO, noise, saturation, velocity mapping, and genre defaults. |
| Level 3: DDSP / neural sound generation | No `ddsp` modules/files are present. `requirements.txt` only comments optional `torch`, `transformers`, and `audiocraft` for MusicGen-style inference. | Not implemented. Treat DDSP as a later research track after playback parity, SoundFonts/SFZ, and unified patch abstractions are stable. |

### Recommended next implementation order

1. **App playback parity first:** implement generated-audio playback in JUCE so app playback can use `result.audioPath`/the backend WAV by default, with MIDI preview retained as an edit/audition mode. This requires completing `AudioEngine::loadAudioFile()` and changing the generation-complete path to load the WAV for playback when available.
2. **Make app FX/mastering real or hide it from the critical path:** either route generated MIDI/sampler output through `MixerGraph::processBlock()` in `AudioEngine::getNextAudioBlock()`, or make the app clearly label MIDI preview as unmastered. Wire `MasteringSuitePanel` actions to backend or real-time processors instead of leaving `applyMasteringRequested()` as a TODO.
3. **Fix rock app instrument preview parity:** include guitar in the `preferredCategoriesForTrack("Chords")` path when the generated/project genre is rock-family, and ensure backend `instruments_used` exposes the guitar sample/category used by the renderer when available.
4. **FluidSynth/SoundFont proof slice:** install FluidSynth and a licensed General MIDI SoundFont under `assets/soundfonts/`, run `python main.py --diagnose-audio`, then regenerate the exact rock prompt and inspect the render report for FluidSynth/SoundFont use. Add a guardrail test or smoke assertion for the selected renderer path.
5. **Post-FluidSynth mastering parity:** if FluidSynth succeeds, load its WAV back through the same post-render master chain or a dedicated file-level mastering function so SoundFont quality and backend loudness/limiting are both present.
6. **Unified natural-instrument patch model:** introduce a small `InstrumentPatch`/`SynthesisVoice` abstraction first for procedural fallback (oscillators, amp ADSR, filter ADSR, velocity-to-amplitude, velocity-to-cutoff, noise/transient layer, saturation), then map existing instrument functions into it incrementally instead of rewriting every instrument at once.
7. **Genre-specific synth engines after parity:** add SF2/SFZ orchestral routing, wavetable/unison for EDM/pop, lo-fi wow/flutter, and Karplus-Strong/multisampled rock guitars as separate PR-sized slices with analyzer and render-report proof.

## App mastered-WAV playback parity implementation — 2026-05-14

Status: **implemented and verified** for the first/highest-priority recommendation above.

### What changed

- `juce/Source/Audio/AudioEngine.h/.cpp`
  - Implemented generated audio-file playback using `juce::AudioFormatReaderSource` and `juce::AudioTransportSource`.
  - Added `hasAudioFileLoaded()` and internal audio-file state.
  - `loadAudioFile()` now validates the file, creates a reader, connects it to the transport source, prepares playback when the audio device is active, and returns `true` on successful load.
  - `play()`, `pause()`, `stop()`, `prepareToPlay()`, `releaseResources()`, `getPlaybackPosition()`, `setPlaybackPosition()`, and `getTotalDuration()` now account for loaded audio files.
  - `getNextAudioBlock()` prefers the loaded audio file while transport is playing, and skips MIDI/track rendering during audio-file playback to avoid doubled playback.
- `juce/Source/MainComponent.cpp`
  - `onGenerationComplete()` still loads generated MIDI for visualization and fallback.
  - After MIDI loading, it attempts to load `result.audioPath`; if the backend WAV exists and loads successfully, the app playback path now uses that rendered/mastered WAV by default.
- `juce/Source/UI/TransportComponent.cpp`
  - Transport controls now treat either loaded audio or loaded MIDI as playable media.
  - Play/status/progress labels can represent audio-file playback, not only MIDI playback.

### Preserved behavior

- Generated MIDI remains loaded for piano-roll/visualization and as fallback if the audio file is missing or cannot be decoded.
- Explicit MIDI loading clears stale audio-file playback so a failed new audio load cannot accidentally keep playing an older mastered WAV.
- No CMake/source-list change was required because the existing JUCE target already links the needed audio modules.

### Verification proof

Commands run from `c:\dev\MUSE-ai\MUSE`:

```powershell
npm run build:debug
npm run build
.\.venv\Scripts\python.exe -m pytest tests/test_protocol.py tests/test_smoke_1990s_rock_contract.py tests/test_golden_prompts_smoke.py -q
git diff --check
.\.venv\Scripts\python.exe -c "import json, pathlib; [json.loads(pathlib.Path(p).read_text(encoding='utf-8')) for p in ['.github/state/orchestration.json','.github/state/memory.json','.github/state/context.json']]; print('state json valid')"
```

Results:

- Debug build: `PASS`.
- Release build: `PASS` after stopping the already-running Release app process that was locking `AI Music Generator.exe`.
- Focused backend/protocol/golden tests: `65 passed, 6 existing librosa warnings`.
- `git diff --check`: `PASS`.
- State JSON parse: `PASS`.

### Remaining follow-up

This closes recommendation 1. The next highest-priority recommendation is to make the app FX/mastering path explicit: either route live MIDI/sampler playback through `MixerGraph::processBlock()` and wire `MasteringSuitePanel` to real processing, or clearly label the MIDI path as an unmastered preview while the generated WAV remains the mastered playback reference.

## App FX/mastering preview honesty implementation — 2026-05-14

Status: **implemented and verified** for the safe half of recommendation 2.

### Decision

The live `MixerGraph::processBlock()` route was intentionally **not** enabled in this slice. Source review found that the current graph mutation/routing path needs hardening before it can safely process the real-time MIDI/sampler preview:

- `MixerGraph::reconnectFXChain()` only handles the `master` bus and does not wire `drums`, `bass`, or `melodic` buses as real-time buses yet.
- Master-chain reconnect removes connections into the master gain node and connects the last FX node to master gain, but the input/track-output-to-first-FX wiring is still incomplete.
- `MainComponent::fxChainChanged()` mutates the graph from the UI/message path while the audio callback would process it if `processBlock()` were added, so graph update thread-safety needs an explicit design.
- The default master graph gain is `+9 dB`, which must never be applied to backend-mastered WAV playback.

Given those risks, this slice chose the safe/explicit path from the plan: **the generated WAV is labeled as the mastered backend reference, and MIDI playback is labeled as an unmastered preview/fallback until real-time FX routing is implemented.**

### What changed

- `juce/Source/UI/TransportComponent.cpp`
  - Audio playback/status now says `mastered audio/reference`.
  - MIDI-only load/play/status now says `unmastered MIDI preview/fallback`.
- `juce/Source/MainComponent.cpp`
  - Generation completion now labels `audioPath` as `Generated mastered audio (backend)` or `Loaded mastered audio/reference`.
  - MIDI fallback/visualization path is labeled `unmastered MIDI preview/fallback`.
  - Completion-message text distinguishes `Mastered audio reference (backend)` from `Unmastered MIDI preview/fallback`.
  - Recent-file selection status also labels audio vs MIDI accordingly.
- `juce/Source/UI/Mastering/MasteringSuitePanel.h/.cpp`
  - Added a visible header notice: `WAV: backend mastered | Live MIDI: unmastered (controls not in preview yet)`.
  - Added tooltip text clarifying that generated WAV playback uses backend mastering and live MIDI preview is not processed by those controls yet.

### Verification proof

Commands/checks run from `c:\dev\MUSE-ai\MUSE`:

```powershell
Select-String -Path juce\Source\Audio\AudioEngine.cpp -Pattern "mixerGraph\.processBlock"
Select-String -Path juce\Source\UI\TransportComponent.cpp,juce\Source\MainComponent.cpp,juce\Source\UI\Mastering\MasteringSuitePanel.* -Pattern "unmastered|mastered"
npm run build:debug
npm run build
.\.venv\Scripts\python.exe -m pytest tests/test_protocol.py tests/test_smoke_1990s_rock_contract.py tests/test_golden_prompts_smoke.py -q
git diff --check
```

Results:

- `AudioEngine.cpp` contains **no** new `mixerGraph.processBlock` call.
- Expected `mastered`/`unmastered` labels are present in Transport, MainComponent, and MasteringSuitePanel.
- Debug build: `PASS`.
- Release build: `PASS` with existing warning noise only.
- Focused backend/protocol/golden tests: `65 passed, 6 existing librosa warnings`.
- `git diff --check`: `PASS`.

### Remaining follow-up

Recommendation 2 is now honest in the UI, but not fully real-time processed. A future real-time FX/mastering slice should first harden `MixerGraph` routing and thread-safety, then route **only** unmastered live MIDI/sampler preview through the graph while keeping backend-mastered WAV playback untouched.

## Transport status readability polish — 2026-05-18

Status: **implemented and verified** as the first post-consolidation UI/UX polish slice after Tasks 066–068.

### What changed

- `juce/Source/UI/TransportComponent.h/.cpp`
  - Added a small `setStatusText()` helper so transport status text, colour, and tooltip stay synchronized.
  - Preserved the exact truthful playback labels introduced by the FX/mastering honesty slice: backend WAV playback remains `mastered audio/reference`, and MIDI-only playback remains `unmastered MIDI preview/fallback`.
  - Changed the status label to left-aligned text so the important prefix is visible first when space is constrained.
  - Replaced the old fixed `140px` status-label allocation with a bounded dynamic width that can expand up to `320px` while preserving fixed BPM and Test Tone controls.
  - The full status string is now available as the label tooltip when visible text is clipped.

### Preserved behavior

- No backend, Python server, OSC protocol, audio renderer, `AudioEngine`, `MixerGraph`, or mastering routing behavior changed.
- No `mixerGraph.processBlock()` route was added.
- The running Release app/server were not stopped during implementation; this polish appears after rebuild/relaunch.

### Verification proof

Commands/checks run from `c:\dev\MUSE-ai\MUSE`:

```powershell
git diff --check
Select-String -Path juce\Source\UI\TransportComponent.cpp,juce\Source\UI\TransportComponent.h -Pattern "withWidth\(140\.0f\)|statusLabel\.setTooltip|setStatusText|mastered audio/reference|unmastered MIDI preview/fallback"
Select-String -Path juce\Source\Audio\AudioEngine.cpp -Pattern "mixerGraph\.processBlock"
& "C:\Program Files\Microsoft Visual Studio\2022\Community\MSBuild\Current\Bin\MSBuild.exe" juce\build\MultimodalMusicGen.sln /m /p:Configuration=Debug /p:Platform=x64 /v:minimal
.\.venv\Scripts\python.exe -m pytest -p no:cacheprovider tests/test_protocol.py tests/test_smoke_1990s_rock_contract.py tests/test_golden_prompts_smoke.py -q
```

Results:

- VS Code diagnostics for `TransportComponent.h/.cpp`: no errors.
- `git diff --check`: `PASS`.
- Static checks: no old `withWidth(140.0f)` status allocation remains; `statusLabel.setTooltip` is centralized in `setStatusText`; mastered/unmastered labels remain present; `AudioEngine.cpp` still has no `mixerGraph.processBlock` route.
- Debug JUCE build: `PASS` via MSBuild, with existing warning noise only.
- Protocol/smoke/golden guard tests: `67 passed`, with 6 existing librosa warnings.

## Rock app instrument preview parity implementation — 2026-05-14

Status: **implemented and verified** for recommendation 3.

### What changed

- `juce/Source/MainComponent.cpp`
  - Added a small rock-family genre helper for generated-project instrument selection.
  - `preferredCategoriesForTrack()` now receives the generated result genre instead of relying on track name alone.
  - For rock-family generated projects, Chords/Pad/Keys/Piano tracks now prefer `guitar` before pad/keys/synth/string/brass fallbacks.
  - For rock-family Melody/Lead/Arp tracks, the app now also prefers `guitar` before synth/keys-style fallbacks.
  - Track names that explicitly contain `guitar` prefer guitar samples regardless of genre.
  - Non-rock preference order is preserved.
- `multimodal_gen/instrument_manager.py`
  - Added `guitar` to `InstrumentMatcher.get_recommendations()` so backend `instruments_used` metadata can expose guitar when guitar samples are available.
- `tests/test_instrument_manager.py`
  - Added a focused guard proving the recommendation list includes `guitar`, alongside existing first-class guitar categorization checks.

### Preserved behavior

- Backend mastered WAV playback remains the primary generated-song playback path in the app.
- MIDI/live preview remains labeled as an unmastered preview/fallback.
- No `MixerGraph::processBlock()` route was added.
- Non-rock genres keep their previous app preview category ordering.
- If no guitar sample is available, the existing category fallback loop still falls through to pad/keys/synth/string/brass choices.
- `InstrumentBrowserPanel` already had first-class `guitar`/`guitars` category color support, so no UI category-list change was required.

### Verification proof

Commands/checks run from `c:\dev\MUSE-ai\MUSE`:

```powershell
git diff --check
.\.venv\Scripts\python.exe -m pytest tests/test_instrument_manager.py tests/test_smoke_1990s_rock_contract.py tests/test_golden_prompts_smoke.py -q
npm run build:debug
```

Results:

- `git diff --check`: `PASS`.
- Focused tests: `30 passed`.
- Debug JUCE build: `PASS`.
- VS Code diagnostics for touched C++/Python files: no errors.
- Post-verifier: `PASS_WITH_NITS` before style cleanup, then nits were fixed and tests re-ran cleanly.

### Remaining follow-up

Recommendation 3 is now covered for the app preview/category-mapping surface and backend recommendation metadata. The next highest-priority slice is the FluidSynth/SoundFont proof: verify/install FluidSynth and a licensed SoundFont, run audio diagnostics, regenerate the exact rock prompt, and assert the selected renderer path in render diagnostics before moving to post-FluidSynth mastering parity.

## FluidSynth/SoundFont proof guardrails — 2026-05-14

Status: **implemented and verified** for the code/documentation half of recommendation 4. The local runtime proof at this point showed FluidSynth and a SoundFont were still **not installed** on this machine, so this slice intentionally did not vendor or download third-party binaries.

> 2026-05-14 update: this environment-only limitation was superseded by the later external runtime proof below. The repo still does not vendor SoundFont binaries; the local `.sf3` asset remains ignored.

### Environment proof

Commands/checks run from `c:\dev\MUSE-ai\MUSE`:

```powershell
Get-Command fluidsynth
where.exe fluidsynth
.\.venv\Scripts\python.exe main.py --diagnose-audio
```

Results:

- `fluidsynth` executable: not found in PATH.
- `assets/soundfonts/`: exists, but contains only `README.md`.
- `main.py --diagnose-audio` reports:
  - `fluidsynth.available=false`
  - `fluidsynth.version=null`
  - `soundfont.discovered=null`
  - `soundfonts_dir_exists=true`
  - `default_audio_file_count=1485`

### What changed

- `scripts/smoke_1990s_rock.ps1`
  - `smoke_summary.json` now includes a `renderer_diagnostics` object derived from the render report.
  - Captured fields include `renderer_path`, `soundfont_path`, `require_soundfont`, and FluidSynth `available`, `version`, `enabled`, `allowed`, `attempted`, `success`, and `skip_reason`.
  - Existing strict-audio semantics are unchanged.
- `tests/test_smoke_1990s_rock_contract.py`
  - Added static contract coverage that the smoke script writes the renderer/SoundFont/FluidSynth diagnostic fields.
- `tests/test_render_report_schema.py`
  - Added no-install FluidSynth diagnostics coverage.
  - Added deterministic `require_soundfont=True` fail-fast coverage proving a no-FluidSynth/no-SoundFont render returns `False`, reports `renderer_path="none"`, `skip_reason="require_soundfont"`, and preserves the structured render failure.
- `assets/soundfonts/README.md`
  - Expanded the setup guide with Windows/macOS/Linux FluidSynth installation options, no-bundled-SoundFonts policy, expected SoundFont names, explicit `--soundfont` usage, `--diagnose-audio` verification, and strict studio mode.
  - The documented JSON example now matches the actual `main.py --diagnose-audio` schema.
- `.gitignore`
  - Added `.sf3`/`.sfz` SoundFont variants to the existing SoundFont binary ignore rules.

### Verification proof

Commands/checks run from `c:\dev\MUSE-ai\MUSE`:

```powershell
git diff --check
.\.venv\Scripts\python.exe -m pytest tests/test_render_report_schema.py tests/test_smoke_1990s_rock_contract.py -q
.\.venv\Scripts\python.exe main.py --diagnose-audio
```

Results:

- `git diff --check`: `PASS`.
- Focused tests: `10 passed`.
- Diagnostics command: `PASS`, with FluidSynth unavailable and no SoundFont discovered as expected for the current environment.
- Post-verifier: initial `FAIL` caught the stale README field names and an environment-dependent test; after fixes, second post-verifier returned `PASS`.
- VS Code diagnostics for touched files: no errors.

### Remaining follow-up

Recommendation 4 is now proof-ready: future smoke artifacts can prove whether a run used FluidSynth, skipped it, or fell back to procedural rendering. To actually make local FluidSynth renders happen, install the external FluidSynth binary and place a licensed `.sf2` under `assets/soundfonts/` or pass `--soundfont` explicitly.

The next highest-priority item is recommendation 5: **post-FluidSynth mastering parity**. Source review still shows the FluidSynth success path runs `_post_process()` textures, then returns; it does not yet share the full procedural master chain stages such as multiband dynamics, spectral processing, auto-gain staging, and true-peak limiting.

## Post-FluidSynth mastering parity implementation — 2026-05-14

Status: **implemented and verified** for recommendation 5 at the code/test level. Because this machine still has no real FluidSynth binary or SoundFont, the FluidSynth success path was verified with a no-install monkeypatched renderer that writes a WAV and returns success.

### What changed

- `multimodal_gen/audio_renderer.py`
  - Successful FluidSynth renders now run a file-level mastering pass before texture `_post_process()` and before the render report is finalized.
  - Added `_apply_file_level_mastering(audio_path, parsed=None, stage_prefix="file_mastering")` for already-rendered WAV files.
  - The file-level pass loads the WAV, ensures stereo processing, applies the master bus chain where available, convolution reverb send, multiband dynamics, spectral processing, reference matching if active, soft clipping, LUFS-targeted auto-gain staging with fallback normalization, and true-peak limiting with fallback limiting.
  - The mastered file is saved back as 16-bit WAV with dither via the existing `save_wav()` helper.
  - FluidSynth mastering stages are recorded in the render report with a `fluidsynth_file_mastering.*` prefix, including `status`, `auto_gain_staging`, and `true_peak_limiter`.
  - If file-level mastering fails, the FluidSynth WAV still remains a successful render, but the render report receives a warning: `FluidSynth file-level mastering failed; output may be unmastered`.
  - `_reset_render_diagnostics()` now resets `_pipeline_stages` so sequential FluidSynth/procedural renders cannot leak stale mastering-stage diagnostics.
- `tests/test_audio_renderer.py`
  - Added a no-install FluidSynth integration test that monkeypatches `render_midi_with_fluidsynth()` to write a WAV, forces a fake SoundFont path, runs `render_midi_file()`, and verifies renderer path, FluidSynth success, prefixed mastering stages, and finite/limited output.
  - Added a direct unit test for `_apply_file_level_mastering()` using a synthetic loud WAV.

### Preserved behavior

- The procedural `_render_procedural()` path was not refactored or replaced in this slice.
- Procedural fallback behavior remains unchanged when FluidSynth is unavailable, skipped, or fails.
- No real FluidSynth binary, SoundFont asset, or large third-party file was installed, downloaded, or committed.
- JUCE app playback parity and MIDI preview/mastering honesty labels were untouched.

### Verification proof

Commands/checks run from `c:\dev\MUSE-ai\MUSE`:

```powershell
git diff --check
.\.venv\Scripts\python.exe -m pytest tests/test_audio_renderer.py tests/test_render_report_schema.py -q
.\.venv\Scripts\python.exe -m pytest tests/test_smoke_1990s_rock_contract.py tests/test_golden_prompts_smoke.py -q
```

Results:

- `git diff --check`: `PASS`.
- Audio renderer + render report tests: `16 passed`, with 2 existing Python 3.13/audioread deprecation warnings.
- Smoke contract + golden prompts: `27 passed`.
- Post-verifier: first pass `PASS_WITH_NITS` required pipeline-stage reset; second pass confirmed the fix. The verifier mentioned a possible numba/LLVM environmental issue, but the focused suite passed in the main terminal.
- VS Code diagnostics for touched files: no errors.

### Remaining follow-up

This closes the post-FluidSynth mastering parity code path, but real end-to-end SoundFont timbre proof still requires installing the external FluidSynth binary and placing a licensed SoundFont under `assets/soundfonts/` or passing `--soundfont`. Once that environment is available, run the 1990s rock smoke and inspect `smoke_summary.json.renderer_diagnostics.renderer_path == "fluidsynth"` plus the render report `pipeline_stages.fluidsynth_file_mastering.*` entries.

## External FluidSynth/SoundFont runtime proof — 2026-05-14

Status: **implemented and verified** for recommendation 4's external runtime half and recommendation 5's real-file proof. The machine now has a local portable FluidSynth binary and a licensed local SoundFont asset, but neither binary nor SoundFont is committed to the repo.

### External assets and licensing posture

- FluidSynth binary: `C:\dev\MUSE-ai\tools\fluidsynth-2.4.7-win10-x64\bin\fluidsynth.exe`
  - `fluidsynth -V` reports `FluidSynth runtime version 2.4.7` / `FluidSynth executable version 2.4.7`.
  - Important Windows-portable finding: this official build is compiled without getopt support. It rejects long options such as `--version`, and it requires FluidSynth render options before positional SoundFont/MIDI arguments.
- Local SoundFont: `assets\soundfonts\FluidR3Mono_GM.sf3`
  - Size: `23712790` bytes.
  - SHA256: `2AACD036D7058D40A371846EF2F5DC5F130D648AB3837FE2626591BA49A71254`.
  - License source: MuseScore/FluidR3Mono-derived MIT notices were checked from the upstream SoundFont documentation.
  - Git status proof: `!! assets/soundfonts/FluidR3Mono_GM.sf3`, so the local SoundFont remains ignored and uncommitted.

### What changed

- `multimodal_gen/audio_renderer.py`
  - `check_fluidsynth_available()` and `get_fluidsynth_version()` now try `--version` first, then fall back to `-V` for Windows portable builds.
  - `find_soundfont()` now discovers `.sf3` SoundFonts before falling back to existing `.sf2` names.
  - `render_midi_with_fluidsynth()` now constructs a no-getopt-safe command: split `-n`/`-i`, put `-F` and `-r` before SoundFont/MIDI, then pass SoundFont and MIDI as positional arguments. This prevents the Windows portable build from interpreting render options as filenames or dropping into a shell.
  - When `use_fluidsynth=False`, default SoundFont discovery is no longer reported in disabled-renderer diagnostics.
- `multimodal_gen/synthesizers/fluidsynth_synth.py`
  - Mirrors the `-V` detection fallback, `.sf3` discovery, options-first command ordering, and render timeout for the synthesizer abstraction wrapper.
- `main.py` and `assets/soundfonts/README.md`
  - User-facing SoundFont help/docs now include `.sf3`.
  - README documents the `fluidsynth -V` fallback for official Windows portable builds.
- Tests
  - Added regression coverage for `--version`/`-V` detection, `.sf3` discovery, no-getopt-safe command ordering, and wrapper timeout behavior.

### Runtime diagnostics proof

Commands/checks run from `c:\dev\MUSE-ai\MUSE` with `C:\dev\MUSE-ai\tools\fluidsynth-2.4.7-win10-x64\bin` prepended to `PATH`:

```powershell
Get-Command fluidsynth
fluidsynth -V
Get-FileHash assets\soundfonts\FluidR3Mono_GM.sf3 -Algorithm SHA256
git status --short --ignored --untracked-files=all assets/soundfonts
.\.venv\Scripts\python.exe main.py --diagnose-audio
```

Results:

- `Get-Command fluidsynth`: `C:\dev\MUSE-ai\tools\fluidsynth-2.4.7-win10-x64\bin\fluidsynth.exe`.
- `main.py --diagnose-audio` reports:
  - `fluidsynth.available=true`
  - `fluidsynth.version` includes `FluidSynth runtime version 2.4.7` and `Sample type=float`
  - `soundfont.discovered="./assets/soundfonts/FluidR3Mono_GM.sf3"`
  - `soundfonts_dir_exists=true`
  - `default_audio_file_count=1485`

### Real renderer-path proof

The first exact full-CLI rock attempt used an explicit empty instrument directory to avoid the custom-drum skip condition, but it stalled in unrelated expansion/instrument registration chatter before reaching the render proof. Rather than misreport that as a FluidSynth failure, the verified proof used a controlled rock MIDI that bypasses expansion bootstrap while exercising the same `AudioRenderer.render_midi_file()` FluidSynth branch and the same file-level mastering pass.

Artifacts:

- MIDI: `output\external_fluidsynth\controlled_renderer_proof\rock_controlled_input.mid`
- WAV: `output\external_fluidsynth\controlled_renderer_proof\rock_controlled_fluidsynth.wav`
- Render report: `output\external_fluidsynth\controlled_renderer_proof\rock_controlled_render_report.json`

Render report proof:

- `renderer_path="fluidsynth"`
- `fluidsynth.available=true`
- `fluidsynth.attempted=true`
- `fluidsynth.success=true`
- `fluidsynth.skip_reason=null`
- `soundfont_path="assets\\soundfonts\\FluidR3Mono_GM.sf3"`
- `render_status.success=true`
- WAV size: `6778924` bytes
- `estimated_lufs=-20.5`
- `peak_dbfs=-1.3`
- `pipeline_stages.fluidsynth_file_mastering.status="applied"`
- `pipeline_stages.fluidsynth_file_mastering.auto_gain_staging="target=-14.0"`
- `pipeline_stages.fluidsynth_file_mastering.true_peak_limiter="ceiling=-1.0dBTP"`

Important interpretation: the controlled proof's `audio_analysis.passed=false` is not a FluidSynth-path failure. It reflects the intentionally tiny hand-authored MIDI used for renderer proof (`genre_match_score=0.58`, analyzer says snare/hihat evidence is weak and top end is bright). The proof objective here was external renderer selection, SoundFont use, and post-FluidSynth mastering parity; full musical rock-quality validation remains the strict 1990s rock generation smoke.

### Verification proof

Commands/checks run from `c:\dev\MUSE-ai\MUSE`:

```powershell
git diff --check
.\.venv\Scripts\python.exe -m pytest tests/test_audio_renderer.py tests/test_render_report_schema.py tests/test_synthesizers.py -q
```

Results:

- `git diff --check`: `PASS`.
- Focused tests: `52 passed`, with 2 existing Python 3.13/audioread deprecation warnings.
- Manual command proof:
  - Positional-first/attached attempts timed out and logged `fluid_is_soundfont(): fopen() failed: 'File does not exist.'`
  - Options-first command `fluidsynth -n -i -F <wav> -r 48000 <sf3> <midi>` exited `0` and wrote a `7376940` byte WAV.

### Remaining follow-up

- Add a safe CLI/runtime switch for exact smoke isolation if we want full-prompt FluidSynth proof without the heavy expansion bootstrap and default custom drum/sample auto-load.
- Improve the controlled rock MIDI/analyzer fixture if future CI needs the proof artifact to pass rock audio analysis as well as renderer-path assertions.

## Procedural tempo-map / rendered silence-gap fix — 2026-05-14

Status: **implemented and verified** for the reported periodic silent/low-level gaps in generated test songs. The controlled FluidSynth proof artifact still has intentional hand-authored rests, but the full generated/procedural 100 BPM rock WAV was not supposed to collapse into a low-level tail around the old 120 BPM-compressed endpoint.

### Root cause

- The generated rock MIDI stores `set_tempo=600000` (100 BPM) on the meta track / track 0.
- `mido.MidiFile.length` correctly uses that global tempo map, so `_render_procedural()` sized the output buffer to the real song length: `38.719s` plus the configured tail.
- `_render_track_procedural()` converted each note track independently with a local default tempo of `500000` microseconds per beat (120 BPM) unless that specific note track contained `set_tempo`.
- Because the note tracks had no tempo messages, notes were rendered too early and ended near the 120 BPM-compressed position (`~32.266s`) while the buffer remained sized for the 100 BPM song, causing an audible/visible near-silent tail from roughly `33.7s` onward.

### What changed

- `multimodal_gen/audio_renderer.py`
  - Added `DEFAULT_MIDI_TEMPO = 500000` and a `MidiTempoMap` helper.
  - `MidiTempoMap.from_midi_file()` collects absolute-tick `set_tempo` events from all MIDI tracks and always provides the MIDI default tempo at tick 0 when needed.
  - `MidiTempoMap.tick_to_sample()` and `tick_delta_to_samples()` convert arbitrary absolute ticks to samples while honoring tempo changes.
  - `_render_procedural()` now builds one global tempo map from the full MIDI file and passes it to every track render.
  - `_render_track_procedural()` now uses the shared tempo map for note `start_sample` and `duration_samples`; if called directly without a map, it still builds a local map for backwards compatibility.
  - `render_stems()` now uses the same global tempo map so stems stay aligned with the full mix.
- `tests/test_audio_renderer.py`
  - Added a regression where tempo exists only on track 0 at 100 BPM and notes live on track 1. The test captures `SynthNote` timing and verifies `start_sample == 423360` and `duration_samples == 52920`, explicitly rejecting the old 120 BPM fallback value `352800`.
  - Added a control regression confirming files with no tempo event still use MIDI's default 120 BPM behavior.

### Runtime proof

Commands/checks run from `c:\dev\MUSE-ai\MUSE`:

```powershell
git diff --check
.\.venv\Scripts\python.exe -m pytest tests/test_audio_renderer.py -q
.\.venv\Scripts\python.exe -m pytest tests/test_render_report_schema.py -q
```

Results:

- `git diff --check`: `PASS`.
- Audio renderer tests: `24 passed`, with 2 existing Python 3.13/audioread deprecation warnings.
- Render report schema tests: `5 passed`.
- VS Code diagnostics for touched Python files: no errors.
- Post-verifier: `PASS_WITH_NITS`; the only nits were lack of a dedicated `render_stems()` regression and an unrelated intermittent native `numba/llvmlite` abort in an older output-analysis path.

Artifact comparison:

- MIDI: `output\_diagnostics\rock_1990s_20260514_091707\rock_100.0bpm_Eminor_20260514_091711.mid`
- Old WAV: `output\_diagnostics\rock_1990s_20260514_091707\rock_100.0bpm_Eminor_20260514_091711.wav`
  - Duration: `40.719s`.
  - First long section below `-45 dBFS`: `33.7s → 40.7s`.
  - Last active window: `33.675s`.
- Fixed WAV: `output\gap_fix_proof\rock_100bpm_Eminor_tempo_map_fix.wav`
  - Duration: `40.719s`.
  - First long section below `-45 dBFS`: `null`.
  - Last active window: `40.175s`.
  - Render report: `output\gap_fix_proof\rock_100bpm_Eminor_tempo_map_fix_render_report.json`
  - `renderer_path="procedural"`, `render_status.success=true`.

### Interpretation

The answer to the listening question is therefore split:

- **Controlled FluidSynth proof gaps:** expected for that tiny hand-authored technical proof MIDI because it contains rests.
- **Full generated/procedural rock-song gaps or long near-silent tails:** **not expected**. They were a procedural tempo-map bug and are now fixed by sharing the global MIDI tempo map across note tracks and stems.
