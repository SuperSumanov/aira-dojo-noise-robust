# v11 raw choice-set completeness audit

日期：2026-08-15。协议：`raw-choice-set-completeness-v1`。source commit：
`6610618a89c91bd2dbea2ea5be05e8acaac11e94`。

## 裁决

producer 与不 import producer 的 verifier 独立一致裁决：

`VERIFIED_LABELED_SIBLING_FRAGMENT_BOUNDARY`

因此：

- `choice_set_faithful_claim_allowed=false`；
- `labeled_sibling_fragment_claim_allowed=true`；
- v11 b0 只能称结构有效的 **published labeled sibling fragment**，不能称完整 source choice set。

## 冻结输入与覆盖

- cards：16,012；
- b0 pair rows：5,897；
- parent units：3,252；
- train：4,263 pairs / 2,293 parents / 333 runs / 23 tasks；
- frozen：1,498 pairs / 845 parents / 92 runs / 22 tasks；
- extension：136 pairs / 114 parents / 15 runs / 10 tasks。

审计不读 code、observation、pair orientation、gap、first-960 或 numeric outcome magnitude；只读取 grade 是否
finite 这一 availability bit。GPU=0，API=0。

## 通过项与失败边界

所有 3,252 parents 均通过 endpoint fidelity、finite-set declaration、run/task/parent context、source-size
一致性与 parent metadata 完整性。所有发布端点覆盖全部 finite retained direct children，所以发布 pair graph 本身
没有漏掉已保留且可评分的兄弟。

未通过的是 source choice-set retention：

| role | source-complete parents | all parents | incomplete parents | parent-equal mean retention | source size>5 |
|---|---:|---:|---:|---:|---:|
| train | 1,628 | 2,293 | 665 | 0.8885485280818947 | 10 |
| frozen | 651 | 845 | 194 | 0.9140433925049315 | 0 |
| extension | 103 | 114 | 11 | 0.9678362573099415 | 0 |

这里的 retention 定义为 retained card children / `n_siblings+1`。它证明当前文件是有限标签过滤后的片段；它
本身不识别缺失 child 是执行失败、评分失败、剪枝、序列化遗漏还是别的机制。

## 独立复核与安全

- focused：`11 passed in 0.21s`；
- full `phase1/tests`：`286 passed in 24.95s`；
- producer elapsed：16.28 s；verifier elapsed：16.56 s；
- input credential-shaped file hits：0；output hits：0；
- verifier receipt：`VERIFIED_RAW_CHOICE_SET_COMPLETENESS_AUDIT`；
- producer summary SHA-256：`a9925bdb8be7a9ef49858a77ccbd81c6fc1f03839dd66eecef62ca5770c9af8f`；
- producer per-parent CSV SHA-256：`75c02200d1f9b8d87614762a9f2b71ba3c678d598ff28bc237c8a46a4bc36d03`。

正式成功产物保留在
`/research/d7/spc/yzyang4/raw-choice-audit-v11-6610618-a2`。第一次 `a1` 因真实 release pair schema 不带
`run_id` 而在结果前 fail-closed；失败目录未覆盖。`a2` 的两套实现均从 endpoint physical-run provenance 独立
推导 run，并由新增回归测试覆盖该 schema。

## 论文边界

旧报告中的 `choice-set-faithful` 与“完整 source choice set”统一撤回。现有结果仍可用于 published labeled
fragment 内的 parent-equal/pair risk，但不能无条件外推到 agent 当时面对的完整 opportunity set。下一步只允许做
outcome-blind source identity/status recovery 与 missingness audit；不能靠更换模型或阈值掩盖该边界。
