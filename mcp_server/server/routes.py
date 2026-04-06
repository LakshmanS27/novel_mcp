from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Any

import networkx as nx
from fastapi import APIRouter, Depends, HTTPException

from mcp_server.core.feedback import FeedbackStore
from mcp_server.core.candidate_selector import identify_scan_candidates
from mcp_server.core.graph_builder import build_filesystem_graph
from mcp_server.core.pipeline import run_full_analysis
from mcp_server.core.risk_engine import compute_risk_score
from mcp_server.core.scanner import scan_directory_sensitive_data, scan_file_sensitive_data, validate_compliance
from mcp_server.core.semantic_inference import explain_risk_with_llm, infer_directory_purpose
from mcp_server.server.config import Settings, get_settings
from mcp_server.server.schemas import (
    CandidateRequest,
    CandidateScanRequest,
    CandidateScanResponse,
    CandidateSelectionResponse,
    ComplianceResponse,
    DirectoryScanResponse,
    DirectoryRequest,
    ExplainRiskResponse,
    FeedbackRequest,
    FeedbackResponse,
    FullAnalysisResponse,
    ListDirectoryResponse,
    MetadataResponse,
    PathRequest,
    RiskScoreResponse,
    ScanResponse,
    SemanticResponse,
    TreeResponse,
    UpdateWeightsResponse,
)
from mcp_server.utils.file_utils import ensure_safe_path, extract_file_candidates
from mcp_server.utils.linux_utils import LinuxCommandError, get_disk_usage, get_stat, run_tree
from mcp_server.utils.logger import get_logger


logger = get_logger(__name__)
router = APIRouter()


def get_feedback_store(settings: Settings = Depends(get_settings)) -> FeedbackStore:
    return FeedbackStore(settings.db_path)


async def _list_directory_entries(path: Path) -> list[dict[str, str]]:
    def scan() -> list[dict[str, str]]:
        entries: list[dict[str, str]] = []
        with os.scandir(path) as iterator:
            for entry in iterator:
                entries.append(
                    {
                        "name": entry.name,
                        "path": str(Path(entry.path).resolve()),
                        "entry_type": "directory" if entry.is_dir(follow_symlinks=False) else "file",
                    }
                )
        return sorted(entries, key=lambda item: (item["entry_type"], item["name"].lower()))

    return await asyncio.to_thread(scan)


async def _prepare_context(
    root_path: Path,
    settings: Settings,
) -> tuple[list[dict[str, Any]], nx.Graph, dict[str, dict[str, Any]], dict[str, Any], dict[str, float]]:
    tree_data = await run_tree(root_path, depth=settings.default_tree_depth)
    graph, metadata_map = await build_filesystem_graph(root_path, tree_data, settings)
    filenames = [Path(path).name for path in extract_file_candidates(tree_data)]
    semantic_summary = await infer_directory_purpose(tree_data, filenames, settings)
    centrality = nx.degree_centrality(graph) if graph.number_of_nodes() else {}
    return tree_data, graph, metadata_map, semantic_summary, centrality


@router.post("/list_directory", response_model=ListDirectoryResponse, tags=["filesystem"])
async def list_directory(request: PathRequest) -> ListDirectoryResponse:
    try:
        path = ensure_safe_path(request.path)
        entries = await _list_directory_entries(path)
        return ListDirectoryResponse(path=str(path), entries=entries)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/get_file_metadata", response_model=MetadataResponse, tags=["filesystem"])
async def get_file_metadata(request: PathRequest) -> MetadataResponse:
    try:
        path = ensure_safe_path(request.path)
        metadata = await get_stat(path)
        return MetadataResponse(**metadata)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/get_directory_structure", response_model=TreeResponse, tags=["filesystem"])
async def get_directory_structure(
    request: DirectoryRequest,
    settings: Settings = Depends(get_settings),
) -> TreeResponse:
    try:
        path = ensure_safe_path(request.path)
        depth = min(request.depth, settings.max_tree_depth)
        tree = await run_tree(path, depth=depth)
        return TreeResponse(path=str(path), depth=depth, tree=tree)
    except LinuxCommandError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/infer_directory_purpose", response_model=SemanticResponse, tags=["intelligence"])
async def infer_directory_purpose_route(
    request: DirectoryRequest,
    settings: Settings = Depends(get_settings),
) -> SemanticResponse:
    try:
        path = ensure_safe_path(request.path)
        tree_data = await run_tree(path, depth=min(request.depth, settings.max_tree_depth))
        filenames = [Path(item).name for item in extract_file_candidates(tree_data)]
        semantic = await infer_directory_purpose(tree_data, filenames, settings)
        return SemanticResponse(**semantic)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/compute_risk_score", response_model=RiskScoreResponse, tags=["intelligence"])
async def compute_risk_score_route(
    request: PathRequest,
    settings: Settings = Depends(get_settings),
    feedback_store: FeedbackStore = Depends(get_feedback_store),
) -> RiskScoreResponse:
    try:
        path = ensure_safe_path(request.path)
        parent = path.parent if path.parent.exists() else path
        tree_data, graph, metadata_map, semantic_summary, centrality = await _prepare_context(parent, settings)
        target = str(path)
        if target not in metadata_map:
            metadata_map[target] = await get_stat(path)
            graph.add_node(
                target,
                name=path.name,
                path=target,
                node_type="file",
                depth=len(path.parts),
                file_type=path.suffix.lstrip("."),
                size=metadata_map[target]["size"],
                permissions=metadata_map[target]["permissions"],
                owner=metadata_map[target]["owner"],
            )
        weights = await feedback_store.get_weights()
        scored = compute_risk_score(target, graph, metadata_map[target], semantic_summary, weights, centrality)
        return RiskScoreResponse(path=target, **scored)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/explain_risk", response_model=ExplainRiskResponse, tags=["intelligence"])
