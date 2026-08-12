# 2026-08-13：Prompt 0.5 的真实树形资格审计（v9）

## 问题与边界

本次只回答一个前置问题：v9 卡片语料是否包含**同一物理 run 内、结构闭合、深度足够**的
子树，使后续 TD/MC backup 比较有实际对象。它**不**实现 TD、不比较任何策略、更不宣称
TD 改善搜索。

这一步专门避免两类旧错误：

1. 把缺失父节点的 card fragment 误当成一棵真树；
2. 把声明中缺失的 child 静默当成 leaf，从而捏造完整 descendant target。

## 冻结输入与复现

- checkout: `226985947b80b371c19650a9dd05c8ff0bcab1ad`
- cards: `cards_current_v9.jsonl`（Git LFS 对象 SHA-256
  `daeb29fc07ad670b5ca7a10cd2d84f1fa9a27dfa9d22510533417f1a8ad9407f`）
- run map: `card_run_map.json`，SHA-256
  `e792b5cd4e9e84105e2a6c2e58d6ac1bbf71bc0563a07ccc2e18b8c63af8f409`
- 随机性：无；脚本确定性。独立重跑两次，`summary.json` 与 `run_topology.csv` 的 SHA
  均逐字一致。

```bash
python phase1/audit_tree_topology.py \
  --cards /immutable/cards_current_v9.jsonl \
  --run-map phase1/card_run_map.json \
  --out-dir phase1/td_topology_v9
```

产物：`phase1/td_topology_v9/{summary.json,run_topology.csv,task_topology.csv}`。

## 资格规则

一条父子边仅在以下条件下可用：父 card 存在、与 child 属于同一 reconstructed physical run、
且任务相同。一个向下子树仅在每个节点的 `children_ids` 与观测到的同-run 子边完全一致、
没有引用缺失 child、并且所有节点都有有限外部分数时才称为闭合。组件的无父节点只叫
**observed fragment root**，绝不叫 original search root。

## 结果

| 指标 | 数值 |
| --- | ---: |
| cards / tasks / reconstructed runs | 14,323 / 23 / 586 |
| 缺失父节点的 cards | 5,591 |
| 跨 run / 跨 task 父子边 | 0 / 0 |
| 声明但缺失的 child 引用 | 3,696 |
| 声明与观测 child 集不一致的 nodes | 2,429 |
| 闭合且有外部分数的 nodes | 10,851 |
| 闭合分支点（至少两个 children） | 1,354 |
| 深度至少为 2 的闭合分支点 | **426** |
| 最大已验证向下深度 | **17** |
| cycle nodes | 0 |

**结构判决：CONTINUE_TO_ESTIMATOR_SPEC。** v9 的确有足够的深闭合分支，不能再用
“树太浅”直接否定 TD；但碎片比例也足够高，任何把全部 card 当完整树的分析均无效。

## 不能越过的推论边界

卡片没有历史 MCTS 的 visit count、累计 `node_value`、每次真实 selection path，故不能仅凭
静态 cards 做一个伪 counterfactual 后宣称“TD 胜过 MCTS”。后续 Prompt 0.5 必须：

1. 先从 `src/dojo/solvers/mcts/mcts.py` 的真实 MC 语义（当前为把新 child 的外部分数加到
   已选 path）定义 TD(λ)；
2. 为新的 baseline 运行记录 path、visit count、每次 backprop 的 reward、节点父子关系与时间戳；
3. 再在同一批完整树上进行固定噪声注入、MC/TD 的配对比较，报告每 task/run/seed 的 CSV。

若新的有日志 baseline 的树形或配对结果不支持 TD 降方差，Line 1 立即止损；不会用本表来
粉饰为 TD 的正面结果。

## 对主线的含义

这不会延迟 Line 2。已有 dose-response 证据的可检验正面主张仍是：**低保真若保持外部评分
通道一致（部分 `submission.csv` 的 pristine grade），在可行动子集上显著优于随机；同深度的
自报 stdout 信号则不可靠。** 现有 HCE 代码的 `50/25/25` 及标签子采样 proxy 不符合当前
`80/10/10 + full_locked + 时间截断` 契约，后续将重建而不是沿用其旧结果。

## 运行环境备注

审计为 CPU-only、无 API 调用。集群 SSH 网关在一次只读探测时主动断连；因此本次未声称任何
队列状态，也未提交 GPU 作业。Git worktree 通过 `GIT_LFS_SKIP_SMUDGE=1` 建立；仓库中另一
历史 LFS 对象 `budget_pairs_v3_runsplit.jsonl` 在 GitHub 返回 404，与本次已校验的 v9 输入无关。
