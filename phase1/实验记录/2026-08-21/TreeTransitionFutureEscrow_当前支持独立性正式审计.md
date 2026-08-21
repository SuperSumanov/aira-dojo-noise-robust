# Tree Transition Future Escrow：当前支持独立性正式审计

日期：2026-08-21。状态：`CURRENT_SUPPORT_NOT_SOURCE_INDEPENDENT`。本轮只回答 activation 前的结构与来源资格，
不读取 prospective outcome，不计算 accuracy、margin、CI 或任何 effect metric。

## 固定输入与实现

- source commit：`4b6b997bdd08e48494ab68497a6f48f28e5a5032`；
- snapshot：`83ab1d681ed863d2374a6648df4801e6dbd6fb80d89f4f20cec8d46de1d5c047`；
- grouped Cards SHA：`5fd24c8e545a67e1048f8a67b23bcb64605b9ad584a4fbaa44aa1b1f1b6e1afb`；
- train SHA：`0ec49d76a896accf8e85a2556ca7ed12b9379b1867247d99c6be5e4c83bea98e`；
- dev SHA：`3b3fb53f84277e935c66d3b3d1646d7a7d33624fb916e3f9bcc15f689904cfa4`。

训练来源的正确口径不是 31,742-card 容器全体，而是 train+dev 的 better/worse/parent 闭包。闭包含 5,612 cards，
来自 5,240 pair rows。producer 和独立 verifier 分别从 frozen manifests、run accumulator、Cards 与 pair rows
重建 first-960 当前前缀、canonical `(task,run,parent)` sibling pairs、父代码覆盖和 ID/run/code-SHA overlap。

## 正式结果

当前支持有 249 runs、6,471 cards、26 tasks、1,665 sibling pairs 和 1,623 parent groups。1,412 pairs 的父节点
代码存在于同一 blind snapshot，coverage=`0.848048048048048`；这些 pairs 覆盖 24 tasks，最大 task share=
`0.18838526912181303`。在逐 pair 排除任一 child/parent ID、run ID 或三张 code SHA 的训练重叠后，仍有 1,134
个 source-novel、parent-covered pairs。

与此同时，整个 current support 与训练闭包有 579 card-ID overlap 和 579 unique code-SHA overlap，run overlap=0。
因此 current support 不能整体称为 source-independent validation。1,134 只证明未来筛选有充足的结构机会；由于所有
当前 runs 均早于 future activation，它们也不能进入 strict effect cohort。

## 独立性与封存

- producer×2 逐字节一致；verifier×2 逐字节一致；独立 summary 与 producer SHA 都为
  `820c4e1df9dc8d711dd2114e3cfac9c8eaac27d5d059be0632e784be9e54f57a`；
- 10 focused tests、574 phase tests 通过；
- producer/verifier stderr 与两个 reproducibility diff 均为空；
- traced prospective forbidden-path hits=0，artifact credential-shape hits=0；
- manifest 全过、产物 writable files=0。

原 runner 在四次科学计算均结束后，因 `grep` 零匹配在 `set -eo pipefail` 下返回非零而未写 conclusion。该问题在
读取结果前定位；后续 finalizer 只记录零命中并封存已有 byte-identical outputs，没有重跑或修改科学计算。erratum
作为正式产物的一部分保留。

## 裁决

1. current support 永久是 support/smoke，不得混入 future effect validation；
2. 旧 2,330 ID / 2,321 code-SHA 的全容器比较被本次 579/579 模型闭包口径正式取代；
3. 路线未被杀死：coverage、任务分布和 1,134 source-novel pairs 表明 future protocol 结构可行；
4. 下一步只能在 activation 后对新 generation-start runs 锁定三臂预测，达到预注册 1,500-pair 等支持门后再揭盲；
5. 当前 accuracy/effect claim 数为 0，不得把本报告描述成 transition 已获得前瞻正结果。

远端完整只读产物：`/research/d7/spc/yzyang4/transition-future-support-audit/4b6b997-v1`；Git 紧凑证据位于
`phase1/results/transition_future_support_audit_20260821_4b6b997/`。
