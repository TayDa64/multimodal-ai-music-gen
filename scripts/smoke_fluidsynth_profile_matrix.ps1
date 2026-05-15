[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$SoundFont,
    [string]$OutputRoot = "output\_diagnostics\fluidsynth_profile_matrix",
    [int]$DurationBars = 8,
    [int]$Seed = 49049,
    [int]$TimeoutSeconds = 480
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = (Resolve-Path (Join-Path $ScriptDir "..")).Path
$RockToneDiagnostic = "high_shelf=-6.0dB@5000Hz;low_shelf=-0.75dB@90Hz"

$Cases = @(
    [ordered]@{
        id = "rock_control"
        prompt = "1990's era rock song with crunchy electric guitar, live drums, bass guitar, verse chorus bridge, energetic band performance, 100 BPM in E minor"
        expected_parsed_genres = @("rock")
        expected_profile = "rock:rock"
        expected_tone_shaping = $RockToneDiagnostic
        expected_rock_tone_shaping = $RockToneDiagnostic
        notes = "Control case for the existing green exact rock FluidSynth profile and tone diagnostic."
    },
    [ordered]@{
        id = "cinematic_classical"
        prompt = "cinematic orchestral film score with strings, brass, choir, timpani, 96 BPM in D minor"
        expected_parsed_genres = @("cinematic", "classical")
        expected_profile = "classical:classical"
        expected_tone_shaping = $null
        expected_rock_tone_shaping = $null
        notes = "First-class cinematic/classical route; profile is intentionally a no-op measurement baseline."
    },
    [ordered]@{
        id = "trap_modern_beat"
        prompt = "dark trap beat with 808 bass, snare, hihat rolls, modern beat energy, 140 BPM in C minor"
        expected_parsed_genres = @("trap", "trap_soul")
        expected_profile = "trap_modern_beat:modern_beat"
        expected_tone_shaping = $null
        expected_rock_tone_shaping = $null
        notes = "First-class trap/modern-beat route; profile is intentionally a no-op measurement baseline."
    },
    [ordered]@{
        id = "generic_jazz"
        prompt = "small-combo jazz quartet with walking bass, ride cymbal, piano comping, 120 BPM in Bb major"
        expected_parsed_genres = @("jazz")
        expected_profile = "jazz:jazz"
        expected_tone_shaping = $null
        expected_rock_tone_shaping = $null
        notes = "First-class generic jazz route; profile is intentionally a no-op measurement baseline."
    }
)

$DeferredCases = @()

function Resolve-MatrixPath {
    param([Parameter(Mandatory = $true)][string]$PathValue)
    if ([System.IO.Path]::IsPathRooted($PathValue)) {
        return $PathValue
    }
    return (Join-Path $RepoRoot $PathValue)
}

function Resolve-ArtifactPath {
    param(
        [string]$BaseDirectory,
        [string]$PathValue
    )
    if ([string]::IsNullOrWhiteSpace($PathValue)) {
        return $null
    }
    if ([System.IO.Path]::IsPathRooted($PathValue)) {
        return $PathValue
    }
    return (Join-Path $BaseDirectory $PathValue)
}

function Read-JsonOrNull {
    param([string]$PathValue)
    if ([string]::IsNullOrWhiteSpace($PathValue) -or -not (Test-Path -LiteralPath $PathValue)) {
        return $null
    }
    try {
        return Get-Content -LiteralPath $PathValue -Raw | ConvertFrom-Json
    }
    catch {
        return $null
    }
}

function Get-LatestArtifactPath {
    param(
        [string]$Directory,
        [string]$Filter
    )
    $artifact = Get-ChildItem -LiteralPath $Directory -Filter $Filter -File -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTimeUtc -Descending |
        Select-Object -First 1
    if ($artifact) {
        return $artifact.FullName
    }
    return $null
}

function Get-FirstAnalysisIssueMessage {
    param($AudioAnalysis)
    if (-not $AudioAnalysis -or -not $AudioAnalysis.issues) {
        return $null
    }
    $firstIssue = @($AudioAnalysis.issues) | Select-Object -First 1
    if ($firstIssue -and $firstIssue.message) {
        return [string]$firstIssue.message
    }
    return $null
}

function Invoke-ProfileMatrixCase {
    param(
        [Parameter(Mandatory = $true)]$Case,
        [Parameter(Mandatory = $true)][string]$RunRoot,
        [Parameter(Mandatory = $true)][string]$PythonPath,
        [Parameter(Mandatory = $true)][string]$MainPath,
        [Parameter(Mandatory = $true)][string]$ResolvedSoundFont,
        [Parameter(Mandatory = $true)][int]$CaseIndex
    )

    $caseOutputDir = Join-Path $RunRoot ([string]$Case.id)
    New-Item -ItemType Directory -Force -Path $caseOutputDir | Out-Null

    $stdoutPath = Join-Path $caseOutputDir "generation.stdout.log"
    $stderrPath = Join-Path $caseOutputDir "generation.stderr.log"
    $caseSeed = $Seed

    $childArgs = @(
        $MainPath,
        ([string]$Case.prompt),
        "--output",
        $caseOutputDir,
        "--duration-bars",
        ([string]$DurationBars),
        "--seed",
        ([string]$caseSeed),
        "--no-banner",
        "--skip-default-instruments",
        "--skip-expansions",
        "--require-soundfont",
        "--soundfont",
        $ResolvedSoundFont
    )

    $psi = [System.Diagnostics.ProcessStartInfo]::new()
    $psi.FileName = $PythonPath
    $psi.WorkingDirectory = $RepoRoot
    $psi.UseShellExecute = $false
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    foreach ($arg in $childArgs) {
        [void]$psi.ArgumentList.Add($arg)
    }

    $process = [System.Diagnostics.Process]::new()
    $process.StartInfo = $psi
    [void]$process.Start()
    $pidValue = $process.Id
    $stdoutTask = $process.StandardOutput.ReadToEndAsync()
    $stderrTask = $process.StandardError.ReadToEndAsync()

    $timeoutMilliseconds = [Math]::Max(1, $TimeoutSeconds) * 1000
    $timedOut = -not $process.WaitForExit($timeoutMilliseconds)
    if ($timedOut) {
        try {
            $process.Kill($true)
        }
        catch {
            try { $process.Kill() } catch { }
        }
    }

    try { $process.WaitForExit() } catch { }
    $stdoutText = $stdoutTask.GetAwaiter().GetResult()
    $stderrText = $stderrTask.GetAwaiter().GetResult()
    Set-Content -LiteralPath $stdoutPath -Value $stdoutText -Encoding UTF8
    Set-Content -LiteralPath $stderrPath -Value $stderrText -Encoding UTF8

    $childExitCode = if ($timedOut) { 124 } else { $process.ExitCode }

    $metadataPath = Join-Path $caseOutputDir "project_metadata.json"
    $metadata = Read-JsonOrNull $metadataPath
    if (-not $metadata) {
        $metadataPath = $null
    }

    $outputs = $null
    $parsed = $null
    if ($metadata -and $metadata.current) {
        $outputs = $metadata.current.outputs
        $parsed = $metadata.current.parsed
    }

    $generatedMidi = if ($outputs -and $outputs.midi) { Resolve-ArtifactPath $caseOutputDir ([string]$outputs.midi) } else { Get-LatestArtifactPath $caseOutputDir "*.mid" }
    $generatedAudio = if ($outputs -and $outputs.audio) { Resolve-ArtifactPath $caseOutputDir ([string]$outputs.audio) } else { Get-LatestArtifactPath $caseOutputDir "*.wav" }
    $renderReport = if ($outputs -and $outputs.render_report) { Resolve-ArtifactPath $caseOutputDir ([string]$outputs.render_report) } else { Get-LatestArtifactPath $caseOutputDir "*_render_report.json" }
    $renderError = if ($outputs -and $outputs.render_error) { Resolve-ArtifactPath $caseOutputDir ([string]$outputs.render_error) } else { Get-LatestArtifactPath $caseOutputDir "*_render_error.txt" }

    $renderReportData = Read-JsonOrNull $renderReport
    $renderStatus = if ($renderReportData -and $renderReportData.render_status) { $renderReportData.render_status } else { $null }
    $renderFailure = if ($renderStatus -and $renderStatus.failure) { $renderStatus.failure } else { $null }
    $renderSuccess = if ($renderStatus -and $null -ne $renderStatus.success) { [bool]$renderStatus.success } else { $null }
    $audioAnalysis = if ($renderReportData -and $renderReportData.audio_analysis) { $renderReportData.audio_analysis } else { $null }
    $rendererPath = if ($renderReportData -and $renderReportData.renderer_path) { [string]$renderReportData.renderer_path } else { $null }
    $soundfontPath = if ($renderReportData -and $renderReportData.soundfont_path) { [string]$renderReportData.soundfont_path } else { $null }
    $requireSoundfont = if ($renderReportData -and $null -ne $renderReportData.require_soundfont) { [bool]$renderReportData.require_soundfont } else { $null }
    $fluidsynth = if ($renderReportData -and $renderReportData.fluidsynth) { $renderReportData.fluidsynth } else { $null }
    $fluidsynthAvailable = if ($fluidsynth -and $null -ne $fluidsynth.available) { [bool]$fluidsynth.available } else { $null }
    $fluidsynthVersion = if ($fluidsynth -and $fluidsynth.version) { [string]$fluidsynth.version } else { $null }
    $fluidsynthEnabled = if ($fluidsynth -and $null -ne $fluidsynth.enabled) { [bool]$fluidsynth.enabled } else { $null }
    $fluidsynthAllowed = if ($fluidsynth -and $null -ne $fluidsynth.allowed) { [bool]$fluidsynth.allowed } else { $null }
    $fluidsynthAttempted = if ($fluidsynth -and $null -ne $fluidsynth.attempted) { [bool]$fluidsynth.attempted } else { $null }
    $fluidsynthSuccess = if ($fluidsynth -and $null -ne $fluidsynth.success) { [bool]$fluidsynth.success } else { $null }
    $fluidsynthSkipReason = if ($fluidsynth -and $fluidsynth.skip_reason) { [string]$fluidsynth.skip_reason } else { $null }
    $pipelineStages = if ($renderReportData -and $renderReportData.pipeline_stages) { $renderReportData.pipeline_stages } else { $null }
    $profileDiagnostic = if ($pipelineStages -and $pipelineStages.'fluidsynth_file_mastering.profile') { [string]$pipelineStages.'fluidsynth_file_mastering.profile' } else { $null }
    $toneShapingDiagnostic = if ($pipelineStages -and $pipelineStages.'fluidsynth_file_mastering.tone_shaping') { [string]$pipelineStages.'fluidsynth_file_mastering.tone_shaping' } else { $null }
    $rockToneShapingDiagnostic = if ($pipelineStages -and $pipelineStages.'fluidsynth_file_mastering.rock_tone_shaping') { [string]$pipelineStages.'fluidsynth_file_mastering.rock_tone_shaping' } else { $null }
    $fileMasteringStatus = if ($pipelineStages -and $pipelineStages.'fluidsynth_file_mastering.status') { [string]$pipelineStages.'fluidsynth_file_mastering.status' } else { $null }

    $analysisPresent = $null -ne $audioAnalysis
    $analysisPassed = if ($analysisPresent -and $null -ne $audioAnalysis.passed) { [bool]$audioAnalysis.passed } else { $null }
    $analysisScore = if ($analysisPresent -and $null -ne $audioAnalysis.genre_match_score) { [double]$audioAnalysis.genre_match_score } else { $null }
    $analysisFailureReason = if ($analysisPassed -eq $false) { Get-FirstAnalysisIssueMessage $audioAnalysis } else { $null }
    if (($analysisPassed -eq $false) -and -not $analysisFailureReason -and $audioAnalysis.analysis_error) {
        $analysisFailureReason = [string]$audioAnalysis.analysis_error
    }

    $parsedGenre = if ($parsed -and $parsed.genre) { [string]$parsed.genre } else { $null }
    $expectedGenres = @($Case.expected_parsed_genres)
    $proofFailures = @()
    if (-not (Test-Path -LiteralPath $ResolvedSoundFont)) {
        $proofFailures += "soundfont_argument_missing"
    }
    if ($timedOut) {
        $proofFailures += "process_timed_out"
    }
    if ($childExitCode -ne 0) {
        $proofFailures += "process_exit_nonzero:$childExitCode"
    }
    if (-not $metadata) {
        $proofFailures += "missing_project_metadata"
    }
    if ([string]::IsNullOrWhiteSpace($renderReport)) {
        $proofFailures += "missing_render_report_artifact"
    }
    if (-not $renderReportData) {
        $proofFailures += "missing_render_report"
    }
    if ($rendererPath -ne "fluidsynth") {
        $proofFailures += "renderer_path_not_fluidsynth:$rendererPath"
    }
    if ($requireSoundfont -ne $true) {
        $proofFailures += "require_soundfont_not_true"
    }
    if ($fluidsynthAttempted -ne $true) {
        $proofFailures += "fluidsynth_attempted_not_true"
    }
    if ($fluidsynthSuccess -ne $true) {
        $proofFailures += "fluidsynth_success_not_true"
    }
    if (-not [string]::IsNullOrWhiteSpace($fluidsynthSkipReason)) {
        $proofFailures += "fluidsynth_skip_reason_present:$fluidsynthSkipReason"
    }
    if ([string]::IsNullOrWhiteSpace($soundfontPath)) {
        $proofFailures += "soundfont_path_missing"
    }
    if ($expectedGenres.Count -gt 0 -and -not ($expectedGenres -contains $parsedGenre)) {
        $proofFailures += "parsed_genre_mismatch:$parsedGenre"
    }
    if ($profileDiagnostic -ne [string]$Case.expected_profile) {
        $proofFailures += "profile_diagnostic_mismatch:$profileDiagnostic"
    }
    if ($null -ne $Case.expected_tone_shaping) {
        if ($toneShapingDiagnostic -ne [string]$Case.expected_tone_shaping) {
            $proofFailures += "tone_shaping_diagnostic_mismatch:$toneShapingDiagnostic"
        }
    }
    elseif (-not [string]::IsNullOrWhiteSpace($toneShapingDiagnostic)) {
        $proofFailures += "unexpected_tone_shaping:$toneShapingDiagnostic"
    }
    if ($null -ne $Case.expected_rock_tone_shaping) {
        if ($rockToneShapingDiagnostic -ne [string]$Case.expected_rock_tone_shaping) {
            $proofFailures += "rock_tone_shaping_diagnostic_mismatch:$rockToneShapingDiagnostic"
        }
    }
    elseif (-not [string]::IsNullOrWhiteSpace($rockToneShapingDiagnostic)) {
        $proofFailures += "unexpected_rock_tone_shaping:$rockToneShapingDiagnostic"
    }

    $caseResult = [ordered]@{
        id = [string]$Case.id
        prompt = [string]$Case.prompt
        notes = [string]$Case.notes
        output_dir = $caseOutputDir
        stdout_path = $stdoutPath
        stderr_path = $stderrPath
        exit_code = $childExitCode
        timed_out = $timedOut
        pid = $pidValue
        seed = $caseSeed
        duration_bars = $DurationBars
        generated_midi = $generatedMidi
        generated_audio = $generatedAudio
        metadata_path = $metadataPath
        render_report = $renderReport
        render_error = $renderError
        parsed_status = [ordered]@{
            genre = $parsedGenre
            expected_genres = $expectedGenres
            bpm = if ($parsed -and $parsed.bpm) { $parsed.bpm } else { $null }
            key = if ($parsed -and $parsed.key) { [string]$parsed.key } else { $null }
            scale = if ($parsed -and $parsed.scale) { [string]$parsed.scale } else { $null }
            instruments = if ($parsed -and $parsed.instruments) { @($parsed.instruments) } else { @() }
            drum_elements = if ($parsed -and $parsed.drum_elements) { @($parsed.drum_elements) } else { @() }
        }
        renderer_diagnostics = [ordered]@{
            renderer_path = $rendererPath
            soundfont_path = $soundfontPath
            require_soundfont = $requireSoundfont
            fluidsynth_available = $fluidsynthAvailable
            fluidsynth_version = $fluidsynthVersion
            fluidsynth_enabled = $fluidsynthEnabled
            fluidsynth_allowed = $fluidsynthAllowed
            fluidsynth_attempted = $fluidsynthAttempted
            fluidsynth_success = $fluidsynthSuccess
            fluidsynth_skip_reason = $fluidsynthSkipReason
        }
        render_status = [ordered]@{
            success = $renderSuccess
            current_stage = if ($renderStatus -and $renderStatus.current_stage) { [string]$renderStatus.current_stage } else { $null }
            failure_reason = if ($renderFailure -and $renderFailure.reason) { [string]$renderFailure.reason } else { $null }
            failure_stage = if ($renderFailure -and $renderFailure.stage) { [string]$renderFailure.stage } else { $null }
            exception_type = if ($renderFailure -and $renderFailure.exception_type) { [string]$renderFailure.exception_type } else { $null }
        }
        profile_diagnostics = [ordered]@{
            expected_profile = [string]$Case.expected_profile
            actual_profile = $profileDiagnostic
            expected_tone_shaping = $Case.expected_tone_shaping
            actual_tone_shaping = $toneShapingDiagnostic
            expected_rock_tone_shaping = $Case.expected_rock_tone_shaping
            actual_rock_tone_shaping = $rockToneShapingDiagnostic
            file_mastering_status = $fileMasteringStatus
            pipeline_stages = $pipelineStages
        }
        audio_analysis = [ordered]@{
            present = $analysisPresent
            passed = $analysisPassed
            genre_match_score = $analysisScore
            failure_reason = $analysisFailureReason
            metrics = $audioAnalysis
        }
        proof_passed = (@($proofFailures).Count -eq 0)
        proof_failures = @($proofFailures)
        command = [ordered]@{
            python = $PythonPath
            main = $MainPath
            args = @($childArgs)
        }
    }

    return $caseResult
}

$outputRootPath = Resolve-MatrixPath $OutputRoot
$soundfontPath = Resolve-MatrixPath $SoundFont
New-Item -ItemType Directory -Force -Path $outputRootPath | Out-Null

$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$runRoot = Join-Path $outputRootPath "matrix_$timestamp"
New-Item -ItemType Directory -Force -Path $runRoot | Out-Null
$summaryPath = Join-Path $runRoot "matrix_summary.json"

$pythonPath = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $pythonPath)) {
    $pythonPath = "python"
}
$mainPath = Join-Path $RepoRoot "main.py"

