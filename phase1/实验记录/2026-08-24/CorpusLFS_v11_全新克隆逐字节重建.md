# Corpus Git LFS v11：全新克隆逐字节重建

日期：2026-08-24

状态：`FRESH_GITHUB_LFS_REBUILD_PASS / V11_PUBLICATION_CHAIN_VERIFIED`

## 1. 正式结论

从 GitHub fork `SuperSumanov/aira-dojo-noise-robust` 的 `phase1-value-critic` 分支做了一次隔离的 fresh clone，
禁用初始 LFS smudge，并使用该 clone 自己的全新 LFS storage 从 `origin` 只拉取 v11 registry 中精确列出的 29 个
immutable batch。这个流程不复用本机或集群主仓库的 LFS object cache，因此直接检验了学长从 GitHub 获取发布语料的
可行性。

结果为 **PASS**：29 个 batch 合计 303,226,677 bytes、16,012 rows；`verify-inputs` 返回
`VERIFIED_IMMUTABLE_CORPUS_BATCHES`。随后由统一 `rebuild_corpus.sh` 重建得到：

- rows：`16012`；
- bytes：`305750663`；
- SHA-256：`6794acbf1dbc21ca75bed5899f4dd071b4b0d1a5b092c2e60bc634a8c5701b75`；
- segmentation：667 runs、cross-segment parents=0、mixed-task segments=0；
- status：`VERIFIED_BYTE_EXACT_CORPUS_REBUILD`。

这些数值与 v11 release descriptor 逐项一致。重建 payload 的 high-confidence credential-shape count=0；没有读取
senior raw tar、0812 withheld label vault 或任何 prospective outcome。临时 clone 与重建 payload 在绝对路径前缀复核后
删除，只保留小型不可变收据，因此没有在 big-data storage 再复制一份 corpus。

## 2. 证据

- 执行 commit：`5d443617bf5315c71b6484184483375430466eb0`；
- audit script SHA-256：
  `f27d0a52615df26ecc1cacfa2c415a94bc51983f7efd73b9a87c802273dbf21a`；
- formal root：
  `/research/d7/spc/yzyang4/corpus-lfs-freshclone-audit/5d44361-v11-v1`；
- formal `SHA256SUMS` 自身 SHA-256：
  `56e09c23d81d416de3cf5fb644748b687551580989ddfe09260a4648f6fca92d`；
- corpus release tests：`11 passed`；manifest、递归只读、临时目录清理均独立复验通过；
- GPU/API=0/0。

本地工作站直接运行 `verify-inputs` 曾因部分 batch 仍是 unsmudged pointer 而 fail closed；fresh-clone 结果证明这是本地
尚未执行 `git lfs pull`，不是 GitHub object 缺失。学长应按 README 执行 `git lfs pull` 后再运行
`rebuild_corpus.sh`，不需要访问我们的 big-data storage。

## 3. 不得外推的范围

1. 该 PASS 只覆盖已发布的 v11；v4/v5 仍明确是
   `UNRECOVERABLE_FROM_PUBLISHED_BATCHES`，不得改称可逐字节重建。
2. `cards_senior_0812.jsonl` 仍在 `withheld_batches.json`，因为发布其 LFS object 会不可逆揭开 temporal-blind labels；
   本轮没有上传或放宽该边界。
3. 0821/0822 prospective archives 已进入结果盲 intake，但尚不是脱敏、不可变、可公开的 corpus batch；不能把
   “已摄取”写成“已由 Git LFS 发布”。未来发布必须另做 label/outcome release 决策、脱敏与 fresh-clone 重建。
4. 这是重要的数据可访问性与复现正资产，不是 critic 效果、模型 scaling 或 search gain。
