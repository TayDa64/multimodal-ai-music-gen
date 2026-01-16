#!/usr/bin/env python3
"""
Agent Orchestrator - Python version for cross-platform support.

Spawns Builder/Verifier subagents and tracks state in agent_state.json.
Uses GitHub Copilot Pro+ subscription via GitHub Models API (no separate API key needed).

Usage:
    python orchestrate.py --task "Update READALL.md" --agent builder --files "READALL.md"
    python orchestrate.py --task "Verify changes" --agent verifier --task-id task-002
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')


def utcnow() -> datetime:
    """Get current UTC time (timezone-aware)."""
    return datetime.now(timezone.utc)

# Try to import OpenAI
try:
    import openai
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False

# =============================================================================
# CONFIGURATION
# =============================================================================

REPO_ROOT = Path(__file__).parent.parent.parent
STATE_FILE = REPO_ROOT / ".github" / "agent_state.json"
AGENTS_DIR = REPO_ROOT / ".github" / "agents"


# =============================================================================
# STATE MANAGEMENT
# =============================================================================

def get_state() -> dict:
    """Load agent state from JSON file."""
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    return {
        "schemaVersion": 1,
        "updatedAt": utcnow().isoformat() + "Z",
        "queue": [],
        "in_progress": [],
        "done": [],
    }


def save_state(state: dict) -> None:
    """Save agent state to JSON file."""
    state["updatedAt"] = utcnow().isoformat() + "Z"
    STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")


def add_task_to_queue(state: dict, task_id: str, agent: str, title: str, notes: str) -> dict:
    """Add a new task to the queue."""
    now = utcnow().isoformat() + "Z"
    task = {
        "id": task_id,
        "agent": f"recursive-{agent}",
        "title": title[:50],
        "status": "queue",
        "created_at": now,
        "updated_at": now,
        "notes": notes,
        "handoff_to": [],
        "artifacts": [],
    }
    state["queue"].append(task)
    return state


def move_to_in_progress(state: dict, task_id: str) -> dict:
    """Move a task from queue to in_progress."""
    for i, task in enumerate(state["queue"]):
        if task["id"] == task_id:
            task = state["queue"].pop(i)
            task["status"] = "in_progress"
            task["started_at"] = utcnow().isoformat() + "Z"
            task["updated_at"] = utcnow().isoformat() + "Z"
            state["in_progress"].append(task)
            break
    return state


def move_to_done(state: dict, task_id: str, notes: str = "", artifacts: list = None) -> dict:
    """Move a task from in_progress to done."""
    for i, task in enumerate(state["in_progress"]):
        if task["id"] == task_id:
            task = state["in_progress"].pop(i)
            task["status"] = "done"
            task["completed_at"] = utcnow().isoformat() + "Z"
            task["updated_at"] = utcnow().isoformat() + "Z"
            if notes:
                task["notes"] = notes
            if artifacts:
                task["artifacts"] = artifacts
            state["done"].append(task)
            break
    return state


# =============================================================================
# AGENT INSTRUCTIONS
# =============================================================================

def get_agent_instructions(agent: str) -> str:
    """Load agent instructions from markdown file."""
    agent_file = AGENTS_DIR / f"recursive-{agent}.agent.md"
    if not agent_file.exists():
        print(f"Warning: Agent file not found: {agent_file}", file=sys.stderr)
        return ""
    
    content = agent_file.read_text(encoding="utf-8")
    
    # Extract body after YAML frontmatter
    parts = content.split("---", 2)
    if len(parts) >= 3:
        return parts[2].strip()
    return content


def build_prompt(agent: str, task: str, files: str, task_id: str) -> str:
    """Build the full prompt for the agent."""
    instructions = get_agent_instructions(agent)
    file_list = "\n".join(f"- {f.strip()}" for f in files.split(",")) if files else "(no specific files)"
    
    return f"""# Agent: recursive-{agent}
# Task ID: {task_id}
# Scoped Files:
{file_list}

## Instructions (from agent spec):
{instructions}

## Your Task:
{task}

## Requirements:
1. Stay scoped to the files listed above.
2. Provide minimal, localized changes.
3. Return a structured response with:
   - CHANGES: List of files modified and what changed
   - PROOFS: Command outputs or verification results
   - STATUS: success/blocked/needs_guidance
   - NOTES: Any uncertainties or handoff requests
