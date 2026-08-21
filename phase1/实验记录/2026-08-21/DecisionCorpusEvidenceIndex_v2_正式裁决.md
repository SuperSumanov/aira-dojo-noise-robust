# Decision-Corpus evidence index v2：source-aware 正式裁决

日期：2026-08-21。正式状态：`INDEPENDENTLY_VERIFIED_SOURCE_AWARE_EVIDENCE_INDEX`。本轮只读取既有独立
JSON 收据；pair labels、predictor outputs、prospective outcomes、checkpoint、GPU 与 API 均未使用。

## 正面结果

v1 的五项资产已经扩为六个互不合并的 estimands，并由机器可核合同统一绑定：decision corpus、source
opportunity、label repeatability、normalized clone、deployment cost 与 prospective gate。正式 index 含 18 份
无重复 artifact 和 136 个固定 assertions；builder 两遍、独立 verifier 两遍分别逐字节一致。index normalized
SHA-256=`fdb77b4458c4342a0fa62c860ed7141478e38a1dc5c26ac369e70ba961ff5c02`。

新增 source-opportunity 项把“数据不完整”从脚注升级为可发布资产：

- 3,252 个 parent 中，870 个 source-incomplete；721 个 parent 可精确恢复 missing identity，parent-equal rate=
  `0.828735632183908`；
- 共恢复 996 个 missing child identities；其中 902 个唯一连接到 source journal，child-equal rate=
  `0.9056224899598394`；
- 已连接 status 为 893 个 execution error、9 个 official grade absent，94 个仍不可恢复；collision 与 parent
  mismatch 均为 0；
- 因此可以正面主张“发布 labeled sibling fragment + 高覆盖、parent-linked 的 missing identity/status registry”，
  但完整 choice set、missing-at-random 和缺失数值 outcome 三项仍明确为 false。

这比只发布成功 pair 更适合 D&B：使用者可以区分 feasibility 与 conditional quality，知道哪些 sibling 从发布
图中消失以及为什么；同时不会把 execution failure 后的 complete-case 样本误当成原始 agent 决策总体。

## 验证与失败链

正式成功控制 commit=`8da197b89ebe513df0516cf71186c068078bf67b`：focused=
`4 passed, 1 skipped`（正式产物尚未写入该隔离 worktree，因此 checked-in-artifact 测试按设计 skip）；全部 phase
tests=`620 passed, 1 skipped, 25 warnings in 52.75s`。回传后本地 focused=`5 passed`，本地 verifier 与 Linux
正式输出逐字节相同，SHA-256=
`602a4f721e0d7e386917deeab31245ef3f621f0e05b2c3459efabd26abb1e3bd`。正式目录全文件 mode 444，两类秘密扫描
均为 0；`SHA256SUMS` SHA-256=
`03f9776ed84fb97bdafaf62f890bedc3fbbb30b3d0031fdb699c76269d41c74b`。

三个失败 attempt 全部保留且不追认为成功：

1. `971752e...` 在环境初始化时因 `nounset`/`LD_LIBRARY_PATH` 停止，尚未建立科学 worktree；
2. `29441ef...` 的双 builder 与 focused tests 通过，但独立 verifier 因仓库根未进入 Python import path 停止；
3. `fdb3cd2...` 的双 builder、双 verifier 和全部 620 tests 已通过，但零秘密命中时 grep status=1 被 `pipefail`
   误判，未晋级；修复只让 0/1 成为 scanner 合法状态，秘密正则未放宽。

## 结论边界

v2 是更完整的 benchmark/release contract，不是新 predictor 方法，也不产生 prospective accuracy。固定
reporting contract 仍禁止 first/only、complete choice set、MAR 与 prospective effect 语言；self-report 固定为
post-execution signal。first-960 + independent accrual closure、strict-future transition transport 与 clean Qwen
G0/G1 的预算门均不改变。

直接证据：`phase1/results/decision_corpus_evidence_index_v2_20260821/README.md`。
