import json
import random
import shutil

import pandas as pd

from dojo.tasks.mlebench.warmup.datasets import check_ids, read_table


def convert_tensorflow(source, public, private, count, seed):
    """Reservoir-sample JSONL line numbers, then stream the split in a second pass."""
    train_path = source / "simplified-nq-train.jsonl"
    generator = random.Random(seed)
    selected_lines = []
    train_count = 0
    with train_path.open("rb") as stream:
        for line_number, line in enumerate(stream):
            if not line.strip():
                raise ValueError("Unexpected blank JSONL record")
            train_count += 1
            if line_number < count:
                selected_lines.append(line_number)
            else:
                position = generator.randrange(line_number + 1)
                if position < count:
                    selected_lines[position] = line_number
    if count >= train_count:
        raise ValueError("Warmup must leave training records")
    public.mkdir()
    for path in source.iterdir():
        if path.name != train_path.name:
            if not path.is_file():
                raise ValueError(f"Unexpected TensorFlow QA public entry: {path.name}")
            shutil.copyfile(path, public / path.name)
    selected_lines = set(selected_lines)
    selected_ids = []
    with (
        train_path.open("rb") as original,
        (public / train_path.name).open("wb") as remaining,
        (public / "simplified-nq-test.jsonl").open("ab") as test,
        (private / "warmup_answers.jsonl").open("wb") as answers,
    ):
        for line_number, line in enumerate(original):
            if line_number not in selected_lines:
                remaining.write(line)
                continue
            record = json.loads(line)
            identifier = str(record["example_id"])
            selected_ids.append(identifier)
            if len(record["annotations"]) != 1:
                raise ValueError("Expected one TensorFlow QA annotation per record")
            record["example_id"] = identifier
            answers.write((json.dumps(record, ensure_ascii=False) + "\n").encode())
            inputs = {
                key: record[key] for key in ["example_id", "question_text", "document_text", "long_answer_candidates"]
            }
            test.write((json.dumps(inputs, ensure_ascii=False) + "\n").encode())
    check_ids(selected_ids)
    sample = read_table(source / "sample_submission.csv")
    extra = pd.DataFrame(
        [
            {"example_id": f"{identifier}_{kind}", "PredictionString": ""}
            for identifier in selected_ids
            for kind in ["short", "long"]
        ]
    )
    pd.concat([sample, extra]).to_csv(public / "sample_submission.csv", index=False)
    return {
        "train_count": train_count,
        "warmup_ids": selected_ids,
        "sampling": "whole JSONL records, reservoir sampling by line number",
    }
