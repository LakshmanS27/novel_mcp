# Workflow Analysis

This document describes what the project currently does, how the MCP server and client interact, what each major tool is responsible for, and where the current design is strong or weak.

It is intentionally based on the code as it exists now, not on an idealized future architecture.

## 1. Current Project Shape

The project is split into two sides:

- `mcp_server/`: the FastAPI-based MCP server exposing tools
- `mcp_client/`: the `mcp-use` client that connects an LLM to those tools

The current flow is:

1. The FastAPI app starts
2. `fastapi_mcp` mounts the FastAPI routes as MCP tools
3. The `mcp-use` client connects to `http://localhost:8081/mcp`
4. The client LLM decides which tool to call
5. The MCP server executes the tool and returns JSON
6. The LLM interprets the result and continues

## 2. High-Level Runtime Flow

### Server startup

The server entrypoint is:

- `mcp_server/server/main.py`

At startup it:

- loads configuration from `.env` through `pydantic-settings`
- configures logging
- initializes the SQLite feedback database
- creates a FastAPI app
- registers routes
- mounts MCP using `FastApiMCP(app, ...)`

So the MCP server is not implemented manually. The FastAPI routes are the source of truth, and `fastapi_mcp` exposes them as MCP tools.

### Client startup

The client entrypoint is:

- `mcp_client/chat_client.py`

At startup it:

- loads `.env`
- configures an OpenAI-compatible LLM through `ChatOpenAI`
- creates an `MCPClient` for the server URL
- wraps it with `MCPAgent`
- enters an interactive chat loop

This means the client is the orchestration layer. The MCP server is the execution/tool layer.

## 3. What the MCP Server Currently Does

The server is a metadata-first DLP and risk-analysis tool service.

It currently supports four major categories:

- filesystem inspection
- intelligence and risk scoring
- scanning
- feedback learning

### 3.1 Filesystem inspection

These tools inspect structure and metadata:

- `/list_directory`
- `/get_file_metadata`
- `/get_directory_structure`
- `/get_disk_usage`

These are used to understand:

- what exists in a directory
- file and directory metadata
- directory tree structure
- size information

The implementation relies on Linux-native commands and APIs:

- `tree -J`
- `stat`
- `du`
- `os.scandir`

Important constraint:

- these tools do not read file contents

### 3.2 Intelligence and risk scoring

These tools operate on metadata and graph context:

- `/infer_directory_purpose`
- `/compute_risk_score`
- `/explain_risk`
- `/run_full_analysis`

The server builds a graph of the filesystem and calculates risk based on:

- filename keywords
- metadata signals
- graph centrality
- semantic directory inference
- feedback-driven weights

Important note:

- the current implementation still includes server-side LLM calls inside `semantic_inference.py`
- this means the server is not purely deterministic today

### 3.3 Scanning

These tools actually inspect content:

- `/identify_scan_candidates`
- `/scan_candidate_files`
- `/scan_file_sensitive_data`
- `/scan_directory_sensitive_data`
- `/validate_compliance`

The current scanning layer is split into two parts:

- candidate selection without content reads
- content scanning on selected targets

Candidate selection uses:

- extension-based exclusion of low-value files
- prioritization of likely text-bearing files
- filename and directory keyword scoring
- file size and permission signals

The scanner performs pattern matching for:

- emails
- long number sequences classified as `pan`
- API key-style strings
- AWS keys
- credential and secret-related keywords

The scanner reads files in chunks using streaming I/O and does not load the full file into memory at once.

Important distinctions:

- `/identify_scan_candidates` ranks likely sensitive files without reading file contents
- `/scan_candidate_files` scans only a chosen list of files
- `/scan_file_sensitive_data` is for one file only
- `/scan_directory_sensitive_data` recursively scans every file under a directory

This distinction was added because earlier the file scan tool could be called on a directory and return an empty result, which created false confidence.

### 3.4 Feedback learning

These tools persist analyst feedback:

- `/submit_feedback`
- `/update_risk_model`

Feedback is stored in SQLite as:

- path
- label: `TP` or `FP`
- notes
- timestamp

The model update step adjusts scoring weights based on the history of true positives and false positives.

## 4. Full Pipeline Workflow

The end-to-end selective pipeline is implemented in:

- `mcp_server/core/pipeline.py`

The workflow is:

1. Read directory structure using `tree`
2. Build a graph of files and directories
3. Collect metadata using `stat`
4. Infer semantic purpose from names and structure
5. Compute risk scores for file nodes
6. Rank files by risk
7. Select only the top 1-5%
8. Scan only those selected files
9. Validate compliance and produce explanations

This is the most efficient workflow currently present in the project.

It is not a full brute-force repo scan. It is a selective scan based on a prior ranking stage.

## 5. Current Tool Behavior by User Intent

### Case A: User asks to inspect structure

Typical tools:

- `/list_directory`
- `/get_directory_structure`
- `/get_file_metadata`

Behavior:

- metadata only
- no content scanning
- fast and cheap

### Case B: User asks for likely risky files or likely sensitive files

Typical tools:

- `/identify_scan_candidates`
- `/scan_candidate_files`
- `/compute_risk_score`
- `/run_full_analysis`
- `/explain_risk`

Behavior:

- deterministic pre-scan candidate filtering
- metadata-first analysis
- graph-aware ranking
- selective scan only in the pipeline flow

### Case C: User asks to scan one known file

Typical tools:

- `/scan_file_sensitive_data`
- `/validate_compliance`

Behavior:

- direct content scan on one file

