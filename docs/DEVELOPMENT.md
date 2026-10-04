# Developer Guide

## Boundaries

The project has four important boundaries:
- GitHub public-data collection
- local/private analyst storage
- optional external AI providers
- public FastAPI read-only API

New code should preserve those boundaries and keep credentials server-side.

## Testing

Prefer deterministic unit tests with mocked upstream responses. For network-backed tests, cap payload size, timeout, pagination, and retry behavior.

## Release

Build from a clean checkout, run the complete test suite, build wheel and sdist, run twine check, and publish only through the protected GitHub Actions release workflow. The workflow requires the repository secret PYPI_API_TOKEN and an explicit manual publish input.

## Deployment

Render should use the Docker image and /api/health health check. Production requires explicit SNB_ALLOWED_HOSTS, API_KEYS, and a durable SNB_DATABASE_URL when hosted history is enabled. Do not use SQLite as the durable production store.

## PostgreSQL verification

The repository includes scripts/postgres_backup_restore.sh. Run it against a disposable PostgreSQL database, restore into a separate database, and verify that run counts and the latest run are identical before calling the backup procedure verified.