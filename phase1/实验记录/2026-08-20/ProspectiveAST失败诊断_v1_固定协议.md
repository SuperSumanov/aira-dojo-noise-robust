# Prospective AST 失败诊断 v1：post-hoc、结果盲固定协议

## 已知信息与不可更改裁决

在编写本诊断前，只读取了 clone audit 的聚合结果：5,643 endpoints 中 AST 失败 155，导致预注册 coverage
`0.9725323409533936 < 0.99`。没有读取失败端点代码、身份、任务、异常类别或恢复结果。原 clone strong gate 已固定
判失败；本诊断无论结果如何都不能修改阈值、删除端点或把该 gate 改成通过。

## 固定诊断

只对同一 frozen `provisional_first960_prefix` 做以下聚合统计：

1. 固定的 SyntaxError/IndentationError 类别计数，不输出原始异常文本；
2. 四种预先写死的机械 sensitivity：仅 dedent、仅移除 Markdown fence 行、仅移除首个非空字符为 `%`/`!` 的
   cell-command 行，以及按 fence→cell-command→dedent 的组合；
3. 失败端点覆盖多少匿名 tasks/runs、最大单 task share 与匿名 task count 向量；
4. 对失败子集复用既有 token-literal fingerprint，报告 coverage 和跨 run/跨任务 exact clones。

这些变换只用于判断直接 `ast.parse` 失败是否可由表面包装解释；变换后的代码不进入主 clone 表、不替代原 AST
fingerprint，也不进入任何 predictor。即使全部可恢复，也只能写成 post-hoc parser sensitivity。

## 安全、复现和资源

- 只读 code-only blind manifest、identity-only run 和 intake/accumulator summaries；
- 不输出 code/task/run/card 值，不打开 label/outcome/scorer/frozen test；
- source commit/blob、snapshot 与输入 SHA 写入 receipt，双跑逐字节一致；
- 两次 file trace 禁读模式 0、credential shape 0、定向与全套测试通过；
- deterministic，0 GPU、0 API、0 LLM update；任何 binding/schema/trace/测试失败均 fail closed。

## 执行结果（固定协议提交后追加）

commit `31aee5a41fcb349b4defd0d8ce807bb680c49ac3` 双跑 receipt 逐字节一致，SHA=
`cde16b78f5df01dde4ec579a6111d97610699d4d52e93b2a388dc7b39cb7a744`；禁读路径与 credential shape 均为 0，
Linux 全套 `439 passed in 38.16s`。

155 个失败分布在 19 runs/8 anonymous tasks，task counts=`[82,62,3,3,2,1,1,1]`；固定四种表面清理及其 union
均恢复 0。失败子集中 tokenizer 成功 150 个，150/150 fingerprints 唯一、跨 run=0、跨 task=0；另 5 个保持
未知。原 clone strong gate 仍为 false，不修改。完整证据：
`phase1/results/prospective_ast_failure_diagnostic_20260820_31aee5a/README.md`。
