# Path-record split 共享前缀 crossing 正式审计

固定 snapshot：`887491a021d75d889c00a5af672a11b8b06e249d98e84fd91288534080f62697`

正式实现 commit：`aec63564cb4a347a3bb6c61b38ae30850d1d755f`

分类：`RUN_ONLY_BROAD_PATH_SPLIT_PREFIX_LEAKAGE_RISK`

## 结论

固定 observed forest 产生 3,599 条 root-to-leaf path records。若把 paths 当独立样本做固定大小
80/10/10 split（2,879/360/360），精确组合期望为：

- 约 `1291.4019805907681` 条 canonical edges 同时跨 train 与 test；
- test unique canonical edges 中预计 `0.63841797380705656` 已在 train 出现；
- test path-edge occurrences 中预计 `0.71072159960645032` 对应的 canonical edge 已在 train 出现。

新冻结的匿名 profile 表明该风险在 physical-run 轴上广泛：435 个 run 中 339 个达到 contamination-ratio
reference 0.25，最大单 run 贡献占比 `0.14093310549689442`，通过 0.20 上限。task 轴覆盖同样广
（34 个 task 中 31 个达到 reference），但最大单 task 贡献占比 `0.45161151698862051`，超过预注册 0.40
上限。因此正式裁决只能是 run-only broad，不能宣称双轴广泛。

按 fragment 或 physical run 分组切分时，exact canonical-edge crossing 均严格为 0，这是发布层 remedy control。

## 边界

- 全局 crossing 数值是已发布 multiplicity histogram 的后验确定性推论；只有匿名 task/run breadth 是冻结后的新读数。
- 未执行实际随机 split、模型训练或 predictor 测试，不能外推真实 accuracy inflation。
- shared prefix、grouped split 与 tree-aware weighting 均已有先例；可守贡献是 MLE-agent observed forest 的精确量化、
  物理 run 广度和可执行 tree-native release contract。
- 不证明语义近重复缺失、完整 source choice set 或跨 snapshot 泛化。

## 复验与安全

- focused：90 passed；全套：1,391 passed、47 warnings。
- producer A/B 与不 import producer 的 verifier A/B 分别逐字节一致；formal manifest 传输后复验通过。
- forbidden-open、credential filename/content 均为 0；GPU/API/model-fit/base-update=`0/0/0/0`。
- 未读取 prospective label/grade/outcome/prediction，也未输出 identity/code/per-path 值。

机器绑定见 `source_bindings.json`；正式收据与独立复验见 `formal/`。
