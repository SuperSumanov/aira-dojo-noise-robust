# Clean Direct-Decision：Draft 父上下文重叠的结果盲发现与复核计划

日期：2026-08-21。状态：`STRUCTURAL_DISCOVERY_PENDING_FORMAL_INDEPENDENT_REPRODUCTION`。本记录来自静态
信号 component-OOF 的模型运行前结构预检；发现与语义分层均未聚合 accuracy、margin、gap、score 或任何
prospective outcome。正在运行的 parent-closed OOF commit=`208e381...` 的 feature/model/统计门未因此改变。

## 1. 确定性结构发现

固定 component split 的 endpoint/run/pair 交集确实为 0，但此前未报告 ancestor parent。只按 `(task,parent)`
重新计集合得到：

| 比较 | shared parents | 左侧受影响 rows | 右侧受影响 rows |
|---|---:|---:|---:|
| train / dev | 8 | 139 | 29 |
| train / test | 62 | 1,684 | 208 |
| dev / test | 23 | 233 | 115 |
| outer train+dev / test | **80** | **1,917** | **305** |

80/80 shared parent IDs 都能在 Cards 中解析为真实 card；只计 endpoint physical run 时 outer-train/test overlap=0，
把 pair 的 parent card 所属 run 加入上下文后 overlap=80。两侧 endpoint exact-code SHA overlap 仍为 0。因此这不是
endpoint 重复或逐字节代码重复，而是 split unit 没有对祖先上下文闭包。

## 2. 该问题完全局限于 synthetic Draft

用结果前已锁定的 Draft/Improve identity manifests 分层后：

- train/dev/test 语义数分别为 Draft=`2902/294/314`、Improve=`1787/257/617`；
- 80 个 same-semantic shared parents 全部属于 Draft；Improve shared parents=`0`；
- test 中受影响的 305 rows 全为 Draft，即 305/314=`0.9713375796178344` 的 Draft test；
- dev 中受影响的 233 rows 全为 Draft，即 233/294=`0.7925170068027211` 的 Draft dev；
- test 全池受影响为 305/931=`0.3276047261009667`。

因此不能笼统写“整个 canonical sibling test 泄漏”。更准确的边界是：run-disjoint 足以隔离 Improve/canonical
raw sibling，但不足以隔离由跨-run construction 形成的 synthetic Draft；若目标是 unseen-parent transfer，Draft
必须以 parent-closed relational component 为 split unit。若部署目标本来允许复用同一 parent，则这些 rows 测的是
within-parent transfer，必须单列，不能和 parent-novel 泛化混成一个 headline。

## 3. 与已有模型结果的关系

0CJ 已见 static champion 在 Draft/Improve 的 micro 分别为 `0.6305732484076433` / `0.5251215559157212`；而
champion 又由 parent-overlap 很高的 dev 选择。结构重叠与 Draft 高点估计相符，但**尚不能据此证明因果**；模型未
显式读取 parent ID，可能通过共同祖先诱导的代码风格、task 或其他相关结构迁移。必须等待结果前已冻结的
parent-closed OOF，才能判断严格 parent isolation 后 code-derived signal 是否仍存在。

0CF 的 TF-IDF test Draft/Improve=`0.5796178343949044` / `0.5672609400324149`。因此结构发现要求把 Draft 数字
标作 parent-context-overlap extension；Improve 的 parent overlap=0，不能因 Draft 问题一并撤回。现阶段不重跑
已见 test、不改变 0CJ/0CF 数字，只收紧其解释。

## 4. 对 G0、future 与论文主张的约束

1. G0/future 的 primary 继续只允许 `canonical_raw_sibling`；该层本次 parent overlap=0。
2. `synthetic_cross_run_draft` 若进入 extension，必须同时报告 within-parent 与 parent-novel；确认性 split 必须先做
   parent closure，不能只写 endpoint-run-disjoint。
3. 旧 merged component test 不再能支持“完全 parent-context-independent”；只能作 retrospective mixed-estimand
   baseline。
4. first-960 是时间外 deployment cohort，不因本次 retrospective audit 改停止规则；但最终 audit card 必须报告
   train/future parent overlap，让读者知道测的是 parent-novel 还是 parent-reuse deployment。
5. 可正面写的 D&B 领域实证是：**cross-run pair construction can defeat an endpoint-run split by reusing ancestor
   context**。connected-component/group split 本身已有先例，不能申通用方法首创。

## 5. 正式复核要求

在更新 `CURRENT_DIRECTION.md` 或撤回任何结论前，须把当前临时双脚本改成仓库内 producer/verifier：

- 固定 Cards/train/dev/test/Draft/Improve 六个 SHA 与 bytes；
- producer×2、不得 import producer 的 verifier×2；
- 逐项复算 parent sets、semantic confinement、endpoint/context run overlap、parent-card presence 与 exact-code overlap；
- synthetic fixture 覆盖 parent reuse、semantic mix、row-order invariance 和 tamper；
- 不计算任何 score/accuracy/gap，GPU/API=0；
- 四次结果与 manifests 一致后，才把状态升级为 independently verified，并把 0CF/0CJ/G0 边界写入唯一入口。
