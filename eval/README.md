# Evaluation Harness — APF 2026 / SecDev 2026

Automated evaluation framework for the risk-aware MCP DLP system. Runs the
selective pipeline (System B) and brute-force baseline (System A) against
target directories, computes recall/precision/F1 against planted ground truth,
and outputs structured JSON reports suitable for paper tables.

## Quick start

```bash
# From the repo root
pip install -r requirements.txt

# Run against any real codebase
python -m eval.run_evaluation /path/to/some/repo

# Run against multiple targets
for repo in ~/projects/repo-a ~/projects/repo-b /tmp/open-source-clone; do
    python -m eval.run_evaluation "$repo"
done
```

## What happens

1. **Enumerate** — counts files and extensions in the target
2. **Seed** — plants ground-truth violations (`.eval_ground_truth/`) with a
   manifest recording exactly what was planted and where
3. **Candidate selection** — runs Phase 1-2 (metadata-only candidate ranking)
4. **Selective scan** — runs the full three-phase pipeline (Phase 1-3)
5. **Baseline scan** — runs brute-force exhaustive scan on all files
6. **Evaluation** — compares both scan modes against the ground-truth manifest

## Ground truth

The seeder (`eval/seed_ground_truth.py`) plants:

- **5 violation files**: `.env` with credentials, CSV with PII/PAN IDs, shell
  script with embedded passwords, Python file with hardcoded card numbers,
  JSON with Aadhaar numbers
- **2 false-positive traps**: test file with industry-standard test card
  numbers, documentation with placeholder credentials

These are placed in `.eval_ground_truth/` so they don't mix with the repo's
real files. The manifest records expected patterns and regulatory frameworks
for each file.

## Flags

```
--skip-seed       Don't plant ground truth (use existing or skip GT metrics)
--skip-baseline   Don't run exhaustive baseline (faster, but no comparison)
```

## Output

Reports are written to `eval/reports/` as JSON:

```
eval/reports/eval_<hostname>_<timestamp>.json
```

Key metrics in each report:

| Metric | Description |
|--------|-------------|
| `selective_scan.reduction_percent` | % of files NOT scanned |
| `selective_scan.elapsed_seconds` | Wall time for selective scan |
| `baseline_scan.elapsed_seconds` | Wall time for exhaustive scan |
| `comparison.speedup_factor` | Baseline time / selective time |
| `ground_truth_eval.selective.recall` | TP / (TP + FN) for selective |
| `ground_truth_eval.selective.precision` | TP / (TP + FP) for selective |
| `ground_truth_eval.baseline.recall` | TP / (TP + FN) for baseline |

## Cleaning up

```bash
python -m eval.seed_ground_truth /path/to/repo --clean
```

## LLM configuration

By default, the evaluation runs with `DLP_MCP_LLM_ENABLED=false` for
reproducibility. The candidate selection and risk scoring use deterministic
heuristics (keyword matching, extension classification, graph centrality)
without LLM calls.

To run with LLM-assisted semantic inference:
```bash
DLP_MCP_LLM_ENABLED=true python -m eval.run_evaluation /path/to/repo
```

## Running on macOS

The system now supports macOS natively. The `stat` and `tree` commands fall
back to Python implementations when GNU versions are not available.
