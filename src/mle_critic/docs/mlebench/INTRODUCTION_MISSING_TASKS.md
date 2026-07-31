# MLEBench 缺失的两个任务：规模与运行时间预估

`all.txt` 比 `low.txt`、`medium.txt`、`high.txt` 的并集多出两个任务：

- `detecting-insults-in-social-commentary`
- `the-icml-2013-whale-challenge-right-whale-redux`

它们都有完整的 MLEBench competition 目录和 `prepare.py`，也被 `src/dojo/configs/benchmark/mlebench/lite.yaml` 纳入。因此这是 split 文件维护不一致，不是任务不存在。

**src/dojo/configs/benchmark/mlebench/lite.yaml 实际包含 22 个任务，正好是 low.txt 的 20 个再加上这两个任务**

本文按 [`INTRODUCTION_LOW_TASKS.md`](INTRODUCTION_LOW_TASKS.md) 的口径，单独说明这两个任务是否值得加入短任务采数池。

## 先说结论

| 任务 | 工作数据 | 3090 上 5 折预估 | 建议 |
|---|---:|---:|---|
| `detecting-insults-in-social-commentary` | 约 2--5 MB（估算） | 2--10 分钟（TF-IDF/线性模型） | 推荐加入短任务池 |
| `the-icml-2013-whale-challenge-right-whale-redux` | 约 0.5--0.7 GB（估算） | 10--30 分钟（预计算音频特征）；端到端频谱模型 30--90 分钟 | 可以加入，但需要限制音频处理方案 |

评论任务几乎没有硬件压力，适合作为稳定的文本任务。鲸鱼任务的文件总量不算大，但每个样本是音频，读取、解码和特征提取的成本会比文件大小更重要。

## 口径

“工作数据”指 MLEBench `prepare.py` 之后 AIRA 实际使用的 `prepared/public` 数据，并考虑当前工作流将 public 数据额外打成 archive 后的占盘。它不是 Kaggle 页面上的下载量：

- 评论任务的 Kaggle 文件总量约 2.4 MB，prepare 后 public 只有 train/test CSV；加上 public archive 后按 2--5 MB 估算。
- 鲸鱼任务的原始 `train2.zip` 约 195 MB、`test2.zip` 约 97 MB。prepare 会从四天训练数据切出两天 train、两天 test，再重新生成两个 zip；加上 public archive 后按 0.5--0.7 GB 估算。

时间假设与低任务文档相同：一张 RTX 3090、约 16 个 CPU 核、本地 SSD；5-fold train/validation；包含读数据、训练、验证和生成 submission，不包含 LLM 思考、排队和环境启动。文本任务使用 TF-IDF/线性模型，音频任务优先使用 MFCC、频谱统计等预计算特征。

## 任务说明

### 1. `detecting-insults-in-social-commentary`

这是单标签英文评论分类任务：判断一条论坛/博客评论是否有意侮辱对话中的其他参与者，指标是 ROC AUC。输入有评论时间和 unicode-escaped 评论文本，标签 `Insult` 为 0 或 1。

MLEBench 的 prepare 不重新随机切分数据，而是直接使用 Kaggle 的 `train.csv`，并把 `test_with_solutions.csv` 去掉标签后作为 public test；完整标签保存在 private test。训练 CSV 约 850 KB，public test 约 300 KB，样本量和文本长度都不会造成显著 I/O 压力。

推荐方案是字符/词 TF-IDF 加 logistic regression、linear SVM 或 LightGBM。5 折通常在 2--10 分钟内完成，3090 基本不是瓶颈，CPU 文本向量化占主要时间。

主要风险不是运行时，而是数据泄漏和过拟合：原始任务文档明确提醒训练分布并不覆盖最终数据，评论中还可能有少量标签噪声。时间字段也可能让 agent 做出不稳定的时间特征。若 agent 直接微调 BERT，虽然小数据仍可能跑完，但没有必要，会增加环境和随机性成本。

**判断：推荐加入第一批短任务。** 它可以补上当前 low 任务池里的一个轻量 NLP 任务，而且比 `jigsaw-toxic-comment-classification-challenge` 更小、更稳定。

### 2. `the-icml-2013-whale-challenge-right-whale-redux`

这是二分类音频检测任务：给定四天训练数据和三天测试数据，判断每段录音中是否有北大西洋露脊鲸叫声，指标是 ROC AUC。原始文件是 `.aif` 音频，训练文件名的后缀 `_1`/`_0` 直接编码正负标签。

MLEBench prepare 将原训练集按日期重切分：前两天作为 public train，后两天作为 public test，并生成 private test 的答案。它把复制后的音频重新压成 `train2.zip` 和 `test2.zip`，因此实际工作目录不需要保存大量小的未压缩音频文件。原始 Kaggle 下载量约 292 MB，但未压缩读取和音频特征缓存会让峰值内存/临时空间更高。

如果使用音频长度、能量、频带统计、MFCC 或短时频谱的预计算特征，再用 logistic regression、随机森林或 LightGBM 做 5 折，预计 10--30 分钟。若每一折都重新扫描全部音频并计算 STFT，通常仍可能在 30 分钟附近；若训练端到端 CNN/Transformer 频谱模型，预计 30--90 分钟，不再满足稳定的短任务预算。

这个任务还有一个和普通 i.i.d. 数据不同的点：prepare 按日期切分，而不是逐样本随机切分。这样更接近时间外推，但每折内部如何划分必须留意日期相关性，不能把相邻时间片随机打散后把结果当成独立泛化估计。

**判断：可以加入第二批或第一批受限版本。** 建议给它固定的音频特征提取预算和 40 分钟 timeout；如果 agent 选择端到端深度音频模型，应单独归入长任务。

## 建议的准备和验证

这两个任务可以直接用 competition id 准备，不需要修改 `low.txt`：

```bash
python src/dojo/tasks/mlebench/utils/prepare.py \
  -c detecting-insults-in-social-commentary \
  --data-dir="$MLE_BENCH_DATA_DIR"

python src/dojo/tasks/mlebench/utils/prepare.py \
  -c the-icml-2013-whale-challenge-right-whale-redux \
  --data-dir="$MLE_BENCH_DATA_DIR"
```

正式批量采数前，建议分别跑 2--4 个 seed，记录文本向量化/音频解码时间、5 折总 wall time、峰值内存，以及音频任务是否重复计算特征。评论任务可以直接使用 30 分钟 timeout；鲸鱼任务建议先用 40 分钟，观察 agent 是否采用预计算特征后再决定是否纳入大规模生产。
