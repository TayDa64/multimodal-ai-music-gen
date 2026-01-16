# Recursive Long-Context Skill
## Overview
This skill provides reusable Recursive Long-Context (RLC) logic for handling massive inputs and codebases. Load it into agents for modular enhancement of long-context reasoning capabilities.
**Use Cases**: Large file analysis, codebase-wide refactoring, multi-document synthesis, complex reasoning over >100K tokens.
---
## Core Functions
### 1. Probe and Filter
Efficiently peek into large contexts without full loading.
- Use code/tools to sample: `print(context[:1000])` in terminal REPL
- Filter via regex/keywords without full load
- Returns: sampled content, metadata (size, matches)
### 2. Recursive Decomposition
Break massive inputs into manageable chunks for sub-agent processing.
- **Strategies**: Uniform chunking, keyword-based, semantic boundaries
- **Invocation**: Sub-agents recursively on snippets
- **Returns**: Per-chunk results ready for aggregation
### 3. Aggregation Patterns
Stitch sub-agent outputs back together coherently.
- Use variables for state: lists/dicts in terminal scripts
- Merge results with conflict resolution
- Returns: unified output (code, report, or structured data)
### 4. Verification Loops
Validate intermediate results with a verification sub-agent.
- Pattern: "@verifier: Run linter on this diff"
- Catches errors before final output
- Returns: pass/fail + feedback
---
## Implementation Patterns
### Modularity & Robustness
Export functions as reusable modules:
```python
# helpers.py - Export for use in sub-agents
def fetch_url(url):
    return subprocess.check_output(['curl', url])
def track_pid(cmd):
    pid = subprocess.Popen(cmd).pid
    return pid
```
### Phased Workflow
Structure large tasks into verifiable phases:
1. **Phase 1 (Lint)**: ESLint / pylint
2. **Phase 2 (Build)**: npm/yarn / python setup
3. **Phase 3 (Test)**: Playwright MCP / pytest
### Stateful & Concurrent Processing
For parallel sub-agents:
```python
from multiprocessing import Queue
queue = Queue()
# Distribute chunks to workers; persist state in files
```
### Systematic Logging & Proofs
- Always log steps with timestamps
- Provide external proof: "Fetched from [URL]: [snippet]"
- Link to source artifacts (commits, URLs, file locations)
---
## RLC-Specific Strategies
### Environment Interaction
Treat workspace as interactive REPL:
- Load files as strings: `with open(file) as f: content = f.read()`
- Use terminal tools for live inspection
- Cache results in variables
### Recursion Patterns
- **Info-Dense** (e.g., semantic analysis): Sub-call per line/pair
- **Sparse** (e.g., search): BM25-like filtering + sub-agents on matches
- **Hierarchical**: Tree-structured recursion with aggregation at each level
### Cost & Efficiency
- Warn if >10 sub-calls required; consider consolidation
- Prefer deterministic code over LM for simple operations
- Use sampling/filtering before full decomposition
---
## Integration Guide
### Loading into Agents
Reference this skill in agent prompts:
```
You have access to the Recursive Long-Context Skill.
For tasks with >50K tokens, use Probe→Decompose→Aggregate pattern.
```
### Example Workflows
**OOLONG-style (Line-by-line analysis)**:
```
1. Chunk by newline
2. Sub-agent processes each chunk (e.g., count patterns)
3. Aggregate counts
```
**BrowseComp-style (Multi-hop search)**:
```
1. Search docs for keywords
2. Spawn concurrent sub-agents per result
3. Merge findings with deduplication
```
---
## Checklist for Use
- [ ] Context size exceeds 50K tokens?
- [ ] Complex recursion needed? (Use Probe→Decompose→Aggregate)
- [ ] Modularity required? (Export helpers as .py files)
- [ ] Concurrent processing? (Use Queue + state persistence)
- [ ] Verification needed? (Add @verifier step)
- [ ] Cost concerns? (Log sub-call count; aim for <10)
---
## Extension Points
- **Domain-specific sub-skills**: Create variants for code/docs/data
- **Tool integrations**: Connect to linters, build systems, test frameworks
- **Caching layers**: Add persistent storage for large intermediate results
This skill ensures scalable, proof-based reasoning over long contexts—extend via sub-skills for specialized domains.
