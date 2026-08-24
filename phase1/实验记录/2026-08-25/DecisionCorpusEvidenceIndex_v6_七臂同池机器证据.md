# Decision-Corpus evidence index v6：七臂同池机器证据

## 1. 问题与冻结边界

本轮只回答：f109 的 WL/graph 四臂与 transition 三臂是否能作为 Decision Corpus 的一项独立、机器可验证的
结构证据发布。它不回答任何 predictor accuracy、方法优越性、search utility 或成本问题，也不读取 label、grade、
outcome、winner orientation 或 prediction-value aggregate。

冻结输入为：

- v5 index normalized SHA-256：`4bff2b9fa48f2b530de886ab6b799011e8c4aa48ed378cdee0959c8b087a1627`；
- coverage matrix SHA-256：`056ac1582deea643be8b06339aec61a99ad1a35760be8500a20bb004c3e058c2`；
- independent coverage verification SHA-256：`3ecab354839054af16ed808b0fccb92025ee4a3d397007ce88141445f5c56149`；
- control commit：`3182b75d8b5fb2835007d575849c99977bbbaca6`。

两份 coverage aggregate 已从正式只读根目录取回，并以 raw SHA 证明与 GitHub 可访问副本逐字节相同；pair-level
predictions 没有复制入仓库。

## 2. v6 契约

v6 在 v5 的 9 项 evidence stack 中增加第 10 项 `prediction_escrow_common_support`，并增加四条强边界：

1. 允许陈述 exact common structural pair universe；
2. 禁止把 common pair universe 写成 common strict-effect population；
3. 禁止七臂 accuracy/effect 语言；
4. 禁止把 transition gate 写成已解锁。

新增 entry 绑定两份 JSON，并逐字段断言 pair/run/task、arm、缺失、双 activation 交叉表和 outcome-blind scope。
独立 verifier 不导入 builder，重新构造整个 index，并复核旧 9 项与新增项的所有路径、哈希和 JSON assertions。

## 3. 正式结果

正式 v2 根目录为：

`/research/d7/spc/yzyang4/decision-corpus-evidence-index-v6/3182b75-v2-threadcap`

结果为：

- status：`INDEPENDENTLY_VERIFIED_COMMON_SUPPORT_EVIDENCE_INDEX`；
- 10 entries / 28 JSON artifacts / 3 bound files / 362 JSON assertions；
- index SHA-256：`0ee7d885dcaccab59b8294d42f1a165d3b7f1354d433303f978ae7e8c18df9d1`；
- independent verification SHA-256：`c7c23aa74e2fc92502d48b24eb2bbf6593b7ef653aa70b8066423d595e7d42b8`；
- focused：`7 passed, 1 skipped in 0.29s`；
- full：`991 passed, 1 skipped, 47 warnings in 71.75s`；
- builder A/B 与 verifier A/B 均逐字节一致；
- credential filename/content hits=`0/0`；
- outcome read / prediction aggregate / GPU/API=`false/false/0`；
- 正式 `SHA256SUMS` 文件自身 SHA-256：
  `784271eb69673e5487ab47aa571bd77a8fb967762c66d114d77aae6298940680`。

GitHub 目录 `phase1/results/decision_corpus_evidence_index_v6_20260825/` 的 index 与 verification receipt 和正式件
逐字节相同。

## 4. 失败历史

第一次正式尝试没有覆盖或删除。未限制数值库线程时，full pytest 在登录节点观测到约 `2892%` CPU，5 分钟仅到
14%；为避免资源滥用，精确进程组被人工终止，且 builder/verifier 尚未运行，没有科学结果。失败根目录封存为：

`/research/d7/spc/yzyang4/decision-corpus-evidence-index-v6/3182b75-v1`

其 `SHA256SUMS` 文件自身 SHA-256 为
`379754b3d463b9d12db16f4b79748621842a6b566a995a8c3e0a8ba53d62c947`。v2 固定 OMP/OpenBLAS/MKL/NumExpr/
VecLib/BLIS 为 1 线程后通过；失败尝试不冒充测试失败，也不从历史中删除。

## 5. 可支持与不可支持的结论

现在可机器验证地说：七个冻结 prediction escrow 字段落在同一 2,589-pair canonical structural universe，覆盖 324
runs / 29 tasks，intersection=union=2,589、IoU=1、orientation reversal=0。双时间分层仍必须报告为 417
both-post、507 post-WL/transition-support-only、1,665 both-support-only；transition 的 missing-parent null 和仅 363
strict-effect-eligible pairs 不能被同池结论抹掉。

本结果是数据/benchmark 的正资产：未来不同 predictor 的 paired comparison 不再被 pair-pool 差异混杂。它仍不证明
任何一个 predictor 有效，也不改变 first-960、target-300、transition 1,500-pair/150-run/任务集中度门或 GPU effect
授权状态。
