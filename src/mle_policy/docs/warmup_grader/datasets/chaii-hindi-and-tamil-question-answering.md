# chaii warmup 转化与审查记录

## 状态与依据

2026-11-08：已实现转换函数和机制测试，已生成本机数据版本；真实模型/GPU 共用链路在 dog breed 上验证，chaii 本身完成转换和评测测试，人工审查待进行。源数据是现有 `data/mlebench/chaii-hindi-and-tamil-question-answering/prepared/public`，不重新运行上游 prepare。

上游依据位于 `src/dojo/tasks/mlebench/mle-bench/mlebench/competitions/chaii-hindi-and-tamil-question-answering/` 的 `prepare.py`、`grade.py`、`config.yaml`。转换实现为 `src/dojo/tasks/mlebench/warmup/converters/chaii.py::convert_chaii`。

## 数据排列

`train.csv` 的列是 `id,context,question,answer_text,answer_start,language`；每行是一条问答。`test.csv` 只有输入列 `id,context,question,language`。`sample_submission.csv` 与私有 `test.csv` 都用 `id,PredictionString`，前者是占位文本，后者是答案。

本机原训练 1,002 条，原测试 112 条。默认从训练中切 `ceil(112*0.2)=23` 条问答；当前实际切出 23 条。按完整 context 分组，以语言比例为目标平衡抽样，固定 seed 0。多行 context 必须用 CSV parser 读取，文件行数不是样本数。

## 转换实现

1. 校验训练和测试 ID，并按 context 分组抽样；检查选中答案的字符起点与文本一致。
2. 复制现有公开目录到独立版本，从新训练表删除选中问答。
3. 将选中记录投影为测试输入列追加至新 test.csv，答案改列名后存入新版本私有 `warmup_answers.csv`。
4. sample 追加 `dummy text`；记录源文件和新文件摘要、ID、实际数量及语言分布。

原数据保持不变。默认输出为 `data/mlebench_warmup/chaii-hindi-and-tamil-question-answering/v1`，生成命令见上级目录的 `RUNNING.md`。

## 评测逻辑

完整提交先检查 ID 唯一且恰好覆盖原测试与 warmup，再按 ID 分块。原 grader 将预测和答案按 ID 排序，空文本填为空字符串，转小写、按空白分词并转词集合。每条问答计算 Jaccard，随后逐样本等权平均，越大越好。词序和重复词不计入指标，标点不会额外清理；不是字符 span 准确率。

原测试得分写私有报告；仅 warmup 汇总分进入新 analysis operator。CV 仍作为 solver 排序指标。

## 风险与人工审查

- 原上游按行划测试集，新 warmup 按 context 分组，两者难度可能不同；23 条的语言和文本长度组成也会影响分数。
- 重点核对字符/token 偏移、Unicode、长文本窗口拼接、空预测及提交 ID 对齐。
- 确认 warmup 标签不再存在于公开训练表，sample 没有复制答案。
- 机制测试覆盖源数据不变、乱序提交、缺失/多余/重复/空 ID、完美预测及原测试分数保持不变。真实模型链路结果见 dog breed 文档，尚未进行 chaii 模型性能实验。
- 当前 sklearn 组合下，如果整个评分分块只有一个不同词，原 grader 的稀疏矩阵会被识别为二分类而报错；机制测试发现了这一上游边界，未改变其指标实现。真实数据版本包含多个词；极小规模手工抽样时需检查。
- 真实 v1 完整 sample 通过评分，新增 23 条占位预测的 warmup 得分为 0；报告位于 `data/mlebench_warmup/real-grader-check/chaii-hindi-and-tamil-question-answering/`。
