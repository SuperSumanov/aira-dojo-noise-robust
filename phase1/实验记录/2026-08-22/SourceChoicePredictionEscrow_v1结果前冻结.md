# SourceChoicePredictionEscrow v1：结果前冻结

日期：2026-08-22。状态：`RESULT_BLIND_CONDITIONAL_PREREGISTRATION`。本协议在
SourceChoiceOOF TF-IDF v1 的正式 A/B 生产仍在运行、`summary.json` 尚未读取时冻结；它不是看到效果后的 rescue。

## 唯一激活条件

只接受正式结果 commit `11b7f23d2d91bc412c3a2e0c8cd7d6a23fbb5baf` 经不 import producer 的独立 verifier
返回 `GO_CROSS_TASK` 或 `GO_RUN_ONLY`。若返回 `NO_NARROW_POSITIVE`，本 escrow fail closed，不换模型、不改门、
不生成 frozen/extension 预测。receipt、commit、输入 SHA 或 verdict 任一不符也禁止执行。

## 激活后允许的唯一动作

使用与 OOF 协议逐字段相同的 char-TFIDF pairwise LR，在全部 2,109 个 train groups 上拟合一次，给公开无标签的
778 个 frozen groups 与 113 个 extension groups 输出完整候选排名和 raw decision score。另输出 min-SHA、max-step、
max-code-length 三个固定 control。producer×2 必须逐字节一致，并由不读取标签的结构 verifier×2 复核；GPU=0、
API=0、底座更新=0。

输入精确绑定 v2 train/frozen/extension/cluster SHA；train/frozen physical run 与 parent 均零交集。frozen 与
extension 对象不得出现 winner 字段。syscall 审计禁止访问 source-choice vault、任何 frozen/extension label、历史
outcome 或 prospective score 路径。

## 明确不做

本层只封存预测，不打开 label vault，不计算 frozen/extension accuracy，不选择 checkpoint/阈值/任务，也不声称新任务
迁移、最终 Kaggle quality、搜索 speedup 或因果效用。揭盲必须另立结果盲 evaluator 协议并由用户单独裁决；因此即使
OOF 为 GO，本轮最多得到“预测已在标签不可见时冻结”的完整性资产。

机器可读合同：`phase1/source_choice_prediction_escrow_protocol_v1.json`。
