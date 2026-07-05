# Read the Room

## LLM-Based Filesystem Intelligence for Targeted Sensitive Data Discovery

**Adhithya Rajasekaran**
**ACM SecDev 2026 · Montréal**

---

## Core Idea

Every file starts **closed**.

Read the Room evaluates a metadata-first approach to sensitive data discovery. Instead of opening every file, the system first inventories a filesystem using **metadata-only MCP tools**:

* Directory structure
* File names
* Extensions
* Permissions
* Sizes
* Path context

It then scores every path, selects a small candidate set, and opens content only for those selected files. Every decision is logged.

> The central research question:
> **Should discovery systems be judged only by what they find, or also by what they had to read to find it?**

---

## Version Status

| Component                          |              Status | Description                                                                                                                |
| ---------------------------------- | ------------------: | -------------------------------------------------------------------------------------------------------------------------- |
| **v1 system**                      |           Available | FastAPI application mounted as an MCP server using `fastapi_mcp`                                                           |
| **v1 tools**                       |           Available | 15 tools for filesystem inspection, graph-based risk scoring, candidate selection, targeted scanning, and analyst feedback |
| **v1 evaluation harness**          |           Available | Plants synthetic ground truth and compares selective scanning against an exhaustive baseline                               |
| **v2 evaluation system**           |      In development | Deterministic FS-BOM read gate over synthetic 5K / 10K corpora with seeded variants and adversarial evasion sets           |
| **ACM SecDev 2026 poster figures** | Poster-only for now | Report v2-generation experiments and are not yet reproducible from this repository                                         |

> **Important reproducibility note**
> This repository currently contains the **v1 system**.
> The ACM SecDev 2026 poster reports the subsequent **v2 evaluation generation**.
> Until v2 lands in this repository, the poster’s exposure and adversarial figures are **not reproducible from this tree**. We state this plainly rather than implying otherwise.

---

## Provenance and Roles

| Workstream                         | Contributors                                                                 |
| ---------------------------------- | ---------------------------------------------------------------------------- |
| Research idea                      | **Adhithya Rajasekaran**                                                     |
| System design                      | **Adhithya Rajasekaran**                                                     |
| Evaluation methodology             | **Adhithya Rajasekaran**                                                     |
| ACM SecDev 2026 poster             | **Adhithya Rajasekaran**, sole author                                        |
| Code implementation                | Lakshman Shanmugam                                                           |
| Evaluation execution               | Lakshman Shanmugam                                                           |
| v2 paper / full implementation WIP | Lakshman Shanmugam, Adhithya Rajasekaran, Dhinakaran, Navya, Kishore, Balaji |

---

## Research Lineage

| Stage  | Output                                         | Ownership                                                   |
| ------ | ---------------------------------------------- | ----------------------------------------------------------- |
| **v1** | Poster and initial research prototype          | Adhithya Rajasekaran                                        |
| **v2** | Full implementation and paper work-in-progress | Lakshman + Adhithya + Dhinakaran + Navya + Kishore + Balaji |

---

## License, Preprint, and Contact

| Item     | Details                                     |
| -------- | ------------------------------------------- |
| License  | MIT — see `LICENSE`                         |
| Preprint | Forthcoming — arXiv endorsement in progress |
| Contact  | `rajasekaran.adhit@gmail.com`               |
| LinkedIn | `linkedin.com/in/adhi1991`                  |

---

## Documentation

| Document                | Purpose                                                                           |
| ----------------------- | --------------------------------------------------------------------------------- |
| `docs/SYSTEM_GUIDE.md`  | Full v1 system guide: architecture, install, API/tool reference, MCP client usage |
| `eval/README.md`        | Evaluation harness instructions                                                   |
| `EXPERIMENTATION.md`    | Experimentation notes and methodology                                             |
| `eval/FIXTURES_NOTE.md` | Notes about intentionally planted synthetic secrets                               |

---

# Picked Up the Leaflet at SecDev?

This section decodes the leaflet shorthand and scopes every number precisely.

The print version is frozen.
This page is the living clarification.

---

## Leaflet Legend: The “Model-Assisted Lane” Line

Example leaflet line:

```text
Flask 273f · A:273 0.71 0/2 · B:100 0.71 0/2 · C(LLM+MCP):8 1.00 2/2
```

This should be read as:

```text
files opened · precision · context traps suppressed
```

on a single Flask fixture.

| Lane  | Meaning                | Files Opened | Precision | Context Traps Suppressed |
| ----- | ---------------------- | -----------: | --------: | -----------------------: |
| **A** | Read-all baseline      |          273 |      0.71 |                    0 / 2 |
| **B** | Heuristic shortlist    |          100 |      0.71 |                    0 / 2 |
| **C** | Bounded LLM + MCP lane |            8 |      1.00 |                    2 / 2 |

### What this number means

