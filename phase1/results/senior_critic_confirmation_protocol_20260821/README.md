# Senior critic confirmation protocol：交付与独立验证

本目录绑定学长 `dojo-reproduce@baf6bdd` 的非侵入式确认协议补丁。它不重写 0820 的探索性结果，也没有运行
GPU；目的只是让下一轮 exact-stratum 数据具备真正的 train/dev/test 隔离和一次性评测链。

## 可复核对象

- upstream base：`baf6bddefe62b769b2fab699ff5805dd627dc69f`
- detached implementation：`9f25145e4b34b5e9e2914e949243d4ca30bf356b`
- patch：`phase1/upstream_patches/0001-Harden-critic-confirmation-protocol.patch`
- patch SHA-256：`2fd5ca7b38e4277b68c2eb90b42c0f0ce85b8ab0ef687802e68ceeb8f0fc1fe2`
- 远端独立 apply 后 commit：`23f51126ebd4b0b90f610f28905d1c7d96b03a50`

## 验证结果

远端固定 detached worktree 使用 Python 3.11.15、PyTorch 2.11.0+cu128、Transformers 4.57.1：

- 补丁从精确 base 成功 apply；
- Python compile 与两个 shell launcher 语法通过；
- `save_strategy=best`、`load_best_model_at_end=true`、`metric_for_best_model=eval_pair_accuracy`、
  `greater_is_better=true` 的 TrainingArguments 构造通过；
- 聚焦测试 33/33 通过，用时 3.80 秒；
- `git diff --check` 通过，远端 audit worktree 额外修改数为 0。

本地没有 PyTorch，因此只运行不依赖 torch 的协议/producer/verifier 测试，结果 24/24；涉及训练参数和 one-shot
模块的测试一律以后述远端结果为准。完整机器可读值在 `verification_receipt.json`。

## 科学边界

补丁提供的是 future confirmation 的必要基础设施，不是 scaling 结果。历史 0820 checkpoint 已在 outer test 上
多次 eval，且该 test 与 b0/b1/b2 是同一 2,087-row multiset；训练 pair 还含跨配置混配。因此不能因代码修好而
追认，也不得再运行旧 checkpoint 的 frozen scoring。新的确认必须使用修复后产生的数据、train-run dev 选出的
新 checkpoint、全新未触碰 frozen test 和 one-shot ledger；重训矩阵仍需单独预算批准。
