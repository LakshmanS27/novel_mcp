# Submission Tracker

## Active Submissions

### 1. AGNTCon + MCPCon Europe 2026
- **Deadline:** June 8, 2026 at 11:59 PM CEST
- **Format:** 25-minute Session Presentation (talk, not paper)
- **Platform:** Sessionize
- **Track:** MCP & Agent Protocols → MCP Server Design Patterns
- **Authors:** Adhithya Rajasekaran, Lakshman Shanmugam
- **Status:** Proposal drafted (`agntcon-mcpcon-proposal.md`)
- **Link:** https://events.linuxfoundation.org/agntcon-mcpcon-europe/program/cfp/

### 2. APF 2026 (Annual Privacy Forum)
- **Deadline:** Abstract submitted (Feb 24). Full paper deadline TBD.
- **Format:** Full paper (Springer LNCS)
- **Location:** Salzburg, Austria — Sep 9-10, 2026
- **Theme:** "10 Years of GDPR"
- **Authors:** Adhithya Rajasekaran, Kishore B, Lakshman S, Dhinakaran T, Balaji P
- **Title:** "Stop Scanning Everything: A Privacy-Respecting Architecture for Context-Aware Enterprise Compliance Discovery"
- **Status:** Abstract accepted/submitted. Full paper uses `paper-v1.md` as base.

### 3. ICISS 2026 (Intl. Conf. on Information Systems Security)
- **Deadline:** July 10, 2026
- **Format:** Full paper
- **Location:** CMI Chennai, India — Dec 16-20, 2026
- **Authors:** Adhithya Rajasekaran, Lakshman Shanmugam
- **Status:** Paper v1 drafted. Needs ICISS formatting + polish.
- **Link:** https://iciss.in/cfp/

### 4. ACM TOPS (Transactions on Privacy and Security)
- **Deadline:** Rolling (no deadline)
- **Format:** Journal paper (20-30 pages)
- **Authors:** Adhithya Rajasekaran, Lakshman Shanmugam
- **Status:** Planned for ~Oct 2026. Expand paper-v1 with ablation study, 20+ repos, statistical tests, threat model. Needs 30%+ new content over conference version.

## Potential Future Venues

| Venue | Deadline | Location | Notes |
|-------|----------|----------|-------|
| AGNTCon + MCPCon North America | Jun 8, 2026 | San Jose, CA | Same CFP as Europe |
| MCP Dev Summit Mumbai | TBA (~May?) | Mumbai, India | Talks/demos, co-located with KubeCon India |
| ACSAC 2026 | ~Jun 2026 (est.) | Los Angeles | Applied security, check CFP site |
| NDSS 2027 Cycle 2 | Jul 30 / Aug 6, 2026 | San Diego | Top-tier, network/system security |
| IEEE TDSC | Rolling | — | Journal, secure systems architecture |

## Paper Files

| File | Format | Purpose |
|------|--------|---------|
| `paper-v1.md` | Markdown | Primary draft, all conferences |
| `paper-v1.tex` | LaTeX | ICISS / ACM TOPS submission |
| `paper-v1.docx` | Word | Sharing with co-authors |
| `agntcon-mcpcon-proposal.md` | Markdown | AGNTCon talk proposal for Sessionize |

## Evaluation Data

Reports in `eval/reports/`. Run the harness to add more:

```bash
python -m eval.run_evaluation /path/to/repo
```

| Repo | Source | Files | Scan Reduction | Recall | Precision |
|------|--------|------:|---------------:|-------:|----------:|
| Flask | GitHub | 235 | 94.9% | 0.40 | 1.00 |
| Django | GitHub | 6,944 | 95.0% | 0.80 | 1.00 |
| Kshetra | Local | 505 | 94.8% | 0.80 | 1.00 |
| veriflow | Local | 523 | 94.8% | 0.40 | 1.00 |
| Yukthi | Local | 4,150 | 95.0% | 0.80 | 1.00 |
| fairmind | Local | 29,339 | 95.0% | 0.80 | 1.00 |

**Mean: 94.9% scan reduction, 0.67 recall, 1.00 precision**
