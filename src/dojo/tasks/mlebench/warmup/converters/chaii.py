import shutil

import pandas as pd

from dojo.tasks.mlebench.warmup.datasets import check_ids, read_table, sample_groups


def convert_chaii(source, public, private, count, seed):
    train = read_table(source / "train.csv")
    check_ids(train["id"])
    test = read_table(source / "test.csv")
    check_ids(test["id"])
    selected = sample_groups(train, "context", "language", count, seed)
    for row in selected.itertuples():
        start = int(row.answer_start)
        if row.context[start : start + len(row.answer_text)] != row.answer_text:
            raise ValueError("chaii answer_start does not match answer_text")
    shutil.copytree(source, public)
    train.drop(index=selected.index).to_csv(public / "train.csv", index=False)
    pd.concat([test, selected[test.columns]]).to_csv(public / "test.csv", index=False)
    answers = selected[["id", "answer_text"]].rename(columns={"answer_text": "PredictionString"})
    answers.to_csv(private / "warmup_answers.csv", index=False)
    sample = read_table(source / "sample_submission.csv")
    extra = answers.copy()
    extra["PredictionString"] = "dummy text"
    pd.concat([sample, extra]).to_csv(public / "sample_submission.csv", index=False)
    return {
        "train_count": len(train),
        "warmup_ids": selected["id"].tolist(),
        "sampling": "whole context groups, balanced by language",
        "strata": selected["language"].value_counts().to_dict(),
        "remaining_train_ids": train.drop(index=selected.index)["id"].tolist(),
    }
