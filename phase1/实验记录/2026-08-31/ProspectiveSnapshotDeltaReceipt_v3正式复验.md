# Prospective Snapshot Delta Receipt v3 正式复验

日期：2026-08-31
方向：Decision Corpus + Predictor Benchmark + Audit Protocol
资源：CPU-only；GPU/API/model fit/base-model update=`0/0/0/0`

## 结论

我们现在有一个独立、identity-free 的生产 snapshot 增量回执。它不仅信任 LATEST 指针，而是逐项复验两份
snapshot 的 manifest payload，解析 transaction contract，从 transaction 独立重建 intake/score registries，并证明
旧 transactions 与两类 registry 都是新版本的 exact byte prefix；输出只含总量和增量。

对 `813f3c1cb5ae0f4fb26873b5627870e35c3705ea89eb245e5649c4cf4a22b54d` 到
`0c0584b87140d9a3242f2aa59920829e07e9178749880e3c1f3bd0d065e0b07a`，正式结果为：

- transactions：`118 -> 119`；
- all physical / eligible runs / endpoints / structural pairs / tasks：
  `495/469/12,536/3,144/34 -> 499/473/12,680/3,151/34`；
- 增量：`+4/+4/+144/+7/+0`；
- label/outcome/prediction value/accuracy/utility read：`false`；
- archive/drop/run/endpoint/pair/candidate identities emitted：`false`。

允许的论文主张是：生产语料的不可变版本 lineage 可以由一个与 producer 解耦、fail-closed、只输出聚合结构的
审计回执证明。它加强数据集与 benchmark 的可信度，但不是 predictor/scaling/search-utility 方法效果。

## 冻结协议与实现

- scientific protocol：`phase1/prospective_snapshot_delta_receipt_v1.json`，SHA-256=
  `504363f2b5b0c829d83176edae613e77258e65288ad71c4b2aff8fbc4e1e22bc`；
- execution addendum v2：SHA-256=
  `96496e3c0fbaf0233ce0f6be2e473825035852a81734c05a509f24029a7445a9`；
- exact source commit：`734a2b14bc20e97c95421c8faaf26b1109c329e5`；
- verifier/test SHA-256：
  `819304af29235d7f576a094a41f8b458f56f6d3f4f48c12b87163d4b3d8e88c8` /
  `c1ae10ed644b5f044221b68d754640fdc4faf51c4ae31b3bcd01f1b0bb2256f3`；
- formal runner SHA-256：
  `958ea06cb9078d729034fd25d14c186fed8f07e20d3468c2e440635c593183ec`。

## 失败链（均保留，未美化）

1. `formal-0e833df-v1`：focused/full=`34/1819 passed` 后，独立 verifier 在真实数据的第一个 registry
   projection 门失败。原因是 verifier 使用 compact JSON separators，而冻结的 production canonical JSONL 保留标准
   separators；receipt 文件数为 0，LATEST 未改。失败 manifest=
   `ff5a27a190443f01d9cdb91f69286ec321b8ce125169d1eec9402758b50e2d8b`。
2. `formal-734a2b1-v2`：远端主仓尚未 fetch 已推送的 exact commit，fresh worktree checkout 前停止；tests/producer
   均未启动。失败 manifest=
   `2255a2fb50f02ab7aa6d1bd7c02b7d3e53e4aeefa001f7282b1aaab64a0c4697`。

两份失败根都已加 manifest 并递归只读；v3 使用 fresh root，没有原地修复或复用结果。

## 正式通过证据

- formal root：`/research/d7/spc/yzyang4/prospective-snapshot-delta/formal-734a2b1-v3`；
- focused：`36 passed`；
- full：`1821 passed, 48 warnings`；
- producer A/B：receipt 逐字节一致；
- grounded verifier A/B：逐字节一致，且不导入 production/verifier 模块；
- formal manifest SHA-256：
  `69149e510d0bc519363dc48b57e578a3933757ae500e8e830ab60ff849d0bba0`；
- 独立 postflight：manifest payload、read-only、clean worktree、LATEST、A/B、trace/security 全部 PASS；
- network/forbidden-path/credential hits：`0/0/0`。

## 当前 outcome-blind 管线状态

- senior source / observation ledger archives：`267/267`；
- baseline / committed / rejected / pending / ready：`128/119/20/0/0`；
- LATEST inventory：`499 physical / 473 eligible runs / 12,680 endpoints / 3,151 pairs / 34 tasks`；
- transition：已追平 LATEST；
- WL：468 runs，距 LATEST 为 `5<12`，按预注册 batch gate deferred；
- receipt-support：因 WL 未追平而等待；
- Target-522：还差 49 eligible runs；
- intake、transition、WL、receipt-support 与三套 Target-522 相关守护进程均存活。

因此，当前没有学长已上传但漏处理的 archive。新 archive 到达后，continuous intake 会先经过 6 小时 age、3 次观察和
至少 600 秒稳定跨度，再进入相同 fail-closed 链；WL 累积到相对 468-run state 的 +12 门后才会重算。

## Continuous lineage chain 部署

一次性 receipt 已升级为每次 LATEST 变化自动运行的 continuous chain：

- exact commit：`2e59423736747f7d806d50a69fd1f312d4927c48`；
- seed：当前 `0c0584b8...b07a` formal receipt；
- schedule：`96 x 300s`，约 8 小时；
- 每个 successor：primary A/B + non-importing grounded A/B；
- state 只在 immutable COMPLETE、manifest、trace/security、无 symlink、只读门全部通过后原子推进；
- 任一失败保留 FAILED evidence，禁止同目录修补，state 不推进。

第一轮 activation 暴露了一个执行错误：preflight 写着 single CPU，但 runner 没有实际 export BLAS thread caps，完整
测试进程约 `2,948% CPU`。在 full suite 15% 时主动终止精确 pytest process group；focused=`50 passed`，receipt/
monitor/state promotion=`0/0/0`，失败根 manifest=
`1352c528368f70eff55a6e4ba8dfde809373785c21de4922efb4553af34c88f3`。

v2 只添加并断言 `OPENBLAS/OMP/MKL/NUMEXPR/VECLIB/BLIS` 六个上限均为 1；实测 pytest 约 79% CPU。fresh
activation 通过：

- focused/full：`50/1835 passed`，48 warnings；
- primary A/B、grounded A/B：均逐字节一致；
- real delta：仍为 transactions `118->119`、inventory `+4/+4/+144/+7/+0`；
- seed no-change monitor smoke：PASS，未创建伪 artifact；
- activation manifest：
  `0b41b37e11355d5907ef0dac75913f7940d122def141d667f68e4d7db4b8fe6a`；
- deployment manifest：
  `30525bb7d78af6f2b76e9dee83368413efe57b853988476a92f1bacc67bca3c0`；
- postflight：PID `1599587` live、lock held、state=LATEST、artifact count=0、values read=false。

这使语料 append-only 与 code/schema migration 不再依赖人工“看到 LATEST 变了再查”，而成为持续、双实现、可追溯的
benchmark release lineage。允许称正面数据基础设施贡献；仍禁止称 critic accuracy、scaling 或 search utility 增益。
