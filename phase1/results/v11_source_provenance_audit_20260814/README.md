# v11 source-journal provenance backfill

状态：`V11_SOURCE_PROVENANCE_AUDIT_COMPLETE`。该审计只读取 allowlist 中的 journal JSONL，并在 JSON
解析前扫描 credential 形状；没有打开 frozen/test/held pair 文件，也没有读取 env 或 tarball。

在 v11 的 16,012 cards 中，14,339 张（0.895515863102673）可唯一映射到 592 个 source-journal SHA，覆盖
587/667 个 heuristic runs。可追溯范围内发现 5 个 heuristic runs 各自合并了两个真实 journal，发现 0 个
source journal 被拆到多个 heuristic runs，card-source collision 为 0。这意味着已观察到的问题是保守合并、
physical-run 数少计和 cluster 过粗；当前审计没有发现由该规则导致的跨-run split 泄漏。

限制必须与结论同时保留：1,673 张未映射 cards 没有得到 source-truth 证明；另有 1 个旧 journal 命中
credential 形状并在解析前跳过。因而“0 split”只适用于可追溯的 89.55%，不能写成全语料绝对证明。

归档文件：

- `summary.json`：完整 root/batch 统计、5 个 merge 反例与限制，SHA-256
  `aa3d56d975269e5d9ba5b98c01651309a06376c06d628652c54aa48c7ab22a93`；
- `artifact_manifest.sha256`：远端完整产物 manifest，SHA-256
  `6f9913425f74a5106ecd8cc2feb2acdb6d918a6384e81afde267bde6bfe9a05a`；
- producer 源码为 `phase1/source_provenance_audit.py`，SHA-256
  `85d1aef6304179281f08579f3822ece697e2c3f508eab470a4873a6cd57225ce`。

逐 card 的 `covered_card_source_sha.json`（1,954,401 bytes，SHA-256
`c914a9a00532ddd3f774b272f08ca9190cb3bb8579e0bb285f3dcd0c70bbd278`）保留在受控远端产物目录，未因体积
复制进 Git；manifest 固定其身份。
