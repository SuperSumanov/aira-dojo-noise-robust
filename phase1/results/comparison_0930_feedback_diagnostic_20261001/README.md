# 两任务搜索轨迹的反馈机制诊断

2026年10月1日。此包分析学长 comparison/0930 的两个固定归档，包含可复现源码、逐运行目录数据和反证结果。**它提供研究取舍依据，不是新critic或analyzer的同预算收益证明。** 官方成绩仅用于既有归档的描述，不进入训练或下一步搜索反馈。

## 已核验的观察

统计范围是39个配置目录、40段从root开始的轨迹、1,023个日志事件。尚未证明目录之间的物理独立性、全部运行结束或实际预算相等；下文的终点一律指“最后日志中原生内部指标选中的节点”，不是认证的最终交付。

| 观察 | QUEST | Petfinder | 合计 |
|---|---:|---:|---:|
| 配置目录 | 15 | 24 | 39 |
| 原始Draft或Improve动作 | 129 | 139 | 268 |
| 原动作自身有有限外部分数 | 25 | 42 | 67 |
| Debug动作 | 452 | 263 | 715 |
| 最后所选节点有有限外部分数 | 15 | 21 | 36 |
| 最后所选节点来自Debug | 12 | 11 | 23 |
| 最后所选节点有分而原提案起初无分 | 11 | 11 | 22 |
| 可测的内部最优节点替换 | 51 | 60 | 111 |
| 上述替换中外部分数下降 | 12 | 13 | 25 |

Debug占已记录代码执行秒数的75.828700183415%；37个有执行时间目录的占比中位数为0.7356981890261513，标准差为0.21588504505345726。**这不是完整系统成本占比，更不能解释为可节省75.8%的时间。** 生成服务和其他搜索开销不在分母内；不少有效节点确实来自修复。

另一个从原始tar独立读取的实现与原实现核对了1,092个逐目录字段，全部一致。时间前缀另用“截断事件后重新排序原生指标”的实现核验182个配对时点、364次选择。见 `raw_comparison_reproduced.json` 与 `time_sensitivity/independent.json`。这些是实现复核，不是新增独立实验样本。

## 胜负对观察时间敏感

以下都是事后敏感性分析，方向统一为正数表示左侧方法较好。`forets-selected`即critic臂。各配对共同日志终点取两条日志覆盖跨度的较短者，上限24小时；它在不同seed可以不同，**不是统一预算**。

| QUEST critic减random | 两边均有数值的配对数 | critic胜负 | 均值 | 中位数 | 跨配对标准差 |
|---|---:|---|---:|---:|---:|
| 日志起点后12小时 | 3 | 0胜3负 | −0.00547333333333333 | −0.003149999999999986 | 0.004401776156659194 |
| 各配对共同日志终点 | 3 | 3胜0负 | +0.016483333333333332 | +0.01981999999999995 | 0.009590674289815776 |

这不能证明critic具有稳定的“前期差、后期好”机制：生产版本、硬件、活动计算时间和随机数对应关系均未完全控制。它确实否定了仅凭某一个观察窗口宣称普适胜负的做法。全部1、3、6、12、18、24小时以及共同终点的结果与缺失分母保留在 `time_sensitivity/`；到24小时，没有critic和random配对的两边日志都持续覆盖该时点，不能向后补值。

## 未支持简单的修复回退解释

另对138个出现Debug后代的Improve起点做固定语法检查，不使用分数大小。其中118个起点有首次有限评分的Debug后代，均可比较Python语法树：QUEST63个、Petfinder55个。原起点中有3个本来已有外部分数，因此不能把118全部叫作“从无效到有效”。

在这118个后代中，完整语法树退回原父代码为0；所有新增调用名全部消失也为0。部分新增调用名消失分别为38/63、33/55。**调用名变化不等于修改目标丢失**：重命名、向量化、API修正、删掉冗余模型均可能改变它。全983个动作中779个可按普通Python解析，204个解析失败保留，不静默修复或剔除以制造结论。详细覆盖在 `syntax_survival.json` 和 `summary.json`。

因此不把“修复经常完整撤销改进”当已发现的核心瓶颈，也不据此增加强制保留全部代码的策略。生产Debug提示本来就要求保持核心方法；再加一句同类要求不是独特方法。

## 对下一轮研究的约束

继续任务内反馈的同信息对照：普通反思B和证据约束C必须得到同一份事实，只有处理事实的方式变化；再检验C是否胜过把相同完整成本用于普通搜索的A。不是给C额外日志、更多候选或更强模型，再把收益归给analyzer。

新颖性仍待实证。近邻 [Gome](https://arxiv.org/html/2603.01692v3)已有执行日志和代码差异驱动的假说更新；[PROBE](https://arxiv.org/html/2605.08717)已有运行证据、结构化诊断和有边界的恢复指导。后者将诊断开销单列在修复尝试预算之外，所以本项目还须检查完整成本，而不能直接照搬其预算口径。这些近邻限制创新主张，不为本方法效果背书。

不恢复旧25run配比或损失追试、HCE、多保真、Probe-First、K≥1或底座更新。存储授权续期待确认，本轮0 GPU、0付费API、0模型拟合、0候选执行。新方法的真实收益仍须后续合法开发状态和冻结同预算运行来证明。

## 复现

源码在 `phase1/scripts/comparison_0930_feedback/`，仅需Python标准库；本轮远端原始读取用Python3.12.3，本地汇总/前缀复核用Python3.11.7。`per_run.csv`一行一个配置目录，含任务、臂、seed、实际生产commit、原始归档与日志哈希。`rows.json`和`numeric_trace.json`为脱敏的既有数值轨迹，不含程序或prompt。原始tar不得直接公开，其中可能包含凭据；从归档复现仅限持有合法副本者，脚本只读指定配置与JOURNAL成员并先做凭据检查。

在仓库根目录执行以下命令，输出目录必须尚不存在：

```bash
python phase1/scripts/comparison_0930_feedback/independent_raw_comparison_0930.py --source /path/to/authorized/0930 --output /tmp/0930-independent-new
python phase1/scripts/comparison_0930_feedback/repair_edit_survival_0930.py --source /path/to/authorized/0930 --output /tmp/0930-syntax-new
python phase1/scripts/comparison_0930_feedback/compare_raw_readers.py --input phase1/results/comparison_0930_feedback_diagnostic_20261001
python phase1/scripts/comparison_0930_feedback/comparison_0930_time_sensitivity.py --input phase1/results/comparison_0930_feedback_diagnostic_20261001 --output /tmp/0930-time-new
python phase1/scripts/comparison_0930_feedback/verify_time_sensitivity_0930.py --input phase1/results/comparison_0930_feedback_diagnostic_20261001 --output /tmp/0930-time-new
python -m unittest discover -s phase1/scripts/comparison_0930_feedback -p 'test_*.py'
```

保留的实现修正：独立读数首次凭据扫描把普通`task-...`子串误识别为密钥前缀，修正token边界后重跑；首次时间脚本用了不存在的臂名`critic`，未发布其结果，改为实际`forets-selected`并加入非空配对断言。两者均未改变实验样本、指标或原始数据。数值结果的SHA随清单核验，不手写假定的哈希。
