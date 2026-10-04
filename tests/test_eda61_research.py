"""Synthetic research-route validation fixtures; never native source-count evidence."""

import copy
import hashlib
import json
from urllib.parse import urlencode

import pytest

from lyme_gap_atlas_ml.eda61_research import (
    CT_LEGACY,
    CT_PLANNING,
    FIELDS,
    RESOURCE,
    MappingBlocked,
    admit,
)


def packet():
    release = {"RELEASE_ID": "synthetic", "BUNDLE_SHA256": "a" * 64}
    consumer = [
        [{"status": "Statement executed successfully."}],
        [release],
        [
            {
                "SOURCE_KEY": "context_svi",
                "VINTAGE": "2022 (2018-2022 ACS)",
                "RELEASE_VERSION": "synthetic",
            }
        ],
        [
            {
                "MEASURE_ID": measure,
                "UNIT": unit,
                "TEMPORAL_GRAIN": "2018-2022 ACS",
                "RELEASE_VERSION": "synthetic",
            }
            for measure, unit in (
                ("population_2022", "people"),
                ("svi_percentile_2022", "percentile"),
            )
        ],
        [
            {
                "FIPS": fips,
                "STATE": "synthetic",
                "POPULATION": 1000,
                "SVI_PERCENTILE": 0.5,
                "RELEASE_ID": "synthetic",
            }
            for fips in ["01001"] + [str(20000 + i) for i in range(3143)]
        ],
        [release],
    ]
    metadata = {
        "id": "x5j9-wybp",
        "name": "synthetic",
        "description": "County of residence 2022",
        "rowsUpdatedAt": 1,
        "viewLastModified": 1,
        "columns": [{"fieldName": key, "dataTypeName": value} for key, value in FIELDS.items()],
    }
    rows = [
        {
            ":id": "row-z",
            ":created_at": "2025-01-01T00:00:00Z",
            ":updated_at": "2025-01-01T00:00:00Z",
            "year": "2022",
            "state": "synthetic",
            "fips": "01001",
            "case_status": "Confirmed",
            "sex": "synthetic",
            "age_cat_yrs": "synthetic",
            "frequency": "0",
        },
        {
            ":id": "row-a",
            ":created_at": "2025-01-01T00:00:00Z",
            ":updated_at": "2025-01-01T00:00:00Z",
            "year": "2022",
            "state": "synthetic",
            "fips": "Unknown",
            "case_status": "Probable",
            "sex": "synthetic",
            "age_cat_yrs": "synthetic",
            "frequency": "2",
        },
    ]
    query = (
        RESOURCE
        + "?"
        + urlencode(
            {
                "$where": "year='2022'",
                "$order": ":id ASC",
                "$limit": "250001",
                "$select": ":id,:created_at,:updated_at," + ",".join(FIELDS),
            }
        )
    )
    return consumer, metadata, rows, query


def run(consumer, metadata, rows, query, *, count=None, after=None, v3=False):
    c, p, m = (json.dumps(x).encode() for x in (consumer, rows, metadata))
    return admit(
        c,
        hashlib.sha256(c).hexdigest(),
        p,
        hashlib.sha256(p).hexdigest(),
        m,
        json.dumps(after or metadata).encode(),
        json.dumps([{"row_count": str(len(rows) if count is None else count)}]).encode(),
        query,
        geography_amendment_v3=v3,
    )


def test_projection_units_are_not_fabricated_native_svi_records() -> None:
    counties, evidence = run(*packet())
    assert len(counties) == 1 and counties[0].floor == 0
    assert evidence["accounting"]["svi_source_rows"] is None
    assert evidence["accounting"]["svi_consumer_projection_rows"] == 3144
    assert evidence["native_svi_source_rows"] is None
    assert evidence["unallocated_source_rows"] == {"Unknown": 1}
    assert evidence["unallocated_published_frequency"] == {"Unknown": 2}
    assert evidence["private_record_hashes_or_reviewed_envelopes_proven"] is False


@pytest.mark.parametrize(
    "field,value",
    [
        ("case_status", "Suspect"),
        ("year", "2023"),
        ("frequency", "Suppressed"),
        ("frequency", "-1"),
        ("frequency", "0.5"),
        ("fips", "invalid"),
    ],
)
def test_unapproved_publisher_values_stop(field, value) -> None:
    consumer, metadata, rows, query = packet()
    rows[0][field] = value
    with pytest.raises(ValueError):
        run(consumer, metadata, rows, query)


def test_native_id_uniqueness_and_completeness_are_required() -> None:
    consumer, metadata, rows, query = packet()
    with pytest.raises(ValueError, match="incomplete"):
        run(consumer, metadata, rows, query, count=3)
    rows[1][":id"] = rows[0][":id"]
    with pytest.raises(ValueError, match="duplicate"):
        run(consumer, metadata, rows, query)


