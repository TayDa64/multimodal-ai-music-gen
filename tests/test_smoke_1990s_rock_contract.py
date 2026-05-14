from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "smoke_1990s_rock.ps1"
EXACT_PROMPT = "1990's era rock song with crunchy electric guitar, live drums, bass guitar, verse chorus bridge, energetic band performance, 100 BPM in E minor"


def test_smoke_1990s_rock_script_contract_is_static_and_strict_ready():
    script_text = SCRIPT_PATH.read_text(encoding="utf-8")

    assert EXACT_PROMPT in script_text
    assert "smoke_summary.json" in script_text
    assert "generation.stdout.log" in script_text
    assert "generation.stderr.log" in script_text
    assert "--require-audio" in script_text
    assert "--duration-bars" in script_text
    assert "--seed" in script_text


def test_smoke_1990s_rock_script_passes_prompt_as_one_process_argument():
    script_text = SCRIPT_PATH.read_text(encoding="utf-8")

    assert "Start-Process" not in script_text
    assert "-ArgumentList" not in script_text
    assert ".ArgumentList.Add($arg)" in script_text
    assert "$childArgs = @(" in script_text


def test_smoke_1990s_rock_summary_reports_audio_analysis_contract():
    script_text = SCRIPT_PATH.read_text(encoding="utf-8")

    assert "$audioAnalysis" in script_text
    assert "audio_analysis" in script_text
    assert "analysis_present = $analysisPresent" in script_text
    assert "analysis_passed = $analysisPassed" in script_text
    assert "analysis_score = $analysisScore" in script_text
    assert "analysis_failure_reason = $analysisFailureReason" in script_text
    assert "Get-FirstAnalysisIssueMessage" in script_text


def test_smoke_1990s_rock_strict_audio_fails_explicit_analysis_false_only():
    script_text = SCRIPT_PATH.read_text(encoding="utf-8")

    strict_line = next(
           line
           for line in script_text.splitlines()
           if "$strictAudioFailed =" in line and "-or" in line
    )

    assert "$analysisExplicitFailure = $false" in script_text
    assert "$analysisExplicitFailure = $true" in script_text
    assert "$analysisPassed -eq $false" in script_text
    assert "-or $analysisExplicitFailure" in strict_line
    assert "-or (-not $analysisPresent)" not in strict_line
    assert "-or ($analysisPassed -eq $null)" not in strict_line


def test_smoke_1990s_rock_summary_reports_renderer_diagnostics_contract():
    script_text = SCRIPT_PATH.read_text(encoding="utf-8")

    assert "renderer_diagnostics" in script_text
    assert "renderer_path = $rendererPath" in script_text
    assert "soundfont_path = $soundfontPath" in script_text
    assert "require_soundfont = $requireSoundfont" in script_text
    assert "fluidsynth_available" in script_text
    assert "fluidsynth_version" in script_text
    assert "fluidsynth_enabled" in script_text
    assert "fluidsynth_allowed" in script_text
    assert "fluidsynth_attempted" in script_text
    assert "fluidsynth_success" in script_text
    assert "fluidsynth_skip_reason" in script_text
    assert "$rendererPath = if ($renderReportData -and $renderReportData.renderer_path)" in script_text
    assert "$fluidsynth = if ($renderReportData -and $renderReportData.fluidsynth)" in script_text
