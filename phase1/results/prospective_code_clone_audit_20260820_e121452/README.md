# Prospective corpus 规范化代码克隆审计（v1）

本审计只回答当前前瞻语料是否由跨 physical run 或跨任务的浅层代码模板复制构成。它在 label、outcome、
scorer prediction 全部封存时运行，不评估 critic，也不能证明语义近重复或训练数据污染不存在。

## 固定协议与复现绑定

- 结果前预注册/source commit：`e121452788d22722a7b69cedf007cc07064f9cfa`
- protocol：`prospective_code_clone_audit_v1`
- frozen snapshot：`88cb79191b23738c1813a131abe2d5dbba48c31cb8c8095d047902afa29170c8`
- scope：当前 `provisional_first960_prefix`，223/960 runs、5,643 endpoints；不是完成的确认 cohort
- receipt SHA256：`9d85a642928385bac099b46ce36d24f5d8e24434a7b5076dc6b83ea8810656be`

同一 clean detached worktree 下从零运行两次，两个 receipt 逐字节一致；五项 accumulator 交叉核验均通过。

## 结果

| 口径 | 覆盖 | 唯一 fingerprint | 跨 run 重复端点 | 跨任务重复端点 | 最大组 |
|---|---:|---:|---:|---:|---:|
| raw exact | 5,643/5,643 = `1.0` | 5,631/5,643 = `0.9978734715576821` | 0 | 0 | 5 |
| token literal norm | 5,638/5,643 = `0.9991139464823675` | 5,573/5,638 = `0.9884710890386662` | 0 | 0 | 5 |
| AST literal norm | 5,488/5,643 = `0.9725323409533936` | 5,423/5,488 = `0.9881559766763849` | 0 | 0 | 5 |
| AST skeleton（诊断） | 5,488/5,643 = `0.9725323409533936` | 5,405/5,488 = `0.9848760932944607` | 0 | 0 | 5 |

token 口径删除注释/换行噪声并按类型归一化数字、字符串，同时保留 identifier/operator；AST literal 口径还删除
位置属性并保留 identifier/import/API/operator。两种主口径在各自覆盖范围内均没有跨 run、跨任务 clone，且没有
size≥10、跨≥3 tasks 的大模板组。这明显加强了此前只基于逐字节 SHA 的资产证据：当前前缀并非由“只改常量或
格式”的跨 run 模板复制堆出。

## 预注册裁决与限制

预注册强门 **未通过**：`ast_literal_norm` 的 coverage=`0.9725323409533936 < 0.99`，共有 155 个端点无法由
Python 3.11 AST 直接解析。其余所有固定检查都通过，但不得因此修改阈值或把总体状态写成
`strong_low_normalized_clone_support=true`。

因此可使用的正面主张必须限定为：token 主口径覆盖 99.91% 且跨 run/跨任务重复为 0；在 97.25% 可解析子集上，
AST 主口径也为 0。不能写成“整个语料没有规范化 clone”，更不能写成“没有 fuzzy/语义近重复”。后续解析失败
诊断只能作为明确标注的 post-hoc sensitivity，不替代本次失败的预注册门。

## 安全与测试

- 两份 `strace -f -e trace=file` 对 label/grade/outcome/scorer/frozen-test 禁读模式合计命中 0；
- credential shape 命中 0；receipt 不输出 code、task、card 值；
- 定向测试 `2 passed in 0.08s`，clean Linux 全套 `437 passed in 35.58s`；
- 完整 trace 留在受控远端，hash 与路径记录于 `verification_summary.json`。

