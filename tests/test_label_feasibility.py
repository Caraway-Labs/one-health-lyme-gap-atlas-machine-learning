import io
import zipfile

import pytest

from lyme_gap_atlas_ml.label_feasibility import MAX_ROWS, summarize, summarize_pa


def test_missing_county_is_not_a_negative_and_source_rows_are_not_labels():
    result = summarize(
        [
            {"year": "2023", "state": "A", "fips": "01001", "n": "20"},
            {"year": "2023", "state": "A", "fips": "Suppressed", "n": "3"},
            {"year": "2022", "state": "A", "fips": "01001", "n": "4"},
        ]
    )
    assert result["source_rows"] == 27
    assert result["published_county_years"] == 2
    assert result["counties"] == 1
    assert result["noncounty_rows"] == 3
    assert result["exact_label_count"] == "NOT_CERTIFIED_BY_THIS_QUERY"
    assert result["historical_availability"] == "UNKNOWN"


def test_duplicate_and_possible_truncation_fail_closed():
    row = {"year": "2023", "state": "A", "fips": "01001", "n": "1"}
    with pytest.raises(ValueError, match="duplicate"):
        summarize([row, row])
    with pytest.raises(ValueError, match="truncated"):
        summarize([row] * MAX_ROWS)


def test_pa_changed_geography_cannot_silently_produce_counts():
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(
            "xl/sharedStrings.xml",
            '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"/>',
        )
        archive.writestr(
            "xl/worksheets/sheet4.xml",
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            '<sheetData><row><c r="A2"><v>0</v></c></row></sheetData></worksheet>',
        )
    with pytest.raises(ValueError, match="county worksheet"):
        summarize_pa(buffer.getvalue())
