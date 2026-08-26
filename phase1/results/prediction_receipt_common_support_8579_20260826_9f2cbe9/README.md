# Prediction receipt common support（8579，2026-08-26）

正式状态：`INDEPENDENT_PREDICTION_RECEIPT_COMMON_SUPPORT_VERIFIED`。

## 结论

在 snapshot `8579d7cd32091a11089b935217f7189e321b1d623dbaa69233182ba2fedd9248` 上，WL/graph 与
transition 两套 promoted prediction escrows 通过 frozen independent-verifier contract、记录命令、artifact-summary
SHA-256 和 promoted state 的全链绑定，receipt-certified exact canonical common support 为 2,755 structural pairs。

这不是重新读取 pair identities 的集合比较。新流程没有打开 `pair_predictions.jsonl` 或 transition `pairs.jsonl`，没有
解析 artifact summary 内容，也没有访问/聚合 prediction values；因此不报告 orientation、margin、tie/non-tie、activation
或 effect eligibility。它只认证两份 frozen independent verifiers 对同一 immutable snapshot 所重建的 canonical pair
population 具有 exact common support。

## 验证

- 结果前事故/撤回与 replacement protocol 已先提交到 public commit
  `9f2cbe9bff91c2f0ee6f86ff93d9737f9431547f`；
- fresh Linux focused/full：`19 passed` / `1104 passed, 47 warnings`；
- producer A/B 与 non-importing independent verifier A/B 各自逐字节一致；
- file-level strace：prediction pair file open hits=`0`，outcome-path open hits=`0`；
- formal manifest SHA-256=`179a511d9c85dbde73b93cd8f3f5eec6b90efc53a7c6f75e341fddf33635d995`；
- receipt SHA-256=`3b2d0200cf8982a69837a65ca0511fcb35534c94ee440f6bf17789c09c721263`；
- independent verification SHA-256=`24a7ff758d391f4fd506236df97f1a9d6692ddb965cab490e6e92475e2cb012e`。

WL snapshot-chain exact replay 也先通过 focused/full=`22/1094 passed`，producer 与 one-shot current artifact 逐字节一致，
manifest SHA-256=`ba152f6171a87cc72ec805c8c4ecacd07bd0462b9a93e063709ce19b798e121d`。随后部署 WL
monitor PID=`2374019` 与 receipt-only join monitor PID=`2374760`；transition monitor PID=`2320379` 保持。两个被替代的
旧 WL/value-reading coverage monitors 只经精确 cmdline 核验后 TERM，历史 artifacts 未删除。

## 主张边界

允许：结果盲、零 prediction-value access 的 exact canonical common-support receipt；可作为未来 paired benchmark 的
完整性资产。

不允许：predictor accuracy、方法优越性、orientation 一致、tie/non-tie、activation/eligibility、runtime/cost 或 search
utility。first-960 仍为 366/960，closure=false；outcome/effect 尚未解封。

本目录只收录安全 projection receipts。完整 remote strace 与 immutable manifest 保留在正式根目录，不把任何 prediction
pair 文件复制进 Git。