def test_historical_numeric_fips_without_canonical_denominator_blocks() -> None:
    consumer, metadata, rows, query = packet()
    rows[0]["fips"] = "09001"
    with pytest.raises(MappingBlocked, match="canonical mapping") as blocked:
        run(consumer, metadata, rows, query)
    assert blocked.value.evidence["unmatched_source_rows"] == 1
    assert blocked.value.evidence["primary_analysis_n"] is None
    assert blocked.value.evidence["association_computed"] is False


def test_publisher_revision_schema_and_order_query_cannot_change() -> None:
    consumer, metadata, rows, query = packet()
    after = copy.deepcopy(metadata)
    after["rowsUpdatedAt"] = 2
    with pytest.raises(ValueError, match="revision"):
        run(consumer, metadata, rows, query, after=after)
    metadata["columns"][0]["dataTypeName"] = "number"
    with pytest.raises(ValueError, match="schema"):
        run(consumer, metadata, rows, query)
    with pytest.raises(ValueError, match="scope/order/cap"):
        run(consumer, metadata, rows, query.replace("250001", "500000"))


@pytest.mark.parametrize(
    "change", ["release", "vintage", "unit", "period", "truncated", "duplicate"]
)
def test_consumer_frame_and_denominator_checks_stop(change) -> None:
    consumer, metadata, rows, query = packet()
    if change == "release":
        consumer[4][0]["RELEASE_ID"] = "different"
    elif change == "vintage":
        consumer[2][0]["VINTAGE"] = "2023"
    elif change == "unit":
        consumer[3][0]["UNIT"] = "percentile"
    elif change == "period":
        consumer[3][0]["TEMPORAL_GRAIN"] = "2023"
    elif change == "truncated":
        consumer[4].pop()
    else:
        consumer[4][1]["FIPS"] = consumer[4][0]["FIPS"]
    with pytest.raises(ValueError):
        run(consumer, metadata, rows, query)


def test_digest_mismatch_blocks_before_parsing() -> None:
    with pytest.raises(ValueError, match="consumer capture digest"):
        admit(b"bad", "a" * 64, b"bad", "b" * 64, b"bad", b"bad", b"bad", "bad")


def v3_packet():
    consumer, metadata, rows, query = packet()
    for index, fips in enumerate(sorted(CT_PLANNING), start=1):
        consumer[4][-index]["FIPS"] = fips
        consumer[4][-index]["STATE"] = "CT"
    for fips in sorted(CT_LEGACY):
        for stratum in range(4):
            row = copy.deepcopy(rows[0])
            row[":id"] = f"synthetic-ct-{fips}-{stratum}"
            row["fips"] = fips
            row["state"] = "CT"
            row["frequency"] = "5"
            rows.append(row)
    return consumer, metadata, rows, query


def test_v3_exact_ct_exclusion_preserves_full_capture_and_analysis_accounting() -> None:
    counties, evidence = run(*v3_packet(), v3=True)
    assert [c.fips for c in counties] == ["01001"]
    assert evidence["capture_accounting"] == {
        "full_native_publisher_rows": 34,
        "full_unique_native_ids": 34,
        "matched_numeric_source_rows": 1,
        "ct_incompatible_source_rows": 32,
        "unallocated_source_rows": 1,
        "full_consumer_projection_units": 3144,
        "ct_incompatible_consumer_units": 9,
        "non_ct_analysis_frame_units": 3135,
        "native_svi_source_rows": None,
    }
    assert evidence["accounting"]["source_observation_rows"] == 2
    assert evidence["accounting"]["canonical_unique_counties"] == 3135
    assert evidence["accounting"]["primary_unique_counties"] == 1
    assert evidence["excluded_ct_legacy_source_fips"] == sorted(CT_LEGACY)
    assert evidence["excluded_ct_consumer_fips"] == sorted(CT_PLANNING)


def test_v3_rejects_every_other_unmatched_fips_and_unexpected_ct_set() -> None:
    consumer, metadata, rows, query = v3_packet()
    rows[0]["fips"] = "99999"
    with pytest.raises(MappingBlocked):
        run(consumer, metadata, rows, query, v3=True)
    rows[-1]["fips"] = "09999"
    with pytest.raises(ValueError, match="pinned Connecticut"):
        run(consumer, metadata, rows, query, v3=True)


def test_v3_full_capture_validation_precedes_any_ct_exclusion() -> None:
    consumer, metadata, rows, query = v3_packet()
    rows[-1]["frequency"] = "invalid"
    with pytest.raises(ValueError, match="frequency"):
        run(consumer, metadata, rows, query, v3=True)
    rows[-1]["frequency"] = "5"
    rows[-1][":id"] = rows[-2][":id"]
    with pytest.raises(ValueError, match="duplicate"):
        run(consumer, metadata, rows, query, v3=True)
