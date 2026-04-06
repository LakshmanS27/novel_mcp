from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class PathRequest(BaseModel):
    path: str = Field(..., description="Absolute Linux or WSL path.")


class DirectoryRequest(PathRequest):
    depth: int = Field(default=3, ge=1, le=8)


class CandidateRequest(PathRequest):
    mode: Literal["credentials", "pii", "broad"] = "broad"
    max_candidates: int = Field(default=100, ge=1, le=1000)


class CandidateScanRequest(BaseModel):
    paths: list[str] = Field(..., min_length=1, max_length=1000)


class FeedbackRequest(BaseModel):
    path: str
    label: Literal["TP", "FP"]
    notes: str | None = None


class MetadataResponse(BaseModel):
    path: str
    size: int
    permissions: str
    owner: str
    group: str
    modified_ts: int
    accessed_ts: int
    created_ts: int | None
    kind: str


class DirectoryEntry(BaseModel):
    name: str
    path: str
    entry_type: str


class ListDirectoryResponse(BaseModel):
    path: str
    entries: list[DirectoryEntry]


class TreeResponse(BaseModel):
    path: str
    depth: int
    tree: list[dict[str, Any]]


class SemanticResponse(BaseModel):
    purpose: str
    confidence: float
    risk_signals: list[str]
    decision: str
    reasoning: list[str]


class RiskScoreResponse(BaseModel):
    path: str
    risk_score: float
    factors: list[str]
    components: dict[str, float]


class ExplainRiskResponse(BaseModel):
    path: str
    risk_score: float
    decision: str
    reasoning: list[str]
    explanation: str


class ScanResponse(BaseModel):
    path: str
    findings: list[dict[str, Any]]
    bytes_read: int
    truncated: bool


class DirectoryScanResponse(BaseModel):
    path: str
    total_files_scanned: int
    matched_files: int
    total_findings: int
    findings_by_file: list[dict[str, Any]]


class CandidateSelectionResponse(BaseModel):
    root_path: str
    mode: str
    total_files: int
    candidate_count: int
    excluded_count: int
    candidates: list[dict[str, Any]]
    excluded: list[dict[str, Any]]
    summary: dict[str, Any]


class CandidateScanResponse(BaseModel):
    requested_paths: list[str]
    scanned_files: int
    matched_files: int
    total_findings: int
    results: list[dict[str, Any]]


class ComplianceResponse(BaseModel):
    path: str | None
    status: str
    finding_count: int
    severe_findings: list[dict[str, Any]]


class FeedbackResponse(BaseModel):
    status: str


class UpdateWeightsResponse(BaseModel):
    weights: dict[str, float]


class FullAnalysisResponse(BaseModel):
    total_files: int
    scanned_files: int
    reduction_percent: float
    high_risk_files: list[dict[str, Any]]
    findings: list[dict[str, Any]]
