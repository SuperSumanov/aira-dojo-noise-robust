# MLE critic data

本目录保存 lookahead reward model 的 cards、pair、tau 和学生结果 CSV。数据口径、来源 commit、行数和不可精确复原的 L2 文件说明见 [`src/mle_critic/docs/train/LOOKAHEAD_DATA_PROVENANCE.md`](../../src/mle_critic/docs/train/LOOKAHEAD_DATA_PROVENANCE.md)。

文件名含 `_rebuilt` 的数据是从提交版生成器重建的可运行替代品，不是学生训练时未提交文件的逐行副本。

JSONL 使用 Git LFS。`cards_current.jsonl` 超过 GitHub 普通 blob 的大小上限，不要移除对应的 `.gitattributes` 规则。
