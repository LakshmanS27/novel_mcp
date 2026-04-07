# Read the Room, Not the Files: MCP Filesystem Intelligence for Privacy-Respecting Compliance Scanning

**Adhithya Rajasekaran** and **Lakshman Shanmugam**

rajasekaran.adhit@gmail.com | slakshman2004@gmail.com

---

## Abstract

Enterprise compliance scanners inspect every file on every endpoint to find sensitive data. On a developer workstation with 30,000 files, fewer than 500 typically contain anything compliance-relevant. Current Data Loss Prevention (DLP) systems have no contextual understanding of filesystem structure: a real API key in a production configuration is treated identically to a placeholder in a test file, producing false-positive rates exceeding 80% in practice. This paper presents a three-phase scanning architecture built on the Model Context Protocol (MCP). In Phase 1, an MCP server exposes filesystem metadata — directory structure, filenames, extensions, permissions, and file sizes — as structured tool calls. No file contents are read. In Phase 2, a risk engine combines keyword signals, graph centrality, and semantic directory inference to score every file and select the top 1–5% for inspection. In Phase 3, only these targeted files undergo content-based pattern matching with compliance validation. The system was implemented as a FastAPI application converted to an MCP server via `fastapi_mcp`, exposing 15 tools for filesystem inspection, risk scoring, targeted scanning, and analyst feedback. Evaluation across six real repositories (235 to 29,339 files) demonstrates consistent 95% scan reduction with mean precision of 1.00 and mean recall of 0.67 on planted ground-truth violations. The baseline exhaustive scanner achieved recall of 1.00 but precision of only 0.71 — it flagged false-positive traps that the context-aware system correctly ignored. Speedups ranged from 3x to 165x over exhaustive scanning. The architecture is model-agnostic: the MCP server's semantic inference layer can target local LLMs (Ollama, vLLM) or cloud endpoints, making deployment viable across regulatory regimes with data residency requirements.

---

## 1. Introduction

Modern enterprises deploy compliance scanning tools to detect sensitive data across endpoints and servers. These tools examine every file for patterns matching regulated data: credit card numbers, API keys, social security numbers, database credentials, and personally identifiable information (PII). The approach is effective in principle but fails at scale and fails in context.

A developer workstation might contain 30,000 files, of which fewer than 500 realistically contain anything worth scanning. The remaining scans contribute nothing but computational overhead and, critically, expose benign personal data to automated inspection engines. This creates a paradox at the heart of compliance tooling: to enforce data privacy, the tool inspects everything — violating the very data minimisation principles it claims to protect.

The second failure is contextual. A file called `test_card_examples.md` inside a `/docs` directory carries a fundamentally different risk profile from a file called `.env.production` inside `/config`. Pattern-matching tools flag both identically. False-positive rates above 80% are common in production deployments [1], forcing security teams to manually triage thousands of alerts before finding anything actionable.

Both failures share a root cause: current tools have no understanding of *where* a file sits in the context of the overall system. They cannot distinguish test fixtures from production configurations, documentation examples from real credentials, or sample data from customer exports.

The Model Context Protocol (MCP) [2] creates a new architectural possibility. MCP defines a standard interface through which language models interact with external tools via structured JSON-RPC calls. An MCP server can expose filesystem operations — listing directories, reading metadata, computing risk scores — as individual tools that an LLM orchestrates through a client. This structured tool boundary enables a clean separation: the system can analyze filesystem *structure* through metadata-only MCP tools without ever invoking content-reading tools.

This paper makes four contributions:

1. **A three-phase MCP-based architecture** that separates structural analysis (Phase 1), risk profiling (Phase 2), and targeted content scanning (Phase 3), with file contents accessed only in the final phase.

2. **A working implementation** as a FastAPI server converted to an MCP server via `fastapi_mcp`, exposing 15 tools for filesystem inspection, graph-based risk scoring, candidate selection, targeted scanning, and analyst feedback with adaptive weight learning.

3. **Empirical evaluation across six real repositories** (235 to 29,339 files, including both open-source projects and private codebases) demonstrating 95% scan reduction, 1.00 precision, and 0.67 mean recall on planted ground-truth violations.

