import io
import json
import tarfile
from pathlib import Path

import pytest

from phase1.reconstruct_archived_generator_provenance import (
    GeneratorProvenanceError,
    build,
    sha256,
)
from phase1.verify_archived_generator_provenance import verify


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8", newline="\n")


def add_bytes(archive: tarfile.TarFile, name: str, payload: bytes) -> None:
    member = tarfile.TarInfo(name=name)
    member.size = len(payload)
    archive.addfile(member, io.BytesIO(payload))


def make_archive(path: Path, run: str, model: str, card_id: str, extra: str = "") -> None:
    config = {
        "solver": {
            "operators": {
                name: {"llm": {"client": {"model_id": model}}}
                for name in ("draft", "debug", "improve", "analyze")
            }
        },
        "comment": extra,
    }
    journal = [
        {"id": "root", "step": 0, "code": "", "metric_info": {"competition_id": "task"}},
        {"id": card_id, "step": 1, "code": "print(1)", "metric_info": {"competition_id": "task"}},
    ]
    with tarfile.open(path, "w:gz") as archive:
        add_bytes(archive, f"{run}/dojo_config.json", json.dumps(config).encode())
        add_bytes(
            archive,
            f"{run}/checkpoint/journal.jsonl",
            ("\n".join(json.dumps(item) for item in journal) + "\n").encode(),
        )


def fixture_inputs(tmp_path: Path) -> tuple[Path, Path, Path, Path, Path, Path]:
    cards_root = tmp_path / "cards"
    archives = tmp_path / "archives"
    cards_root.mkdir()
    archives.mkdir()
    batch = "cards_batch.jsonl"
    cards = cards_root / batch
    cards.write_text(
        json.dumps({"id": "task__node1", "label": {"graded": 0.7}}) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    make_archive(archives / "source.tar.gz", "run1", "deepseek-v4-flash", "node1")
    registry = tmp_path / "registry.json"
    write_json(
        registry,
        {
            "schema_version": "aira-dojo-corpus-batch-registry-v1",
            "batches": [
                {"file": batch, "sha256": sha256(cards), "bytes": cards.stat().st_size, "rows": 1}
            ],
        },
    )
    source_map = tmp_path / "source_map.json"
    write_json(
        source_map,
        {
            "schema_version": "archived-generator-provenance-source-map-v1",
            "sources": [{"batch": batch, "archive_dir": str(archives.resolve())}],
        },
    )
    overlay = tmp_path / "overlay.jsonl"
    summary = tmp_path / "summary.json"
    verification = tmp_path / "verification.json"
    return registry, source_map, cards_root, overlay, summary, verification


def test_complete_mapping_matches_independent_verifier(tmp_path: Path) -> None:
    registry, source_map, cards_root, overlay, summary, _ = fixture_inputs(tmp_path)
    payload = build(registry, source_map, cards_root, overlay, summary, True)
    receipt = verify(registry, source_map, cards_root, overlay, summary)
    assert payload["coverage"] == {
        "batches": 1,
        "target_rows": 1,
        "exact_rows": 1,
        "ambiguous_rows": 0,
        "missing_rows": 0,
    }
    assert payload["model_counts"] == {"deepseek-v4-flash": 1}
    assert receipt["status"] == "PASS"
    assert receipt["coverage"] == payload["coverage"]


def test_conflicting_model_for_same_card_fails_complete_gate(tmp_path: Path) -> None:
    registry, source_map, cards_root, overlay, summary, _ = fixture_inputs(tmp_path)
    archives = Path(json.loads(source_map.read_text(encoding="utf-8"))["sources"][0]["archive_dir"])
    make_archive(archives / "second.tar.gz", "run2", "qwen3.5-397b-a17b", "node1")
    with pytest.raises(GeneratorProvenanceError, match="unresolved rows"):
        build(registry, source_map, cards_root, overlay, summary, True)


def test_credential_shape_in_selected_config_fails_closed(tmp_path: Path) -> None:
    registry, source_map, cards_root, overlay, summary, _ = fixture_inputs(tmp_path)
    archives = Path(json.loads(source_map.read_text(encoding="utf-8"))["sources"][0]["archive_dir"])
    (archives / "source.tar.gz").unlink()
    fake_secret = "sk-" + "A" * 32
    make_archive(
        archives / "source.tar.gz", "run1", "deepseek-v4-flash", "node1", extra=fake_secret
    )
    with pytest.raises(GeneratorProvenanceError, match="credential shape"):
        build(registry, source_map, cards_root, overlay, summary, True)


def test_archive_link_fails_closed(tmp_path: Path) -> None:
    registry, source_map, cards_root, overlay, summary, _ = fixture_inputs(tmp_path)
    archives = Path(json.loads(source_map.read_text(encoding="utf-8"))["sources"][0]["archive_dir"])
    with tarfile.open(archives / "link.tar.gz", "w:gz") as archive:
        member = tarfile.TarInfo("run2/link")
        member.type = tarfile.SYMTYPE
        member.linkname = "../outside"
        archive.addfile(member)
    with pytest.raises(GeneratorProvenanceError, match="link rejected"):
        build(registry, source_map, cards_root, overlay, summary, True)