$caseResults = @()
for ($i = 0; $i -lt $Cases.Count; $i++) {
    $caseResults += Invoke-ProfileMatrixCase `
        -Case $Cases[$i] `
        -RunRoot $runRoot `
        -PythonPath $pythonPath `
        -MainPath $mainPath `
        -ResolvedSoundFont $soundfontPath `
        -CaseIndex $i
}

$failures = @()
foreach ($caseResult in $caseResults) {
    if (@($caseResult.proof_failures).Count -gt 0) {
        $failures += [ordered]@{
            id = $caseResult.id
            proof_failures = @($caseResult.proof_failures)
            output_dir = $caseResult.output_dir
            render_report = $caseResult.render_report
            stdout_path = $caseResult.stdout_path
            stderr_path = $caseResult.stderr_path
        }
    }
}

$summary = [ordered]@{
    schema_version = 1
    matrix_name = "fluidsynth_profile_matrix"
    generated_at = [DateTime]::UtcNow.ToString("yyyy-MM-ddTHH:mm:ssZ")
    repo_root = $RepoRoot
    run_root = $runRoot
    summary_path = $summaryPath
    parameters = [ordered]@{
        soundfont = $soundfontPath
        soundfont_exists = (Test-Path -LiteralPath $soundfontPath)
        output_root = $outputRootPath
        duration_bars = $DurationBars
        seed = $Seed
        timeout_seconds = $TimeoutSeconds
        default_failure_policy = "Fail only process/render-path/profile proof; record audio_analysis.passed=false as measurement data."
        required_runtime_flags = @("--skip-default-instruments", "--skip-expansions", "--require-soundfont", "--soundfont")
    }
    aggregate = [ordered]@{
        case_count = @($caseResults).Count
        deferred_case_count = @($DeferredCases).Count
        proof_passed = (@($failures).Count -eq 0)
        failure_count = @($failures).Count
        failures = @($failures)
    }
    cases = @($caseResults)
    deferred_cases = @($DeferredCases)
}

$summary | ConvertTo-Json -Depth 30 | Set-Content -LiteralPath $summaryPath -Encoding UTF8

if (@($failures).Count -gt 0) {
    exit 3
}

exit 0
