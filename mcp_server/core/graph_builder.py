from __future__ import annotations

import asyncio
from collections import defaultdict
from pathlib import Path
from typing import Any

import networkx as nx

from mcp_server.server.config import Settings
from mcp_server.utils.file_utils import depth_from_root, guess_file_type
from mcp_server.utils.linux_utils import get_stat


async def build_filesystem_graph(
    root_path: str | Path,
    tree_data: list[dict[str, Any]],
    settings: Settings,
) -> tuple[nx.Graph, dict[str, dict[str, Any]]]:
    root = Path(root_path).resolve()
    graph = nx.Graph()
    semaphore = asyncio.Semaphore(settings.stat_concurrency)
    metadata_map: dict[str, dict[str, Any]] = {}
    tree_nodes: list[dict[str, Any]] = []

    def walk(node: dict[str, Any], parent: str | None = None) -> None:
        tree_nodes.append(
            {
                "path": node["path"],
                "name": node["name"],
                "type": node.get("type", "unknown"),
                "parent": parent,
            }
        )
        for child in node.get("contents", []) or []:
            walk(child, node["path"])

    for item in tree_data:
        walk(item)

    async def fetch_metadata(node_path: str) -> None:
        async with semaphore:
            try:
                metadata_map[node_path] = await get_stat(node_path)
            except Exception:
                metadata_map[node_path] = {
                    "path": node_path,
                    "size": 0,
                    "permissions": "000",
                    "owner": "unknown",
                    "group": "unknown",
                    "modified_ts": 0,
                    "accessed_ts": 0,
                    "created_ts": None,
                    "kind": "unknown",
                }

    await asyncio.gather(*(fetch_metadata(node["path"]) for node in tree_nodes))

    similarity_buckets: dict[str, list[str]] = defaultdict(list)
    for node in tree_nodes:
        node_path = Path(node["path"])
        metadata = metadata_map[node["path"]]
        file_type = "directory" if node["type"] == "directory" else guess_file_type(node_path)
        graph.add_node(
            node["path"],
            name=node["name"],
            path=node["path"],
            node_type=node["type"],
            depth=depth_from_root(root, node_path),
            file_type=file_type,
            size=metadata["size"],
            permissions=metadata["permissions"],
            owner=metadata["owner"],
        )
        if node["parent"]:
            graph.add_edge(node["parent"], node["path"], relation="parent-child")
        if node["type"] != "directory":
            stem = node_path.stem.lower()[:48]
            extension = node_path.suffix.lower()
            bucket_key = f"{extension}:{stem[:8]}"
            similarity_buckets[bucket_key].append(node["path"])

    for bucket_paths in similarity_buckets.values():
        limited = bucket_paths[: settings.similarity_bucket_limit]
        for index, source in enumerate(limited):
            source_stem = Path(source).stem.lower()
            for target in limited[index + 1 :]:
                target_stem = Path(target).stem.lower()
                overlap = len(set(source_stem.split("_")) & set(target_stem.split("_")))
                if overlap > 0 or source_stem[:4] == target_stem[:4]:
                    graph.add_edge(source, target, relation="name-similarity")

    return graph, metadata_map