### Case D: User asks to scan an entire folder or repo exhaustively

Typical tool:

- `/scan_directory_sensitive_data`

Behavior:

- recursive content scan across all files under the root
- this is the brute-force path

## 6. Brute-Force vs Selective Behavior

This is the most important operational distinction in the current system.

### Selective mode

The project is selective when:

- the client uses `/run_full_analysis`
- or the client manually uses metadata/risk tools first, then scans only selected files

In this mode, the project:

- examines all paths structurally
- computes a ranking
- scans only a small risky subset

This is aligned with the original DLP idea.

### Brute-force mode

The project is brute-force when:

- the client uses `/scan_directory_sensitive_data`

In this mode, the project:

- recursively visits every file under the given root
- scans contents regardless of whether a file is likely to be useful

This is useful for exhaustive audits, but it is not cost-efficient.

### Current limitation

The server now has a dedicated deterministic candidate-selection tool, but recursive directory scanning is still available and still brute-force when the client chooses it.

The main remaining gap is that candidate selection is extension and metadata driven rather than parser-aware for rich document formats.

## 7. Current LLM Responsibility Split

The intended architecture discussed during development is:

- server = tools
- client = LLM

However, the current code is not fully there yet.

### What the client LLM currently does

The client LLM:

- receives the user request
- decides which MCP tool to call
- interprets tool outputs
- decides follow-up tool calls
- produces the final natural-language response

### What the server still does with LLMs

The server still performs server-side LLM-backed logic for:

- semantic directory inference
- risk explanation generation

That means the current server is partly deterministic and partly LLM-assisted.

So the present architecture is a hybrid:

- client-side LLM orchestration
- server-side execution
- some server-side semantic reasoning

## 8. Current Strengths

The project already has several solid properties.

### Clear FastAPI to MCP integration

- Uses normal FastAPI routes
- Uses `fastapi_mcp` rather than manually implementing MCP
- Keeps the server callable both as HTTP API and MCP tool layer

### Metadata-first structure

- separates structure analysis from content scanning
- supports selective scanning
- uses Linux-native commands for metadata extraction

### Scalable building blocks

- async FastAPI routes
- concurrent metadata collection
- chunked file scanning
- SQLite feedback persistence

### Safer behavior than before

- file scan no longer silently accepts directory paths
- recursive scan now has its own dedicated tool

## 9. Current Weaknesses and Design Gaps

These are the main architectural gaps in the current implementation.

### No deterministic candidate discovery tool

There is no tool whose explicit purpose is:

- identify likely secret-bearing files
- exclude irrelevant file types
- rank candidates before content scan

This is the biggest missing piece for efficient DLP triage.

### Recursive scan is still brute-force

The recursive directory scanner currently walks all files and scans them all.

That means:

- images may be scanned unnecessarily
- binaries may be scanned unnecessarily
- low-value files are not excluded early

### Server still contains LLM-based reasoning

This makes the server:

- less purely tool-like
- more complex to operate
- more coupled to a specific reasoning strategy

### False negatives can still depend on tool choice

If the client chooses the wrong workflow, results may still be suboptimal even though the directory/file mismatch is now handled better.

For example:

- the client may choose exhaustive recursive scan when selective triage would have been better
- the client may choose selective analysis when the user really wanted exhaustive certainty

## 10. Current Recommended Usage

Given the current codebase, the best practical usage is:

### For quick structural understanding

Use:

- `/list_directory`
- `/get_directory_structure`
- `/get_file_metadata`

### For efficient DLP triage

Use:

- `/identify_scan_candidates`
- `/scan_candidate_files`
- `/run_full_analysis`

Why:

- it filters out obvious low-value files before content scanning
- it prioritizes likely text-bearing secret or PII files
- it computes risk first
- it scans only the most suspicious files
- it is the closest thing to intelligent selective scanning in the current project

### For exhaustive validation

Use:

- `/scan_directory_sensitive_data`

Why:

- it recursively scans all files
- it is useful when the user explicitly wants full coverage

### For a known suspicious file

Use:

- `/scan_file_sensitive_data`
- `/validate_compliance`

## 11. Recommended Client Prompting Strategy Right Now

Without changing server code further, the client should follow these rules:

1. If the user asks for a full or exhaustive repo scan, use `/scan_directory_sensitive_data`
2. If the user asks for efficiency or likely risky files, use `/identify_scan_candidates` first and then `/scan_candidate_files`
3. If the user names a specific file, use `/scan_file_sensitive_data`
4. If the user asks why something is risky, use `/explain_risk`
5. If the user gives analyst feedback, use `/submit_feedback` and optionally `/update_risk_model`

This is important because the current intelligence depends heavily on the client selecting the right tool path.

## 12. What the Project Is Today, in One Sentence

Today, the project is a metadata-first MCP DLP server with graph-based risk scoring, selective top-risk scanning, brute-force recursive scan support, and a separate `mcp-use` client that uses an LLM to orchestrate those tools.

## 13. What Is Missing for the Ideal Version

To reach the strongest version of this system, the next major capability would be a deterministic candidate-selection layer between metadata analysis and content scanning.

That layer should:

- identify text-like and secret-bearing file candidates
- deprioritize or exclude irrelevant file types
- give the client ranked scan candidates
- reduce the need for brute-force recursive scans

At that point the clean workflow would become:

1. structure discovery
2. candidate filtering
3. risk ranking
4. targeted scan
5. explanation and analyst feedback

That would be the most efficient non-brute-force design direction from the current codebase.
