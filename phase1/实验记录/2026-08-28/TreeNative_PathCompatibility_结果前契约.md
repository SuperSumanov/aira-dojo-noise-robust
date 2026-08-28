# Tree-native canonical view 与 path compatibility view：结果前契约

时间：2026-08-28
状态：`OUTCOME_BLIND_CONTRACT_FROZEN_BEFORE_COMPATIBILITY_CERTIFICATE`

## 为什么做

上游 887 快照审计已经证明，把 observed forest 枚举成所有 root-to-leaf paths 会把 10,895 条唯一 edge
扩成 26,107 个 edge occurrences，并实质改变 task/run 的经验权重。这个结论只诊断了问题；本轮把它转成一个
可执行、可逆且不破坏路径型消费者的发布契约。

## 固定设计

发布层保留两种并列视图：

1. tree-native canonical view：node、observed edge、fragment 与 observed sibling group；每条 observed edge
   的 canonical mass 固定为 1。
2. path compatibility view：枚举 observed fragment 的全部 root-to-leaf paths。每个 edge occurrence 同时携带
   `edge_multiplicity=m_e` 与精确质量 `1/m_e`。

因此，对任意 edge `e`，它在所有路径中的 occurrence 质量严格满足

`sum_{occurrence of e} 1/m_e = m_e * (1/m_e) = 1`。

正式 verifier 不使用浮点近似，而用精确有理数逐 edge 复算，并要求 task、physical run、depth 三个聚合层也逐项
恢复 canonical unique-edge counts。任何 edge 缺失、重复计数漂移、path 不连续、跨 run/task、upstream hash 漂移、
身份泄露或 A/B 不一致均 fail closed。

## 与现有资产的边界

- `export_status_certified_edges.py` 导出的是同一 decision parent 下的有效/无效比较关系，不是 search-tree lineage；
  本契约不替代它。
- `decision_corpus_audit.py` 已有 choice-set 聚合检查；本契约只提供 observed sibling grouping，不把不完整 fragment
  冒充 complete source choice set。
- `decision_predictor_estimand_panel_v1.json` 的 task→parent→pair headline 继续是预测 benchmark 的权威 estimand。
  inverse-multiplicity 只解决 path 表示导致的 edge 经验测度漂移，不能用于改变或 rescue predictor primary。

## 预先披露与 novelty 边界

本轮在上游 linearization materiality 结果已知后设计，因此是 remedy 的前瞻实现验证，不是第二个独立发现。
`1/m_e` 恒等式本身是初等计权，不声称算法 novelty。可守的贡献是：把真实 MLE-agent observed forest、physical-run
provenance、路径兼容性和 benchmark estimand 做成一个机器可验证、失败即关闭的双视图发布合同。

first-960 尚未闭合。真实快照只允许输出无身份 aggregate certificate；node ID、代码、逐 edge/path 行和任何
prospective label/outcome/prediction 在 closure 与 release review 前均不得落盘。

## 固定绑定

- snapshot：`887491a021d75d889c00a5af672a11b8b06e249d98e84fd91288534080f62697`
- upstream linearization receipt SHA-256：
  `642e9fd793950d4dfd082669df164be0781bd13847f35d6483ebd8611a136ea8`
- predictor estimand panel SHA-256：
  `4f394d0e0437992eb9d3e5f3aa56f83df86ffcbda68a752ebada4e306bf7adea`
- 完整机器协议：`phase1/tree_native_path_compatibility_contract_v1.json`
- 机器协议 SHA-256：`319906f0dc0525ecbc2455a5d468d5fe9e3522405455657d29f0dd5accf54511`

## 资源与安全

本轮只做 CPU 结构复算与 synthetic tests；GPU/API/model fit/base LLM update 均为 0。不会打开学长 raw archive，
不会读取 prospective truth、prediction、accuracy 或 search utility。
