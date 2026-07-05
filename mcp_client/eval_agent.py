from __future__ import annotations

import asyncio
import json
import os
import socket
import sys
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from mcp_use import MCPAgent, MCPClient

from mcp_server.utils.llm import normalize_openai_base_url


load_dotenv()


BASE_DIR = Path(__file__).resolve().parent
SYSTEM_PROMPT_PATH = BASE_DIR / "prompts" / "agent_system_prompt.txt"
EVAL_PROMPT_PATH = BASE_DIR / "prompts" / "eval_agent_prompt.txt"


def _load_prompt(path: Path) -> str:
    return path.read_text(encoding="utf-8").strip()


def _build_llm() -> ChatOpenAI:
    """Build LLM client with auto-detected provider support.
    
    Checks for API keys in priority order: CommandCode > OpenAI > OpenRouter
    Uses the first provider with a valid, non-empty API key.
    """
    # Provider configuration with priority order
    providers = [
        {
            "name": "commandcode",
            "api_key_env": "COMMANDCODE_API_KEY",
            "base_url_env": "COMMANDCODE_BASE_URL",
            "model_env": "COMMANDCODE_MODEL",
            "default_base_url": "https://api.commandcode.ai/v1",
            "default_model": "commandcode-v1",
        },
        {
            "name": "openai",
            "api_key_env": "OPENAI_API_KEY",
            "base_url_env": "OPENAI_BASE_URL",
            "model_env": "OPENAI_MODEL",
            "default_base_url": "https://api.openai.com/v1",
            "default_model": "gpt-4o-mini",
        },
        {
            "name": "openrouter",
            "api_key_env": "OPENROUTER_API_KEY",
            "base_url_env": "OPENROUTER_BASE_URL",
            "model_env": "OPENROUTER_MODEL",
            "default_base_url": "https://openrouter.ai/api/v1",
            "default_model": "nvidia/nemotron-3-nano-30b-a3b:free",
        },
    ]
    
    for provider in providers:
        api_key = os.getenv(provider["api_key_env"], "").strip()
        # Skip if key is missing, empty, or placeholder
        if not api_key or api_key in ("", "your-api-key-here", "sk-xxx"):
            continue
            
        base_url = normalize_openai_base_url(
            os.getenv(provider["base_url_env"], provider["default_base_url"])
        )
        model = os.getenv(provider["model_env"], provider["default_model"])
        
        return ChatOpenAI(
            api_key=api_key,
            base_url=base_url,
            model=model,
        )
    
    # Fallback to OpenRouter with defaults (will fail if no key set)
    return ChatOpenAI(
        api_key=os.getenv("OPENROUTER_API_KEY"),
        base_url=normalize_openai_base_url(
            os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
        ),
        model=os.getenv("OPENROUTER_MODEL", "nvidia/nemotron-3-nano-30b-a3b:free"),
    )


def _extract_json(text: str) -> dict:
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise
        return json.loads(text[start : end + 1])


def _server_url() -> str:
    return os.getenv("DLP_MCP_SERVER_URL", "http://localhost:8081/mcp")


def _base_http_url(server_url: str) -> tuple[str, str, int]:
    parsed = urlparse(server_url)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    base_url = f"{parsed.scheme}://{host}:{port}"
    return base_url, host, port


async def _is_port_open(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=1):
            return True
    except OSError:
        return False


async def ensure_local_mcp_server() -> asyncio.subprocess.Process | None:
    server_url = _server_url()
    _, host, port = _base_http_url(server_url)
    if await _is_port_open(host, port):
        return None

    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "uvicorn",
        "mcp_server.server.main:app",
        "--host",
        host,
        "--port",
        str(port),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    for _ in range(50):
        if await _is_port_open(host, port):
            return process
        await asyncio.sleep(0.2)

    process.terminate()
    await process.wait()
    raise RuntimeError("Failed to start local MCP server for evaluation.")


async def run_eval_via_mcp(target_path: str) -> dict:
    server_url = _server_url()
    config = {
        "mcpServers": {
            "risk_aware_dlp": {
                "url": server_url,
            }
        }
    }

    system_prompt = _load_prompt(SYSTEM_PROMPT_PATH)
    eval_prompt = _load_prompt(EVAL_PROMPT_PATH)
    llm = _build_llm()
    client = MCPClient.from_dict(config)
    agent = MCPAgent(llm=llm, client=client, max_steps=40)

    prompt = (
        f"{system_prompt}\n\n"
        f"{eval_prompt}\n\n"
        f"Target directory: {target_path}\n"
        "Use broad candidate discovery and return the required JSON schema."
    )

    try:
        result = await agent.run(prompt)
        return _extract_json(str(result))
    finally:
        await client.close_all_sessions()
