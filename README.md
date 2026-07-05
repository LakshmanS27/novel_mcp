# Read the Room

**LLM-Based Filesystem Intelligence for Targeted Sensitive Data Discovery**
Adhithya Rajasekaran · ACM SecDev 2026 · Montréal

Every file starts **closed**. The system inventories a filesystem through metadata-only MCP tools — structure, names, extensions, permissions, sizes — scores every path, and opens file content only for the small selected set, with every decision logged. The question it evaluates: *judge discovery systems not only by what they find, but by what they read to find it.*

> **Versions — read this first.** This repository currently contains the **v1 system**: a FastAPI application mounted as an MCP server via `fastapi_mcp` (15 tools spanning filesystem inspection, graph-based risk scoring, candidate selection, targeted scanning, and analyst feedback), plus an evaluation harness that plants synthetic ground truth and compares selective scanning against an exhaustive baseline. The **ACM SecDev 2026 poster reports the subsequent (v2) evaluation generation** — a deterministic FS-BOM read gate over synthetic 5K/10K corpora with seeded variants and adversarial evasion sets. **v2 is under active development and will be released in this repository.** Until it lands, the poster's exposure and adversarial figures are not reproducible from this tree, and we state that plainly rather than imply otherwise.

**Provenance and roles.** The research idea, system design, and evaluation methodology are by **Adhithya Rajasekaran**, sole author of the ACM SecDev 2026 poster. **Lakshman Shanmugam** contributes code implementation and evaluation execution, and is collaborating on the v2 system currently in development here.