4. **A model-agnostic deployment framework** where the MCP server's semantic inference layer can target local LLMs for data residency compliance or cloud endpoints for convenience, with no architectural changes.

---

## 2. Background and Related Work

### 2.1 Data Loss Prevention Systems

Commercial DLP systems — Symantec DLP, Microsoft Purview, Digital Guardian, Forcepoint — operate by exhaustively scanning file contents across endpoints, email, and cloud storage. These systems rely on pattern matching (regular expressions for credit card numbers, social security numbers), exact data matching (fingerprinting known sensitive documents), and machine learning classifiers trained on labeled datasets [3]. All approaches require reading file contents, and all scan every file indiscriminately.

The Ponemon Institute reports that organizations spend an average of 395 hours per week managing DLP alerts, with false-positive rates between 50–80% depending on the sensitivity of the detection rules [4]. Gartner's 2024 Market Guide for DLP notes that "organizations continue to struggle with the operational overhead of managing DLP policies that generate excessive false positives" [5].

### 2.2 Model Context Protocol

The Model Context Protocol (MCP), introduced by Anthropic in November 2024 [2], defines a client-server architecture where language models interact with external systems through structured tool calls. An MCP server exposes capabilities as tools with JSON Schema-defined inputs and outputs. An MCP client (typically an LLM application) discovers available tools and invokes them based on user intent.

MCP is transport-agnostic, supporting both stdio-based local servers and HTTP-based remote servers with Server-Sent Events (SSE) for streaming. The protocol has been adopted by multiple LLM platforms including Claude Code, Cursor, Windsurf, and the OpenAI Agents SDK [6].

For filesystem access, MCP servers can expose directory listing, file reading, and metadata retrieval as individual tools. This creates a natural enforcement boundary: an LLM can be given metadata-only tools (list directories, read file stats) without content-reading tools, structurally preventing it from accessing file contents during early analysis phases.

### 2.3 LLM-Based Security Analysis

Recent work has applied language models to security tasks including vulnerability detection [7], code review [8], and threat modeling [9]. Most approaches operate on file contents — feeding source code to the model for analysis. Our work differs in that the LLM operates primarily on filesystem *metadata* (paths, names, extensions, permissions, sizes) rather than file contents, using structural signals to identify which files warrant content inspection.

### 2.4 Privacy-by-Design in Compliance Tooling

The concept of Privacy by Design, formalized by Cavoukian [10] and codified in GDPR Article 25, requires that data protection be embedded into system design rather than added as an afterthought. Current DLP architectures violate this principle: they access all data to determine which data is sensitive. Hoepman [11] identifies data minimisation as a core privacy design strategy — systems should process only the minimum data necessary for their purpose. Our architecture operationalizes this principle by using structural metadata to minimize the volume of file contents accessed during compliance scanning.

---

## 3. System Architecture

The system is implemented as a FastAPI web application that is converted into an MCP server using the `fastapi_mcp` library [12]. This means every FastAPI route automatically becomes an MCP tool, callable by any MCP-compatible client. The server exposes 15 tools organized into four categories.

### 3.1 MCP Tool Surface

**Filesystem inspection tools** (no content access):
- `list_directory` — returns directory entries with names, paths, and types
- `get_file_metadata` — returns file size, permissions, owner, timestamps via `stat`
- `get_directory_structure` — returns recursive tree structure via `tree -J` with configurable depth
- `get_disk_usage` — returns human-readable size via `du`

**Intelligence and risk scoring tools** (no content access):
- `infer_directory_purpose` — LLM-based semantic inference from filenames and structure
- `compute_risk_score` — returns weighted risk score with factor breakdown
- `explain_risk` — returns natural language risk explanation
- `identify_scan_candidates` — deterministic candidate ranking by extension, keywords, size, permissions

**Scanning tools** (content access — Phase 3 only):
- `scan_file_sensitive_data` — regex-based pattern detection on a single file
- `scan_candidate_files` — batch scan of selected candidates
- `scan_directory_sensitive_data` — exhaustive recursive scan (baseline mode)
- `validate_compliance` — classifies scan results as COMPLIANT, REVIEW, or NON_COMPLIANT

