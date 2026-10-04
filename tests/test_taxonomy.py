from snb.taxonomy import classify_repository


def test_taxonomy_matches_public_metadata():
    result = classify_repository(
        {
            "name": "kubernetes-runtime-security",
            "description": "eBPF runtime security and supply chain provenance",
            "topics": ["ebpf", "sigstore", "sbom"],
        }
    )
    ids = {item["id"] for item in result}
    assert "cloud_security" in ids
    assert "linux_ebpf" in ids
    assert "supply_chain" in ids


def test_taxonomy_is_bounded():
    try:
        classify_repository({}, max_skills=0)
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError")
