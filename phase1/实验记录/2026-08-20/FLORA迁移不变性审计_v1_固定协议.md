# FLORA-style baseline 迁移不变性审计 v1：固定协议

## 问题与边界

本审计只回答两个结构问题：FLORA-Bench / Agentic Predictor 的 workflow-graph 输入能否**等价**映射到我方真实
MLE sibling 决策单元；若把 physical search lineage 当图，非代码视图在同一 choice set 内是否有能力区分候选。
它不训练模型、不读 first-960 outcome、不计算 accuracy/utility，也不为同一 OOF 继续试图挑出正方法。

官方实现固定到 FLORA-Bench commit `47810805fd41101a1ef6b563c0cd27a0116a0ee8` 和 Agentic Predictor
commit `4d6b2774b22919fe998c4a089f89554017834e2e`。机器协议记录相关源码 SHA256。官方输入的图节点对应
workflow 内 agent/operator calls，要求 node prompt、operator implementation、node implementation code、internal
edge graph、global prompt/code 和 task description；我方 search parent/child 不会被悄悄改名成这些语义。
自然语言 task view 接受显式 `task_description` 或 v11 的 `task.desc`；只有 task slug 的前瞻 blind sidecar 不算。

## 冻结判据

1. **Literal transfer**：七项官方语义必须在作用域内每个 endpoint 上直接存在，缺一即不声称等价迁移。
2. **Lineage-only non-degeneracy**：同 sibling pair 的 task/run/parent 按 estimand 固定；只有 `op/depth/step/n_siblings`
   至少一项在至少一个 pair 上不同，lineage 非代码视图才算非退化。不设效果阈值。
3. 候选代码是否逐字节不同单列报告；代码不同不能把 lineage 图变成 workflow 图。
4. 若 literal 不支持且 prospective lineage-only 为 pair-invariant，则允许给出可复核的 baseline omission rationale；
   AST/token code graph 属于新的适配表示，只能预冻结后用于 outcome-unread extension 或未来 cohort。

## 已知信息（不伪装成预注册未知量）

冻结前已知当前前瞻前缀为 223 runs / 5,643 endpoints，operator-support 审计中 mixed-operator parent=0；Python
AST parse coverage=`0.9725323409533936`，token coverage=`0.9991139464823675`。这些数字写入协议，不能作为本次
新发现或据此调阈值。本次新增的是跨 v11 与前瞻结构的完整 pair-invariance 复核和官方语义字段映射。

## 数据、复核与安全

- v11：b0 train/frozen/extension 的发布 sibling pairs；只做结构统计，不算 outcome metric。
  frozen pair row 若不发布 `run_id`，只允许在两个 endpoint 的 card provenance 给出相同 physical run 时恢复；
  pair 自带 run 时还必须与两端一致，恢复行数单列。
- prospective：冻结 first-960 排序的当前 prefix，只读 snapshot registry、scoreable run identity 与
  `eligible_blind_manifest.jsonl`；禁止打开 label/grade/outcome/scorer prediction。
- producer 与不 import producer 的 verifier 独立重算；双跑需逐字节一致；输出不得含 task/run/card/code 值。
- 0 GPU、0 API、0 base-LLM update。任何 input binding、schema、SHA、Git commit 或安全约束不符即 fail closed。

本协议是短 CPU 审计，不授权训练 graph model，也不恢复历史 TGCA/HCE/多保真方向。
