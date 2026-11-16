# Read the Room

## LLM-Based Filesystem Intelligence for Targeted Sensitive Data Discovery

**Adhithya Rajasekaran**
**ACM SecDev 2026 · Montréal**

> **Correction, November 2026.** The evaluation figures on the ACM SecDev 2026 poster are withdrawn. The synthetic corpus behind most of them leaked class labels through file names, content types and sizes, and the single-fixture LLM lane has no run logs. See [Withdrawn Poster Figures](#withdrawn-poster-figures).

---

## One-Line Summary

**Read the Room** is a metadata-first sensitive data discovery system that asks:

> Can we find sensitive files while opening far fewer files?

Instead of reading every file, the system first inspects only filesystem metadata, ranks paths by risk, and opens content only for a small selected set. Every access decision is logged.

---

## Core Idea

Most sensitive data discovery systems are judged by:

* What they find
* Their recall
* Their precision
* Their false positives

This project argues that they should also be judged by:

> **What they had to read in order to find it.**

Every file starts **closed**.

The system begins with metadata-only inspection:

* File and directory names
* Extensions
* Sizes
* Permissions
* Directory structure
* Path context

It then scores paths, selects likely candidates, and opens only those files for targeted scanning.

---

## Repository Status

This repository contains the **v1 system**.

The evaluation figures on the ACM SecDev 2026 poster came from a later v2 evaluation generation. Those figures are withdrawn; see [Withdrawn Poster Figures](#withdrawn-poster-figures).

| Area                  |    Status | Notes                                                                                                          |
| --------------------- | --------: | -------------------------------------------------------------------------------------------------------------- |
| v1 system             | Available | FastAPI application mounted as an MCP server using `fastapi_mcp`                                               |
| v1 MCP tools          | Available | 15 tools for filesystem inspection, risk scoring, candidate selection, targeted scanning, and analyst feedback |
| v1 evaluation harness | Available | Seeds synthetic ground truth and compares selective scanning against an exhaustive baseline                    |
| v2 evaluation         | Withdrawn | Synthetic 5K / 10K corpora leaked class labels                                                                 |
| Poster figures        | Withdrawn | See [Withdrawn Poster Figures](#withdrawn-poster-figures)                                                      |

---

## Provenance and Roles

The research idea, system design, and evaluation methodology are by **Adhithya Rajasekaran**, sole author of the ACM SecDev 2026 poster.

**[Lakshman Shanmugam](https://www.linkedin.com/in/lakshman-shanmugam-00bb42267/)** contributes code implementation and evaluation execution, is collaborating on the v2 system currently in development, and is a contributor to the full paper (in progress).

| Workstream                      | Contributors                                           |
| ------------------------------- | ------------------------------------------------------ |
| Research idea                   | Adhithya Rajasekaran                                   |
| System design                   | Adhithya Rajasekaran                                   |
| Evaluation methodology          | Adhithya Rajasekaran                                   |
| ACM SecDev 2026 poster          | Adhithya Rajasekaran                                   |
| v1 poster and initial research  | Adhithya Rajasekaran                                   |
| Inital Code Setup + Help        | Lakshman                                               |
| v2 implementation and paper WIP | Lakshman, Adhithya, Dhinakaran, Navya, Kishore, Balaji |

---

## License, Preprint, and Contact

| Item     | Details                                    |
| -------- | ------------------------------------------ |
| License  | MIT — see `LICENSE`                        |
| Preprint | None                                       |
| Contact  | `rajasekaran.adhit@gmail.com`              |
| LinkedIn | `linkedin.com/in/adhi1991`                 |

---

## Documentation

| File                    | Purpose                                                                                          |
| ----------------------- | ------------------------------------------------------------------------------------------------ |
| `docs/SYSTEM_GUIDE.md`  | Full v1 system guide: architecture, installation, API reference, MCP tools, and MCP client usage |
| `eval/README.md`        | Evaluation harness instructions                                                                  |
| `EXPERIMENTATION.md`    | Experimentation notes                                                                            |
| `eval/FIXTURES_NOTE.md` | Notes on intentionally planted synthetic secrets                                                 |

---

# System Overview

Read the Room follows a three-phase selective discovery workflow.

```text
Phase 1: Metadata-only inventory
        ↓
Phase 2: Risk scoring and candidate selection
        ↓
Phase 3: Targeted content scanning
```

---

## Phase 1: Metadata-Only Inventory

The first phase does **not** open file content.

It collects structural and metadata signals such as:

| Signal            | Example                                      |
| ----------------- | -------------------------------------------- |
| Path              | `/finance/payroll/2025/report.xlsx`          |
| Filename          | `employee_tax_ids.csv`                       |
| Extension         | `.csv`, `.xlsx`, `.pdf`, `.env`              |
| Size              | Small config file vs. large archive          |
| Permissions       | World-readable, owner-only, group-readable   |
| Directory context | `/tests/`, `/src/`, `/backups/`, `/exports/` |

This creates a filesystem bill of materials style view: an **FS-BOM**.

---

## Phase 2: Risk Scoring

Each path is scored using metadata-derived signals.

The v2 FS-BOM score is a hand-weighted heuristic with zero training:

```text
sᵢ =
0.45 · path-keywords
+ 0.25 · extension
+ 0.15 · world-readable
+ 0.15 · size-vs-budget
```

| Component      | Weight | Meaning                                                      |
| -------------- | -----: | ------------------------------------------------------------ |
| Path keywords  |   0.45 | Sensitive words in path or filename                          |
| Extension      |   0.25 | File type risk                                               |
| World-readable |   0.15 | Permission exposure                                          |
| Size-vs-budget |   0.15 | Whether the file is plausible to scan within the read budget |

The key property is that this score is computed from metadata only.

No file content is read during scoring.

---

## Phase 3: Targeted Content Scanning

Only selected candidates are opened.

The system then performs targeted scanning for sensitive content, including:

* Secrets
* PII
* PHI
* Card data
* Compliance-sensitive files

The current v1 system also supports analyst feedback so that scoring weights can be adapted over time.

---

# What Makes This Different?

Traditional scanning often starts by reading everything.

Read the Room starts from the opposite assumption:

> A file should remain closed unless there is a reason to open it.

The contribution is not simply better detection. The contribution is **exposure accounting**.

| Question                                | Traditional Scanner | Read the Room                |
| --------------------------------------- | ------------------- | ---------------------------- |
| Did it find sensitive data?             | Yes / no            | Yes / no                     |
| How precise was it?                     | Measured            | Measured                     |
| How much did it read?                   | Often not central   | Central metric               |
| Were content reads justified?           | Usually implicit    | Explicit and logged          |
| Can the inventory phase avoid content?  | Usually no          | Yes                          |
| Is access bounded by tool capabilities? | Usually no          | Yes, via MCP tool subsetting |

---

# MCP Access Boundary

The system uses MCP tools so that filesystem access can be divided into separate capabilities.

During metadata-only inventory, the agent is given structure-oriented tools only.

Content-reading tools are not available in that phase.

This means the access boundary is enforced by:

> **Capability subsetting at the MCP tool manifest.**

Every capability is a discrete, named, loggable tool call.

---

# Important Privacy Note

The FS-BOM is **content-free**, not **metadata-free**.

Metadata can still be sensitive.

Examples:

* A filename may reveal a patient name.
* A folder path may reveal a legal matter.
* Ownership may reveal team structure.
* Timestamps may reveal business activity.
* Permissions may reveal exposure.

So the claim is not “zero exposure.”

The claim is narrower:

> Metadata-first discovery creates a smaller exposure surface than read-all scanning.

The metadata inventory should still inherit the same access boundary, retention policy, and audit logging expectations as content reads.

---

# Evaluation Summary

There are two generations of evaluation discussed in this project.

| Evaluation    | Repository Status | Purpose                                                                                                            |
| ------------- | ----------------: | ------------------------------------------------------------------------------------------------------------------ |
| v1 evaluation |         Available | Demonstrates selective scanning against an exhaustive baseline using synthetic ground truth                        |
| v2 evaluation |         Withdrawn | Deterministic FS-BOM read gating over synthetic corpora; the corpora leaked class labels (see Withdrawn Poster Figures) |

---

## v1 Evaluation

The current repository includes an evaluation harness that:

* Plants synthetic ground truth
* Runs selective scanning
* Runs an exhaustive baseline
* Compares results

Reported metrics include:

| Metric          | Meaning                                             |
| --------------- | --------------------------------------------------- |
| Recall          | Fraction of planted positives found                 |
| Precision       | Fraction of flagged results that are true positives |
| Scan reduction  | Reduction in number of files opened                 |
| Wall-clock time | Runtime compared with exhaustive scanning           |

---

# Withdrawn Poster Figures

In November 2026 the authors withdrew the evaluation figures on the ACM SecDev 2026 poster. Do not cite them.

| Poster figure | Why it is withdrawn |
| ------------- | ------------------- |
| v2 results on the synthetic 5K / 10K corpora (~75% read reduction, 100% recall on base positives, 0.1 decoy suppression) | The corpus leaked class labels: file names, content types, body sizes and self-labelled bodies reveal which files are positives, so the figures do not measure the read gate. |
| Adversarial evasion results (2,730 cases, 91.6% caught, 78.5% S3-like recall) | Built on the same corpus. |
| Single-fixture LLM + MCP lane (Flask, 273 → 8 files opened, precision 1.00, 2 / 2 decoys suppressed) | No run logs or clean artifact back it. |
| Scanner baselines (Gitleaks, TruffleHog, detect-secrets) | Run on the same synthetic corpus, with live secret verification on and synthetic tokens that do not match real formats. |
| Zero content-read calls against the official Filesystem MCP server | The server version was never recorded, so the run cannot be reproduced. |

After the leak was removed, a related metadata read gate did no better than opening files at random.

---

# Deployment Profiles

The poster describes deployment profiles A–E.

These are not the same as the A / B / C lanes in the single-fixture example.

| Profile | Use Case                          |
| ------- | --------------------------------- |
| A       | Endpoint DLP assist               |
| B       | Code and secret scanning          |
| C       | Privacy discovery across drives   |
| D       | Compliance evidence review        |
| E       | Organization-controlled inference |

Each profile shares the same access-boundary principle, but each requires separate validation.

---

# False Positive Context

The poster references production DLP false-positive challenges.

The “80%+ false positives” framing follows Ponemon Institute reporting of 50–80% false-positive rates in production DLP deployments. The poster uses the upper-bound framing.

---

# What Is in This Repository

The current v1 tree includes:

* FastAPI application
* MCP server mounting via `fastapi_mcp`
* Filesystem inspection tools
* Graph-based risk scoring
* Candidate selection
* Targeted scanning
* Analyst feedback
* Evaluation harness
* Synthetic fixture generation

---

## v1 MCP Tooling

The v1 system exposes 15 tools spanning:

| Tool Area             | Purpose                                    |
| --------------------- | ------------------------------------------ |
| Filesystem inspection | Inspect structure and metadata             |
| Graph analysis        | Build and analyze filesystem relationships |
| Risk scoring          | Rank paths by sensitivity likelihood       |
| Candidate selection   | Select files for targeted scanning         |
| Targeted scanning     | Open and inspect selected files            |
| Analyst feedback      | Adjust scoring behavior based on review    |

The system is exposed both as:

| Interface   | Use                                   |
| ----------- | ------------------------------------- |
| HTTP routes | Direct API workflows                  |
| MCP tools   | Agentic workflows through MCP clients |

---

# Note for Scanner Authors

This repository intentionally contains synthetic secrets in its evaluation seeder.

See:

```text
eval/FIXTURES_NOTE.md
```

If a scanner flags these values, it is working as intended.

That result also illustrates part of the research problem: many tools can identify secret-like strings, but they do not always understand whether reading the file was necessary or whether the surrounding context matters.

---

# Citation

```text
A. Rajasekaran,
"Read the Room: LLM-Based Filesystem Intelligence for Targeted Sensitive Data Discovery,"
poster, ACM SecDev 2026.
```

---

# Final Note

If you run this on a real corpus, failure reports are worth more than stars.
