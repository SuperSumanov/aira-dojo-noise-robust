# Balanced continuation E1-Q fresh-anchor pilot 裁决

日期：2026-08-14。source commit：`0d1ca6fd948d24f23d4abecc3298d8ff6ef53974`。正式状态：
`VERIFIED_COMPLETE_REAL_E1_COLLECTION`；第二个不 import producer 的 compact-archive verifier 状态：
`VERIFIED_INDEPENDENT_E1_ARCHIVE_ANALYSIS`。

## 1. 完整性与成本

两阶段 8/8 rollout 均完成，16/16 candidate processes、8/8 Qwen operator calls，retry/analyze/D_test 读取
均为 0。stage 1/2 只看 capability、worker、独立 receipt 与 safety rc；直到 8 个 rollout 完整覆盖后才打开
16 个 sealed D_val receipts。八个 workspace/token 均唯一。candidate 墙钟总和
`4918.986782835971` 秒，即 `1.3663852174544364 GPU·h`。

collection summary SHA-256 为
`f98ee3d663fab2d1085ec9cefcf14c36d17e15b966ba45eb90ef538f49f92d11`。独立 archive verifier 重算
8 rollout、4 sibling、2 task 与全部 summary aggregate；安全扫描 filename/content 均为 0。

## 2. 冻结裁决

两个任务在两个 replicate block 中都选出同一个 sibling，task replicate agreement=2/2；四个 sibling 的
balanced `V_1` label 非退化。因此按预注册属于 **`E1Q_LABEL_FEASIBILITY_OBSERVED`**，不是
`NONINFORMATIVE`。

但 8 个 rollout 只有 2 个 positive gain，0 个超过 `0.01` practical delta。spaceship 的 task mean gain=
`-0.001920614596670922`；tabular=`0.000059111405560141606`。因此没有 practical improvement 正结果，
更不能声称 continuation search 已改善。

compact collection 漏了预注册要求的 execution status 明细。该缺口没有通过改写 collection 修复，而是另做
post-hoc reporting repair：只读已经过独立 worker verifier 的 16 个 `execution.json`，在 JSON parse 前拒绝
credential pattern，不输出 code/terminal/raw response。warm 为 6 ok + 2 execution_error；continuation 为
6 ok + 1 execution_error + 1 timeout；两阶段均只有 6/8 artifact 被 D_search/D_val 成功评分。

这给 hurdle 分解一个**设计依据**：validity failure 与 conditional gain 是不同机制；但样本只有两任务两 anchor，
且条件 gain 很小，所以绝不是 hurdle critic 的方法正结果。

## 3. 后续门

- `primary_gate_claim_allowed=false`、`e2_e3_unlocked=false` 保持不变；
- 不沿用旧 43.76 GPU·h 表机械启动 E2；先按 6/8 validity、观察方差、1.366 GPU·h 实际成本与更广 task/anchor
  支持重新做 power/design；
- 若继续，E2 必须预先区分 validity head 与 conditional-value head，并把同预算 downstream utility 设为最终门；
- 最低成本的正向扩展是与学长讨论把少量 equal-K/randomized sibling micro-intervention 嵌入未来数据生产，在
  不增加总执行预算的前提下积累可识别标签；这会改变生产 policy，未经双方确认不得直接上线。

E1-Q 是 gated 支线的 feasibility 正结果；论文稳定主线仍是 physical-run-clean、choice-set-faithful benchmark 与
first-960 prospective confirmation。
