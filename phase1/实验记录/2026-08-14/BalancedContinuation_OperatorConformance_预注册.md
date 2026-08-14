# Balanced Continuation operator-only 完整脚本闸门（预注册）

日期：2026-08-14。性质：**零 GPU、零候选执行、恰好 2 次 API 调用的工程预检**。它不能补写
已完成 E1 的方法结果，不能解锁 E2/E3，也不自动授权新的 GPU 预算。

## 固定问题与结论边界

冻结 E1 的 8 个 continuation 没有一个生成 submission：2 个 `invalid_format`，6 个被当作完整脚本执行的
片段/伪代码在 0.49 秒内失败。旧调用全部顶满 8192 completion tokens，且未保留原始响应，只保留其 SHA。
本预检只问：在不执行代码的情况下，严格 prompt + fail-closed 完整脚本检查能否让一个代码模型在两个任务上
都返回可进入候选执行阶段的完整 Python 替代脚本。

通过只说明 operator adapter 具备最低工程可用性；不说明 continuation 提升分数，不说明 balanced
continuation 有效，也不允许从该结果计算任何论文 headline。

## 冻结矩阵与预算

- provider/model：DashScope OpenAI-compatible `qwen3-coder-flash`；
- thinking：`enable_thinking=false`；temperature=0；max output=8192；
- 调用：2 tasks × 1 structurally selected warm artifact = **2 calls**；SDK retry=0，semantic retry=0；
- GPU jobs=0；candidate executions=0；预计输入约 1 万 token、输出上限 1.64 万 token，费用上限远低于 ¥1；
- 样本：每任务从 `execution_status=ok` 且已有 immutable submission 的 warm rollout 中按 rollout_id
  字典序取第一个：spaceship=`2a95db…69c2`，tabular=`3075e7…c387`；不按 D_search/D_val 分数选择；
- 旧 scorer 把所有 warm start 误标为 buggy。probe 只把 prompt action 改为 `improve`；render 函数不读取
  score，probe 不读 sealed D_val，也不读取 D_test、prospective first-960 或 0812 withheld payload。

## 13 项长实验预检逐项落实

1. **产物侧旋钮验证**：summary 必须记录 model、endpoint SHA、thinking、temperature、token cap；两条 intent
   在调用前落盘。
2. **新代码便宜自测**：synthetic caller 覆盖两任务、exactly-two-call、raw archive、完整脚本 gate；正式调用前
   跑 focused tests。
3. **测试集查重**：N/A；不训练、不评估 outcome。两个请求按 task 唯一，rollout_id 不重复。
4. **先看分布**：只报告逐任务 gate，不用 pooled 均值掩盖单任务失败；必须 2/2 同时通过。
5. **评估配平**：N/A；每任务恰好一次调用、同 model/prompt/cap。
6. **贵 run 存模型/产物**：没有模型训练；原始响应和 intent 以 mode 0600 保存，summary 绑定 SHA。
7. **泄漏三查**：请求只读 public task description、旧代码和 terminal；不读 D_val/D_test/first-960；prompt 与
   raw response 做 credential-shape 拒绝。
8. **RNG 流复现**：temperature=0，无 shuffle；样本字典序规则冻结。API 后端仍可能非确定，因此不重试。
9. **发布前密钥扫描**：key 只从远端 mode-600 `.env` 注入；raw response 不进 Git；push 前文件名与内容双扫。
10. **墙钟核算**：每调用 client timeout=240 秒；串行上限 8 分钟，通常 2–4 分钟。
11. **功效含训练侧**：N/A；这是 adapter conformance，不是效应估计。2/2 是工程必要条件，不作统计推断。
12. **链脚本 rc**：调用出错或 intent 后状态不明时立即退出；已存在 output root 拒绝重跑，不能把歧义调用记作
    rc=0。
13. **扩语料前冻结抽签**：固定从已完成 E1 中按结构规则取两条；未来语料/新 rollout 不改变本 probe。

## 通过/停止条件

每个响应必须同时满足：仅一个完整 fenced Python block、无前后 prose、AST 可编译、无 Ellipsis
占位、长度不少于 `max(512,min(4096,previous_chars/4))` 且不少于 20 行、含 `read_csv`、
`submission.csv`、`to_csv`、`FINAL_VALIDATION_SCORE`，并且未顶满 8192 token。两任务 **2/2** 才通过。

任何一条失败即 `FAIL_OPERATOR_ONLY_GATE`，不在本预注册内换模型、加 prompt 或重试。即便通过，也只允许
编写修复版 E1 的新预算门；本轮不启动 GPU rerun。

官方参数依据：Alibaba Model Studio 的 OpenAI-compatible 文档规定非标准 `enable_thinking` 通过
`extra_body` 传入；Qwen-Coder 属于其代码模型系列。链接：
<https://www.alibabacloud.com/help/en/model-studio/deep-thinking>、
<https://www.alibabacloud.com/help/en/model-studio/context-cache>。
