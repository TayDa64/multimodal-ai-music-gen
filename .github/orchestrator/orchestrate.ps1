<#
.SYNOPSIS
    Agent Orchestrator - Spawns Builder/Verifier subagents and tracks state.

.DESCRIPTION
    This script enables true autonomous agent orchestration by:
    1. Managing task state in agent_state.json
    2. Calling the GitHub Copilot API (via gh copilot) or OpenAI API
    3. Tracking PIDs for long-running processes
    4. Aggregating results for the Supervisor

.PARAMETER Task
    The task description to execute.

.PARAMETER Agent
    Which agent to invoke: "builder" or "verifier"

.PARAMETER TaskId
    The task ID to track in agent_state.json

.PARAMETER Files
    Comma-separated list of files to scope the agent to.

.PARAMETER DryRun
    If set, prints the prompt without executing.

.EXAMPLE
    .\orchestrate.ps1 -Task "Update READALL.md" -Agent builder -TaskId "task-002" -Files "READALL.md,multimodal_gen/motif_engine.py"
#>

param(
    [Parameter(Mandatory=$true)]
    [string]$Task,
    
    [Parameter(Mandatory=$true)]
    [ValidateSet("builder", "verifier", "supervisor")]
    [string]$Agent,
    
    [Parameter(Mandatory=$false)]
    [string]$TaskId = "task-$(Get-Date -Format 'yyyyMMddHHmmss')",
    
    [Parameter(Mandatory=$false)]
    [string]$Files = "",
    
    [Parameter(Mandatory=$false)]
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$StateFile = Join-Path $RepoRoot ".github\agent_state.json"
$AgentsDir = Join-Path $RepoRoot ".github\agents"

# =============================================================================
# STATE MANAGEMENT
# =============================================================================

function Get-AgentState {
    if (Test-Path $StateFile) {
        return Get-Content $StateFile -Raw | ConvertFrom-Json
    }
    return @{
        schemaVersion = 1
        updatedAt = (Get-Date -Format "o")
        queue = @()
        in_progress = @()
        done = @()
    }
}

function Save-AgentState {
    param($State)
    $State.updatedAt = (Get-Date -Format "o")
    $State | ConvertTo-Json -Depth 10 | Set-Content $StateFile -Encoding UTF8
}

function Add-TaskToQueue {
    param($State, $TaskId, $Agent, $Title, $Notes)
    
    $task = @{
        id = $TaskId
        agent = "recursive-$Agent"
        title = $Title
        status = "queue"
        created_at = (Get-Date -Format "o")
        updated_at = (Get-Date -Format "o")
        notes = $Notes
        handoff_to = @()
        artifacts = @()
    }
    
    $State.queue += $task
    return $State
}

function Move-TaskToInProgress {
    param($State, $TaskId)
    
    $task = $State.queue | Where-Object { $_.id -eq $TaskId }
    if ($task) {
        $State.queue = @($State.queue | Where-Object { $_.id -ne $TaskId })
        $task.status = "in_progress"
        $task.started_at = (Get-Date -Format "o")
        $task.updated_at = (Get-Date -Format "o")
        $State.in_progress += $task
    }
    return $State
}

function Move-TaskToDone {
    param($State, $TaskId, $Notes, $Artifacts)
    
    $task = $State.in_progress | Where-Object { $_.id -eq $TaskId }
    if ($task) {
        $State.in_progress = @($State.in_progress | Where-Object { $_.id -ne $TaskId })
        $task.status = "done"
        $task.completed_at = (Get-Date -Format "o")
        $task.updated_at = (Get-Date -Format "o")
        if ($Notes) { $task.notes = $Notes }
        if ($Artifacts) { $task.artifacts = $Artifacts }
        $State.done += $task
    }
    return $State
}

# =============================================================================
# AGENT INSTRUCTIONS LOADER
# =============================================================================

function Get-AgentInstructions {
    param($AgentName)
    
    $agentFile = Join-Path $AgentsDir "recursive-$AgentName.agent.md"
    if (-not (Test-Path $agentFile)) {
        Write-Warning "Agent file not found: $agentFile"
        return ""
    }
    
    $content = Get-Content $agentFile -Raw
    
    # Extract markdown body (after YAML frontmatter)
    if ($content -match '(?s)^---.*?---\s*(.*)$') {
        return $Matches[1].Trim()
    }
    return $content
}

# =============================================================================
# PROMPT BUILDER
# =============================================================================

function Build-AgentPrompt {
    param($Agent, $Task, $Files, $TaskId)
    
    $instructions = Get-AgentInstructions -AgentName $Agent
    $fileList = if ($Files) { $Files -split ',' | ForEach-Object { "- $_" } | Out-String } else { "(no specific files)" }
    
    $prompt = @"
# Agent: recursive-$Agent
# Task ID: $TaskId
# Scoped Files:
$fileList

## Instructions (from agent spec):
$instructions

## Your Task:
$Task

## Requirements:
1. Stay scoped to the files listed above.
2. Provide minimal, localized changes.
3. Return a structured response with:
   - CHANGES: List of files modified and what changed
   - PROOFS: Command outputs or verification results
   - STATUS: success/blocked/needs_guidance
   - NOTES: Any uncertainties or handoff requests
"@
    
    return $prompt
}

# =============================================================================
# EXECUTION
# =============================================================================

function Invoke-Agent {
    param($Prompt, $Agent)
    
    Write-Host "=== Invoking $Agent agent ===" -ForegroundColor Cyan
    Write-Host "Prompt length: $($Prompt.Length) chars" -ForegroundColor Gray
    
    # Option 1: Use GitHub Copilot CLI (if available)
    if (Get-Command "gh" -ErrorAction SilentlyContinue) {
        $tempFile = [System.IO.Path]::GetTempFileName()
        $Prompt | Set-Content $tempFile -Encoding UTF8
        
        try {
            # gh copilot suggest expects interactive mode, so we use explain as fallback
            $result = gh copilot explain $Prompt 2>&1
            if ($LASTEXITCODE -eq 0) {
                Remove-Item $tempFile -ErrorAction SilentlyContinue
                return $result
            }
        } catch {
            Write-Warning "gh copilot failed: $_"
        }
        Remove-Item $tempFile -ErrorAction SilentlyContinue
    }
    
    # Option 2: Direct OpenAI API call (requires OPENAI_API_KEY)
    if ($env:OPENAI_API_KEY) {
        $body = @{
            model = "gpt-4o"
            messages = @(
                @{ role = "system"; content = "You are a code assistant executing agent tasks. Follow instructions precisely." }
                @{ role = "user"; content = $Prompt }
            )
            max_tokens = 4096
        } | ConvertTo-Json -Depth 10
        
        try {
            $response = Invoke-RestMethod -Uri "https://api.openai.com/v1/chat/completions" `
                -Method Post `
                -Headers @{ "Authorization" = "Bearer $($env:OPENAI_API_KEY)"; "Content-Type" = "application/json" } `
                -Body $body
            
            return $response.choices[0].message.content
        } catch {
            Write-Warning "OpenAI API failed: $_"
        }
    }
    
    # Option 3: Azure OpenAI (requires AZURE_OPENAI_* vars)
    if ($env:AZURE_OPENAI_ENDPOINT -and $env:AZURE_OPENAI_KEY) {
        $body = @{
            messages = @(
                @{ role = "system"; content = "You are a code assistant executing agent tasks. Follow instructions precisely." }
                @{ role = "user"; content = $Prompt }
            )
            max_tokens = 4096
        } | ConvertTo-Json -Depth 10
        
        try {
            $response = Invoke-RestMethod -Uri "$($env:AZURE_OPENAI_ENDPOINT)/openai/deployments/$($env:AZURE_OPENAI_DEPLOYMENT)/chat/completions?api-version=2024-02-15-preview" `
                -Method Post `
                -Headers @{ "api-key" = $env:AZURE_OPENAI_KEY; "Content-Type" = "application/json" } `
                -Body $body
            
            return $response.choices[0].message.content
        } catch {
            Write-Warning "Azure OpenAI failed: $_"
        }
    }
    
    # Fallback: Return prompt for manual execution
    Write-Warning "No LLM API available. Set OPENAI_API_KEY or AZURE_OPENAI_* environment variables."
    Write-Host "`n=== PROMPT FOR MANUAL EXECUTION ===" -ForegroundColor Yellow
    Write-Host $Prompt
    Write-Host "=== END PROMPT ===" -ForegroundColor Yellow
    
    return "MANUAL_EXECUTION_REQUIRED"
}

# =============================================================================
# MAIN
# =============================================================================

Write-Host "╔════════════════════════════════════════╗" -ForegroundColor Green
Write-Host "║     Agent Orchestrator v1.0            ║" -ForegroundColor Green
Write-Host "╚════════════════════════════════════════╝" -ForegroundColor Green
Write-Host ""
Write-Host "Task:    $Task" -ForegroundColor White
Write-Host "Agent:   $Agent" -ForegroundColor White
Write-Host "TaskId:  $TaskId" -ForegroundColor White
Write-Host "Files:   $Files" -ForegroundColor White
Write-Host ""

# Load state
$state = Get-AgentState

# Add task to queue if new
$existingTask = ($state.queue + $state.in_progress + $state.done) | Where-Object { $_.id -eq $TaskId }
if (-not $existingTask) {
    Write-Host "Adding task to queue..." -ForegroundColor Gray
    $state = Add-TaskToQueue -State $state -TaskId $TaskId -Agent $Agent -Title $Task.Substring(0, [Math]::Min(50, $Task.Length)) -Notes "Created by orchestrator"
    Save-AgentState -State $state
}

# Move to in_progress
Write-Host "Moving task to in_progress..." -ForegroundColor Gray
$state = Move-TaskToInProgress -State $state -TaskId $TaskId
Save-AgentState -State $state

# Build prompt
$prompt = Build-AgentPrompt -Agent $Agent -Task $Task -Files $Files -TaskId $TaskId

if ($DryRun) {
    Write-Host "`n=== DRY RUN - PROMPT ===" -ForegroundColor Yellow
    Write-Host $prompt
    Write-Host "=== END DRY RUN ===" -ForegroundColor Yellow
    exit 0
}

# Invoke agent
$result = Invoke-Agent -Prompt $prompt -Agent $Agent

# Parse result and update state
if ($result -ne "MANUAL_EXECUTION_REQUIRED") {
    Write-Host "`n=== AGENT RESPONSE ===" -ForegroundColor Green
    Write-Host $result
    Write-Host "=== END RESPONSE ===" -ForegroundColor Green
    
    # Move to done
    $state = Get-AgentState  # Reload in case of concurrent updates
    $state = Move-TaskToDone -State $state -TaskId $TaskId -Notes "Completed by $Agent agent" -Artifacts @()
    Save-AgentState -State $state
    
    Write-Host "`nTask $TaskId completed." -ForegroundColor Green
} else {
    Write-Host "`nTask requires manual execution. State left as in_progress." -ForegroundColor Yellow
}

# Output for Supervisor aggregation
Write-Host "`n=== STATE SUMMARY ===" -ForegroundColor Cyan
Write-Host "Queue:       $($state.queue.Count) tasks"
Write-Host "In Progress: $($state.in_progress.Count) tasks"
Write-Host "Done:        $($state.done.Count) tasks"
