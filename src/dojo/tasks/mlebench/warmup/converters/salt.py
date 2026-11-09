import shutil

import pandas as pd

from dojo.tasks.mlebench.warmup.datasets import check_ids, check_images, read_table


def convert_salt(source, public, private, count, seed):
    train = read_table(source / "train.csv")
    train_ids = check_ids(train["id"])
    check_images(source / "train/images", train_ids, ".png")
    check_images(source / "train/masks", train_ids, ".png")
    sample = read_table(source / "sample_submission.csv")
    check_images(source / "test/images", check_ids(sample["id"]), ".png")
    depths = read_table(source / "depths.csv")
    if set(check_ids(depths["id"])) != set(train_ids):
        raise ValueError("Salt depths must cover current prepared training IDs")
    selected = train.sample(n=count, random_state=seed)
    shutil.copytree(source, public)
    for identifier in selected["id"]:
        shutil.move(public / "train/images" / f"{identifier}.png", public / "test/images")
        (public / "train/masks" / f"{identifier}.png").unlink()
    train.drop(index=selected.index).to_csv(public / "train.csv", index=False)
    depths[~depths["id"].isin(selected["id"])].to_csv(public / "depths.csv", index=False)
    selected.to_csv(private / "warmup_answers.csv", index=False)
    extra = selected.copy()
    extra["rle_mask"] = "1 1"
    pd.concat([sample, extra]).to_csv(public / "sample_submission.csv", index=False)
    return {
        "train_count": len(train),
        "warmup_ids": selected["id"].tolist(),
        "remaining_train_ids": train.drop(index=selected.index)["id"].tolist(),
        "sampling": "whole images, seeded random sample",
    }
