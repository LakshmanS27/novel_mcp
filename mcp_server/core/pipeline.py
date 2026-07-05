from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import networkx as nx

from mcp_server.core.feedback import FeedbackStore
from mcp_server.core.graph_builder import build_filesystem_graph
from mcp_server.core.risk_engine import compute_risk_score, rank_high_risk_files
from mcp_server.core.scanner import scan_file_sensitive_data, validate_compliance
from mcp_server.core.semantic_inference import explain_risk_with_llm, infer_directory_purpose
from mcp_server.server.config import Settings
from mcp_server.utils.file_utils import extract_file_candidates
from mcp_server.utils.linux_utils import run_tree


async def run_full_analysis(root_path: str | Path, depth: int, settings: Settings) -> dict[str, Any]:
    root = Path(root_path).resolve()
    tree_data = await run_tree(root, depth=depth)
    graph, metadata_map = await build_filesystem_graph(root, tree_data, settings)
    filenames = [Path(path).name for path in extract_file_candidates(tree_data)]
    semantic_summary = await infer_directory_purpose(tree_data, filenames, settings)
    centrality = nx.degree_centrality(graph) if graph.number_of_nodes() else {}
    weights = await FeedbackStore(settings.db_path).get_weights()

    file_paths = [path for path, meta in metadata_map.items() if meta.get("kind") != "directory"]
    scored_files: list[dict[str, Any]] = []
    for file_path in file_paths:
        scored = compute_risk_score(file_path, graph, metadata_map[file_path], semantic_summary, weights, centrality)
        scored_files.append({"path": file_path, **scored})

    high_risk = rank_high_risk_files(scored_files, settings.min_scan_percent, settings.max_scan_percent)
    scan_results = await asyncio.gather(*(scan_file_sensitive_data(item["path"], settings) for item in high_risk))

    findings: list[dict[str, Any]] = []
    for item, scan_result in zip(high_risk, scan_results, strict=False):
        explanation = await explain_risk_with_llm(
            item["path"],
            item["risk_score"],
            item["factors"],
            semantic_summary,
            settings,
        )
        compliance = await validate_compliance(scan_result)
        findings.append(
            {
                "path": item["path"],
                "risk_score": item["risk_score"],
                "factors": item["factors"],
                "scan_findings": scan_result["findings"],
                "compliance": compliance["status"],
                "explanation": explanation["explanation"],
            }
        )

    total_files = len(file_paths)
    scanned_files = len(high_risk)
    return {
        "total_files": total_files,
        "scanned_files": scanned_files,
        "reduction_percent": round((1 - (scanned_files / total_files)) * 100, 2) if total_files else 0.0,
        "high_risk_files": high_risk,
        "findings": findings,
    }
