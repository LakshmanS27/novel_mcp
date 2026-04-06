# MCP Client

This directory is intentionally separate from the MCP server package. The LLM lives here, not inside the server boundary.

## Files

- `chat_client.py`: interactive `mcp-use` client using `MCPAgent` and `ChatOpenAI`
- `prompts/agent_system_prompt.txt`: selective orchestration rules for tool choice
- `requirements.txt`: Python dependencies for the client only

## Install

```bash
pip install -r mcp_client/requirements.txt
```

## Environment

The client reads these values from the root `.env`:

```dotenv
DLP_MCP_SERVER_URL=http://localhost:8081/mcp
OPENROUTER_API_KEY=your-key
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
OPENROUTER_MODEL=nvidia/nemotron-3-nano-30b-a3b:free
```

## Run

Start the MCP server first, then run:

```bash
python3 mcp_client/chat_client.py
```

## Behavior

The client prepends `prompts/agent_system_prompt.txt` to each user request so the agent:

- prefers `identify_scan_candidates` for repo and folder hunts
- uses `scan_candidate_files` before brute-force recursive scans
- only falls back to `scan_directory_sensitive_data` when the user explicitly wants exhaustive coverage
