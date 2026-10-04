"""Issue #65 descriptive documentation association; no I/O or biological negatives."""

from __future__ import annotations

import math
import random
import re
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from typing import Any

VECTOR = ("Established", "Reported", "No records")
PATHOGEN = ("Present", "No records")
MISSING = {
    "Unknown",
    "UNKNOWN",
    "NO_QUALIFYING_RECORD",
    "NO_QUALIFYING_RECORDS",
    "NO_RECORD",
    "NO_QUALIFYING_SOURCE_RECORD",
    "Unavailable",
    "UNAVAILABLE",
    "NO_RECORDS_AVAILABLE",
    "NO_SOURCE_RECORD",
    "UNKNOWN_SOURCE_COVERAGE",
}


def _missing(value: object) -> bool:
    return value is None or (isinstance(value, str) and value in MISSING)


def vector_state(scapularis: object, pacificus: object) -> str | None:
    """Require both known species categories; union is an analytical projection."""
    for value in (scapularis, pacificus):
        if not _missing(value) and value not in VECTOR:
            raise ValueError("unrecognized vector category")
    if _missing(scapularis) or _missing(pacificus):
        return None
    if "Established" in (scapularis, pacificus):
        return "Established"
    if "Reported" in (scapularis, pacificus):
        return "Reported"
    return "No records"


def table_statistics(table: Sequence[Sequence[int]]) -> dict[str, Any]:
    """Remove empty margins, expose sparsity, refuse undefined association."""
    if not table or not table[0] or any(len(row) != len(table[0]) for row in table):
        raise ValueError("rectangular nonempty table required")
    if any(type(n) is not int or n < 0 for row in table for n in row):
        raise ValueError("nonnegative integer counts required")
    active_rows = [i for i, row in enumerate(table) if sum(row)]
    active_cols = [j for j in range(len(table[0])) if sum(row[j] for row in table)]
    n = sum(map(sum, table))
    result: dict[str, Any] = {
        "n": n,
        "active_rows": active_rows,
        "active_columns": active_cols,
        "v": None,
        "iid_reference_p": None,
    }
    if len(active_rows) < 2 or len(active_cols) < 2:
        return result | {"status": "NOT_ESTIMABLE", "reason": "zero N or constant margin"}
    observed = [[table[i][j] for j in active_cols] for i in active_rows]
    r = list(map(sum, observed))
    c = [sum(row[j] for row in observed) for j in range(len(active_cols))]
    expected = [[ri * cj / n for cj in c] for ri in r]
    residuals = [
        [(o - e) / math.sqrt(e) for o, e in zip(row, erow, strict=True)]
        for row, erow in zip(observed, expected, strict=True)
    ]
    chi2 = sum(x * x for row in residuals for x in row)
    df = (len(r) - 1) * (len(c) - 1)
    v = math.sqrt(chi2 / (n * min(len(r) - 1, len(c) - 1)))
    if df not in (1, 2) or len(c) != 2:
        raise ValueError("issue #65 supports only 2x2 or 3x2 tables")
    result |= {
        "status": "ESTIMABLE",
        "v": v,
        "chi2": chi2,
        "df": df,
        "expected": expected,
        "pearson_residuals": residuals,
    }
    if min(e for row in expected for e in row) >= 5:
        p = math.erfc(math.sqrt(chi2 / 2)) if df == 1 else math.exp(-chi2 / 2)
        return result | {"method": "chi-square IID reference", "iid_reference_p": p}
    exact_p = fixed_margin_exact(observed)
    return result | {
        "method": "fixed-margin exact IID reference",
        "iid_reference_p": exact_p,
        "exact_work_cap": 100_000,
        "exact_status": "work-cap exceeded" if exact_p is None else "complete",
    }


def fixed_margin_exact(table: Sequence[Sequence[int]], cap: int = 100_000) -> float | None:
    """Fisher/Freeman-Halton probability-ordering two-sided fixed-margin test.

    Exhaustively enumerate first-column allocations for 2 or 3 rows. Return
    unavailable at the deterministic work cap; never fall back to chi-square.
    """
    if len(table) not in (2, 3) or any(len(row) != 2 for row in table):
        raise ValueError("2x2 or 3x2 required")
    if any(type(x) is not int or x < 0 for row in table for x in row):
        raise ValueError("nonnegative integer counts required")
    margins = list(map(sum, table))
    first = sum(row[0] for row in table)
    n = sum(margins)

    def logchoose(total: int, chosen: int) -> float:
        return math.lgamma(total + 1) - math.lgamma(chosen + 1) - math.lgamma(total - chosen + 1)

    denominator = logchoose(n, first)
    observed_logp = sum(logchoose(m, row[0]) for m, row in zip(margins, table, strict=True))
    observed_logp -= denominator
    probabilities: list[float] = []
    visited = 0
    low = max(0, first - sum(margins[1:]))
    high = min(margins[0], first)
    for x in range(low, high + 1):
        remainder = first - x
        ylo = max(0, remainder - margins[2]) if len(table) == 3 else remainder
        yhi = min(margins[1], remainder) if len(table) == 3 else remainder
        for y in range(ylo, yhi + 1):
            visited += 1
            if visited > cap:
                return None
            allocation = [x, y] if len(table) == 2 else [x, y, remainder - y]
            logp = sum(logchoose(m, a) for m, a in zip(margins, allocation, strict=True))
            logp -= denominator
            if logp <= observed_logp + 1e-10:
                probabilities.append(math.exp(logp))
    return min(1.0, math.fsum(probabilities))


