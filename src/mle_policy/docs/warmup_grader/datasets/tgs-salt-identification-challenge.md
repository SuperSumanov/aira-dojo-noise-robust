# TGS salt warmup 转化与审查记录

## 状态与依据

2026-11-08：已实现转换与机制测试，已生成本机数据版本；共用真实模型链路在 dog breed 上验证，salt 本身完成转换和评测测试，人工审核待进行。来源为现有 `data/mlebench/tgs-salt-identification-challenge/prepared/public`。

上游依据是同名 competition 下的 `prepare.py`、`grade.py` 及 `mlebench/competitions/utils.py::rle_decode`；转换实现为 `src/dojo/tasks/mlebench/warmup/converters/salt.py::convert_salt`。

## 数据排列与转换

`train.csv` 是 `id,rle_mask`，`train/images/<id>.png` 是输入，`train/masks/<id>.png` 是像素标签。`test/images/` 只有输入；sample 和私有 test.csv 采用同样的 `id,rle_mask`。当前 prepared 的 `depths.csv` 只保留训练 ID 的深度信息。

从现有训练表按固定 seed 抽整张图片，数量为原测试图片数的 20%，向上取整且不超过 500。复制公开目录后，将选中输入移至新 test/images，删除对应公开 mask，删除 train.csv 和 depths.csv 中的对应行。私有 warmup 答案直接保存原 RLE；sample 对新 ID 填 `1 1`。

本机 v1：原训练 3,000、原测试 1,000、warmup 200；新训练 2,800、新测试 1,200。seed 为 0。

必须同时移除 mask 文件和 CSV 标签；只删其中一个仍会公开答案。当前实现删除选中深度行，保持现有“depths 只含训练 ID”的安排，而不是新增测试深度规则。

## 评测逻辑

提交要求恰好两列 `id,rle_mask`。空 RLE 表示全背景。RLE 为 1-based 的 start/length 对，按列展开，即先从上到下，再从左到右；原 grader 解码为 101×101 二值 mask。

两侧按 ID 排序后逐图计算上游 IoU 阈值指标：阈值取 0.50 至 0.95、步长 0.05，使用严格大于阈值的匹配；每图平均这些阈值下的值，再跨图等权平均。它不是单纯像素准确率或平均 IoU。真值和预测都为空时该图得 1，只有真值为空而预测非空时得 0。

新评分入口按 ID 切原测试与 warmup，两者分别调用这个原 grader；不混合分数，也不从总分反推。

## 风险与验证

重点审查 RLE 展开方向、起点、空 mask、图像 resize 后恢复及阈值选择。当前抽样不按 mask 覆盖率分层，小 warmup 的空/非空构成可能造成波动。原 RLE decoder 的异常覆盖并不等同于所有非法编码都被拒绝，错误预测测试要专门覆盖。

RLE 格式与边界处理沿用原 grader 和 decoder。非整数 token 等触发的异常由上游 `Grader.__call__` 记录并返回评分失败；warmup 外层仅校验完整提交 ID 和拆分。

机制测试覆盖训练 mask 与 depths 清除、源目录不变、原测试得分不变、完美预测、乱序与非法 ID、错误 RLE 和错误报告更新。salt 尚未进行真实分割模型性能实验；人工审核待进行。

真实 v1 完整 sample 通过评分，新增 200 条占位 RLE 的 warmup 得分为 0；报告位于 `data/mlebench_warmup/real-grader-check/tgs-salt-identification-challenge/`。
