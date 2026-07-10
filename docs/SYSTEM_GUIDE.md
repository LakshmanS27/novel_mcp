# Risk-Aware MCP for Metadata-First Data Loss Prevention

Risk-Aware MCP is a local, metadata-first data loss prevention system exposed as both a normal FastAPI service and an MCP server. It is designed to answer a practical question:

> Can we find likely secrets, credentials, PII, and payment data without blindly reading every file first?

The project does that by separating discovery from content scanning. It first looks at directory structure, filenames, extensions, permissions, sizes, graph position, and optional LLM semantic summaries. Only after that ranking step does it read the contents of selected files.

This gives the project three useful properties:

- It can reduce the number of files read during a scan.
- It gives an LLM client a safe tool surface for selective DLP workflows.
- It includes an evaluation harness that compares selective scanning against an exhaustive baseline with planted ground truth.

## Table of Contents

- [What This Project Does](#what-this-project-does)
- [Why It Exists](#why-it-exists)
- [System Architecture](#system-architecture)
- [Repository Layout](#repository-layout)
- [Three-Phase DLP Model](#three-phase-dlp-model)
- [Execution Paths](#execution-paths)
- [Core Components](#core-components)
- [MCP and FastAPI Surface](#mcp-and-fastapi-surface)
- [LLM Provider Configuration](#llm-provider-configuration)
- [Install](#install)
- [Run the Server](#run-the-server)
- [Use the API](#use-the-api)
- [Use the MCP Client](#use-the-mcp-client)
- [Evaluation Harness](#evaluation-harness)
- [Configuration Reference](#configuration-reference)
- [Security and Privacy Model](#security-and-privacy-model)
- [Troubleshooting](#troubleshooting)
- [Known Limitations](#known-limitations)

## What This Project Does

The server exposes tools for:

- Listing directories.
- Reading filesystem metadata.
- Building directory trees.
- Inferring directory purpose from names and structure.
- Computing risk scores for files.
- Selecting likely scan candidates.
- Scanning selected files for sensitive data patterns.
- Running an end-to-end selective analysis pipeline.
- Accepting true-positive and false-positive feedback.
- Updating risk scoring weights from feedback.
- Running controlled experiments against planted ground truth.

The main idea is simple: reading every file is expensive, noisy, and often unnecessary. This project tries to narrow the scan set first, then read only the files most likely to contain sensitive information.

## Why It Exists

Traditional DLP scans often work like this:

1. Walk an entire directory.
2. Open every file.
3. Run regexes or parsers over all content.
4. Return many alerts, including low-value noise.

That approach has clear drawbacks:

- Large repositories and home directories can contain tens or hundreds of thousands of files.
- Many files are binary, generated, vendored, or irrelevant.
- Reading contents before triage can be overbroad from a privacy perspective.
- LLM agents need guardrails so they do not default to exhaustive recursive scans.

Risk-Aware MCP explores a different architecture:

1. Use metadata and structure first.
2. Rank files by likely sensitivity.
3. Scan only selected files.
4. Keep exhaustive scanning available as a baseline or explicit user choice.

The project is also shaped for research evaluation. The `eval/` harness measures scan reduction, timing, recall, precision, and F1 against controlled seeded violations.

## System Architecture

At runtime there are three layers:

```text
User / evaluator / MCP agent
        |
        v
FastAPI routes mounted as MCP tools
        |
        v
Core DLP engine
        |
        v
Filesystem metadata, optional LLM provider, SQLite feedback store
```

The server is FastAPI-first. Routes are defined in `mcp_server/server/routes.py`, and `fastapi_mcp` mounts those same routes as MCP tools in `mcp_server/server/main.py`.

This means the same capabilities are available through:

- HTTP POST calls.
- MCP clients such as `mcp-use`.
- Direct Python imports in the evaluation harness.

## Repository Layout

```text
.
|-- main.py
|-- pyproject.toml
|-- requirements.txt
|-- .env.example
|-- mcp_server/
|   |-- server/
|   |   |-- main.py
|   |   |-- routes.py
|   |   |-- schemas.py
|   |   `-- config.py
|   |-- core/
|   |   |-- candidate_selector.py
|   |   |-- graph_builder.py
|   |   |-- risk_engine.py
|   |   |-- semantic_inference.py
|   |   |-- scanner.py
|   |   |-- feedback.py
|   |   `-- pipeline.py
|   |-- utils/
|   |   |-- file_utils.py
|   |   |-- linux_utils.py
|   |   |-- llm.py
|   |   `-- logger.py
|   |-- prompts/
|   |   `-- reasoning_prompt.txt
|   `-- data/
|       `-- state.db
|-- mcp_client/
|   |-- chat_client.py
|   |-- eval_agent.py
|   |-- requirements.txt
|   `-- prompts/
|       |-- agent_system_prompt.txt
|       `-- eval_agent_prompt.txt
`-- eval/
    |-- run_evaluation.py
    |-- seed_ground_truth.py
    |-- README.md
    |-- RUNNING_EXPERIMENTS.md
    `-- reports/
```

### Important Files

| File | Role |
| --- | --- |
| `main.py` | Small entrypoint that starts the FastAPI/MCP server. |
| `mcp_server/server/main.py` | Creates the FastAPI app, initializes feedback storage, mounts MCP. |
| `mcp_server/server/routes.py` | HTTP routes and MCP tool source. |
| `mcp_server/server/schemas.py` | Pydantic request and response models. |
| `mcp_server/server/config.py` | Environment-driven settings and LLM provider detection. |
| `mcp_server/core/candidate_selector.py` | Fast deterministic candidate ranking without reading file contents. |
| `mcp_server/core/pipeline.py` | Graph-based full analysis pipeline. |
| `mcp_server/core/scanner.py` | Content scanner for regex and keyword findings. |
| `mcp_server/core/risk_engine.py` | Risk scoring and top-percentile selection. |
| `mcp_server/core/semantic_inference.py` | Optional LLM semantic reasoning and explanations. |
| `mcp_server/core/feedback.py` | SQLite feedback and adaptive scoring weights. |
| `mcp_client/chat_client.py` | Interactive `mcp-use` agent client. |
| `mcp_client/eval_agent.py` | Programmatic MCP client used by LLM-enabled evaluation. |
| `eval/run_evaluation.py` | End-to-end benchmark runner. |
| `eval/seed_ground_truth.py` | Plants known violations and false-positive traps. |

## Three-Phase DLP Model

The project is built around strict phase separation.

### Phase 1: Metadata and Structure

Phase 1 collects information such as:

- Directory tree.
- File names.
- Extensions.
- Sizes.
- Permissions.
- Owners and groups.
- Modified, accessed, and created timestamps where available.
- Parent-child relationships.

This phase does not read file contents.

The implementation lives mostly in:

- `mcp_server/utils/linux_utils.py`
- `mcp_server/utils/file_utils.py`
- `mcp_server/core/graph_builder.py`

### Phase 2: Risk Ranking

Phase 2 ranks files using metadata and context. There are two ranking paths:

- Candidate selector ranking in `candidate_selector.py`.
- Graph and risk-engine ranking in `risk_engine.py`.

Signals include:

- Sensitive keywords in filenames and paths.
- High-value text extensions such as `.env`, `.json`, `.csv`, `.pem`, `.key`, `.sql`.
- Low-value extension exclusion for common binary or generated formats.
- File size.
- Broad read permissions.
- Graph centrality.
- Directory semantic summary from optional LLM inference.
- Similarity links between similarly named files.

This phase still avoids content scanning.

### Phase 3: Selective Content Scan

Only selected files are opened and scanned. The scanner looks for:

- Emails.
- Payment-card-like numbers.
- API keys matching `sk_`, `rk_`, or `pk_` style tokens.
- AWS access key IDs.
- Indian PAN numbers.
- Aadhaar-like numbers.
- Sensitive keywords such as `password`, `secret`, `api_key`, `private key`, `ssn`, and `social security`.

The scanner reads in chunks and stops after `DLP_MCP_MAX_FILE_READ_BYTES` per file. Compliance status is derived from finding severity:

- `COMPLIANT`: no findings.
- `REVIEW`: keyword or lower-severity findings.
- `NON_COMPLIANT`: severe findings such as API keys, AWS keys, payment-card-like values, PAN, or Aadhaar.

## Execution Paths

The codebase has several execution paths because it supports both application use and evaluation.

### Direct API Path

Run the server and call HTTP routes directly:

```bash
python main.py
```

Then call routes such as `/identify_scan_candidates` or `/scan_candidate_files`.

### MCP Agent Path

Run the server, then start the interactive MCP client:

```bash
python main.py
python mcp_client/chat_client.py
```

The agent prompt tells the LLM to prefer selective workflows:

1. Call `identify_scan_candidates`.
2. Call `scan_candidate_files`.
3. Use exhaustive directory scanning only when explicitly requested.

### Evaluation Path

Run:

```bash
python -m eval.run_evaluation /path/to/repo
```

The harness evaluates:

| System | Description | Reads file contents |
| --- | --- | --- |
| System A | Exhaustive baseline | Every file |
| System B | Candidate-selector pipeline | Only selected candidates |
| System B2 | Graph-based risk pipeline | Top ranked 1-5 percent |

With `DLP_MCP_LLM_ENABLED=false`, all systems are deterministic. With `DLP_MCP_LLM_ENABLED=true`, System B uses the MCP client and System B2 enables server-side LLM semantic inference.

## Core Components

### Candidate Selector

`mcp_server/core/candidate_selector.py` is the fastest selective path. It walks files and assigns scores using:

- Extension category.
- Filename/path keywords.
- Size.
- Permissions.
- Hidden-file status.
- Well-known sensitive filenames such as `.env`, `.npmrc`, `.pypirc`, `id_rsa`, and `id_dsa`.

Modes:

- `credentials`: focuses on secrets, tokens, keys, auth, config, vault, env, PEM files.
- `pii`: focuses on customers, HR, identity, SSNs, PAN, Aadhaar, payroll, resumes.
- `broad`: combines credential, PII, finance, legal, backup, export, payment, and dump signals.

Low-value extensions such as images, videos, archives, compiled objects, shared libraries, bytecode, and binaries are excluded from the candidate list.

### Graph Builder

`mcp_server/core/graph_builder.py` converts the directory tree into a `networkx.Graph`.

It adds:

- One node per file or directory.
- Parent-child edges.
- Name-similarity edges for files with related stems and extensions.
- Metadata attributes for size, permissions, owner, depth, and file type.

This lets the risk engine include graph centrality and neighborhood context, rather than judging each file as an isolated path string.

### Risk Engine

`mcp_server/core/risk_engine.py` computes a risk score from four component groups:

- `keyword`: sensitive terms in filenames.
- `semantic`: LLM or fallback directory-purpose signals.
- `graph`: centrality and high-degree graph position.
- `metadata`: risky extensions, broad permissions, and large size.

The default weights are:

```python
{
    "keyword": 0.35,
    "semantic": 0.25,
    "graph": 0.2,
    "metadata": 0.2,
}
```

Scores are normalized with a sigmoid, then the graph pipeline scans the top range controlled by `DLP_MCP_MIN_SCAN_PERCENT` and `DLP_MCP_MAX_SCAN_PERCENT`.

### Semantic Inference

`mcp_server/core/semantic_inference.py` asks an OpenAI-compatible LLM to infer directory purpose from metadata only. The prompt explicitly says not to assume contents were read.

It is used for:

- Directory purpose.
- Risk signals.
- `SCAN` or `IGNORE` decision support.
- Human-readable risk explanations.

If LLM use is disabled, no API key is available, a provider fails, or the response cannot be parsed, the system falls back to deterministic filename-based purpose inference.

The LLM request first tries JSON structured output. If a provider rejects `response_format` with a `400`, the code retries without `response_format` and asks the model to return only JSON.

### Scanner

`mcp_server/core/scanner.py` is the only layer that reads file contents.

It scans bytes using regex patterns and keyword matching. It deduplicates findings by type and preview, returns a byte count, and marks whether scanning was truncated by `DLP_MCP_MAX_FILE_READ_BYTES`.

### Feedback Store

`mcp_server/core/feedback.py` stores user feedback in SQLite:

- `feedback`: path, `TP` or `FP`, notes, timestamp.
- `model_weights`: adaptive scoring weights.

Calling `/update_risk_model` adjusts and normalizes the keyword, semantic, graph, and metadata weights based on true-positive and false-positive feedback counts.

## MCP and FastAPI Surface

All tools are normal FastAPI routes first. MCP is mounted over those routes using `FastApiMCP`.

### Filesystem Tools

| Route | Purpose |
| --- | --- |
| `POST /list_directory` | List immediate entries under a directory. |
| `POST /get_file_metadata` | Return stat-style metadata for a file or directory. |
| `POST /get_directory_structure` | Return a JSON directory tree up to a depth limit. |
| `POST /get_disk_usage` | Return human-readable disk usage using `du -sh`. |

### Intelligence Tools

| Route | Purpose |
| --- | --- |
| `POST /infer_directory_purpose` | Summarize likely directory purpose from metadata and names. |
| `POST /compute_risk_score` | Compute risk components and final risk score for one path. |
| `POST /explain_risk` | Compute score and produce an LLM or fallback explanation. |

### Scanning Tools

| Route | Purpose |
| --- | --- |
| `POST /identify_scan_candidates` | Rank likely scan-worthy files without reading contents. |
| `POST /scan_candidate_files` | Scan an explicit list of candidate files. |
| `POST /scan_file_sensitive_data` | Scan one file. |
| `POST /scan_directory_sensitive_data` | Exhaustively scan all files under a directory. |
| `POST /validate_compliance` | Scan one file and return compliance status. |

### Feedback and Pipeline Tools

| Route | Purpose |
| --- | --- |
| `POST /submit_feedback` | Store `TP` or `FP` feedback for a path. |
| `POST /update_risk_model` | Recompute adaptive weights from feedback. |
| `POST /run_full_analysis` | Run the graph-based selective pipeline end to end. |

## LLM Provider Configuration

The project supports OpenAI-compatible chat-completions providers.

Provider detection order:

1. CommandCode, if `COMMANDCODE_API_KEY` is set.
2. OpenAI, if `OPENAI_API_KEY` is set.
3. OpenRouter, if `OPENROUTER_API_KEY` is set.

The same provider detection is used by the server and MCP client unless you set explicit `DLP_MCP_LLM_*` overrides for server-side semantic inference.

### Base URL Rule

Use the API root, not the full chat-completions endpoint.

Correct:

```dotenv
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
OPENAI_BASE_URL=https://api.openai.com/v1
COMMANDCODE_BASE_URL=https://api.commandcode.ai/provider/v1
```

Wrong:

```dotenv
COMMANDCODE_BASE_URL=https://api.commandcode.ai/provider/v1/chat/completions
```

The code normalizes accidental trailing `/chat/completions`, but the `.env` should still use the root URL.

### Example `.env`

```dotenv
DLP_MCP_APP_HOST=127.0.0.1
DLP_MCP_APP_PORT=8081
DLP_MCP_SERVER_URL=http://localhost:8081/mcp

OPENROUTER_API_KEY=your-openrouter-key
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
OPENROUTER_MODEL=nvidia/nemotron-3-nano-30b-a3b:free

OPENAI_API_KEY=
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-4o-mini

COMMANDCODE_API_KEY=
COMMANDCODE_BASE_URL=https://api.commandcode.ai/provider/v1
COMMANDCODE_MODEL=commandcode-v1

DLP_MCP_LLM_ENABLED=true
DLP_MCP_LLM_TIMEOUT_SECONDS=30.0
```

### Server-Side LLM Overrides

By default, B2 semantic inference uses the auto-detected provider. Only set these if you want the server-side inference path to use a different backend:

```dotenv
DLP_MCP_LLM_BASE_URL=
DLP_MCP_LLM_API_KEY=
DLP_MCP_LLM_MODEL=
```

## Install

Python 3.11 or newer is required.

```bash
cd /path/to/novel_mcp
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Optional, if you want to install the client dependencies separately:

```bash
pip install -r mcp_client/requirements.txt
```

On Linux or WSL, installing `tree` improves directory enumeration:

```bash
sudo apt update
sudo apt install tree
```

If `tree` is unavailable, the project falls back to a Python directory walker. On macOS, stat collection also falls back to Python where GNU-style `stat` is unavailable.

Create local config:

```bash
cp .env.example .env
```

Then edit `.env` for your provider and paths.

## Run the Server

Start through the thin entrypoint:

```bash
python main.py
```

Or run uvicorn directly:

```bash
uvicorn mcp_server.server.main:app --host 127.0.0.1 --port 8081
```

Useful URLs:

- FastAPI docs: `http://127.0.0.1:8081/docs`
- MCP endpoint: `http://127.0.0.1:8081/mcp`

The app creates and initializes the SQLite feedback database on startup.

## Use the API

Identify candidates:

```bash
curl -X POST http://127.0.0.1:8081/identify_scan_candidates \
  -H "Content-Type: application/json" \
  -d '{"path":"/home/youruser/project","mode":"broad","max_candidates":100}'
```

Scan selected candidate files:

```bash
curl -X POST http://127.0.0.1:8081/scan_candidate_files \
  -H "Content-Type: application/json" \
  -d '{"paths":["/home/youruser/project/.env","/home/youruser/project/config/settings.yaml"]}'
```

Run graph-based full analysis:

```bash
curl -X POST http://127.0.0.1:8081/run_full_analysis \
  -H "Content-Type: application/json" \
  -d '{"path":"/home/youruser/project","depth":5}'
```

Scan one file:

```bash
curl -X POST http://127.0.0.1:8081/scan_file_sensitive_data \
  -H "Content-Type: application/json" \
  -d '{"path":"/home/youruser/project/.env"}'
```

Submit feedback:

```bash
curl -X POST http://127.0.0.1:8081/submit_feedback \
  -H "Content-Type: application/json" \
  -d '{"path":"/home/youruser/project/.env","label":"TP","notes":"Confirmed secret exposure"}'
```

Update risk weights:

```bash
curl -X POST http://127.0.0.1:8081/update_risk_model
```

## Use the MCP Client

Start the server first:

```bash
python main.py
```

Then start the interactive client:

```bash
python mcp_client/chat_client.py
```

Example prompts:

- `Analyze /home/me/project for likely credentials using selective scanning.`
- `List the riskiest files under /home/me/data.`
- `Scan /home/me/project/.env for sensitive data.`
- `Explain why /home/me/project/config/prod.yaml is risky.`

The client prompt is intentionally conservative. It tells the agent to use candidate discovery and targeted scanning before any exhaustive scan.

## Evaluation Harness

The evaluation harness lives in `eval/`.

It does the following:

1. Counts files and extensions.
2. Plants controlled ground-truth files if none exist.
3. Runs candidate selection.
4. Runs System B.
5. Runs System B2.
6. Runs System A unless `--skip-baseline` is used.
7. Compares findings against the planted manifest.
8. Writes a JSON report to `eval/reports/`.

### Ground Truth

`eval/seed_ground_truth.py` creates `.eval_ground_truth/` inside the target directory.

It plants 5 violation files:

- Production `.env` with credentials and keys.
- CSV with customer PII and Indian PAN IDs.
- Shell migration script with embedded password.
- Python payment handler with hardcoded card number and Stripe-style key.
- Employee JSON with Aadhaar numbers and salary data.

It also plants 2 false-positive traps:

- Test file with standard payment test card numbers.
- API documentation with placeholder credentials.

The seeder writes a manifest with expected patterns and frameworks.

### Run Deterministic Evaluation

```bash
DLP_MCP_LLM_ENABLED=false python -m eval.run_evaluation /path/to/repo
```

This evaluates System A, System B, and System B2 without LLM calls.

### Run LLM-Enabled Evaluation

```bash
DLP_MCP_LLM_ENABLED=true python -m eval.run_evaluation /path/to/repo
```

In this mode:

- System B uses `mcp_client/eval_agent.py` and MCP tools.
- System B auto-starts a local MCP server if needed.
- System B2 runs direct core code with LLM semantic inference enabled.
- System A remains deterministic.

The runner prints the resolved LLM provider, model, and base URL near startup.

### Useful Flags

```bash
python -m eval.run_evaluation /path/to/repo --skip-seed
python -m eval.run_evaluation /path/to/repo --skip-baseline
```

Clean seeded files:

```bash
python -m eval.seed_ground_truth /path/to/repo --clean
```

Reports are written as:

```text
eval/reports/eval_<hostname>_<timestamp>.json
```

Report fields include:

- Target metadata.
- File and extension counts.
- Candidate selection summary.
- System B results.
- System B2 results.
- System A baseline results.
- Ground-truth recall, precision, F1.
- Scan reduction and timing comparison.

## Configuration Reference

### Application Settings

| Variable | Default | Meaning |
| --- | --- | --- |
| `DLP_MCP_APP_NAME` | `Risk-Aware MCP DLP` | FastAPI app title. |
| `DLP_MCP_APP_HOST` | `127.0.0.1` | Server bind host. |
| `DLP_MCP_APP_PORT` | `8000` in code, often `8081` in `.env` | Server bind port. |
| `DLP_MCP_SERVER_URL` | `http://localhost:8081/mcp` in clients | MCP endpoint for clients. |
| `DLP_MCP_LOG_LEVEL` | `INFO` | Logging level. |

### Tree, Graph, and Selection

| Variable | Default | Meaning |
| --- | --- | --- |
| `DLP_MCP_DEFAULT_TREE_DEPTH` | `3` | Default route tree depth. |
| `DLP_MCP_MAX_TREE_DEPTH` | `8` | Maximum accepted tree depth. |
| `DLP_MCP_STAT_CONCURRENCY` | `64` | Concurrent metadata collection limit. |
| `DLP_MCP_SIMILARITY_BUCKET_LIMIT` | `64` | Limits name-similarity edge explosion. |
| `DLP_MCP_MIN_SCAN_PERCENT` | `0.01` | Minimum graph-selected scan percentage. |
| `DLP_MCP_MAX_SCAN_PERCENT` | `0.05` | Maximum graph-selected scan percentage. |
| `DLP_MCP_DEFAULT_CANDIDATE_MODE` | `broad` | Candidate selector default mode. |
| `DLP_MCP_MAX_CANDIDATE_FILES` | `100` | Default maximum selected candidates. |

### Scanner

| Variable | Default | Meaning |
| --- | --- | --- |
| `DLP_MCP_MAX_FILE_READ_BYTES` | `2000000` | Max bytes read per file. |
| `DLP_MCP_SCAN_CHUNK_SIZE` | `8192` | Chunk size for file reads. |

### Storage and Prompts

| Variable | Default | Meaning |
| --- | --- | --- |
| `DLP_MCP_DB_PATH` | `mcp_server/data/state.db` | SQLite feedback database. |
| `DLP_MCP_PROMPTS_DIR` | `mcp_server/prompts` | Server-side reasoning prompt directory. |

### LLM

| Variable | Meaning |
| --- | --- |
| `COMMANDCODE_API_KEY`, `COMMANDCODE_BASE_URL`, `COMMANDCODE_MODEL` | CommandCode provider config. |
| `OPENAI_API_KEY`, `OPENAI_BASE_URL`, `OPENAI_MODEL` | OpenAI provider config. |
| `OPENROUTER_API_KEY`, `OPENROUTER_BASE_URL`, `OPENROUTER_MODEL` | OpenRouter provider config. |
| `DLP_MCP_LLM_ENABLED` | Enables server-side LLM semantic inference when true. |
| `DLP_MCP_LLM_BASE_URL` | Optional server-side override base URL. |
| `DLP_MCP_LLM_API_KEY` | Optional server-side override key. |
| `DLP_MCP_LLM_MODEL` | Optional server-side override model. |
| `DLP_MCP_LLM_TIMEOUT_SECONDS` | Timeout for server-side LLM calls. |

## Path Safety

The project restricts paths for local safety.

Linux and WSL allowed roots:

- `/home/`
- `/mnt/`
- `/tmp/`

macOS allowed roots:

- `/Users/`
- `/tmp/`
- `/private/`

The restriction lives in `mcp_server/utils/file_utils.py`. If your target directory is outside those roots, update `ALLOWED_ROOT_PREFIXES`.

## Security and Privacy Model

This project is local-first, but it still handles sensitive paths and potentially sensitive file contents.

Important behaviors:

- Phase 1 and Phase 2 do not read file contents.
- LLM semantic inference receives tree data and filenames, not file contents.
- File contents are read only by explicit scan functions or Phase 3 selected scans.
- Scanner output includes match previews, not entire file contents.
- `.env` may contain real API keys and should not be committed.
- Evaluation seeding writes synthetic secrets into `.eval_ground_truth/` inside target directories.
- MCP tools can scan local files under allowed roots, so expose the server only to trusted local clients.

## Troubleshooting

### The eval run is using the wrong model

The runner prints:

```text
LLM: provider=<provider> model=<model> base_url=<url>
```

If that line does not match `.env`, check shell overrides:

```bash
env | grep -E 'COMMANDCODE|OPENAI|OPENROUTER|DLP_MCP_LLM'
```

Environment variables exported in the shell can override values you expect from `.env`.

### `404 ... /chat/completions/chat/completions`

Your provider base URL probably included `/chat/completions`. Use the API root:

```dotenv
COMMANDCODE_BASE_URL=https://api.commandcode.ai/provider/v1
```

### OpenRouter returns `400 Bad Request`

Some models reject `response_format` or other structured-output parameters. The semantic inference layer retries without `response_format`, but a second `400` can still mean:

- the model slug is invalid,
- the provider key does not have access,
- the model does not support chat completions through that route,
- the request size is too large for the model/provider,
- provider-specific parameters are being rejected.

Try another OpenRouter model or use `DLP_MCP_LLM_MODEL` to isolate B2 from the client model.

### `tree` command not found

The code falls back to a Python directory walker. Installing `tree` is still recommended for Linux and WSL:

```bash
sudo apt install tree
```

### `stat` behaves differently on macOS

The code falls back to Python `os.stat()` when GNU-style `stat` is not available.

### Path not allowed

Use an absolute path under the allowed roots or update `ALLOWED_ROOT_PREFIXES` in `mcp_server/utils/file_utils.py`.

### Baseline is slow

System A scans every file. Use:

```bash
python -m eval.run_evaluation /path/to/large/repo --skip-baseline
```

### MCP client cannot connect

Check that server and client agree on the MCP URL:

```dotenv
DLP_MCP_SERVER_URL=http://localhost:8081/mcp
```

Start the server manually for interactive client use:

```bash
python main.py
```

For evaluation, the harness can auto-start the local server when LLM mode is enabled.

## Known Limitations

- The scanner is regex and keyword based. It does not parse PDFs, Office documents, images, or archives deeply.
- Payment-card-like matches are checksum-validated with the Luhn algorithm, and Aadhaar-like matches with the Verhoeff algorithm, but Luhn/Verhoeff only prove checksum validity, not that a number is a real, active credential — some synthetic test numbers can still pass.
- Indian PAN matches are validated against the PAN category-code position but have no public checksum digit, so false positives are still possible on PAN-shaped strings.
- Semantic inference depends on provider/model behavior and may fall back to deterministic logic.
- Candidate selection favors text-bearing and configuration-like files; unusual sensitive binary formats need specialized parsers.
- The graph pipeline uses bounded tree depth, so very deep files may be missed by B2 depending on `DLP_MCP_MAX_TREE_DEPTH`.
- Feedback learning is simple count-based weight adaptation, not a trained classifier.
- The project is intended for local experimentation and research-oriented evaluation, not as a complete enterprise DLP product.

## Development Notes

Compile-check the Python modules:

```bash
.venv/bin/python -m compileall mcp_server mcp_client eval
```

Inspect current resolved settings:

```bash
.venv/bin/python - <<'PY'
from dotenv import load_dotenv
load_dotenv('.env')
from mcp_server.server.config import Settings
s = Settings()
print(s.llm_provider)
print(s.llm_model)
print(s.llm_base_url)
print(s.llm_enabled)
PY
```

The codebase intentionally keeps the core engine importable without running the web server. That makes evaluation, testing, and MCP serving share the same implementation instead of drifting into separate behaviors.
