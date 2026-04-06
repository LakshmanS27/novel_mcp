# Risk-Aware MCP for Intelligent Data Loss Prevention

This project implements a production-oriented FastAPI service that is converted into an MCP server with `fastapi_mcp`. It performs metadata-first DLP analysis in three strict phases:

1. Phase 1: filesystem structure and metadata only
2. Phase 2: probabilistic risk scoring with graph and semantic inference
3. Phase 3: selective scanning of only the top 1-5% highest-risk files

The MCP surface is exposed from normal FastAPI routes and can be consumed by local LLM clients such as `mcp-use`.

## Architecture

```text
mcp_server/
├── server/
│   ├── main.py
│   ├── routes.py
│   ├── schemas.py
│   └── config.py
├── core/
│   ├── candidate_selector.py
│   ├── graph_builder.py
│   ├── risk_engine.py
│   ├── semantic_inference.py
│   ├── scanner.py
│   ├── feedback.py
│   └── pipeline.py
├── utils/
│   ├── file_utils.py
│   ├── linux_utils.py
│   └── logger.py
├── prompts/
│   └── reasoning_prompt.txt
└── data/
    └── state.db

mcp_client/
├── README.md
├── chat_client.py
├── prompts/
│   └── agent_system_prompt.txt
└── requirements.txt
```

## Features

- Uses `tree -J`, `stat`, and `du` for Linux-native metadata collection
- Supports Linux and WSL-style paths such as `/home/...` and `/mnt/c/...`
- Builds a `networkx` graph of directories and files without reading contents during phases 1 and 2
- Calls an OpenAI-compatible local LLM endpoint for semantic directory inference and risk explanations
- Scans only the highest-risk 1-5% of files with streamed reads
- Learns from user feedback using SQLite-backed adaptive weights
- Exposes all major capabilities as FastAPI routes and MCP tools through `fastapi_mcp`
- Adds deterministic candidate filtering so likely text-bearing secret/PII files can be scanned before any brute-force recursive sweep

## Install

Python 3.11+ is required.

### Linux / WSL prerequisites

Install `tree`:

```bash
sudo apt update
sudo apt install tree
```

### Python dependencies

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Install the optional interactive MCP client dependencies if you want to run `mcp_client/chat_client.py`:

```bash
pip install -r mcp_client/requirements.txt
```

## Configuration

Create a local `.env` file from `.env.example` and adjust the values for your environment:

```bash
cp .env.example .env
```

Example `.env` values:

```dotenv
DLP_MCP_APP_HOST=127.0.0.1
DLP_MCP_APP_PORT=8000
DLP_MCP_LLM_BASE_URL=http://127.0.0.1:11434/v1
DLP_MCP_LLM_API_KEY=
DLP_MCP_LLM_MODEL=local-model
DLP_MCP_SERVER_URL=http://localhost:8000/mcp
OPENROUTER_API_KEY=
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
OPENROUTER_MODEL=nvidia/nemotron-3-nano-30b-a3b:free
```

Notes:

