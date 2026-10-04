import importlib.util

import pytest

from snb.report import write_pdf_report


@pytest.mark.skipif(importlib.util.find_spec("reportlab") is None, reason="optional PDF dependency")
def test_pdf_report_writes_file(tmp_path):
    result = write_pdf_report([], tmp_path, "Test")
    assert result.exists()
    assert result.suffix == ".pdf"
    assert result.stat().st_size > 0
