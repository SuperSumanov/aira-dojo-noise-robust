# Source opportunity journal status：预注册与执行前检查

日期：2026-08-15。状态：在读取 missing child 对应的 journal node status 前冻结。

本实验承接 721/870 incomplete-parent identity recovery 正结果。唯一问题是：已恢复的 996 个 missing child IDs
中，有多少能在 allowlisted source journals 内唯一绑定到真实生成节点，并把“为何未进入 labeled cards”分解成
execution failure、official grade 缺失、normalization metadata 缺失或仍不可解释。

## 冻结输入与安全边界

- identity registry：
  `/research/d7/spc/yzyang4/source-identity-recovery-v11-3faf001-a1/producer/per_parent.jsonl`，固定 SHA-256
  `b4261a4f042e92acca4a53630efe3e33ea1f2847d1a8148e9c8f18c35b447cd2`；
- journal roots 仅限先前 provenance audit 的八个 allowlisted roots：ours、senior_older、extract_0806、0807、
  0808、0809、0810、0811；
- 只选 canonical `checkpoint/journal.jsonl` 或同 run 的唯一 `JOURNAL.jsonl`；不读 env、workspace、submission、
  frozen/test pair、first-960 或 tar 中其他 member；
- 每个 journal 在 JSON parse 前整文件做高置信 credential scan；命中即记录 skipped，绝不解析或打印原文。

## 冻结定义与裁决

对每个 target child ID，journal node ID 按 `competition_id + "__" + node.id/step` 生成。只有恰好命中一个 canonical
source journal/node 才算 `node_recovered`；0 个记 missing，>1 个记 collision 并 fail-closed。

对唯一 recovered node 只读取 availability/status，不记录 score magnitude、code 或 stdout：

- `EXECUTION_ERROR`：`exit_code` 是非零整数；
- `OFFICIAL_GRADE_ABSENT`：`exit_code==0` 且 `metric_info.score` 不存在或为空；
- `NORMALIZATION_METADATA_ABSENT`：`exit_code==0`、official grade 存在，但 gold/silver/bronze threshold 全缺；
- `UNEXPLAINED_FILTER`：`exit_code==0`、grade 与至少一个 threshold 都存在；
- `EXECUTION_STATUS_UNKNOWN`：其余 schema。

固定正门：target node recovery rate≥0.80、collision=0、每个 recovered child 的 journal parent ID 等于 identity registry
parent、producer/verifier 逐 child 与逐类计数一致。全过=`VERIFIED_HIGH_COVERAGE_MISSING_STATUS_REGISTRY`；有唯一
恢复但不足 0.80=`PARTIAL_MISSING_STATUS_REGISTRY`；无恢复或结构冲突=`MISSING_STATUS_REGISTRY_UNSUPPORTED`。

## 13 项执行前检查

1. **唯一问题**：只恢复 missing identity 的 node/status，不训练模型。
2. **主因变量**：996 个 target ID 的 child-equal unique node recovery rate。
3. **parent 控制**：journal 重建 parent ID 必须与冻结 registry 完全相等。
4. **collision 控制**：同 ID 多 journal 命中一律 fail-closed，不择优。
5. **结果隔离**：不读 numeric grade、pair orientation、gap、first-960 或 predictor output。
6. **敏感字段**：不输出 code、term_out、metric 值、路径中的用户环境内容。
7. **credential**：scan-before-parse；命中 journal 只计数和相对路径 hash，不打印原始 bytes。
8. **未覆盖处理**：0 命中保留为 `SOURCE_JOURNAL_NOT_FOUND`，不删除。
9. **schema 处理**：缺 exit/status 字段归 unknown，不从 stdout 猜。
10. **双实现**：verifier 不 import producer，重扫 roots 并逐 child 重建。
11. **复现**：固定 identity SHA、root inventory、source commit、命令、Python 与产物 hashes。
12. **预算**：CPU-only、GPU=0、API=0；预计顺序读取两遍约 800 个 journal，少于 10 分钟。
13. **停止**：固定一次正式执行；不新增 root、改 0.80 门或按结果打开 tar 补覆盖。

通过只允许发布 journal-status registry 与缺失机制描述。它不证明 missing-at-random、不恢复 label，也不自动授权
censor-aware predictor 或完整 choice-set utility 主张。
