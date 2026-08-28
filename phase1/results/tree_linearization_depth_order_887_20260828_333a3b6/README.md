# Tree linearization depth-order 正式后验解析

固定 snapshot：`887491a021d75d889c00a5af672a11b8b06e249d98e84fd91288534080f62697`

正式实现 commit：`333a3b66ca5399dcf87e586be1339423917d1264`

分类：`VERIFIED_SHALLOW_DEPTH_STOCHASTIC_ORDER_COROLLARY`

## 结论

固定 outcome-blind observed forest 上，canonical unique-edge view 的平均 logged depth 为
`89213/10895 = 8.1884350619550261`；root-to-leaf path-frequency view 为
`183993/26107 = 7.0476500555406592`。path-minus-canonical shift 为
`-324480056/284435765 = -1.1407850064143656`，均值比为 `0.86068339093086754`。

path CDF 在全部 observed depths 上均不低于 canonical CDF，非零 PMF 差恰交叉一次；最大 CDF gap 在
depth 5，且与 depth-distribution TV 同为 `27231696/284435765 = 0.095739352609191045`。
nearest-rank median/p90 从 `7/15` 变为 `6/13`。因此，枚举 root-to-leaf paths 会系统性把 logged
edge-depth 经验分布推向浅层。

## 边界

- 均值、CDF 顺序和交叉数在声明前已被探索性看见；这是已发布 aggregate 的确定性后验解析，不是预注册发现。
- logged depth 不等于语义重要性、难度或因果贡献。
- 不申 shared-prefix/root bias/tree-aware weighting 的通用 novelty；也没有测 predictor effect 或 search utility。
- 当前仍未达到 first-960 closure，跨 snapshot 泛化尚未建立。

## 复验与安全

- focused：63 passed；全套：1,369 passed、47 warnings。
- producer A/B 与不 import producer 的 verifier A/B 分别逐字节一致；formal manifest 传输后复验通过。
- forbidden-open、credential filename/content 均为 0；GPU/API/model-fit/base-update=`0/0/0/0`。
- 未读取 prospective label/grade/outcome/prediction，也未输出 task/run/card/edge identity。

机器绑定见 `source_bindings.json`；正式收据与独立复验见 `formal/`。
