# Score-channel grounding availability 与 truth-support 正式审计

状态：`GROUNDING_AVAILABILITY_SECONDARY_COMPLETE` + `DISCRIMINATIVE_COMMON_SUPPORT_ZERO`。

本结果是已知旧 primary aggregate KILL 后冻结的 post-hoc descriptive analysis，不是第二个 confirmatory test。它没有
改变历史机器状态，但纠正其科学解释：旧共同覆盖 support 的真值全部并列，不能比较排序能力。

## 核心结果

- 158 parents / 320 candidates / 94 runs / 17 tasks；candidate count 154×2、4×3。
- 联合通道状态：both=7、external-only=8、stdout-only=85、neither=220。
- 148/158=`0.9367088607594937` parents 的 sibling truth 全并列；仅 10 个 non-tied，且只来自 4 tasks。
- external：任意可用 parent=10、comparative=5；但在 10 个 non-tied parent 上二者都是 0。
- stdout：任意可用 parent=56、comparative=36；在 non-tied parent 上分别为 3 和 1。
- primary common：6 cards / 3 parents；truth-tied=3，truth-nontied=0。
- identifiability funnel：structural 158 → truth-informative 10 → external-comparative 0 / stdout-comparative 1 →
  paired-channel-comparative 0。

Post-hoc regret 分解中 external/stdout/hybrid ranking regret 都为 0；结合上述漏斗，这表示缺少可比较支持，不是通道
完美。external−stdout total-regret mean=`-0.00006231927410509466`，run CI=
`[-0.009615384615384616,0.00931010760618107]`，task CI=`[-0.00024212570430995738,0.0]`；
hybrid−stdout mean/CI 均为 0。方法正主张不允许。

## 复现与完整性

Availability producer×2、independent verifier×2 的三份输出/receipt 分别逐字节一致；producer/verifier stderr=0。
Truth-support audit 在 fresh no-smudge commit 上双跑逐字节一致，focused=`8 passed in 0.33s`，full phase1=
`747 passed, 33 warnings in 55.03s`，stderr=0。

- availability source commit=`ab062e1a41c483a87f6d30213b35b8ba88689cb6`；
- availability summary SHA=`b561db4dd652f676f3cfce3454908ec68057f328f784941e240682554a5fd1b6`；
- candidate CSV SHA=`cffd40db71e4af0d3a7e8ef53bfe1022ad5344777c535a782508f8f30f987a4a`；
- per-parent CSV SHA=`79c334cbd0623b16bc24963f7a60d9a9d406d2ebae8bdae987cf3971ba21587b`；
- independent verification SHA=`df8ad759182827a68c4af37f91b12bffefefa0986c3f3815532026a003a36dba`；
- truth-support source commit=`c1a19cf1b69ebdabf0c4d60b010c448c56210a02`；
- truth-support audit SHA=`cae8bd6e13a9caa2c33b0bc0734b443ca0f01cd05c611cd955bf3d268b1f5862`。

只读正式目录：

- `/research/d7/spc/yzyang4/grounding-availability-secondary/ab062e1`；
- `/research/d7/spc/yzyang4/score-channel-truth-support-audit/c1a19cf`。

两条链均绑定原 selection/replay/approval/orientation/four-shard SHA；没有输出 raw score、label、stdout 或 code；GPU=0、
API=0、model fit=0。结构化关键结果见 `reported_summary.json` 和 `truth_support_audit.json`。
