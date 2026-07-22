# MLEBench `low` 任务规模与运行时间预估

本文用于从 [`low.txt`](../../dojo/tasks/mlebench/splits/low.txt) 的 20 个任务中筛选适合消费级 GPU 批量采数的任务。目标是：单张 RTX 3090 上，一次常规的 5-fold train/validation 尽量在 30 分钟内结束。

## 先说结论

第一批建议优先准备以下 9 个任务：

- `aerial-cactus-identification`
- `denoising-dirty-documents`
- `jigsaw-toxic-comment-classification-challenge`
- `leaf-classification`
- `mlsp-2013-birds`
- `nomad2018-predict-transparent-conductors`
- `plant-pathology-2020-fgvc7`
- `random-acts-of-pizza`
- `spooky-author-identification`

`tabular-playground-series-may-2022` 和两个 text-normalization 任务也可以试，但比较依赖 agent 选对实现：全量 GPU boosting、低效 pandas 操作或逐行规则处理都可能越过 30 分钟。

下面这些不建议纳入第一批：

- `aptos2019-blindness-detection`、`histopathologic-cancer-detection`：已有实际运行证明会到 2--3 小时。
- `ranzcr-clip-catheter-line-classification`、`siim-isic-melanoma-classification`：医学影像多且分辨率高，前者通常需要数小时，后者的数据本身就大得不适合当前采数方案。
- `new-york-city-taxi-fare-prediction`：约 5500 万行。agent 可以靠抽样在半小时内跑完，但不同轨迹的抽样比例和内存行为差异很大，不适合作为稳定的短任务。
- `dog-breed-identification`、`dogs-vs-cats-redux-kernels-edition`：不是跑不了，但正常的 5 折迁移学习大概率超过半小时。

## 测试结果

- `aerial-cactus-identification`：速度够快，平均应该能半小时内产出一个节点，但有点太饱和了。
- `denoising-dirty-documents`：虽然数据量小，但deepseek肯定会上较大且复杂的u-net，导致两个持续失败，跑通的两个2-3h才能产出一个节点
- `jigsaw-toxic-comment-classification-challenge`：虽然数据量小，但deepseek会毫不犹豫地上distill-bert模型做微调，要4-5h才能产出一个节点
- `leaf-classification`：速度够快，差不多10分钟一个点，好像也没有完全饱和
- `mlsp-2013-birds`：非常buggy，搜索了40个draft没有一个跑通的，可能需要进debug流程再测。
- `nomad2018-predict-transparent-conductors`：同样非常buggy，唯一跑通的一个预估是半小时到1小时之间
- `plant-pathology-2020-fgvc7`：差不多半小时一个点，然后难度好像也偏低一点，而且agent会无脑用efficient net
- `random-acts-of-pizza`：够快，然后甚至难度还行，初始的draft得牌率不高
- `spooky-author-identification`：同样够快而且难度可以

## 口径

### 数据大小

表中的“工作数据”指 AIRA 实际能看到的 MLEBench `prepared/public` 数据量，并考虑当前打包方式中 `public.tar` 带来的额外一份占盘。它比 Kaggle 下载页的压缩包大小更接近实际存储压力。

- **实测**：直接对当前 `data/mlebench/<task>` 运行 `du -sh`。本机已有 6 个 `low_dev` 任务。
- **估算**：根据 Kaggle API 文件大小、MLEBench 固定版本 `d0f60ad` 的 `prepare.py`、样本数量和文件格式估算。给区间而不是伪精确值。
- 准备任务时如果还保留 Kaggle 总 zip 和 `raw/`，峰值占盘可能再增加约 1--2 倍。表中不包含这个准备阶段峰值。

### 时间

时间是“数据已经准备好以后，一次合理的 5 折建模方案”的粗估，假设：

- 1 张 RTX 3090（24 GB），约 16 个 CPU 核，本地 SSD/NVMe；
- 图像任务使用预训练的轻量 CNN、混合精度、合理 resize，不做大规模 TTA 或超参搜索；
- 文本任务使用 TF-IDF/线性模型，表格任务使用 LightGBM/XGBoost/CatBoost 一类常规模型；
- 包含读数据、训练、validation 和生成测试预测，不包含 LLM 思考、排队、镜像启动和依赖安装时间。

因此它衡量的是任务的计算下限是否适合批量采数，而不是保证任意 agent 生成的程序都能在这个时间内结束。

