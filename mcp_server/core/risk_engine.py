from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import networkx as nx


SENSITIVE_KEYWORDS = {
    "secret",
    "token",
    "password",
    "credential",
    "finance",
    "invoice",
    "payroll",
    "tax",
    "ssn",
    "passport",
    "customer",
    "employee",
    "hr",
    "legal",
    "contract",
    "pii",
    "key",
    "pem",
}

RISKY_EXTENSIONS = {
    ".env",
    ".pem",
    ".key",
    ".p12",
    ".csv",
    ".xlsx",
    ".json",
    ".sql",
    ".db",
    ".bak",
}


def _sigmoid(value: float) -> float:
    return 1.0 / (1.0 + math.exp(-value))


def compute_risk_score(
    path: str,
    graph: nx.Graph,
    metadata: dict[str, Any],
    semantic_summary: dict[str, Any],
    weights: dict[str, float],
    centrality: dict[str, float] | None = None,
) -> dict[str, Any]:
    node = graph.nodes[path]
    path_obj = Path(path)
    name_text = path_obj.name.lower()
    keyword_hits = sorted(keyword for keyword in SENSITIVE_KEYWORDS if keyword in name_text)
    keyword_signal = min(len(keyword_hits) / 4.0, 1.0)

    ext_signal = 0.35 if path_obj.suffix.lower() in RISKY_EXTENSIONS else 0.0
    permission_signal = 0.3 if str(metadata.get("permissions", "")).endswith(("6", "7")) else 0.0
    size = float(metadata.get("size", 0))
    size_signal = 0.3 if size > 10_000_000 else 0.15 if size > 1_000_000 else 0.0
    metadata_signal = min(permission_signal + size_signal + ext_signal, 1.0)

    graph_score = 0.0
    if centrality and path in centrality:
        graph_score = min(centrality[path] * 10, 1.0)
    if graph.degree(path) > 6:
        graph_score = min(graph_score + 0.2, 1.0)

    semantic_signal = min(
        float(semantic_summary.get("confidence", 0.0)) * 0.7
        + min(len(semantic_summary.get("risk_signals", [])) * 0.1, 0.3),
        1.0,
    )

    weighted_sum = (
        keyword_signal * weights.get("keyword", 0.35)
        + semantic_signal * weights.get("semantic", 0.25)
        + graph_score * weights.get("graph", 0.2)
        + metadata_signal * weights.get("metadata", 0.2)
    )
    score = _sigmoid((weighted_sum - 0.45) * 5)

    factors: list[str] = []
    if keyword_hits:
        factors.append(f"Filename keywords: {', '.join(keyword_hits)}")
    if semantic_summary.get("risk_signals"):
        factors.append("Semantic signals: " + ", ".join(semantic_summary["risk_signals"]))
    if graph_score >= 0.25:
        factors.append(f"Graph centrality elevated ({graph_score:.2f})")
    if metadata_signal > 0:
        factors.append(
            f"Metadata signals: extension={path_obj.suffix or 'none'}, permissions={metadata.get('permissions')}, size={int(size)}"
        )
    if node.get("depth", 0) <= 2:
        factors.append("Shallow path depth increases exposure likelihood")

    return {
        "risk_score": round(score, 4),
        "factors": factors,
        "components": {
            "keyword": round(keyword_signal, 4),
            "semantic": round(semantic_signal, 4),
            "graph": round(graph_score, 4),
            "metadata": round(metadata_signal, 4),
        },
    }


def rank_high_risk_files(
    scored_files: list[dict[str, Any]],
    min_percent: float,
    max_percent: float,
) -> list[dict[str, Any]]:
    if not scored_files:
        return []
    sorted_items = sorted(scored_files, key=lambda item: item["risk_score"], reverse=True)
    max_pick = max(1, math.ceil(len(sorted_items) * max_percent))
    min_pick = max(1, math.ceil(len(sorted_items) * min_percent))
    dynamic_pick = max(min_pick, min(max_pick, math.ceil(len(sorted_items) * 0.05)))
    return sorted_items[:dynamic_pick]
