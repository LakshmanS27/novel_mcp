from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx

from mcp_server.server.config import Settings
from mcp_server.utils.logger import get_logger
from mcp_server.utils.llm import normalize_openai_base_url


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


def _parse_llm_response(response_data: dict) -> str:
    """Parse LLM response handling different provider formats.
    
    Different providers may return responses in slightly different formats.
    This normalizes them to extract the message content.
    """
    # Standard OpenAI-compatible format
    if "choices" in response_data:
        return response_data["choices"][0]["message"]["content"]
    
    # Alternative format with direct content
    if "content" in response_data:
        return response_data["content"]
    
    # Some providers wrap it in different structures
    if "message" in response_data:
        msg = response_data["message"]
        if isinstance(msg, dict):
            return msg.get("content", str(msg))
        return str(msg)
    
    # Last resort: try to find any string content
    for key in ["text", "output", "response", "result"]:
        if key in response_data:
            val = response_data[key]
            if isinstance(val, str):
                return val
            if isinstance(val, dict) and "content" in val:
                return val["content"]
    
    raise ValueError(f"Unable to parse LLM response format: {list(response_data.keys())}")


def _extract_json_object(text: str) -> dict[str, Any]:
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise
        return json.loads(text[start : end + 1])


async def _post_chat_completion(
    settings: Settings,
    headers: dict[str, str],
    body: dict[str, Any],
) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=settings.llm_timeout_seconds) as client:
        response = await client.post(
            f"{normalize_openai_base_url(settings.llm_base_url)}/chat/completions",
            headers=headers,
            json=body,
        )
        response.raise_for_status()
        return response.json()


async def _chat_completion(settings: Settings, system_prompt: str, user_payload: dict[str, Any]) -> dict[str, Any]:
    if not settings.llm_enabled:
        return _fallback_purpose(user_payload.get("filenames", []))
    
    if not settings.llm_api_key:
        logger.warning("No LLM API key configured, using fallback")
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

    try:
        response_data = await _post_chat_completion(settings, headers, body)
    except httpx.HTTPStatusError as exc:
        status_code = exc.response.status_code
        if status_code != 400 or "response_format" not in body:
            raise

        logger.warning(
            "Structured output request rejected by %s %s for model %s; retrying without response_format",
            settings.llm_provider,
            status_code,
            settings.llm_model,
        )
        fallback_body = dict(body)
        fallback_body.pop("response_format", None)
        fallback_body["messages"] = [
            {
                "role": "system",
                "content": (
                    f"{system_prompt}\n\n"
                    "Return only a single valid JSON object and no surrounding markdown."
                ),
            },
            {"role": "user", "content": json.dumps(user_payload)},
        ]
        response_data = await _post_chat_completion(settings, headers, fallback_body)
    
    try:
        content = _parse_llm_response(response_data)
    except (KeyError, ValueError, IndexError) as e:
        logger.error("Failed to parse LLM response: %s, response keys: %s", e, list(response_data.keys()))
        return _fallback_purpose(user_payload.get("filenames", []))
    
    try:
        parsed = _extract_json_object(content)
    except json.JSONDecodeError as e:
        logger.error("Failed to parse LLM response as JSON: %s", e)
        return _fallback_purpose(user_payload.get("filenames", []))
    
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
        # Validate required fields exist in response
        if not isinstance(response, dict) or not all(k in response for k in ("purpose", "confidence", "risk_signals", "decision", "reasoning")):
            logger.warning("LLM response missing required fields, using fallback")
            response = _fallback_purpose(filenames)
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