The reduction from **273 files opened to 8 files opened** is a **97% reduction**.

But this is a **single-fixture illustration**, not a scaled benchmark.

| Figure             | Applies To                                |
| ------------------ | ----------------------------------------- |
| **97% reduction**  | Single Flask fixture: 273 → 8             |
| **~75% reduction** | v2 deterministic gate on 5K / 10K corpora |

> These are different experiments.
> They should not be conflated.

---

## Two Trap-Suppression Numbers, Two Different Experiments

The leaflet contains two trap-related numbers that refer to different experiments.

|    Number | Experiment                                      | Meaning                                                                                                               |
| --------: | ----------------------------------------------- | --------------------------------------------------------------------------------------------------------------------- |
|   **0.1** | v2 deterministic metadata gate at 5K-file scale | Weak decoy suppression. Metadata alone often cannot distinguish a test card in `/tests/` from a real card in `/src/`. |
| **2 / 2** | Bounded LLM lane on the single Flask fixture    | The LLM lane can reason about context and suppress both fixture decoys.                                               |

> Whether LLM-lane trap suppression holds at scale is future work.

---

## Recall: Base Positives vs. Adversarial Set

The poster separates two different evaluation groups:

| Evaluation Group            | Meaning                                                             |                                                       Result |
| --------------------------- | ------------------------------------------------------------------- | -----------------------------------------------------------: |
| **Base planted positives**  | Realistic seeded secrets across source profiles and corpus scales   |                                                  100% recall |
| **Adversarial evasion set** | Deliberately crafted trap cases designed to defeat metadata signals | Partial recall, with misses concentrated in S3-like profiles |

### Adversarial Evasion Set

| Metric                          | Value |
| ------------------------------- | ----: |
| Total trap cases                | 2,730 |
| Seeds                           |    10 |
| Trap cases per seed             |   273 |
| S3-like cases per seed          |   107 |
| Misses per seed                 |    23 |
| Total misses                    |   230 |
| Total caught                    | 2,500 |
| Aggregate caught rate           | 91.6% |
| S3-like adversarial recall      | 78.5% |
| Repository profile recall       |  100% |
| Local filesystem profile recall |  100% |
| Shared-drive profile recall     |  100% |

The missed cases are all in the **S3-like profile**.

Flat namespaces with opaque object keys carry little or no path semantics. That is the mapped boundary of metadata-first triage, not a hidden failure.

---

## Erratum: Poster Section 04

The printed poster headline says:

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
| Correct aggregate                  | **91.6%** |

---

## Terminology Note: “Trap” Appears Twice

The word **trap** appears in two different senses.

| Term                 | Meaning                       | Desired System Behavior |
| -------------------- | ----------------------------- | ----------------------- |
| **Trap cases**       | Adversarial evasion positives | Catch them              |
| **Trap suppression** | Planted fixture decoys        | Skip them               |

> Evasion traps are things the system should catch.
> Decoy traps are things the system should ignore.

---

# Leaflet Terms

| Term                        | Meaning                                                                                                                         |
| --------------------------- | ------------------------------------------------------------------------------------------------------------------------------- |
| **5K / 10K**                | Synthetic corpora. The evaluated file counts are 4,700 and 9,333 respectively; non-evaluable files are excluded.                |
| **M10**                     | 10-seed evaluation matrix                                                                                                       |
| **10 seeds → 25.2–25.7%**   | Seeds randomize fixture generation, not the gate. The gate is deterministic and reproduces byte-identically on a fixed fixture. |
| **516-row checksums**       | Fixture integrity manifest pinning every evaluation file by hash                                                                |
| **195 tests**               | v2 test suite across macOS and WSL2                                                                                             |
| **Deployment profiles A–E** | Endpoint DLP assist, code and secret scanning, privacy discovery, compliance evidence review, and org-controlled inference      |
| **FS-BOM score `sᵢ`**       | Hand-weighted metadata heuristic with zero training                                                                             |

---

## Deployment Profiles A–E

These are distinct from the A / B / C lanes used in the single-fixture leaflet illustration.

| Profile | Deployment Use Case               |
| ------- | --------------------------------- |
| **A**   | Endpoint DLP assist               |
| **B**   | Code and secret scanning          |
| **C**   | Privacy discovery across drives   |
| **D**   | Compliance evidence review        |
| **E**   | Organization-controlled inference |

Each profile shares an access-boundary idea, but each requires separate validation.

---

## FS-BOM Score

The FS-BOM score `sᵢ` is a hand-weighted heuristic computed from path and stat metadata only.

```text
sᵢ =
0.45 · path-keywords
+ 0.25 · extension
+ 0.15 · world-readable
+ 0.15 · size-vs-budget
```