**License:** MIT (see `LICENSE`) · **Preprint:** forthcoming — the author is seeking arXiv endorsement · **Contact:** rajasekaran.adhit@gmail.com · [linkedin.com/in/adhi1991](https://linkedin.com/in/adhi1991)

V1 -> Poster + Inital research - Adhithya Rajasekaran
V2 + full Implemnetation -> Paper WIP - Lakshman + Adhithya + Dhinakaran + Navya + Kishore + Balaji

**Documentation:** full v1 system guide — architecture, install, API/tool reference, MCP client usage — lives in [`docs/SYSTEM_GUIDE.md`](docs/SYSTEM_GUIDE.md). Evaluation instructions: [`eval/README.md`](eval/README.md) and [`EXPERIMENTATION.md`](EXPERIMENTATION.md).

---

## Picked up the leaflet at SecDev?

This section decodes its shorthand and scopes every number precisely. The print is frozen; this page is the living version.

### Legend — the "Model-assisted lane" line

```
Flask 273f · A:273 0.71 0/2 · B:100 0.71 0/2 · C(LLM+MCP):8 1.00 2/2
```

reads as **files opened · precision · context traps suppressed** on a single Flask fixture: **A** read-all baseline (273 files, precision 0.71 = 5 true / 7 flagged, 0/2 traps suppressed), **B** heuristic shortlist (100 files, 0.71, 0/2), **C** bounded LLM+MCP lane (8 files, 1.00, 2/2). A single-fixture **illustration, not a scaled benchmark** — the 97% reduction (273→8) applies to this fixture only; the ~75% figure elsewhere on the leaflet is the v2 deterministic gate on the 5K/10K corpora. Different experiments; do not conflate.

### Two trap-suppression numbers, two experiments

**0.1** — the v2 deterministic metadata gate at 5K-file scale. Weak, and reported as such: metadata alone cannot reliably distinguish a test card in `/tests/` from a real card in `/src/`. **2/2** — the bounded LLM lane on the single fixture above, which *can* reason about context. Whether LLM-lane suppression holds at scale is named future work.

### Recall — base positives vs. adversarial set (and one erratum)

**100% recall** refers to **base planted positives** (realistic seeded secrets) across every source profile and both corpus scales. The **adversarial evasion set** is separate: **2,730 trap cases across 10 seeds (273 per seed, of which 107 per seed are S3-like)**, deliberately crafted to defeat metadata signals. **23 cases are missed per seed — 230 total — all in the S3-like profile** (S3-like adversarial recall **78.5%**; repository, local filesystem, and shared-drive profiles: 100%). Flat namespaces with opaque object keys carry no path semantics — that is the mapped boundary of metadata-first triage, not a hidden failure.

> **Erratum (poster §04).** The printed headline reads "92.7% of 2,730 trap cases caught." The correct aggregate is **91.6%** (2,730 − 230 = 2,500 caught; 2,500 / 2,730 = 91.6%). The caption ("230 of 2,730 missed"), the per-profile bars, and §07's "23 misses every seed" are the correct, mutually consistent figures.

**Terminology note — "trap" appears twice with opposite meanings.** *Trap cases* in the adversarial panel are **evasion positives the system should catch**. *Trap suppression* (0.1, §07) concerns **planted fixture decoys the system should ignore**. Evasion traps we want to catch; decoy traps we want to skip.

### Terms on the leaflet

**5K / 10K** — synthetic corpora (4,700 and 9,333 evaluated files respectively; non-evaluable files excluded). **M10** — the 10-seed evaluation matrix. **10 seeds → 25.2–25.7%** — seeds randomize *fixture generation*, not the gate; the gate is deterministic and reproduces byte-identically on a fixed fixture. **516-row checksums** — fixture integrity manifest pinning every evaluation file by hash. **195 tests** — v2 test suite (macOS + WSL2). **Deployment profiles A–E** — A endpoint DLP assist · B code & secret scanning · C privacy discovery (drives) · D compliance evidence review · E org-controlled inference; one shared access boundary, each requiring separate validation. Distinct from lanes A/B/C above. **FS-BOM score sᵢ** — hand-weighted heuristic, zero training: `0.45·path-keywords + 0.25·extension + 0.15·world-readable + 0.15·size-vs-budget`, computed on path/stat metadata only, never content.

### Enforcement, stated precisely

"Enforced by the protocol" on the leaflet cover is shorthand — the mechanism is **capability subsetting at the MCP tool manifest**: the inventory phase mounts structure-only tools, and every capability is a discrete, named, loggable call. The v2 run against the official Filesystem MCP server ([version/commit ___], 14 tools, stdio) recorded **zero content-read calls**, verified from the tool-call log; `search_files` performs name/path matching only — no content grep — in the pinned version.

### Metadata is not privacy-neutral

The FS-BOM is content-free, **not metadata-free**: paths, filenames, owners, and timestamps can themselves be personal data. The claim is a strictly *smaller* exposure surface, not zero exposure; the inventory inherits the same access boundary and audit logging as content reads.

### Sources

The "80%+ false positives" problem statistic follows Ponemon Institute reporting of 50–80% false-positive rates in production DLP deployments; the leaflet takes the upper bound.

**Local scanner baselines** (poster §05): Gitleaks rec 0.16 / prec 0.65 / trap 0.88 · TruffleHog 0.16 / 0.96 / 1.00 · detect-secrets 0.14 / 0.56 / 0.90. These are secret scanners; the ground truth spans PII, PHI, and card-data families outside their detection scope. The contribution claimed is the **access boundary and exposure accounting these tools lack — not out-detecting them.**

---

## What is in this tree (v1)

Three-phase selective DLP. **Phase 1:** metadata-only structural analysis — no content reads. **Phase 2:** risk scoring combining keyword, semantic-inference, graph-centrality, and metadata signals, selecting candidates (default top ~5%). **Phase 3:** targeted content scanning with compliance validation and analyst feedback that adapts scoring weights. Exposed simultaneously as HTTP routes and MCP tools. The `eval/` harness seeds synthetic ground truth and reports recall, precision, scan reduction, and wall-clock time against an exhaustive baseline.

**Note for scanner authors:** this repository intentionally contains synthetic secrets in its evaluation seeder — see [`eval/FIXTURES_NOTE.md`](eval/FIXTURES_NOTE.md). Any tool flagging them is working as intended, and is incidentally demonstrating the context-blindness this project addresses.

## Cite

A. Rajasekaran, "Read the Room: LLM-Based Filesystem Intelligence for Targeted Sensitive Data Discovery," poster, ACM SecDev 2026. Preprint forthcoming (arXiv endorsement in progress).

*If you run this on a real corpus, failure reports are worth more than stars.*
