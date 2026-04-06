from __future__ import annotations

import os
from pathlib import Path
from typing import Any


ALLOWED_ROOT_PREFIXES = ("/home/", "/mnt/")


def normalize_path(path_str: str) -> Path:
    path = Path(path_str).expanduser().resolve()
    return path


def is_supported_path(path: Path) -> bool:
    text = str(path)
    return path.is_absolute() and (
        text == "/home"
        or text.startswith(ALLOWED_ROOT_PREFIXES)
        or text == "/mnt"
    )


def ensure_safe_path(path_str: str) -> Path:
    path = normalize_path(path_str)
    if not is_supported_path(path):
        raise ValueError("Only Linux and WSL absolute paths under /home or /mnt are supported.")
    return path


def guess_file_type(path: Path) -> str:
    if path.is_dir():
        return "directory"
    suffix = path.suffix.lower()
    if not suffix:
        return "unknown"
    return suffix.lstrip(".")


def depth_from_root(root: Path, node_path: Path) -> int:
    try:
        return len(node_path.relative_to(root).parts)
    except ValueError:
        return len(node_path.parts)


def flatten_tree_nodes(tree_data: list[dict[str, Any]] | dict[str, Any]) -> list[dict[str, Any]]:
    roots = tree_data if isinstance(tree_data, list) else [tree_data]
    results: list[dict[str, Any]] = []

    def visit(node: dict[str, Any], parent: str | None) -> None:
        current = {
            "name": node.get("name", ""),
            "type": node.get("type", "unknown"),
            "path": node.get("path", ""),
            "parent": parent,
            "contents_count": len(node.get("contents", []) or []),
        }
        results.append(current)
        for child in node.get("contents", []) or []:
            visit(child, current["path"])

    for root in roots:
        visit(root, None)
    return results


def extract_file_candidates(tree_data: list[dict[str, Any]] | dict[str, Any]) -> list[str]:
    return [
        node["path"]
        for node in flatten_tree_nodes(tree_data)
        if node["type"] != "directory"
    ]


def relative_display(root: Path, path: Path) -> str:
    try:
        return os.fspath(path.relative_to(root))
    except ValueError:
        return os.fspath(path)
