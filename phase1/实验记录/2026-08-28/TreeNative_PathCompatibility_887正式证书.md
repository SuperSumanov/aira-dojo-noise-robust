# Tree-native / path-compatible 双视图：887 正式证书

## 正式裁决

结果前协议 `tree-native-path-compatibility-contract-v1` 在固定 snapshot `887491a...` 上分类为
`VERIFIED_LOSSLESS_TREE_NATIVE_PATH_COMPATIBILITY`。这把上一轮“trajectory linearization 会材料性重加权”从诊断
推进到一个机器可验证的 remedy：canonical view 每条 observed edge 只计一次；path view 仍枚举全部 root-to-leaf
trajectories，但每个 edge occurrence 携带精确 `1/m_e` 质量。

正式复算得到：

- 11,906 eligible endpoints；1,011 observed fragments；10,895 canonical observed edges；
- 3,599 path records；26,107 edge occurrences；15,212 duplicate occurrences；
- 142 个 single-node fragments/paths 被保留，且贡献 0 个 edge occurrences；
- 8,307 个 observed child groups，其中 2,565 个有至少两个 observed children，最大 group size=3；
- 精确有理数逐 edge 复算后，每条 edge 的质量误差上界为 `0/1`，总质量为 `10895/1`；
- task=34、physical run=435、depth cluster=37 三层聚合均逐项精确恢复 canonical unique-edge counts。

所有 verification gates 通过。正式 producer A/B、独立 verifier A/B 和第二 fresh-worktree postflight 均逐字节
一致；focused/full=`31/1314 passed`，full 有 47 warnings。formal/postflight manifest SHA-256 分别为
`342eefd91090229aa056eadc8586c364e7349e8e34cc8d7f76c9f28bd7a66f2e` 与
`073b1bdba76bda7a8de508de7ff1292e6594be05732d9a0f622d9d155e27fc1a`。forbidden-open、credential
filename/content=`0/0/0`；GPU/API/model-fit/base-update=`0/0/0/0`。

## 论文主张的增量

可写的正面主张变为两段闭环：

1. 在真实 MLE-agent observed forest 上，root-to-leaf linearization 会材料性改变 task/run empirical weights；
2. 一个 tree-native canonical release 可以同时提供 legacy path compatibility，并由固定 inverse-multiplicity ledger
   精确恢复 canonical edge measure。

第二段不是新学习算法，也不把初等 `1/m_e` 冒充数学 novelty。它的价值是把 benchmark 表示选择、physical-run
provenance、消费者兼容性和 estimand firewall 做成可执行、可独立复验的 release contract，而不只是在文中提醒
“注意 shared prefixes”。

## 不能越过的边界

- 协议是在上游 materiality 结果已知后冻结，因此 remedy 本身不是独立 replication。
- observed fragments 不等于 complete source trees；observed child groups 不等于已证完整的 source choice sets。
- 当前 435/960、closure=false；最终 first-960+closure 后仍须按相同合同重签证书。
- 没有读取 prospective label/outcome/prediction，没有 predictor effect、accuracy 或 search utility 结论。
- task→parent→pair estimand panel 继续控制 predictor benchmark；path weighting 不能用于改变或 rescue primary。

## 失败史

第一次 launcher 在 worktree 创建前因远端 remote alias 写成 `myfork` 而失败；实际 alias 为 `fork`。失败 manifest
SHA-256=`910e11c71d4e0fefd300d132d9d91b40938b21a86fde3a58ece7d22bd11dc9f2`。修正轮只改 launcher remote
名称，协议、实现 commit、snapshot、计权规则和 classification 均未改变。

结果包：`phase1/results/tree_native_path_compatibility_887_20260828_cdc90e4/`。
