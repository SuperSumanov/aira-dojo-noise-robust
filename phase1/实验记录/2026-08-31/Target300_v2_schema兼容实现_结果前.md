# Target-300 v2 schema 兼容实现（结果前，2026-08-31）

## 实现边界

producer 与独立 verifier 的唯一逻辑改动是把 provenance key-set 的 strict equality 改为：

`required_keys <= actual_keys <= required_keys | {competition_id_source}`

`competition_id_source` 存在时，各自只接受 `explicit_journal` 或 `archive_consensus_fallback`。字段不进入
`cohort_runs.jsonl`，因此不改变 run identity、task、eligibility、archive 时间序、去重、target=300 或完整 boundary archive 规则。

新增 mixed legacy/new schema 正例；新增 producer 和独立 verifier 的非法 optional value 反例。协议、实现与部署静态门共
24/24 tests 通过。代码 SHA-256：

- producer：`0273b1e1d6db0e8acc2d90682d03cbcd1da88dfe1cf3eabf84f76619c871d25f`
- verifier：`4ed03a0fb9108d33ce9b4f5d3740231d55c187c50cf38cf3f20fa9cba345622e`
- one-shot wrapper：`1674743050c7d333476c6a88b3627f869a2bcbde9b9318641298d530e39761c5`
- deployer：`08fe53516b3aa3d047bd24aba0361884b65ebb5bcbbe0bf10751edf990f99306`
- runtime-patched formal runner：`0f50c1dc8d0742b688a14a4c000d66cfa4e1bf95ccb90bdf4a2135221d5edbff`

runtime patch 只做两件事：使用独立 v2 worktree 路径；在 producer 前断言 LATEST 仍精确等于 v1 自动冻结的
`30945550...104f`。调用者不能传 candidate，固定 attempt root 保证 v2 只能尝试一次。previous 仍绑定 193-run / 60-archive
formal output 的 manifest/summary/verification 三个原始哈希。

## 测试说明

本地 focused/static tests 为 24/24。Windows 本地 Python 没有 scipy/sklearn，full suite 在 11 个依赖导入处 collection-stop；
这不是实现测试失败，也没有运行科学 producer。正式 runner 会在远端固定 venv 中先跑 focused 与完整 phase1 suite，只有全部通过后
才启动 producer A/B；因此远端 full suite 是硬门而不是事后检查。

v1 的 rc=2 与失败产物永久保留，v2 不覆盖或重跑 v1。v2 仍为 CPU-only，且未读取候选身份/profile/private selection、
truth、outcome、prediction、accuracy 或 utility。
