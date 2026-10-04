"""Bounded source inventories, without scientific label admission."""

import csv
import hashlib
import io
import re
from collections import Counter
from html.parser import HTMLParser
from typing import Any
from urllib.request import urlopen

URLS = {
    "wi": "https://www.dhs.wisconsin.gov/epht/lyme-county.csv",
    "eisen": "https://pmc.ncbi.nlm.nih.gov/articles/PMC4844559/",
}


class Tables(HTMLParser):
    """Extract displayed table cells, preserving blank inherited status codes."""

    def __init__(self) -> None:
        super().__init__()
        self.tables: list[list[list[str]]] = []
        self.active = False
        self.cell = False
        self.rows: list[list[str]] = []
        self.row: list[str] = []
        self.value = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "table":
            self.active = True
            self.rows = []
        if self.active and tag == "tr":
            self.row = []
        if self.active and tag in ("td", "th"):
            self.cell = True
            self.value = ""

    def handle_data(self, data: str) -> None:
        if self.active and self.cell:
            self.value += data

    def handle_endtag(self, tag: str) -> None:
        if self.active and tag in ("td", "th"):
            self.row.append(self.value.strip())
            self.cell = False
        if self.active and tag == "tr":
            self.rows.append(self.row)
        if self.active and tag == "table":
            self.tables.append(self.rows)
            self.active = False


def summarize_eisen(body: bytes) -> dict[str, Any]:
    parser = Tables()
    parser.feed(body.decode("utf-8"))
    tables = [t for t in parser.tables if len(t) > 1000 and "State and county" in t[0][0]]
    if len(tables) != 1:
        raise ValueError("unexpected I. scapularis table shape")
    changes: Counter[str] = Counter()
    states: Counter[str] = Counter()
    statuses: Counter[str] = Counter()
    identities: set[tuple[str, str]] = set()
    state = ""
    missing_sources = 0
    duplicate_rows = 0
    unresolved_rows = 0
    state_names = {row[0].strip() for row in parser.tables[0] if len(row) == 5}
    for row in tables[0][1:]:
        if not 2 <= len(row) <= 4:
            raise ValueError("unexpected table row")
        county, status, change, source = row + [""] * (4 - len(row))
        county = county.lstrip("\xa0 ")
        if not status:
            if county in state_names:
                state = county
            else:
                unresolved_rows += 1
            continue
        if status not in ("Established", "Reported") or not state:
            raise ValueError("unexpected county status")
        if (state, county) in identities:
            if change or source:
                raise ValueError("duplicate changed county identity")
            duplicate_rows += 1
            continue
        identities.add((state, county))
        statuses[status] += 1
        if change:
            if change not in ("N-E", "R-E", "N-R"):
                raise ValueError("unsupported change")
            missing_sources += int(not source)
            changes[change] += 1
            states[state] += 1
    return {
        "recorded_counties": len(identities),
        "duplicate_unchanged_rows": duplicate_rows,
        "unresolved_blank_status_rows": unresolved_rows,
        "displayed_statuses": dict(statuses),
        "table_change_codes": dict(changes),
        "changed_counties": sum(changes.values()),
        "changed_rows_without_displayed_source": missing_sources,
        "changed_by_state": dict(states.most_common()),
        "unchanged_recorded_counties": len(identities) - sum(changes.values()),
        "narrative_codes": {"N-E": 262, "R-E": 184, "N-R": 208},
        "narrative_table_reconciled": changes == Counter({"N-E": 262, "R-E": 184, "N-R": 208}),
        "admitted_ml_examples": "NOT_CERTIFIED",
    }


def summarize_wi(body: bytes) -> dict[str, Any]:
    rows = list(csv.DictReader(io.StringIO(body.decode("utf-8-sig"))))
    if len(rows) >= 10000:
        raise ValueError("row bound exceeded")
    keys: set[tuple[str, str]] = set()
    signs: Counter[str] = Counter()
    years: Counter[str] = Counter()
    for row in rows:
        if (row["Sub-topic"], row["Topic"]) != ("Counts", "Cases"):
            continue
        key = (row["Fips"], row["Year"])
        if not re.fullmatch(r"55\d{3}", key[0]) or key in keys:
            raise ValueError("invalid or duplicate county-year")
        keys.add(key)
        years[key[1]] += 1
        value = row["Number Total"]
        if not re.fullmatch(r"\d+", value):
            signs["unavailable"] += 1
        else:
            signs["explicit_zero" if int(value) == 0 else "numeric_positive"] += 1
    return {
        "source_rows": len(rows),
        "count_rows": len(keys),
        "counties": len({key[0] for key in keys}),
        "by_year": dict(sorted(years.items())),
        "count_signs": dict(signs),
        "admitted_ml_examples": "NOT_CERTIFIED",
    }


def research_alternative(source: str) -> dict[str, Any]:
    url = URLS[source]
    with urlopen(url, timeout=30) as response:  # noqa: S310
        body = response.read(2_000_001)
    if len(body) > 2_000_000:
        raise ValueError("response exceeds byte bound")
    summary = summarize_wi(body) if source == "wi" else summarize_eisen(body)
    return {
        "summary": summary,
        "url": url,
        "bytes": len(body),
        "sha256": hashlib.sha256(body).hexdigest(),
    }
