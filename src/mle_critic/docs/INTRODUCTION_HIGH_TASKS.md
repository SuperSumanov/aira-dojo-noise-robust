# MLEBench `high` 任务规模与运行时间预估

本文整理 [`high.txt`](../../dojo/tasks/mlebench/splits/high.txt) 中的 15 个任务。这里的 high 通常意味着大规模图像、视频、3D、医学数据或昂贵的序列建模；“工作数据”是 prepared/public 加 `public.tar` 的近似占盘，“3090 上 5 折预估”是假定使用合理轻量 baseline 的模型与 I/O 时间，不包含 LLM 思考、排队、环境启动和依赖安装。数字是筛选用的区间，实际实现可能更慢。

## 先说结论

在当前“单个任务尽量半小时完成”的采数目标下，high 不应作为第一批。最多可先试 `predict-volcanic-eruptions-ingv-oe`、`stanford-covid-vaccine` 和 `smartphone-decimeter-2022` 的表格/特征版本；其余任务通常需要小时级训练，或准备阶段就会占用几十到数百 GB。若必须纳入，建议把 high 单独设为长 timeout，并限制模型规模和 fold 数。

## 总表

| 任务 | 类型和规模 | 工作数据 | 3090 上 5 折预估 | 30 分钟目标 |
|---|---|---:|---:|---|
| `3d-object-detection-for-autonomous-vehicles` | nuScenes 风格车载 LiDAR/相机 3D 检测，约 10 万帧 | 50--150 GB | 6--20 小时 | 排除 |
| `bms-molecular-translation` | 分子图/SMILES 到结构字符串翻译，约 2.4M 分子 | 5--20 GB | 1--5 小时 | 排除 |
| `google-research-identify-contrails-reduce-global-warming` | 卫星序列云迹分割，约 10,000 个时空样本 | 10--30 GB | 2--8 小时 | 排除 |
| `hms-harmful-brain-activity-classification` | EEG 片段脑电活动分类，约 10,000 段长序列 | 20--60 GB | 2--8 小时 | 排除 |
| `iwildcam-2019-fgvc6` | 野外相机物种识别，约 260 万图像 | 100--200 GB | 8--24 小时 | 排除 |
| `nfl-player-contact-detection` | 美式橄榄球视频中的球员接触检测 | 20--80 GB | 2--10 小时 | 排除 |
| `predict-volcanic-eruptions-ingv-oe` | 地震/火山传感器时间序列，数千小时记录 | 2--10 GB | 30--120 分钟 | 边缘 |
| `rsna-2022-cervical-spine-fracture-detection` | 颈椎 CT 多切片骨折分类，约 2,000 病例 | 40--100 GB | 4--15 小时 | 排除 |
| `rsna-breast-cancer-detection` | 乳腺 X 光癌症检测，约 55,000 研究 | 30--80 GB | 3--12 小时 | 排除 |
| `rsna-miccai-brain-tumor-radiogenomic-classification` | 脑 MRI 四序列肿瘤分子标志物分类，约 1,000 病例 | 10--30 GB | 1--5 小时 | 排除 |
| `siim-covid19-detection` | 胸部 X 光/CT COVID 检测与定位，约 33,000 研究 | 80--200 GB | 5--20 小时 | 排除 |
| `smartphone-decimeter-2022` | 手机 GNSS 原始测量到厘米级位置回归，数百 GB 日志 | 10--50 GB | 30--180 分钟 | 边缘 |
| `stanford-covid-vaccine` | mRNA 序列结构/反应性多目标回归，约 24,000 序列 | 0.5--3 GB | 15--60 分钟 | 可试 |
| `vesuvius-challenge-ink-detection` | 古卷 CT 体数据中的墨迹 3D 分割 | 20--100 GB | 3--15 小时 | 排除 |
| `vinbigdata-chest-xray-abnormalities-detection` | 胸片 14 类病变检测，约 18,000 张 | 15--40 GB | 2--8 小时 | 排除 |

## 逐任务风险摘要

### `3d-object-detection-for-autonomous-vehicles`

需要同时处理点云、相机和 3D 框，体素化与增强的 CPU/I/O 成本很高。即使只用小型检测器，五折也远超半小时；数据复制和缓存还会造成很高峰值磁盘占用。

### `bms-molecular-translation`

这是大规模分子序列到序列翻译。token 数和词表不算极端，但 240 万样本使 Transformer 五折训练达到小时级；只能用指纹/字符串基线才可能缩短，而这会改变任务性质。

### `google-research-identify-contrails-reduce-global-warming`

每个样本是多帧卫星图像，目标为像素级云迹 mask。解码、时序堆叠和分割输出都很重，常规 U-Net 五折通常数小时。

### `hms-harmful-brain-activity-classification`

EEG 原始波形时间长、采样率高，预处理（重采样、频谱）常常比模型更慢。端到端时序网络不适合 3090 半小时约束。

### `iwildcam-2019-fgvc6`

百万级野外相机图像且类别长尾，训练和采样都很重；应直接排除短任务池。

### `nfl-player-contact-detection`

视频帧、球员追踪和接触标签需要复杂时空特征。逐帧读取会让 5 折 I/O 成为主瓶颈，短 timeout 下失败率会很高。

### `predict-volcanic-eruptions-ingv-oe`

传感器时间序列可以先做统计/频域特征，再用树模型，预计 30--120 分钟。若 agent 直接训练长窗口深度时序模型，运行时间和内存都会上升。

### `rsna-2022-cervical-spine-fracture-detection`

每个病例包含大量 CT 切片，重采样和 3D/2.5D 模型的显存、磁盘压力都很大；典型五折为小时级。

### `rsna-breast-cancer-detection`

乳腺 X 光分辨率高、单图文件大，常见方案需要切片/多视图处理。即使使用 2D backbone，五折也通常超过数小时。

### `rsna-miccai-brain-tumor-radiogenomic-classification`

MRI 四序列需要配准、切片或 3D pooling；样本数虽只有约千例，预处理和每折重复读取使任务明显慢于普通表格分类。

### `siim-covid19-detection`

同时有 X 光和 CT 研究、检测框/分类标签，原始文件多且大。准备阶段就可能达到百 GB，训练不应纳入短任务生产。

### `smartphone-decimeter-2022`

GNSS 日志可通过聚合和物理特征做树模型，才有机会接近一小时；端到端序列模型、复杂轨迹匹配会显著超时。还要留意按设备/轨迹分组切分，避免随机行泄漏。

### `stanford-covid-vaccine`

序列和结构特征规模相对小，可以用 k-mer、二级结构统计和树模型在 15--60 分钟完成。适合 high 中的受限试跑，但要确认多目标提交格式和序列级切分。

### `vesuvius-challenge-ink-detection`

3D CT 体数据分辨率极高，训练通常依赖 patch 采样、滑窗推理和大量临时缓存。磁盘和 I/O 往往比 24 GB 显存更早成为瓶颈。

### `vinbigdata-chest-xray-abnormalities-detection`

约 1.8 万张高分辨率胸片，且为 14 类目标检测。标注解析、缩放和检测模型五折通常达到数小时；只做图像级分类会偏离原任务。

## 实际使用建议

先把 high 任务视为“长任务/压力测试”而非短任务数据源：为 `predict-volcanic-eruptions-ingv-oe`、`stanford-covid-vaccine`、`smartphone-decimeter-2022` 各跑少量 seed，记录 prepared 数据峰值、实际 fold 数、预处理时间和内存。其余任务除非明确接受小时级 wall time 和更高存储预算，否则不建议进入大规模生产池。