def _v_only(table: Sequence[Sequence[int]]) -> float | None:
    r = list(map(sum, table))
    c = [sum(row[j] for row in table) for j in range(2)]
    nr, nc = sum(x > 0 for x in r), sum(x > 0 for x in c)
    if min(nr, nc) < 2:
        return None
    n = sum(r)
    chi2 = sum(
        (table[i][j] - r[i] * c[j] / n) ** 2 / (r[i] * c[j] / n)
        for i in range(len(r))
        for j in range(2)
        if r[i] and c[j]
    )
    return math.sqrt(chi2 / (n * min(nr - 1, nc - 1)))


def _cluster_interval(clusters: Mapping[str, Sequence[Sequence[int]]]) -> dict[str, Any]:
    """State bootstrap robustness, not sampling-design or exposure uncertainty."""
    keys = sorted(clusters)
    base: dict[str, Any] = {
        "clusters": len(keys),
        "seed": 6501,
        "replicates": 2000,
        "interval": None,
        "failed_replicates": None,
    }
    if len(keys) < 10:
        return base | {"reason": "fewer than ten state clusters"}
    row_count = len(clusters[keys[0]])
    rng = random.Random(6501)
    values: list[float] = []
    for _ in range(2000):
        table = [[0, 0] for _ in range(row_count)]
        for key in rng.choices(keys, k=len(keys)):
            for i in range(row_count):
                for j in range(2):
                    table[i][j] += clusters[key][i][j]
        v = _v_only(table)
        if v is not None:
            values.append(v)
    failed = 2000 - len(values)
    if failed > 100:
        return base | {"failed_replicates": failed, "reason": ">5% degenerate replicates"}
    values.sort()

    def quantile(p: float) -> float:
        index = (len(values) - 1) * p
        lo, hi = math.floor(index), math.ceil(index)
        return values[lo] + (values[hi] - values[lo]) * (index - lo)

    return base | {"failed_replicates": failed, "interval": [quantile(0.025), quantile(0.975)]}


def analyze_counties(rows: Sequence[Mapping[str, object]], release_id: str) -> dict[str, Any]:
    """Validate a governed projection, count exclusions and analyze once per county."""
    if len(rows) != 3144:
        raise ValueError("published release must contain exactly 3144 county projection rows")
    seen: set[str] = set()
    exclusions: Counter[str] = Counter()
    states: Counter[str] = Counter()
    table = [[0, 0] for _ in range(3)]
    clusters: dict[str, list[list[int]]] = defaultdict(lambda: [[0, 0] for _ in range(3)])
    for row in rows:
        fips = row.get("FIPS")
        if not isinstance(fips, str) or not re.fullmatch(r"\d{5}", fips) or fips in seen:
            raise ValueError("invalid or duplicate county FIPS")
        seen.add(fips)
        if row.get("RELEASE_ID") != release_id:
            raise ValueError("mixed or changed release")
        scope = row.get("IN_CONTIGUOUS_TICK_SCOPE")
        if scope is not None and type(scope) is not bool:
            raise ValueError("scope must be explicit boolean or missing")
        s, p, b = (
            row.get(k) for k in ("SCAPULARIS_STATUS", "PACIFICUS_STATUS", "BURGDORFERI_STATUS")
        )
        v = vector_state(s, p)
        if not _missing(b) and b not in PATHOGEN:
            raise ValueError("unrecognized pathogen category")
        states.update({f"scapularis:{s}": 1, f"pacificus:{p}": 1, f"pathogen:{b}": 1})
        if scope is not True:
            exclusions["out_of_scope" if scope is False else "missing_scope"] += 1
            continue
        exclusions["in_scope"] += 1
        if v is None:
            exclusions["vector_unknown_in_scope"] += 1
        if _missing(b):
            exclusions["pathogen_unknown_in_scope"] += 1
        if v is None and _missing(b):
            exclusions["both_unknown_in_scope"] += 1
        if v is None or _missing(b):
            exclusions["unknown_union_in_scope"] += 1
            continue
        i, j = VECTOR.index(v), PATHOGEN.index(str(b))
        table[i][j] += 1
        clusters[fips[:2]][i][j] += 1
    sensitivity = [[table[0][j] + table[1][j] for j in range(2)], table[2]]
    sensitivity_clusters = {
        key: [[value[0][j] + value[1][j] for j in range(2)], value[2]]
        for key, value in clusters.items()
    }
    primary = table_statistics(table)
    v = primary["v"]
    disposition = (
        "NOT_ESTIMABLE"
        if v is None
        else (
            "STRONG_ASSOCIATION"
            if v >= 0.5
            else "MODERATE_ASSOCIATION"
            if v >= 0.3
            else "WEAK_OR_NO_ASSOCIATION"
        )
    )
    return {
        "release_id": release_id,
        "projection_rows": len(rows),
        "unique_counties": len(seen),
        "source_observation_rows": None,
        "source_observation_rows_reason": "not exposed by governed county projection",
        "states_all_counties": dict(sorted(states.items())),
        "exclusions": {
            k: exclusions[k]
            for k in (
                "in_scope",
                "out_of_scope",
                "missing_scope",
                "vector_unknown_in_scope",
                "pathogen_unknown_in_scope",
                "both_unknown_in_scope",
                "unknown_union_in_scope",
            )
        },
        "table": table,
        "row_labels": list(VECTOR),
        "column_labels": list(PATHOGEN),
        "primary": primary,
        "sensitivity_table": sensitivity,
        "sensitivity": table_statistics(sensitivity),
        "primary_state_robustness": _cluster_interval(clusters),
        "sensitivity_state_robustness": _cluster_interval(sensitivity_clusters),
        "disposition": disposition,
        "causal": False,
        "uncertainty_limit": "state robustness; nonrandom surveillance; cross-state dependence",
    }
