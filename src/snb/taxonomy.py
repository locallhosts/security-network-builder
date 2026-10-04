"""Small, deterministic security technology taxonomy for public repository metadata."""
from __future__ import annotations

import re
from typing import Any

TAXONOMY: dict[str, dict[str, Any]] = {
    "cloud_security": {
        "label": "Cloud Security",
        "keywords": ("aws", "azure", "gcp", "cloud security", "kubernetes", "container security", "cspm", "iac"),
    },
    "identity_zero_trust": {
        "label": "Identity and Zero Trust",
        "keywords": ("iam", "identity", "oauth", "oidc", "saml", "spiffe", "spire", "zero trust", "mtls"),
    },
    "application_security": {
        "label": "Application Security",
        "keywords": ("owasp", "appsec", "api security", "secure coding", "sast", "dast", "web security"),
    },
    "detection_engineering": {
        "label": "Detection Engineering",
        "keywords": ("sigma", "yara", "siem", "soar", "detection engineering", "mitre attack", "threat detection"),
    },
    "linux_ebpf": {
        "label": "Linux and eBPF Security",
        "keywords": ("ebpf", "bpf", "falco", "tetragon", "kernel security", "runtime security"),
    },
    "security_automation": {
        "label": "Security Automation",
        "keywords": ("security automation", "security tooling", "security scanner", "orchestration", "devsecops"),
    },
    "vulnerability_research": {
        "label": "Vulnerability Research",
        "keywords": ("vulnerability research", "exploit", "fuzzing", "fuzzer", "memory corruption", "cve"),
    },
    "supply_chain": {
        "label": "Software Supply Chain Security",
        "keywords": ("supply chain", "sbom", "sigstore", "slsa", "dependency security", "provenance"),
    },
}


def _text(repo: dict[str, Any]) -> str:
    topics = repo.get("topics") or []
    parts = [
        str(repo.get("name") or ""),
        str(repo.get("description") or ""),
        " ".join(str(x) for x in topics[:30]),
    ]
    return re.sub(r"\s+", " ", " ".join(parts).lower()).strip()


def classify_repository(repo: dict[str, Any], *, max_skills: int = 8) -> list[dict[str, Any]]:
    """Return taxonomy matches with deterministic keyword evidence."""
    if not 1 <= max_skills <= 20:
        raise ValueError("max_skills must be between 1 and 20")
    text = _text(repo)
    matches: list[dict[str, Any]] = []
    for key, item in TAXONOMY.items():
        hits = [kw for kw in item["keywords"] if kw in text]
        if hits:
            matches.append({
                "id": key,
                "label": item["label"],
                "matches": hits[:8],
                "confidence": round(min(1.0, 0.25 * len(hits)), 2),
            })
    matches.sort(key=lambda x: (-len(x["matches"]), x["id"]))
    return matches[:max_skills]
