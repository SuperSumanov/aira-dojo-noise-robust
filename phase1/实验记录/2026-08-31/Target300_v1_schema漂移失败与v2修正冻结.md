# Target-300 v1 schema 漂移失败与 v2 修正冻结（2026-08-31）

## 结论先行

从 `98f2` 的 193-run 前缀续接已按预注册的第一个稳定 successor 规则，在 `30945550...104f` 连续 5 次稳定后触发。
v1 没有产生科学结果：12 个 focused tests 与 965 个 full tests 均通过，但 producer A 在读取新 intake 的
`source_provenance.json` 时以 `rc=2` fail-closed；producer B、独立 verifier 与一次性 closure anchor 均未启动或写入。

只读 key-only 审计定位为 forward-schema compatibility omission。126 个 provenance 文件共 520 行，其中 495 行仍为
原 12-key schema；25 行保留全部 12 个旧字段，并只增加正式 intake fallback 引入的
`competition_id_source`。没有缺失旧字段，也没有第二种额外字段。全程未输出字段值、候选身份/profile/private selection，
未读取 truth、outcome、prediction、accuracy 或 utility。

## 为什么不能直接重跑

v1 协议明确规定 formal 失败后不得重试或换 candidate，因此该失败永久保留。修正只能作为显式的 v2 schema amendment：
candidate 仍固定为 v1 自动选中的同一 `30945550...104f`，previous 仍是独立验证的 193 runs / 60 archives exact prefix；
不允许调用者改 snapshot。

## v2 的唯一改动

reader 与独立 verifier 接受且只接受两种 key set：原 12 个 required keys，或原 12 keys 加唯一可选字段
`competition_id_source`。字段存在时只允许 `explicit_journal` / `archive_consensus_fallback`；任意其他额外字段、缺字段或非法值
继续 fail-closed。该字段不进入 cohort identity rows，因此 archive 时间序、run 去重、eligibility、target=300、完整 boundary archive
overshoot 和 previous exact-prefix 契约均不变。

v2 运行前必须新增 mixed-schema 正例与 producer/verifier 非法值反例，运行 focused/full tests、producer A/B、独立 verifier A/B、
trace/security、clean worktree 门。v2 仍是 CPU-only；GPU/API/model fit/base update 均为 0。即使 v2 闭合，也只构成结构身份里程碑，
不会自动授权 truth-support、replay 或 effect 实验。
