# Security Network Builder

[![CI](https://github.com/locallhosts/security-network-builder/actions/workflows/ci.yml/badge.svg)](https://github.com/locallhosts/security-network-builder/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)

**Security Engineer Discovery and Intelligence Platform**

Discover, analyze, and rank engineers on GitHub by cybersecurity specialization, using technical signals instead of follower counts. Every recommendation comes with a score breakdown and the evidence behind it.

---

## Table of Contents

- [Overview](#overview)
- [Implementation Roadmap](#implementation-roadmap)
- [Key Features](#key-features)
- [Quick Start](#quick-start)
- [Usage](#usage)
- [Dashboard](#dashboard)
- [Public Platform](#public-platform)
- [Configuration](#configuration)
- [How It Works](#how-it-works)
- [Architecture](#architecture)
- [Security Domains](#security-domains)
- [Project Structure](#project-structure)
- [Development](#development)
- [Troubleshooting](#troubleshooting)
- [Security and Privacy](#security-and-privacy)
- [Responsible Use](#responsible-use)
- [Future Work](#future-work)
- [License](#license)

---

## Overview

Security professionals often want to build meaningful technical networks, but follower-based discovery rewards popularity, not expertise. Finding the right people by hand is slow.

GitHub holds strong signals of real engineering work: repositories, topics, languages, commit and review activity, and organization memberships. Security Network Builder turns those signals into a ranked, explainable list of engineers who work in the domains you care about.

**Who it is for**

- Security engineers who want a technically aligned professional network
- Detection, cloud, and runtime security practitioners looking for collaborators
- Open source contributors searching for maintainers in a specific domain
- Community builders and recruiters mapping security engineering ecosystems

**Design principles**

- **Expertise over popularity.** Star and follower contributions are capped so they cannot dominate a score.
- **Explainable.** Every point in a score is itemized and backed by evidence.
- **Read-only.** The tool never follows, stars, or messages anyone. Outreach is always your own decision.
- **Local-first.** Data stays on your machine; the optional AI features are opt-in.

---

## Implementation Roadmap

This roadmap is the **source of truth for the product**. We will implement it sequentially, verify every item locally, add tests, and only then mark it complete.

### Product standard

Security Network Builder is being built as a **real, public security-intelligence web platform**, not a mockup or static portfolio page.

Every feature must satisfy these rules:

1. **Real data** — no hard-coded users, repositories, scores, graph nodes, statistics, or fake API responses in production code.
2. **Evidence first** — every intelligence claim must be traceable to public source data or a deterministic calculation.
3. **Server-backed** — important filters, pagination, aggregation, and security controls must be enforced by the API.
4. **Exportable** — users must be able to take their own search and analysis results with them.
5. **Accessible** — graph information must also exist as structured data.
6. **Secure by default** — untrusted GitHub content is data, never executable instructions; secrets never reach the browser.
7. **Offline AI by default** — the platform works without an LLM. OpenAI and Anthropic are explicit opt-in integrations.
8. **Observable and testable** — public capabilities receive API, failure-path, security, and UI/contract coverage as appropriate.
9. **Honest product state** — a feature is not complete until it works against real data and passes acceptance criteria.
10. **Public-safe** — only intentionally public GitHub information is exposed; private notes, credentials, and internal operations stay protected.

### Phase 1 — Foundation
**Status: COMPLETE**

- [x] Core discovery and scoring foundation
- [x] Security profile and configurable domains
- [x] GitHub REST/GraphQL data collection
- [x] Explainable scoring and relationship graph foundation
- [x] Local history and reporting
- [x] Local dashboard foundation
- [x] Preflight/doctor checks
- [x] Security and privacy baseline

### Phase 2 — API
**Status: COMPLETE**

- [x] FastAPI application/configuration boundary
- [x] Health/readiness endpoints
- [x] Public web response and OpenAPI documentation
- [x] Public repository search
- [x] Public graph endpoint
- [x] Protected run/history/analysis endpoints
- [x] Input validation and bounded parameters
- [x] API-key authentication for private routes
- [x] Search rate limiting
- [x] GitHub URL validation and safe error handling
- [x] API regression/contract tests
- [x] Public engineer/user search endpoint
- [x] Repository search filters and server-side sorting

**Exit criteria:** public data is discoverable through stable, validated endpoints; private data remains protected; failures are deterministic and tested.

### Phase 3 — Web Platform
**Status: IMPLEMENTATION COMPLETE — VALIDATION GATE PENDING**

#### 3A. Professional public shell
- [x] Professional light/white visual system
- [x] Responsive desktop/tablet/mobile layout
- [x] Clear product navigation
- [x] Security-intelligence positioning and terminology
- [x] Accessibility audit and keyboard-only workflow
- [x] WCAG-oriented contrast/focus review
- [x] Browser compatibility verification
- [x] Consistent loading/skeleton states
- [x] Global error/retry UX

#### 3B. Real discovery
- [x] Repository search against GitHub
- [x] Language filtering
- [x] Minimum-star filtering
- [x] Server-backed pagination
- [x] Sort by stars, updated, forks, help-wanted and relevance
- [x] Engineer/user search against GitHub
- [x] Engineer sorting
- [x] Engineer → profile navigation
- [x] Repository → engineer navigation
- [x] CSV export
- [x] JSON export
- [x] Advanced query builder
- [x] Search history for the current browser session
- [x] Saved searches stored locally or behind authenticated storage
- [x] Search result quality/evidence panel
- [x] Result deduplication and stable ordering
- [x] Search API usage/rate-limit visibility

#### 3C. Engineer intelligence
- [x] Public engineer profile
- [x] Organizations
- [x] Public repositories
- [x] Public activity context
- [x] Score breakdown with evidence links
- [x] Security-domain classification
- [x] Skills/technology extraction from public repositories
- [x] Contribution/repository trend summaries
- [x] Repository quality and maintenance signals
- [x] Engineer-to-engineer relationship evidence
- [x] Profile comparison
- [x] Profile export
- [x] Shareable public profile URL without exposing private analysis

#### 3D. Network intelligence
- [x] Interactive relationship graph
- [x] Relationship weights
- [x] Community filtering
- [x] Centrality filtering
- [x] Node search
- [x] Dragging nodes
- [x] Relationship detail panel
- [x] Accessible graph-data fallback
- [x] SVG export
- [x] Graph JSON export
- [x] Zoom/pan controls with reset
- [x] Graph legend and relationship-type legend
- [x] Edge-type filters
- [x] Node-type filters
- [x] Highlight neighborhood and shortest-path exploration
- [x] Community summary cards
- [x] Centrality/top-node ranking table
- [x] Large-graph progressive rendering
- [x] Graph query parameters validated server-side
- [x] Deterministic graph snapshot export

#### 3E. Intelligence workspace
- [x] Investigation/workspace model
- [x] Add repositories and engineers to a workspace
- [x] Notes and evidence references
- [x] Tags and analyst status
- [x] Timeline of investigation changes
- [x] Export complete investigation bundle
- [x] Delete/clear workspace data
- [x] Explicit privacy boundary between public data and private analyst notes

#### 3F. Reporting and exports
- [x] Search report export
- [x] Engineer profile report export
- [x] Graph report export
- [x] Investigation bundle export
- [x] CSV
- [x] JSON
- [x] SVG
- [x] Human-readable Markdown
- [x] Optional PDF report generated locally/server-side (install the optional pdf extra)
- [x] Export metadata: query, timestamp, source, filters, schema version
- [x] No secrets or private notes in public exports

#### 3G. Public-platform operations
- [x] Public API usage documentation
- [x] Rate-limit status and friendly retry messages
- [x] Abuse protection
- [x] Request correlation IDs
- [x] Structured application logging
- [x] Metrics for search/graph/profile requests
- [x] Error monitoring hooks without collecting unnecessary personal data
- [x] Cache policy for safe public GitHub data
- [x] Explicit data freshness indicators
- [x] GitHub upstream outage/degraded-state UX

**Phase 3 exit criteria:** an unauthenticated visitor can perform real GitHub discovery, inspect evidence-backed engineer intelligence, explore a real relationship network, filter/export results, and understand freshness and limitations without accessing private data.

> **Validation gate:** Phase 3 implementation is complete on `feature/public-platform-foundation`. The remaining gate is the full local compile/test/browser validation pass; no deployment is implied by this status.

### Phase 4 — Intelligence Layer
**Status: COMPLETE CORE / EXTEND CAREFULLY**

- [x] OpenAI provider interface
- [x] OpenAI secret handling
- [x] Prompt/input boundaries
- [x] Output validation
- [x] Offline fallback
- [x] OpenAI failure tests
- [x] Anthropic provider interface
- [x] Anthropic secret handling
- [x] Prompt/input boundaries
- [x] Output validation
- [x] Offline fallback
- [x] Anthropic failure tests
- [x] Durable background jobs
- [x] Retry/idempotency controls
- [x] Job status API
- [x] Resource/rate-limit controls
- [x] Verify every public web intelligence feature has a deterministic non-AI path
- [x] Optional AI explanations in the investigation workspace
- [x] AI provenance indicator showing when text is AI-generated
- [x] AI request audit metadata without storing secrets
- [x] AI output regression tests against prompt-injection-shaped GitHub content

**AI contract:** offline remains the default. A remote provider is used only when explicitly configured and supplied with its required secret. No public visitor can silently cause an LLM request.

### Phase 5 — Production hardening
**Status: IMPLEMENTATION COMPLETE — DEPLOYMENT INTENTIONALLY DEFERRED**

#### 5A. Configuration
- [x] Production environment configuration
- [x] Fail-closed production secret validation
- [x] Safe default configuration
- [x] Offline AI default verified in production configuration
- [x] Separate public/private configuration boundaries
- [x] Secret redaction tests

#### 5B. Health and operations
- [x] Deployment health checks
- [x] Readiness semantics verified
- [x] Startup/shutdown behavior verified
- [x] Dependency failure behavior
- [x] GitHub outage/degraded-mode behavior
- [x] Worker health/status
- [x] Operational runbook

#### 5C. Deployment and recovery
- [x] CI test/build pipeline
- [x] Security/dependency checks
- [x] Container build and smoke test
- [x] Rollback procedure
- [ ] Render deployment
- [ ] Post-deployment verification
- [ ] Production smoke tests
- [ ] Backup/restore verification for PostgreSQL
- [x] Migration rollback strategy

**Production rule:** deployment is the final gate. We will not deploy while a required product, security, or operational acceptance criterion is unchecked.

### Phase 6 — Advanced intelligence and ecosystem
**Status: IN PROGRESS**

- [x] Scheduled discovery metadata and local watchlists
- [x] Deterministic change detection and alerts between discovery runs
- [x] Watchlist enable/disable and due-run scheduling controls
- [x] Protected watchlist and alert API endpoints
- [x] Execute scheduled watchlists through the durable worker
- [x] Persist alert acknowledgement/delivery state locally
- [ ] Add user-selectable external alert channels (explicitly disabled until implemented)
- [x] Saved investigations
- [x] Compare searches over time
- [x] Multi-profile comparison
- [x] Organization intelligence
- [x] Repository health intelligence
- [x] Security technology/skill taxonomy
- [x] Public graph snapshots and versioning
- [x] Standard graph formats: GraphML, GEXF, edge list
- [x] Optional integrations with other public data sources (CISA KEV)
- [x] Public API versioning (/api/v1 with legacy aliases)
- [x] API SDK/client examples
- [x] PyPI release tooling and artifact verification (publication requires explicit release action)
- [x] Contributor/developer documentation

Phase 6 deliberately starts with deterministic, local-first scheduling and change intelligence. No external notification channel or automatic outreach is enabled.

### Completion rule

For every unchecked item:

1. Read the item and acceptance criteria.
2. Inspect existing code before changing it.
3. Implement the smallest real end-to-end slice.
4. Add positive, negative, security, and regression tests as applicable.
5. Test with real public data locally where network access is appropriate.
6. Verify secrets and private state cannot cross the public boundary.
7. Update documentation.
8. Run the complete local suite.
9. Only then mark [x].
10. Move to the next item.

The roadmap is deliberately detailed so we do not skip features, fake completion, or turn the platform into a collection of disconnected demos.
## Public Platform

The public web application has two intentionally separate product surfaces:

### 1. GitHub Discovery

Discovery is an exploratory research surface. Visitors can search public GitHub repositories and engineers, apply filters, inspect profiles, compare engineers, and export discovery results.

**Discovery does not create, replace, or mutate the Security Intelligence Graph.** A search such as `eBPF`, `cloud security`, or any other repository query is not treated as the platform's intelligence model.

### 2. Security Intelligence Graph

The **Security Intelligence Graph** is the canonical, persisted SNB intelligence snapshot produced by the analysis workflow. The public page reads it through `GET /api/graph` and does not rebuild it from an arbitrary browser search.

The graph represents:

- analyzed engineers and their explainable security scores
- evidence-backed relationships
- security-domain communities
- centrality and network position
- relationship reasons/evidence
- the latest persisted analysis run and its snapshot timestamp

The graph UX must remain stable while a visitor performs unrelated discovery searches. A search may help a researcher decide what to investigate next, but it must never silently overwrite the canonical intelligence snapshot.

### Intelligence graph UX contract

| Surface | Purpose | Persistence | Canonical graph impact |
| --- | --- | --- | --- |
| GitHub Discovery | Find repositories and engineers | Browser search/history | None |
| Engineer Profile | Inspect public evidence for one engineer | Request-scoped | None |
| Security Intelligence Graph | Explore the latest SNB analysis | Persisted history run | Read-only from public UX |
| Private/terminal analysis | Generate and persist a new intelligence run | History database | Creates the next canonical snapshot |

The graph interface should provide:

- overview metrics for engineers, relationships, communities, and highest-centrality engineer
- community summaries and community filtering
- relationship-type filtering
- centrality ranking
- node search and shortest-path exploration
- click-through from a graph node to engineer intelligence
- relationship evidence/reasons rather than unexplained edges
- accessible structured graph data in addition to the SVG visualization
- deterministic JSON, SVG, and Markdown exports
- explicit snapshot source, run ID, and snapshot creation time
- a clear empty state explaining that discovery searches do not create the graph
- a **Refresh intelligence** action that reloads the persisted snapshot, not a browser-search-to-graph shortcut

### Analysis boundary

The endpoint `POST /api/public/graph/build` remains an explicit analysis capability for controlled workflows and regression coverage. It is **not** part of the normal discovery interaction and must not be presented as “Build graph from search” in the public UX. Any future product surface that invokes it must clearly label it as an intentional analysis operation and explain that it will create a new persisted run.

The canonical public graph endpoint is:

```text
GET /api/graph
```

Search endpoints remain discovery endpoints:

```text
GET /api/search
GET /api/users/search
```

This separation is a core product invariant and should be preserved in future frontend, API, deployment, and test work.

## Key Features

The product is designed as a public security-intelligence platform built on real GitHub data.

| Capability | Current state |
|---|---|
| **Public repository discovery** | Real GitHub Search API with bounded filters, pagination and sorting |
| **Public engineer discovery** | Real GitHub user search with profile navigation |
| **Evidence-backed profiles** | Public repositories, organizations, activity and engineering signals |
| **Security-domain intelligence** | Configurable domains, keywords and explainable scoring |
| **Relationship intelligence** | Real repository/org/domain relationships, weights, centrality and communities |
| **Interactive network analysis** | Filtering, zoom/pan, relationship-type filters, progressive rendering, rankings and accessible fallback data |
| **Search exports** | CSV and JSON |
| **Graph exports** | SVG and JSON |
| **Local investigations** | Private API-key-protected workspace with evidence, notes, tags, status and bundle export |
| **Reports** | Search, engineer and graph Markdown/JSON exports plus optional local PDF reports with source/timestamp/schema metadata |
| **Data freshness** | Source timestamps, GitHub capacity visibility, retry UX and public-cache policy |
| **API** | FastAPI with public/private boundaries and OpenAPI |
| **Background jobs** | Durable queue with idempotency, retries and rate controls |
| **Optional AI** | OpenAI/Anthropic behind explicit configuration |
| **Offline AI default** | **Yes — deterministic offline behavior is the default** |
| **Production container** | Docker image, health check and CI smoke test |
| **Privacy boundary** | Public GitHub intelligence is separate from private analyst data |

### Product quality bar

We are intentionally not building:

- fake graph nodes to make the UI look populated
- invented statistics
- simulated GitHub profiles
- client-only filters presented as server-side intelligence
- fake AI explanations
- hidden browser API calls containing private credentials
- automatic contact, follow, star, or message behavior
- private-data scraping

A demo state may use fixtures only inside tests. Production UI and API paths must use actual data or explicitly display that no data is available.

## Quick Start

### 1. Install

Requires **Python 3.10 or newer**.

```bash
git clone https://github.com/locallhosts/security-network-builder
cd security-network-builder
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

This installs the `snb` command (also available as `python -m snb`).

> Run each command on its own line. Pasting trailing `# comments` into zsh can cause errors.

### 2. Add a GitHub token

A token raises your rate limits and enables the faster GraphQL mode. This tool only reads public data, so the token needs **no permissions**.

1. GitHub → **Settings → Developer settings → Personal access tokens → Fine-grained tokens → Generate new token**
2. Set repository access to **Public repositories (read-only)** and grant no additional permissions.
3. Save it to a local `.env` file (git-ignored):

```bash
cp .env.example .env
```

Then edit `.env` and set:

```
GITHUB_TOKEN=your_token_here
```

### 3. Set your username

Edit `profiles/security_profile.yaml` and set `github_username` to your own login, so you are excluded from your own results.

### 4. Verify your setup

```bash
snb doctor
```

You should see `[ OK ]` for the token, GraphQL access, and rate limits. Warnings explain what to fix; failures stop the run with a clear reason.

### 5. Run a first discovery

```bash
snb --queries-per-domain 1 --max-candidates 10 --top 5
```

This is a deliberately small run (about a minute with a token):

| Option | Effect |
|---|---|
| `--queries-per-domain 1` | Runs one search query per security domain instead of all of them, which saves API calls. |
| `--max-candidates 10` | Analyzes the 10 most promising engineers in depth. |
| `--top 5` | Keeps the 5 best-scoring engineers in the report. |

Results are printed to the terminal, written to `reports/` as Markdown and JSON, and saved to the local history database.

### 6. Open the dashboard

```bash
snb dashboard --open
```

This starts a local server on `http://127.0.0.1:8765` and opens it in your browser. Press `Ctrl-C` in the terminal to stop it. The dashboard needs at least one recorded run, so complete step 5 first.

Once the small run looks right, drop the limiting options for a full run:

```bash
snb
```

---

## Usage

### Watchlists and change alerts

Watchlists are local, bounded public-data schedules. They do not store GitHub credentials and do not contact people.

    snb watchlist create "Cloud security" "cloud security" --domain cloud --interval-minutes 1440
    snb watchlist list
    snb watchlist due
    snb watchlist enable WATCHLIST_ID
    snb watchlist disable WATCHLIST_ID
    snb alerts
    snb alerts --min-move 5
    snb worker --max-jobs 1
    snb search-history record "cloud" "cloud security" --limit 10
    snb search-history compare "cloud"
    snb profile-compare --profile general=profiles/security_profile.yaml --profile cloud=profiles/cloud_security_profile.yaml --user locallhosts
snb repo-health locallhosts/security-network-builder
snb taxonomy locallhosts/security-network-builder
snb graph-export --history-db data/history.db --format graphml --output reports/network.graphml
snb --format pdf --output-dir reports

`alerts` compares the latest persisted discovery run with the previous run and reports new engineers, dropped engineers, and material score changes. Due watchlists are queued and executed by the durable worker. Each schedule slot uses an idempotency key, and local alert events can be acknowledged through the protected API without enabling external notifications.

### Discovery runs

```bash
snb                                   # full run with profile defaults
snb --top 25 --min-score 15           # larger, stricter report
snb --queries-per-domain 1            # quick run, fewer API calls
snb --profile profiles/mine.yaml      # use a custom profile
snb --expand 5                        # also analyze contributors of the top 5 engineers' repos
snb --api rest                        # force REST (no token required)
AI_PROVIDER=openai snb --ai       # LLM explanations with OpenAI\nAI_PROVIDER=anthropic snb --ai    # LLM explanations with Anthropic
snb --no-report                       # print only, write no report files
snb --include-ignored                 # include engineers you marked as ignored
```

### Other commands

```bash
snb doctor                            # preflight checks (add --offline to skip network checks)
snb dashboard --open                  # local web dashboard (add --port to change the port)
snb history                           # list past runs
snb history --diff                    # what changed since the previous run
snb history --login alice             # score trend for one engineer
snb history --set alice reviewing --note "check eBPF repo"
snb profile-suggest --github-user YOU # propose a profile from your own repositories
snb --version
```

### Example output

The format looks like this (names and numbers are illustrative):

```
Building security network... [GRAPHQL]

Searching:
sigma detection

Found 54 engineers; analysing top 10...

Recommended Engineers:

@developer

Score: 35

Areas:
- Linux / eBPF Security
- Detection Engineering

Why: @developer scored 35, matching Linux / eBPF Security and Detection Engineering.
Strongest signal: developer/tracer (500 stars). Matching work is recent.

Report written: reports/report_20261001_120000.md
Saved as run #1. View with: snb dashboard
```

---

## Dashboard

```bash
snb dashboard --open
```

The dashboard is a local, read-only view of your run history:

- **Ranking** with filters by security area, triage status, and free-text search
- **Relationship graph** showing engineers as nodes (sized by score, colored by community) connected by shared repositories, organizations, and domains
- **Changes since previous run**: new engineers, dropped engineers, and score movers
- **Organizations** that concentrate matching engineers, with member count, score share, domain diversity, and top-domain signals
- **Engineer detail** with explanation, itemized score breakdown, evidence, matching repositories, and score history
- **Triage notes** (`reviewing`, `connected`, `ignored`, plus a private note). These are stored locally as your own notebook; nothing is sent to GitHub.

The server binds to `127.0.0.1` only. See [Security and Privacy](#security-and-privacy) for its protections.

---

## Public Platform

The repository includes a containerized FastAPI service for public, read-only discovery.

### Local container test

From the repository root:

```bash
cp deployment/.env.example deployment/.env
docker compose -f deployment/docker-compose.yml up --build
```

Open `http://127.0.0.1:8765/`.

The browser search endpoint is public and rate-limited in-process. Run history and engineer history remain protected by `API_KEY` when one is configured. FastAPI's interactive API documentation is available at `/docs`.

### Render

`deployment/render.yaml` defines the free Docker web service and its environment variables. Set the secrets in Render rather than committing them: