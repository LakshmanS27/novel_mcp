# Project Structure

This document summarizes the repository layout and the role of the main files and folders.

Root
- `main.py`: entrypoint that launches the FastAPI + MCP server (`mcp_server.server.main`).
- `README.md`: high-level project overview and links to docs.
- `pyproject.toml`: package metadata and top-level dependencies.
- `requirements.txt`: runtime dependencies used for quick installs.
- `.env.example` / `.env`: runtime environment variables (LLM keys, server URL).
- `EXPERIMENTATION.md`, `workflow.md`: design notes and workflows.

Top-level folders
- `mcp_server/` — FastAPI-based server implementing the MCP tool surface.
  - `server/`
    - `main.py`: constructs FastAPI app, mounts MCP tools, runs uvicorn.
    - `routes.py`: HTTP routes (also exposed as MCP tools via fastapi_mcp).
    - `config.py`: settings read from `.env` (pydantic-settings); LLM provider auto-detect.
    - `schemas.py`: request/response Pydantic models.
  - `core/`
    - `candidate_selector.py`, `risk_engine.py`, `scanner.py`, `pipeline.py`: core DLP logic.
    - `feedback.py`: SQLite-backed feedback store and model update logic.
  - `prompts/`: server-side LLM prompts used for semantic inference/explanations.
  - `data/`: runtime state (SQLite DB `state.db` by default).
  - `utils/`: helper utilities (file I/O, logging, LLM helpers).

- `mcp_client/` — LLM-driven client that uses `mcp-use` to call server tools.
  - `chat_client.py`: interactive REPL agent that prompts an LLM and calls MCP tools.
  - `eval_agent.py`: programmatic agent used by evaluation harness.
  - `prompts/`: client-side system prompts for orchestration.
  - `requirements.txt`: client-specific dependencies (langchain-openai, mcp-use, python-dotenv).

- `eval/` — evaluation harness and experiments.
  - `run_evaluation.py`, `seed_ground_truth.py`: utilities to run experiments and seed test data.
  - `RUNNING_EXPERIMENTS.md`, `README.md`: evaluation instructions and notes.

Packaging / metadata
- `novel_mcp.egg-info/`: generated package metadata for builds.

How pieces fit at runtime
1. Start the server (FastAPI app) which mounts MCP tools via `fastapi_mcp`.
2. The client (`mcp_client/chat_client.py`) connects to the server MCP endpoint and uses an LLM to orchestrate tool calls.
3. Typical workflows:
   - Metadata-only inspection (list, tree, metadata endpoints) — no file reads.
   - Candidate identification and selective scan (recommended) — rank by risk, scan top percent.
   - Brute-force recursive scan (explicit) — scans all files under a directory.

Quick start (local)
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -r mcp_client/requirements.txt
# configure .env with your LLM keys and DLP_MCP_SERVER_URL
python3 main.py            # start server (defaults to 127.0.0.1:8000)
# in another terminal with the same .env loaded
python3 mcp_client/chat_client.py
```

Configuration notes
- LLM provider is auto-detected from environment variables: `COMMANDCODE_*`, `OPENAI_*`, `OPENROUTER_*`.
- Server settings are read via `pydantic-settings` from `.env` (prefix `DLP_MCP_` for explicit overrides).
- Default server port in `Settings` is `8000`; the client example defaults to `http://localhost:8081/mcp` unless `DLP_MCP_SERVER_URL` is set.

Where to look next
- For server startup: `mcp_server/server/main.py` and `mcp_server/server/config.py`.
- For client usage: `mcp_client/chat_client.py` and `mcp_client/requirements.txt`.
- For running experiments: `eval/README.md` and `eval/run_evaluation.py`.

Contact / provenance
- See `README.md` for authorship and license (MIT).

