# denoising-dirty-documents：图片成对训练，像素逐行提交

状态：数据与评测逻辑参考，尚未接入转换代码。下述转换步骤用于后续实现和人工审查。

## 原始准备与当前文件排列

代码依据：`src/dojo/tasks/mlebench/mle-bench/mlebench/competitions/denoising-dirty-documents/prepare.py`（包括 `to_df()`）、同目录 `grade.py` 和 `config.yaml`。

上游解压原 144 张 noisy 训练图，按 `train_test_split(test_size=0.2, random_state=0)` 选出 29 张测试，把对应 clean 图移到私有目录，转换成 answers.csv 后删除私有 clean 图片目录。当前文件情况：

| 文件/目录 | 内容 |
| --- | --- |
| `public/train/<stem>.png` | 115 张 noisy 图片 |
| `public/train_cleaned/<stem>.png` | 115 张同名 clean 图片，是训练标签，必须与 noisy 一一对应 |
| `public/test/<stem>.png` | 29 张 noisy 测试图片 |
| `public/sampleSubmission.csv` | 注意大小写；`id,value`，5,789,880 条像素记录，value 全部为 1 |
| `private/answers.csv` | 同样的像素 ID，value 是正确 clean 灰度值 |

当前图片尺寸为宽 540、高 258 或 420；公开训练 noisy 总计 22,670,280 像素，原测试总计 5,789,880 像素。一张图对应十几万到二十几万条提交记录，因此 T 是 29，不是 5,789,880。

## 图片如何转成答案行

`to_df()` 使用 `Image.open(...).convert("L")` 转成单通道灰度，以 numpy 数组除以 255.0 得到 [0,1] 浮点标签。按 row 外循环、col 内循环生成：

```text
id = <图片文件 stem>_<row+1>_<col+1>
value = clean 灰度数组[row, col] / 255.0
```

例如 `110.png` 左上角是 `110_1_1`，右邻是 `110_1_2`，下一行首像素是 `110_2_1`。ID 坐标从 1 开始，数组索引从 0 开始，顺序是行在前、列在后。stem 来自原文件名，不是重新编号；统一将完整像素 ID 当字符串，不用数值排序或图像列表位置推算身份。

## grader 如何对齐和计分

1. 检查答案和提交包含 `id,value`，value 能转成 float，提交行数等于答案行数。
2. 分别按字符串 id 排序，对比 ID 数组完全相等，提取 value 计算 `root_mean_squared_error`。
3. 整体分数为 `sqrt(sum((预测值 - 正确值)^2) / 全部像素数)`，越小越好，完全正确为 0。

上游变量名把提交赋给 y_true、答案赋给 y_pred，但 RMSE 对两者对称，不影响分数。按 ID 字符串排序会使 `..._10` 排在 `..._2` 前，双方相同排序后仍能正确对齐；不能只对一侧用自然数坐标排序。

该实现不显式强制预测在 [0,1]，也不会自动裁剪。不要在外层擅自裁剪后再宣称沿用原指标。非数值、NaN/inf、重复或缺失像素等情况需要提交测试和受控反馈。大图片权重大：这是全像素 RMSE，不是每图 RMSE 的平均数，也不是按图片等权。

## 转化步骤

默认目标 W 为 6 张图片，从当前 115 对 noisy/clean 中抽取完整图片对，不能在同张图里随机抽像素或 patch 充当独立 warmup。

1. 核对 train 和 train_cleaned 的 stem、尺寸严格一一对应；统计尺寸分布，固定 seed 抽图，并记录 warmup/剩余训练的尺寸分布。若后续发现同源页面或重复图片，应先给出证据再制定完整组切分。
2. 在新版本把选中的 noisy 图从 `train/` 移到 `test/`，移除对应公开 `train_cleaned` 图。
3. 在可信进程按上游 to_df 的规则从选中 clean 图生成私有 `warmup_answers.csv`。clean 图不放在新公开目录；可直接从原数据读取生成答案，无需再发布一份私有图片副本。
4. 在原 `sampleSubmission.csv` 后追加这些图片全部像素 ID，value 统一为 1，保留其实际大小写。不能误写一个 agent 看不到的 `sample_submission.csv` 替代原文件。
5. manifest 同时记录图片 stem/宽高、图片数、像素数和提交行归属规则。提交校验先验证完整像素 ID 和重复，再按已知图片 stem 归属拆分；可用从右侧拆两个坐标段的方式解析，但必须检查 stem 已知、坐标合法且全像素覆盖，不能只按前缀模糊匹配。
6. 两部分各自运行原 grader，warmup 给出 `RMSE / lower_is_better=true / 6 images / 实际像素数`，原测试仍用原答案。

## 人工检查重点与可能问题

- 6 张图按现有尺寸对应 835,920 到 1,360,800 条额外像素行。默认上限 500 是图片数上限，不是 CSV 行数或内存上限；对其他图片任务仍须任务级评估。
- 评分时两个大 dataframe、排序和复制可能比模型推理更费内存，需测量 CSV 大小、峰值内存和两块评分耗时。manifest 可存图片清单及尺寸而不逐条保存数百万像素 ID；完整行覆盖验证仍不可省略。
- 提交常见错误包括横纵坐标颠倒、0/1 起点混淆、输出 0–255 而不是 0–1、图像 resize 后未恢复尺寸、RGB/灰度处理不同。warmup 应走完整推理和提交链路才能捕获这些问题。
- 若 agent 在同一图片内切 patch 做 CV，CV 很好而整图 warmup 低分可能来自图内相似性，而非导出 bug；analysis 应结合划分代码判断。
- 6 张图的数百万像素不代表数百万独立样本。页面/背景之间相关性强，报告实际图片数量，避免把像素数当成反馈的统计可靠性。
- 做正确答案提交、常量提交、乱序提交、坐标偏移及缺/重复像素的测试。原测试的固定提交在转化前后必须给出完全相同分数。
