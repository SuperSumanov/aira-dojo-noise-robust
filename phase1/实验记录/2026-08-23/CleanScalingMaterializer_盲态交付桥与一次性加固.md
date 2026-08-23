# Clean scaling materializer：盲态交付桥与一次性加固

日期：2026-08-23。状态：`MATERIALIZER_READY_SYNTHETIC_ONLY_REAL_TRUTH_FORBIDDEN`。

## 问题

0004 已让 evaluator 保存 endpoint scores，但它的 output/ledger 不能直接交给 frozen scaling analyzer：缺 canonical
pair/component IDs、oriented utility、truth/source hash 链、checkpoint artifact 对照和 bundle-relative ledgers。若用临时
脚本后验拼接，最危险的是换 Cards、换 checkpoint、换 ledger 路径重试或把 disconnected sibling fragments 当成一个
component。

## 实现

新增 `phase1/critic_scaling_confirmation_materializer.py`：

- truth：pairs/Cards exact-hash + credential-first，raw sibling/run/lineage/direction/budget/duplicate 全部 fail closed；
- component：同 parent graph 取 maximal connected components，零 drop，canonical digest；
- model：绑定 pre-test lock、one-shot output/ledger、checkpoint manifest 及 prelocked path identities，验证 endpoint
  scores 和 pair pool 后才输出标准 predictions；
- bundle：只接受 root 内普通文件，严格 8-run matrix 和逐 artifact/ledger 哈希。

15 项纯合成 adversarial tests 覆盖确定性、lower-is-better、disconnected components、split/semantic/run/duplicate/
direction/budget/credential 破坏、endpoint inconsistency、hash/orientation substitution、ledger-path retry、checkpoint
substitution、path traversal 与 matrix omission。冻结 analyzer 接受合成最终 bundle。另 10 项既有 scaling/endpoint
联合测试通过。本机 full collection 因缺 `scipy/sklearn`，该结果不算 full-suite pass，等待集群 exact commit 复验。

访问证明：real future truth=false，GPU=0，API=0，model fit=0。当前没有产生任何 scaling 效果数字。
