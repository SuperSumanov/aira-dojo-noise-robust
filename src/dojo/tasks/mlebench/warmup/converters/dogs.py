import importlib
import shutil

import pandas as pd

from dojo.tasks.mlebench.warmup.datasets import check_ids, check_images, read_table, sample_groups


def convert_dogs(source, public, private, count, seed):
    train = read_table(source / "labels.csv")
    check_images(source / "train", check_ids(train["id"]), ".jpg")
    sample = read_table(source / "sample_submission.csv")
    check_images(source / "test", check_ids(sample["id"]), ".jpg")
    selected = sample_groups(train.assign(group=train["id"]), "group", "breed", count, seed)
    module = importlib.import_module("mlebench.competitions.dog-breed-identification.prepare")
    answers = module.to_one_hot(selected[["id", "breed"]])
    if set(answers.columns) != set(sample.columns):
        raise ValueError("Dog breed columns differ from the upstream class list")
    shutil.copytree(source, public)
    for identifier in selected["id"]:
        shutil.move(public / "train" / f"{identifier}.jpg", public / "test")
    train.drop(index=selected.index).to_csv(public / "labels.csv", index=False)
    answers.to_csv(private / "warmup_answers.csv", index=False)
    extra = answers.astype({column: float for column in answers.columns if column != "id"})
    extra.loc[:, extra.columns != "id"] = 1.0 / (len(extra.columns) - 1)
    pd.concat([sample, extra]).to_csv(public / "sample_submission.csv", index=False)
    return {
        "train_count": len(train),
        "warmup_ids": selected["id"].tolist(),
        "remaining_train_ids": train.drop(index=selected.index)["id"].tolist(),
        "sampling": "whole images, balanced by breed",
        "strata": selected["breed"].value_counts().to_dict(),
    }