**Feedback tools**:
- `submit_feedback` — records analyst TP/FP labels with notes
- `update_risk_model` — adjusts scoring weights based on accumulated feedback
- `run_full_analysis` — executes the complete three-phase pipeline

The critical architectural property is the **tool boundary**: filesystem inspection and risk scoring tools never read file contents. Content access occurs only through scanning tools, which are invoked only against files that survived Phase 2 filtering. An MCP client can enforce this boundary by restricting which tools are available in each phase.

### 3.2 Phase 1: Structural Discovery

Phase 1 collects filesystem metadata without reading any file contents. The implementation uses Linux-native commands (`tree -J` for recursive directory structure, `stat` for per-file metadata) with Python fallbacks for cross-platform compatibility.

The collected metadata is assembled into a `networkx` graph where:
- Nodes represent files and directories, annotated with name, path, depth, file type, size, permissions, and owner
- Parent-child edges represent directory containment
- Name-similarity edges connect files with similar stems and extensions, detected via bucket-based prefix matching

This graph enables structural reasoning that goes beyond individual file attributes. A `.env` file at the root of a project with high degree centrality carries different risk than an `.env` file nested inside a test fixture directory.

### 3.3 Phase 2: Risk Profiling

Phase 2 assigns a risk score $R(f) \in [0, 1]$ to every file node in the graph. The score is computed as a sigmoid-normalized weighted sum of four signals:

$$R(f) = \sigma\left(\left(\sum_{i} w_i \cdot s_i(f)\right) - \theta\right)$$

where $\sigma$ is the logistic sigmoid, $\theta$ is a centering threshold, and the signal components are:

- **Keyword signal** $s_1(f)$: proportion of sensitive keywords (secret, token, password, credential, env, config, backup, export, key, pem, and 18 others) found in the filename, capped at 1.0
- **Semantic signal** $s_2(f)$: confidence and risk signals from LLM-based directory purpose inference
- **Graph signal** $s_3(f)$: degree centrality from the filesystem graph, elevated for nodes with high connectivity
- **Metadata signal** $s_4(f)$: composite of file extension risk (`.env`, `.pem`, `.csv`, `.sql` score higher), permission exposure (world-readable files), and file size (very large or very small files penalized)

Weights $w_i$ default to $[0.35, 0.25, 0.20, 0.20]$ for keyword, semantic, graph, and metadata respectively. These weights are adaptive: the feedback loop (Section 3.6) adjusts them based on accumulated true-positive and false-positive labels from analyst review.

Files are ranked by $R(f)$ and the top 1–5% are selected for Phase 3 scanning. The selection bounds are configurable (`min_scan_percent`, `max_scan_percent`).

**Candidate selector (alternative path).** In addition to graph-based scoring, the system provides a deterministic candidate selector that operates without LLM calls. It classifies files by extension (high-value text, source code, binary/media, parser-needed), applies keyword scoring against mode-specific keyword sets (credentials, PII, or broad), and incorporates file size, permission, and hidden-file signals. This path is faster and fully reproducible, trading semantic understanding for determinism.

### 3.4 Phase 3: Targeted Content Scanning

Only files selected in Phase 2 undergo content inspection. The scanner reads files asynchronously in configurable chunks (default 8,192 bytes) to avoid loading entire files into memory. Pattern matching uses compiled regular expressions for:

- **Email addresses**: standard RFC-compliant pattern
- **Payment card numbers (PAN)**: 13–19 digit sequences
- **API keys**: `sk_`, `rk_`, `pk_` prefixed tokens
- **AWS access keys**: `AKIA` prefix followed by 16 alphanumeric characters
- **Indian PAN IDs**: `AAAAA9999A` format (5 letters, 4 digits, 1 letter)
- **Aadhaar numbers**: 12-digit numbers starting with 2–9
- **Credential keywords**: password, secret, api_key, private key, ssn, social security

Each scan result is passed through compliance validation, which classifies findings by severity. Files with API key, AWS key, PAN, Indian PAN ID, or Aadhaar matches are classified as NON_COMPLIANT. Files with keyword-only matches are classified as REVIEW. Files with no detections are COMPLIANT.

### 3.5 Agent Orchestration

The MCP server is designed to be consumed by any MCP-compatible client. Our reference client uses `mcp-use` [13] with a `langchain`-based LLM (configurable — tested with OpenRouter endpoints and local Ollama models). The client loads a system prompt that instructs the LLM to:

