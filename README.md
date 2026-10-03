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
- [ ] Optional PDF report generated locally/server-side (deferred until report dependency is intentionally added)
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
- [ ] Verify every public web intelligence feature has a deterministic non-AI path
- [ ] Optional AI explanations in the investigation workspace
- [ ] AI provenance indicator showing when text is AI-generated
- [ ] AI request audit metadata without storing secrets
- [ ] AI output regression tests against prompt-injection-shaped GitHub content

**AI contract:** offline remains the default. A remote provider is used only when explicitly configured and supplied with its required secret. No public visitor can silently cause an LLM request.

### Phase 5 — Production hardening
**Status: IMPLEMENTATION COMPLETE — VALIDATION GATE PENDING**

#### 5A. Configuration
- [ ] Production environment configuration
- [ ] Fail-closed production secret validation
- [ ] Safe default configuration
- [ ] Offline AI default verified in production configuration
- [ ] Separate public/private configuration boundaries
- [ ] Secret redaction tests

#### 5B. Health and operations
- [ ] Deployment health checks
- [ ] Readiness semantics verified
- [ ] Startup/shutdown behavior verified
- [ ] Dependency failure behavior
- [ ] GitHub outage/degraded-mode behavior
- [ ] Worker health/status
- [ ] Operational runbook

#### 5C. Deployment and recovery
- [x] CI test/build pipeline
- [x] Security/dependency checks
- [x] Container build and smoke test
- [ ] Rollback procedure
- [ ] Render deployment
- [ ] Post-deployment verification
- [ ] Production smoke tests
- [ ] Backup/restore verification for PostgreSQL
- [ ] Migration rollback strategy

**Production rule:** deployment is the final gate. We will not deploy while a required product, security, or operational acceptance criterion is unchecked.

### Phase 6 — Advanced intelligence and ecosystem
**Status: PLANNED**

- [ ] Scheduled discovery runs
- [ ] Change detection and alerts
- [ ] Watchlists
- [ ] Saved investigations
- [ ] Compare searches over time
- [ ] Multi-profile comparison
- [ ] Organization intelligence
- [ ] Repository health intelligence
- [ ] Security technology/skill taxonomy
- [ ] Public graph snapshots and versioning
- [ ] Standard graph formats: GraphML, GEXF, edge list
- [ ] Optional integrations with other public data sources
- [ ] Public API versioning
- [ ] API SDK/client examples
- [ ] PyPI release
- [ ] Contributor/developer documentation

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
| **Reports** | Search, engineer and graph Markdown/JSON exports with source/timestamp/schema metadata; PDF remains optional |
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
- **Organizations** that concentrate matching engineers
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

- `GITHUB_TOKEN` — recommended for higher GitHub API limits
- `API_KEY` — protects private run-history endpoints
- `OPENAI_API_KEY` / `OPENAI_MODEL` — optional OpenAI explanations
- `ANTHROPIC_API_KEY` / `ANTHROPIC_MODEL` — optional Anthropic explanations
- `AI_PROVIDER` — `offline`, `openai`, or `anthropic`

The hosted service is intentionally read-only with respect to GitHub. Do not expose private triage data through a public deployment.

> **Persistence:** the current history implementation uses SQLite. Render's free filesystem is not durable across service replacement/redeploys, so persistent hosted run history should use a managed PostgreSQL-backed history layer before relying on the service as a long-term hosted notebook.

---

## Configuration

### Environment variables

| Variable | Required | Purpose |
|---|---|---|
| `GITHUB_TOKEN` | Recommended | Higher rate limits and GraphQL mode. No permissions needed. |
| `ANTHROPIC_API_KEY` | Optional | Only used with `--ai`. |
| `ANTHROPIC_MODEL` | Optional | Overrides the default model used by `--ai`. |

### Security profile

The profile defines what you are looking for. By default `snb` reads `profiles/security_profile.yaml` in the current directory, and falls back to a profile bundled with the package if that file is not present.

```yaml
name: Security Engineer
github_username: "your-login"      # excluded from results

settings:
  min_stars: 5                     # minimum stars on a seed repository
  active_within_days: 365          # seed repositories must have been pushed to recently
  results_per_query: 30
  max_candidates: 30               # engineers analyzed in depth per run
  max_repos_per_user: 100
  users_only: true                 # skip organizations
  include_forks: false
  preferred_languages: [Python, Go, Rust]
  exclude_users: []

domains:
  ebpf_linux_security:
    label: Linux / eBPF Security
    weight: 10                     # points for a matching engineer
    keywords: [ebpf, runtime security, falco, tetragon]
    search_queries: ["ebpf security", "topic:ebpf"]
```

