# Decision Semantic Mixture v2：正式裁决

日期：2026-08-21。source commit：`c5d2cf72a9e0e7aae2aa394532aca16279ad9047`；senior data commit：
`baf6bddefe62b769b2fab699ff5805dd627dc69f`。正式状态：`DISCOVERY_NO_UNLOCK`。

## 1. 一句话结论

固定的 Draft/Improve semantic mix 给出方向良好的小幅点增益，但跨任务不稳定，六个预注册效果门只通过四个；
因此不解锁 future confirmation，不运行结果揭晓前冻结的 parent-weighting 消歧，也不换 mix 权重、任务或子集追救。

## 2. Headline 与六个门

| 指标 | pooled | semantic mix | delta / CI | 门 |
|---|---:|---:|---:|---|
| merged micro | 0.5832438238453276 | 0.6004296455424275 | +0.017185821697099923 | 描述性 |
| merged task macro | 0.5743054636618959 | 0.5845981187534576 | +0.010292655091561631 | PASS `>=0.010` |
| task bootstrap | — | — | [-0.020432976223223577, 0.04351597259972664] | **FAIL** lower>0 |
| parent-clustered micro | — | — | [-0.003174687247780468, 0.037353489626701986] | secondary |
| Draft micro delta | — | — | +0.019108280254777066 | PASS `>=-0.005` |
| Improve micro delta | — | — | +0.01620745542949753 | PASS `>=-0.005` |

supported tasks 数为 23，数量门通过；但只有 10 positive / 9 zero / 4 negative，严格正比例
`0.43478260869565216`，低于 0.60，故第二个稳定性门失败。supported-task delta 从
`random-acts-of-pizza` 的 -0.1333333333333333 到 `nomad2018-predict-transparent-conductors` 的 +0.1875，
不是少量打印误差。pure specialist 的 merged task macro 只有 `0.5585785965631349`，也没有证据把 fixed mix 的
小增益解释成普遍的 specialist 优势。

## 3. 完整性与复现

- exact-config 输入固定为 5,240 train / 931 test；train/test endpoint 与 physical-run overlap 均为 0；
- producer×2 逐字节一致；不 import producer 的 full-refit verifier×2 逐字节一致，全部 19 个 aggregate checks
  为 true；
- focused tests 10/10；三 heads 均收敛；30,000 train-only TF-IDF features；ties=0；
- 四进程顺序总 wall 1,184.46 秒，最大 RSS 3,567,940 kB；GPU/API/checkpoint/base-LLM update/prospective
  outcome access 全为 0；
- artifact filename/content credential matches 均为 0，SHA manifest 全过。

完整远端包 bytes=`10535`，SHA-256=
`d96e747fcbd12c8e200b06eda644401cec0e18a1033e8ad0f2afee56aa591ed3`。Git 聚合证据位于
`phase1/results/decision_semantic_mixture_v2_20260821_c5d2cf7/`。

## 4. 结果揭晓前发现的机制混杂与停止

在读取本轮结果前已提交 commit `9a5b163...`：Draft 训练的 3,196 pairs 只来自 135 个 `(task,parent)`，
Improve 的 2,044 pairs 来自 1,576 个 parent，平均 pairs/parent 相差 `18.253591360440673` 倍。条件预注册规定：
只有本轮 status 精确为 `DISCOVERY_UNLOCK_FUTURE_CONFIRMATION` 才运行 raw-pair × parent-equal 的 2×2 消歧。
当前触发条件失败，因此正式状态是 `NOT_RUN_PARENT_WEIGHT_DISAMBIGUATION_NOT_TRIGGERED`；运行它来寻找另一组正数
会违反停止规则。

另有一项诚实的工程勘误：preflight line 06 写了 atomic output，但 producer 实际是直接写入 fresh directory，
没有 staging+rename。因为两份完整目录、manifest、双重重拟合和 SHA 全过，这不改变科学裁决；原回执不篡改，
勘误单独归档。

## 5. 对路线的影响

semantic routing 作为当前旧 test 上的正方法候选关闭。点增益可以在 benchmark appendix 中作为描述性结果完整
报告，但不得称稳健提升、不得作为 future arm、不得挑 Nomad 等正任务。APLOT、PaTaRM、correlated RM 与 Themis
又分别覆盖 adaptive margin、pairwise→pointwise/task-adaptive、higher-order choice context 与 code-RM scaling，
所以也不转向这些已被直接覆盖的 objective 追新方法。

论文主线保持 Decision Corpus + Predictor Benchmark + first-960/closure：真实 sibling comparison distribution、
run-clean/exact-config、gap/noise/missingness/cost 与时间外确认。模型支持线上，下一项真正有价值的是学长建议的
direct-decision Qwen scaling，但必须使用已交付的 clean dev/immutable frozen 协议；在给出精确模型×seed 矩阵和
总 GPU·时并获批前不提交。
