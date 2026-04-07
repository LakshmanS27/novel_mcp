"""APF/SecDev 2026 Evaluation Runner.

Runs the three-phase selective pipeline and brute-force baseline against a
target directory, then compares results to ground-truth to compute recall,
precision, false-positive rate, and scan reduction.

Usage:
    # Seed ground truth, run evaluation, clean up
    python -m eval.run_evaluation /path/to/repo

    # Run against a directory that already has .eval_ground_truth/
    python -m eval.run_evaluation /path/to/repo --skip-seed

    # Only run selective (skip brute-force baseline)
    python -m eval.run_evaluation /path/to/repo --skip-baseline

Reports are written to eval/reports/
"""

from __future__ import annotations

import asyncio
import json
import os
import platform
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mcp_server.core.candidate_selector import identify_scan_candidates
from mcp_server.core.pipeline import run_full_analysis
from mcp_server.core.scanner import scan_directory_sensitive_data, scan_file_sensitive_data, validate_compliance
from mcp_server.server.config import Settings


def _count_files(root: Path) -> dict[str, Any]:
    """Count files and extensions under root, excluding common noise."""
    skip_dirs = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build"}
    total_files = 0
    total_dirs = 0
    extensions: dict[str, int] = {}

    for current_root, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in skip_dirs]
        total_dirs += len(dirs)
        for f in files:
            total_files += 1
            ext = Path(f).suffix.lower() or "(none)"
            extensions[ext] = extensions.get(ext, 0) + 1

    return {
        "total_files": total_files,
        "total_dirs": total_dirs,
        "extensions": dict(sorted(extensions.items(), key=lambda x: -x[1])),
    }


def _load_manifest(target_root: Path) -> dict | None:
    manifest_path = target_root / ".eval_ground_truth" / "manifest.json"
    if manifest_path.exists():
        return json.loads(manifest_path.read_text(encoding="utf-8"))
    return None


def _match_findings_to_ground_truth(
    scan_findings: list[dict[str, Any]],
    manifest: dict,
) -> dict[str, Any]:
    """Compare scan results against ground-truth manifest."""
    gt_violations = [f for f in manifest["files"] if not f["is_false_positive_trap"]]
    gt_fp_traps = [f for f in manifest["files"] if f["is_false_positive_trap"]]

    # Paths that the scanner flagged with findings
    # Handle both formats: baseline uses "findings", selective uses "scan_findings"
    flagged_paths = set()
    for finding in scan_findings:
        path = finding.get("path", "")
        has_findings = finding.get("findings") or finding.get("scan_findings")
        if has_findings:
            flagged_paths.add(path)

    # True positives: ground-truth violations that were detected
    true_positives = []
    false_negatives = []
    for gt_file in gt_violations:
        if gt_file["path"] in flagged_paths:
            true_positives.append(gt_file["path"])
        else:
            false_negatives.append(gt_file["path"])

    # False positives from traps: FP-trap files that were incorrectly flagged
    false_positives_from_traps = []
    correctly_ignored_traps = []
    for gt_file in gt_fp_traps:
        if gt_file["path"] in flagged_paths:
            false_positives_from_traps.append(gt_file["path"])
        else:
            correctly_ignored_traps.append(gt_file["path"])

    tp = len(true_positives)
    fn = len(false_negatives)
    fp_traps = len(false_positives_from_traps)

    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    precision = tp / (tp + fp_traps) if (tp + fp_traps) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

    return {
        "true_positives": true_positives,
        "false_negatives": false_negatives,
        "false_positives_from_traps": false_positives_from_traps,
        "correctly_ignored_traps": correctly_ignored_traps,
        "tp_count": tp,
        "fn_count": fn,
        "fp_trap_count": fp_traps,
        "recall": round(recall, 4),
        "precision": round(precision, 4),
        "f1_score": round(f1, 4),
    }