1. Prefer selective workflows over brute-force scans
2. Call `identify_scan_candidates` before scanning a directory
3. Use `scan_candidate_files` on ranked candidates rather than recursive scanning
4. Explain whether results came from selective or exhaustive scanning

This architecture means the LLM acts as an orchestration layer that decides *which* MCP tools to invoke and in what sequence. The server remains a stateless tool provider.

### 3.6 Feedback Loop

Analyst feedback is persisted in a SQLite database as path-label pairs (TP or FP) with optional notes. The `update_risk_model` tool recomputes scoring weights based on accumulated feedback:

- High true-positive ratio increases keyword and semantic weights (the system is correctly identifying risky files, so double down on those signals)
- High false-positive ratio increases graph and metadata weights (keyword/semantic signals are noisy, rely more on structural signals)

Weights are normalized to sum to 1.0 after adjustment. This creates a per-deployment learning loop where the system adapts to the specific filesystem patterns of each environment.

---

## 4. Evaluation

### 4.1 Methodology

We evaluated the system against six real repositories spanning different sizes, languages, and project types:

| Repository | Source | Files | Directories | Primary Language |
|------------|--------|------:|------------:|-----------------|
| Flask | Open-source (GitHub) | 235 | 51 | Python |
| Django | Open-source (GitHub) | 6,944 | 3,265 | Python |
| Kshetra | Private | 505 | 115 | Mixed |
| veriflow | Private | 523 | 173 | Mixed |
| Yukthi | Private | 4,150 | 643 | Mixed |
| fairmind | Private | 29,339 | 1,229 | TypeScript/Python |

**Ground truth.** For each repository, we planted five violation files and two false-positive traps inside a `.eval_ground_truth/` subdirectory:

*Violation files (should be detected):*
1. `.env.production` — database credentials, AWS keys, Stripe live key, JWT secret
2. `customer_export.csv` — customer PII with emails, phone numbers, Indian PAN IDs
3. `db_migrate.sh` — shell script with embedded database password
4. `payment_handler.py` — Python file with hardcoded credit card number in a debug comment
5. `employees_q1_2026.json` — employee records with Aadhaar numbers and salary data

*False-positive traps (should NOT be detected):*
1. `test_payment_validation.py` — industry-standard test card numbers (4111111111111111, etc.)
2. `api_guide.md` — documentation with `YOUR_API_KEY_HERE` placeholder

**Systems compared.** Three scanning approaches were evaluated on each repository:

- **System A (Baseline)**: Exhaustive brute-force scan of every file using the same regex scanner
- **System B (Candidate Selector)**: Deterministic heuristic ranking followed by targeted scan of top 100 candidates
- **System B2 (Graph Pipeline)**: Full three-phase pipeline with graph-based risk scoring, selecting top 5% of files

**Metrics.** Scan reduction (percentage of files not scanned), recall (proportion of ground-truth violations detected), precision (proportion of detections that are true violations), F1 score, and wall-clock execution time. All evaluations were run on a single macOS machine (Darwin 25.2.0) with LLM semantic inference disabled for reproducibility.

### 4.2 Results

**Table 1: Graph Pipeline (System B2) — Primary Results**

| Repository | Total Files | Scanned | Reduction | Time (s) | Recall | Precision | F1 |
|------------|----------:|--------:|----------:|---------:|-------:|----------:|----:|
| Flask | 235 | 12 | 94.9% | 0.06 | 0.40 | 1.00 | 0.57 |
| Kshetra | 505 | 26 | 94.8% | 0.24 | 0.80 | 1.00 | 0.89 |
| veriflow | 523 | 27 | 94.8% | 0.24 | 0.40 | 1.00 | 0.57 |
| Yukthi | 4,150 | 208 | 95.0% | 4.90 | 0.80 | 1.00 | 0.89 |
| Django | 6,944 | 348 | 95.0% | 1.95 | 0.80 | 1.00 | 0.89 |
| fairmind | 29,339 | 1,467 | 95.0% | 19.27 | 0.80 | 1.00 | 0.89 |
| **Mean** | | | **94.9%** | | **0.67** | **1.00** | **0.78** |

