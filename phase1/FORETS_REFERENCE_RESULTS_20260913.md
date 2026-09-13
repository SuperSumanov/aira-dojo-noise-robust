# 新同期对照闭合：增加执行参照没有兑现 critic 收益

2026-09-13 05:24 UTC。13213/13214 全八次单次执行已终态；05:18:39 独立读出完成。
本轮不是训练：是原 MLE-bench 镜像/3090 上的真实 ForeTS 搜索，含实际候选训练、提交和外部重评分。

## 真实结果

两任务×seed32/33×random/reference-critic；每run600秒、每程序300秒、四候选选二。
两臂实际执行相同 RF 初始程序，成本计入预算；生成器/原 UCT/debug/镜像相同，仅选择机制不同。
reference-critic 看已执行 parent/incumbent/最近节点的搜索可见参照，不看外部成绩或未执行候选结果。

| 任务/seed | 共同起点 | random最终 | reference-critic最终 | critic相对random的有向差 |
|---|---:|---:|---:|---:|
| Leaf32，loss↓ | 1.51485 | 1.51485 | 1.51485 | 0 |
| Leaf33，loss↓ | 1.51485 | 0.64273 | 1.51485 | −0.87212 |
| Space32，accuracy↑ | 0.79655 | 0.81149 | 0.79655 | −0.01494 |
| Space33，accuracy↑ | 0.79655 | 0.81724 | 0.79655 | −0.02069 |

8/8技术合格且起终点有效，4/4配对可比较：0胜、1平、3负。四条critic都没有改善共同起点。
Leaf配对差中位数−0.43606、样本标准差0.6166819660084119；Space中位数−0.017815000000000025、标准差0.004065863991822593。
每任务只有两个seed，不宣称显著普遍劣势，也不把不同指标尺度合成一个平均改善数。

所有原提交均独立重评分。Slurm的FAILED不等于没有有效终点：多数为预算内拒绝发起最后一次API请求；
两条按超时结束。没有新增首次内核失败；所有费用结算后仍仅保留原两条历史未知，未抹掉责任。

## 对后续投入的裁决

[揭盲前写定的门](FORETS_REFERENCE_NEXT_GATE_20260913.md)要求至少3个严格正差；本轮为0，明确不通过。
不启动三臂24run扩大，不继续给这套配置追加seed追正数。更大生成器、加版本提示、局部代码改进都有已有实验或相关工作，不能反复当新想法。

同期可核实的研究进步，是把两个瓶颈分开：旧四池全16原程序补齐后，三个池没有直接有效程序，另一个池尚有历史未知；
而新参考条件下random确实在三个运行找到改进。这不能简化为“没有好程序”，也不能说critic只要多看上下文就有效。
05:51更新：新四首池全部9次零API补齐已完成；全16原程序1有效、14失败、1未知。唯一有效者被critic排第一，却因CV错位/缺失指标未交付。
真实同预测对齐验证和范围反证已经完成；这是局部机制证据，不是e2e新收益。见[后续实质结果](FORETS_THREE_HOUR_FINDINGS_20260913.md)。

逐已解析动作保存原搜索选解的组件已通过15单元测试及真实ForeTS解析/debug钩子的CPU接线；
尚未投入新的真实轨迹，因此没有交付收益结论，不能拿测试代替正结果。当前运行结果不按它重算。

## 复验异常公开记录

首次读出完成了原8个提交的数值复验，随后参照核验报错：冻结verifier假定嵌套metric，实际Journal序列化为浮点metric+metric_maximize。
已保留原readout-intent和三个已完成产物，单独新增格式兼容层及continuation；原冻结reader、实验源码、分数和资格判据全部不改。
5项兼容层测试通过；05:18:39补完所有真实参照请求核验。完成回执显式记录恢复脚本和兼容层SHA，不伪装成首次无错误通过。

source `f1cdee3a9e553e8efeedaa1a66a2c6bd778f9798`；controller `9cf2e7ec921730630568f3a090d81ca49cda46d2`。
root `/research/d7/spc/yzyang4/forets-wallclock-20260912-5_czzimk`。
finish SHA `6a456108ae1e9895bc4ae8902d3d58eac33e297a5cf2117c626694dfbac40f1e`；
common-summary SHA `f46e5767077a98eeaecabc415b19bd6b21b74bfdf6263dca1d8c2bbdd7b01f54`。
实际本轮1.2930555555555556 GPU·h；累计账1310调用、结算3.988558392USD、责任5.388558392USD，原两条未知完整保留。

[全八逐行结果](results/forets_reference_s32_s33_20260913/common-start-runs.csv)；
[独立结果与全部配对](results/forets_reference_s32_s33_20260913/common-start-summary.json)；
[兼容恢复回执](results/forets_reference_s32_s33_20260913/readout-finished.json)；
[新增相关工作边界](FORETS_REPAIR_RELATED_WORK_20260913.md)。
