from unittest.mock import Mock, patch

import pytest

from snb.public_sources import fetch_cisa_kev


def test_cisa_kev_is_bounded_and_sanitized():
    response = Mock()
    response.json.return_value = {
        "catalogVersion": "2026-10-01",
        "vulnerabilities": [
            {"cveID": "CVE-2026-1", "vendorProject": "Example", "product": "Thing"}
        ],
    }
    response.raise_for_status.return_value = None
    with patch("snb.public_sources.requests.get", return_value=response) as get:
        result = fetch_cisa_kev(limit=1)
    get.assert_called_once()
    assert result["source"] == "cisa-kev"
    assert result["count"] == 1
    assert result["vulnerabilities"][0]["cveID"] == "CVE-2026-1"


def test_cisa_kev_rejects_unbounded_limit():
    with pytest.raises(ValueError):
        fetch_cisa_kev(limit=0)
