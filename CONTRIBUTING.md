# Contributing

## Development setup

    python -m venv .venv
    source .venv/bin/activate
    pip install -e ".[dev]"
    python -m pytest

The test suite is designed to run offline. Network-backed checks should be explicit and bounded.

## Before opening a pull request

1. Run python -m compileall -q src tests.
2. Run python -m pytest.
3. Run the dashboard DOM test when Node/jsdom is available.
4. Build the package with python -m build.
5. Run python -m twine check dist/* for release candidates.
6. Review the diff for secrets, private data, unsafe URLs, and unbounded external calls.
7. Update README/docs and the roadmap for user-visible changes.

## Security

Do not commit tokens, API keys, database credentials, production exports, or private analyst notes. Security reports should use the repository's private reporting process where available.

## Architecture changes

Keep public GitHub data, private analyst state, and external provider credentials on separate boundaries. New integrations must be bounded, failure-safe, documented, and covered by regression tests.