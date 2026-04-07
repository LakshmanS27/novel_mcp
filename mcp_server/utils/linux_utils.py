from __future__ import annotations

import asyncio
import json
import os
import platform
import shutil
from pathlib import Path
from typing import Any

from mcp_server.utils.logger import get_logger


logger = get_logger(__name__)

PLATFORM = platform.system()


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


def _walk_directory_py(root: Path, max_depth: int) -> dict[str, Any]:
    """Pure-Python directory walker that produces tree-compatible output."""

    def _build(current: Path, current_depth: int) -> dict[str, Any]:
        node: dict[str, Any] = {"name": current.name or str(current), "path": str(current)}
        if current.is_dir():
            node["type"] = "directory"
            if current_depth < max_depth:
                children: list[dict[str, Any]] = []
                try:
                    for entry in sorted(current.iterdir(), key=lambda p: p.name.lower()):
                        if entry.name.startswith(".git") and entry.is_dir():
                            continue
                        if entry.name in ("node_modules", "__pycache__", ".venv", "venv"):
                            continue
                        children.append(_build(entry, current_depth + 1))
                except PermissionError:
                    pass
                node["contents"] = children
        else:
            node["type"] = "file"
        return node

    return _build(root, 0)


async def run_tree(path: str | Path, depth: int = 3) -> list[dict[str, Any]]:
    target = Path(path).resolve()
    depth = max(1, depth)
    tree_bin = shutil.which("tree")

    if tree_bin:
        try:
            output = await _run_command(
                tree_bin, "-J", "-L", str(depth), "--noreport", str(target),
                timeout=60.0,
            )
            parsed = json.loads(output)
            if isinstance(parsed, list):
                annotated: list[dict[str, Any]] = []
                for item in parsed:
                    if isinstance(item, dict):
                        item["name"] = str(target) if item.get("name") == target.name else item.get("name", str(target))
                        annotated.append(_annotate_tree_paths(item))
                logger.info("tree parsed for %s with %s root entries", target, len(annotated))
                return annotated
        except (LinuxCommandError, json.JSONDecodeError):
            logger.info("tree -J failed, falling back to Python walker")

    root_node = await asyncio.to_thread(_walk_directory_py, target, depth)
    root_node["name"] = str(target)
    annotated_node = _annotate_tree_paths(root_node)
    logger.info("python walker for %s", target)
    return [annotated_node]


async def get_stat(path: str | Path) -> dict[str, Any]:
    target = Path(path).resolve()

    if PLATFORM == "Darwin":
        return await _get_stat_python(target)

    stat_bin = _require_command("stat")
    fmt = "%n|%s|%a|%U|%G|%Y|%X|%W|%F"
    try:
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
    except LinuxCommandError:
        return await _get_stat_python(target)


async def _get_stat_python(target: Path) -> dict[str, Any]:
    """Cross-platform stat using Python's os.stat."""

    def _do_stat() -> dict[str, Any]:
        st = target.stat()
        import pwd
        import grp
        try:
            owner = pwd.getpwuid(st.st_uid).pw_name
        except (KeyError, ImportError):
            owner = str(st.st_uid)
        try:
            group = grp.getgrgid(st.st_gid).gr_name
        except (KeyError, ImportError):
            group = str(st.st_gid)

        kind = "regular file"
        if target.is_dir():
            kind = "directory"
        elif target.is_symlink():
            kind = "symbolic link"

        return {
            "path": str(target),
            "size": st.st_size,
            "permissions": oct(st.st_mode)[-3:],
            "owner": owner,
            "group": group,
            "modified_ts": int(st.st_mtime),
            "accessed_ts": int(st.st_atime),
            "created_ts": int(st.st_birthtime) if hasattr(st, "st_birthtime") else None,
            "kind": kind,
        }

    return await asyncio.to_thread(_do_stat)


async def get_disk_usage(path: str | Path) -> dict[str, Any]:
    du_bin = _require_command("du")
    target = Path(path).resolve()
    output = await _run_command(du_bin, "-sh", str(target), timeout=20.0)
    size_human, _, raw_path = output.partition("\t")
    return {
        "path": raw_path or str(target),
        "human_size": size_human,
    }
