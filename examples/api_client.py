"""Minimal standard-library client for the public Security Network Builder API."""
from __future__ import annotations

import json
from urllib.parse import urlencode
from urllib.request import Request, urlopen

def search(base_url: str, query: str, *, limit: int = 10) -> dict:
    params = urlencode({"q": query, "limit": limit})
    request = Request(f"{base_url.rstrip('/')}/api/v1/search?{params}", headers={"Accept": "application/json", "User-Agent": "snb-example-client/1"})
    with urlopen(request, timeout=10) as response:
        return json.load(response)

if __name__ == "__main__":
    print(json.dumps(search("http://127.0.0.1:8000", "cloud security", limit=5), indent=2))