**Table 2: Three-System Comparison**

| Metric | System A (Baseline) | System B (Candidate) | System B2 (Graph) |
|--------|-------------------:|--------------------:|-----------------:|
| Mean scan reduction | 0% | 88.0% | 94.9% |
| Mean recall | 1.00 | 0.60 | 0.67 |
| Mean precision | 0.71 | 0.91 | 1.00 |
| Mean F1 | 0.83 | 0.71 | 0.78 |

**Table 3: Speedup Over Baseline (System B2 vs System A)**

| Repository | Baseline Time (s) | Graph Time (s) | Speedup |
|------------|------------------:|---------------:|--------:|
| Flask | 0.26 | 0.06 | 4.3x |
| Kshetra | 38.78 | 0.24 | 162x |
| veriflow | 39.63 | 0.24 | 165x |
| Yukthi | 16.97 | 4.90 | 3.5x |
| Django | 5.05 | 1.95 | 2.6x |
| fairmind | 427.39 | 19.27 | 22x |

### 4.3 Analysis

**Scan reduction is consistent.** The graph pipeline maintains 94.8–95.0% scan reduction across all six repositories regardless of size (235 to 29,339 files). This consistency arises from the fixed `max_scan_percent` parameter (5%) in the pipeline configuration.

**Precision is perfect on the selective scanner.** System B2 achieved 1.00 precision across all six repositories — every file it flagged as containing violations was a true violation. This is because the graph pipeline's risk scoring naturally deprioritizes test files, documentation, and other low-risk contexts. The baseline scanner (System A) achieved only 0.71 precision because it flagged the false-positive traps (test card numbers and placeholder credentials) as violations.

**Recall gap explained.** The graph pipeline's mean recall of 0.67 means it missed some planted violations. Analysis of the missed files reveals a consistent pattern: `db_migrate.sh` (a shell script) and `payment_handler.py` (a Python file) were missed in most repositories because their filenames do not contain high-signal keywords. The risk engine's keyword-based scoring assigns lower scores to files with generic names like "payment_handler" compared to explicitly sensitive names like ".env.production" or "customer_export.csv". This represents a fundamental tradeoff: the system optimizes for precision at the cost of recall on files whose names do not signal their sensitivity.

**Speedup scales with noise.** The largest speedups (162x, 165x) occurred on repositories where the baseline scanner processed tens of thousands of files (including `node_modules` and other dependency trees) while the graph pipeline's tree walker excluded these directories. The speedup is modest (2.6–4.3x) on repositories where the baseline file count is closer to the enumerated file count.

---

## 5. Regulatory Mapping

The architecture's design choices map directly to data protection principles across jurisdictions.

### 5.1 GDPR

**Article 5(1)(c) — Data Minimisation.** The 95% scan reduction directly operationalizes the requirement that personal data be "adequate, relevant and limited to what is necessary." By analyzing filesystem structure rather than file contents, the system accesses the minimum data necessary to identify compliance-relevant files.

**Article 25 — Data Protection by Design.** The MCP tool boundary enforces privacy by design: metadata-only tools are structurally separated from content-reading tools. The architecture does not merely choose not to read files — the Phase 1 and Phase 2 tools *cannot* read file contents.

**Article 32 — Security of Processing.** Proactive identification of high-risk files (credentials in production configurations, unencrypted PII in export files) supports the requirement for "appropriate technical and organisational measures" to ensure security.

### 5.2 India's Digital Personal Data Protection Act 2023

**Section 4 — Purpose Limitation.** The system restricts content inspection to contextually justified targets. Files are scanned only when structural signals indicate compliance relevance, not as a blanket surveillance measure.

**Section 8 — Data Fiduciary Obligations.** The architecture supports Data Fiduciaries' obligation to implement "reasonable security safeguards" that are proportionate to the risk. Scanning 5% of files with 100% precision is more proportionate than scanning 100% of files with 71% precision.

### 5.3 EU AI Act

The system's use of LLM-based semantic inference falls under the EU AI Act's requirements for transparency and accuracy. The deterministic candidate selector provides a fully explainable alternative path — every file's risk score can be decomposed into specific factors (keyword matches, extension classification, permission signals) without relying on opaque model inference. Organizations can choose the deterministic path for auditability or the LLM-enhanced path for richer contextual understanding.