| Signal                    | Weight | Source                   |
| ------------------------- | -----: | ------------------------ |
| Path keywords             |   0.45 | Path / filename metadata |
| Extension                 |   0.25 | File extension           |
| World-readable permission |   0.15 | Permission metadata      |
| Size-vs-budget            |   0.15 | File size metadata       |

No file content is read to compute this score.

---

# Enforcement

The leaflet phrase:

```text
Enforced by the protocol
```

is shorthand.

More precisely, the mechanism is:

> **Capability subsetting at the MCP tool manifest.**

During the inventory phase, the system mounts only structure-oriented tools. Every capability is a discrete, named, loggable call.

The v2 run against the official Filesystem MCP server:

```text
version / commit: ___
tools: 14
transport: stdio
```

recorded:

```text
zero content-read calls
```

verified from the tool-call log.

`search_files` performs name/path matching only in the pinned version. It does not perform content grep.

---

# Metadata Is Not Privacy-Neutral

The FS-BOM is **content-free**, not **metadata-free**.

Paths, filenames, owners, timestamps, permissions, and directory structure can themselves reveal sensitive or personal information.

The claim is therefore limited and precise:

> Metadata-first discovery creates a strictly smaller exposure surface than read-all scanning.
> It does not create zero exposure.

The inventory phase inherits the same access boundary and audit logging expectations as content reads.

---

# Sources and Baselines

## Production DLP False Positives

The “80%+ false positives” problem statistic follows Ponemon Institute reporting of **50–80% false-positive rates** in production DLP deployments. The leaflet uses the upper bound.

---

## Local Scanner Baselines

Poster Section 05 compares against local scanner baselines.

| Scanner        | Recall | Precision | Trap Score |
| -------------- | -----: | --------: | ---------: |
| Gitleaks       |   0.16 |      0.65 |       0.88 |
| TruffleHog     |   0.16 |      0.96 |       1.00 |
| detect-secrets |   0.14 |      0.56 |       0.90 |

These are secret scanners.

The ground truth in Read the Room spans:

* PII
* PHI
* Card-data families
* Secrets
* Compliance-sensitive files

Some of these are outside the detection scope of traditional secret scanners.

> The contribution is not “out-detecting” these tools.
> The contribution is the access boundary and exposure accounting that these tools generally lack.

---

# What Is in This Repository Today

This repository currently contains the **v1 selective DLP system**.

## v1 System Flow

```text
Phase 1: Metadata-only structural analysis
        ↓
Phase 2: Risk scoring and candidate selection
        ↓
Phase 3: Targeted content scanning and analyst feedback
```

---

## Phase 1: Metadata-Only Structural Analysis

The system first inventories the filesystem without reading file content.

| Reads Content? | What It Uses                                                   |
| -------------- | -------------------------------------------------------------- |
| No             | Structure, names, extensions, permissions, sizes, path context |

---

## Phase 2: Risk Scoring and Candidate Selection

The system scores paths using multiple metadata-derived and structural signals.

| Signal Type        | Example                                               |
| ------------------ | ----------------------------------------------------- |
| Keyword signal     | `finance`, `identity`, `patient`, `secret`, `payroll` |
| Semantic inference | Path-level context suggesting sensitive purpose       |
| Graph centrality   | Files connected to high-risk folders or clusters      |
| Metadata signal    | Extension, permissions, size, ownership               |

By default, the system selects roughly the top **5%** of candidates for content scanning.

---

## Phase 3: Targeted Content Scanning and Feedback

Only selected candidates are opened for content inspection.

The system then performs:

* Targeted content scanning
* Compliance validation
* Analyst feedback collection
* Adaptive scoring-weight updates

---

## Interfaces

The v1 system is exposed through both:

| Interface   | Purpose                               |
| ----------- | ------------------------------------- |
| HTTP routes | Direct API usage                      |
| MCP tools   | Agent/tool-based filesystem workflows |

---

## Evaluation Harness

The `eval/` harness:

* Seeds synthetic ground truth
* Runs selective scanning
* Runs exhaustive baseline scanning
* Compares results

It reports:

| Metric          | Meaning                                        |
| --------------- | ---------------------------------------------- |
| Recall          | How many planted positives were found          |
| Precision       | How many flagged items were true positives     |
| Scan reduction  | How many fewer files were opened               |
| Wall-clock time | Runtime comparison against exhaustive scanning |

---

# Note for Scanner Authors

This repository intentionally contains synthetic secrets in its evaluation seeder.

See:

```text
eval/FIXTURES_NOTE.md
```

If your scanner flags them, it is working as intended.

It is also incidentally demonstrating the context-blindness that this project studies.

---

# Cite

```text
A. Rajasekaran,
"Read the Room: LLM-Based Filesystem Intelligence for Targeted Sensitive Data Discovery,"
poster, ACM SecDev 2026.
Preprint forthcoming.
```

---

## Final Note

If you run this on a real corpus, failure reports are worth more than stars.
