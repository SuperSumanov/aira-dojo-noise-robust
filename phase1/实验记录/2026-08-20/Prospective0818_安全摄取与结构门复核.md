# Prospective 0818 安全摄取与结构门复核（2026-08-20）

## 裁决

0818 新增 8 个归档。生产流程在固定 6 小时稳定窗后逐包处理：7 包形成不可变 transaction；`multi-modal-gesture-recognition-8seeds.tar.gz` 在 intake 处 fail-closed。credential-first 独立 auditor 对后者双跑逐字节一致，4/4 checkpoint journals 的 task identity cardinality 均为 0，因此按精确 path/size/mtime/SHA 整包结构拒收，未按文件名补 task。

最终快照为 `88cb79191b23738c1813a131abe2d5dbba48c31cb8c8095d047902afa29170c8`。相对 0817 完成快照，增加 7 transactions、26 eligible runs、2 tasks、1,219 endpoints 和 257 structural sibling pairs。当前累计：

- 42 transactions，249 physical runs，其中 223 eligible；
- 25 tasks、5,643 eligible endpoints；
- 1,473 structural sibling pairs，222 finite-decision runs；
- 最大 pair-task share=`0.1887304820095044`；
- 5,631/5,643 unique exact-code SHA，12 个重复端点。

## 独立复核

新增 verifier commit=`ea438c50ebe9ed0bfb32a8349e605c93b2fc7f6a`，不 import 生产 accumulator；它只读登记后的 `eligible_blind_manifest.jsonl`、`eligible_structural_pairs.jsonl`、identity-only runs 与 summary receipt，自行按 `(task, run, parent)` 重建所有 sibling 组合。真实快照双跑逐字节一致，收据 SHA=`af494085faded657d3486f75c6b7ce7b39ae25d00e69a7d5cd405a2a769894b7`。transactions、runs、tasks、endpoints、pairs、code uniqueness、duplicate count 和 per-task pair counts 八项均与生产 accumulator 一致；两份 strace 对 label vault、grade、outcome、frozen、blind score 和 score index 的命中均为 0。依赖齐全的远端 clean worktree 全套测试为 `435 passed in 39.77s`。

## 结构门

冻结门要求：至少 1,500 pairs、150 finite-decision runs、15 tasks，且最大 pair-task share 不超过 0.25。当前后三项通过，pair 数单项失败：`1473 < 1500`，程序打印剩余 27。故状态保持 `STRUCTURAL_GATE_NOT_YET_MET` 与 `PROSPECTIVE_COHORT_COLLECTING`；`vault_open_allowed=false`。

这不是方法效果正结果，也不能回填任何旧实验。当前正面进展是 outcome 前的时间外推样本支持已接近冻结门，且新增批次带来 +257 真实 sibling pairs；下一步只继续 append-only 安全摄取。达到门后先冻结精确 cohort 与版本收据，再按既有一次性协议开 vault，不得提前窥视。
