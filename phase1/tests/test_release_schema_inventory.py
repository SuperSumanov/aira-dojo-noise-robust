import json
from pathlib import Path

import pytest

from phase1.release_schema_inventory import InventoryError, build_inventory
from phase1.verify_release_schema_inventory import independently_inventory


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
        newline="\n",
    )


def test_value_free_schema_counts_and_independent_match(tmp_path: Path) -> None:
    source = tmp_path / "sample.jsonl"
    write_jsonl(
        source,
        [
            {"id": "secret-a", "nested": {"score": None}, "items": [1, 2]},
            {"id": "secret-b", "nested": {"score": 0.5}, "items": []},
        ],
    )
    payload = build_inventory([("sample", source)])
    resource = payload["resources"]["sample"]
    assert resource["rows"] == 2
    assert resource["fields"]["$.nested.score"]["null_occurrences"] == 1
    assert resource["fields"]["$.items"]["array_length_min"] == 0
    assert resource["fields"]["$.items"]["array_length_max"] == 2
    assert resource["fields"]["$.items[]"]["occurrences"] == 2
    assert independently_inventory(source) == {
        key: resource[key]
        for key in ("rows", "bytes", "sha256_raw", "sha256_normalized_lf", "fields")
    }
    rendered = json.dumps(payload, sort_keys=True)
    assert "secret-a" not in rendered
    assert "secret-b" not in rendered
    assert "0.5" not in rendered


def test_duplicate_resource_labels_fail_closed(tmp_path: Path) -> None:
    source = tmp_path / "sample.jsonl"
    write_jsonl(source, [{"x": 1}])
    with pytest.raises(InventoryError, match="unique"):
        build_inventory([("same", source), ("same", source)])


def test_empty_jsonl_fails_closed(tmp_path: Path) -> None:
    source = tmp_path / "empty.jsonl"
    source.write_text("\n", encoding="utf-8")
    with pytest.raises(InventoryError, match="empty"):
        build_inventory([("empty", source)])
