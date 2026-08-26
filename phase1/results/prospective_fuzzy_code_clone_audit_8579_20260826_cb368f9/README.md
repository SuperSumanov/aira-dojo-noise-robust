# Prospective first-960 fuzzy code-clone audit（snapshot 8579）

本包来自公开 source commit `cb368f95c5374fd2ab7448455b3ba3af054d02ec` 的 fresh detached no-smudge
Linux worktree，绑定不可变 snapshot
`8579d7cd32091a11089b935217f7189e321b1d623dbaa69233182ba2fedd9248`。阈值、表示、五项成功门和独立验证
均在读取真实相似度前冻结。

## 正式结果

- 366/960 runs、10,683 endpoints；10,674 fingerprinted，coverage=`0.9991575400168492`；
- Jaccard≥0.85：61,070 candidate pairs exact-check 后有 7,069 near-duplicate pairs；
- 7,069 对全部在同一 physical run：parent-child=`4078`、same-parent siblings=`50`、same-run-other=`2941`；
  cross-run same-task=`0`、cross-run cross-task=`0`；
- Jaccard≥0.95：2,758 pairs，cross-run affected endpoints 仍为 0；
- 五项预注册门、384-doc brute force、producer/verifier A/B 全部通过；
- focused=`13 passed`；full=`1163 passed, 47 warnings`；forbidden/credential hits=`0/0`；
- GPU/API/model-fit/base-LLM update=`0/0/0/0`；producer/verifier A 的 wall time=`4:16.50/4:01.27`，
  max RSS=`3298876/2936592` KiB。

producer/verifier/formal-summary SHA-256：

- `f07454fdaacfc5ace8ef8b7f6630ed824b80acd0666bc549a2f6e53bc29ccbdc`；
- `9c6d4bd0938e3cb2517b1c317a8eaa89628bff04eb9d537ac35ec9e4b7c10cf4`；
- `8ddc1dbf5efb154fd3ea4f468c98ba5447c6138c4296afaf8f563dbc6a8d1493`。

远端 formal manifest SHA-256=`88c6309bc0b4694a4bcc962915a68374e87df3a852c9bad5f29bf320a3f46204`。

## 解释边界

可用主张是：高相似代码在搜索轨迹内部大量存在，但在固定 lexical token-5gram/Jaccard 定义下严格
lineage-local，并非跨 physical-run 或跨任务模板复制。`exact` 只指 128-bit shingle-set threshold join；本结果不证明
semantic equivalence absence、变量重命名 clone 不存在、公开任务未进入底座预训练、predictor 无泄漏或方法有效。
当前仍是 provisional 366/960 prefix；first-960+closure 后必须原协议重跑。

`producer_a.json` 与 `verification_a.json` 是 formal A 的逐字节拷贝；`remote_formal_SHA256SUMS` 绑定完整 19-file
远端 formal root，本目录 `SHA256SUMS` 只覆盖发布载荷。
