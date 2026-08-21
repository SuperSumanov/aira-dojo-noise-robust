import hashlib
import json
from pathlib import Path

import pyarrow.parquet as pq


ROOT = Path("/research/d7/spc/yzyang4/external/traceml-61faec615b179f186dbe9c82ee59d17e14817e96")
FILES = {
    "extras/nodes.parquet": "771c77f4da2e9c328621be6e4504cf424d643bb429b3b819b443eff4cb1505c1",
    "extras/edges.parquet": "7996605cc525f52ae3fb7deba6e5907e683ec04a98924624af1f9a18d06da169",
    "extras/trees.parquet": "fcecb84842fa212a7eb4f20aad4e2a7220fd5cbce5d8f626c906773e5596c9f8",
    "extras/kernels.parquet": "ae53a786b3c93da4b4dd0b34bbfd444f059cef6b29834b341de89c735fbea9ec",
    "manifests/competitions.json": "d64a62e58dbcf4cb6d1709343e39d1ac58c10918fd12ccc7895d01c760329206",
    "code/02_parent/build_forest.py": "8527c436769f467a511f9e61001c2db6deb7714ed4fd6fd45895e966a617bf77",
    "code/02_parent/build_graph_tables.py": "bbc0e258f84ea77ade8d3b97fc7084ea5972927e0f747d94e7cd6f8578ab8d76",
    "README.md": "ce8d9d43d95861610e0feafcb9313c1764ae27e431b6ff081a018399d9360b4d",
    "LICENSE": "03363f4372252d335bb87dcbb41aa19d4918ba863e0e5b7256722388ded4cdcb",
}


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


for relative, expected in FILES.items():
    assert digest(ROOT / relative) == expected

parquet = {}
for relative in [
    "extras/nodes.parquet",
    "extras/edges.parquet",
    "extras/trees.parquet",
    "extras/kernels.parquet",
]:
    file = pq.ParquetFile(ROOT / relative)
    arrow_schema = file.schema_arrow
    parquet[relative] = {
        "columns": [
            {"name": field.name, "nullable": field.nullable, "type": str(field.type)}
            for field in arrow_schema
        ],
        "num_row_groups": file.metadata.num_row_groups,
        "num_rows": file.metadata.num_rows,
    }

competitions = json.loads((ROOT / "manifests/competitions.json").read_text(encoding="utf-8"))
if isinstance(competitions, dict):
    competition_rows = list(competitions.values())
    top_level_kind = "mapping"
elif isinstance(competitions, list):
    competition_rows = competitions
    top_level_kind = "list"
else:
    raise AssertionError("unexpected competitions manifest type")
assert all(isinstance(row, dict) for row in competition_rows)
manifest_keys = sorted({key for row in competition_rows for key in row})
direction_field = next(
    (name for name in ("score_is_max", "score_direction", "direction") if name in manifest_keys),
    None,
)
direction_values = sorted({str(row.get(direction_field)) for row in competition_rows}) if direction_field else []

forest_source = (ROOT / "code/02_parent/build_forest.py").read_text(encoding="utf-8")
graph_source = (ROOT / "code/02_parent/build_graph_tables.py").read_text(encoding="utf-8")
receipt = {
    "dataset": "TraceML-HF/TraceML",
    "files": FILES,
    "fixed_revision": "61faec615b179f186dbe9c82ee59d17e14817e96",
    "manifest_schema": {
        "direction_field": direction_field,
        "direction_values": direction_values,
        "keys": manifest_keys,
        "rows": len(competition_rows),
        "top_level_kind": top_level_kind,
    },
    "official_code_checks": {
        "canonical_priority_literal_present": 'PRIORITY = {"version": 0, "fork": 1, "code_sim": 2}' in forest_source,
        "graph_table_raw_code_path_present": '"total_lines", "raw_code_path", "alt_parents_json"' in graph_source,
        "nodes_canonical_parent_fields_present": all(
            token in graph_source for token in ('"parent_id"', '"edge_kind"', '"depth"')
        ),
    },
    "parquet_schema": parquet,
    "raw_notebook_archive_downloaded": False,
    "scope": {
        "parquet_column_values_read": [],
        "score_values_read": False,
        "support_aggregates_computed": False,
    },
    "status": "TRACEML_HUMAN_FORK_S0_SCHEMA_BOUND",
}
assert all(receipt["official_code_checks"].values())
(ROOT / "s0/schema_receipt.json").write_text(
    json.dumps(receipt, indent=2, sort_keys=True, allow_nan=False) + "\n",
    encoding="utf-8",
)
print("TRACEML_HUMAN_FORK_S0_SCHEMA_BOUND")
