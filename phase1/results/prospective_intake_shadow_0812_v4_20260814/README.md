# Prospective intake：0812 最终代码影子回放

日期：2026-08-14。协议：`prospective_drop_intake_v1`。代码 commit：
`ca86739ed992d11a11d652dcbcb2e85394308532`。

## 裁决

正式工程状态为 **`SHADOW_REPLAY_PASS`**。远端 28 项相关测试全部通过，随后对学长 0812 的 10 个唯一 archive
进行了全量回放：60 个 run roots 中有 57 个 checkpoint physical runs、3 个 live-only runs；共 9 个任务、
1,304 个非空代码端点与 286 个结构 sibling pairs。所有 run 的 root creation time 都早于固定 scorer 激活点，
因此 eligible runs/endpoints/pairs 均为 0。

这只证明真实 tar schema、收格、安全与防泄漏链可执行，不是 prospective 科学结果，也没有计算任何
scorer-vs-grade metric。

## 安全与盲态

- intake 不解压 tar，只流式读取 `checkpoint/journal.jsonl`；`env_variables.json` 与 live event journal 均未读取。
- journal bytes 在 JSON parse 前完成 credential-shape 扫描，命中为 0；raw journal 不落盘。
- 16,012 个历史 endpoint IDs 与 15,912 个 exact-code SHA 全量检查，两层 overlap 均为 0。
- label 不参与 run/endpoint 选择，summary 中 metric 列表为空。
- label vault 只留在远端封存目录，本归档没有复制或打开它；源 archive 前后 SHA 不变。

关键哈希：

- `summary.json`: `9e3e9b3df34e07d792baf77401c2cf9292b0aaacdabd59c64feb22b4b1e0bdc6`
- `archive_audits.json`: `54727df401645d5a769754ced412d3173ec073bcfa2be3b9556f6db735a59b13`
- `source_provenance.json`: `c1e75e5ab072c544f7e268b99ae0205cb1b24e321018fd7b0c93f79b54cb9f8a`
- `archive_manifest.tsv`: `0ec5086f1fb331128371bb3caf21605489d0249473af079850efc4b22ce6dc91`

语料发布遵守学长的 Git LFS 设计：只上传一次写入的不可变分批文件；`git lfs pull` 后由统一 manifest 驱动
`rebuild_corpus.sh`，再以行数和 SHA 验证逐字节重建，不重复上传每个合并版本。

## 归档边界

本目录只含公开审计件。`all_blind_views.jsonl`、`eligible_blind_manifest.jsonl`、结构 pair 明细与
`label_vault.jsonl` 均未复制到 Git；完整封存产物留在远端实验根中。
