# Tree linearization estimand sensitivity 正式后验解析

固定 snapshot：`887491a021d75d889c00a5af672a11b8b06e249d98e84fd91288534080f62697`

后验声明 commit：`d8214ce0a1aecdc184ef6909fc2542c3e1506719`

正式实现 commit：`5a96d92e0d638af6dba6f65c5f4a96e1ab37e9b4`

分类：`VERIFIED_EXACT_EDGE_MEASURE_SENSITIVITY_COROLLARY`

## 结论

固定 observed forest 含 10,895 条 canonical unique edges；root-to-leaf path view 含 26,107 个 edge
occurrences。两种经验 edge measures 的精确 total variation 为
`109845598 / 284435765 = 0.38618771447395162`。

达到该 sharp bound 的 multiplicity-defined edge indicator 由 2,286 条 unique edges 构成：它在 canonical
measure 下占 `2286/10895 = 0.20982101881597062`，在 path-frequency measure 下占
`15560/26107 = 0.59600873328992221`，差值恰为上述 TV。这说明 path linearization 不只是“产生重复行”，
而是能对任意 `[0,1]` edge-level bounded statistic 造成至多且可达到的 38.6188 个百分点经验期望偏移。

描述性 inverse-HHI diversity 从 canonical 的 10,895 降至
`681575449/296317 = 2300.1564169453659`，保留率为
`681575449/3228373715 = 0.2111203686962245`；最大单 edge 质量膨胀为
`1568880/26107 = 60.094227601792625`。每个 occurrence 使用 `1/m_e` 后，修正 measure 对 canonical 的
精确 TV 为 `0/1`。

## 边界

- 数值在声明前已被探索性看见；这是已发布 aggregate 的确定性后验解析推论，不是预注册独立发现。
- sharp TV envelope 只保证某个 edge indicator 达界；不声称 predictor accuracy 或自然任务指标实际移动 38.6 个点。
- inverse-HHI 只称描述性多样性，不称统计有效样本量。
- 这是 benchmark estimand/release-contract 证据，不是新学习算法或 `1/m_e` 数学 novelty。
- 当前仍为 435/960、closure=false；未读取 prospective truth/prediction，未计算 accuracy、effect 或 search utility。

## 复验

- focused：27 passed；全套：1,330 passed、47 warnings；postflight focused：16 passed。
- formal producer A/B 与 non-importing verifier A/B 分别逐字节一致。
- 第二 fresh detached worktree 的 verifier A/B 与 formal verifier 逐字节一致。
- formal/postflight manifests 在远端与传输后全部验证通过。
- forbidden-open、credential filename/content 均为 0；GPU/API/model-fit/base-update=`0/0/0/0`。

机器绑定见 `source_bindings.json`；正式与独立收据分别见 `formal/`、`postflight/`。
