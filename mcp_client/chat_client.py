import asyncio
from os import getenv
from pathlib import Path

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from mcp_use import MCPAgent, MCPClient

from mcp_server.server.config import OPENROUTER, PROVIDER_CONFIGS, detect_provider, get_provider_env_vars
from mcp_server.utils.llm import normalize_openai_base_url

import logging

# Reduce mcp_use logs

logging.getLogger("mcp_use").setLevel(logging.CRITICAL)


load_dotenv()


PROMPT_PATH = Path(__file__).resolve().parent / "prompts" / "agent_system_prompt.txt"


def _load_agent_prompt() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8").strip()


def _build_llm() -> ChatOpenAI:
    """Build LLM client with auto-detected provider support.

    Uses the same detection order and provider defaults as the server
    (`mcp_server.server.config`) so the client and server never disagree
    about which provider or base URL is in effect.
    """
    provider = detect_provider()
    env_vars = get_provider_env_vars(provider)
    api_key = env_vars["api_key"] or getenv(PROVIDER_CONFIGS[OPENROUTER]["api_key_env"])

    return ChatOpenAI(
        api_key=api_key,
        base_url=env_vars["base_url"],
        model=env_vars["model"],
    )


async def main() -> None:
    config = {
        "mcpServers": {
            "risk_aware_dlp": {
                "url": getenv("DLP_MCP_SERVER_URL", "http://localhost:8081/mcp"),
            }
        }
    }

    llm = _build_llm()

    client = MCPClient.from_dict(config)
    agent = MCPAgent(llm=llm, client=client, max_steps=30)
    system_prompt = _load_agent_prompt()

    print("MCP Agent Chat (type 'exit' to quit)\n")

    try:
        while True:
            query = input("You: ")
            if query.lower() in ("exit", "quit"):
                break

            agent_input = f"{system_prompt}\n\nUser request:\n{query}"
            result = await agent.run(agent_input)
            print(f"Agent: {result}\n")
    finally:
        await client.close_all_sessions()


if __name__ == "__main__":
    asyncio.run(main())
