# Read the Room

## LLM-Based Filesystem Intelligence for Targeted Sensitive Data Discovery

**Adhithya Rajasekaran**
**ACM SecDev 2026 · Montréal**

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

This repository currently contains the **v1 system**.

The ACM SecDev 2026 poster reports results from a later **v2 evaluation generation**. That v2 work is under active development and will be released here.

Until v2 is released, the poster’s v2 exposure and adversarial evaluation figures are **not fully reproducible from this repository**.

| Area                  |         Status | Notes                                                                                                          |
| --------------------- | -------------: | -------------------------------------------------------------------------------------------------------------- |
| v1 system             |      Available | FastAPI application mounted as an MCP server using `fastapi_mcp`                                               |
| v1 MCP tools          |      Available | 15 tools for filesystem inspection, risk scoring, candidate selection, targeted scanning, and analyst feedback |
| v1 evaluation harness |      Available | Seeds synthetic ground truth and compares selective scanning against an exhaustive baseline                    |
| v2 evaluation system  | In development | Deterministic FS-BOM read gate over synthetic 5K / 10K corpora                                                 |
| Poster figures        |       v2-based | Report later evaluation-generation results, not all reproducible from the current tree                         |

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
| Preprint | Forthcoming; arXiv endorsement in progress |
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

In the v2 run against the official Filesystem MCP server:

```text
version / commit: ___
tools: 14
transport: stdio
```

the inventory phase recorded:

```text
zero content-read calls
```

This was verified from the tool-call log.

In the pinned version used for that run, `search_files` performs name/path matching only. It does not perform content grep.

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
| v2 evaluation |    In development | Evaluates deterministic FS-BOM read gating over larger synthetic corpora with seeded variants and adversarial sets |

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

## v2 Evaluation

The ACM SecDev 2026 poster reports results from the v2 evaluation generation.

This evaluation uses:

* Synthetic 5K / 10K corpora
* 10-seed evaluation matrix
* Seeded source profiles
* Adversarial evasion sets
* Deterministic FS-BOM read gate
* Checksum-pinned fixture integrity

| Term              | Meaning                                                   |
| ----------------- | --------------------------------------------------------- |
| 5K corpus         | 4,700 evaluated files after excluding non-evaluable files |
| 10K corpus        | 9,333 evaluated files after excluding non-evaluable files |
| M10               | 10-seed evaluation matrix                                 |
| 516-row checksums | Fixture integrity manifest pinning files by hash          |
| 195 tests         | v2 test suite across macOS and WSL2                       |

The gate is deterministic. Seeds randomize fixture generation, not the gate itself.

---

# Poster Figure Clarifications

This section clarifies the ACM SecDev 2026 poster figures.

---

## Single-Fixture Model-Assisted Example

One poster line reports a single Flask fixture:

```text
Flask 273f · A:273 0.71 0/2 · B:100 0.71 0/2 · C(LLM+MCP):8 1.00 2/2
```

This means:

```text
files opened · precision · context traps suppressed
```

| Lane | Meaning                | Files Opened | Precision | Context Traps Suppressed |
| ---- | ---------------------- | -----------: | --------: | -----------------------: |
| A    | Read-all baseline      |          273 |      0.71 |                    0 / 2 |
| B    | Heuristic shortlist    |          100 |      0.71 |                    0 / 2 |
| C    | Bounded LLM + MCP lane |            8 |      1.00 |                    2 / 2 |

The reduction from 273 files opened to 8 files opened is:

```text
273 → 8 = 97% reduction
```

This is a **single-fixture illustration**, not a scaled benchmark.

It should not be confused with the separate v2 corpus-level read-reduction figure.

| Figure         | Applies To                                |
| -------------- | ----------------------------------------- |
| 97% reduction  | Single Flask fixture only                 |
| ~75% reduction | v2 deterministic gate on 5K / 10K corpora |

---

## Trap Suppression Clarification

