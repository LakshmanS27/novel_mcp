from __future__ import annotations

import asyncio
import os
import re
from pathlib import Path
from typing import Any

import aiofiles

from mcp_server.server.config import Settings
from mcp_server.core.validators import luhn_check, verhoeff_check


# ---------------------------------------------------------------------------
# Regex patterns
# ---------------------------------------------------------------------------

PATTERNS = {
    # Email Address
    "email": re.compile(
        rb"\b[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[A-Za-z]{2,}\b"
    ),

    # Credit/Debit Card (13–19 digits with optional spaces or hyphens)
    # NOTE: Validate with Luhn algorithm after regex match.
    "credit_card": re.compile(
        rb"\b(?:\d{4}[- ]?){3}\d{4}\b|\b\d{13,19}\b"
    ),

    # OpenAI / Generic API Keys
    "api_key": re.compile(
        rb"\b(?:sk|pk|rk)[-_][A-Za-z0-9_-]{20,}\b"
    ),

    # AWS Access Key ID
    "aws_key": re.compile(
        rb"\b(?:AKIA|ASIA|AIDA|AGPA)[A-Z0-9]{16}\b"
    ),

    # Indian PAN Number. The 4th character is a holder-category code
    # restricted to a fixed set of letters (ABCFGHLJPT), which narrows
    # this considerably versus matching any 5-letter/4-digit/1-letter run.
    "indian_pan": re.compile(
        rb"\b[A-Z]{3}[ABCFGHLJPT][A-Z][0-9]{4}[A-Z]\b"
    ),

    # FIX 2 — Tightened Aadhaar regex (spaces-aware, less greedy)
    # NOTE: Validate with Verhoeff algorithm after regex match.
    "aadhaar": re.compile(
        rb"\b[2-9]\d{3}\s?\d{4}\s?\d{4}\b"
    ),

    # JWT Token
    "jwt": re.compile(
        rb"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b"
    ),

    # Private Keys. Real headers carry an algorithm qualifier before
    # "PRIVATE KEY" (e.g. "RSA PRIVATE KEY", "OPENSSH PRIVATE KEY",
    # "EC PRIVATE KEY"), so match zero-or-more leading qualifier words
    # rather than assuming a single alternative directly precedes "KEY".
    "private_key": re.compile(
        rb"-----BEGIN (?:[A-Z0-9]+ )*PRIVATE KEY-----"
    ),

    # Password Assignments
    "password": re.compile(
        rb"(?i)\b(password|passwd|pwd)\b\s*[:=]\s*\S+"
    ),

    # Secret / Token Assignments
    "secret": re.compile(
        rb"(?i)\b(secret|token|api[_-]?key|client[_-]?secret)\b\s*[:=]\s*\S+"
    ),
}

# FIX 4 — Keywords already covered by PATTERNS above; skip to avoid double-counting
_KEYWORD_COVERED_BY_PATTERN: frozenset[bytes] = frozenset({
    b"password",
    b"passwd",
    b"pwd",
    b"secret",
    b"api_key",
    b"apikey",
    b"api-key",
    b"private_key",
    b"private key",
})

KEYWORD_PATTERNS: list[bytes] = [
    b"password",
    b"passwd",
    b"pwd",

    b"secret",
    b"client_secret",
    b"clientsecret",

    b"api_key",
    b"apikey",
    b"api-key",

    b"access_token",
    b"refresh_token",
    b"bearer",

    b"private_key",
    b"private key",
    b"ssh-rsa",
    b"-----begin private key-----",

    b"aws_access_key_id",
    b"aws_secret_access_key",

    b"db_password",
    b"database_url",

    b".env",
]


# ---------------------------------------------------------------------------
# Core file scanner
# ---------------------------------------------------------------------------

