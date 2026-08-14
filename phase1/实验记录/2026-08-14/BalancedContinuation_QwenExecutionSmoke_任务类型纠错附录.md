# Balanced continuation：Qwen execution smoke 任务类型纠错附录

日期：2026-08-14。本文写在任何旧候选重执行、任何新 operator API 调用和任何
D_search/D_val/D_test/outcome 读取之前。旧目录、旧 summary、旧 `VERDICT.md` 与其哈希原样保留；
本附录只允许对两个不可变 `submission.csv` 做一次新的独立工程重验。

## 1. 为什么旧 1/2 裁决不能继续作为有效工程门

旧 smoke producer/verifier 对两个任务共同执行了 `float(value)`，把“可解析且有限”错误实现成了
“所有 target 都必须是浮点数”。但实验开始前已经提交的严格 E1 scorer 明确区分任务：

- `spaceship-titanic` 的 metric 是 accuracy，`Transported` 只接受大小写无关的
  `True/False/1/0`；
- `tabular-playground-series-may-2022` 的 metric 是 ROC-AUC，`target` 才要求 `[0,1]` 内有限浮点数。

只读、无标签审计确认旧 spaceship artifact 是 1,562 行布尔字面量，artifact SHA-256 为
`78328281553d3dc5b756bb2017fb0770aae5bf5818027c785df103b225f2691f`，对应 public sample SHA-256 为
`68809cd3c667da24678954db3b84333cead612983ad2a64b8322ae33221330d3`。调用已提交的严格 E1
parser、传入空 evaluation-id 列表时，完整 header/ID/行数/target 类型检查通过；标签和分数均未打开。
tabular artifact SHA-256 为
`8e23326b67a367f9382d7185b9621805bdabda179ef17b23ce99c47823ef299b`，159,998 行有限浮点数，也通过
相同 public-shape 检查。

因此旧 `unparseable_prediction` 是 verifier 与科学 scorer 的类型契约冲突，不是候选执行失败。
这不允许直接把旧 FAIL 改字为 PASS；必须用新 commit 的独立 verifier 透明重建。

## 2. 冻结纠错范围

1. producer 的 public-shape helper 改为 task-aware：accuracy 严格布尔，ROC-AUC 为 `[0,1]` 有限概率；
2. 独立 verifier 不 import smoke producer，自行实现同一类型规则；
3. repair 模式只允许一个历史差异：index 0 的旧 summary 必须精确为
   `FAIL_EXECUTION_ONLY + unparseable_prediction + rows=0 + columns=[]`，新重建必须为通过；
4. index 1、response→code、执行 receipt、容器参数、artifact SHA、逐行 ID/行数、0 retry、0 API、
   public-only mount 和所有无分数边界仍须逐项通过；任何其他差异均 fail closed；
5. repair receipt 写入新文件，不覆盖旧 verification；新候选执行=0、API=0、GPU=0，不读取或报告
   external score/gain/utility/frozen/first-960 outcome；
6. 新增回归测试覆盖布尔通过、accuracy 小数拒绝、AUC 布尔拒绝、AUC 越界拒绝、ID 重排拒绝，
   以及“默认严格重验拒绝旧 mismatch、只有显式 repair 模式可接纳”的边界。

## 3. 预先裁决

- 两个 immutable artifact 在上述独立 repair verifier 下全过：输出
  `VERIFIED_QWEN_EXECUTION_SMOKE_PASS_TASK_TYPE_REPAIR`，只恢复 fresh-anchor E1-Q 的**准备与预检**；
- 任一项失败：保持 E1-Q 关闭，不重试候选、不改 prompt/model/token/time/task；
- 即使通过，也只证明既有 Qwen 完整脚本可执行并符合 public submission contract，不证明 continuation
  有增益、Qwen 优于 DeepSeek、balanced label 更可靠或 hurdle critic 有效。
