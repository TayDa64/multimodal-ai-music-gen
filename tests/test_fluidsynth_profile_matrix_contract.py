"""Static contract tests for the FluidSynth profile measurement matrix."""

from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "smoke_fluidsynth_profile_matrix.ps1"
ROCK_TONE_DIAGNOSTIC = "high_shelf=-6.0dB@5000Hz;low_shelf=-0.75dB@90Hz"
JAZZ_TONE_DIAGNOSTIC = "high_shelf=-5.0dB@4000Hz"


def _script_text() -> str:
    return SCRIPT_PATH.read_text(encoding="utf-8")


def _cases_block(script_text: str) -> str:
    return script_text.split("$Cases = @(", 1)[1].split("$DeferredCases = @(", 1)[0]


def _case_block(cases_block: str, case_id: str) -> str:
    return cases_block.split(f'id = "{case_id}"', 1)[1].split("    [ordered]@{", 1)[0]


def _proof_block(script_text: str) -> str:
    return script_text.split("$proofFailures = @()", 1)[1].split("$caseResult = [ordered]@", 1)[0]


def test_fluidsynth_profile_matrix_script_exists_and_has_parameters():
    script_text = _script_text()

    assert SCRIPT_PATH.exists()
    assert "matrix_summary.json" in script_text
    assert "generation.stdout.log" in script_text
    assert "generation.stderr.log" in script_text
    assert "[Parameter(Mandatory = $true)]" in script_text
    assert "[string]$SoundFont" in script_text
    assert '[string]$OutputRoot = "output\\_diagnostics\\fluidsynth_profile_matrix"' in script_text
    assert "[int]$DurationBars = 8" in script_text
    assert "[int]$Seed = 49049" in script_text
    assert "[int]$TimeoutSeconds = 480" in script_text
    assert "Resolve-MatrixPath" in script_text


def test_fluidsynth_profile_matrix_runs_isolated_explicit_soundfont_cases():
    script_text = _script_text()

    assert "Start-Process" not in script_text
    assert "-ArgumentList" not in script_text
    assert ".ArgumentList.Add($arg)" in script_text
    assert "--skip-default-instruments" in script_text
    assert "--skip-expansions" in script_text
    assert "--require-soundfont" in script_text
    assert "--soundfont" in script_text
    assert "--duration-bars" in script_text
    assert "--seed" in script_text
    assert "--no-banner" in script_text


def test_fluidsynth_profile_matrix_case_contracts_and_generic_jazz_runtime():
    script_text = _script_text()
    cases_block = _cases_block(script_text)
    generic_jazz_block = _case_block(cases_block, "generic_jazz")

    assert 'id = "rock_control"' in cases_block
    assert 'expected_profile = "rock:rock"' in cases_block
    assert ROCK_TONE_DIAGNOSTIC in script_text
    assert JAZZ_TONE_DIAGNOSTIC in script_text
    assert 'id = "cinematic_classical"' in cases_block
    assert 'expected_profile = "classical:classical"' in cases_block
    assert 'id = "trap_modern_beat"' in cases_block
    assert 'expected_profile = "trap_modern_beat:modern_beat"' in cases_block
    assert 'id = "generic_jazz"' in cases_block
    assert 'expected_parsed_genres = @("jazz")' in generic_jazz_block
    assert 'expected_profile = "jazz:jazz"' in generic_jazz_block
    assert 'expected_tone_shaping = $JazzToneDiagnostic' in generic_jazz_block
    assert 'expected_rock_tone_shaping = $null' in generic_jazz_block
    assert "measured jazz brightness policy" in generic_jazz_block
    assert "$DeferredCases = @()" in script_text
    assert "Deferred: the FluidSynth profile registry has a jazz no-op profile" not in script_text


def test_fluidsynth_profile_matrix_parses_required_artifacts_and_summary_schema():
    script_text = _script_text()

    assert "project_metadata.json" in script_text
    assert "*_render_report.json" in script_text
    assert "renderer_diagnostics" in script_text
    assert "render_status" in script_text
    assert "audio_analysis" in script_text
    assert "pipeline_stages" in script_text
    assert "fluidsynth_file_mastering.profile" in script_text
    assert "profile_diagnostics" in script_text
    assert "aggregate = [ordered]@" in script_text
    assert "proof_failures" in script_text
    assert "deferred_cases" in script_text


def test_fluidsynth_profile_matrix_failure_policy_excludes_audio_analysis_quality():
    script_text = _script_text()
    proof_block = _proof_block(script_text)

    assert "process_exit_nonzero" in proof_block
    assert "missing_render_report" in proof_block
    assert "renderer_path_not_fluidsynth" in proof_block
    assert "require_soundfont_not_true" in proof_block
    assert "fluidsynth_attempted_not_true" in proof_block
    assert "fluidsynth_success_not_true" in proof_block
    assert "fluidsynth_skip_reason_present" in proof_block
    assert "soundfont_path_missing" in proof_block
    assert "profile_diagnostic_mismatch" in proof_block
    assert "unexpected_tone_shaping" in proof_block
    assert "$analysisPassed" not in proof_block
    assert "analysis_passed" not in proof_block
    assert "record audio_analysis.passed=false as measurement data" in script_text