async def run_selective(target: Path, settings: Settings) -> dict[str, Any]:
    """Run candidate-selector + targeted scan pipeline (System B in the paper).

    This uses identify_scan_candidates (deterministic heuristic ranking) followed
    by scan_candidate_files. This is the recommended selective workflow per the
    project README and matches the paper's three-phase description.
    """
    start = time.perf_counter()

    # Phase 1-2: Candidate selection (no content reading)
    candidates = await identify_scan_candidates(
        target, mode="broad", max_candidates=settings.max_candidate_files, settings=settings,
    )

    total_files = candidates["total_files"]
    selected = candidates["candidates"]

    # Phase 3: Scan only selected candidates
    scan_results: list[dict[str, Any]] = []
    for candidate in selected:
        try:
            result = await scan_file_sensitive_data(candidate["path"], settings)
            compliance = await validate_compliance(result)
            scan_results.append({
                "path": candidate["path"],
                "risk_score": candidate["score"],
                "reasons": candidate["reasons"],
                "scan_findings": result["findings"],
                "compliance": compliance["status"],
                "bytes_read": result["bytes_read"],
            })
        except (OSError, IsADirectoryError):
            continue

    elapsed = time.perf_counter() - start
    scanned = len(scan_results)
    reduction = round((1 - (scanned / total_files)) * 100, 2) if total_files > 0 else 0.0

    return {
        "mode": "selective",
        "total_files": total_files,
        "scanned_files": scanned,
        "reduction_percent": reduction,
        "high_risk_files": [
            {"path": r["path"], "risk_score": r["risk_score"]}
            for r in scan_results
        ],
        "findings": scan_results,
        "elapsed_seconds": round(elapsed, 2),
    }


async def run_graph_pipeline(target: Path, settings: Settings) -> dict[str, Any]:
    """Run the graph-based full analysis pipeline for comparison."""
    start = time.perf_counter()
    result = await run_full_analysis(target, depth=settings.max_tree_depth, settings=settings)
    elapsed = time.perf_counter() - start

    return {
        "mode": "graph_pipeline",
        "total_files": result["total_files"],
        "scanned_files": result["scanned_files"],
        "reduction_percent": result["reduction_percent"],
        "high_risk_files": [
            {"path": f["path"], "risk_score": f["risk_score"]}
            for f in result["high_risk_files"]
        ],
        "findings": result["findings"],
        "elapsed_seconds": round(elapsed, 2),
    }


async def run_baseline(target: Path, settings: Settings) -> dict[str, Any]:
    """Run brute-force exhaustive scan (System A in the paper)."""
    start = time.perf_counter()
    result = await scan_directory_sensitive_data(target, settings)
    elapsed = time.perf_counter() - start

    return {
        "mode": "baseline_exhaustive",
        "total_files_scanned": result["total_files_scanned"],
        "matched_files": result["matched_files"],
        "total_findings": result["total_findings"],
        "findings_by_file": result["findings_by_file"],
        "elapsed_seconds": round(elapsed, 2),
    }


async def run_candidate_selection(target: Path, settings: Settings) -> dict[str, Any]:
    """Run candidate selection phase independently for analysis."""
    start = time.perf_counter()
    result = await identify_scan_candidates(
        target, mode="broad", max_candidates=settings.max_candidate_files, settings=settings,
    )
    elapsed = time.perf_counter() - start

    return {
        "total_files": result["total_files"],
        "candidate_count": result["candidate_count"],
        "excluded_count": result["excluded_count"],
        "selection_ratio_percent": round(
            (result["candidate_count"] / result["total_files"] * 100) if result["total_files"] > 0 else 0, 2
        ),
        "top_candidates": [
            {"path": c["path"], "score": c["score"], "reasons": c["reasons"]}
            for c in result["candidates"][:20]
        ],
        "summary": result["summary"],
        "elapsed_seconds": round(elapsed, 2),
    }


