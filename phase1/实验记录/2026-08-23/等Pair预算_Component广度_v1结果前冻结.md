# 等 pair 预算下的 component/run 广度：v1 结果前冻结

## 目的

学长正在继续生产约 60 runs/day。仅证明“pair 更多时 predictor 更好”不能区分新增独立 runs 与同一 run/component
内增加相关 pair。这里固定每个 task 的训练 pair 数，只改变这些 pair 分布在多少个独立 logged comparison
components / physical runs 上，直接检验数据生产的独立性是否有边际价值。

本实验只服务 Decision Corpus / clean critic 的数据设计，不恢复旧 HCE、probe、多保真、TD/RL 或 selector 方法线。

## 结果盲结构可行性

在读取任何 arm dev metric 前，structure-only 程序只访问 train/dev pair identity、component、task，以及 Cards 的
`id→physical run` 投影；selection hash 使用
`task|parent|lexicographically_sorted_endpoint_ids`，不使用 better/worse 方向。输入固定为：

- train：4,689 pairs / 28 tasks / 127 components；
- dev：551 pairs / 25 tasks；
- 每 task 取 `ceil(0.5 × train pairs)`，故每 seed、每 arm 均为 2,353 pairs；
- seeds：`20260823, 20260824, 20260825`；
- feasibility JSON SHA-256：
  `773db70feb0872039af326fc19121254db26d106bb44e5081fc4f54b99a608b6`。

结构门结果固定如下，之后不得更改 50% 预算、seed 或 arm：

| seed | broad components / runs | concentrated components / runs | random components / runs |
|---:|---:|---:|---:|
| 20260823 | 127 / 429 | 53 / 224 | 125 / 426 |
| 20260824 | 127 / 429 | 53 / 223 | 123 / 426 |
| 20260825 | 127 / 429 | 53 / 224 | 123 / 425 |

三 seed 的 broad−concentrated 均为 +74 components，physical runs 为 +205/+206/+205；25 个 dev tasks
中 24 个在三 seed 都有 component 广度差异。所有 arm 的逐 task pair budget hash 必须完全相同，否则在模型 fit
前关闭。

## 三个冻结 arm

- `broad`：每 task 先按 orientation-independent hash 从尽可能多的 components 各取一个 pair，再 hash-fill 到
  精确 pair 预算；它最大化 component 广度。
- `concentrated`：每 task 按 component pair 数降序、hash 破同分，依次取 pair 到精确预算；它最小化
  component 数。
- `random`：每 task 对全部 pair 做 orientation-independent hash prefix；只作描述性 sanity baseline，不进入
  broad−concentrated primary 解锁门。

## 固定模型与推断

三个 arm 完全复用同一个 decision-time 模型：20,000-character code prefix，`char_wb` 3--5 gram TF-IDF，
30,000 features，`min_df=3`，sublinear TF；mirrored pair differences；LR `C=0.5`、`lbfgs`、
`max_iter=1500`；pair margin 不含 intercept。TF-IDF 只 fit 当前 arm 的 train code，dev 仅 transform。

Primary 是全部 25 个 dev tasks（不是结果后挑选 24 个 informative tasks）的 task-macro binary log loss；secondary
是 tie-aware task-macro accuracy。先在每 task 内对三 seed 求平均 broad−concentrated，再做 20,000 次 task
bootstrap（seed `20260827`）与 leave-one-task-out。

proper-score 正门必须同时满足：

1. 三个 seed 的 task-macro `broad−concentrated log loss < 0`；
2. 全 task point effect `≤ -0.01`；
3. task-bootstrap 95% CI 上界 `< 0`；
4. 所有 LOTO effect `< 0`。

top-1 正门同理要求三 seed 全正、point `≥ +0.02`、CI 下界 `>0`、全部 LOTO `>0`。任一门失败不得用
random arm、subgroup、informative-only tasks、换 fraction/seed/model/threshold 来追救。

## 复现与边界

机器合同 SHA-256：
`1dc28d105922741d0c6a8263d9b2ebd2566d1a28de3dec1eb8f490116f7e6316`。正式链要求 producer×2、不同
`PYTHONHASHSEED` 逐字节一致，随后不 import producer 的 verifier×2 从 source 重新选择、重新拟合并逐行验证。
每个实现最多 9 次单线程 CPU fit；GPU/API/base-LLM update=`0/0/0`。

提交前，producer 与 verifier 在真实输入上分别只执行 source→structure 路径，均未调用 `fit_arm/refit` 或
`evaluate/decision`；两份 JSON 逐字节一致，共同 SHA-256=
`380a33b814527fd9bc3fdfc8f6f0bebba774076f7275850752e6e98e139f0c6b`。合成正/负控、orientation
invariance、篡改拒绝、独立 import 与 overwrite fail-closed 为 8/8；fresh no-smudge overlay 的完整
`phase1/tests` 为 874/874（33 warnings），凭据 filename/content 扫描 0/0。没有真实 arm effect 被读取。

即使通过，也只能写：在当前 retrospective MLE component-clean dev 上、等 task/pair 预算时，更独立的
component/run 广度改善固定廉价 critic。reward-model data scaling、group-aware splitting 与 data diversity 均已有
先例，因此不得写成 data scaling law、方法首创、frozen/future confirmation 或 search utility。它的价值是为本语料
生产和 D&B benchmark 提供可复核的采样设计证据。
