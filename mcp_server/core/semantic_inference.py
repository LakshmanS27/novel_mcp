from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx

from mcp_server.server.config import Settings
from mcp_server.utils.logger import get_logger


logger = get_logger(__name__)


def _load_prompt(settings: Settings) -> str:
    prompt_path = Path(settings.prompts_dir) / "reasoning_prompt.txt"
    return prompt_path.read_text(encoding="utf-8")


def _fallback_purpose(filenames: list[str]) -> dict[str, Any]:
    lowered = " ".join(name.lower() for name in filenames[:100])
    signals = []
    purpose = "general filesystem storage"
    if any(token in lowered for token in ("finance", "invoice", "payroll", "tax")):
        purpose = "financial records"
        signals.append("financial naming patterns")
    if any(token in lowered for token in ("hr", "resume", "employee", "candidate")):
        purpose = "human resources records"
        signals.append("employee-related naming patterns")
    if any(token in lowered for token in ("secret", "token", "key", "credential", "vault")):
        purpose = "credential or secrets storage"
        signals.append("credential-related naming patterns")
    return {
        "purpose": purpose,
        "confidence": 0.45,
        "risk_signals": signals,
        "decision": "SCAN" if signals else "IGNORE",
        "reasoning": signals or ["No strong semantic signals were available from filenames alone."],
    }


async def _chat_completion(settings: Settings, system_prompt: str, user_payload: dict[str, Any]) -> dict[str, Any]:
    if not settings.llm_enabled:
        return _fallback_purpose(user_payload.get("filenames", []))
    headers = {"Content-Type": "application/json"}
    if settings.llm_api_key:
        headers["Authorization"] = f"Bearer {settings.llm_api_key}"
    body = {
        "model": settings.llm_model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(user_payload)},
        ],
        "temperature": 0.1,
        "response_format": {"type": "json_object"},
    }
    async with httpx.AsyncClient(timeout=settings.llm_timeout_seconds) as client:
        response = await client.post(
            f"{settings.llm_base_url.rstrip('/')}/chat/completions",
            headers=headers,
            json=body,
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
    parsed = json.loads(content)
    logger.info("llm response keys: %s", sorted(parsed.keys()))
    return parsed


async def infer_directory_purpose(
    tree_data: list[dict[str, Any]],
    filenames: list[str],
    settings: Settings,
) -> dict[str, Any]:
    prompt = _load_prompt(settings)
    payload = {
        "task": "Infer the purpose of this directory tree from names and structure only. Never assume file contents.",
        "tree": tree_data,
        "filenames": filenames[:300],
        "required_output": {
            "purpose": "string",
            "confidence": "float between 0 and 1",
            "risk_signals": ["array of strings"],
            "decision": "SCAN or IGNORE",
            "reasoning": ["array of strings"],
        },
    }
    try:
        response = await _chat_completion(settings, prompt, payload)
    except Exception as exc:
        logger.warning("LLM inference failed, using fallback: %s", exc)
        response = _fallback_purpose(filenames)
    return {
        "purpose": str(response.get("purpose", "general filesystem storage")),
        "confidence": float(response.get("confidence", 0.4)),
        "risk_signals": list(response.get("risk_signals", [])),
        "decision": str(response.get("decision", "IGNORE")),
        "reasoning": list(response.get("reasoning", [])),
    }


async def explain_risk_with_llm(
    path: str,
    risk_score: float,
    factors: list[str],
    semantic_summary: dict[str, Any],
    settings: Settings,
) -> dict[str, Any]:
    prompt = _load_prompt(settings)
    payload = {
        "task": "Explain why this path is risky using metadata-only context and return JSON.",
        "path": path,
        "risk_score": risk_score,
        "factors": factors,
        "semantic_summary": semantic_summary,
        "required_output": {
            "decision": "SCAN or IGNORE",
            "reasoning": ["array of strings"],
            "explanation": "string",
        },
    }
    try:
        response = await _chat_completion(settings, prompt, payload)
    except Exception as exc:
        logger.warning("LLM explanation failed, using fallback: %s", exc)
        response = {
            "decision": "SCAN" if risk_score >= 0.6 else "IGNORE",
            "reasoning": factors,
            "explanation": f"{path} scored {risk_score:.2f} due to metadata and graph signals.",
        }
    return {
        "decision": str(response.get("decision", "IGNORE")),
        "reasoning": list(response.get("reasoning", factors)),
        "explanation": str(response.get("explanation", "")),
    }
