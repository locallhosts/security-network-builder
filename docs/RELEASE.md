# Release and deployment runbook

## 1. Local release gate

Run compile, tests, package build, and artifact verification:

    python -m compileall -q src tests
    python -m pytest
    python -m build
    python -m pip install twine
    python -m twine check dist/*

PDF support is optional: install .[pdf] when PDF output is required.

## 2. PyPI

Configure the repository secret PYPI_API_TOKEN. Trigger the Publish Python package workflow manually and set publish=true only after the release candidate has passed the complete CI gate.

## 3. Render

Configure these production secrets/environment values in Render:

- GITHUB_TOKEN
- API_KEYS
- SNB_DATABASE_URL using a managed PostgreSQL connection string
- SNB_ALLOWED_HOSTS with the Render hostname or custom domain
- AI_PROVIDER=offline unless an AI provider is explicitly required

The deployment manifest already defines the Docker service and /api/health health check. The application readiness endpoint will report degraded when durable PostgreSQL or production authentication is missing.

## 4. Post-deployment verification

Set BASE_URL to the deployed service and run:

    bash scripts/production_smoke.sh

Verify /api/health, /api/readiness, /api/v1/health, and a bounded public search. Also inspect Render logs for startup errors and verify that no secrets appear in logs.

## 5. PostgreSQL backup/restore

Use a disposable restore database. Run:

    SOURCE_DB_URL='postgresql://...' RESTORE_DB_URL='postgresql://...' bash scripts/postgres_backup_restore.sh

The script uses pg_dump custom format and pg_restore, then compares the run count and latest run ID between source and restore. This is a verification drill, not a substitute for scheduled provider backups.

## 6. Actual production gate

Render deployment, post-deployment verification, production smoke tests, and the live PostgreSQL backup/restore drill remain unchecked until they are executed against real infrastructure. Configuration alone does not mark those acceptance criteria complete.