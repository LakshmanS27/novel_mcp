import asyncio
from os import getenv
from pathlib import Path

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from mcp_use import MCPAgent, MCPClient


load_dotenv()


PROMPT_PATH = Path(__file__).resolve().parent / "prompts" / "agent_system_prompt.txt"


def _load_agent_prompt() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8").strip()


async def main() -> None:
    config = {
        "mcpServers": {
            "risk_aware_dlp": {
                "url": getenv("DLP_MCP_SERVER_URL", "http://localhost:8081/mcp"),
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
