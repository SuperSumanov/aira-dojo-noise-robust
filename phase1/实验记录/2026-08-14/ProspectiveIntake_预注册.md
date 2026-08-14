# Prospective drop intake：outcome 前工程协议

日期：2026-08-14。协议：`prospective_drop_intake_v1`。状态：**在任何 activation 后 senior drop 出现前冻结**。
本协议只实现 `prospective_decision_v1` 的安全收样与盲态评分入口，不改变 active scorer、first-960、任务门、
pair graph、utility 门或论文 frozen 文件状态。

## 1. 唯一目标与输入边界

目标是把每个 senior `tar.gz` drop 确定性地转换为：

1. scorer 可读的 label-free code+lineage manifest；
2. 与 manifest 等 card support、权限隔离的 label vault；
3. source archive/journal/run start 的 provenance；
4. 完成、失败、无标签与未完成 run 的显式流程审计。

intake 不计算任何 scorer-vs-grade metric，不选择 task/operator/success/margin，不解封 0812 或论文 frozen pairs。
source drop 只读且运行前后逐 archive 复核 SHA；输出不得位于 source drop 内。

## 2. tar 与 journal 权威规则

- 对 archive 内所有 member 先检查绝对路径、`..`、反斜杠/NUL、symlink/hardlink/device/FIFO 和资源上限；
  不调用 `extract`，以顺序 tar stream 读取，且只 materialize 固定 checkpoint member。每次正式 drop 在读取前固定
  archive 数/压缩字节、单 archive member 数/声明字节、单 journal 字节与总 journal 字节上限；超限 fail closed。
- **唯一 node-state 权威源是 `<run>/checkpoint/journal.jsonl`**。`<run>/json/JOURNAL.jsonl` 是另一种事件日志
  schema，永不读取；只有 live event log、没有 checkpoint 的 run 记为 `live_only_runs_excluded`，不得静默消失。
- `env_variables.json` 无论是否存在都不读取、不提取、不复制。checkpoint journal 的原始 bytes 必须先做
  credential-shape 扫描，命中即在 JSON parse 前 fail closed；raw journal 不落盘。
- physical run ID 固定为 `journal:` 加 checkpoint journal SHA-256；manifest 的 `source_sha256` 也固定为该 journal
  SHA，active scorer 必须核对二者逐字一致，禁止靠改 run 名绕过。generation start 固定取唯一 step-0 root 的
  `creation_time`，转为 UTC；所有 node creation time 不得早于 root，journal member mtime 不得明显早于 root，
  每个非 root node 必须恰有一个更早 step 的 parent；时间缺失/无时区/越界/未来漂移均失败。上传时间和 tar
  mtime 不能替代 generation start。

0812 outcome-free schema 审计已证明：60 个 run roots 中 57 个有 checkpoint、3 个仅有 live event log；
checkpoint 无独有 step，而 live event log 不是相同 node schema。因此本规则不是 outcome 后挑版本。

## 3. endpoint、标签隔离与完整性

- endpoint 收录仅由“checkpoint 中存在非空 code”决定；是否 finite grade、是否成功、外部分数、gap、task、
  scorer margin 均不得影响 endpoint manifest。无标签 code 也先评分，label vault 中对应值为 null。
- manifest 顶层严格为 `card_id/task/run_id/code/code_sha256/lineage/generation_started_at_utc/source_sha256`；
  lineage 严格为 `parent/depth/step/n_siblings/op`。任何额外字段使 active scorer fail closed。
- label vault 与 blind manifest 分文件原子生成；scorer 命令只接收 blind manifest，不接收 vault 路径。intake
  可以为封存而访问 source 的 label 字段，但 label 不参与 run/endpoint/任务选择、不打印、不进入 summary metric。
- sibling structure 只由 `(task, physical run, parent)` 与 endpoint IDs 生成，不读 label；finite non-tie pair 只在
  first-960 identity 冻结后的 evaluator 中一次性确定。

## 4. pre-cutoff 双层拒绝

旧 667-run denylist 使用历史 heuristic run ID，而新 source-truth run ID 使用 journal SHA，命名空间不能直接等价。
因此在任何 future drop 前，从 hash-locked v11 cards 生成 label-free
`precutoff_endpoint_denylist.csv = (card_id, exact-code SHA-256)`：

- 必须覆盖 16,012 个 pre-cutoff endpoints；输入 cards JSONL 本身含 label，但 producer 与独立 verifier 均只选择
  `id/code` 两个键，不以 label 做筛选、不打印 label，并从原 cards 独立重建每一行；
- intake 在写盘前要求 future endpoint ID 与 exact-code SHA 两层交集均为 0；
- active scorer 在读取 blind manifest 时再次独立执行同样两层拒绝，同时保留原 667-run denylist；
- intake 与 scorer 命令均须显式声明并核对 `expect-precutoff-endpoints=16012`；任一 ID/code overlap、denylist
  SHA/行数/schema/排序异常均为 `INVALID`，不能通过改 run 名绕过。

## 5. cohort 与失败语义

单个 drop intake 只产出 eligible identity/manifest，不决定 first-960 停止。后续 accumulator 仍按
`(generation_started_at_utc, source_sha256, physical_run_id)` 对所有合格 runs 排序，first-240 只作盲态结构报告，
first-960 才一次性解封 outcome。达到前只允许看路径、SHA、run/task/endpoint/structural-pair 数与作业健康。

有 checkpoint 且 task/时间/树结构可信、但没有非空 code 的 completed run 仍计入 prospective physical-run
identity，`flow_status=no_scoreable_code`、endpoint=0；有 code 但无 finite grade 的 endpoint 仍先盲评分。live-only
单独计数。无可信 task/start、unsafe tar、credential hit、schema 冲突或 pre-cutoff overlap 使整个 intake
fail closed、不给 cohort 产物，具体原因保留在 stderr/作业日志，不得归入科学负结果。intake 与 scorer 都是
CPU、0 GPU、0 API、0 base-LLM update；正式新 drop 必须使用新 artifact root、原子目录提交与真退出码。
