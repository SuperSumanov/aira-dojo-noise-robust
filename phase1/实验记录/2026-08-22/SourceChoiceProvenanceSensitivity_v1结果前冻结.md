# SourceChoice provenance sensitivity v1：结果前冻结

日期：2026-08-22。状态：`RESULT_BLIND_CONDITIONAL_PREREGISTRATION`。本协议在 OOF 正式 A/B 仍运行、
`summary.json` 尚未读取时冻结；不训练新模型，也不接触 frozen/extension。

## 为什么必须做

S2 v2 已删除显式 `provenance/source_journal_sha256`，并修复 operator 大小写代理，但 train 的 2,109 groups 中仍有
496 个同时含 card 与 journal-recovered candidate。697 个 recovered candidates 均不是 winner。完整 code bytes 是合法的
decision-time 输入，却仍可能编码两类不同机制：可部署的静态失败/可执行性线索，或只属于恢复流水线的存储格式捷径。
仅凭全池 GO 不能区分二者。

## 冻结分析与门

只在独立 OOF verifier 返回 `GO_CROSS_TASK` 或 `GO_RUN_ONLY` 时激活；NO verdict 不做 rescue。复用已经写出的
task-LOTO `tfidf_pairwise_lr` 逐组预测，不重新拟合、不改排名。结果盲结构预检确认 all-card 1,613 groups 覆盖全部
23 tasks，arity 2/3/5 分别为 1,014/565/34；mixed 496 groups 覆盖 13 tasks。primary 固定为 all-card groups，逐组基线仍是
其真实 arity 下的 `1/source_size`；先组内 delta，再 task 内平均，最后 task-macro。20,000 次 task bootstrap
seed=20260824，并做忽略 exact zero 的单侧 exact task sign test。

结构支持因此已满足 all-card groups≥1,000、tasks≥15。效果门与原 OOF 相同：task-macro delta≥0.03、task CI 下界>0、
sign p<0.05。通过记 `ROBUST_BEYOND_RECOVERY_MIX`；否则记 `RECOVERY_MIX_SENSITIVE`，必须降格广义 branch
intelligence 主张。mixed 496 groups 仅作次级归因：报告模型相对 exact uniform、card-only uniform、模型选择 provenance
比例，以及 task/arity strata。

即使通过，也只证明信号不局限于 recovery 混合组；不等于语义理解、因果效用、最终质量、搜索 speedup 或新任务部署。
机器可读合同：`phase1/source_choice_provenance_sensitivity_protocol_v1.json`。
