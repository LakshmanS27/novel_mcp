from __future__ import annotations


def normalize_openai_base_url(base_url: str) -> str:
    """Normalize OpenAI-compatible base URLs to the API root.

    Some providers expose docs using a full `/chat/completions` endpoint, while
    OpenAI-compatible SDKs expect the API root and append that path
    themselves. Accept either form and normalize to the root.
    """
    normalized = base_url.strip().rstrip("/")
    suffix = "/chat/completions"
    if normalized.endswith(suffix):
        normalized = normalized[: -len(suffix)]
    return normalized