async def _scan_file(target: Path, settings: Settings) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    bytes_read = 0

    # FIX 1 — carry last 64 bytes of each chunk into the next
    # so secrets that straddle a chunk boundary are not missed.
    leftover = b""

    async with aiofiles.open(target, "rb") as handle:
        while True:
            raw_chunk = await handle.read(settings.scan_chunk_size)
            if not raw_chunk:
                break

            chunk = leftover + raw_chunk
            leftover = chunk[-64:]          # tail carried to next iteration
            bytes_read += len(raw_chunk)    # count only new bytes

            # --- regex patterns ---
            pattern_types_matched: set[str] = set()

            for label, pattern in PATTERNS.items():
                for match in pattern.finditer(chunk):
                    value = match.group(0).decode("utf-8", errors="ignore")

                    # Validate Credit Card with Luhn
                    if label == "credit_card":
                        card = value.replace(" ", "").replace("-", "")
                        if not luhn_check(card):
                            continue

                    # Validate Aadhaar with Verhoeff
                    elif label == "aadhaar":
                        clean = value.replace(" ", "")
                        if not verhoeff_check(clean):
                            continue

                    pattern_types_matched.add(label)
                    findings.append(
                        {
                            "type": label,
                            "match_preview": value[:48],
                        }
                    )

            # FIX 4 — keyword scan: skip keywords whose type is already
            # covered by a regex pattern match to avoid double-counting.
            lowered = chunk.lower()
            for keyword in KEYWORD_PATTERNS:
                if keyword in _KEYWORD_COVERED_BY_PATTERN:
                    # Only emit keyword finding if the regex didn't fire
                    covered_type = (
                        "password" if keyword in {b"password", b"passwd", b"pwd"} else
                        "secret"   if keyword in {b"secret"} else
                        "api_key"  if keyword in {b"api_key", b"apikey", b"api-key"} else
                        "private_key"
                    )
                    if covered_type in pattern_types_matched:
                        continue

                if keyword in lowered:
                    findings.append(
                        {
                            "type": "keyword",
                            "match_preview": keyword.decode("utf-8"),
                        }
                    )

            if bytes_read >= settings.max_file_read_bytes:
                break

    # Deduplicate by (type, preview) key
    deduped: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
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


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def scan_file_sensitive_data(
    path: str | Path,
    settings: Settings,
) -> dict[str, Any]:
    target = Path(path).resolve()
    if target.is_dir():
        raise IsADirectoryError(
            f"{target} is a directory. Use recursive directory scanning instead."
        )
    try:
        return await _scan_file(target, settings)
    except UnicodeDecodeError:
        return {"path": str(target), "findings": [], "bytes_read": 0, "truncated": False}


async def scan_directory_sensitive_data(
    path: str | Path,
    settings: Settings,
) -> dict[str, Any]:
    root = Path(path).resolve()
    if not root.is_dir():
        raise NotADirectoryError(f"{root} is not a directory.")

    def collect_files() -> list[Path]:
        file_paths: list[Path] = []
        for current_root, dirnames, filenames in os.walk(root, followlinks=False):
            dirnames[:] = [d for d in dirnames if not (Path(current_root) / d).is_symlink()]
            for filename in filenames:
                candidate = Path(current_root) / filename
                if candidate.is_symlink():
                    continue
                file_paths.append(candidate)
        return file_paths

    file_paths = await asyncio.to_thread(collect_files)
    semaphore = asyncio.Semaphore(max(4, min(settings.stat_concurrency, 64)))

    async def worker(file_path: Path) -> dict[str, Any]:
        async with semaphore:
            try:
                return await _scan_file(file_path, settings)
            except (UnicodeDecodeError, OSError):
                return {
                    "path": str(file_path),
                    "findings": [],
                    "bytes_read": 0,
                    "truncated": False,
                }

    results = await asyncio.gather(*(worker(fp) for fp in file_paths))
    matched_files = [r for r in results if r["findings"]]
    total_findings = sum(len(r["findings"]) for r in matched_files)

    return {
        "path": str(root),
        "total_files_scanned": len(file_paths),
        "matched_files": len(matched_files),
        "total_findings": total_findings,
        "findings_by_file": matched_files,
    }


async def validate_compliance(scan_result: dict[str, Any]) -> dict[str, Any]:
    # FIX 3 — handle both single-file shape {"findings": [...]}
    # and directory shape {"findings_by_file": [...]}
    if "findings_by_file" in scan_result:
        all_findings: list[dict[str, Any]] = []
        for file_result in scan_result["findings_by_file"]:
            all_findings.extend(file_result.get("findings", []))
    else:
        all_findings = scan_result.get("findings", [])

    # FIX 5 — added "jwt" to the severe set
    _SEVERE_TYPES = {
        "api_key",
        "aws_key",
        "credit_card",
        "indian_pan",
        "aadhaar",
        "private_key",
        "jwt",          # ← new
    }

    severe = [item for item in all_findings if item["type"] in _SEVERE_TYPES]
    status = "NON_COMPLIANT" if severe else "REVIEW" if all_findings else "COMPLIANT"

    return {
        "path": scan_result.get("path"),
        "status": status,
        "finding_count": len(all_findings),
        "severe_findings": severe,
    }