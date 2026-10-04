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


## Production readiness

Before a production start, verify:

    SNB_ENV=production SNB_ALLOWED_HOSTS=your-host.example API_KEYS=replace-with-a-long-random-key AI_PROVIDER=offline python -m uvicorn snb.api.app:app --host 0.0.0.0 --port 8000

Then check `/api/health` and `/api/readiness`. `/api/readiness` must report `status: ok`. Production readiness fails closed when private API authentication, trusted hosts, the history/jobs stores, or a configured remote AI provider is invalid.

The protected worker status endpoint is `GET /api/worker/status` with `X-API-Key`. It reports queue counts only; job payloads, results, API keys, and provider secrets are never returned.

## Rollback

For a container deployment, rollback means returning the service to the last known-good image/commit and verifying health and readiness before accepting traffic. Do not roll back by deleting or manually editing persistent database files.

Keep database migrations backward-compatible. If a migration cannot safely roll back, restore the last known-good database backup before starting the older application version.

## Recovery checklist

1. Stop traffic or scale the service down if the failure is active.
2. Capture readiness, container logs, and the deployment revision.
3. Identify whether the failure is application, GitHub upstream, AI provider, or persistent storage.
4. Roll back the application revision if the failure was introduced by the deployment.
5. Restore persistent storage only when data corruption/loss is confirmed.
6. Re-run health/readiness and a public read-only smoke test.
7. Record the incident and root cause before the next release.
