# Tree-native / path-compatible 双视图正式证书

固定 snapshot：`887491a021d75d889c00a5af672a11b8b06e249d98e84fd91288534080f62697`

结果前协议 commit：`0deb5b6e9161547bff7c2ec3566a90c5ab324fad`

正式实现 commit：`cdc90e472eb57189a939187399d6b5fb5ec9a5c1`

分类：`VERIFIED_LOSSLESS_TREE_NATIVE_PATH_COMPATIBILITY`

## 结论

在同一 outcome-blind observed forest 上，canonical tree-native view 保留 10,895 条唯一 child→parent edge；
path compatibility view 保留 3,599 条 root-to-leaf paths 和 26,107 个 edge occurrences。每个 occurrence 使用
冻结的精确质量 `1 / edge_multiplicity` 后，逐 edge 的质量严格恢复为 1，总质量严格恢复为
`10895 / 1`。task、435 个 physical runs 与 37 个 depth clusters 的聚合质量也全部逐项精确恢复。

这使“保留树原生 benchmark estimand”与“兼容只消费 trajectories 的工具”可以同时成立；未经逆 multiplicity
修正的 path-frequency 统计仍必须单列为 compatibility sensitivity，不能冒充 canonical edge empirical measure。

额外结构盘点为 1,011 个 observed fragments、8,307 个至少含一个 observed child 的 parent groups，其中
2,565 个含至少两个 observed children，最大 observed child group size 为 3。它们只能称 observed sibling
groups，不能据此宣称 complete source choice sets。

## 边界

- 这是上游 linearization materiality 结果之后冻结的 remedy 验证，不是第二个独立发现。
- `1/m` 恒等式本身不是算法 novelty；贡献是与 MLE-agent physical-run provenance、双视图 schema、estimand
  firewall 和 fail-closed verifier 绑定的可执行发布机制。
- 当前仍为 435/960、closure=false。未读取 prospective truth/prediction，未计算 predictor accuracy、effect 或
  search utility，也未发布 node ID、代码或逐路径行。
- 现有 `decision_predictor_estimand_panel_v1.json` 继续控制 task→parent→pair headline；本证书不能 rescue
  任何 predictor primary。

## 复验与失败史

- focused：31 passed；全套：1,314 passed、47 warnings。
- formal producer A/B、non-importing verifier A/B 分别逐字节一致。
- 第二个 fresh detached worktree 的 verifier A/B 与 formal independent verifier 逐字节一致。
- formal/postflight manifest 在远端与传输后均验证通过；forbidden-open、credential filename/content 均为 0。
- 首次 launcher 因把远端 Git remote 写成 `myfork`（实际为 `fork`）而在 worktree 和任何科学输入读取前停止；
  失败现场保存在 `failed_launcher_preworktree/`。成功重跑只修正 remote 名称，未改协议、人口或计权规则。

机器绑定见 `source_bindings.json`；正式与独立收据分别见 `formal/`、`postflight/`。
