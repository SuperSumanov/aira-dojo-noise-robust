# Component-clean 数据学习曲线 v1：结果前冻结

日期：2026-08-23。状态：`PREREGISTERED_RETROSPECTIVE_DEV_ONLY_NOT_RUN`。本实验服务当前 clean critic scaling 与学长
继续生产 runs 的决策，不恢复旧 HCE/probe/多保真路线，也不读取 outer frozen test、prospective vault 或
score-channel truth。

## 1. 问题与已知信息

问题固定为：在 outer-train 内，增加互不跨 split 的 pair-graph components，是否让同一个 char-TFIDF critic 在
component-clean dev 上改善？它只能回答“继续增加独立训练支持是否有经验价值”，不能替代 Qwen scaling、future
confirmation 或 live-search utility。

冻结前已经知道 full-train dev micro accuracy=`0.604355716878403`、task macro=
`0.5643959081886237`；因此本实验是 retrospective dev diagnostic，不得包装成未触碰确认。冻结前没有计算
25%/50%/75% 中间点、proper-score curve 或 smallest-to-full contrast。

## 2. 结构预飞与固定矩阵

只允许三个既有输入：Cards SHA-256=`5fd24c8e545a67e1048f8a67b23bcb64605b9ad584a4fbaa44aa1b1f1b6e1afb`、
component train SHA-256=`0ec49d76a896accf8e85a2556ca7ed12b9379b1867247d99c6be5e4c83bea98e`、dev
SHA-256=`3b3fb53f84277e935c66d3b3d1646d7a7d33624fb916e3f9bcc15f689904cfa4`。test pair path 不进入 CLI。

结果盲结构审计打印：train=`4,689 pairs / 28 tasks / 127 components`，最大任务 share=
`0.08871827681808488`；dev=`551 / 25 / 41`，最大任务 share=`0.147005444646098`。三种固定 hash seeds 为
`20260823/20260824/20260825`，fractions=`25/50/75/100%`。每个 seed 先按
`sha256(seed|task|component_id)` 给每个 train task 取一个 coverage-floor component，再按全局同一顺序增加 component，
直到达到 `ceil(fraction × 4,689)` pairs；这保证 nested、component 不拆分、每个 train task 始终有支持。

结构预飞的 realized pair fractions 为：

- seed 20260823：`0.262316/0.523353/0.761570/1.0`；
- seed 20260824：`0.254639/0.526978/0.751333/1.0`；
- seed 20260825：`0.297505/0.507784/0.751973/1.0`。

最大 overshoot 固定≤0.05。模型逐字节复用同池 baseline：20k code prefix、char_wb 3--5 gram、30k features、
min_df=3、sublinear TF-IDF、对称 pair differences、LR `C=0.5/lbfgs/max_iter=1500`；margin 不含 intercept。

## 3. 事前 estimand 与裁决

Primary 为每 task 先平均的 dev binary log loss；secondary 为 task-macro pair accuracy，tie 固定记 0.5。完整报告
pair-micro、逐 task、逐 fraction/selection-seed 和 realized components/runs/pairs。

strong proper-score positive 要求同时满足：四点 seed-mean log-loss 单调不升；三个 seed 的 full−quarter 均<0；
full−mean-quarter≤−0.01；20,000 次 task bootstrap（seed 20260826）CI 上界<0；全部 leave-one-task-out 仍<0。
top-1 positive 独立要求 accuracy 曲线单调不降、三个 seed full−quarter 均>0、点差≥+0.02、task-bootstrap CI
下界>0、全部 LOTO>0。两类门分开报告，任何一个失败都不得改 fraction、seed、task pool、TF-IDF 或阈值追救。

## 4. 资源、安全与主张边界

预计 producer 与不 import producer 的 verifier 各做 10 个唯一 CPU fits（100% 三 seed 同一 subset 缓存一次），
顺序单线程，约 1.5--2.5 小时，峰值约 4GB；GPU/API/base-LLM update=`0/0/0`。Cards 整包 JSON 会被解析，但程序
只引用并保留 id/code/run/task/config 投影；raw-grade 字段不引用、不保留、不参与选择/拟合。stdout、自报分、
runtime、test prediction 和 prospective truth 禁用。

学习曲线、reward-model data scaling 与 NAS predictor sample efficiency 均不是方法 novelty。若通过，只能写为本
MLE-agent corpus 上的 outer-train-only 数据生产证据；若失败，只能说明该固定 cheap critic/dev 上未见增益，不外推
到未来 neural critic。机器协议为 `phase1/critic_component_data_learning_curve_v1.json`；SHA-256=
`a7c6bca3e430580c4a178d89694e90658a5496b8a1775a967221b7dc32d3c9da`。

结果读取前的实现验证为远端合成 8/8，覆盖 protocol hash/closed input surface、launcher 不含 test/GPU、component
nesting、正负控、数值篡改、独立 verifier 不 import producer、Python/JSON literal 混用和 overwrite fail-closed。
本机因缺 SciPy 在 collection 阶段
停止（0 tests executed）；第一版远端 wrapper 又因在 `env_setup.sh` 前开启 nounset 而退出。两次都发生在真实输入拟合
前，不计 code PASS。新增 launcher 测试的第一次沙箱又因 wrapper 漏复制 launcher 文件得到 1 fail / 7 pass；补齐沙箱
输入后从头得到 8/8。远端环境没有 Ruff，未把 lint 冒充为通过。

scientific commit `18518fd54a0d9b2cde6fb951d0bf7c2fe4e1ae79` 的第一次 formal launcher 在 fresh worktree
和 input SHA 后、任何模型 fit 前 fail closed：wrapper 没有 `cd` 到 repo，故相对路径 `py_compile` 报文件不存在。
失败 root `critic-component-data-curve/18518fd-v1` 原样保留；其中不得有 producer/verification/decision artifact。
唯一修复是在 tests/effect 前增加 `cd "$repo"`，不改 contract、input、fraction、seed、model、estimand 或 gate；必须
新 commit、新输出 root 从头运行。
