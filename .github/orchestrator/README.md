# Agent Orchestrator

Shell-based orchestration for autonomous agent workflows. Enables true subagent spawning using your **GitHub Copilot Pro+ subscription** - no separate API key needed!

## Why This Exists

VS Code's agent `handoffs` are **user-clickable buttons**, not autonomous execution. When Supervisor says "handoff to Builder," it's just outputting text. This orchestrator solves that by:

1. Managing task state in `agent_state.json`
2. Calling GitHub Models API directly (uses your Copilot Pro+ subscription)
3. Loading agent instructions from `.github/agents/*.agent.md`
4. Tracking progress and aggregating results

## Setup

### Using GitHub Copilot Pro+ (Recommended - No API Key Needed!)
```bash
# Just make sure you're logged in to GitHub CLI
gh auth login
gh auth status  # Should show ✓ Logged in
```

That's it! The orchestrator will automatically use your Copilot subscription.

### Alternative: OpenAI API
```bash
export OPENAI_API_KEY="sk-..."
```

### Alternative: Azure OpenAI
```bash
export AZURE_OPENAI_ENDPOINT="https://your-resource.openai.azure.com"
export AZURE_OPENAI_KEY="your-key"
export AZURE_OPENAI_DEPLOYMENT="gpt-4o"
```

## Usage

### PowerShell
```powershell
# Basic usage
.\.github\orchestrator\orchestrate.ps1 -Task "Update READALL.md" -Agent builder

# With file scope
.\.github\orchestrator\orchestrate.ps1 -Task "Add motif_engine docs" -Agent builder -Files "READALL.md,multimodal_gen/motif_engine.py"

# Dry run (print prompt only)
.\.github\orchestrator\orchestrate.ps1 -Task "Verify links" -Agent verifier -DryRun
```

### Python
```bash
# Basic usage
python .github/orchestrator/orchestrate.py --task "Update READALL.md" --agent builder

# With file scope
python .github/orchestrator/orchestrate.py --task "Add motif_engine docs" --agent builder --files "READALL.md,multimodal_gen/motif_engine.py"

# Dry run
python .github/orchestrator/orchestrate.py --task "Verify links" --agent verifier --dry-run
```

## Integration with Supervisor

The Supervisor agent can invoke this orchestrator via the `execute` tool:

```markdown
# In Supervisor response:
I will now delegate to Builder via the orchestrator.

```bash
python .github/orchestrator/orchestrate.py --task "Refresh READALL.md with new modules" --agent builder --files "READALL.md"
```
```

## State File

The orchestrator reads/writes `.github/agent_state.json`:

```json
{
  "schemaVersion": 1,
  "updatedAt": "2026-01-16T19:00:00Z",
  "queue": [],
  "in_progress": [
    {
      "id": "task-001",
      "agent": "recursive-builder",
      "title": "Update READALL.md",
      "status": "in_progress",
      "started_at": "2026-01-16T19:00:00Z"
    }
  ],
  "done": []
}
```

## Architecture

```
┌─────────────────┐
│   Supervisor    │  ← You invoke @recursive-supervisor
│   (Agent)       │
└────────┬────────┘
         │ execute: orchestrate.py --task "..." --agent builder
         ▼
┌─────────────────┐
│  Orchestrator   │  ← PowerShell or Python script
│   .ps1 / .py    │
└────────┬────────┘
         │ 1. Load agent instructions from .github/agents/
         │ 2. Update state: queue → in_progress
         │ 3. Call LLM API with full prompt
         │ 4. Parse response, apply edits
         │ 5. Update state: in_progress → done
         ▼
┌─────────────────┐
│ agent_state.json│  ← Shared state for tracking
└─────────────────┘
```
