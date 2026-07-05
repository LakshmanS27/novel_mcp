import asyncio
from os import getenv
from pathlib import Path

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from mcp_use import MCPAgent, MCPClient

from mcp_server.utils.llm import normalize_openai_base_url


load_dotenv()


PROMPT_PATH = Path(__file__).resolve().parent / "prompts" / "agent_system_prompt.txt"


def _load_agent_prompt() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8").strip()


def _build_llm() -> ChatOpenAI:
    """Build LLM client with auto-detected provider support.
    
    Checks for API keys in priority order: CommandCode > OpenAI > OpenRouter
    Uses the first provider with a valid, non-empty API key.
    """
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
        api_key = getenv(provider["api_key_env"], "").strip()
        if not api_key or api_key in ("", "your-api-key-here", "sk-xxx"):
            continue
            
        base_url = normalize_openai_base_url(
            getenv(provider["base_url_env"], provider["default_base_url"])
        )
        model = getenv(provider["model_env"], provider["default_model"])
        
        return ChatOpenAI(
            api_key=api_key,
            base_url=base_url,
            model=model,
        )
    
    return ChatOpenAI(
        api_key=getenv("OPENROUTER_API_KEY"),
        base_url=normalize_openai_base_url(
            getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
        ),
        model=getenv("OPENROUTER_MODEL", "nvidia/nemotron-3-nano-30b-a3b:free"),
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
