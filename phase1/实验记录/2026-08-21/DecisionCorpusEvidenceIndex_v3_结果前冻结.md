# Decision-Corpus evidence index v3：结果前冻结

时间：2026-08-21。该工作只包装已经正式验证的漏斗结论，不产生新的效果 estimand，不读取任何新结果。

## 固定目标

以 normalized-LF SHA-256=`fdb77b4458c4342a0fa62c860ed7141478e38a1dc5c26ac369e70ba961ff5c02`
的 v2 index 为不可变来源，在 source-opportunity 后新增独立的 `decision_observability` 条目。v2 的六项条目、顺序、
artifact、assertion、claim 与边界均不得修改。

新增条目仅绑定两份正式 JSON：远端 `SHA256SUMS` 中 SHA-256=
`e2bf11bc557ff147a11040821a6d3aa5a0650023ba585bbbf7f5e730fcf07ceb` 的漏斗 summary，以及 SHA-256=
`d83f2128ccc1d0309a31b3aa5f518b453514181dc1d858445b23facbcbe4feb1` 的独立 verifier。summary 本地副本必须与远端
manifest hash 完全一致。

## 唯一允许的新增主张

当前 3,252-parent release 中，14.61% 的 source child-slot loss 对应 38.51% 的 declared pair-capacity loss，且
train/frozen roles 均达到冻结的 material gate。它说明 candidate censoring 非线性压缩可观察 comparison resolution。

## 强制边界

- `C(n,2)` 是 declared structural capacity，不是真实 agent comparison log；
- 全部 3,252 parents 都保留 finite/published decision，禁止写“38.5% 决策点消失”；
- 不恢复 complete labeled choice set，不假定 missing-at-random；
- 不证明 predictor accuracy、search utility、因果性或 prospective effect；
- 不读取 code、numeric outcome、pair orientation、first-960 vault、raw archive 或 checkpoint。

## 正式门与复现

固定七条目顺序；固定 source 与两份 artifact hashes；逐条 dotted JSON assertion；builder×2 与不 import builder 的
verifier×2 必须逐字节一致；focused 与全部 phase tests 必须通过；worktree 前后干净；秘密扫描为 0；正式目录只读。
任一项失败即不生成正式解释、不更新方向入口、不提交结果。资源：single-thread CPU，GPU/API/base-LLM update 均为 0；
预计墙钟小于 30 分钟。

