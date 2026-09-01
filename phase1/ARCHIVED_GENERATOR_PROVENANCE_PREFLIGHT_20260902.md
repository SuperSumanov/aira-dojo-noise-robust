# Archived generator provenance reconstruction preflight（2026-09-02）

状态：`FROZEN_BEFORE_FORMAL_RUN`。本协议只补历史 v11 发布治理信息，不读取或评价
first-960、Target-300、Target-522 的标签、预测、accuracy、utility、候选身份或 private selection。

## 1. 问题与单位

v11 provider inventory 中五个 late historical batch 仍有 6,111 行未映射。首次入库 commit、文件名、
日期和脱敏后的共享代理环境都不能证明生成模型。原始 source archives 另含每个 physical run 的
`dojo_config.json`，其中四类 operator 的 `solver.operators.*.llm.client.model_id` 是直接生产配置证据。

正式单位是 **card ID**，不是 batch。每个归档 run 的 config 必须恰好给出一个一致 model ID；同目录
journal 只用于恢复 `competition_id + node id`。目标 card 若跨任何 source occurrence 对应多个 model，
记 ambiguous；没有证据记 missing。不得把模型标识进一步推断为 API 服务商、合同主体或账号区域。

## 2. 冻结输入

- `phase1/corpus_releases/batch_registry.json`：固定 batch SHA/bytes/rows；
- 五个 batch：`cards_senior_0805seq.jsonl`、`cards_senior_0808.jsonl`、
  `cards_senior_0809.jsonl`、`cards_senior_0810.jsonl`、`cards_senior_0811.jsonl`；
- source-map 只在远端 formal root 中保存绝对目录；公开 template 不含本机路径；
- 所有普通文件都作为候选 archive，包括 0811 的两个无 `.tar.gz` 后缀归档；
- archive 采用最后一个同名 member 的既定入库语义。

正式运行前须固定 exact Git commit，并重新核验 batch registry 与每个 source archive 的 SHA-256 aggregate lock。

## 3. 安全与泄漏门

1. 拒绝绝对路径、`..`、symlink、hardlink、超限 selected member；
2. 只读 `dojo_config.json` 与 canonical journal，绝不打开 `env_variables.json`；
3. selected config/journal 任一严格 credential shape 命中即整次 fail closed；
4. release card JSONL 仅保留首字段 `id`；不保留 label 值；
5. 不读取 prospective resource，不启动网络、GPU、API 或模型拟合；
6. 公开 overlay 只含 batch、card ID、generator model ID、evidence status。

## 4. A/B 与失败条件

Producer 与 verifier 不共享实现：producer 递归收集受限 model identifier；verifier 直接读取已知
operator config 路径，并独立重建 card mapping、batch/model counts、overlay SHA、archive aggregate lock。

以下任一出现即不晋升：

- batch SHA/bytes/rows 漂移；
- archive 不安全、无法解析或 selected member 含凭据形状；
- 同一 config 不止一个 model ID；
- overlay A/B 不同；
- `exact + ambiguous + missing != target`；
- ambiguous 或 missing 非零；
- public artifact 含凭据形状、绝对 source path 或 prospective trace。

## 5. 探索性功效检查（不作为正式结果）

一次未固定 commit 的只读 smoke 显示五批分别为 854、1,628、1,940、835、854 行，合计 6,111；
候选映射为 exact 6,111、ambiguous 0、missing 0。该数字只证明正式实验有功效，必须由本协议的
exact-commit producer、独立 verifier、artifact security scan 与只读 postflight 复现后才能进入主文档。

## 6. 资源与预计时间

- CPU-only；0 GPU·h；0 付费 API；0 模型训练；
- producer 预计 3--6 分钟，独立 verifier 预计 3--6 分钟；
- 产物：`overlay.jsonl`、`summary.json`、`verification.json`、formal/postflight receipt；
- 即使全部通过，也只关闭 generator-model provenance 缺口，不构成法律意见、release clearance 或新的科学主张。
