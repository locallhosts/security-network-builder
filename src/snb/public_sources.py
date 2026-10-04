"""Bounded integrations with optional public security-data sources."""
from __future__ import annotations

from typing import Any

import requests

CISA_KEV_URL = "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json"


def fetch_cisa_kev(*, timeout: float = 8.0, limit: int = 100) -> dict[str, Any]:
    """Fetch the public CISA KEV catalog without credentials.

    Only a bounded catalog slice is returned; caller controls whether to cache it.
    """
    if not 1 <= limit <= 500:
        raise ValueError("limit must be between 1 and 500")
    response = requests.get(
        CISA_KEV_URL,
        timeout=max(1.0, min(float(timeout), 20.0)),
        headers={"Accept": "application/json", "User-Agent": "security-network-builder/1"},
    )
    response.raise_for_status()
    payload = response.json()
    vulnerabilities = payload.get("vulnerabilities")
    if not isinstance(vulnerabilities, list):
        raise ValueError("invalid CISA KEV payload")
    items = []
    for item in vulnerabilities[:limit]:
        if not isinstance(item, dict):
            continue
        items.append({
            "cveID": str(item.get("cveID") or ""),
            "vendorProject": str(item.get("vendorProject") or ""),
            "product": str(item.get("product") or ""),
            "vulnerabilityName": str(item.get("vulnerabilityName") or ""),
            "dateAdded": str(item.get("dateAdded") or ""),
            "dueDate": str(item.get("dueDate") or ""),
        })
    return {
        "schema_version": 1,
        "source": "cisa-kev",
        "source_url": CISA_KEV_URL,
        "catalog_version": payload.get("catalogVersion"),
        "count": len(items),
        "vulnerabilities": items,
    }
