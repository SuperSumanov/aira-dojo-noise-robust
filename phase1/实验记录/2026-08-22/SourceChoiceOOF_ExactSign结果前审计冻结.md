# SourceChoice OOF exact-sign：结果前实现审计冻结

日期：2026-08-22。状态：`RESULT_BLIND_IMPLEMENTATION_AUDIT`。本文形成时，固定 TF-IDF 正式 OOF 的
producer A 仍在计算，`result_a/summary.json` 尚不存在，任何 OOF 指标、verdict 及 frozen/extension label vault
均未读取。

## 发现与裁决

OOF 协议把 task sign test 定义为 `one_sided_exact_positive_ignoring_exact_zero`，但 producer 与第一版独立
verifier 都先用 binary float 计算 `hit - 1/source_size` 及 task mean，再用 `value == 0` 判断 exact zero。对 arity=3/5
的任务，数学上恰为零的 task delta 可能因浮点舍入被错记为极小正数或负数。producer A/B 与原 verifier 一致只能证明
代码复现，不能证明这里的“exact”语义。

结果前固定新增 `audit_source_choice_oof_exact_sign.py`：不拟合模型、不改变任何 prediction/ranking，直接对正式
`predictions.csv` 中两个 split 的 `tfidf_pairwise_lr` 行用 `fractions.Fraction` 重算逐 task delta 和单侧 sign p，随后只
替换 cross-task gate 的 sign 项，保持原 task bootstrap、run gate 和阈值不变，报告 `reported_verdict`、
`exact_sign_verdict` 与是否改变。若 exact audit 把 GO 改为 NO，以 exact 结果为准；不得把它用作 rescue。正式 runner
要求先存在原 independent-verifier COMPLETE，并绑定其 summary SHA，双跑逐字节比较、审计文件访问且拒绝
frozen/extension/vault 路径。

同时实现已冻结的 recovery-provenance sensitivity：只在独立 OOF 为 GO 时激活，复用 task-LOTO TF-IDF ranking；
all-card 主分析使用有理数判断数学 exact zero。实际 train 视图的结果盲结构预检逐项复现协议中的 2,109 groups、
all-card 1,613 groups/23 tasks、mixed 496 groups/13 tasks、5,042 card 与 697 recovered candidates，全部 winner 为 card。
该预检不含 predictor outcome。

合成测试固定覆盖：all-card 正信号、NO verdict 禁止激活、数学 exact zero，以及报告/精确 verdict 可相同但 sign counts
不同的情况。该审计只修正统计语义，不允许更换模型、阈值、split、subset 或 frozen cohort。