"""


# =============================================================================
# LLM INVOCATION
# =============================================================================

def invoke_openai(prompt: str) -> Optional[str]:
    """Call OpenAI API."""
    if not HAS_OPENAI:
        return None
    
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return None
    
    try:
        client = openai.OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a code assistant executing agent tasks. Follow instructions precisely."},
                {"role": "user", "content": prompt},
            ],
            max_tokens=4096,
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"OpenAI API error: {e}", file=sys.stderr)
        return None


def invoke_azure_openai(prompt: str) -> Optional[str]:
    """Call Azure OpenAI API."""
    endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT")
    api_key = os.environ.get("AZURE_OPENAI_KEY")
    deployment = os.environ.get("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")
    
    if not endpoint or not api_key:
        return None
    
    try:
        import requests
        url = f"{endpoint}/openai/deployments/{deployment}/chat/completions?api-version=2024-02-15-preview"
        headers = {"api-key": api_key, "Content-Type": "application/json"}
        body = {
            "messages": [
                {"role": "system", "content": "You are a code assistant executing agent tasks. Follow instructions precisely."},
                {"role": "user", "content": prompt},
            ],
            "max_tokens": 4096,
        }
        response = requests.post(url, headers=headers, json=body)
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"Azure OpenAI error: {e}", file=sys.stderr)
        return None


def invoke_gh_copilot(prompt: str) -> Optional[str]:
    """Call GitHub Copilot CLI."""
    try:
        result = subprocess.run(
            ["gh", "copilot", "explain", prompt[:2000]],  # Truncate for CLI
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode == 0:
            return result.stdout
    except Exception as e:
        print(f"gh copilot error: {e}", file=sys.stderr)
    return None


def invoke_github_models(prompt: str) -> Optional[str]:
    """
    Call GitHub Models API using your Copilot Pro+ subscription.
    Uses GITHUB_TOKEN from `gh auth token` - no separate API key needed!
    """
    # Get token from gh CLI or environment
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        try:
            result = subprocess.run(
                ["gh", "auth", "token"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                token = result.stdout.strip()
        except Exception:
            pass
    
    if not token:
        print("No GitHub token found. Run 'gh auth login' first.", file=sys.stderr)
        return None
    
    try:
        import requests
        
        # GitHub Models API endpoint (available with Copilot Pro+)
        url = "https://models.inference.ai.azure.com/chat/completions"
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        
        body = {
            "model": "gpt-4o",  # Available models: gpt-4o, gpt-4o-mini, o1, o1-mini
            "messages": [
                {"role": "system", "content": "You are a code assistant executing agent tasks. Follow instructions precisely."},
                {"role": "user", "content": prompt},
            ],
            "max_tokens": 4096,
        }
        
        response = requests.post(url, headers=headers, json=body, timeout=120)
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"GitHub Models API error: {e}", file=sys.stderr)
        return None


def invoke_agent(prompt: str, agent: str) -> str:
    """Try all available LLM backends."""
    print(f"\n=== Invoking {agent} agent ===")
    print(f"Prompt length: {len(prompt)} chars")
    
    # Try GitHub Models first (uses Copilot Pro+ subscription, no extra API key)
    print("Trying GitHub Models API (Copilot Pro+)...")
    result = invoke_github_models(prompt)
    if result:
        return result
    
    # Fallback to gh copilot CLI
    print("Trying gh copilot CLI...")
    result = invoke_gh_copilot(prompt)
    if result:
        return result
    
    # Try OpenAI if configured
    result = invoke_openai(prompt)
    if result:
        return result
    
    # Try Azure OpenAI if configured
    result = invoke_azure_openai(prompt)
    if result:
        return result
    
    # Fallback
    print("\nNo LLM API available.")
    print("Options:")
    print("  1. Run 'gh auth login' to use your Copilot Pro+ subscription")
    print("  2. Set OPENAI_API_KEY for OpenAI")
    print("  3. Set AZURE_OPENAI_* for Azure")
    print("\n=== PROMPT FOR MANUAL EXECUTION ===")
    print(prompt)
    print("=== END PROMPT ===")
    return "MANUAL_EXECUTION_REQUIRED"


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description="Agent Orchestrator")
    parser.add_argument("--task", required=True, help="Task description")
    parser.add_argument("--agent", required=True, choices=["builder", "verifier", "supervisor"])
    parser.add_argument("--task-id", default=None, help="Task ID (auto-generated if not provided)")
    parser.add_argument("--files", default="", help="Comma-separated list of files to scope")
    parser.add_argument("--dry-run", action="store_true", help="Print prompt without executing")
    
    args = parser.parse_args()
    
    task_id = args.task_id or f"task-{utcnow().strftime('%Y%m%d%H%M%S')}"
    
    print("=" * 44)
    print("     Agent Orchestrator v1.0 (Python)     ")
    print("=" * 44)
    print(f"\nTask:    {args.task}")
    print(f"Agent:   {args.agent}")
    print(f"TaskId:  {task_id}")
    print(f"Files:   {args.files or '(none)'}")
    
    # Load state
    state = get_state()
    
    # Check if task exists
    all_tasks = state["queue"] + state["in_progress"] + state["done"]
    existing = [t for t in all_tasks if t["id"] == task_id]
    
    if not existing:
        print("\nAdding task to queue...")
        state = add_task_to_queue(state, task_id, args.agent, args.task, "Created by orchestrator")
        save_state(state)
    
    # Move to in_progress
    print("Moving task to in_progress...")
    state = move_to_in_progress(state, task_id)
    save_state(state)
    
    # Build prompt
    prompt = build_prompt(args.agent, args.task, args.files, task_id)
    
    if args.dry_run:
        print("\n=== DRY RUN - PROMPT ===")
        print(prompt)
        print("=== END DRY RUN ===")
        return
    
    # Invoke agent
    result = invoke_agent(prompt, args.agent)
    
    if result != "MANUAL_EXECUTION_REQUIRED":
        print("\n=== AGENT RESPONSE ===")
        print(result)
        print("=== END RESPONSE ===")
        
        # Move to done
        state = get_state()
        state = move_to_done(state, task_id, f"Completed by {args.agent} agent")
        save_state(state)
        
        print(f"\nTask {task_id} completed.")
    else:
        print("\nTask requires manual execution. State left as in_progress.")
    
    # Summary
    state = get_state()
    print("\n=== STATE SUMMARY ===")
    print(f"Queue:       {len(state['queue'])} tasks")
    print(f"In Progress: {len(state['in_progress'])} tasks")
    print(f"Done:        {len(state['done'])} tasks")


if __name__ == "__main__":
    main()
