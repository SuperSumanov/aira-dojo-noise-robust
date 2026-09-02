from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BIB = ROOT / "phase1" / "DECISION_CORPUS_REFERENCES_20260902.bib"
DRAFT = ROOT / "phase1" / "PAPER_DRAFT_DECISION_CORPUS_20260902.md"
MAP = ROOT / "phase1" / "RELATED_WORK_CITATION_MAP_20260902.md"
RECEIPT = ROOT / "phase1" / "bibliography_postpush_receipt_20260902.json"

REQUIRED_KEYS = {
    "zheng2026foreagent",
    "foster2026rpm",
    "liu2025mlagent",
    "yang2026frontisma1",
    "jerryyan2026mletrajv1",
    "jerryyan2026mletrajv3",
    "xia2025agentrm",
    "zhai2024stepq",
    "lyu2025reloc",
    "chi2024sela",
    "white2021predictors",
    "krishnakumar2022nasbenchsuitezero",
    "tu2022nasbench360",
    "sokol2024benchmarkcards",
    "reuel2024betterbench",
    "zhu2025agenticbenchmarks",
    "pattnayak2026reproevalcard",
    "toledo2025aira",
    "hambardzumyan2026aira2",
    "atinafu2026rewardhackingagents",
    "du2026mlevolve",
    "yuan2025archpilot",
}


def test_working_bibliography_has_unique_expected_entries() -> None:
    text = BIB.read_text(encoding="utf-8")
    keys = re.findall(r"^@\w+\{([^,]+),", text, flags=re.MULTILINE)
    assert len(keys) == 22
    assert len(keys) == len(set(keys))
    assert set(keys) == REQUIRED_KEYS
    assert len(re.findall(r"(?<!\\)\{", text)) == len(re.findall(r"(?<!\\)\}", text))


def test_primary_identifiers_and_urls_are_bound() -> None:
    text = BIB.read_text(encoding="utf-8")
    required_ids = {
        "2601.05930",
        "2608.13940",
        "2505.23723",
        "2607.28568",
        "2502.18407",
        "2409.09345",
        "2508.07434",
        "2410.17238",
        "2104.01177",
        "2210.03230",
        "2110.05668",
        "2410.12974",
        "2411.12990",
        "2507.02825",
        "2507.02554",
        "2603.26499",
        "2603.11337",
        "2606.06473",
        "2511.03985",
    }
    for arxiv_id in required_ids:
        assert text.count(arxiv_id) >= 2
    assert "10.18653/v1/2026.acl-short.22" in text
    assert "https://aclanthology.org/2026.acl-short.22/" in text
    for revision in (
        "4fc7f6e3d2fbd72d80bb75e1a35a9415630f3285",
        "97b1217a6ab98ccb1c1f2d4a5f044b9d03f161d3",
    ):
        assert text.count(revision) >= 2


def test_manuscript_citation_keys_resolve() -> None:
    draft = DRAFT.read_text(encoding="utf-8")
    cited = set(re.findall(r"@([a-zA-Z0-9_-]+)", draft))
    assert cited
    assert cited <= REQUIRED_KEYS
    for key in {
        "zheng2026foreagent",
        "foster2026rpm",
        "toledo2025aira",
        "white2021predictors",
        "pattnayak2026reproevalcard",
        "jerryyan2026mletrajv1",
        "jerryyan2026mletrajv3",
    }:
        assert key in cited


def test_mle_traj_artifacts_resolve_without_inventing_paper_authors() -> None:
    bib = BIB.read_text(encoding="utf-8")
    draft = DRAFT.read_text(encoding="utf-8")
    mapping = MAP.read_text(encoding="utf-8")
    identity = json.loads(
        (ROOT / "phase1" / "mle_traj_artifact_citation_identity_v1.json").read_text(
            encoding="utf-8"
        )
    )
    assert "mle-traj v1/v3 are cited" in bib
    assert identity["status"] == (
        "ARTIFACT_CITATIONS_RESOLVED_FORMAL_PROCEEDINGS_AUTHORSHIP_UNRESOLVED"
    )
    assert [item["revision"] for item in identity["sources"]] == [
        "4fc7f6e3d2fbd72d80bb75e1a35a9415630f3285",
        "97b1217a6ab98ccb1c1f2d4a5f044b9d03f161d3",
    ]
    assert identity["sources"][0]["card_proposed_proceedings_author_is_placeholder"] is True
    assert identity["publication_rule"]["infer_formal_paper_authors"] is False
    assert "literal placeholder" in draft
    assert "formal proceedings authorship remains" in mapping


def test_postpush_receipt_binds_exact_commit_and_limitations() -> None:
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
    assert receipt["exact_public_commit"] == "75eece4f6156f1a6d2300da925ba42c811b06309"
    assert receipt["focused_tests"]["passed"] == 18
    assert receipt["full_tests"]["passed"] == 2097
    assert receipt["full_tests"]["failed"] == 0
    assert receipt["bibliography"]["entries"] == 20
    assert receipt["bibliography"]["abbreviated_large_author_lists"] == 7
    assert receipt["bibliography"]["unresolved_exact_citation_identities"] == [
        "mle-traj public release/card"
    ]
    assert receipt["bibliography"]["invented_citations"] == 0
    assert receipt["exact_public_commit"] != ""
    assert sum(receipt["security"].values()) == 0
