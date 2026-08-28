# Decision Corpus Evidence Index v9（lineage provenance repair）

权威 source commit：`f10881237447501a1b3b51213a267865bd854d17`。协议 SHA-256：
`a5d49990f3af37ce8968495fd13bf1b1c3f5e48875b117a86a878b75ed8d958a`。正式状态仍为
**`PROVISIONAL_TEMPORAL_SPLIT_CERTIFIED_EVIDENCE_STACK_AWAITING_FIRST960`**。

## 正式结果

v9 修复了 v8 的一处证据 provenance 缺口：旧 `decision_corpus` entry 所指 v1 artifact 没有读取
`lineage.parent_id`，不足以独立证明 declared-parent direct-child relation。v9 只替换这 1 项；其余 15 项与 v8
逐对象完全相等，状态没有升级。

新 entry 绑定 2026-08-29 lineage audit v2 的 producer、独立 verifier 与 source bindings，共 3 artifacts / 51
项 JSON assertions。它机器保留如下完整结论：

- 九个 canonical v11 sets 共 8,107 rows，全部为 recorded-parent lineage-direct siblings；
- parent-present strict core=7,579，lineage-verifiable orphan-parent tier=528；same-run non-sibling/cross-run=0/0；
- 15/15 hard integrity gates 通过；
- 36 个 support gates 通过 35 个，唯一失败仍是
  `frozen:b2.maximum_single_run_pair_share`，不得隐藏或升级为全门通过；
- v8 的 first-960 provisional 状态、其它 15 项 evidence 与全部 effect/utility 禁止项均保留。

builder A/B 和不 import builder 的 verifier A/B 各自逐字节一致；index/verifier SHA-256=
`b2d88479abb03cf72b27f9f958badfb3aeb8bc1e1e3cac2c50a3aace43511ff6` /
`2319c028b3cb28bef01db9b343a307a9327f3414c3e15e5595bd500af6985e6d`。focused/full=
`37/1496 passed`，full 有 47 个既有 warnings；单线程 CPU 约束固定。forbidden opens、network、credential
filename/content 均为 0，且内容扫描器返回码明确为“无命中”而非“工具不存在”。

## 失败史

本包不只保留成功轮：

1. r1 在测试前因远端名误用 `myfork` 而 fetch rc=128，无 index；
2. r2 的 full suite 在登录节点触发约 27 核 BLAS，被资源守护主动中断，无 index；
3. r3 科学测试完成，但集群没有 `rg`，旧 `|| true` 把 scanner rc=127 误写成空命中，故整轮正式作废；
4. r4 固定 cluster remote、单线程 BLAS 和 scanner return-code gate 后成为唯一权威 formal。

权威 formal manifest SHA-256=
`2cc3b1b9fc7a12cb884913fddfa3448dc6ebc7d22be86bc4c69374f86bae854a`；独立 postflight manifest=
`fb3cb40cc0a80f42ad113cfb0fbf17d68714d0136113113e85387baffd192b58`。

## Claim boundary

这是已知 lineage 结果后的 reporting/provenance 修复，不是新的结果前实验，也不构成一般 evidence-index、benchmark
card 或 lineage 方法首创。recorded parent 不是语义/因果真值；b2 的集中度限制必须同报；本包不证明 predictor
accuracy/scaling/search utility 或 prospective generalization。没有 row-level release，未读 prospective values 或 raw
senior archives；GPU/API/model-fit/base-update=`0/0/0/0`。
