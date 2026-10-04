"""Bounded publisher-current aggregates; never certify exact labels or availability."""

import hashlib
import io
import json
import re
import xml.etree.ElementTree as ET
import zipfile
from collections import Counter
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlencode
from urllib.request import urlopen

RESOURCES = ("qtbi-xd4i", "x5j9-wybp")
MAX_BYTES = 2_000_000
MAX_ROWS = 10_000
PA_URL = (
    "https://www.pa.gov/content/dam/copapwp-pagov/en/health/documents/topics/"
    "documents/diseases-and-conditions/vectorborne/OfficialLymeByReport2024withMap.xlsx"
)


def summarize_pa(body: bytes) -> dict[str, Any]:
    """Inspect the frozen worksheet shape; count numeric cells, never approve labels."""
    ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    with zipfile.ZipFile(io.BytesIO(body)) as archive:
        if sum(item.file_size for item in archive.infolist()) > 10_000_000:
            raise ValueError("workbook exceeds uncompressed bound")
        strings = [
            "".join(item.itertext())
            for item in ET.fromstring(archive.read("xl/sharedStrings.xml")).findall("m:si", ns)
        ]
        sheet = ET.fromstring(archive.read("xl/worksheets/sheet4.xml"))
        rows: list[dict[str, str]] = []
        for xml_row in sheet.findall(".//m:row", ns):
            values = {}
            for cell in xml_row.findall("m:c", ns):
                xml_value = cell.find("m:v", ns)
                if xml_value is not None and xml_value.text is not None:
                    text = xml_value.text
                    if cell.get("t") == "s":
                        text = strings[int(text)]
                    values[re.sub(r"\d", "", cell.attrib["r"])] = text
            if values:
                rows.append(values)
        names = [row["A"] for row in rows[1:]]
        if len(names) != 67 or len(set(names)) != 67 or rows[0].get("A") != "Jurisdiction":
            raise ValueError("unexpected county worksheet shape")
        years = {col: year for col, year in rows[0].items() if col != "A"}
        if set(years.values()) != {str(year) for year in range(1980, 2025)}:
            raise ValueError("unexpected period range")
        by_year = {}
        for col, year in years.items():
            counts: Counter[str] = Counter()
            total = 0
            for row in rows[1:]:
                value = row.get(col)
                if value == "*":
                    counts["suppressed"] += 1
                elif value is None:
                    counts["missing"] += 1
                elif re.fullmatch(r"\d+", value):
                    counts["explicit_zero" if int(value) == 0 else "numeric_positive"] += 1
                    total += int(value)
                else:
                    raise ValueError("unexpected count cell")
            by_year[year] = {**dict(counts), "numeric_sum": total}
        windows = {}
        for start, end in ((1980, 2024), (2011, 2016), (2017, 2019), (2020, 2021), (2022, 2024)):
            windows[f"{start}-{end}"] = {
                key: sum(by_year[str(year)].get(key, 0) for year in range(start, end + 1))
                for key in ("numeric_positive", "explicit_zero", "suppressed", "missing")
            }
        return {
            "county_year_cells": len(names) * len(years),
            "counties": len(names),
            "by_year": by_year,
            "windows": windows,
            "core_metadata": archive.read("docProps/core.xml").decode(),
            "historical_availability": "UNKNOWN",
        }


def research_pa() -> dict[str, Any]:
    with urlopen(PA_URL, timeout=30) as response:  # noqa: S310
        body = response.read(MAX_BYTES + 1)
    if len(body) > MAX_BYTES:
        raise ValueError("response exceeds research byte bound")
    return {
        "summary": summarize_pa(body),
        "receipt": {
            "url": PA_URL,
            "bytes": len(body),
            "sha256": hashlib.sha256(body).hexdigest(),
            "retrieved_at": datetime.now(UTC).isoformat(),
        },
    }


def fetch_json(url: str) -> tuple[Any, dict[str, Any]]:
    """One request, timeout and hard response bound; no retries or raw persistence."""
    with urlopen(url, timeout=30) as response:  # noqa: S310
        body = response.read(MAX_BYTES + 1)
    if len(body) > MAX_BYTES:
        raise ValueError("response exceeds research byte bound")
    return json.loads(body), {
        "url": url,
        "retrieved_at": datetime.now(UTC).isoformat(),
        "bytes": len(body),
        "sha256": hashlib.sha256(body).hexdigest(),
    }


def summarize(rows: list[dict[str, str]]) -> dict[str, Any]:
    """Count published county keys only, excluding unallocated source identities."""
    if len(rows) >= MAX_ROWS:
        raise ValueError("possible truncated aggregate")
    keys: set[tuple[str, str]] = set()
    county_states: dict[str, str] = {}
    years: Counter[str] = Counter()
    states: Counter[str] = Counter()
    source_rows = 0
    noncounty_rows = 0
    for row in rows:
        source_rows += int(row["n"])
        fips = row.get("fips", "")
        if not re.fullmatch(r"\d{5}", fips):
            noncounty_rows += int(row["n"])
            continue
        key = (fips, row["year"])
        if key in keys:
            raise ValueError("duplicate aggregate county-year")
        keys.add(key)
        county_states[fips] = row["state"]
        years[row["year"]] += 1
        states[row["state"]] += 1
    return {
        "source_rows": source_rows,
        "noncounty_rows": noncounty_rows,
        "published_county_years": len(keys),
        "counties": len(county_states),
        "source_state_labels": len(states),
        "fips_prefixes": len({fips[:2] for fips in county_states}),
        "by_year": dict(sorted(years.items())),
        "by_state": dict(states.most_common()),
        "exact_label_count": "NOT_CERTIFIED_BY_THIS_QUERY",
        "historical_availability": "UNKNOWN",
    }


def research() -> dict[str, Any]:
    result: dict[str, Any] = {}
    for resource in RESOURCES:
        metadata, metadata_receipt = fetch_json(f"https://data.cdc.gov/api/views/{resource}")
        query = urlencode(
            {
                "$select": "year,state,fips,count(*) as n,sum(frequency) as published_floor",
                "$group": "year,state,fips",
                "$order": "year,state,fips",
                "$limit": MAX_ROWS,
            }
        )
        rows, receipt = fetch_json(f"https://data.cdc.gov/resource/{resource}.json?{query}")
        result[resource] = {
            "summary": summarize(rows),
            "aggregate_receipt": receipt,
            "metadata_receipt": metadata_receipt,
            "publisher_metadata": {
                k: metadata.get(k)
                for k in (
                    "name",
                    "description",
                    "createdAt",
                    "publicationDate",
                    "rowsUpdatedAt",
                )
            },
            "fields": [c.get("fieldName") for c in metadata.get("columns", [])],
        }
    return result
