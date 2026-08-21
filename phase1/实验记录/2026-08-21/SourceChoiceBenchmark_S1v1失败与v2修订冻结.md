# Source Choice Benchmark S1v1：首次失败与 v2 修订冻结

日期：2026-08-21。v1 控制 commit：`537a34c69cbe51b3f5b2fc2b9e63cbaef4cb7571`。

## v1 失败事实

首次正式 producer 在 13 项 pre-flight 与 14 项 focused tests 通过后运行 8:07，最大 RSS 3,358,616 KiB，随后以
`selected parent card absent`、exit 2 fail-closed。它没有写出 public 或 vault 正式结果；失败目录保留在：

- `/research/d7/spc/yzyang4/source-choice-benchmark-materialization/.537a34c-v1.tmp.1360452`；
- `/research/d7/spc/yzyang4/source-choice-benchmark-vault/.537a34c-v1.tmp.1360452`。

失败发生在 candidate journal/code 已扫描后、group 输出前。它不是 S0 的 candidate-code 支持门失败，而是 v1
自行新增了 S0 未定义的 parent-code requirement。该要求与项目已知的 orphan/parent-pruned 边界冲突；把
`candidate_code_reference_complete` 扩写成 parent+candidate context complete 是 scope drift。

## v2 唯一修订

v2 对全部 3,000 组统一采用 candidate-only choice context：task、run/parent hash、source size 与完整 candidate
codes。parent code 对所有组一律不作为字段使用或输出，parent card 不作为资格条件；cards JSONL 的整行 bytes/
JSON 仍会经过 credential scan 与解析，不能误写成物理上从未读取 parent code bytes。不按 parent availability 筛组，也不把
parent code 作为可选特征制造不均一 context。candidate card 仍须独立满足 task/run/lineage-parent/code hash，missing
candidate 仍须满足 status-bound journal SHA/parent/code closure。

其余全部不变：3,000 groups、8,027 candidate slots、role/task/arity 精确计数、status winner、candidate hash 排序、
train/frozen 零交集、credential-first、train label 与 frozen/extension vault 隔离、producer×2 与 independent
verifier×2。v2 不降低任何 candidate-level 门，也不从失败后筛数据。

若 v2 出现任一 candidate identity/code/context/hash 缺口，S1 整体关闭；不得再做第三个 schema rescue。通过也只说明
candidate-only benchmark artifact ready，不支持 parent-aware transition critic、predictor/search utility、完整 v11、
prospective effect 或算法 novelty。
