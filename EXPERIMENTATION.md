# Experimentation Runbook

This runbook explains exactly how to run the evaluation harness in the current codebase.

It covers:

- what each system means
- deterministic vs LLM-enabled runs
- whether you need to manually start the MCP server or client
- how seeding works
- exact commands to run
- how to compare the resulting reports

## 1. Systems under evaluation

The harness evaluates three systems:

- **System A**: exhaustive baseline
  - scans every file recursively
  - always deterministic
- **System B**: candidate-selector pipeline
  - first identifies likely scan-worthy files
  - then scans only those files
- **System B2**: graph-based selective pipeline
  - builds structure/context
  - computes graph/risk-based scores
  - scans only the top-ranked files

## 2. What changes between deterministic and LLM-enabled runs

### Deterministic run

When:

```bash
DLP_MCP_LLM_ENABLED=false
```

the systems behave as follows:

- **A**: deterministic
- **B**: deterministic
- **B2**: deterministic

### LLM-enabled run

When:

```bash
DLP_MCP_LLM_ENABLED=true
```

the systems behave as follows:

- **A**: still deterministic
- **B**: uses `mcp_client` over MCP for LLM-guided selective orchestration
- **B2**: still runs directly from `mcp_server.core`, but server-side semantic inference and explanations are LLM-enabled

Important detail:

- **B and B2 now use the same provider/model by default**
- server-side B2 semantic inference falls back to the same `OPENROUTER_*` values used by the MCP client
- only set `DLP_MCP_LLM_*` if you intentionally want B2 to use a different provider/model from B

## 3. Do you need to manually run the MCP server or MCP client?

### For deterministic runs

No.

Do **not** manually start:

- `python3 main.py`
- `uvicorn mcp_server.server.main:app --reload`
- `python3 mcp_client/chat_client.py`

Reason:

- the deterministic harness imports `mcp_server.core.*` directly and runs in-process

### For LLM-enabled runs

Also usually no.

The harness will:

- auto-start a local MCP server if one is not already running
- use a programmatic MCP client internally for System B

So for normal LLM-enabled evaluation runs, you should **not** manually start:

- the MCP server
- the interactive MCP client

### Recommended practice

For the cleanest experiment:

- do **not** keep a manual MCP server running in another terminal
- let the harness manage startup for LLM-enabled runs

Why:

- if a server is already running, the harness may reuse it
- that can make it unclear which config/env was actually used

## 4. Ground-truth seeding behavior

You do **not** need to manually seed in the normal path.

`run_evaluation.py` automatically:

1. checks whether `.eval_ground_truth/manifest.json` already exists
2. if not present, seeds the target repo
3. if present, reuses it

### Recommended practice

Before each fresh run on a repo, clean previous seed data:

```bash
python -m eval.seed_ground_truth /path/to/repo --clean
```

This avoids stale seeded files affecting repeated runs.

## 5. Prerequisites

From the repo root:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

For LLM-enabled runs, your `.env` should include at least:

```dotenv
DLP_MCP_APP_PORT=8081
DLP_MCP_SERVER_URL=http://localhost:8081/mcp
OPENROUTER_API_KEY=your-key
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
OPENROUTER_MODEL=nvidia/nemotron-3-nano-30b-a3b:free
```

Optional:

```dotenv
DLP_MCP_LLM_BASE_URL=
DLP_MCP_LLM_API_KEY=
DLP_MCP_LLM_MODEL=
```

Leave those blank unless you want the server-side B2 path to use a different LLM backend than the MCP client.

## 6. Recommended experiment plan per repo

For each target repo, do this:

1. clean old seed data
2. run deterministic evaluation
3. clean seed data again
4. run LLM-enabled evaluation
5. optionally clean seed data again

That gives you:

- one deterministic report
- one LLM-enabled report

Each report already includes:

- System A
- System B
- System B2

## 7. Exact commands

Assume:

```bash
TARGET=/path/to/repo
```

### Step 1: activate the environment

```bash
cd /path/to/novel_mcp
source .venv/bin/activate
```

### Step 2: deterministic run

```bash
python -m eval.seed_ground_truth "$TARGET" --clean
DLP_MCP_LLM_ENABLED=false python -m eval.run_evaluation "$TARGET"
```

What this does:

- System A runs as deterministic brute force
- System B runs as deterministic candidate selection
- System B2 runs as deterministic graph pipeline

### Step 3: clean before the next mode

```bash
python -m eval.seed_ground_truth "$TARGET" --clean
```

### Step 4: LLM-enabled run

```bash
DLP_MCP_LLM_ENABLED=true python -m eval.run_evaluation "$TARGET"
```

What this does:

