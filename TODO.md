# TODO

## Urgent (Before Jun 8)

- [ ] Submit AGNTCon/MCPCon talk proposal on Sessionize
  - Proposal: `agntcon-mcpcon-proposal.md`
  - Speakers: Adhithya + Lakshman
  - Need: Sessionize account, speaker photos, bios

- [ ] Lakshman: Run eval harness on Linux/WSL (2-3 repos)
  - Instructions: `eval/RUNNING_EXPERIMENTS.md`
  - Send JSON reports back for cross-platform data

## Before Jul 10 (ICISS Chennai)

- [ ] Polish paper-v1 for ICISS submission format
- [ ] Add Lakshman's Linux eval results to paper tables
- [ ] Expand related work section (target 30+ references)
- [ ] Add proper ICISS formatting (check their LaTeX template)
- [ ] Run evaluation with LLM enabled (semantic inference ON) and compare
- [ ] Run on 2-3 more repos for stronger evaluation section

## Before Oct 2026 (ACM TOPS)

- [ ] Expand evaluation to 15-20 repos
- [ ] Add Windows endpoint evaluation
- [ ] Ablation study: keyword-only vs graph-only vs combined scoring
- [ ] Test different max_scan_percent thresholds (1%, 3%, 5%, 10%)
- [ ] Add confidence intervals and significance tests
- [ ] Full threat model section (adversarial evasion, prompt injection via filenames)
- [ ] Deeper regulatory analysis with case law
- [ ] Expand paper to 20+ pages (journal length)
- [ ] Ensure 30%+ new content vs ICISS version

## System Improvements

- [ ] Fix recall gap: `db_migrate.sh` and `payment_handler.py` missed in most runs
  - Root cause: generic filenames don't trigger keyword scoring
  - Potential fix: scan `.sh` files by default, add "handler" as keyword
- [ ] Add more scanner patterns: private keys (BEGIN RSA), JWT tokens, connection strings
- [ ] Test feedback loop: submit TP/FP labels, verify weight adjustment improves next run
- [ ] Demo video for AGNTCon proposal (optional but helpful)

## Done

- [x] Build eval harness (eval/run_evaluation.py)
- [x] Build ground-truth seeder (eval/seed_ground_truth.py)
- [x] macOS compatibility (linux_utils.py, file_utils.py)
- [x] Add Indian PAN + Aadhaar patterns to scanner
- [x] Run evaluation on 6 repos (Flask, Django, Kshetra, veriflow, Yukthi, fairmind)
- [x] Draft paper-v1 (Markdown, LaTeX, Word)
- [x] Draft AGNTCon/MCPCon talk proposal
- [x] Create PR to novel_mcp (#1)
- [x] Create RUNNING_EXPERIMENTS.md for contributors
