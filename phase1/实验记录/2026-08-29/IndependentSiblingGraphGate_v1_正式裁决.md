# Independent Sibling Graph Gate v1：正式裁决

日期：2026-08-29

正式分类：**`HISTORICAL_SENIOR0819_INDEPENDENT_SIBLING_GRAPH_FEASIBLE`**

## 1. 本轮回答的问题

0IN 在 v11 train:b0 上发现低 endpoint budget 的 label-yield 正信号，但 b1/b2 与 b0 的 physical runs 100% 嵌套，不能
充当独立确认。本轮只回答一个更窄的结果前问题：senior-0819 已认证 train-only direct-sibling core 在严格剔除 v11 的
endpoint、declared parent 与 physical run 后，是否仍存在足够大且分布不过度集中的独立历史图。

318 条 senior 历史 test core 全部禁用；本轮没有计算 acquisition curve、accuracy 或 search utility。

## 2. 权威结果

冻结候选 train core 为 952 pairs / 1,782 endpoints / 847 parents / 327 physical runs / 37 tasks。候选与 v11 的描述性
crosswalk 有 413 exact pairs、746 endpoints、342 parents、0 physical runs 重合；固定 EP mask 因而剔除 413 rows，保留
539 rows。

strict residual 为：

| 指标 | 结果 | 冻结门 | 判定 |
|---|---:|---:|:---:|
| pairs | 539 | ≥500 | pass |
| pair retention | 77/136 | ≥1/2 | pass |
| endpoints | 1,036 | ≥500 | pass |
| parents | 505 | ≥250 | pass |
| physical runs | 190 | ≥75 | pass |
| tasks | 36 | ≥15 | pass |
| max task pair share | 58/539 | ≤1/3 | pass |
| max run pair share | 2/49 | ≤1/10 | pass |

residual 对 v11 的 exact pair/endpoint/parent/run overlap 为 `0/0/0/0`；duplicate unordered rows 与 conflicting reverse
orientation 都为 0。八个 integrity gates 和八个 support gates 全部通过。

## 3. 独立复验和操作链

权威 r2 从公开 commit `7ad83d2afa16c30df1464bdbe5fbb17ac16ac7c4` 的 fresh detached worktree 运行：producer 在
`PYTHONHASHSEED=0/1` 下逐字节一致，non-importing verifier 另行重建 senior core、v11 parser、strict residual、profile、
fingerprints 和分类，并在两次运行中逐字节一致；全部 aggregate 字段 exact。

- protocol SHA-256：`b033ddbe99c94a0e9e924233181879121e8a3f2021d86278210f58d1fa720c4c`
- producer SHA-256：`ea66df81b640c8623936c40bd2742245361c684f6d270ef53b59f4432e65fa18`
- verifier SHA-256：`6f7c3a3ca782e4d18d9d67ee6954f0a6bcbbafedac0d1a134a1b1fdfa6e0c8a1`
- focused/full：`15 passed` / `1573 passed, 47 warnings`
- forbidden opens / network / credential filename / credential blob：`0/0/0/0`
- GPU/API/model-fit/base-update：`0/0/0/0`

r1 的 producer/verifier 与 r2 SHA 完全相同，但旧 scanner 将普通 `task-...` 文本中的 `sk-` 误判为 credential，最终
`FAILED_RC=90` 且无 `COMPLETE`。修复只改变 runner 的 token 左边界并加 scanner 正负 self-test；protocol、输入、算法、
门、输出与分类均未改变。r1 失败回执保留，r2 才是唯一权威 formal。

## 4. 正面资产与边界

这是 b1/b2 碰撞后首个真正做到 physical-run、endpoint、parent、exact-pair 四层零重叠的独立历史 sibling 图，足以支撑
下一份**结果前冻结**的 acquisition confirmation。它提升的是数据与审计资产，不是已经证明方法增益。

同时图很稀疏：539 edges、1,036 vertices、505 components、最大 endpoint degree=4，只有少数结构复用机会。因此合理的
待确认假设应明确限定在 label-scarce regime；不得把 b0 的高预算失败删掉，也不得声称全预算普遍优势。下一步只能在读取
本 residual curve 前冻结相对预算、强 `uniform_edge` 基线、多 seed、breadth/anti-dominance 和 no-rescue 门。

正式包：`phase1/results/historical_independent_sibling_graph_gate_20260829_7ad83d2/`。
