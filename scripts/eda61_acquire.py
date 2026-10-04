"""One bounded publisher capture of governed x5j9-wybp; never ingest or query Snowflake."""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1] / "outputs" / "eda61-publisher"
RESOURCE = "https://data.cdc.gov/resource/x5j9-wybp.json"
METADATA = "https://data.cdc.gov/api/views/x5j9-wybp"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--resume-rejected-select", action="store_true")
    options = parser.parse_args()
    if ROOT.exists() and not options.resume_rejected_select:
        raise ValueError("immutable capture directory exists; do not silently reacquire")
    ROOT.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    receipts: list[dict[str, object]] = []
    total_bytes = 0
    resumed_before = resumed_count = None
    if options.resume_rejected_select:
        receipts = json.loads((ROOT / "receipt.json").read_text(encoding="utf-8"))
        if len(receipts) != 2 or (ROOT / "rows-2022.json").exists():
            raise ValueError("resume requires only the retained pre-row metadata/count")
        captured_start = datetime.fromisoformat(str(receipts[0]["captured_at"]))
        started -= (datetime.now(UTC) - captured_start).total_seconds()
        receipts.append(
            {
                "status": 400,
                "path": None,
                "response_body_retained": False,
                "url": RESOURCE
                + "?"
                + urlencode(
                    {
                        "$where": "year='2022'",
                        "$select": ":id,:created_at,:updated_at,*",
                        "$order": ":id ASC",
                        "$limit": "250001",
                    }
                ),
                "reason": "explicit select syntax correction",
            }
        )
        resumed_before = json.loads((ROOT / "metadata-before.json").read_bytes())
        resumed_count = json.loads((ROOT / "count-2022.json").read_bytes())
        total_bytes = sum(int(item.get("bytes", 0)) for item in receipts)

    def fetch(name: str, url: str) -> object:
        nonlocal total_bytes
        if len(receipts) >= 5 or time.monotonic() - started >= 180:
            raise ValueError("request/runtime cap")
        request = Request(
            url, headers={"Accept": "application/json", "User-Agent": "Atlas-EDA61/1"}
        )
        with urlopen(request, timeout=30) as response:
            raw = response.read(64 * 1024 * 1024 + 1)
            headers = dict(response.headers.items())
            status = response.status
        total_bytes += len(raw)
        (ROOT / name).write_bytes(raw)
        receipts.append(
            {
                "path": name,
                "url": url,
                "sha256": hashlib.sha256(raw).hexdigest(),
                "bytes": len(raw),
                "status": status,
                "headers": headers,
                "captured_at": datetime.now(UTC).isoformat(),
            }
        )
        (ROOT / "receipt.json").write_text(json.dumps(receipts, indent=2), encoding="utf-8")
        if len(raw) > 64 * 1024 * 1024 or total_bytes > 128 * 1024 * 1024:
            raise ValueError("byte cap")
        if time.monotonic() - started >= 180 or status != 200:
            raise ValueError("runtime/status failure")
        return json.loads(raw)

    before = resumed_before or fetch("metadata-before.json", METADATA)
    if not isinstance(before, dict) or before.get("id") != "x5j9-wybp":
        raise ValueError("resource identity changed")
    title = str(before.get("name", "")).lower()
    if "lyme disease" not in title or "public use aggregated data with geography" not in title:
        raise ValueError("governed publisher resource title changed")
    fields = {
        item["fieldName"]: item["dataTypeName"]
        for item in before["columns"]
        if not item["fieldName"].startswith(":")
    }
    if (
        len(fields) != 7
        or not {"year", "state", "fips", "case_status", "frequency"} <= fields.keys()
    ):
        raise ValueError("governed native source schema changed")
    query = {"$where": "year='2022'", "$select": "count(*) AS row_count"}
    count = resumed_count or fetch("count-2022.json", RESOURCE + "?" + urlencode(query))
    expected = int(count[0]["row_count"])
    if not 0 < expected <= 250000:
        raise ValueError("2022 source row count outside cap")
    query = {
        "$where": "year='2022'",
        "$select": ":id,:created_at,:updated_at," + ",".join(fields),
        "$order": ":id ASC",
        "$limit": "250001",
    }
    rows = fetch("rows-2022.json", RESOURCE + "?" + urlencode(query))
    after = fetch("metadata-after.json", METADATA)
    revision_keys = ("id", "name", "description", "rowsUpdatedAt", "viewLastModified", "columns")
    if any(before.get(key) != after.get(key) for key in revision_keys):
        raise ValueError("publisher resource/schema revision changed during capture")
    if not isinstance(rows, list) or len(rows) != expected:
        raise ValueError("incomplete source capture")
    proof = {
        "resource_key": "cdc_lyme_x5j9_wybp",
        "definition_version": 2,
        "source_profile_commit": "a62f2e32c748d0b23033c19287e7594feb5857a9",
        "retrospective_publisher_snapshot": True,
        "expected_rows": expected,
        "actual_rows": len(rows),
        "native_fields": fields,
        "revision": {key: before.get(key) for key in revision_keys if key != "columns"},
        "metadata_before_sha256": receipts[0]["sha256"],
        "metadata_after_sha256": receipts[-1]["sha256"],
        "rows_sha256": receipts[-2]["sha256"],
        "request_count": len(receipts),
        "total_bytes": total_bytes,
        "elapsed_seconds": time.monotonic() - started,
    }
    (ROOT / "capture-proof.json").write_text(json.dumps(proof, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                key: proof[key]
                for key in (
                    "expected_rows",
                    "actual_rows",
                    "rows_sha256",
                    "request_count",
                    "total_bytes",
                    "elapsed_seconds",
                )
            }
        )
    )


if __name__ == "__main__":
    main()