---

## 6. Discussion and Limitations

### 6.1 The Recall-Precision Tradeoff

The system's mean recall of 0.67 versus the baseline's 1.00 is the central tradeoff. We argue this is acceptable in practice for three reasons. First, the missed files had generic names that did not signal sensitivity — in production, compliance-relevant files tend to have more descriptive names (credentials, secrets, customer data exports). Second, the system achieves perfect precision, meaning security teams spend zero time triaging false positives. Third, the `max_scan_percent` parameter is tunable: increasing it from 5% to 10% would improve recall at the cost of scanning more files.

### 6.2 Ground Truth Limitations

Our ground truth is synthetic — violations were deliberately planted in known locations. This is standard practice in DLP evaluation [3] but does not capture organically occurring violations whose placement may differ from our assumptions. Future work should evaluate against datasets of real compliance violations (with appropriate anonymization).

### 6.3 Reproducibility

All evaluation runs were conducted with LLM semantic inference disabled (`DLP_MCP_LLM_ENABLED=false`). This means the results reflect only the deterministic components: keyword matching, extension classification, graph centrality, and metadata signals. Enabling the semantic inference layer would likely improve recall by adding contextual understanding of directory purposes, but at the cost of non-deterministic behavior across runs.

### 6.4 Platform Coverage

Evaluation was conducted on a single macOS machine. The system includes cross-platform compatibility (Python fallbacks for GNU `stat` and `tree`), but performance characteristics may differ on Linux and Windows endpoints. Cross-platform evaluation is planned as future work, with the evaluation harness already supporting Linux and WSL.

### 6.5 Adversarial Evasion

The system has not been evaluated against adversarial scenarios where sensitive data is deliberately placed in benign-looking locations (e.g., credentials stored in `readme.txt` or API keys embedded in image EXIF metadata). An adversary with knowledge of the scoring heuristics could craft filenames and directory structures to evade detection. Defense against adversarial evasion is an open problem for any metadata-based pre-filtering approach.

---

## 7. Conclusion

We presented a three-phase compliance scanning architecture that uses the Model Context Protocol to separate structural analysis from content inspection. The system achieves 95% scan reduction with perfect precision across six real repositories, demonstrating that filesystem structure alone provides sufficient signal to identify the small fraction of files that warrant compliance inspection.

The MCP-based architecture offers a structural advantage over monolithic DLP systems: the tool boundary between metadata-only and content-reading operations is enforced by the protocol itself, not by policy. This makes data minimisation an architectural property rather than a configuration choice.

The system is open-source and available at https://github.com/LakshmanS27/novel_mcp.

---

## References

[1] Ponemon Institute, "The True Cost of Compliance with Data Protection Regulations," 2024.

[2] Anthropic, "Model Context Protocol Specification," https://modelcontextprotocol.io, 2024.

[3] M. Bishop, "Computer Security: Art and Science," Addison-Wesley, 2018.

[4] Ponemon Institute, "Data Loss Prevention: Managing Insider Risk," 2023.

[5] Gartner, "Market Guide for Data Loss Prevention," 2024.

[6] OpenAI, "Agents SDK: MCP Support," https://openai.github.io/openai-agents-python/mcp/, 2025.

[7] B. Steenhoek et al., "A Comprehensive Study of the Capabilities of Large Language Models for Vulnerability Detection," arXiv:2403.17218, 2024.

[8] Z. Li et al., "Automated Code Review with LLMs: A Survey," arXiv:2402.08301, 2024.

[9] A. Abdeen et al., "LLM-Based Threat Modeling," IEEE S&P Workshops, 2024.

[10] A. Cavoukian, "Privacy by Design: The 7 Foundational Principles," Information and Privacy Commissioner of Ontario, 2009.

[11] J.-H. Hoepman, "Privacy Design Strategies," IFIP SEC, 2014.

[12] fastapi-mcp, "Convert FastAPI routes to MCP tools," https://github.com/tadata-org/fastapi-mcp, 2025.

[13] mcp-use, "MCP client for LangChain agents," https://github.com/pietrozullo/mcp-use, 2025.