- `.env` is loaded automatically by [`config.py`](/home/slakshman2004/novel-mcp/mcp_server/server/config.py#L11)
- If your local OpenAI-compatible endpoint does not require auth, leave `DLP_MCP_LLM_API_KEY` empty
- Update `DLP_MCP_DB_PATH` and `DLP_MCP_PROMPTS_DIR` if you move the project directory

## Run the FastAPI + MCP server

```bash
python main.py
```

Or with uvicorn:

```bash
uvicorn mcp_server.server.main:app --host 127.0.0.1 --port 8000
```

## How MCP tools are exposed

The application defines standard FastAPI routes first in `mcp_server/server/routes.py`. The app is then converted into MCP in `mcp_server/server/main.py` using:

```python
from fastapi_mcp import FastApiMCP

mcp = FastApiMCP(app, name="risk_aware_dlp", description="Metadata-first DLP analysis exposed as MCP tools.")
mcp.mount_http()
```

This exposes the MCP server over HTTP transport on the mounted MCP path managed by `fastapi_mcp`.

## Exposed tools

- `/list_directory`
- `/get_file_metadata`
- `/get_directory_structure`
- `/infer_directory_purpose`
- `/compute_risk_score`
- `/explain_risk`
- `/scan_file_sensitive_data`
- `/identify_scan_candidates`
- `/scan_candidate_files`
- `/scan_directory_sensitive_data`
- `/validate_compliance`
- `/submit_feedback`
- `/update_risk_model`
- `/run_full_analysis`
- `/get_disk_usage`

All routes are async and return strict JSON.

## Example API usage

Identify likely credential-bearing candidates:

```bash
curl -X POST http://127.0.0.1:8000/identify_scan_candidates \
  -H "Content-Type: application/json" \
  -d '{"path":"/home/youruser/project","mode":"credentials","max_candidates":25}'
```

Scan only selected candidate files:

```bash
curl -X POST http://127.0.0.1:8000/scan_candidate_files \
  -H "Content-Type: application/json" \
  -d '{"paths":["/home/youruser/project/.env","/home/youruser/project/config/settings.yaml"]}'
```

Get directory structure:

```bash
curl -X POST http://127.0.0.1:8000/get_directory_structure \
  -H "Content-Type: application/json" \
  -d '{"path":"/home/youruser/data","depth":4}'
```

Run the full pipeline:

```bash
curl -X POST http://127.0.0.1:8000/run_full_analysis \
  -H "Content-Type: application/json" \
  -d '{"path":"/mnt/c/Users/youruser/Documents","depth":5}'
```

Submit feedback:

```bash
curl -X POST http://127.0.0.1:8000/submit_feedback \
  -H "Content-Type: application/json" \
  -d '{"path":"/home/youruser/data/payroll.csv","label":"TP","notes":"Contains salary data"}'
```

## Connecting with `mcp-use`

Example Python client workflow for `mcp-use`:

```python
import asyncio
from os import getenv

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from mcp_use import MCPAgent, MCPClient

load_dotenv()

async def main():
    config = {
        "mcpServers": {
            "risk_aware_dlp": {
                "url": getenv("DLP_MCP_SERVER_URL", "http://localhost:8000/mcp")
            }
        }
    }

    llm = ChatOpenAI(
        api_key=getenv("OPENROUTER_API_KEY"),
        base_url=getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
        model=getenv("OPENROUTER_MODEL", "nvidia/nemotron-3-nano-30b-a3b:free"),
    )

    client = MCPClient.from_dict(config)
    agent = MCPAgent(llm=llm, client=client, max_steps=30)
    result = await agent.run("Analyze /home/me/data and scan only the riskiest files")
    print(result)

asyncio.run(main())
```

The server lives under `mcp_server/`. Client-side `mcp-use` integration artifacts live separately under [`mcp_client/README.md`](/home/slakshman2004/novel-mcp/mcp_client/README.md) and [`mcp_client/chat_client.py`](/home/slakshman2004/novel-mcp/mcp_client/chat_client.py).

The client also loads a separate orchestration prompt from [`mcp_client/prompts/agent_system_prompt.txt`](/home/slakshman2004/novel-mcp/mcp_client/prompts/agent_system_prompt.txt) so it prefers selective candidate discovery and targeted scans before brute-force recursive scans.

## Example queries from an MCP client

- "List the top risky files under `/home/slakshman2004/projects`"
- "Explain why `/mnt/c/Users/me/Documents/finance/payroll.xlsx` should be scanned"
- "Analyze `/home/me/data` and only scan the highest-risk files"
- "Mark `/home/me/data/archive.csv` as a false positive and update the risk model"

## Phase separation

- Phase 1 collects structure and metadata only using `tree`, `stat`, and `du`
- Phase 2 builds the graph, computes probabilistic risk scores, and can identify likely scan candidates deterministically
- Phase 3 scans only the top 1-5% of risky files using streaming reads, or scans chosen candidates when the client uses the selective scan workflow

## Notes

- The semantic inference layer never reads file contents
- The scanner reads file contents only for the selected top-risk files
- SQLite state is initialized automatically at `mcp_server/data/state.db`
