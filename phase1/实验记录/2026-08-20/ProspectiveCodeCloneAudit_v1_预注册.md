# Prospective code clone audit v1：结果盲预注册

## 目标与边界

当前 exact-code 唯一率很高，但逐字节 SHA 不能排除只改常量、格式或变量名的模板复制。本审计在任何
label/outcome/scorer prediction 打开前，固定检查 provisional first-960 prefix 的规范化 exact clones。它只读
`eligible_blind_manifest.jsonl`、identity-only runs、intake/accumulator summaries；不输出代码、task/card 值，
不计算 predictor accuracy，也不改变 first-960/closure 停止规则。

本实验不能证明“没有语义近重复”：规范化 hash 只识别定义明确的 exact clone；未命中的 fuzzy/语义等价程序仍
可能存在。`ast_skeleton` 过于激进，只作模板碰撞上界，不进入正结论门。

## 结果前固定的四层 fingerprint

1. `raw_exact`：UTF-8 code SHA256；
2. `token_literal_norm`：Python tokenizer 删除注释与换行噪声，保留 INDENT/DEDENT、identifier、operator，
   number/string 分别替换为类型占位符；
3. `ast_literal_norm`：AST 删除位置属性，仅把 literal 按类型归一化，保留 identifiers、imports、attributes、
   operators；这是主规范化；
4. `ast_skeleton`：在 AST literal norm 上进一步归一化用户 identifiers/定义名/aliases，但保留 import module 与
   attribute/API 名；仅诊断。

每层固定报告 fingerprint coverage、unique fraction、duplicate groups、largest group、same-parent、cross-run、
cross-task、duplicate endpoint membership，以及 size≥10 且跨≥3 tasks 的大模板组数。解析失败不删除：计入失败并
降低 coverage；规范化指标的分母是 fingerprint 成功端点数。

## 预注册成功门

只有全部满足才记 `strong_low_normalized_clone_support=true`：

- raw exact cross-run duplicate groups=0；
- `token_literal_norm` 与 `ast_literal_norm` 各自 coverage≥0.99；
- 两个主规范化各自 cross-run duplicate endpoint fraction≤0.01；
- 两个主规范化各自 cross-task duplicate endpoint fraction≤0.005；
- 两个主规范化均没有 size≥10 且跨≥3 tasks 的 duplicate group。

阈值在真实结果前写入代码常量与本文件；失败不改规范化、阈值或删除任务。通过只支持“按两种固定规范化，当前
prefix 的 exact clone 冗余较低”，不能升级为语义唯一、无训练数据污染或 critic 有效。

## 复现与安全

- cohort target 锁死 960；当前不足时明确标为 provisional prefix；
- deterministic、无随机 seed、0 GPU、0 API、0 LLM update；
- producer 双跑逐字节一致，独立输入/accumulator count 交叉核验；
- 两次文件访问 trace 的 label/grade/outcome/scorer/frozen-test 禁读模式必须为 0；
- source commit、verifier blob、Python、所有输入 SHA 写入 receipt；
- 定向测试与 Linux 全套测试必须通过，任何 schema/SHA/trace/rc 失败均 fail closed。
