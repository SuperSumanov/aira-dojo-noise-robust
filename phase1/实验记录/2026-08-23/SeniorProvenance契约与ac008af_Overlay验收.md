# Senior provenance 契约与 `ac008af` clean-confirmation overlay 验收

日期：2026-08-23。正式状态：`OVERLAY_COMPATIBLE_PROVENANCE_CONTRACT_READY_EFFECT_BLOCKED`。本轮 GPU/API/
model fit/outcome/frozen reads 均为 0。

## 1. `ac008af` overlay 的可迁移性

在集群 fresh no-smudge worktree、精确 base
`ac008af8b907d319b694f26b0ba9cf4053b3bf69` 上按顺序应用三份补丁：

- confirmation protocol：`2fd5ca7b38e4277b68c2eb90b42c0f0ce85b8ab0ef687802e68ceeb8f0fc1fe2`；
- fixed-step G0：`89d7af494e436c4d5a7ed5c4a06e43c4d012cb26c3efd3c1e9f52bf00b3bd641`；
- wall-clock receipts：`a4146bdc6ef3123e3b88a3b909352dd40db3cff992503919d4207c1756313f67`。

三份均通过 `git apply --check`；Python compile、launcher shell syntax、`git diff --check` 通过，8 个聚焦测试文件
打印 `35 passed in 47.38s`。因此不需要为学长新 commit 重写 clean confirmation harness。这个正面结果只说明
工程 overlay 兼容，不证明模型效果，也不允许直接运行当前 mixed launcher。

## 2. producer provenance contract

新增 `phase1/contracts/SENIOR_SOURCE_PROVENANCE_MANIFEST_V1.md` 和完全独立于 corpus/pair producer 的
`phase1/validate_senior_source_provenance_manifest.py`。每个 frozen run 必须由一行精确绑定：

`run_id, task, source_date, batch_id, archive_path, archive_sha256, producer_commit`。

校验器 fail closed 地要求 exact schema、按 run_id 排序、676-run（或输入冻结版本的全部 runs）零缺失/零额外、task/date
一致、archive 相对路径和 SHA 正确、无 symlink，并在 tar header 中找到唯一的
`<batch>/<source-run>/checkpoint/journal.jsonl`。link/device/FIFO、重复 journal、零 journal、冲突 hash 均拒绝；
不调用 `extract`/`extractfile`，不暴露或解析 member payload。

本地新旧相关测试合计打印 `23 passed in 0.29s`；精确同一批测试在远端 Python 3.11 环境打印
`23 passed in 0.12s`。远端第一次建立临时 worktree 时因主 clone 尚未 fetch commit 而在测试前失败；runner 增加
精确 `fetch` 与 `FETCH_HEAD==5f3f7b1...` 门后复跑通过。该失败保留为基础设施记录，不算作测试失败或成功。
加入 mixed dataset audit 的三项既有测试后，扩展相关套件本地打印 `26 passed in 0.30s`，远端打印
`26 passed in 0.15s`。

## 3. 尚未解除的阻塞

当前没有真实 producer provenance manifest，所以 formal status 仍不是 `PROVENANCE_VERIFIED`。学长还必须上传正确
的 0811/0812 leaf archives（现存对象分别与同日 tabular archive 逐字节相同），并为 0730 symlink archive 与 0809
零-journal archive 给出 canonical replacement。之后用本校验器对 frozen expected-run manifest 全量运行；不能只对
636 个可 join runs 做事后 salvage。

只有正式 receipt 为 `PROVENANCE_VERIFIED`，再通过新 mixed builder receipt、experiment-closed train/dev/全新
frozen、dev/final-step-only 选择、Cards fresh-clone LFS 和单旋钮门，才允许提交 dev-only G0 预算校准。当前远端
GPU queue 为空是预期状态。