## 总表

| 任务 | 类型和规模 | 工作数据 | 3090 上 5 折预估 | 30 分钟目标 |
|---|---|---:|---:|---|
| `aerial-cactus-identification` | 32x32 航拍图，二分类，约 1.75 万张训练图 | **120 MB（实测）** | 8--20 分钟 | 推荐 |
| `aptos2019-blindness-detection` | 高分辨率眼底图，5 级有序分类，约 3,600 张 | **17 GB（实测）** | **2--3 小时（已有实测）** | 排除 |
| `denoising-dirty-documents` | 灰度文档图像去噪，像素级回归，约 144 张训练图 | 0.15--0.3 GB（估算） | 5--20 分钟 | 推荐 |
| `dog-breed-identification` | 自然图像，120 类，约 1.02 万张训练图 | 1.4--1.7 GB（估算） | 30--60 分钟 | 边缘 |
| `dogs-vs-cats-redux-kernels-edition` | 自然图像，二分类，2.5 万张训练图 | 1.6--2.0 GB（估算） | 25--50 分钟 | 边缘 |
| `histopathologic-cancer-detection` | 96x96 病理切片，二分类，约 22 万张训练图 | **12 GB（实测）** | **2--3 小时（已有实测）** | 排除 |
| `jigsaw-toxic-comment-classification-challenge` | 约 16 万条评论，6 标签文本分类 | 0.2--0.5 GB（估算） | 10--25 分钟（TF-IDF） | 推荐 |
| `leaf-classification` | 990 条训练样本，192 个形状/纹理特征，99 类 | 0.05--0.1 GB（估算） | 2--8 分钟 | 推荐 |
| `mlsp-2013-birds` | 645 段 10 秒音频，19 标签，附预计算特征/频谱 | 1.0--1.5 GB（估算） | 5--15 分钟（预计算特征） | 推荐 |
| `new-york-city-taxi-fare-prediction` | 约 5500 万行表格回归 | 10--13 GB（估算） | 全量 1--3 小时；抽样 10--30 分钟 | 排除 |
| `nomad2018-predict-transparent-conductors` | 约 2,400 个材料结构，双目标回归 | 0.02--0.06 GB（估算） | 5--15 分钟 | 推荐 |
| `plant-pathology-2020-fgvc7` | 苹果叶图像，4 标签，约 1,800 张原始训练图 | **774 MB（实测）** | 12--25 分钟 | 推荐 |
| `random-acts-of-pizza` | 5,671 条 Reddit 请求，文本+元数据二分类 | **42 MB（实测）** | 3--10 分钟 | 推荐 |
| `ranzcr-clip-catheter-line-classification` | 约 3 万张高分辨率胸片，11 标签 | 20--30 GB（估算） | 2--5 小时 | 排除 |
| `siim-isic-melanoma-classification` | 33,126 个皮肤病灶样本，同时提供 DICOM/JPEG/TFRecord | 150--220 GB（估算） | 4--10 小时 | 排除 |
| `spooky-author-identification` | 约 1.96 万段文本，3 类作者识别 | **6.4 MB（实测）** | 2--8 分钟 | 推荐 |
| `tabular-playground-series-dec-2021` | 400 万行合成表格，7 类分类 | 1.2--1.6 GB（估算） | 30--70 分钟 | 边缘 |
| `tabular-playground-series-may-2022` | 90 万行合成表格，二分类，含特征交互 | 1.0--1.4 GB（估算） | 15--35 分钟 | 可试 |
| `text-normalization-challenge-english-language` | 约 992 万 token，英文书面形式转口语形式 | 0.15--0.3 GB（估算，文件为 zip） | 10--30 分钟（词典/规则） | 可试 |
| `text-normalization-challenge-russian-language` | 大规模俄文 token normalization | 0.2--0.4 GB（估算，文件为 zip） | 15--40 分钟（词典/规则） | 边缘 |

## 逐任务说明和风险

### 1. `aerial-cactus-identification`

判断 32x32 航拍小图里有没有柱状仙人掌，指标是 ROC AUC。图像虽然有一万多张，但分辨率极小，数据加载和模型训练都很轻。轻量 CNN 甚至小型自定义 CNN 已经足够，是很适合批量采数的图像任务。

