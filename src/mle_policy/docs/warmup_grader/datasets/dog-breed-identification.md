# Dog breed warmup 转化与审查记录

## 状态与依据

2026-11-08：已实现转换与机制测试，已生成本机版本，并完成 Minimax 生成代码、真实 GPU 执行、warmup 评分和真实 analysis 的链路短测；人工审核待进行。从当前 `data/mlebench/dog-breed-identification/prepared/public` 继续处理。

上游依据为同名 competition 的 `prepare.py`、`grade.py`、`dogs.py` 和共享 `one_hot_dfs_to_log_loss_inputs`。转换实现为 `src/dojo/tasks/mlebench/warmup/converters/dogs.py::convert_dogs`。

## 数据排列与转换

`labels.csv` 每行 `id,breed`，训练图片在 `train/<id>.jpg`，测试图片在 `test/<id>.jpg`。sample 和私有 test.csv 都是 id 加 120 个犬种列；私有答案为 one-hot，sample 每类概率为 1/120。犬种名称和类别顺序以原 `DOGS_LIST` 为准。

以整张图片为样本、breed 为平衡目标，固定 seed 从现有训练数据抽原测试规模的 20%，上限 500。复制公开目录，把选中 JPG 移到 test，删掉 labels.csv 对应行。调用上游 `to_one_hot` 生成私有 warmup 答案，sample 追加均匀概率，不把类别名称或 one-hot 答案写到公开新增文件。

本机 v1：原训练 9,199、原测试 1,023、warmup 205；新训练 8,994、新测试 1,228。seed 为 0。概率的数值类型、范围和归一化校验沿用原 grader；warmup 外层只额外处理非有限的最终得分。

## 评测逻辑

原 grader 检查 id 和所有 120 类列存在、行数匹配；概率需要在 [0,1]，每行总和接近 1。共享 helper 按 id 排序，与答案的类别列对齐；不做 softmax，再调用 sklearn log_loss。越小越好，不是 top-1 accuracy。模型训练标签编码和导出概率列必须显式按犬种名称对应。

外层先检查完整提交 ID 唯一且全集准确，再分块调用原 grader；原测试分数和 warmup 分数独立保存，仅后者送给 analysis。

## 风险与验证

- warmup 中各品种数量很少；分层目标是接近原分布，不保证每类相同数量。不能以局部品种准确率代替整体 log loss。
- 错列、将 logits 当概率、类别编号顺序不一致和未归一化都会影响提交。原 grader 不自动修正这些问题。
- 图片主体和背景相似性可能让 CV 与 warmup 不一致，低分本身不证明代码错误。
- 机制测试覆盖原目录不变、文件/表 ID 对应、原测试得分不变、完美预测、乱序和非法 ID、错误概率与报告覆盖。

## 真实模型/GPU 短测

2026-11-08 使用指定的 `litellm_minimax-m3.1-flash.yaml` 生成单文件 TinyCNN，Slurm allocation 25756 / gpu35，实际使用 NVIDIA RTX 3090，容器为 `verl_vllm.sif`。代码将图片缩放到 32×32，读取 1,500 张训练图片，分出 300 张验证，训练三轮，对全部 1,228 个测试 ID 推理。执行日志记录 CUDA 设备，代码运行约 51 秒，整个模型请求、容器启动、评分与分析过程为分钟量级。

- 提交 `(1228, 121)`，每行概率和为 1；task 返回 valid_solution=true。
- 脚本 CV log loss 为 4.717441；warmup 的 205 张图片 log loss 为 4.74259。
- 新 analyze 的真实请求包含独立 warmup JSON，响应保留 metric=4.717441，is_bug=false，说明两个分数接近且小模型能力有限。
- 检查实际分析请求，未包含私有报告的 medal thresholds、above_median、valid_submission 等字段。原测试报告留在 private_reports。
- 模型分析中“训练表按 breed 排序”等具体判断需要人工核对；本次以实际请求/响应确认信息链路，不把模型解释当成事实依据。

证据位于 `data/mlebench_warmup/smoke-20261108-bound/`：`execution.log`、`analysis.json`、`analysis_call.json`、`private_reports/`、`draft.txt` 和 `solution.py`。首次尝试因容器缺少共享数据挂载而失败，修正 bind 后复用同一模型草稿完成，保留了失败目录 `smoke-20261108/`。该次短测验证组件链路；常用 MCTS 实验命令见 `../RUNNING.md`。

进一步使用同一草稿完成 Greedy 集成验证，证据在 `smoke-20261108-integrated/`。真实分析保留 CV=4.717441，并读取 warmup=4.74259；这次响应将截取前 1,500 张训练图及静默吞掉图像读取错误列为风险，返回 is_bug=true，Greedy 相应将节点标为 buggy，选择指标为空而不是替换成 warmup 或原测试分数。`selection.json` 保存这一结果。两次分析的 bug 判断不同，表明反馈链路正确不等于 LLM 判断稳定；不能把低分或模型的条件性猜测直接当成已确认缺陷。

真实完整 sample 的格式/评分检查也通过，均匀 1/120 概率的 warmup log loss 为 4.78749，报告保存在 `data/mlebench_warmup/real-grader-check/dog-breed-identification/`。
