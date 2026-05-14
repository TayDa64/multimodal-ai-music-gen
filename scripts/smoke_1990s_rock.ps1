[CmdletBinding()]
param(
    [string]$OutputRoot = "output\_diagnostics",
    [int]$DurationBars = 16,
    [int]$Seed = 199001,
    [switch]$StrictAudio,
    [switch]$FluidSynthIsolation,
    [string]$SoundFont
)

$ErrorActionPreference = "Stop"

$Prompt = "1990's era rock song with crunchy electric guitar, live drums, bass guitar, verse chorus bridge, energetic band performance, 100 BPM in E minor"
$Timeout = [TimeSpan]::FromMinutes(8)

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = (Resolve-Path (Join-Path $ScriptDir "..")).Path

function Resolve-SmokePath {
    param([Parameter(Mandatory = $true)][string]$PathValue)
    if ([System.IO.Path]::IsPathRooted($PathValue)) {
        return $PathValue
    }
    return (Join-Path $RepoRoot $PathValue)
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

function First-ArtifactPath {
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

$outputRootPath = Resolve-SmokePath $OutputRoot
New-Item -ItemType Directory -Force -Path $outputRootPath | Out-Null

$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$outputDir = Join-Path $outputRootPath "rock_1990s_$timestamp"
New-Item -ItemType Directory -Force -Path $outputDir | Out-Null

$stdoutPath = Join-Path $outputDir "generation.stdout.log"
$stderrPath = Join-Path $outputDir "generation.stderr.log"
$summaryPath = Join-Path $outputDir "smoke_summary.json"

$pythonPath = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $pythonPath)) {
    $pythonPath = "python"
}

$mainPath = Join-Path $RepoRoot "main.py"
$childArgs = @(
    $mainPath,
    $Prompt,
    "--output",
    $outputDir,
    "--duration-bars",
    ([string]$DurationBars),
    "--seed",
    ([string]$Seed),
    "--no-banner"
)
if ($StrictAudio.IsPresent) {
    $childArgs += "--require-audio"
}
if ($FluidSynthIsolation.IsPresent) {
    $childArgs += "--skip-default-instruments"
    $childArgs += "--skip-expansions"
    $childArgs += "--require-soundfont"
    if (-not [string]::IsNullOrWhiteSpace($SoundFont)) {
        $childArgs += "--soundfont"
        $childArgs += (Resolve-SmokePath $SoundFont)
    }
}

$psi = [System.Diagnostics.ProcessStartInfo]::new()
$psi.FileName = $pythonPath
$psi.WorkingDirectory = $RepoRoot
$psi.UseShellExecute = $false
$psi.RedirectStandardOutput = $true
$psi.RedirectStandardError = $true
foreach ($arg in $childArgs) {
    [void]$psi.ArgumentList.Add($arg)
}

$process = [System.Diagnostics.Process]::new()
$process.StartInfo = $psi
$startedAt = [DateTimeOffset]::UtcNow
[void]$process.Start()
$pidValue = $process.Id
$stdoutTask = $process.StandardOutput.ReadToEndAsync()
$stderrTask = $process.StandardError.ReadToEndAsync()
$timedOut = $false

while (-not $process.HasExited) {
    if (([DateTimeOffset]::UtcNow - $startedAt) -gt $Timeout) {
        $timedOut = $true
        try {
            $process.Kill($true)
        }
        catch {
            try { $process.Kill() } catch { }
        }
        break
    }

    Start-Sleep -Seconds 1
    try { $process.Refresh() } catch { }
}

try { $process.WaitForExit() } catch { }
$stdoutText = $stdoutTask.GetAwaiter().GetResult()
$stderrText = $stderrTask.GetAwaiter().GetResult()
Set-Content -LiteralPath $stdoutPath -Value $stdoutText -Encoding UTF8
Set-Content -LiteralPath $stderrPath -Value $stderrText -Encoding UTF8

$childExitCode = if ($timedOut) { 124 } else { $process.ExitCode }

$metadataPath = Join-Path $outputDir "project_metadata.json"
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

$generatedMidi = if ($outputs -and $outputs.midi) { [string]$outputs.midi } else { First-ArtifactPath $outputDir "*.mid" }
$generatedAudio = if ($outputs -and $outputs.audio) { [string]$outputs.audio } else { First-ArtifactPath $outputDir "*.wav" }
$renderReport = if ($outputs -and $outputs.render_report) { [string]$outputs.render_report } else { First-ArtifactPath $outputDir "*_render_report.json" }
$renderError = if ($outputs -and $outputs.render_error) { [string]$outputs.render_error } else { First-ArtifactPath $outputDir "*_render_error.txt" }

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
$analysisPresent = $null -ne $audioAnalysis
$analysisPassed = if ($analysisPresent -and $null -ne $audioAnalysis.passed) { [bool]$audioAnalysis.passed } else { $null }
$analysisScore = if ($analysisPresent -and $null -ne $audioAnalysis.genre_match_score) { [double]$audioAnalysis.genre_match_score } else { $null }
$analysisFailureReason = if ($analysisPassed -eq $false) { Get-FirstAnalysisIssueMessage $audioAnalysis } else { $null }
if (($analysisPassed -eq $false) -and -not $analysisFailureReason -and $audioAnalysis.analysis_error) {
    $analysisFailureReason = [string]$audioAnalysis.analysis_error
}