主要风险是 agent 使用过重的 ImageNet backbone，并把 32x32 图片无意义地放大到 224x224；这样仍能跑，但浪费不少计算。

### 2. `aptos2019-blindness-detection`

根据眼底照片预测糖尿病视网膜病变等级 0--4，指标是 quadratic weighted kappa。样本数不多，但原图分辨率很高，而且常见方案会做圆形裁剪、较大尺寸 resize 和多折迁移学习。当前准备后数据实测 17 GB，实际 5 折训练已经需要 2--3 小时。

结论很明确：不适合 30 分钟采数池。

### 3. `denoising-dirty-documents`

输入是带污渍、褶皱等噪声的扫描文档，目标是恢复干净的灰度像素，指标为像素 RMSE。训练集只有约 144 对 noisy/clean 图像。传统滤波、图像到图像回归或小型 patch CNN 都能很快跑完。

风险不是数据规模，而是 submission 是逐像素长表。低效地用 Python 循环展开像素可能比模型训练还慢。

### 4. `dog-breed-identification`

约 1.02 万张狗图，预测 120 个犬种，指标是 multiclass log loss。类别细、每类样本少，合理方案通常是预训练 CNN。单折不重，但 5 折要重复做五次完整特征提取/微调，处于 30 分钟边缘。

若固定 backbone、一次性缓存 embedding，再对 embedding 做 5 折线性分类，可以压进半小时；若每折端到端微调，则通常不行。

### 5. `dogs-vs-cats-redux-kernels-edition`

2.5 万张训练图的猫狗二分类，指标是 log loss。任务简单但图像数量不算小。轻量网络、较少 epoch 时可能接近半小时，常规 5 折迁移学习更可能需要 25--50 分钟。

它可以作为第二批候选，但不适合要求稳定低于 30 分钟的第一批。

### 6. `histopathologic-cancer-detection`

对 96x96 病理切片判断中心区域是否含有转移癌，指标是 ROC AUC。单图很小，但训练图约 22 万张，小文件读取和 5 折完整遍历都很贵。当前数据实测占 12 GB，实际训练已经需要 2--3 小时。

和 APTOS 一样应直接排除。

### 7. `jigsaw-toxic-comment-classification-challenge`

约 16 万条 Wikipedia 评论，预测 toxic、threat、insult 等 6 个非互斥标签，指标是各列 ROC AUC 的平均。字符/词 TF-IDF 加 logistic regression 是强而便宜的基线，5 折通常可以控制在 10--25 分钟。

风险是 agent 直接微调 BERT 一类模型；在 3090 上做 5 折会明显超过半小时。这个任务适合采数，但最好给统一的运行 timeout。

### 8. `leaf-classification`

根据叶片的 margin、shape、texture 三组特征识别 99 个物种。训练集约 990 行，每行 192 个数值特征；还附带叶片图，但表格特征已经足够建模。随机森林、SVM、logistic regression 等 5 折都只需几分钟。

这是最稳定的短任务之一。

### 9. `mlsp-2013-birds`

645 段 10 秒环境录音，预测 19 种鸟是否出现，指标是 ROC AUC。数据包不只含 WAV，还提供频谱、分段结果和预计算特征。直接使用预计算特征时建模很快，适合作为一个不同模态的短任务。

风险是 agent 忽略现成特征，重新对音频做昂贵的深度特征提取。不过总录音时长仍不大，通常不会像大型图像任务那样失控。

### 10. `new-york-city-taxi-fare-prediction`

根据上车时间和经纬度预测出租车费用，指标是 RMSE。训练 CSV 约 5.7 GB、5500 万行；MLEBench prepare 后还会重新写出几乎同样大的 labels CSV。完整读入就对内存和 I/O 有压力，全量 5 折 boosting 不可能稳定在半小时内。

抽样几十万到几百万行可以很快得到不错的结果，但 agent 的抽样策略会主导成本，因此不适合当前要控制生产速度的任务池。

### 11. `nomad2018-predict-transparent-conductors`

根据晶体组成和 `geometry.xyz` 结构信息预测 formation energy 与 band gap 两个连续目标，指标是两列 RMSLE 的平均。样本只有约 2,400 个，数据很小。即使做一些结构特征工程，5 折树模型一般也在十几分钟以内。

这是值得保留的科学表格/结构数据任务。

### 12. `plant-pathology-2020-fgvc7`

