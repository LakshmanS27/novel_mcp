from __future__ import annotations

import asyncio
import json
import shutil
from pathlib import Path
from typing import Any

from mcp_server.utils.logger import get_logger


logger = get_logger(__name__)


class LinuxCommandError(RuntimeError):
    """Raised when a required Linux command fails."""


def _require_command(command: str) -> str:
    resolved = shutil.which(command)
    if not resolved:
        raise LinuxCommandError(f"Required command '{command}' is not installed or not on PATH.")
    return resolved


async def _run_command(*args: str, timeout: float = 30.0) -> str:
    try:
        process = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
    except FileNotFoundError as exc:
        raise LinuxCommandError(f"Command not found: {args[0]}") from exc
    except asyncio.TimeoutError as exc:
        raise LinuxCommandError(f"Command timed out: {' '.join(args)}") from exc
    if process.returncode != 0:
        raise LinuxCommandError(stderr.decode().strip() or f"Command failed: {' '.join(args)}")
    return stdout.decode().strip()


def _annotate_tree_paths(node: dict[str, Any], parent_path: str | None = None) -> dict[str, Any]:
    name = node.get("name", "")
    if parent_path:
        path = str(Path(parent_path) / name)
    else:
        path = name
    node["path"] = path
    for child in node.get("contents", []) or []:
        _annotate_tree_paths(child, path)
    return node


async def run_tree(path: str | Path, depth: int = 3) -> list[dict[str, Any]]:
    tree_bin = _require_command("tree")
    target = Path(path).resolve()
    depth = max(1, depth)
    output = await _run_command(
        tree_bin,
        "-J",
        "-L",
        str(depth),
        "--noreport",
        str(target),
        timeout=60.0,
    )
    try:
        parsed = json.loads(output)
    except json.JSONDecodeError as exc:
        raise LinuxCommandError("tree returned invalid JSON output.") from exc
    if not isinstance(parsed, list):
        raise LinuxCommandError("tree output JSON did not contain a list root.")
    annotated: list[dict[str, Any]] = []
    for item in parsed:
        if isinstance(item, dict):
            item["name"] = str(target) if item.get("name") == target.name else item.get("name", str(target))
            annotated.append(_annotate_tree_paths(item))
    logger.info("tree parsed for %s with %s root entries", target, len(annotated))
    return annotated


async def get_stat(path: str | Path) -> dict[str, Any]:
    stat_bin = _require_command("stat")
    target = Path(path).resolve()
    fmt = "%n|%s|%a|%U|%G|%Y|%X|%W|%F"
    output = await _run_command(stat_bin, "-c", fmt, str(target), timeout=20.0)
    parts = output.split("|")
    if len(parts) != 9:
        raise LinuxCommandError("Unexpected stat output format.")
    created_raw = int(parts[7])
    return {
        "path": parts[0],
        "size": int(parts[1]),
        "permissions": parts[2],
        "owner": parts[3],
        "group": parts[4],
        "modified_ts": int(parts[5]),
        "accessed_ts": int(parts[6]),
        "created_ts": created_raw if created_raw >= 0 else None,
        "kind": parts[8],
    }


async def get_disk_usage(path: str | Path) -> dict[str, Any]:
    du_bin = _require_command("du")
    target = Path(path).resolve()
    output = await _run_command(du_bin, "-sh", str(target), timeout=20.0)
    size_human, _, raw_path = output.partition("\t")
    return {
        "path": raw_path or str(target),
        "human_size": size_human,
    }
