from __future__ import annotations

import asyncio
import os
from collections import Counter
from pathlib import Path
from typing import Any

from mcp_server.server.config import Settings


LOW_VALUE_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".bmp",
    ".webp",
    ".svg",
    ".mp4",
    ".mov",
    ".avi",
    ".mkv",
    ".mp3",
    ".wav",
    ".zip",
    ".tar",
    ".gz",
    ".7z",
    ".rar",
    ".exe",
    ".dll",
    ".so",
    ".dylib",
    ".pyc",
    ".class",
    ".o",
    ".a",
    ".bin",
    ".iso",
}

HIGH_VALUE_TEXT_EXTENSIONS = {
    ".env",
    ".txt",
    ".md",
    ".json",
    ".yaml",
    ".yml",
    ".ini",
    ".cfg",
    ".conf",
    ".csv",
    ".log",
    ".xml",
    ".toml",
    ".properties",
    ".sql",
    ".pem",
    ".key",
    ".crt",
    ".pub",
}

PARSER_NEEDED_EXTENSIONS = {
    ".docx",
    ".xlsx",
    ".pptx",
    ".pdf",
}

MODE_KEYWORDS = {
    "credentials": {
        "secret",
        "password",
        "token",
        "credential",
        "key",
        "private",
        "auth",
        "vault",
        "config",
        "env",
        "pem",
    },
    "pii": {
        "customer",
        "employee",
        "hr",
        "aadhaar",
        "aadhar",
        "ssn",
        "passport",
        "pan",
        "identity",
        "payroll",
        "resume",
        "personal",
    },
    "broad": {
        "secret",
        "password",
        "token",
        "credential",
        "key",
        "private",
        "auth",
        "vault",
        "customer",
        "employee",
        "hr",
        "aadhaar",
        "aadhar",
        "ssn",
        "passport",
        "pan",
        "identity",
        "payroll",
        "resume",
        "finance",
        "legal",
        "invoice",
        "backup",
        "export",
    },
}


def _classify_extension(path: Path) -> tuple[str, float, list[str]]:
    suffix = path.suffix.lower()
    reasons: list[str] = []
    if suffix in LOW_VALUE_EXTENSIONS:
        return "excluded_low_value", -1.0, [f"low-value extension {suffix}"]
    if suffix in HIGH_VALUE_TEXT_EXTENSIONS:
        return "high_value_text", 0.6, [f"text-bearing extension {suffix}"]
    if suffix in PARSER_NEEDED_EXTENSIONS:
        return "parser_needed", 0.35, [f"document extension {suffix} likely needs specialized parsing"]
    if not suffix:
        return "unknown", 0.05, ["no extension"]
    return "unknown", 0.1, [f"unclassified extension {suffix}"]


def _keyword_score(path: Path, mode: str) -> tuple[float, list[str]]:
    keywords = MODE_KEYWORDS.get(mode, MODE_KEYWORDS["broad"])
    text = "/".join(part.lower() for part in path.parts)
    hits = sorted(keyword for keyword in keywords if keyword in text)
    if not hits:
        return 0.0, []
    return min(0.1 * len(hits), 0.4), [f"context keywords: {', '.join(hits)}"]


def _size_score(size: int) -> tuple[float, list[str]]:
    if size <= 0:
        return 0.0, []
    if size < 64:
        return -0.05, ["very small file"]
    if size <= 5_000_000:
        return 0.1, ["small-to-medium file size suitable for text scanning"]
    if size <= 50_000_000:
        return 0.02, ["moderate file size"]
    return -0.15, ["very large file"]


def _hidden_penalty(path: Path) -> tuple[float, list[str]]:
    if path.name.startswith(".") and path.suffix.lower() not in {".env", ".pem", ".key"}:
        return 0.02, ["hidden file"]
    return 0.0, []


def _permission_score(mode_bits: int) -> tuple[float, list[str]]:
    other_readable = bool(mode_bits & 0o004)
    group_readable = bool(mode_bits & 0o040)
    if other_readable or group_readable:
        return 0.08, ["broad read permissions"]
    return 0.0, []


def _normalize_score(raw_score: float) -> float:
    return max(0.0, min(raw_score, 1.0))


async def identify_scan_candidates(
    root_path: str | Path,
    mode: str,
    max_candidates: int,
    settings: Settings,
) -> dict[str, Any]:
    root = Path(root_path).resolve()
    if not root.is_dir():
        raise NotADirectoryError(f"{root} is not a directory.")
    normalized_mode = mode if mode in MODE_KEYWORDS else "broad"

    def collect_paths() -> list[Path]:
        file_paths: list[Path] = []
        for current_root, _, filenames in os.walk(root):
            for filename in filenames:
                file_paths.append(Path(current_root) / filename)
        return file_paths

    file_paths = await asyncio.to_thread(collect_paths)
    candidates: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    category_counter: Counter[str] = Counter()

    for file_path in file_paths:
        try:
            stat_result = file_path.stat()
        except OSError:
            excluded.append({"path": str(file_path), "reason": "stat_failed"})
            continue

        category, base_score, reasons = _classify_extension(file_path)
        category_counter[category] += 1
        if category == "excluded_low_value":
            excluded.append({"path": str(file_path), "reason": reasons[0], "category": category})
            continue

        keyword_score, keyword_reasons = _keyword_score(file_path, normalized_mode)
        size_score, size_reasons = _size_score(stat_result.st_size)
        perm_score, perm_reasons = _permission_score(stat_result.st_mode)
        hidden_score, hidden_reasons = _hidden_penalty(file_path)

        raw_score = base_score + keyword_score + size_score + perm_score + hidden_score
        if file_path.name.lower() in {"id_rsa", "id_dsa", ".env", ".npmrc", ".pypirc"}:
            raw_score += 0.25
            reasons.append("well-known secret-bearing filename")

        combined_reasons = reasons + keyword_reasons + size_reasons + perm_reasons + hidden_reasons
        candidates.append(
            {
                "path": str(file_path),
                "score": round(_normalize_score(raw_score), 4),
                "category": category,
                "extension": file_path.suffix.lower(),
                "size": stat_result.st_size,
                "reasons": combined_reasons,
            }
        )

    ranked = sorted(candidates, key=lambda item: item["score"], reverse=True)
    selected = ranked[: max(1, max_candidates)] if ranked else []
    selected_set = {item["path"] for item in selected}
    deferred = [
        {
            "path": item["path"],
            "reason": "below candidate cutoff",
            "category": item["category"],
            "score": item["score"],
        }
        for item in ranked[max_candidates:]
        if item["path"] not in selected_set
    ]

    return {
        "root_path": str(root),
        "mode": normalized_mode,
        "total_files": len(file_paths),
        "candidate_count": len(selected),
        "excluded_count": len(excluded) + len(deferred),
        "candidates": selected,
        "excluded": (excluded + deferred)[:500],
        "summary": {
            "category_counts": dict(category_counter),
            "high_value_text_candidates": sum(1 for item in selected if item["category"] == "high_value_text"),
            "parser_needed_candidates": sum(1 for item in selected if item["category"] == "parser_needed"),
        },
    }
