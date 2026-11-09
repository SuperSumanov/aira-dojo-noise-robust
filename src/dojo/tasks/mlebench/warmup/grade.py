"""Split a combined submission and grade each part using the original grader."""

import copy
import hashlib
import json
import math
from datetime import datetime
from pathlib import Path

import pandas as pd
from mlebench.data import get_leaderboard
from mlebench.grade_helpers import CompetitionReport
from mlebench.utils import read_csv

from dojo.tasks.mlebench.warmup.datasets import check_ids

FEEDBACK_PREFIX = "\n\n[Harness warmup grading]\n"


def load_answers(path: Path):
    if path.suffix == ".csv":
        return read_csv(path, dtype={"id": str})
    if path.suffix != ".jsonl":
        raise ValueError(f"Unsupported answer format: {path.suffix}")
    records = []
    with path.open() as stream:
        for line in stream:
            record = json.loads(line)
            records.append(
                {
                    "example_id": str(record["example_id"]),
                    "annotations": record["annotations"],
                }
            )
    return records


def answer_ids(answers):
    if isinstance(answers, pd.DataFrame):
        return check_ids(answers["id"])
    identifiers = check_ids(record["example_id"] for record in answers)
    return [f"{identifier}_{kind}" for identifier in identifiers for kind in ["short", "long"]]


class WarmupGrader:
    def __init__(self, competition, warmup_dir: Path):
        self.competition = competition
        self.directory = warmup_dir.resolve()
        self.manifest = json.loads((self.directory / "private/manifest.json").read_text())
        identity = dict(self.manifest)
        version = identity.pop("version")
        if hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest() != version:
            raise ValueError("Warmup manifest identity mismatch")
        if self.manifest["format_version"] != 1 or self.manifest["competition_id"] != competition.id:
            raise ValueError("Warmup manifest belongs to another task or format")
        filename = self.manifest["answers_file"]
        if filename not in {"warmup_answers.csv", "warmup_answers.jsonl"}:
            raise ValueError("Unexpected warmup answer path")
        answer_path = self.directory / "private" / filename
        digest = hashlib.sha256(answer_path.read_bytes()).hexdigest()
        if digest != self.manifest["private_inventory"][filename]["sha256"]:
            raise ValueError("Warmup answers changed after preparation")
        sample_path = self.directory / "public/sample_submission.csv"
        digest = hashlib.sha256(sample_path.read_bytes()).hexdigest()
        if digest != self.manifest["public_inventory"]["sample_submission.csv"]["sha256"]:
            raise ValueError("Warmup sample submission changed after preparation")
        self.original_answers = load_answers(competition.answers)
        self.warmup_answers = load_answers(answer_path)
        self.original_ids = set(answer_ids(self.original_answers))
        self.warmup_ids = set(answer_ids(self.warmup_answers))
        if self.original_ids != set(self.manifest["original_submission_ids"]):
            raise ValueError("Original test answers do not match the warmup version")
        if self.warmup_ids != set(self.manifest["warmup_submission_ids"]):
            raise ValueError("Warmup answer IDs do not match the manifest")
        if self.original_ids & self.warmup_ids:
            raise ValueError("Original test and warmup IDs overlap")
        self.leaderboard = get_leaderboard(competition)
        self.lower_is_better = bool(competition.grader.is_lower_better(self.leaderboard))

    def feedback(self, status, score=None, error=None):
        feedback = {
            "status": status,
            "score": score,
            "metric": self.competition.grader.name,
            "lower_is_better": self.lower_is_better,
            "num_samples": self.manifest["actual_count"],
            "num_submission_rows": len(self.warmup_ids),
            "version": self.manifest["version"],
        }
        if error is not None:
            feedback["error"] = error
        return feedback

    def grade_part(self, submission, answers):
        score = self.competition.grader(submission.copy(deep=True), copy.deepcopy(answers))
        if score is None or not math.isfinite(score):
            return None
        return float(score)

    def invalid_submission(self, submission_path, output_dir, error):
        return self.write_report(
            submission_path,
            output_dir,
            None,
            self.feedback("invalid_submission", error=error),
            False,
        )

    def grade(self, submission_path: Path, output_dir: Path):
        try:
            submission = read_csv(submission_path, dtype={"id": str, "example_id": str})
        except (pd.errors.ParserError, pd.errors.EmptyDataError, UnicodeDecodeError):
            return self.invalid_submission(submission_path, output_dir, "invalid_csv")
        identifier_column = "example_id" if isinstance(self.original_answers, list) else "id"
        if identifier_column not in submission:
            return self.invalid_submission(submission_path, output_dir, "missing_id_column")
        identifiers = submission[identifier_column]
        if identifiers.isna().any() or identifiers.eq("").any() or identifiers.duplicated().any():
            return self.invalid_submission(submission_path, output_dir, "empty_or_duplicate_ids")
        if set(identifiers) != self.original_ids | self.warmup_ids:
            return self.invalid_submission(submission_path, output_dir, "missing_or_unexpected_ids")
        original = submission[identifiers.isin(self.original_ids)]
        warmup = submission[identifiers.isin(self.warmup_ids)]
        warmup_score = self.grade_part(warmup, self.warmup_answers)
        original_score = self.grade_part(original, self.original_answers)
        feedback = self.feedback(
            "scored" if warmup_score is not None else "invalid_submission",
            warmup_score,
            None if warmup_score is not None else "invalid_prediction_format",
        )
        valid = original_score is not None and warmup_score is not None
        return self.write_report(submission_path, output_dir, original_score, feedback, valid)

    def write_report(self, submission_path, output_dir, original_score, feedback, valid):
        rank = self.competition.grader.rank_score(original_score, self.leaderboard)
        report = CompetitionReport(
            competition_id=self.competition.id,
            score=original_score,
            gold_threshold=rank["gold_threshold"],
            silver_threshold=rank["silver_threshold"],
            bronze_threshold=rank["bronze_threshold"],
            median_threshold=rank["median_threshold"],
            any_medal=rank["gold_medal"] or rank["silver_medal"] or rank["bronze_medal"],
            gold_medal=rank["gold_medal"],
            silver_medal=rank["silver_medal"],
            bronze_medal=rank["bronze_medal"],
            above_median=rank["above_median"],
            submission_exists=submission_path.is_file(),
            valid_submission=valid,
            is_lower_better=self.lower_is_better,
            created_at=datetime.now(),
            submission_path=str(submission_path),
        ).to_dict()
        report["warmup"] = feedback
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "grading_report.json").write_text(json.dumps(report, indent=2, allow_nan=False))
        (output_dir / "warmup_report.json").write_text(json.dumps(feedback, indent=2, allow_nan=False))
        return report, feedback, valid


def append_feedback(exec_output, feedback):
    exec_output.term_out.append(FEEDBACK_PREFIX + json.dumps(feedback, allow_nan=False) + "\n")
