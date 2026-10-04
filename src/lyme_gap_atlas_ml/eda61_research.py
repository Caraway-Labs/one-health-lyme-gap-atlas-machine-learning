"""Admit retrospective publisher bytes plus governed consumer projection, not warehouse lineage."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from lyme_gap_atlas_ml.eda61 import FIPS, County, cohort, number

RESOURCE = "https://data.cdc.gov/resource/x5j9-wybp.json"
FIELDS = {
    "year": "text",
    "state": "text",
    "fips": "text",
    "case_status": "text",
    "sex": "text",
    "age_cat_yrs": "text",
    "frequency": "number",
}
CT_LEGACY = frozenset({"09001", "09003", "09005", "09007", "09009", "09011", "09013", "09015"})
CT_PLANNING = frozenset(
    {"09110", "09120", "09130", "09140", "09150", "09160", "09170", "09180", "09190"}
)


class MappingBlocked(ValueError):
    """A proven unmatched geography; retain diagnostics without computing an association."""

    def __init__(self, evidence: dict[str, Any]) -> None:
        super().__init__("numeric Lyme FIPS absent from canonical mapping")
        self.evidence = evidence


def checked_bytes(path: Path, expected: str) -> bytes:
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError(f"digest mismatch: {path.name}")
    return raw


def admit(
    consumer_raw: bytes,
    expected_consumer_sha: str,
    publisher_raw: bytes,
    expected_publisher_sha: str,
    before_raw: bytes,
    after_raw: bytes,
    count_raw: bytes,
    publisher_query_url: str,
    *,
    geography_amendment_v3: bool = False,
) -> tuple[list[County], dict[str, Any]]:
    """Input diagnostics run before aggregation; no unavailable private gate is marked PASS."""
    if hashlib.sha256(consumer_raw).hexdigest() != expected_consumer_sha:
        raise ValueError("consumer capture digest mismatch")
    if hashlib.sha256(publisher_raw).hexdigest() != expected_publisher_sha:
        raise ValueError("publisher capture digest mismatch")
    parsed = urlparse(publisher_query_url)
    query = parse_qs(parsed.query)
    expected_query = {
        "$where": ["year='2022'"],
        "$order": [":id ASC"],
        "$limit": ["250001"],
        "$select": [":id,:created_at,:updated_at," + ",".join(FIELDS)],
    }
    if (
        parsed.scheme != "https"
        or parsed.netloc != "data.cdc.gov"
        or parsed.path != "/resource/x5j9-wybp.json"
        or query != expected_query
    ):
        raise ValueError("publisher query scope/order/cap changed")
    if any(
        len(raw) > 64 * 1024 * 1024 for raw in (publisher_raw, before_raw, after_raw, count_raw)
    ):
        raise ValueError("publisher byte cap")
    before, after = json.loads(before_raw), json.loads(after_raw)
    keys = ("id", "name", "description", "rowsUpdatedAt", "viewLastModified", "columns")
    if any(before.get(key) != after.get(key) for key in keys):
        raise ValueError("publisher revision changed during capture")
    if before.get("id") != "x5j9-wybp":
        raise ValueError("wrong governed resource")
    fields = {
        c["fieldName"]: c["dataTypeName"]
        for c in before["columns"]
        if not c["fieldName"].startswith(":")
    }
    if fields != FIELDS:
        raise ValueError("governed native schema changed")
    description = str(before.get("description", "")).lower()
    if "county of residence" not in description or "2022" not in description:
        raise ValueError("publisher geography/era semantics changed")
    rows = json.loads(publisher_raw)
    expected_rows = int(json.loads(count_raw)[0]["row_count"])
    if not isinstance(rows, list) or not 0 < len(rows) <= 250000 or len(rows) != expected_rows:
        raise ValueError("publisher capture incomplete or over cap")
    ids: list[str] = []
    human = []
    categories = Counter[str]()
    unallocated = Counter[str]()
    unallocated_frequency = Counter[str]()
    for row in rows:
        if not set(FIELDS) <= row.keys() or not {":id", ":created_at", ":updated_at"} <= row.keys():
            raise ValueError("native fields/identity missing")
        native_id = row[":id"]
        if not isinstance(native_id, str) or not native_id:
            raise ValueError("invalid native identity")
        ids.append(native_id)
        if row["year"] != "2022" or row["case_status"] not in {"Confirmed", "Probable"}:
            raise ValueError("source year/case category outside approved scope")
        frequency = number(row["frequency"])
        if frequency is None or frequency < 0 or not frequency.is_integer():
            raise ValueError("invalid published frequency")
        fips = row["fips"]
        if not isinstance(fips, str) or (
            not FIPS.fullmatch(fips) and fips not in {"Suppressed", "Unknown"}
        ):
            raise ValueError("unsupported geography state")
        categories[row["case_status"]] += 1
        if not FIPS.fullmatch(fips):
            unallocated[fips] += 1
            unallocated_frequency[fips] += int(frequency)
        human.append(
            {
                "source_record_id": native_id,
                "county_fips": fips,
                "report_year": 2022,
                "case_status": row["case_status"],
                "frequency": frequency,
            }
        )
    if len(set(ids)) != len(ids):
        raise ValueError("native identities duplicate")
    # Socrata :id values are opaque, not lexically sortable representations of
    # its native row_id ordering. The retained exact :id ASC query establishes
    # native request order; never reorder or manufacture native identities.
    consumer = json.loads(consumer_raw)
    if not isinstance(consumer, list) or len(consumer) != 6 or consumer[1] != consumer[5]:
        raise ValueError("consumer release/capture shape changed")
    if len(consumer[1]) != 1 or len(consumer[4]) != 3144:
        raise ValueError("consumer capture completeness not established")
    release = consumer[1][0]
    source = next((s for s in consumer[2] if s.get("SOURCE_KEY") == "context_svi"), None)
    if source is None or source.get("VINTAGE") != "2022 (2018-2022 ACS)":
        raise ValueError("consumer SVI vintage changed")
    if source.get("RELEASE_VERSION") != release["RELEASE_ID"]:
        raise ValueError("consumer source/release mismatch")
    for measure, unit in (("population_2022", "people"), ("svi_percentile_2022", "percentile")):
        matches = [m for m in consumer[3] if m.get("MEASURE_ID") == measure]
        if len(matches) != 1 or matches[0].get("UNIT") != unit:
            raise ValueError("consumer measure/unit mismatch")
        if matches[0].get("TEMPORAL_GRAIN") != "2018-2022 ACS":
            raise ValueError("consumer denominator/percentile period mismatch")
        if matches[0].get("RELEASE_VERSION") != release["RELEASE_ID"]:
            raise ValueError("consumer measure/release mismatch")
    canonical = []
    svi = []
    for row in consumer[4]:
        if row.get("RELEASE_ID") != release["RELEASE_ID"]:
            raise ValueError("consumer row/release mismatch")
        fips = row.get("FIPS")
        if not isinstance(fips, str) or not FIPS.fullmatch(fips) or row.get("STATE") is None:
            raise ValueError("invalid consumer county identity")
        canonical.append(fips)
        svi.append(
            {
                "county_fips": fips,
                "population": row.get("POPULATION"),
                "svi_percentile": row.get("SVI_PERCENTILE"),
            }
        )
    if len(set(canonical)) != len(canonical):
        raise ValueError("duplicate canonical consumer FIPS")
    canonical_set = set(canonical)
    numeric = [row for row in human if FIPS.fullmatch(str(row["county_fips"]))]
    ct_source_rows = []
    full_consumer_count = len(canonical)
    if geography_amendment_v3:
        source_ct = {
            str(row["county_fips"]) for row in numeric if str(row["county_fips"]).startswith("09")
        }
        consumer_ct = {fips for fips in canonical if fips.startswith("09")}
        if source_ct != CT_LEGACY or consumer_ct != CT_PLANNING:
            raise ValueError("v3 pinned Connecticut geography sets changed")
        ct_source_rows = [row for row in human if row["county_fips"] in CT_LEGACY]
        human = [row for row in human if row["county_fips"] not in CT_LEGACY]
        canonical = [fips for fips in canonical if fips not in CT_PLANNING]
        svi = [row for row in svi if row["county_fips"] not in CT_PLANNING]
        canonical_set = set(canonical)
    unmatched = Counter(
        str(row["county_fips"])
        for row in human
        if FIPS.fullmatch(str(row["county_fips"])) and row["county_fips"] not in canonical_set
    )
    if unmatched:
        raise MappingBlocked(
            {
                "validation_status": "MAPPING_BLOCKED",
                "association_computed": False,
                "source_observation_rows": len(rows),
                "native_unique_ids": len(set(ids)),
                "case_category_source_rows": dict(categories),
                "numeric_fips_source_rows": len(numeric),
                "numeric_fips_unique_geographies": len({row["county_fips"] for row in numeric}),
                "unmatched_source_rows": sum(unmatched.values()),
                "unmatched_source_fips_rows": dict(sorted(unmatched.items())),
                "matched_unique_county_candidates": len(
                    {row["county_fips"] for row in numeric if row["county_fips"] in canonical_set}
                ),
                "unallocated_source_rows": dict(unallocated),
                "unallocated_published_frequency": dict(unallocated_frequency),
                "consumer_projection_rows": len(consumer[4]),
                "native_svi_source_rows": None,
                "consumer_release": release,
                "consumer_sha256": expected_consumer_sha,
                "publisher_sha256": expected_publisher_sha,
                "publisher_query_url": publisher_query_url,
                "publisher_revision": {
                    k: before.get(k) for k in ("rowsUpdatedAt", "viewLastModified")
                },
                "primary_analysis_n": None,
            }
        )
    # All source validation precedes this first aggregation. No native SVI IDs are fabricated.
    counties, accounting = cohort(svi, human, canonical, svi_observation_unit="consumer_projection")
    matched_numeric = [row for row in human if row["county_fips"] in canonical_set]
    capture_accounting = {
        "full_native_publisher_rows": len(rows),
        "full_unique_native_ids": len(ids),
        "matched_numeric_source_rows": len(matched_numeric),
        "ct_incompatible_source_rows": len(ct_source_rows),
        "unallocated_source_rows": sum(unallocated.values()),
        "full_consumer_projection_units": full_consumer_count,
        "ct_incompatible_consumer_units": full_consumer_count - len(canonical),
        "non_ct_analysis_frame_units": len(canonical),
        "native_svi_source_rows": None,
    }
    if len(rows) != len(matched_numeric) + len(ct_source_rows) + sum(unallocated.values()):
        raise ValueError("native source partition does not reconcile")
    return counties, {
        "accounting": accounting,
        "capture_accounting": capture_accounting,
        "geography_amendment_v3": geography_amendment_v3,
        "excluded_ct_legacy_source_fips": sorted(CT_LEGACY) if geography_amendment_v3 else [],
        "excluded_ct_consumer_fips": sorted(CT_PLANNING) if geography_amendment_v3 else [],
        "case_category_source_rows": dict(categories),
        "unallocated_source_rows": dict(unallocated),
        "unallocated_published_frequency": dict(unallocated_frequency),
        "native_publisher_ids": len(ids),
        "consumer_release": release,
        "consumer_sha256": expected_consumer_sha,
        "publisher_sha256": expected_publisher_sha,
        "publisher_revision": {k: before.get(k) for k in ("rowsUpdatedAt", "viewLastModified")},
        "native_svi_source_rows": None,
        "historical_first_publication": None,
        "input_admission": (
            "retrospective-publisher-plus-governed-consumer-v3-non-ct"
            if geography_amendment_v3
            else "retrospective-publisher-plus-governed-consumer-v2"
        ),
        "publisher_query_url": publisher_query_url,
        "private_record_hashes_or_reviewed_envelopes_proven": False,
    }
