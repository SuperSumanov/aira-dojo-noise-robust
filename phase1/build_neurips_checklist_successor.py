"""Build the provisional NeurIPS checklist and manuscript successor deterministically."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BASE_PAPER = ROOT / "phase1/PAPER_DRAFT_DECISION_CORPUS_9PAGE_20260902.md"
BASE_APPENDIX = ROOT / "phase1/PAPER_REPRODUCIBILITY_APPENDIX_DRAFT_20260902.md"
CHECKLIST_DATA = ROOT / "phase1/neurips_paper_checklist_provisional_v1.json"
CHECKLIST_TEMPLATE = ROOT / "phase1/render/neurips_2026_checklist_template.tex"
OUTPUT_PAPER = ROOT / "phase1/PAPER_DRAFT_DECISION_CORPUS_CHECKLIST_20260903.md"
OUTPUT_APPENDIX = ROOT / "phase1/PAPER_REPRODUCIBILITY_APPENDIX_DRAFT_20260903.md"
OUTPUT_CHECKLIST = ROOT / "phase1/render/decision_corpus_neurips_2026_checklist_provisional.tex"


PAPER_INSERT = """## Broader impacts, safeguards, and LLM use

The intended positive impact is more reliable evaluation of expensive ML-engineering
agents: provenance, uncertainty, and cost accounting can prevent misleading predictor
claims and reduce wasted executions. Potential harms include overfitting to public
competition tasks, using released trajectories to automate brittle or unsafe code
changes, and exposing credentials, private paths, competition content, or provider
outputs. Release is therefore gated by credential and path scans, content review,
provider and license clearance, a structure-only fallback, and append-only sanitized
successors. Raw competition data are not redistributed, and prospective identities,
predictions, and outcomes remain sealed until the preregistered closure rule.

LLMs are a core experimental component: AIRA-dojo uses an LLM to generate candidate
programs, and independent reward models or external LLM judges are predictor families.
Their outputs are accepted only through the recorded execution and pristine external
evaluation path; model and provider provenance gaps are reported rather than inferred.
No agent base model is fine-tuned or updated with reinforcement learning in this work.
The study involves no crowdsourcing or human-subject experiment; the evaluated units
are machine-generated programs and execution records.

"""


APPENDIX_INSERT = """## A.12 Reported experiment settings and compute-ledger status

The historical Table 1 development pool uses the frozen pair-component split with
4,689 train, 551 development, and 931 test pairs. Pair, endpoint, and referenced-run
overlap are zero across roles. Test is prediction-only; model selection uses development
task-macro accuracy, with deterministic model-order tie breaking. Runtime, stdout,
execution status, and self-reported score are excluded from execution-free inputs.

| Family | Frozen fitting and representation settings |
|---|---|
| Static LR | Symmetric pair augmentation; sparse standardization; logistic regression with `C=1.0`, `lbfgs`, no intercept, and `max_iter=4000` |
| Static GBM | Symmetric forward/reverse margin; histogram GBM with 300 iterations, learning rate 0.08, 31 leaves, minimum leaf 20, no early stopping, and seed 7 |
| Task-conditioned variants | The same estimator settings with a training-task indicator; an unseen task yields missing prediction rather than an inferred identity |
| Character TF-IDF + LR | First 20,000 code characters; train-only `char_wb` 3--5 grams, `min_df=3`, at most 30,000 features, sublinear TF; LR `C=0.5`, `lbfgs`, `max_iter=1500`, seed 0 |

Historical row/UST inference uses 20,000 percentile bootstrap replicates. The nested
task-parent headline resamples 28 tasks with seed 20260830; global-parent sensitivity
uses seed 20260831. Paired contrasts resample the same task or parent units. The label
repeatability estimate is reported only on its measured ten-task subset, and the
opportunity-yield decomposition is deterministic rather than assigned a sampling CI.

The deployment-cost attestation consists of two independent CPU runs, 3 predictor
families, 3 initialization trials per family per run (18 fits total), and 4,608 timed
single-pair queries after 10 warmups. It pins one CPU affinity on an Intel Xeon Silver
4114 host, Python 3.11.15, NumPy 1.26.4, SciPy 1.16.2, scikit-learn 1.6.1, and one thread
for BLAS/OpenMP; GPU and paid-model API use are zero for that attestation. Its online
latency excludes JSON input time but includes representation transform, both pair
orientations, and preference comparison.

This is sufficient to interpret the experiments reported in the current draft, but it
does not yet close the NeurIPS compute-resources checklist item. Total upstream corpus
production compute, historical reward-model/judge development, storage, and preliminary
or failed GPU/API work have not been consolidated into a submission-level ledger.
Until that ledger is added, the compute-resources answer remains No.

## A.13 Evidence routing for this appendix"""


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} is not a JSON object")
    return value


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.replace("\r\n", "\n").replace("\r", "\n"), encoding="utf-8", newline="\n")


