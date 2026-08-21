# Decision-Corpus Evidence Index v5：执行前冻结

日期：2026-08-21。状态：`NOT RUN`。这是 0DG 已知结果之后的 deterministic release packaging，不伪装成
结果前科学检验。目标是逐字继承 v4 八项，再把 `source_decision_answerability` 作为第九个互不合并的 estimand
接入机器可核验合同。

## 固定输入与输出

- source v4 index normalized-LF SHA-256：
  `80450de3528fcaf2dc5edb5f54109ba30189f81e66c5715fbe755012d5de391b`；
- answerability `per_parent.csv`：3,252 data rows，SHA-256=
  `b2488d059ce4fafacc321e98fb4f4e82b5f0b4d4abc86a413d9e6f80da0cb4d4`；
- answerability `per_task.csv`：23 data rows，SHA-256=
  `7c1669f101706efc76c0894c76f5abc382eb842401141b01037505404d168fb5`；
- summary / independent verifier / producer manifest normalized-LF SHA-256=
  `048f18cc...323026` / `05e4398e...c845e` / `67440527...de18`；
- 输出固定为 v5 index：保留 v4 entry 顺序，在 `status_certified_partial_order` 后插入
  `source_decision_answerability`，总计 9 个 entries。

新 entry 直接绑定两份 CSV 的 hash、精确 header、line count、data-row count 与等宽性，并绑定三份 JSON 的 hash
和声明式 assertions。builder 与独立 verifier 只能共同 import 无 I/O 的 schema；verifier 不 import builder。

## 固定边界

允许新增的是 source-level unique-winner answerability release claim。schema 必须显式禁止把它写成 predictor
accuracy、search utility、完整 numeric total order、prospective effect 或 logged comparisons；149 个
identity-unavailable parents 继续在全部 3,252 分母中保持 unanswered。旧八项 claim、artifact、assertion 与边界
不得改变，estimands 不得合并。

## 十三项 pre-flight

1. 方向：failure-aware Decision Corpus / D&B 发布合同，不恢复 HCE、TD、probe 或多保真。
2. 问题：0DG 能否成为第九个独立、机器可核验 estimand。
3. 输入：只读已提交 v4 index 与 0DG 正式产物，所有 SHA 固定。
4. 单位：两个 bound CSV、三个 asserted JSON；不重新定义 parent scientific unit。
5. 已见结果：0DG 数值已经知道，本轮只验证封装，不作新效果推断。
6. 完整性：source v4 必须逐字节 hash 匹配，旧八项顺序与 membership 固定。
7. CSV：header、line/data-row count、row width 与 normalized hash 同时验证。
8. JSON：每个 artifact 必须有非空 dotted/exact-key assertions，并逐项复核。
9. 负控：claim drift、CSV binding drift、CSV header drift 均必须 fail closed。
10. 复现：builder×2、独立 verifier×2、完整 commit、逐字节 diff 与 SHA manifest。
11. 访问：不读 code/obs、grade/gap、raw archive、checkpoint、prospective outcome 或 first-960。
12. 资源：single-thread CPU；GPU=0、API=0、底座更新=0；预计完整回归小于 30 分钟。
13. 停止：任一 hash/header/row/assertion/旧 entry/秘密/worktree 门失败即保留失败目录，不追救科学 claim。

本地结果前 focused tests=`7 passed, 1 skipped`；skip 仅因正式 v5 checked-in index 尚未生成。
