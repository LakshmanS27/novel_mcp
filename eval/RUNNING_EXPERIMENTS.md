# Running Experiments — Instructions for Contributors

This guide explains how to run the evaluation harness on your machine to generate
data for the APF 2026 / SecDev 2026 paper.

We need runs from **multiple machines and OS types** (Linux, Windows/WSL, macOS).
Each run produces a JSON report that goes directly into the paper tables.

---

## Prerequisites

- Python 3.11+
- Git

That's it. No API keys needed — the evaluation runs with LLM disabled for
reproducibility.

---

## Linux / WSL Setup

```bash
# 1. Clone the repo (or pull the eval branch if you already have it)
git clone https://github.com/LakshmanS27/novel_mcp.git
cd novel_mcp
git checkout eval/experiment-harness

# 2. Create venv and install dependencies
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 3. Run against target directories
#    Pick 2-3 repos or project directories on your machine.
#    Larger is better (500+ files). Examples:

python -m eval.run_evaluation ~/projects/some-repo
python -m eval.run_evaluation ~/projects/another-repo
python -m eval.run_evaluation /home/youruser/work/big-project

# 4. Check reports
ls eval/reports/
```

### What it does

For each target directory:

1. Counts all files and extensions
2. Plants 5 violation files + 2 false-positive traps inside `.eval_ground_truth/`
3. Runs **System B** (candidate-selector pipeline) — scans only top-ranked files
4. Runs **System B2** (graph-based pipeline) — scans only top 1-5%
5. Runs **System A** (exhaustive baseline) — scans every file
6. Compares all three against ground truth → recall, precision, F1
7. Cleans up the planted files automatically (or run cleanup manually, see below)

### Output

Each run creates a JSON report in `eval/reports/`:
```
eval/reports/eval_<hostname>_<timestamp>.json
```

---

## Windows Setup

### Option A: WSL (Recommended)

If you have WSL installed, follow the Linux instructions above inside your WSL terminal.
You can scan Windows directories through WSL mount points:

```bash
# Scan a Windows directory from WSL
python -m eval.run_evaluation /mnt/c/Users/YourName/Projects/some-repo
```

### Option B: Native Windows (PowerShell)

```powershell
# 1. Clone and checkout
git clone https://github.com/LakshmanS27/novel_mcp.git
cd novel_mcp
git checkout eval/experiment-harness

# 2. Create venv
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# 3. Run evaluation
python -m eval.run_evaluation C:\Users\YourName\Projects\some-repo
```

> **Note**: On native Windows, the `tree` command works differently. The harness
> falls back to a Python directory walker automatically — no extra setup needed.
> However, the `stat` permission bits will show differently than on Linux/macOS.

---

## What to scan

Pick **real directories** from your machine. Good targets:

- Your own project repos (any language)
- Open source repos you have cloned locally
- Work project directories

**Do NOT use tiny test directories** (< 50 files). The system's value shows at
scale. Aim for directories with 500+ files.

**Examples of good targets:**
```bash
# A Node.js project with node_modules excluded
python -m eval.run_evaluation ~/projects/my-web-app

# A Python project
python -m eval.run_evaluation ~/projects/my-api

# A large monorepo
python -m eval.run_evaluation ~/work/company-monorepo

# An open source clone
git clone --depth 1 https://github.com/django/django.git /tmp/django
python -m eval.run_evaluation /tmp/django
```

---

## Sending results

After running, collect the JSON files from `eval/reports/` and either:

1. **Push them to your fork** and update the PR
2. **Share them directly** with the team

Each JSON contains everything needed for the paper: file counts, scan reduction
percentages, timing, recall, precision, and F1 scores.

---

## Cleaning up

The seeder plants files in `.eval_ground_truth/` inside each target directory.
The evaluation does NOT auto-clean these. To remove:

```bash
python -m eval.seed_ground_truth /path/to/repo --clean
```

Or just delete the `.eval_ground_truth/` folder manually.

---

## Troubleshooting

### `tree` command not found
No problem — the harness falls back to a Python walker. No action needed.

### Permission denied on target directory
Make sure you have read access. The harness only reads files, never writes to
the target (except the `.eval_ground_truth/` seed directory).

### Path not allowed error
The harness restricts paths for safety:
- **Linux/WSL**: `/home/`, `/mnt/`, `/tmp/`
- **macOS**: `/Users/`, `/tmp/`, `/private/`

If your target is outside these, you'll need to update `ALLOWED_ROOT_PREFIXES`
in `mcp_server/utils/file_utils.py`.

### Very slow baseline on huge directories
The baseline (System A) scans every file. On directories with 50K+ files this
can take several minutes. You can skip it:

```bash
python -m eval.run_evaluation /path/to/huge-repo --skip-baseline
```

You'll still get System B and B2 metrics, just no baseline comparison.
