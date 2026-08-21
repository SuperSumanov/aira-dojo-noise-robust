# Source Choice Materialization S0：正式裁决

日期：2026-08-21。控制 commit：`efbda542e69484bc93b0b36fcda10d37712cc674`。正式状态：
`SOURCE_CHOICE_MATERIALIZATION_SUPPORT_FEASIBLE`。

## 正结果

对固定 3,252 个 source parents，只连接 SHA-pinned answerability census 与旧正式流程的纯结构 construction
census。3,001 个 status-certified winners 中有 3,000 个具备完整 candidate-code 引用，coverage=
`0.9996667777407531`；相对全部 parents 的 materializable rate=`0.922509225092251`。

train 的 2,109 个、frozen 的 778 个 certified winners 全部可物化；extension 为 113/114。总计 8,027 个
candidate slots，3,000 组中 1,521 组 source size≥3，variable-arity share=`0.507`。23 个任务均有覆盖，20 个任务
至少 20 组；dominant-task share=`0.20066666666666666`。train/frozen parent 与 physical-run hash overlap 均为 0。
全部 13 个预冻结材料门通过，正式授权 S1。

## 唯一缺口与边界

唯一 code-reference-incomplete certified winner 位于 extension，不进入 S1；不降低门、不插补，也不切换分母。
本轮没有读取 code bytes、numeric grade、gap、旧 hurdle 模型结果、prospective outcome、raw archive/journal 或
first-960。完整性来自既有正式 provenance 链，所以当前准确措辞是 code-reference complete；S1 物化时仍须重新
校验每个 candidate 的 code hash 与 parent/run/task context。

因此该结果是 D&B release 的材料正资产，不是 predictor/search utility 或 listwise 方法正结果；不允许声称整个
v11 是完整 choice-set dataset、算法 novelty 或 prospective effect。传递推断关系不写成 logged comparisons。

## 复现与审计

- producer×2、独立 verifier×2 逐字节一致，独立 verifier 不 import producer；
- summary SHA-256=`5ab474bd061f7f8845a19d1cefd5023fc9e2a0e5a1b45d4d93842fb62759c303`；
- focused=`7 passed`，完整 phase tests=`686 passed, 25 warnings`；
- forbidden scientific path、secret filename/content、worktree drift、正式可写文件均为 0；
- GPU=0、API=0、base LLM update=0；
- 本地证据：`phase1/results/source_choice_materialization_support_v1_20260821_efbda54/`；
- 远端只读证据：
  `/research/d7/spc/yzyang4/source-choice-materialization-support/efbda54-v1`。

## 后续

S1 只能构造 answerability-conditioned train inputs 与 sealed frozen evaluator，并逐条重验物化数据；在 S1
独立验证完成前，不训练新模型、不触碰 frozen 结果、不提交 GPU，也不把材料支持写成方法收益。