根据苹果叶照片预测 healthy、rust、scab、multiple diseases 四个标签，指标是各列 ROC AUC 平均。MLEBench 从原训练集重切分，实际约 1,800 张图；本地 prepared 数据只有 774 MB。轻量预训练模型 5 折预计 12--25 分钟。

这是当前已经跑通、规模也合适的图像任务。

### 13. `random-acts-of-pizza`

根据 Reddit 求披萨帖子的正文和用户元数据，判断请求最终是否成功，指标是 ROC AUC。总共 5,671 条请求。本地数据 42 MB，TF-IDF 加表格特征的 5 折只需几分钟。

样本较小、类别可能不平衡，但从采集 reasoning/工程轨迹的角度是非常合适的短任务。

### 14. `ranzcr-clip-catheter-line-classification`

从胸部 X 光片判断导管和管线的位置状态，共 11 个标签，指标是各标签 AUC 平均。原训练集约 3 万张高分辨率医学图像。MLEBench 会把这些图重新复制到 train/test，再打成 tar，工作数据预计 20--30 GB。

即使 resize 后模型能放进 3090，图像解码和 5 折训练仍通常要 2--5 小时，应排除。

### 15. `siim-isic-melanoma-classification`

根据皮肤病灶图像和病人元数据判断黑色素瘤，指标是 ROC AUC，训练样本 33,126 个。这个任务同时保留 DICOM、JPEG 和 TFRecord 三套图像表示；MLEBench 的 prepare 又会复制训练数据并制作 public tar，所以存储放大很严重。

它是 `low` 中最不适合当前硬件约束的任务：准备后的数据预计 150 GB 以上，5 折训练通常需要数小时。

### 16. `spooky-author-identification`

根据短文本判断作者是 Edgar Allan Poe、H. P. Lovecraft 还是 Mary Shelley，指标是 multiclass log loss。约 1.96 万条训练文本，本地数据只有 6.4 MB。词/字符 TF-IDF 加线性模型可以在几分钟内完成 5 折。

这是最稳定的短文本任务之一。

### 17. `tabular-playground-series-dec-2021`

400 万行合成森林覆盖数据，做 7 类分类，指标是 accuracy。特征维度不高，但行数足够大；5 折意味着训练约五次 320 万行模型。GPU boosting 可能在一小时内，CPU 或保守参数会更慢。

如果坚持 30 分钟上限，建议暂不选；如果允许 agent 合理下采样，则可以作为第二批。

### 18. `tabular-playground-series-may-2022`

90 万行合成表格二分类，重点是连续、离散特征之间的交互，指标是 ROC AUC。规模比 Dec 2021 小很多，GPU XGBoost/CatBoost/LightGBM 的 5 折大致在 15--35 分钟。

可以纳入小规模试跑，通过实际轨迹决定是否进入正式任务池。

### 19. `text-normalization-challenge-english-language`

把英文书面 token 转成适合 TTS 的读法，例如数字、日期、货币和单位；MLEBench 训练集约 992 万 token，指标是 exact-match accuracy。文件压缩率高，磁盘不大，但 pandas 读写和构建 submission 会处理近千万行。

高频 token 查表、按 class 写规则的方案能接近或低于 30 分钟；逐 token 调模型或使用序列模型则会失控。建议先试跑并加 timeout。

### 20. `text-normalization-challenge-russian-language`

与英文任务相同，但目标是俄文读法并包含 transliteration 规则。数据和规则复杂度都略高，合理的查表/规则方案预计 15--40 分钟。

它不是硬件意义上的大任务，但 agent 实现差异会很大，放到第二批更稳妥。

## 建议的实际筛选方式

仅靠上述静态估计仍不能覆盖 agent 写法差异。正式大量采数前，建议对候选任务各跑 2--4 个 seed，并记录：

1. `prepared/public.tar` 大小和挂载后的实际读取吞吐；
2. 每个 execution 的 wall time、GPU 利用率、CPU 利用率和峰值内存；
3. agent 是否使用全量数据、实际 fold 数、epoch/boosting rounds；
4. timeout、OOM、submission 生成过慢等失败类型。

第一轮可以对推荐的 9 个任务设 40 分钟 execution timeout。若绝大多数轨迹都在 30 分钟内结束，再进入大规模生产；否则单独剔除或限制该任务的训练预算。