To bootstrap a profile from your own work:

```bash
snb profile-suggest --github-user YOUR_LOGIN
```

This reads your public repositories and writes `profiles/suggested_profile.yaml` for you to review.

---

## How It Works

### 1. Discovery

Your profile's search queries run against the GitHub Search API, filtered to active, non-fork, non-archived repositories above a star threshold. Repository owners become candidates. Organizations and excluded users are removed.

### 2. Analysis

Candidates are pre-ranked, and the top ones are analyzed in depth. With a token, GraphQL fetches repositories, topics, organization memberships, and contribution statistics for 10 engineers per request. Otherwise the REST API is used.

### 3. Scoring

Each engineer is scored from their public repositories. Keywords are matched as whole words against repository names, descriptions, and topics, so `iam` does not match `william`.

| Component | Points |
|---|---|
| Domain match | Domain weight from your profile (first matching repo) |
| Additional matching repos in the same domain | +1 each, up to +3 |
| Recent activity | +3 if pushed within 90 days, +1 within a year |
| Community traction | log-scaled stars, up to +3 |
| Preferred language | +1 |
| Reputation | up to +6 (see below) |

**Reputation** is deliberately hard to game: followers contribute at most +2; contribution volume over the last year contributes +1 or +2; code review activity adds +1; account tenure of three years or more adds +1. Contribution and review data requires GraphQL (a token). In REST mode only followers and tenure are available.

### 4. Relationships

The final list is turned into a graph. Edges come from shared repository contributions (weight 4), shared organizations (weight 3 per organization), and two or more overlapping domains (weight 1 per domain). Weighted-degree centrality and deterministic community detection are computed from it.

### 5. Reporting and history

Results are explained in plain language, written to `reports/` as Markdown and JSON, and stored in a local SQLite database so later runs can flag new engineers and show score changes.

---

## Architecture

```
          Security Profile (YAML)
                    │
                    ▼
        Discovery (GitHub Search API)
                    │
                    ▼
     Analysis (GraphQL batches, REST fallback)
                    │
                    ▼
       Scoring Engine + Reputation Signals
                    │
        ┌───────────┼────────────────┐
        ▼           ▼                ▼
  Relationship   Explanations    History
  Graph + Orgs   (offline / AI)  (SQLite)
        └───────────┼────────────────┘
                    ▼
        Reports (Markdown, JSON)  ·  Dashboard
```

---

## Security Domains

The default profile covers six domains. All are fully configurable.

| Domain | Example technologies |
|---|---|
| **Detection Engineering** | Sigma, YARA, SIEM, SOAR, MITRE ATT&CK |
| **Linux / eBPF Security** | eBPF, kernel security, runtime security, Falco |
| **Cloud Security** | AWS, Kubernetes, Terraform, DevSecOps |
| **Identity and Zero Trust** | SPIFFE/SPIRE, IAM, mTLS, workload identity |
| **Application Security** | OWASP, API security, secure coding |
| **Security Automation** | Python, Go, security tooling |

---

## Project Structure

```
security-network-builder/
├── src/snb/
│   ├── main.py             # CLI, pipeline, command dispatch
│   ├── doctor.py           # preflight checks
│   ├── config.py           # profile loading and keyword matching
│   ├── github_api.py       # read-only REST and GraphQL transport, rate-limit handling
│   ├── graphql_api.py      # batched GraphQL fetching
│   ├── discovery.py        # profile to GitHub searches to candidates
│   ├── scoring.py          # explainable scoring engine
│   ├── reputation.py       # capped reputation signals
│   ├── graph.py            # relationship graph, centrality, communities
│   ├── orgs.py             # organization analysis
│   ├── history.py          # SQLite run history, triage notes, run diffs
│   ├── workspace.py        # private investigation workspace, evidence, notes and timeline
│   ├── explain.py          # offline and optional LLM explanations
│   ├── profile_builder.py  # profile suggestion
│   ├── dashboard.py        # hardened local HTTP server
│   ├── dashboard_page.py   # single-page UI
│   ├── default_profile.yaml
│   ├── models.py
│   └── report.py
├── profiles/
│   └── security_profile.yaml   # your editable profile
├── docs/
│   └── WEB_PLATFORM.md         # public UI, accessibility, graph and operational behavior
├── tests/                  # offline pytest suite, plus a jsdom dashboard test
├── .github/                # CI workflow and Dependabot configuration
├── pyproject.toml
├── .env.example
└── README.md
```

