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

This roadmap is the project's build sequence. **Do not deploy the production service until the implementation phases below are complete and the local test/Docker validation is green.** Keep this section updated as work progresses so the project history and remaining work are visible to contributors and users.

### Phase 1 — Foundation
**Theme: Build the security-engineering core**

Goal: establish discovery, scoring, relationships, persistence, reporting, and the local dashboard as a reliable foundation.

- [x] Core discovery and scoring foundation
- [x] Security profile and configurable domains
- [x] GitHub REST/GraphQL data collection
- [x] Explainable scoring and relationship graph foundation
- [x] Local history and reporting
- [x] Local dashboard foundation
- [x] Preflight/doctor checks
- [x] Security and privacy baseline

**Phase 1 exit criteria:** discovery, scoring, graph generation, local history, reporting, and dashboard functionality are implemented and covered by the local test suite.

### Phase 2 — API
**Theme: Turn the foundation into a secure, testable service**

Goal: expose the foundation through a stable FastAPI interface while protecting private data and validating public input.

4. **FastAPI application**
   - [x] Complete application/configuration boundary
   - [x] Health endpoint
   - [x] Root/public web response
   - [x] OpenAPI metadata and interactive API documentation
   - [x] Security middleware and response headers

5. **API routes**
   - [x] Public GitHub repository search
   - [x] Public latest community graph
   - [x] Protected run history
   - [x] Protected latest run
   - [x] Protected individual run lookup
   - [x] Protected engineer history
   - [x] Request validation and bounded parameters
   - [x] API-key protection for private routes
   - [x] Lightweight search rate limiting
   - [x] Safe GitHub URL validation
   - [x] Clear API error handling

6. **API tests**
   - [x] Health/root coverage
   - [x] Search success and validation coverage
   - [x] GitHub error handling coverage
   - [x] Private-route authentication coverage
   - [x] Run-not-found behavior
   - [x] Empty/non-empty graph behavior
   - [x] Security-header coverage
   - [x] Complete API contract/regression coverage

**Phase 2 exit criteria:** all API routes have a documented contract, private data is protected, public inputs are validated/rate-limited, and the complete API suite is green.

### Phase 3 — Web Platform
**Theme: Build the user-facing security intelligence platform**

Goal: make the API useful through a professional web experience.

7. **Search UI**
   - [ ] Search engineers/repositories
   - [ ] Filters and pagination
   - [ ] Loading, empty, and error states
   - [ ] Evidence-first result cards
   - [ ] Secure rendering of GitHub content

8. **Engineer profiles**
   - [ ] Engineer profile page
   - [ ] Score and domain breakdown
   - [ ] Matching repositories and evidence
   - [ ] Activity/history view
   - [ ] Organization and relationship context

9. **Graph visualization**
   - [ ] Interactive relationship graph
   - [ ] Node/edge filtering
   - [ ] Community/domain views
   - [ ] Relationship details
   - [ ] Accessible non-graph fallback
   - [ ] Larger-graph performance testing

**Phase 3 exit criteria:** a user can search, inspect an engineer, and explore relationships through the web platform.

### Phase 4 — Intelligence Layer
**Theme: Add controlled AI and automated discovery**

Goal: add optional intelligence without allowing untrusted GitHub content to control application behavior.

10. **OpenAI integration**
   - [ ] Provider interface
   - [ ] Secure configuration and secret handling
   - [ ] Prompt/input boundaries
   - [ ] Output validation
   - [ ] Offline fallback
   - [ ] Provider failure tests

11. **Anthropic integration**
   - [ ] Same provider interface
   - [ ] Secure configuration and secret handling
   - [ ] Prompt/input boundaries
   - [ ] Output validation
   - [ ] Offline fallback
   - [ ] Provider failure tests

12. **Background discovery jobs**
   - [ ] Job lifecycle
   - [ ] Queue/worker implementation
   - [ ] Retry and backoff policy
   - [ ] Idempotency and duplicate protection
   - [ ] Job status API
   - [ ] Failure/recovery tests
   - [ ] Resource and rate-limit controls

**Phase 4 exit criteria:** AI is optional and validated, and background discovery is observable, retryable, idempotent, and rate-limit aware.

### Phase 5 — Production
**Theme: Make the platform durable, authenticated, and deployable**

