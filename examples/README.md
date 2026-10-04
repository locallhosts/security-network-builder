# API client examples

The public API is versioned under /api/v1. The examples intentionally use only the standard library.

## cURL

    curl "http://127.0.0.1:8000/api/v1/search?q=cloud%20security&limit=5"

## Python

    python examples/api_client.py

The public endpoints require no API key. Private endpoints require the configured X-API-Key header and should never expose that key in browser-side code.