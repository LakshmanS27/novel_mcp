from __future__ import annotations

import asyncio
import os
import re
from pathlib import Path
from typing import Any

import aiofiles

from mcp_server.server.config import Settings


PATTERNS = {
    "email": re.compile(rb"\b[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[A-Za-z]{2,}\b"),
    "pan": re.compile(rb"\b(?:\d[ -]*?){13,19}\b"),
    "api_key": re.compile(rb"\b(?:sk|rk|pk)_[A-Za-z0-9]{16,}\b"),
    "aws_key": re.compile(rb"\bAKIA[0-9A-Z]{16}\b"),
}

KEYWORD_PATTERNS = [
    b"password",
    b"secret",
    b"api_key",
    b"private key",
    b"ssn",
    b"social security",
]


async def _scan_file(target: Path, settings: Settings) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    bytes_read = 0
    async with aiofiles.open(target, "rb") as handle:
        while True:
            chunk = await handle.read(settings.scan_chunk_size)
            if not chunk:
                break
            bytes_read += len(chunk)
            for label, pattern in PATTERNS.items():
                for match in pattern.finditer(chunk):
                    findings.append(
                        {
                            "type": label,
                            "match_preview": match.group(0)[:48].decode("utf-8", errors="ignore"),
                        }
                    )
            lowered = chunk.lower()
            for keyword in KEYWORD_PATTERNS:
                if keyword in lowered:
                    findings.append(
                        {
                            "type": "keyword",
                            "match_preview": keyword.decode("utf-8"),
                        }
                    )
            if bytes_read >= settings.max_file_read_bytes:
                break

    deduped: list[dict[str, Any]] = []
    seen = set()
    for finding in findings:
        key = (finding["type"], finding["match_preview"])
        if key not in seen:
            seen.add(key)
            deduped.append(finding)
    return {
        "path": str(target),
        "findings": deduped,
        "bytes_read": bytes_read,
        "truncated": bytes_read >= settings.max_file_read_bytes,
    }


async def scan_file_sensitive_data(path: str | Path, settings: Settings) -> dict[str, Any]:
    target = Path(path).resolve()
    if target.is_dir():
        raise IsADirectoryError(f"{target} is a directory. Use recursive directory scanning instead.")
    try:
        return await _scan_file(target, settings)
    except UnicodeDecodeError:
        return {"path": str(target), "findings": [], "bytes_read": 0, "truncated": False}


async def scan_directory_sensitive_data(path: str | Path, settings: Settings) -> dict[str, Any]:
    root = Path(path).resolve()
    if not root.is_dir():
        raise NotADirectoryError(f"{root} is not a directory.")

    def collect_files() -> list[Path]:
        file_paths: list[Path] = []
        for current_root, _, filenames in os.walk(root):
            for filename in filenames:
                file_paths.append(Path(current_root) / filename)
        return file_paths

    file_paths = await asyncio.to_thread(collect_files)
    semaphore = asyncio.Semaphore(max(4, min(settings.stat_concurrency, 64)))

    async def worker(file_path: Path) -> dict[str, Any]:
        async with semaphore:
            try:
                return await _scan_file(file_path, settings)
            except (UnicodeDecodeError, OSError):
                return {"path": str(file_path), "findings": [], "bytes_read": 0, "truncated": False}

    results = await asyncio.gather(*(worker(file_path) for file_path in file_paths))
    matched_files = [result for result in results if result["findings"]]
    total_findings = sum(len(result["findings"]) for result in matched_files)
    return {
        "path": str(root),
        "total_files_scanned": len(file_paths),
        "matched_files": len(matched_files),
        "total_findings": total_findings,
        "findings_by_file": matched_files,
    }


async def validate_compliance(scan_result: dict[str, Any]) -> dict[str, Any]:
    findings = scan_result.get("findings", [])
    severe = [item for item in findings if item["type"] in {"api_key", "aws_key", "pan"}]
    status = "NON_COMPLIANT" if severe else "REVIEW" if findings else "COMPLIANT"
    return {
        "path": scan_result.get("path"),
        "status": status,
        "finding_count": len(findings),
        "severe_findings": severe,
    }
