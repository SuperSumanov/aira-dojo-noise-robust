# MLEBench `medium` 任务规模与运行时间预估

本文整理 [`medium.txt`](../../dojo/tasks/mlebench/splits/medium.txt) 中的 38 个任务，供 RTX 3090 批量采数时筛选。目标仍是一次常规 5-fold train/validation 尽量不超过 30 分钟。除特别说明外，数据量和时间都是基于 Kaggle 文件、MLEBench `prepare.py` 和常见 baseline 的工程估算，不是官方保证。

## 口径

“工作数据”按 prepared/public 数据和 `public.tar` 的占盘计算，不包含下载 zip、raw 缓存和准备阶段峰值。时间假设单张 3090、约 16 个 CPU 核、本地 SSD；图像用轻量预训练 CNN，表格用 LightGBM/XGBoost，文本用 TF-IDF/线性模型，音频/3D 使用预计算特征。包含读数据、训练、validation 和预测，不包含 LLM 思考、排队、启动和安装依赖。

## 先说结论

第一轮可试：`AI4Code`、`google-quest-challenge`、`kuzushiji-recognition`、`learning-agency-lab-automated-essay-scoring-2`、`petfinder-pawpularity-score`、`plant-pathology-2021-fgvc8`、`statoil-iceberg-classifier-challenge`、`tweet-sentiment-extraction`、`us-patent-phrase-to-phrase-matching`、`ventilator-pressure-prediction`、`whale-categorization-playground`。这些任务在缓存特征或轻量模型下大致可压到 10--35 分钟。

不建议作为短任务：`cdiscount-image-classification-challenge`、`h-and-m-personalized-fashion-recommendations`、`herbarium-2020-fgvc7`、`herbarium-2021-fgvc8`、`herbarium-2022-fgvc9`、`hotel-id-2021-fgvc8`、`inaturalist-2019-fgvc6`、`iwildcam-2020-fgvc7`、`uw-madison-gi-tract-image-segmentation`。它们的图像/行为数据或分割输出会使正常五折训练达到数小时。

# 测试结果

- `tabular-playground-series-may-2022`：速度行，而且初始几乎没有拿牌的
- `text-normalization-challenge-english-language`：速度行而且拿牌率低。

## 总表

