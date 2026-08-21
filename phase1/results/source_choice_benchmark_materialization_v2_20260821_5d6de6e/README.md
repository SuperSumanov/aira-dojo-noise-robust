# Source Choice Benchmark Materialization v2

发布裁决：`SOURCE_CHOICE_RAW_MATERIALIZATION_VERIFIED_MODEL_VIEW_BLOCKED`。物化控制 commit：
`5d6de6eddad30cef46c5803d8810f835c3f58c4f`。

## 双结论

原始物化与封存本身正式通过。固定的 3,000 个 answerability-conditioned source groups 全部得到完整候选代码，
共 8,027 个 candidate slots；train/frozen/extension 分别为 2,109/778/113 groups 和
5,739/2,041/247 candidates。1,521/3,000 groups 为 source size>=3，23 个任务有覆盖，train/frozen 的
parent 与 physical-run overlap 均为 0。899 个原本不在 Cards 中的候选从 169 个已绑定且先过 credential gate
的 journal 中恢复；169/169 全找到。公开 frozen/extension 文件的 winner 字段均为 0，label vault 独立封存，
本轮没有用其训练或评分。

但 v2 的原始候选对象不能直接作为 predictor 输入发布。物化完成后、任何模型或 frozen 评分之前做的 train-only
后验字段审计发现：5,042 个 `card` candidates 包含全部 2,109 个 winners，而 697 个
`journal_recovered` candidates 的 winner 数为 0。2,109 组中 496 组混合两种来源。仅过滤掉
`journal_recovered`，uniform expected top-1 就从 `0.4001780146516962` 增至
`0.4399241346609778`，delta=`0.039746120009281544`；固定 min-hash control 也从
`0.39023233760075865` 增至 `0.42484589853010907`，delta=`0.034613560929350404`。
这是 post-selection observability 泄漏，不是合法的 decision-time signal，也不是 predictor 正结果。

因此，`provenance` 与 `source_journal_sha256` 只能保留在内部审计层，严禁进入训练、公开 frozen inputs 或模型
harness。v2 原始物化包不会通过 Git LFS 分发。下一步只授权单独的 exact-field decision-time 投影视图：结构化
删除上述字段、重新生成 label-free frozen/extension inputs，并让独立 verifier 与 sealed evaluator 拒绝任何额外
字段。该投影完成前不得训练新 source-choice 模型或读取 frozen/extension label vault。

## 可复现性与完整性

- producer x2、vault x2 与不 import producer 的 verifier x2 均逐字节一致，三个 diff 均为 0 bytes；
- independent verifier 状态为 `INDEPENDENT_SOURCE_CHOICE_BENCHMARK_MATERIALIZATION_VERIFIED`；
- focused=`14 passed`；完整 phase tests=`695 passed, 25 warnings`；
- forbidden scientific path hits=0，credential filename/content hits=0，前后 worktree drift=0；
- 正式公开侧与 vault 侧均为只读，writable files=0；
- GPU=0、API=0、base LLM update=0；本次 release decision 未打开 frozen/extension labels；
- 正式公开侧远端目录：
  `/research/d7/spc/yzyang4/source-choice-benchmark-materialization/5d6de6e-v2`；
- 独立 vault 目录：`/research/d7/spc/yzyang4/source-choice-benchmark-vault/5d6de6e-v2`。

关键 SHA-256：

- public summary：`dc5a7af25cef3cb967b76cbe3262473b42011bd6f8758caec4e4a1a198ceec1f`；
- public manifest：`04973efd6708593208171eac36bb40c946bd21378ae9cf3ad43c2fccec2a8a92`；
- independent verification：`a915da2d77fa7d8db9775035b0a31a02ddb6ec20451d9dd30f8adb67fda96479`；
- train-only provenance audit：`5a02a10df7f823785f08d3a59cc5fd6b5b12277a96da6c7c5e13ad6a778894e1`；
- 回传的远端 `SHA256SUMS`：`d199fe0645f08d90154c1949c1f655f5cb90cbc13782f2926b4d251de76a3577`。

## 主张边界

允许主张：在 fixed answerability-conditioned support 上，我们已可复现地恢复 3,000 个真实 source choice sets
与完整候选代码，并发现/封锁了一个由选择性记录产生的确定性 provenance 泄漏。这把此前的 answerability census
推进成可构造但尚未可公开训练的 benchmark 原料。

禁止主张：不得称原始 v2 为 release-ready/model-ready benchmark，不得使用 provenance 产生 accuracy，不得声称
整个 v11 complete，也不得写 predictor/search utility、listwise 方法收益、prospective effect 或算法 novelty。
materialization success 与 release readiness 必须分开报告。
