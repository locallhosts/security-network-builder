# Deployment

## Local Docker

From the repository root:

```bash
cp deployment/.env.example deployment/.env
docker compose -f deployment/docker-compose.yml up --build
```

The production API listens on port 8000 inside the container. The local compose mapping exposes it through port 8765.

Health check:

```text
http://127.0.0.1:8765/api/health
```

## Render

The repository includes `deployment/render.yaml`.

Create a Render Blueprint from this repository. Configure these secrets in Render:

- `GITHUB_TOKEN`
- `OPENAI_API_KEY`
- `ANTHROPIC_API_KEY`
- `API_KEY`

The service health endpoint is:

```text
/api/health
```

Never commit credentials to Git.

## API

Public endpoints:

```text
GET /api/health
GET /api/search?q=ebpf
GET /api/runs
GET /api/runs/latest
GET /api/runs/{id}
GET /api/engineers/{login}
GET /api/graph
```

If `API_KEY` is configured, protected endpoints require:

```text
X-API-Key: <key>
```
