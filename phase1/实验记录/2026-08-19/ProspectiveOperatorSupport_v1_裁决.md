# Prospective Operator Support v1：裁决

## 复现与边界

- 结果前 commit：`1740d513b7ea2fc497c3906ca80771b52bdef91c`；
- transactions：35 行，SHA256=`6db342bc711ef4b0445171db796a3efb52b7989524120a17795a1480a7fd1408`；
- 远端完整测试：`387 passed in 31.57s`；
- producer 双跑逐字节一致；summary SHA256=
  `ce611700a9afa5a9f543f57992ef3b1033bbfa20198d8e78dc4d2759561ca0d5`；
- 独立 verifier 两次均通过；verification SHA256=
  `d91405269b20df4e9abcd4dd7d391e9218f530472d05aed1ba78974c2301a092`；
- outcome/label/numeric grade/raw-code output/GPU/API：0/0/0/0/0/0。

## 冻结门结果

197 eligible runs、23 tasks、4,424 endpoints 的边际 operator 数量达到门槛：Debug=2,034、Improve=1,998、
Draft=392；Debug/Improve 分别覆盖 23/22 tasks。可是 3,229 个 nonroot parents 中：

- mixed-operator parents=`0`（门：≥100）；
- mixed-operator tasks=`0`（门：≥10）；
- exact-two mixed-operator parents=`0`（门：≥60）；
- dominant mixed-task share 因分母为 0 不可定义（门失败）。

## 裁决

状态固定为 **`INSUFFICIENT_OPERATOR_RANDOMIZATION_SUPPORT`**。不降低门、不按任务筛选、不把全局 operator
边际覆盖误当作 sibling 内支持。现有语料的 operator 变化只发生在 parent 之间，无法支持 parent-matched operator
effect 或随机化自然实验。

这不证明主动 child-level operator 随机化永远不可行；它证明该方案必须被视为一个新的生产干预，而不是对当前
语料的免费重分析。任何此类干预仍需真实 append-only scheduler event stream、displaced-slot budget ledger、
单独预注册与预算批准。本轮不激活 production，也不产生因果或 search-utility 主张。

