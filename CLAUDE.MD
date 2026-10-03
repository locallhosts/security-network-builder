for your repository.

# Security Network Builder — Remaining Implementation Roadmap

## Project Goal

Transform Security Network Builder from a local security engineer discovery tool into a public security intelligence platform.

Current completed components:

- GitHub discovery engine
- Security domain profiling
- Explainable scoring engine
- Reputation signals
- Relationship graph engine
- Organization analysis
- History tracking
- Local dashboard
- CLI interface
- Dockerfile
- Test suite

Current branch:


feature/public-platform-foundation


---

# Remaining Features

## 1. Public Deployment Platform

## Objective

Create a production-ready deployment environment.

Add:


deployment/

├── Dockerfile
├── docker-compose.yml
├── nginx.conf
├── .env.example
└── README.md


Architecture:

             Internet

                |

              Nginx

                |

    ------------------------

    |                      |

    v                      v

  Web UI                  API

                             |

                             v

                     SNB Engine

Services:

- Frontend web server
- API backend
- Database
- Reverse proxy

---

# 2. API Platform

## Objective

Expose Security Network Builder functionality through a public API.

Create:


src/snb/api/

├── init.py
├── app.py

└── routes/

├── health.py
├── search.py
├── engineers.py
├── graph.py
└── profiles.py

Recommended stack:

- FastAPI
- Uvicorn
- Pydantic

---

## API Endpoints

### Health Check


GET /api/health


Example:

```json
{
  "status": "ok",
  "service": "security-network-builder"
}
Security Engineer Search
GET /api/search?q=cloud-security

Example:

{
  "query": "cloud-security",
  "results": [
    {
      "username": "engineer",
      "score": 42,
      "domains": [
        "Cloud Security"
      ],
      "evidence": [
        "Kubernetes security contributor"
      ]
    }
  ]
}
Engineer Details
GET /api/engineers/{username}

Return:

score
expertise
repositories
organizations
evidence
history

Example:

{
 "username":"alice",
 "score":45,
 "domains":[
    "Cloud Security",
    "DevSecOps"
 ],
 "repositories":[]
}
Community Graph API
GET /api/graph

Expose:

nodes
edges
communities
organizations

Example:

{
 "nodes":[
   {
    "id":"alice",
    "score":40,
    "community":1
   }
 ],

 "edges":[
   {
    "source":"alice",
    "target":"bob",
    "weight":4
   }
 ]
}

Use existing:

src/snb/graph.py

Do not duplicate graph logic.

3. Interactive Web Platform

Create:

web/

├── index.html
├── search.html
├── engineer.html
├── graph.html

├── css/

│   └── style.css

└── js/

    ├── api.js
    ├── search.js
    ├── engineer.js
    └── graph.js
Web Features
Search Interface

Users can search:

security domains
technologies
engineers
organizations

Filters:

Domain:

[x] Cloud Security
[x] Detection Engineering
[x] Application Security
[x] Linux Security


Minimum Score:

[30]
Engineer Profile Page

Example:

/engineer/alice

Display:

Alice

Security Engineer

Score:
45


Expertise:

- Kubernetes Security
- AWS
- Terraform


Evidence:

Repository:
cloud-defense

Activity:
30 days ago
4. Community Security Graph
Objective

Make the relationship graph publicly explorable.

Technology:

Recommended:

Cytoscape.js
D3.js

Graph objects:

Nodes

Represent:

engineers
organizations
repositories

Example:

{
"id":"alice",
"type":"engineer",
"score":50
}
Edges

Represent:

shared repositories
organizations
domains
collaboration

Example:

{
"source":"alice",
"target":"bob",
"type":"shared_repository",
"weight":4
}
5. AI Provider System
Objective

Support multiple AI providers.

Current:

ANTHROPIC_API_KEY

Add:

OPENAI_API_KEY

Create:

src/snb/ai/

├── provider.py
├── openai_provider.py
├── anthropic_provider.py
└── offline_provider.py

Environment:

AI_PROVIDER=openai

OPENAI_API_KEY=
OPENAI_MODEL=

ANTHROPIC_API_KEY=
ANTHROPIC_MODEL=

Supported modes:

OpenAI

Example:

AI_PROVIDER=openai
OPENAI_MODEL=gpt-5
Anthropic

Example:

AI_PROVIDER=anthropic
Offline

Default:

AI_PROVIDER=offline

No external API calls.

AI Security Requirements

Never:

commit API keys

Never store:

OPENAI_API_KEY
ANTHROPIC_API_KEY
GITHUB_TOKEN

inside code.

Use:

.env

Only send:

public repository metadata
computed scores
security domains

Treat GitHub repository text as untrusted input.

6. Environment Configuration

Create:

.env.example

Example:

# GitHub

GITHUB_TOKEN=


# AI

AI_PROVIDER=openai

OPENAI_API_KEY=
OPENAI_MODEL=gpt-5


ANTHROPIC_API_KEY=
ANTHROPIC_MODEL=


# Database

DATABASE_URL=


# API

API_SECRET_KEY=


# Runtime

ENVIRONMENT=production
7. Database Upgrade

Current:

SQLite

For public deployment:

Add:

PostgreSQL

Stack:

PostgreSQL
SQLAlchemy
Alembic

Tables:

users

engineers

repositories

scores

graphs

api_keys

search_history
8. Background Jobs

Discovery should not block API requests.

Add:

workers/

├── scheduler.py
└── jobs.py

Technology:

Celery
Redis

Example:

Every 24 hours:

Run GitHub discovery

Update scores

Update graph

Generate reports
9. API Authentication

Create:

src/snb/api/auth.py

Features:

API keys
authentication middleware
rate limiting

Header:

X-API-Key: key_here
10. Security Hardening

Before public launch:

Add:

API Security
input validation
rate limits
request logging
CORS policy
Web Security

Nginx headers:

Content-Security-Policy

X-Frame-Options

X-Content-Type-Options
11. CI/CD Pipeline

Create:

.github/workflows/

├── ci.yml
├── security-scan.yml
└── deploy.yml

Pipeline:

Commit

 |

Tests

 |

Security Scan

 |

Docker Build

 |

Deploy

Tools:

pytest
Ruff
Bandit
Trivy
Dependabot
Implementation Priority
Phase 1 — Foundation
docker-compose.yml
nginx.conf
environment configuration
Phase 2 — API
FastAPI application
API routes
API tests
Phase 3 — Web Platform
Search UI
Engineer profiles
Graph visualization
Phase 4 — Intelligence Layer
OpenAI integration
Anthropic integration
Background discovery jobs
Phase 5 — Production
PostgreSQL
API authentication
CI/CD deployment
Final Architecture
                         Users

                           |

                         Nginx

                           |

              ----------------------------

              |                          |

              v                          v

          Web Platform                 API

                                           |

                                           v

                                  SNB Core Engine

                                           |

              ------------------------------------------------

              |                    |                         |

        GitHub API             Database                 AI Providers

                              PostgreSQL              OpenAI / Anthropic


Success Criteria

The completed platform should provide:

✅ Public security engineer discovery
✅ Interactive search
✅ Explainable ranking
✅ Community security graph
✅ API access
✅ OpenAI + Anthropic AI support
✅ Production deployment
✅ Secure CI/CD pipeline


This file will act as the implementation contract for the remaining development.