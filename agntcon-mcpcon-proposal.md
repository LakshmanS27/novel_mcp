# AGNTCon + MCPCon Europe 2026 — Talk Proposal

> Deadline: June 8, 2026 at 11:59 PM CEST
> Submit via: Sessionize
> Format: Session Presentation (25 min)

---

## Title

Read the Room, Not the Files: Using MCP to Build a Privacy-Respecting Compliance Scanner

## Track

**MCP & Agent Protocols** (sub-topic: MCP Server Design Patterns)

Secondary: **Security and Privacy**

## Abstract (for Sessionize)

Enterprise compliance tools scan every file to find sensitive data. On a developer machine with 30,000 files, fewer than 500 matter. We built an MCP server that flips this: it exposes filesystem metadata as tools — directory structure, filenames, permissions, file sizes — and lets an LLM agent decide what's worth scanning before any file contents are read.

The server is a FastAPI application converted to 15 MCP tools via fastapi_mcp. Four tools inspect filesystem structure (no content access). Four compute risk scores using a networkx graph of the filesystem. Four perform targeted scanning — but only on files the agent selects. The remaining tools handle analyst feedback that adapts scoring weights over time.

The key design pattern: the MCP tool boundary enforces privacy by construction. Phase 1 and Phase 2 tools physically cannot read file contents. The agent orchestrates which tools to call and in what order — metadata-only tools first, content tools last and only on the top 5%.

We evaluated this on six real codebases (235 to 29,000 files). Result: 95% of files are never opened. Every file the system flagged was a real violation (100% precision). The baseline scanner that reads everything flagged test card numbers and placeholder credentials as violations — 29% false positive rate.

This talk covers the MCP server architecture, the tool boundary pattern for privacy enforcement, the risk scoring graph, and lessons from building a real agent workflow where the LLM is the orchestrator and the MCP server is the stateless tool layer.

## Key Takeaways

1. **MCP tool boundaries as a privacy mechanism** — structurally preventing content access in early analysis phases, not just by policy but by which tools are exposed
2. **Practical MCP server design pattern** — FastAPI routes to MCP tools via fastapi_mcp, with 15 tools organized into filesystem/intelligence/scanning/feedback categories
3. **Real evaluation numbers** — 95% scan reduction, 100% precision, 3x–165x speedup across six repositories
4. **Agent orchestration pattern** — LLM client decides the tool sequence, server stays stateless and deterministic

## Outline (25 minutes)

| Time | Section |
|------|---------|
| 0–3 min | The problem: DLP scans everything, 80% false positives, privacy paradox |
| 3–8 min | Architecture: 15 MCP tools in 4 categories, tool boundary diagram |
| 8–13 min | Live demo or walkthrough: agent analyzes a repo, selects candidates, scans only those |
| 13–18 min | Results: 6 repos, 95% reduction, precision/recall tradeoff |
| 18–22 min | Design patterns: tool boundary for privacy, feedback loop, model-agnostic deployment |
| 22–25 min | Q&A |

## Speaker Bio

**Adhithya Rajasekaran** is a security engineer and independent researcher focused on AI-assisted compliance tooling. His recent work includes closed-loop systems connecting security scanners to AI agent instruction files (evaluated across 108 trials with statistically significant vulnerability reduction), and MCP-based architectures for privacy-respecting data loss prevention. He contributes to open-source security tooling and has published on cross-jurisdictional privacy engineering covering GDPR, India's DPDP Act 2023, and the EU AI Act.

**Lakshman Shanmugam** is a software engineer and the primary developer of the risk-aware MCP DLP server. He designed and implemented the FastAPI-to-MCP architecture, the networkx-based filesystem graph, and the adaptive risk scoring engine with feedback learning. His work focuses on building practical MCP server patterns for security-sensitive applications.

## Additional Notes for Reviewers

- Working open-source implementation: https://github.com/LakshmanS27/novel_mcp
- Evaluation harness included in the repo (PR #1) — reviewers can run it themselves
- No vendor pitch — this is an open-source research project
- Happy to do a live demo if AV setup allows terminal access
