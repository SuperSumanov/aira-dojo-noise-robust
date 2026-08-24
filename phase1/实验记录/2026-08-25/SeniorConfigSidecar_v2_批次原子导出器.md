# Senior config sidecar v2：批次原子导出器

日期：2026-08-25

状态：`ATOMIC_BATCH_EXPORTER_VERIFIED_NOT_DEPLOYED`

## 1. 目的

单 run exporter 已能生成 prompt-sensitive v2 row，但学长通常一次发布同一任务的 4/8 个 seeds。手工循环会留下三类
风险：某个 run 失败后仍遗留部分 sidecar、参数顺序改变文件字节、以及重复 run ID 被静默写入。本轮新增
`phase1/senior_experiment_config_batch_v2.py`，只面向 producer 侧尚未归档的显式 `dojo_config.json` 路径。

它不扫描目录、不展开 tar、不读取 `env_variables.json`，也不推断 task、hardware 或 generator release。所有 config
先在内存中通过既有 v2 单 run 契约；随后检查 run ID 唯一，按 UTF-8 run ID 排序，使用 exclusive temporary file、
`fsync` 和 atomic replace 一次落盘，并打印完整 manifest SHA-256。任意 row 失败时 output 不存在。

推荐把 `<archive-basename>.config_v2.jsonl` 作为 tar 的不可变邻接文件，在任何 archive outcome 被分析前上传；不得把
raw config、环境 dump 或 solver projection 放进 sidecar。

## 2. 测试与失败历史

攻击与行为测试覆盖：

- 反转 CLI config 参数顺序后 bytes 不变；
- 4-run canonical JSONL、逐 row stratum hash 与 manifest hash；
- duplicate physical run ID 整批拒绝；
- 一个 credential-shaped config 使整批零输出；
- mixed operator client 使整批零输出；
- existing output、错误后缀、空 batch fail closed；
- 真实 CLI 两 run smoke。

首轮本地测试为 `4 failed, 12 passed`：新测试夹具使用了比冻结契约更宽松的人造 run ID，单 run exporter 在任何输出
前正确拒绝。夹具改为真实 `family_seed_<n>_id_<8hex>` 形式后为 `17 passed`；实现契约没有因测试方便而放宽。发布
diff 中攻击测试原有一条假 key-shaped literal，内容扫描计数为 1；随后改为运行时字符串拼接，保持攻击覆盖并使最终
filename/content scans=`0/0`。

## 3. Linux 正式复验

control commit=`f4099ade59d300c42eec482a4746138ab27b3699`。fresh detached Linux worktree 结果：

- focused：`17 passed in 0.19s`；
- full：`1000 passed, 47 warnings in 70.79s`；
- CLI help、release ancestry、工作树前后 clean 均通过；
- credential filename/content hits=`0/0`；
- archive/outcome read / GPU/API=`false/0`；
- receipt status=`ATOMIC_BATCH_EXPORTER_VERIFIED_NOT_DEPLOYED`；
- formal root=`/research/d7/spc/yzyang4/config-v2-batch-postpush/f4099ad-v1`；
- `SHA256SUMS` 文件自身 SHA-256=
  `ceb4959cc4f45a1190c065c6edff4c995443d87f1944190b3e92bab775da31b5`。

## 4. 当前边界

本结果消除了“工具只能逐 run、容易形成半批”的工程缺口，但没有观察到真实 producer sidecar，学长生产也尚未部署。
因此 0823 及更早 archives 仍不能事后回填为 prompt A/B、b80 exact-stratum 或 scaling confirmation。只有下一批在
outcome-before 阶段实际生成并上传 sidecar，consumer 再与完整 source provenance/producer commit 组合通过 validator，
状态才能从 NOT DEPLOYED 升级。