$analysisExplicitFailure = $false
if ($analysisPresent -and $null -ne $analysisPassed -and ($analysisPassed -eq $false)) {
    $analysisExplicitFailure = $true
}

$hasMetadataAudio = $false
if ($outputs -and $null -ne $outputs.audio -and -not [string]::IsNullOrWhiteSpace([string]$outputs.audio)) {
    $hasMetadataAudio = $true
}

$strictAudioFailed = $false
if ($StrictAudio.IsPresent) {
    $strictAudioFailed = ($childExitCode -ne 0) -or (-not $metadata) -or (-not $hasMetadataAudio) -or ($renderSuccess -eq $false) -or $analysisExplicitFailure
}

$fluidsynthIsolationFailed = $false
if ($FluidSynthIsolation.IsPresent) {
    $fluidsynthIsolationFailed = ($rendererPath -ne "fluidsynth") -or ($fluidsynthAttempted -ne $true) -or ($fluidsynthSuccess -ne $true) -or (-not [string]::IsNullOrWhiteSpace($fluidsynthSkipReason)) -or ([string]::IsNullOrWhiteSpace($soundfontPath))
}

$summary = [ordered]@{
    prompt = $Prompt
    pid = $pidValue
    exit_code = $childExitCode
    timed_out = $timedOut
    strict_audio = [bool]$StrictAudio.IsPresent
    strict_audio_failed = $strictAudioFailed
    fluidsynth_isolation = [bool]$FluidSynthIsolation.IsPresent
    fluidsynth_isolation_failed = $fluidsynthIsolationFailed
    stdout_path = $stdoutPath
    stderr_path = $stderrPath
    output_dir = $outputDir
    generated_midi = $generatedMidi
    generated_audio = $generatedAudio
    metadata_path = $metadataPath
    render_report = $renderReport
    render_error = $renderError
    parsed_status = [ordered]@{
        genre = if ($parsed -and $parsed.genre) { [string]$parsed.genre } else { $null }
        bpm = if ($parsed -and $parsed.bpm) { $parsed.bpm } else { $null }
        key = if ($parsed -and $parsed.key) { [string]$parsed.key } else { $null }
        scale = if ($parsed -and $parsed.scale) { [string]$parsed.scale } else { $null }
        instruments = if ($parsed -and $parsed.instruments) { @($parsed.instruments) } else { @() }
        drum_elements = if ($parsed -and $parsed.drum_elements) { @($parsed.drum_elements) } else { @() }
    }
    audio_status = [ordered]@{
        metadata_has_audio = $hasMetadataAudio
        render_success = $renderSuccess
        failure_reason = if ($renderFailure -and $renderFailure.reason) { [string]$renderFailure.reason } else { $null }
        failure_stage = if ($renderFailure -and $renderFailure.stage) { [string]$renderFailure.stage } elseif ($renderStatus -and $renderStatus.current_stage) { [string]$renderStatus.current_stage } else { $null }
        exception_type = if ($renderFailure -and $renderFailure.exception_type) { [string]$renderFailure.exception_type } else { $null }
        analysis_present = $analysisPresent
        analysis_passed = $analysisPassed
        analysis_score = $analysisScore
        analysis_failure_reason = $analysisFailureReason
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
    command = [ordered]@{
        python = $pythonPath
        main = $mainPath
        duration_bars = $DurationBars
        seed = $Seed
        require_audio = [bool]$StrictAudio.IsPresent
        fluidsynth_isolation = [bool]$FluidSynthIsolation.IsPresent
        soundfont = if (-not [string]::IsNullOrWhiteSpace($SoundFont)) { (Resolve-SmokePath $SoundFont) } else { $null }
    }
    generated_at = [DateTime]::UtcNow.ToString("yyyy-MM-ddTHH:mm:ssZ")
}

$summary | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $summaryPath -Encoding UTF8

if ($StrictAudio.IsPresent -and $strictAudioFailed) {
    if ($childExitCode -ne 0) {
        exit $childExitCode
    }
    if ($FluidSynthIsolation.IsPresent -and $fluidsynthIsolationFailed) {
        exit 3
    }
    exit 2
}

if ($FluidSynthIsolation.IsPresent -and $fluidsynthIsolationFailed) {
    if ($childExitCode -ne 0) {
        exit $childExitCode
    }
    exit 3
}

exit $childExitCode