Goal: move from local application to production-grade service only after earlier phases are stable.

13. **PostgreSQL**
   - [ ] PostgreSQL history implementation
   - [ ] Schema and migration strategy
   - [ ] Data-access boundary
   - [ ] SQLite local compatibility where appropriate
   - [ ] Transaction and concurrency tests

14. **API authentication**
   - [~] Current API-key foundation
   - [ ] Production authentication design
   - [ ] Key/token rotation
   - [ ] Authorization boundaries
   - [ ] Audit/security logging
   - [ ] Abuse/rate-limit controls
   - [ ] Authentication regression tests

15. **CI/CD deployment**
   - [ ] CI test/build pipeline fully green
   - [ ] Security/dependency checks
   - [ ] Container build and smoke test
   - [ ] Production environment configuration
   - [ ] Deployment health checks
   - [ ] Rollback procedure
   - [ ] Render deployment
   - [ ] Post-deployment verification

**Phase 5 exit criteria:** persistent storage, production authentication, secure CI/CD, container validation, operational checks, and deployment verification are complete.

### Phase 3 — Web Platform

7. **Search UI**
8. **Engineer profiles**
9. **Graph visualization**

### Phase 4 — Intelligence Layer

10. **OpenAI integration**
11. **Anthropic integration**
12. **Background discovery jobs**

### Phase 5 — Production

13. **PostgreSQL**
14. **API authentication**
15. **CI/CD deployment**

### Completion rule

### Build Sequence

The implementation order is intentional:

**Foundation → API → Web Platform → Intelligence → Production**

For every phase:

1. Read the roadmap before coding.
2. Implement the next unchecked item.
3. Add or update tests.
4. Run the local test suite.
5. Review security boundaries and failure cases.
6. Mark the item `[x]` only when it is actually finished.
7. Move to the next item.

Production deployment is the final milestone, not an intermediate step. The README roadmap is the source-of-truth checklist for what we build and what remains.

---

## Key Features

| Capability | Description |
|---|---|
| **Profile-driven discovery** | Define your security domains, keywords, and search queries in YAML. The tool searches GitHub accordingly. |
| **Explainable scoring** | Domain match, recent activity, traction, language fit, and reputation, each itemized in the report. |
| **GraphQL and REST** | With a token, GraphQL batches 10 engineers per request. Without one, it falls back to REST. |
| **Reputation signals** | Contribution volume, code review activity, and account tenure, with followers capped at a minor share. |
| **Relationship graph** | Co-contribution, shared organizations, and overlapping domains produce edges, centrality, and communities. |
| **Contributor expansion** | `--expand N` finds and scores contributors of the top engineers' repositories. |
| **Organization analysis** | Shows which organizations concentrate the engineers you found. |
| **Run history and diffs** | Every run is stored locally. See who is new, who dropped off, and whose score moved. |
| **Local dashboard** | Ranking, interactive graph, score breakdowns, history, and private triage notes in the browser. |
| **Public platform** | FastAPI web UI with public GitHub repository search, health checks, API documentation, and a read-only community graph. |
| **Container deployment** | Docker/Compose for local validation plus a Render deployment manifest for a public service. |
| **Explanations** | Deterministic offline explanations, with optional LLM-written ones (`--ai`). |
| **Profile suggestion** | Proposes a profile from your own public repositories. |
| **Preflight checks** | `snb doctor` validates your token, rate limits, profile, and paths before a run. |

---

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
│   ├── explain.py          # offline and optional LLM explanations
│   ├── profile_builder.py  # profile suggestion
│   ├── dashboard.py        # hardened local HTTP server
│   ├── dashboard_page.py   # single-page UI
│   ├── default_profile.yaml
│   ├── models.py
│   └── report.py
├── profiles/
│   └── security_profile.yaml   # your editable profile
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

Possible next steps, in no particular order:

- Durable PostgreSQL-backed hosted run history
- Scheduled recurring runs with automatic diff summaries
- Production-grade distributed rate limiting and abuse controls
- Comparing multiple profiles side by side
- Additional public signal sources beyond GitHub
- Exporting the relationship graph to standard graph formats
- Publishing to PyPI

---

## Why This Project Exists

I built this project to explore how security engineering communities can be discovered through technical signals rather than popularity metrics.

---

## License

Released under the [MIT License](LICENSE).