async def main(target_path: str, skip_seed: bool = False, skip_baseline: bool = False) -> None:
    target = Path(target_path).resolve()
    if not target.is_dir():
        print(f"Error: {target} is not a directory")
        sys.exit(1)

    # Disable LLM calls for reproducible evaluation
    os.environ["DLP_MCP_LLM_ENABLED"] = "false"
    settings = Settings()

    reports_dir = Path(__file__).resolve().parent / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    hostname = platform.node()

    print("=" * 70)
    print("APF/SecDev 2026 EVALUATION")
    print("=" * 70)
    print(f"Target:    {target}")
    print(f"Machine:   {hostname}")
    print(f"Platform:  {platform.system()} {platform.release()}")
    print(f"Time:      {timestamp}")
    print("=" * 70)

    # Phase 0: Enumerate
    print("\n[Phase 0] Enumerating filesystem...")
    enumeration = _count_files(target)
    print(f"  Files: {enumeration['total_files']}  Dirs: {enumeration['total_dirs']}")

    # Seed ground truth if needed
    manifest = _load_manifest(target)
    if not manifest and not skip_seed:
        from eval.seed_ground_truth import seed
        print("\n[Seeding] Planting ground-truth violations...")
        manifest = seed(target)
        print(f"  Planted {manifest['total_violation_files']} violations + {manifest['total_fp_trap_files']} FP traps")
        # Re-count after seeding
        enumeration = _count_files(target)
    elif manifest:
        print(f"\n[Seeding] Using existing ground truth ({manifest['total_violation_files']} violations, {manifest['total_fp_trap_files']} FP traps)")
    else:
        print("\n[Seeding] Skipped (--skip-seed). No ground truth for recall/precision metrics.")

    # Candidate selection analysis
    print("\n[Phase 1-2] Running candidate selection...")
    candidate_result = await run_candidate_selection(target, settings)
    print(f"  {candidate_result['candidate_count']}/{candidate_result['total_files']} candidates selected ({candidate_result['selection_ratio_percent']}%)")

    # Selective scan — candidate selector pipeline (System B)
    print("\n[System B] Running candidate-selector pipeline...")
    selective_result = await run_selective(target, settings)
    print(f"  Scanned {selective_result['scanned_files']}/{selective_result['total_files']} files")
    print(f"  Reduction: {selective_result['reduction_percent']}%")
    print(f"  Time: {selective_result['elapsed_seconds']}s")

    # Graph pipeline (System B2) — for comparison
    print("\n[System B2] Running graph-based pipeline...")
    graph_result = await run_graph_pipeline(target, settings)
    print(f"  Scanned {graph_result['scanned_files']}/{graph_result['total_files']} files")
    print(f"  Reduction: {graph_result['reduction_percent']}%")
    print(f"  Time: {graph_result['elapsed_seconds']}s")

    # Baseline exhaustive scan (System A)
    baseline_result = None
    if not skip_baseline:
        print("\n[System A] Running exhaustive baseline scan...")
        baseline_result = await run_baseline(target, settings)
        print(f"  Scanned {baseline_result['total_files_scanned']} files")
        print(f"  Findings: {baseline_result['total_findings']}")
        print(f"  Time: {baseline_result['elapsed_seconds']}s")

    # Ground truth comparison
    selective_gt = None
    graph_gt = None
    baseline_gt = None
    if manifest:
        print("\n[Evaluation] Comparing against ground truth...")
        selective_gt = _match_findings_to_ground_truth(
            selective_result.get("findings", []), manifest
        )
        print(f"  System B  (candidate) — Recall: {selective_gt['recall']}  Precision: {selective_gt['precision']}  F1: {selective_gt['f1_score']}")
        if selective_gt["false_negatives"]:
            print(f"    Missed: {selective_gt['false_negatives']}")

        graph_gt = _match_findings_to_ground_truth(
            graph_result.get("findings", []), manifest
        )
        print(f"  System B2 (graph)     — Recall: {graph_gt['recall']}  Precision: {graph_gt['precision']}  F1: {graph_gt['f1_score']}")

        if baseline_result:
            baseline_gt = _match_findings_to_ground_truth(
                baseline_result.get("findings_by_file", []), manifest
            )
            print(f"  System A  (baseline)  — Recall: {baseline_gt['recall']}  Precision: {baseline_gt['precision']}  F1: {baseline_gt['f1_score']}")

    # Assemble report
    report = {
        "metadata": {
            "target_path": str(target),
            "machine_name": hostname,
            "os": f"{platform.system()} {platform.release()}",
            "timestamp": timestamp,
            "llm_enabled": settings.llm_enabled,
            "scan_percent_config": f"{settings.min_scan_percent * 100:.0f}-{settings.max_scan_percent * 100:.0f}%",
        },
        "enumeration": enumeration,
        "candidate_selection": candidate_result,
        "selective_scan": selective_result,
        "graph_pipeline_scan": graph_result,
        "baseline_scan": baseline_result,
        "ground_truth_eval": {
            "selective": selective_gt,
            "graph_pipeline": graph_gt,
            "baseline": baseline_gt,
        } if manifest else None,
        "comparison": None,
    }

    # Compute comparison metrics
    if baseline_result and selective_result:
        speedup = (
            baseline_result["elapsed_seconds"] / selective_result["elapsed_seconds"]
            if selective_result["elapsed_seconds"] > 0 else 0
        )
        report["comparison"] = {
            "scan_reduction_percent": selective_result["reduction_percent"],
            "graph_reduction_percent": graph_result["reduction_percent"],
            "selective_time_seconds": selective_result["elapsed_seconds"],
            "graph_time_seconds": graph_result["elapsed_seconds"],
            "baseline_time_seconds": baseline_result["elapsed_seconds"],
            "speedup_factor": round(speedup, 2),
            "selective_files_scanned": selective_result["scanned_files"],
            "graph_files_scanned": graph_result["scanned_files"],
            "baseline_files_scanned": baseline_result["total_files_scanned"],
        }
        if selective_gt and baseline_gt:
            report["comparison"]["recall_selective"] = selective_gt["recall"]
            report["comparison"]["recall_graph"] = graph_gt["recall"] if graph_gt else None
            report["comparison"]["recall_baseline"] = baseline_gt["recall"]
            report["comparison"]["precision_selective"] = selective_gt["precision"]
            report["comparison"]["precision_graph"] = graph_gt["precision"] if graph_gt else None
            report["comparison"]["precision_baseline"] = baseline_gt["precision"]

    # Write report
    report_name = f"eval_{hostname}_{timestamp}.json"
    report_path = reports_dir / report_name
    report_path.write_text(json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8")

    print("\n" + "=" * 70)
    print("EVALUATION COMPLETE")
    print("=" * 70)
    print(f"Report: {report_path}")

    if report.get("comparison"):
        c = report["comparison"]
        print(f"\n  {'Metric':<25} {'System B':>10} {'System B2':>10} {'System A':>10}")
        print(f"  {'':─<25} {'(candidate)':>10} {'(graph)':>10} {'(baseline)':>10}")
        print(f"  {'Scan reduction':<25} {c['scan_reduction_percent']:>9.1f}% {c['graph_reduction_percent']:>9.1f}% {'0.0%':>10}")
        print(f"  {'Files scanned':<25} {c['selective_files_scanned']:>10} {c['graph_files_scanned']:>10} {c['baseline_files_scanned']:>10}")
        print(f"  {'Time (seconds)':<25} {c['selective_time_seconds']:>10.2f} {c['graph_time_seconds']:>10.2f} {c['baseline_time_seconds']:>10.2f}")
        if "recall_selective" in c:
            print(f"  {'Recall':<25} {c['recall_selective']:>10.4f} {c.get('recall_graph', 'N/A'):>10} {c['recall_baseline']:>10.4f}")
            print(f"  {'Precision':<25} {c['precision_selective']:>10.4f} {c.get('precision_graph', 'N/A'):>10} {c['precision_baseline']:>10.4f}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m eval.run_evaluation <target_directory> [--skip-seed] [--skip-baseline]")
        sys.exit(1)

    target_arg = sys.argv[1]
    skip_seed_flag = "--skip-seed" in sys.argv
    skip_baseline_flag = "--skip-baseline" in sys.argv

    asyncio.run(main(target_arg, skip_seed=skip_seed_flag, skip_baseline=skip_baseline_flag))
