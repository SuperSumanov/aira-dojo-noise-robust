# 同版本第二seed：未复现稳定、可归因的critic收益

2026-09-12 00:03 UTC完成整组及独立复核；job13118 COMPLETED/gpu28，4/4进程完成、3/4有效最终解。
不是模型训练、G0验收或clean scaling。两个版本只有paid_budget.py的累计授权结转不同，科学配方未变。

| 任务 | seed | 随机最终成绩 | critic最终成绩 | 结论边界 |
|---|---:|---:|---:|---|
| Leaf（logloss越低越好） | 11 | 无有效final | 无有效final | 缺失，不补零或称打平 |
| Leaf | 12 | 无有效final | 0.37782 | 仅critic臂有效，但未实际改选 |
| Spaceship（accuracy越高越好） | 11 | 0.74368 | 0.79655 | 观测差+5.28700pp，未实际改选 |
| Spaceship | 12 | 0.80805 | 0.61839 | 观测差−18.96600pp，有实际改选 |

所有差值由冻结的汇总代码打印，见results/forets_repeat_20260912/seed11-seed12-comparison.json。
Spaceship两个seed的条件差值中位数−0.068395，样本方差0.02941040045（原accuracy尺度，不是pp尺度）；
仅两个seed，不据此给稳定效应或泛化保证，也不跨不同任务指标混合平均。

## 干预检查如何限制解读

seed12全部12池重放与实际执行一致，critic四个可剪枝池的top2边界均严格。
实际slot及原字节/AST改选仅发生在Spaceship的step1、step3；Leaf各池与同池随机规则选择一致。
因此Leaf的有效解出现不能归功于critic选择；Spaceship也不能将全部降幅归因为critic，因两臂生成抽样独立。
两seed中两个“看上去有利”的任务例均未发生改选，当前尤其不能只挑这些例子宣布收益。

这没有证明critic在所有条件下无用，但明确不支持按当前配方继续盲目扩大矩阵。
按此前条件方案，转入已固定的seed11两任务首池全部8程序诊断，分辨生成分布与选择质量；
不反转分数、不挑候选、不重跑失败槽位、不把诊断当新e2e胜出。
GPU上限1.5小时（单卡）、零生成API/critic调用；实际提交状态仍看短交接。

## 实际工作量与证据

- 本块3337秒双卡，1.853888888888889GPUh；20次真实程序执行、5次正常退出。
- 5次超时、7次其他代码错误、2次pandas类别赋值、1次缺目标列；失败全保留。
- 本块64次API、0.143920179USD已结算；累计304次/0.718421106USD已结算。
  旧0.70USD未知责任继续保留，累计责任1.418421106USD，不重置用户100人民币/10USD总上限。
- 原SSH监视连接中断，原watch退出后，确认所有primary输出均不存在；随后只执行一次closeout。
  独立final和selection检查随后各执行一次。只读观察器11591已结束；没有重复提交或重写结果。
- Final检查是所选节点与外部grade一致性，不是原始submission数值重评分；原任务删除CSV的限制保留。

source tree：35711518b3b7262bccd3bebfdd2b4a4b7c726715；controller：aa4f13c2cc480f7ead84b1970b3511c5b6dd6a30。
根：/research/d7/spc/yzyang4/forets-repeat-20260912-zuvnt3oa。
公开回执：results/forets_repeat_20260912/；8份导出均远端先扫描凭据形状，0命中。

independent-final SHA256：8d7d97426828227bbdd5df758956f8245db74a8d962d9a6fd854012a7341bd9f。
independent-selection SHA256：82498f29b793e7ca43ee0d73bed4296112d3ae16265dfb9bea8692f26188d66a。
两seed汇总 SHA256：6d373c97fe91527b081b1b0308ed0c5c43a5876c946192c5ee7b7b5bb245beaa。

学长0910六包已隔离、24配置两版本的来源事实另见SENIOR_0910_INTAKE_STATUS_20260912.md；没有据此训练或揭开保护集。