async def explain_risk_route(
    request: PathRequest,
    settings: Settings = Depends(get_settings),
    feedback_store: FeedbackStore = Depends(get_feedback_store),
) -> ExplainRiskResponse:
    try:
        path = ensure_safe_path(request.path)
        parent = path.parent if path.parent.exists() else path
        _, graph, metadata_map, semantic_summary, centrality = await _prepare_context(parent, settings)
        target = str(path)
        metadata = metadata_map.get(target) or await get_stat(path)
        if target not in graph:
            graph.add_node(
                target,
                name=path.name,
                path=target,
                node_type="file",
                depth=len(path.parts),
                file_type=path.suffix.lstrip("."),
                size=metadata["size"],
                permissions=metadata["permissions"],
                owner=metadata["owner"],
            )
        weights = await feedback_store.get_weights()
        scored = compute_risk_score(target, graph, metadata, semantic_summary, weights, centrality)
        explanation = await explain_risk_with_llm(
            target,
            scored["risk_score"],
            scored["factors"],
            semantic_summary,
            settings,
        )
        return ExplainRiskResponse(
            path=target,
            risk_score=scored["risk_score"],
            decision=explanation["decision"],
            reasoning=explanation["reasoning"],
            explanation=explanation["explanation"],
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/scan_file_sensitive_data", response_model=ScanResponse, tags=["scanning"])
async def scan_file_sensitive_data_route(
    request: PathRequest,
    settings: Settings = Depends(get_settings),
) -> ScanResponse:
    try:
        path = ensure_safe_path(request.path)
        result = await scan_file_sensitive_data(path, settings)
        return ScanResponse(**result)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/identify_scan_candidates", response_model=CandidateSelectionResponse, tags=["scanning"])
async def identify_scan_candidates_route(
    request: CandidateRequest,
    settings: Settings = Depends(get_settings),
) -> CandidateSelectionResponse:
    try:
        path = ensure_safe_path(request.path)
        result = await identify_scan_candidates(
            path,
            request.mode or settings.default_candidate_mode,
            min(request.max_candidates, settings.max_candidate_files),
            settings,
        )
        return CandidateSelectionResponse(**result)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/scan_candidate_files", response_model=CandidateScanResponse, tags=["scanning"])
async def scan_candidate_files_route(
    request: CandidateScanRequest,
    settings: Settings = Depends(get_settings),
) -> CandidateScanResponse:
    try:
        normalized_paths = [str(ensure_safe_path(path)) for path in request.paths]
        raw_results = await asyncio.gather(
            *(scan_file_sensitive_data(path, settings) for path in normalized_paths)
        )
        compliance_results = await asyncio.gather(
            *(validate_compliance(result) for result in raw_results)
        )
        results = []
        for scan_result, compliance in zip(raw_results, compliance_results, strict=False):
            enriched = dict(scan_result)
            enriched["compliance"] = compliance
            results.append(enriched)
        matched_files = [result for result in results if result["findings"]]
        total_findings = sum(len(result["findings"]) for result in matched_files)
        return CandidateScanResponse(
            requested_paths=normalized_paths,
            scanned_files=len(normalized_paths),
            matched_files=len(matched_files),
            total_findings=total_findings,
            results=results,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/scan_directory_sensitive_data", response_model=DirectoryScanResponse, tags=["scanning"])
async def scan_directory_sensitive_data_route(
    request: PathRequest,
    settings: Settings = Depends(get_settings),
) -> DirectoryScanResponse:
    try:
        path = ensure_safe_path(request.path)
        result = await scan_directory_sensitive_data(path, settings)
        return DirectoryScanResponse(**result)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/validate_compliance", response_model=ComplianceResponse, tags=["scanning"])
async def validate_compliance_route(
    request: PathRequest,
    settings: Settings = Depends(get_settings),
) -> ComplianceResponse:
    try:
        path = ensure_safe_path(request.path)
        result = await scan_file_sensitive_data(path, settings)
        compliance = await validate_compliance(result)
        return ComplianceResponse(**compliance)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/submit_feedback", response_model=FeedbackResponse, tags=["feedback"])
async def submit_feedback_route(
    request: FeedbackRequest,
    feedback_store: FeedbackStore = Depends(get_feedback_store),
) -> FeedbackResponse:
    try:
        path = ensure_safe_path(request.path)
        result = await feedback_store.submit_feedback(str(path), request.label, request.notes)
        return FeedbackResponse(**result)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/update_risk_model", response_model=UpdateWeightsResponse, tags=["feedback"])
async def update_risk_model_route(
    feedback_store: FeedbackStore = Depends(get_feedback_store),
) -> UpdateWeightsResponse:
    try:
        weights = await feedback_store.update_risk_model()
        return UpdateWeightsResponse(weights=weights)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/run_full_analysis", response_model=FullAnalysisResponse, tags=["pipeline"])
async def run_full_analysis_route(
    request: DirectoryRequest,
    settings: Settings = Depends(get_settings),
) -> FullAnalysisResponse:
    try:
        root_path = ensure_safe_path(request.path)
        result = await run_full_analysis(root_path, min(request.depth, settings.max_tree_depth), settings)
        return FullAnalysisResponse(**result)
    except Exception as exc:
        logger.exception("full analysis failed")
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/get_disk_usage", tags=["filesystem"])
async def get_disk_usage_route(request: PathRequest) -> dict[str, Any]:
    try:
        path = ensure_safe_path(request.path)
        return await get_disk_usage(path)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
