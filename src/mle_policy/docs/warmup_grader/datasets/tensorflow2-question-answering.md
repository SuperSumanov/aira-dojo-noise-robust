# TensorFlow QA warmup 转化与审查记录

## 状态与依据

2026-11-08：已实现转换与机制测试，本机数据版本已生成；共用真实模型链路在 dog breed 上验证，TFQA 本身完成转换和评测测试，人工审核待进行。源是现有 `data/mlebench/tensorflow2-question-answering/prepared/public`，不重新从原始数据准备。

上游依据为同名 competition 的 `prepare.py`、`grade.py`、`config.yaml`。转换实现为 `src/dojo/tasks/mlebench/warmup/converters/tensorflow.py::convert_tensorflow`。

## 数据排列

`simplified-nq-train.jsonl` 每行是一个完整 example，包含 example_id、问题、document_text、long_answer_candidates 和 annotations。公开 test JSONL 只保留前四种输入字段。私有 test.jsonl 保留标签；每条记录的 annotations 在当前设置下只有一项。

sample 的列为 `example_id,PredictionString`，每个输入样本对应 `<id>_short` 与 `<id>_long` 两行。example_id 必须保留为字符串，不能经浮点数中转而丢失大整数精度。抽样单位是完整 example，不是提交行。

本机 v1：原训练 276,635、原测试输入 30,738；warmup 500，新训练 276,135、新测试输入 31,238、提交行数 62,476。seed 为 0。

## 转换实现

当前训练文件约 15 GB。第一遍按行号进行 reservoir sampling，固定 seed 抽最多 500 个完整记录，避免把训练全集载入内存。第二遍原样复制未选行到新训练文件，选中记录写到私有 warmup_answers.jsonl；仅提取四个输入字段追加到新公开 test JSONL。sample 对选中 example 各追加 short/long 空占位预测。

生成目录记录源和输出摘要、seed、原测试样本数及目标/实际数。运行时加载私有 JSONL 只保留 example_id 和 annotations，避免在 grader 内常驻整篇 document_text。其标签结构与原 grader 读取的结构相同。

## 当前 grader 的实际评测逻辑

预测可以是空字符串、`YES`、`NO` 或 `start_token:end_token`。token 下标对应 document_text 按空格划分的原始 token，不能用子词 tokenizer 的索引直接提交。long 对应 long_answer 区间；short 对应各 short_answers 区间或 yes_no_answer。

特别注意：本仓库当前上游实现生成两组二值数组，y_pred 表示“是否非空预测”；非空预测只有精确匹配任一有效答案时 y_true 才置 1；空预测则根据是否存在答案设置 y_true。最后调用 `f1_score(average="micro")`。这是该实现的实际行为，不能直接当成官方 Natural Questions 的 span F1 或另外重写“标准 F1”。例如无答案且不预测会计为匹配，有答案但给出错误非空区间会计为不匹配。

外层保证两行提交 ID 成对、唯一并覆盖全集，按 ID 分为原测试与 warmup，然后使用同一个原 grader。原测试报告语义不变。

## 风险与验证

- JSONL 必须按完整记录移动，公开新增记录不得残留 annotations。只有 sample 增行而未追加测试输入会导致无法推理。
- long/short 不能分到两侧；空值的 CSV 读取和 `_short`/`_long` 后缀处理都要测试。
- 原 prepare 按 1,000 行分块分别随机切 10% 测试；新转换在当前训练文件上抽样。文档不能描述成重新做一次原始 train/test split。
- 文件大，转换包含摘要扫描和两遍读取，I/O 时间明显长于小任务；磁盘、加载时间与模型推理时间要分别记录。
- 预测字符串和 token 区间解析沿用原 grader；无法解析的整数等异常由上游包装器记录并返回评分失败。warmup 外层保留完整 ID 校验和分块，区间边界的接受行为由上游决定。
- 机制测试覆盖公开 test 不含 annotations、2 倍提交行数、原测试分数不变、完美预测、乱序和非法 ID、异常区间与报告覆盖。TFQA 尚未进行真实问答模型性能实验；人工审核待进行。
- 真实 v1 完整 sample 通过评分，500 个 warmup example 的空预测得分为 0.552。这也印证当前 grader 将无答案且空预测计为匹配，不能将其解读为实际回答正确率。报告位于 `data/mlebench_warmup/real-grader-check/tensorflow2-question-answering/`。
