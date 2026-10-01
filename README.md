# Security Network Builder

> A security engineering intelligence platform for discovering, analyzing, and connecting with engineers working in similar cybersecurity domains.

**Security Engineer Discovery and Intelligence Platform**

---

## Overview

Security Network Builder automates the discovery and ranking of engineers on GitHub based on their security specialization, so you can find relevant peers, maintainers, and collaborators without hours of manual searching.

**What problem does this solve?**
Finding relevant security engineers manually is time consuming. Follower counts and stars measure popularity, not expertise.

**Why was it built?**
GitHub contains valuable technical signals that are rarely used for discovery:

- repositories
- commits
- topics
- contributions
- technical domains

This project turns those signals into a ranked, explainable list of engineers.

**Who is it for?**

- Security engineers who want a technically aligned professional network
- Detection, cloud, and runtime security practitioners looking for collaborators
- Open source contributors searching for maintainers in a specific domain
- Recruiters and community builders mapping security engineering ecosystems

---

## Problem Statement

Security professionals often want to build meaningful technical networks, but traditional follower discovery is based on popularity rather than expertise.

This project focuses on:

- technical alignment
- engineering contribution
- security specialization
- active development

---

## Goals

### Primary Goals

- Discover security engineers from GitHub
- Identify engineers by technical domain
- Rank candidates using security relevance
- Provide explainable recommendations

### Non Goals

- Not a follower farming tool
- Not a mass follow bot
- Not a social scraping system
- Not intended to spam users

---

## Architecture

```
Security Profile
       |
       v
GitHub Discovery Engine
       |
       v
Repository Analysis
       |
       v
Engineer Scoring Engine
       |
       v
Recommendation Report
```

*(Detailed diagram to be added.)*

---

## Security Domains

### Detection Engineering

Technologies: Sigma, YARA, SIEM, SOAR, MITRE ATT&CK

### Linux / eBPF Security

Technologies: eBPF, kernel security, runtime security, Falco

### Cloud Security

Technologies: AWS, Kubernetes, Terraform, DevSecOps

### Identity and Zero Trust

Technologies: SPIFFE/SPIRE, IAM, mTLS, workload identity

### Application Security

Technologies: OWASP, API Security, secure coding

### Security Automation

Technologies: Python, Go, security tooling

---

## How It Works

### 1. Discovery

Searches GitHub for:

- security repositories
- maintainers
- contributors
- engineers

### 2. Profile Analysis

Analyzes:

- repository names
- descriptions
- topics
- programming languages
- activity

### 3. Scoring Engine

Domain weights come from your profile:

```
Detection Engineering   +10
eBPF Security           +10
Cloud Security          +8
Zero Trust              +9
Security Automation     +7
```

Plus: +1 per additional matching repo in a domain (max +3), recent activity (+3 within 90 days, +1 within a year), log-scaled star traction (max +3, so popularity cannot dominate), and +1 for preferred languages. Every point appears in the report's score breakdown.

### 4. Recommendation

Produces an explainable report:

```
Engineer:  @username
Score:     32

Matched Areas:
  ✓ eBPF
  ✓ Linux Security
  ✓ Runtime Security

Evidence:
  - Maintains security tooling
  - Active commits
  - Related repositories
```

---

## Installation

```bash
git clone https://github.com/locallhosts/security-network-builder
cd security-network-builder
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

Requires Python 3.10+.

---

## Configuration

**Environment variables**

```bash
cp .env.example .env      # then set GITHUB_TOKEN
```

A token with **no scopes** is enough (public data only). Without one the tool still runs, but anonymous GitHub limits are low (10 searches/min, 60 calls/hour).

**Security profile**

```
profiles/security_profile.yaml
```

---

## Usage

```bash
python src/main.py                                  # defaults
python src/main.py --top 25 --min-score 15          # bigger, stricter report
python src/main.py --queries-per-domain 1           # quick run, fewer API calls
python src/main.py --profile profiles/mine.yaml     # your own profile
python src/main.py --no-report                      # print only
```

Reports are written to `reports/` as Markdown and JSON.

Example output:

```
Building security network...

Searching:
ebpf security

Searching:
sigma detection

Recommended Engineers:

@developer
Score: 35
Areas:
  - eBPF
  - Detection Engineering
```

---

## Project Structure

```
security-network-builder/
├── src/
│   ├── main.py          # CLI entry point and pipeline
│   ├── config.py        # profile loading, validation, keyword matching
│   ├── github_api.py    # read-only GitHub REST client with rate-limit handling
│   ├── discovery.py     # profile -> GitHub searches -> candidate engineers
│   ├── scoring.py       # explainable scoring engine
│   ├── models.py        # Candidate / Recommendation dataclasses
│   └── report.py        # console, Markdown and JSON output
├── profiles/
│   └── security_profile.yaml
├── reports/
├── tests/               # pytest suite (runs offline)
├── requirements.txt
├── .env.example
└── README.md
```

---

## Roadmap

### Phase 1
- [x] GitHub discovery
- [x] Security profile matching
- [x] Ranking system

### Phase 2
- [ ] GitHub GraphQL integration
- [ ] Contributor graph analysis
- [ ] Organization analysis
- [ ] Better reputation scoring

### Phase 3
- [ ] Web dashboard
- [ ] Engineer relationship graph
- [ ] Recommendation history

### Phase 4
- [ ] AI-assisted security profile analysis
- [ ] Natural language explanations

---

## Testing

```bash
python -m pytest
```

The suite runs offline against fake GitHub responses.

---

## Security Considerations

- The GitHub client is read-only: the tool never follows, stars, or messages anyone

- GitHub tokens are stored locally
- API rate limits are respected
- No private repository access required
- No credentials collected
- No automated interaction without user approval

---

## Technologies

- Python
- GitHub REST API
- GitHub GraphQL API
- JSON / YAML
- GitHub Actions

---

## Why This Project Exists

I built this project to explore how security engineering communities can be discovered through technical signals rather than popularity metrics.

---

## License

MIT License