- System A stays deterministic
- System B uses the MCP client + MCP server path
- System B2 uses direct graph pipeline with server-side LLM enabled
- the harness auto-starts the MCP server if necessary

### Step 5: optional final cleanup

```bash
python -m eval.seed_ground_truth "$TARGET" --clean
```

## 8. Multi-repo loop

If you want to run this for multiple repos:

```bash
cd /path/to/novel_mcp
source .venv/bin/activate

for TARGET in ~/projects/repo1 ~/projects/repo2 /home/youruser/work/repo3; do
  echo "============================================================"
  echo "Target: $TARGET"

  python -m eval.seed_ground_truth "$TARGET" --clean
  DLP_MCP_LLM_ENABLED=false python -m eval.run_evaluation "$TARGET"

  python -m eval.seed_ground_truth "$TARGET" --clean
  DLP_MCP_LLM_ENABLED=true python -m eval.run_evaluation "$TARGET"

  python -m eval.seed_ground_truth "$TARGET" --clean
done
```

## 9. What report files you will get

Each run writes one JSON report to:

```bash
eval/reports/
```

Typical filename:

```text
eval_<hostname>_<timestamp>.json
```

So for each repo you should end up with:

- one deterministic report
- one LLM-enabled report

## 10. What to compare in the reports

The most important sections are:

- `metadata`
- `candidate_selection`
- `selective_scan`
- `graph_pipeline_scan`
- `baseline_scan`
- `ground_truth_eval`
- `comparison`

### Most useful fields

- `metadata.llm_enabled`
- `selective_scan.execution_path`
- `graph_pipeline_scan.execution_path`
- `selective_scan.reduction_percent`
- `graph_pipeline_scan.reduction_percent`
- `baseline_scan.total_files_scanned`
- `ground_truth_eval.selective.recall`
- `ground_truth_eval.selective.precision`
- `ground_truth_eval.graph_pipeline.recall`
- `ground_truth_eval.graph_pipeline.precision`
- `ground_truth_eval.baseline.recall`
- `ground_truth_eval.baseline.precision`
- `comparison.speedup_factor`

## 11. How to interpret the two modes

### Deterministic run

Use this to measure:

- reproducible heuristic-only performance
- scan reduction without LLM assistance
- whether B and B2 work purely from deterministic logic

### LLM-enabled run

Use this to measure:

- whether System B improves with MCP-client orchestration
- whether System B2 improves with server-side semantic inference enabled
- whether latency increases relative to deterministic mode

## 12. Should you manually run `main.py` or `chat_client.py`?

### `python3 main.py`

Not needed for the evaluation harness.

Only run it manually if:

- you want to debug the MCP server separately
- auto-start is failing and you want to isolate server issues

### `python3 mcp_client/chat_client.py`

Do **not** use this for evaluation.

That script is for interactive chat, not the structured experiment flow.

The harness uses:

- `mcp_client/eval_agent.py`

internally when System B is LLM-enabled.

## 13. Safest exact sequence

If you want the safest possible procedure per target repo, use exactly this:

```bash
cd /path/to/novel_mcp
source .venv/bin/activate

TARGET=/path/to/repo

python -m eval.seed_ground_truth "$TARGET" --clean
DLP_MCP_LLM_ENABLED=false python -m eval.run_evaluation "$TARGET"

python -m eval.seed_ground_truth "$TARGET" --clean
DLP_MCP_LLM_ENABLED=true python -m eval.run_evaluation "$TARGET"

python -m eval.seed_ground_truth "$TARGET" --clean
```

## 14. Practical cautions

- do not use Windows UNC paths inside WSL/bash
  - use `/home/...` or `/mnt/c/...`
- do not keep an old MCP server running during LLM-enabled experiments unless you really mean to reuse it
- if a run fails midway, clean `.eval_ground_truth` before rerunning
- large repos can make System A much slower than B/B2
- if B2 logs LLM fallback errors, check the resolved server-side LLM settings first

## 15. What to send back to the team

For each target repo, send:

- the generated JSON report files from `eval/reports/`
- a short note including:
  - repo name/path
  - deterministic run completed
  - LLM-enabled run completed
  - machine / OS used
  - any anomalies, failures, or suspicious metrics

## 16. Short version

For each repo:

```bash
python -m eval.seed_ground_truth /path/to/repo --clean
DLP_MCP_LLM_ENABLED=false python -m eval.run_evaluation /path/to/repo

python -m eval.seed_ground_truth /path/to/repo --clean
DLP_MCP_LLM_ENABLED=true python -m eval.run_evaluation /path/to/repo

python -m eval.seed_ground_truth /path/to/repo --clean
```

No manual `uvicorn`, no manual `main.py`, and no manual `mcp_client/chat_client.py` are needed for the normal evaluation workflow.
