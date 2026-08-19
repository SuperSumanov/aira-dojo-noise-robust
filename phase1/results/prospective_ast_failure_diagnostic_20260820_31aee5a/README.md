# Prospective AST 失败诊断（v1，post-hoc outcome-blind）

本诊断解释规范化 clone audit 中 155 个直接 `ast.parse` 失败端点。它是在只见到聚合失败数后固定并提交的
post-hoc sensitivity；无论结果如何都不改变原预注册 strong gate=`false`，也不输出代码、任务、run 或 card
身份。

## 复现绑定

- source commit：`31aee5a41fcb349b4defd0d8ce807bb680c49ac3`
- protocol：`prospective_ast_failure_diagnostic_v1`
- frozen snapshot：`88cb79191b23738c1813a131abe2d5dbba48c31cb8c8095d047902afa29170c8`
- scope：`provisional_first960_prefix`，5,643 endpoints
- receipt SHA256：`cde16b78f5df01dde4ec579a6111d97610699d4d52e93b2a388dc7b39cb7a744`

两次 clean detached run 的 receipt 逐字节一致。

## 结果

- 直接 AST 失败 155/5,643，分布在 19 个 physical runs、8 个匿名 tasks；匿名 task 失败数降序为
  `[82, 62, 3, 3, 2, 1, 1, 1]`，最大 task share=`0.5290322580645161`。失败明显集中，不能假定是均匀缺失。
- 固定异常类别：generic invalid syntax 139、invalid character 12、invalid numeric literal 3、unterminated
  string 1。报告不包含原始异常文本。
- 仅 dedent、仅删 Markdown fence 行、仅删 `%`/`!` cell-command 行、三者固定组合以及四者 union 的恢复数
  全部为 **0/155**。因此不能把 AST 缺口解释成这几种表面包装，也不能据此“修复”原强门。
- 失败子集中 150/155 可由 tokenizer 处理；150 个 token-literal fingerprints **150/150 唯一**，duplicate
  groups=0、跨 run=0、跨 task=0。其余 5 个 tokenizer 也失败，保持未知。

这加强但不扩大 0BL 的正面边界：AST 缺失子集中的绝大多数仍被 parser-independent token 口径覆盖，而且没有
发现 clone；然而 5 个端点在两种口径下均不可判，且 AST 失败集中于少数任务。论文应报告这两个限制，不能写成
“全语料无规范化 clone”。

## 安全与测试

- 两份 file trace 的 label/grade/outcome/scorer/frozen-test 禁读模式合计命中 0；credential shape 0；
- 定向测试 `2 passed in 0.11s`，clean Linux 全套 `439 passed in 38.16s`；
- 完整 trace 留在受控远端，hash 与位置记录于 `verification_summary.json`；
- 0 GPU、0 API、0 LLM update，`label_vault_opened=false`。