---

## Development

```bash
pip install -e ".[dev]"
python -m pytest                        # offline unit and integration tests
```

The test suite runs entirely offline against fake GitHub responses.

The dashboard also has a DOM-level test. It starts a real server seeded with hostile data (script tags, `javascript:` URLs, event-handler payloads) and drives the page in jsdom to confirm nothing executes:

```bash
npm ci --prefix tests/web               # one-time: installs jsdom
python -m pytest tests/test_dashboard_dom.py
```

jsdom is a DOM implementation, not a full browser: it does not render CSS or enforce Content Security Policy (CSP headers are verified separately at the server level). The DOM test is skipped automatically when Node or jsdom is unavailable.

Continuous integration (`.github/workflows/ci.yml`) runs the tests on Python 3.10 to 3.12, runs the DOM test, and builds and smoke-tests the wheel in a clean virtual environment.

---

## Troubleshooting

| Symptom | Likely cause and fix |
|---|---|
| `snb: command not found` | The virtual environment is not active, or the install failed. Run `source .venv/bin/activate`, then `pip install -e ".[dev]"`. You can also use `python -m snb`. |
| `Invalid requirement: '#'` during install | A `# comment` was pasted onto the command line in zsh. Run the command on its own. |
| `ERROR: .[dev], is not a valid editable requirement` | A trailing comma was copied with the command. Use exactly `pip install -e ".[dev]"`. |
| Python version too old | This project needs Python 3.10+. Check with `.venv/bin/python --version` and recreate the virtual environment with a newer interpreter if needed. |
| `rate limited; reset in ~N s` | Anonymous GitHub limits are low. Add a `GITHUB_TOKEN` to `.env`, or wait for the reset. Use `--queries-per-domain 1` to save calls. |
| `snb doctor` warns about token scopes | Your classic token has broader scopes than needed. Use a fine-grained token with no permissions. |
| GraphQL warning in `snb doctor` | The tool falls back to REST automatically. Check that the token is valid and not expired. |
| Dashboard shows "No runs yet" | Complete a discovery run first (`snb --queries-per-domain 1 --max-candidates 10 --top 5`). |
| Dashboard port already in use | Choose another: `snb dashboard --port 8766 --open`. |

---

## Security and Privacy

- **Read-only.** The GitHub client has no follow, star, or message capability.
- **Local storage.** Tokens live in `.env` (git-ignored). Run history and triage notes stay in a local SQLite file.
- **Public data only.** No private repository access is needed or requested. No credentials are collected.
- **Rate limits respected.** Requests back off on rate limiting, and partial results are kept if a limit is reached mid-run.
- **No automated interaction.** Triage states such as `connected` are your own private notes.
- **Hardened dashboard.** It binds to `127.0.0.1` only, validates the `Host` header (DNS-rebinding defense), requires a per-launch CSRF token for writes, and sends a strict Content Security Policy. All GitHub-sourced text is rendered as plain text, never as HTML, and links are restricted to `github.com`.
- **Opt-in AI.** `--ai` sends only public repository metadata and computed scores to the selected OpenAI or Anthropic API, and instructs the model to treat GitHub text as untrusted data.
- **Token hygiene.** If a token is ever committed, revoke it on GitHub immediately; deleting the commit is not enough.

---

## Responsible Use

This project exists to help people find technically relevant peers and collaborators. It is intentionally not:

- a follower-farming tool
- a mass-follow or mass-message bot
- a social scraping system
- a way to contact people who have not invited it

Please follow [GitHub's Acceptable Use Policies](https://docs.github.com/en/site-policy/acceptable-use-policies/github-acceptable-use-policies) and API terms, and treat the people in your reports with respect. Review a recommendation's evidence before reaching out, and keep any outreach personal and relevant.

---

## Future Work

Future work is tracked in the numbered roadmap above. We do not use this section as a second, conflicting checklist.

Priority after the current web-platform work:

1. Finish the professional discovery, profile, and graph experience.
2. Build the investigation workspace and evidence model.
3. Complete export/reporting capabilities.
4. Add operational visibility, abuse controls, and freshness indicators.
5. Finish production hardening and rollback procedures.
6. Deploy only after the production gate is green.
7. Then expand into scheduled intelligence, watchlists, organization intelligence, and ecosystem integrations.

## Why This Project Exists

I built this project to explore how security engineering communities can be discovered through technical signals rather than popularity metrics.

---

## License

Released under the [MIT License](LICENSE).