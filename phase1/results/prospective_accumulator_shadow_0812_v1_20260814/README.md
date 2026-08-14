# Prospective accumulator：0812 真实 schema 盲态复放

日期：2026-08-14。协议：`prospective_accumulator_v1`。代码 commit：
`ca86739ed992d11a11d652dcbcb2e85394308532`。

## 裁决

正式工程状态为 **`PROSPECTIVE_COHORT_COLLECTING`**。累积器对最终 0812 intake 做了真实 schema 复放，重验
archive manifest/provenance、run 与 endpoint identity、历史 endpoint/exact-code denylist、all-to-eligible 子集关系
和结构 sibling pairs。它还会拒绝跨 drop 重复的 source archive、physical run 或 endpoint。

该批 57 个 physical runs 均早于 scorer 激活，因此 eligible、provisional first-240 和 provisional first-960
计数均为 0；没有生成任何 frozen cohort 文件。这是预期的 fail-closed 行为，不是负科学结果。

## 冻结规则与盲态证据

- first-240/first-960 在生产关闭前只能是 provisional，不能仅因累计数量达到阈值就冻结。
- 只有非 outcome 的生产关闭凭据绑定准确 registry SHA，并声明 `all_scheduled_runs_uploaded=true`、
  `outcomes_read=false`，才允许按预注册顺序冻结；关闭时不足 960 则记为不完整。
- `label_vault_opened=false`；outcome 与 scorer prediction 打开列表均为空。
- `sealed_vault_registry.jsonl` 只记录 vault 的路径与 opaque SHA，不读取 vault 内容。

关键哈希：

- `summary.json`: `f2cbefa765b90c8c432a1ecb2467ce235ce7051cfaa0e7cbb22c3cc4c776d13c`
- `registry.jsonl`: `c6039630ffbac8a47b43b86358b8a41b6d6df215bb366f3078fae12e73380b9e`
- `sealed_vault_registry.jsonl`: `6c12fb26d822b48139c3a53d3d1ae8df77625f5d3d376f42b3c24f9b49028cfa`
- `provisional_runs.jsonl`: `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`

`run.txt` 是最终 commit 上的预检、测试、producer 和哈希日志。三个 provisional JSONL 均为空文件；它们被保留
是为了证明当前状态，而不是遗漏数据。

## 归档边界

本目录不含 label vault、端点代码、outcome 或 prediction。它只保存 summary、registry、sealed-vault registry、
空的 provisional 身份清单与运行日志。