| 任务 | 类型和规模 | 工作数据 | 3090 上 5 折预估 | 30 分钟目标 |
|---|---|---:|---:|---|
| `AI4Code` | 代码 notebook markdown 单元排序，约 1.6 万本 | 1--3 GB（估算） | 10--30 分钟（特征） | 推荐 |
| `alaska2-image-steganalysis` | 512x512 图像隐写检测，约 8 万张 | 15--25 GB | 1--3 小时 | 排除 |
| `billion-word-imputation` | 大规模英文词缺失恢复，千万级 token | 2--5 GB | 30--90 分钟（规则/LM） | 边缘 |
| `cassava-leaf-disease-classification` | 木薯叶 4 类图像，约 2.1 万张 | 2--4 GB | 25--60 分钟 | 边缘 |
| `cdiscount-image-classification-challenge` | 商品图像 5 千类，约 90 万张 | 50--70 GB | 4--10 小时 | 排除 |
| `chaii-hindi-and-tamil-question-answering` | 印地语/泰米尔语阅读理解，约 1,100 问题 | 20--60 MB | 5--20 分钟 | 推荐 |
| `champs-scalar-coupling` | 分子原子对耦合回归，约 4.7M 行 | 1--3 GB | 30--90 分钟 | 边缘 |
| `facebook-recruiting-iii-keyword-extraction` | 招聘文本关键词抽取，百万级文本 | 1--3 GB | 20--60 分钟 | 边缘 |
| `freesound-audio-tagging-2019` | 41 类环境声音，约 4.9 万段音频 | 8--15 GB | 1--3 小时（端到端） | 排除 |
| `google-quest-challenge` | 问答网站质量多标签，约 6,000 条 | 20--80 MB | 5--15 分钟 | 推荐 |
| `h-and-m-personalized-fashion-recommendations` | 用户商品推荐，约 3,000 万交易 | 15--30 GB | 1--4 小时 | 排除 |
| `herbarium-2020-fgvc7` | 植物标本细粒度分类，约 1.5M 图像 | 15--30 GB | 3--8 小时 | 排除 |
| `herbarium-2021-fgvc8` | 植物标本分类，约 3.5M 图像 | 30--60 GB | 5--12 小时 | 排除 |
| `herbarium-2022-fgvc9` | 植物标本分类，约 1.5M 图像 | 20--40 GB | 4--10 小时 | 排除 |
| `hotel-id-2021-fgvc8` | 酒店地点识别，约 1.3M 图像 | 25--50 GB | 4--10 小时 | 排除 |
| `hubmap-kidney-segmentation` | 肾脏显微图像实例分割，约 20 个大切片 | 5--15 GB | 1--4 小时 | 排除 |
| `icecube-neutrinos-in-deep-ice` | 冰立方探测器中微子方向回归，约 1.3M 事件 | 5--15 GB | 30--120 分钟 | 边缘 |
| `imet-2020-fgvc7` | 地标图像多标签分类，约 17 万图像 | 8--20 GB | 2--5 小时 | 排除 |
| `inaturalist-2019-fgvc6` | 1,010 类物种分类，约 2.7M 图像 | 80--120 GB | 8--20 小时 | 排除 |
| `iwildcam-2020-fgvc7` | 野外相机物种识别，约 260 万图像 | 80--150 GB | 8--20 小时 | 排除 |
| `jigsaw-unintended-bias-in-toxicity-classification` | 180 万评论多标签毒性分类 | 2--5 GB | 20--60 分钟（TF-IDF） | 边缘 |
| `kuzushiji-recognition` | 日文古文字 10 类图像，约 28 万张 | 1--3 GB | 15--35 分钟 | 推荐 |
| `learning-agency-lab-automated-essay-scoring-2` | 英文作文分数回归，约 17,000 篇 | 0.1--0.4 GB | 5--20 分钟 | 推荐 |
| `lmsys-chatbot-arena` | 聊天机器人偏好/胜负预测，百万级对话 | 2--8 GB | 20--90 分钟 | 边缘 |
| `multi-modal-gesture-recognition` | 手势视频/传感器分类，数万段序列 | 2--8 GB | 30--120 分钟 | 边缘 |
| `osic-pulmonary-fibrosis-progression` | 肺纤维化影像和临床特征回归，约 1,000 人 | 1--3 GB | 15--45 分钟 | 可试 |
| `petfinder-pawpularity-score` | 宠物照片受欢迎度回归，约 10,000 张 | 1--3 GB | 10--30 分钟 | 推荐 |
| `plant-pathology-2021-fgvc8` | 苹果叶多标签病害，约 23,000 张 | 2--5 GB | 20--45 分钟 | 可试 |
| `seti-breakthrough-listen` | 射电频谱异常检测，约 60,000 张频谱图 | 8--15 GB | 30--90 分钟 | 边缘 |
| `statoil-iceberg-classifier-challenge` | SAR 船/冰山二分类，约 16,000 样本 | 0.2--0.6 GB | 8--25 分钟 | 推荐 |
| `tensorflow-speech-recognition-challenge` | 12 词语音识别，约 65,000 WAV | 1--3 GB | 20--60 分钟 | 边缘 |
| `tensorflow2-question-answering` | Wikipedia 阅读理解，约 100,000 问题 | 0.5--2 GB | 20--90 分钟 | 边缘 |
| `tgs-salt-identification-challenge` | 卫星图像盐体分割，约 4,000 张 | 0.5--1.5 GB | 15--45 分钟 | 可试 |
| `tweet-sentiment-extraction` | Tweet 情绪片段抽取，约 27,000 条 | 20--100 MB | 5--20 分钟 | 推荐 |
| `us-patent-phrase-to-phrase-matching` | 专利短语语义相似度，约 36,000 对 | 20--100 MB | 5--15 分钟 | 推荐 |
| `uw-madison-gi-tract-image-segmentation` | 腹部 MRI 器官分割，约 1,000 个序列 | 10--30 GB | 2--6 小时 | 排除 |
| `ventilator-pressure-prediction` | 呼吸机时间序列压力回归，约 2,500 万行 | 2--6 GB | 15--45 分钟 | 可试 |
| `whale-categorization-playground` | 鲸鱼个体图像识别，约 10,000 张 | 1--3 GB | 15--40 分钟 | 可试 |

## 逐任务风险摘要

- `AI4Code`、`google-quest-challenge`、`learning-agency-lab-automated-essay-scoring-2`、`tweet-sentiment-extraction`、`us-patent-phrase-to-phrase-matching`：文本/表格特征很小，适合作为第一批；主要风险是 agent 直接调用大型 Transformer。
- `chaii-hindi-and-tamil-question-answering`、`tensorflow2-question-answering`：问答任务的评估和答案 span 后处理容易出错；小模型或 TF-IDF 才能满足时间预算。
- `cassava-leaf-disease-classification`、`kuzushiji-recognition`、`petfinder-pawpularity-score`、`plant-pathology-2021-fgvc8`、`statoil-iceberg-classifier-challenge`、`tgs-salt-identification-challenge`、`whale-categorization-playground`：可用轻量 CNN/缓存 embedding 试跑；每折重复解码图像会把边缘任务推过 30 分钟。
- `alaska2-image-steganalysis`、`cdiscount-image-classification-challenge`、`freesound-audio-tagging-2019`、`herbarium-*`、`hotel-id-2021-fgvc8`、`imet-2020-fgvc7`、`inaturalist-2019-fgvc6`、`iwildcam-2020-fgvc7`、`uw-madison-gi-tract-image-segmentation`：数据复制、解码或分割输出是主要瓶颈，不建议投入短任务采数。
- `billion-word-imputation`、`facebook-recruiting-iii-keyword-extraction`、`champs-scalar-coupling`、`icecube-neutrinos-in-deep-ice`、`jigsaw-unintended-bias-in-toxicity-classification`、`lmsys-chatbot-arena`、`multi-modal-gesture-recognition`、`osic-pulmonary-fibrosis-progression`、`seti-breakthrough-listen`、`tensorflow-speech-recognition-challenge`、`ventilator-pressure-prediction`：规模或预处理成本差异大，应先单独跑 1--2 个 seed 再决定是否批量化。

建议对“推荐/可试”任务先设置 40 分钟 timeout，记录实际读取量、fold 数、模型类型和峰值内存；不要把 LLM 推理或镜像启动时间混入这里的模型运行估计。
