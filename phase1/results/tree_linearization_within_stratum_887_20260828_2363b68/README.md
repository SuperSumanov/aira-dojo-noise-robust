# Within-stratum decomposition 正式失败收据

固定 snapshot：`887491a021d75d889c00a5af672a11b8b06e249d98e84fd91288534080f62697`

正式实现 commit：`2363b687ea503ced5945208766bb25f1baaeffed`

正式分类：`WITHIN_STRATUM_DECOMPOSITION_GATE_FAIL`

## 裁决

必须保留失败，且不得在同一 snapshot 上补门救回。失败来自一个结果前硬完整性门：上游收据保存的 task
marginal decimal 是 `0.1603376038171571`，而 exact fraction `45605749/284435765` 按本协议固定的
`.17g` 规则重算为 `0.16033760381715709`。两者是同一个 JSON 浮点值的不同字符串表示，但协议要求逐字
round-trip，因此正式分类只能失败。这是协议表示层缺陷，不是科学广度门失败。

## 仅作描述性的科学读数

- task canonical-standardized within-TV：`0.34286096272939481`；34 个 task 中 32 个达到
  conditional-TV reference 0.10，最大匿名贡献占比 `0.35387441357728333`。
- physical-run canonical-standardized within-TV：`0.30840042995574296`；434 个可条件化 run 中 356 个达到
  reference，最大匿名贡献占比 `0.10868797144906397`。
- 两个预注册 scientific axis gates 均通过，但不能覆盖 hard-integrity failure。

这些值支持“composition 并不能解释全部 linearization shift”这一后续假设，却不是本 snapshot 的正式正结论。
下一次确认必须提前改用 exact rational 绑定，并只在首个未见稳定 snapshot 上运行。

## 复验与安全

- focused：49 passed；全套：1,355 passed、47 warnings。
- producer A/B 与不 import producer 的 verifier A/B 分别逐字节一致；formal manifest 传输后复验通过。
- forbidden-open、credential filename/content 均为 0。
- 未读取 prospective label/grade/outcome/prediction，未输出 identity/code/per-edge 值；
  GPU/API/model-fit/base-update=`0/0/0/0`。

机器绑定见 `source_bindings.json`，完整失败现场及收据见 `formal/`。
