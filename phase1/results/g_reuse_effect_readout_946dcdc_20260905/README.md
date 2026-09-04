# G-reuse效果读出统计核：结果前冻结回执

最终结果前代码commit=`946dcdca08dda0eca1e40fe1af022bc5fa9ec5b9`，git archive SHA-256=
`9b39e554b69abfd14d0a8bec2523744b29fa6e0d061e5a4f923608688a8b7896`。独立Linux根为
`/research/d7/spc/yzyang4/g-reuse-effect-readout/formal-946dcdc-v2`；10项合成层级/攻击测试通过，stderr为0。
协议与统计核SHA-256分别为
`3e82858a9b66e5deb9f96efb27968259823470106d86dc0b439b11c666bfb2d5`和
`2b66495684a9fce110eb436110802f04166250fd4c3210d2aceb9780782689d7`。

这次关闭的是分析自由度，不是效果结果：

- 主估计量固定为任务内pair-micro、三seed平均、任务等权；
- 固定20,000次task-cluster percentile bootstrap及type-7分位；
- parent/run敏感性用各5,000次任务外层、任务内cluster内层的paired bootstrap，不能救主门；
- TF-IDF同池单预测从每个full seed分别相减；tie固定0.5 credit；
- 若L1显著胜Lbudget，full必须再显著胜L1，否则只能解释为避免local重复训练；
- 只有deployment与L1层级先通过才计算full-vs-hash，后级不能救前级；
- 单任务35%门固定为“一个任务的正向未归一化pair×seed正确数增益/所有正向任务增益”。

当前模块只是统计核，明确不会打开label vault或认证checkpoint/prediction escrow。正式使用前仍需独立实现复算器和
outcome-aware caller；同producer来源、split、G0、checkpoint/manifest及GPU批准的阻断全部不变。synthetic test、
测试数量或readiness均不能称critic accuracy/scaling/正效果。GPU/API/model fit/protected read均为0。