Two trap-suppression values appear in the poster, but they come from different experiments.

| Value | Experiment                                 | Interpretation                 |
| ----: | ------------------------------------------ | ------------------------------ |
|   0.1 | v2 deterministic metadata gate at 5K scale | Weak decoy suppression         |
| 2 / 2 | Single-fixture bounded LLM lane            | Both fixture decoys suppressed |

Metadata alone cannot reliably distinguish every decoy.

For example:

```text
/tests/sample_card.txt
/src/customer_card_export.csv
```

Both paths may contain signals related to card data, but only one may represent realistic sensitive exposure.

The LLM lane can reason about context in the small fixture. Whether that holds at scale is future work.

---

## Recall Clarification

The poster separates two groups:

| Group                   | Meaning                                        |         Result |
| ----------------------- | ---------------------------------------------- | -------------: |
| Base planted positives  | Realistic seeded sensitive files               |    100% recall |
| Adversarial evasion set | Hard cases designed to defeat metadata signals | Partial recall |

The 100% recall claim applies to **base planted positives**, not to the adversarial evasion set.

---

## Adversarial Evasion Results

The adversarial set contains:

| Metric                          | Value |
| ------------------------------- | ----: |
| Total adversarial cases         | 2,730 |
| Seeds                           |    10 |
| Cases per seed                  |   273 |
| S3-like cases per seed          |   107 |
| Misses per seed                 |    23 |
| Total misses                    |   230 |
| Total caught                    | 2,500 |
| Aggregate caught rate           | 91.6% |
| S3-like adversarial recall      | 78.5% |
| Repository profile recall       |  100% |
| Local filesystem profile recall |  100% |
| Shared-drive profile recall     |  100% |

All missed cases are in the S3-like profile.

This is expected to be the hardest profile because flat object-store namespaces often lack useful path semantics.

Example:

```text
s3://bucket/a8f31d9c-blob
s3://bucket/export-00017
s3://bucket/tmp-object-92
```

With opaque object keys, metadata-first triage has less context to reason from.

This is a mapped boundary of the approach, not a hidden failure.

---

## Poster Erratum

The poster Section 04 headline says:

```text
92.7% of 2,730 trap cases caught
```

The correct aggregate is:

```text
2,730 − 230 = 2,500 caught
2,500 / 2,730 = 91.6%
```

| Poster Element                     | Status    |
| ---------------------------------- | --------- |
| Headline: “92.7% caught”           | Incorrect |
| Caption: “230 of 2,730 missed”     | Correct   |
| Per-profile bars                   | Correct   |
| Section 07: “23 misses every seed” | Correct   |
| Correct aggregate                  | 91.6%     |

---

## Terminology: Two Meanings of “Trap”

The word “trap” is used in two ways.

| Term                  | Meaning                                       | Desired Behavior |
| --------------------- | --------------------------------------------- | ---------------- |
| Adversarial trap case | A hard positive case the system should catch  | Catch it         |
| Decoy trap            | A planted non-sensitive or context-only decoy | Suppress it      |

In short:

```text
Evasion traps should be caught.
Decoy traps should be skipped.
```

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

# Scanner Baselines

The poster compares against local scanner baselines.

| Scanner        | Recall | Precision | Trap Score |
| -------------- | -----: | --------: | ---------: |
| Gitleaks       |   0.16 |      0.65 |       0.88 |
| TruffleHog     |   0.16 |      0.96 |       1.00 |
| detect-secrets |   0.14 |      0.56 |       0.90 |

These are secret scanners.

The Read the Room ground truth includes sensitive data families outside traditional secret-scanning scope:

* PII
* PHI
* Card data
* Compliance-sensitive files
* Secrets

The project does **not** claim to simply out-detect these tools.

The claimed contribution is:

> Access-boundary-aware discovery with explicit exposure accounting.

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
Preprint forthcoming.
```

---

# Final Note

If you run this on a real corpus, failure reports are worth more than stars.