def tex_escape(value: str) -> str:
    substitutions = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    return "".join(substitutions.get(character, character) for character in value)


def build_paper(data: dict[str, Any]) -> str:
    # The immutable 2026-09-02 source contains four lone CR bytes where the
    # intended LaTeX token was ``\rightarrow``. Read bytes directly so Python's
    # universal-newline handling cannot silently turn them into line breaks,
    # and repair only that hash-bound defect in this successor.
    source = BASE_PAPER.read_bytes().decode("utf-8")
    expected = data["bindings"]["base_paper_sha256"]
    if sha256(BASE_PAPER) != expected:
        raise ValueError("base paper hash drift")
    malformed_right_arrow = "\r" + "ightarrow"
    if source.count(malformed_right_arrow) != 4:
        raise ValueError("unexpected malformed right-arrow count in base paper")
    source = source.replace(malformed_right_arrow, r"\rightarrow")
    anchor = "# Conclusion\n"
    if source.count(anchor) != 1:
        raise ValueError("paper conclusion anchor is not unique")
    return source.replace(anchor, PAPER_INSERT + anchor, 1)


def build_appendix(data: dict[str, Any]) -> str:
    source = BASE_APPENDIX.read_text(encoding="utf-8")
    expected = data["bindings"]["base_appendix_sha256"]
    if sha256(BASE_APPENDIX) != expected:
        raise ValueError("base appendix hash drift")
    anchor = "## A.12 Evidence routing for this appendix"
    if source.count(anchor) != 1:
        raise ValueError("appendix evidence anchor is not unique")
    source = source.replace(anchor, APPENDIX_INSERT, 1)
    source = source.replace(
        "Status: manuscript appendix draft, 2026-09-02.",
        "Status: checklist successor draft, 2026-09-03.",
        1,
    )
    return source


def build_checklist(data: dict[str, Any]) -> str:
    if sha256(CHECKLIST_TEMPLATE) != data["bindings"]["official_checklist_template_sha256"]:
        raise ValueError("official checklist template hash drift")
    text = CHECKLIST_TEMPLATE.read_text(encoding="utf-8")
    begin = text.index("%%% BEGIN INSTRUCTIONS %%%")
    end_marker = "%%% END INSTRUCTIONS %%%"
    end = text.index(end_marker) + len(end_marker)
    text = r"\clearpage" + "\n" + text[:begin] + text[end:]
    cursor = 0
    for item in data["items"]:
        title_marker = rf"\item {{\bf {item['title']}}}"
        title_at = text.find(title_marker, cursor)
        if title_at < 0:
            raise ValueError(f"checklist title missing or out of order: {item['title']}")
        question_marker = rf"\item[] Question: {item['question_tex']}"
        question_at = text.find(question_marker, title_at)
        if question_at < 0:
            raise ValueError(f"official question drift: {item['title']}")
        next_title = text.find(r"\item {\bf ", title_at + len(title_marker))
        block_end = len(text) if next_title < 0 else next_title
        block = text[title_at:block_end]
        answer_pattern = re.compile(
            r"(?m)^(\s*\\item\[\] Answer:) \\answerTODO\{\}[^\n]*$"
        )
        justification_pattern = re.compile(
            r"(?m)^(\s*\\item\[\] Justification:) \\justificationTODO\{\}\s*$"
        )
        block, answer_count = answer_pattern.subn(
            lambda match: f"{match.group(1)} {item['latex_answer']}",
            block,
            count=1,
        )
        block, justification_count = justification_pattern.subn(
            lambda match: f"{match.group(1)} {tex_escape(item['justification'])}",
            block,
            count=1,
        )
        if answer_count != 1 or justification_count != 1:
            raise ValueError(f"answer slots malformed: {item['title']}")
        text = text[:title_at] + block + text[block_end:]
        cursor = title_at + len(block)
    if r"\answerTODO" in text or r"\justificationTODO" in text:
        raise ValueError("generated checklist still contains TODO macros")
    return text


def build_all() -> dict[str, str]:
    data = read_json(CHECKLIST_DATA)
    if data.get("status") != "PROVISIONAL_NOT_SUBMISSION_READY":
        raise ValueError("unexpected checklist status")
    outputs = {
        OUTPUT_PAPER.as_posix(): build_paper(data),
        OUTPUT_APPENDIX.as_posix(): build_appendix(data),
        OUTPUT_CHECKLIST.as_posix(): build_checklist(data),
    }
    for path_string, text in outputs.items():
        write_text(Path(path_string), text)
    return {path: hashlib.sha256(text.encode("utf-8")).hexdigest() for path, text in outputs.items()}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--print-hashes", action="store_true")
    arguments = parser.parse_args()
    hashes = build_all()
    if arguments.print_hashes:
        print(json.dumps(hashes, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
