"""Stream rows into per-split parquet files.

A single SFT row carries a full prompt plus completion, so rows are written in
small batches instead of being materialised all at once.  Empty splits still get
a file so the output layout does not depend on the data.
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

MESSAGE_TYPE = pa.list_(pa.struct([("role", pa.string()), ("content", pa.string())]))


class SplitParquetWriter:
    """Write dict rows into ``<output_dir>/<name>_<split>.parquet``."""

    def __init__(
        self,
        output_dir: Path,
        name: str,
        schema: pa.Schema,
        splits: tuple[str, ...] = ("train", "val"),
        batch_size: int = 256,
    ) -> None:
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.name = name
        self.schema = schema
        self.splits = splits
        self.batch_size = batch_size
        self._writers: dict[str, pq.ParquetWriter] = {}
        self._buffers: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self.counts: dict[str, int] = {split: 0 for split in splits}

    def write(self, split: str, row: dict[str, Any]) -> None:
        if split not in self.counts:
            raise ValueError(f"Unknown split {split!r}; expected one of {self.splits}")
        buffer = self._buffers[split]
        buffer.append(row)
        if len(buffer) >= self.batch_size:
            self._flush(split)

    def _flush(self, split: str) -> None:
        rows = self._buffers[split]
        if not rows:
            return
        if split not in self._writers:
            path = self.output_dir / f"{self.name}_{split}.parquet"
            self._writers[split] = pq.ParquetWriter(path, self.schema)
        self._writers[split].write_table(pa.Table.from_pylist(rows, schema=self.schema))
        self.counts[split] += len(rows)
        self._buffers[split] = []

    def close(self) -> None:
        for split in self.splits:
            self._flush(split)
            if split not in self._writers:
                # Keep the file layout stable even when a split has no rows.
                path = self.output_dir / f"{self.name}_{split}.parquet"
                self._writers[split] = pq.ParquetWriter(path, self.schema)
        for writer in self._writers.values():
            writer.close()
