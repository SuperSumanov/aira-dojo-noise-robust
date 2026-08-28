# Selective parent recovery：887 时间切分结果前协议

状态：`OUTCOME_BLIND_DEVELOPMENT_SPLIT_FROZEN_BEFORE_MARGIN_READOUT`。冻结时间
`2026-08-28T15:22:44Z`；当时 LATEST 仍为 `887491a...`，Target-522 candidate 不存在。

## 为什么值得做

已披露开发结果说明 exact run + preceding depth 下，identifier-erased Jaccard 的 unique top 能复原 recorded parent
`9196/9739` 次，但仍有 `543/9739` 个 child 会被错误 unique top 击中。直接把 94.4% top-1 写成“可修复 parent”不够
严谨；真正有 release 价值的问题是：能否只对有把握的 edge 给建议，并把其余 edge 明确拒答。

新 readout 在冻结前完全未看：top-vs-second Jaccard margin 分布、margin 与正确性的关系、按 run chronology 切分后的
train/test profile、选出的阈值及任何 selective precision/coverage。此前只知道总体 top-1、三个错误替换分母和候选集
大小分位数，这些全部写入机器协议，不能伪装成新发现。

## 固定设计

使用 snapshot 887 的 immutable `provisional_runs.jsonl` 字节顺序；前 290 个完整 physical runs 只用于选阈值，后
145 个 runs 只用于一次测试。禁止 edge-level 随机切分、task 重平衡或 test label 参与阈值选择。每条 edge 的 recorded
parent 在排名时被遮蔽；候选仍是同 run、exact preceding depth、fingerprint-valid 的全部节点，至少两个候选。

置信度固定为 top Jaccard 减 second Jaccard 的 exact fraction；top tie 直接拒答。只在 train 的 distinct positive
margins 中选阈值：train precision≥0.99、accepted≥500，并在满足者中最大化 coverage；平手选更小阈值。若无阈值满足，
不允许查看 test 后另选规则。

最强开发分类要求 test accepted≥1,000、precision≥0.98、coverage≥0.50，且 selective error 不超过无阈值 unique-top
error 的一半；另有匿名 task/run breadth 与 anti-dominance 门。必须同时报告 all-alternative micro、每 child 均匀替换
一个 wrong parent、每 child 对抗式选择三个不同分母，任何一个都不能冒充“总体 corruption risk”。

## 主张边界

这是 disclosed 887 内部的 chronological run-disjoint development test，不是 Target-522 前瞻确认。recorded pointer 不是
外部语义或因果真值；primary 只含 parent 仍存在的 edge，不能据此宣称 orphan 已修复。即使通过，产物也只能作为
`suggested_parent + confidence + provenance` 的可选审计层，不能静默覆盖 canonical physical parent。

一般 selective nearest-neighbor、软件 lineage 和 model parentage 均已有工作；这里不申算法首创。可守贡献是把
MLE-agent tree release 做成自审计 artifact：provenance hashes、graph invariants、content concordance 与 calibrated
reject option 分层共存，并给出 run-clean、结果盲、可独立复算的证书。

机器协议：`phase1/tree_content_selective_parent_recovery_887_protocol_v1.json`。本文件写入时尚未执行 margin readout；
GPU/API/model-fit/base-update=`0/0/0/0`，prospective truth/prediction 与 raw senior archives 未读。
