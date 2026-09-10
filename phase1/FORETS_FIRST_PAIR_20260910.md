# 首个有效同预算对照：critic本次没有收益

这是2026-09-10的探索结果，不是确认实验。保护cohort未读取，也未训练新模型。

## 实际结果

13004在gpu28双3090运行，香港21:52:03至22:35:00；Slurm为COMPLETED。
入口0656869fc6863d056a23cac0b2f9f41a59f2f6ad，组合源码树bbd22e323d6321925a145c12bdc02445c1ad80f4。
两臂同原SIF、生成器、seed、搜索设置及请求/时间上限，仅selector不同。没有新训练。

|leaf-classification / seed6|全池随机|critic top2内随机|
|---|---:|---:|
|最终选中解的外部log loss（低好）|0.66022|2.5208|
|进程秒数|1041.0410418610554|1348.9142407530453|
|预留API尝试数|12|12|
|成功响应|9|8|
|HTTP502|2|2|
|Timeout|1|2|
|有效最终成绩|是|是|

正向分差定义random−critic，结果为**-1.86058**。本对critic更差，而且耗时更长。
两侧均有单一合法最终EVAL，选中节点在各自checkpoint/journal.jsonl中唯一对应，
节点is_buggy=false、metric_info.score与EVAL相同。不是最后一次grading report或事后外部最优值。
运行配置再次核对通过；从runtime manifest重算的读出与原summary完全相同。

仅一个任务/seed，无可估跨seed方差，不给显著性或普遍结论。原8槽位保留，当前首阶段只启动2个，
其余6个未运行；不能把它们写成失败，也不能用这个结果事后改写首阶段停止规则。
停止首对边界是在看到结果前确定的，与正负方向无关。

## 不是哪里出了问题

- 这轮没有因为接口错误取消兄弟候选：17成功响应、4个502、3次Timeout均有记录；
  重试没有突破每run40次上限。成功响应不等于有效程序，费用未知仍为null。
- critic真的参与：首批3候选中做过一次有效剪枝，三个分数非全同、top2边界无打平，
  保存的选择与固定selector重放一致。不能用“没调用/全部打平”解释这轮较差的最终分。
- 在critic自己的候选池上，同种子随机槽位仍在top2内，但重新在top2抽样后槽位发生变化。
  这不是另一个实际random run的反事实成绩，未执行候选也没有真值，不能由此断言删错候选。

## 当前结果能推动的下一步

真实闭环已打通；这是一项执行进展，不是模型正收益。当前4步里根节点占一步，debug又会占步；
本对两臂各只有两批候选，critic只有一次实质筛选机会，见FORETS_SHORT_HORIZON_20260910.md。
不立刻上更大模型，不因为一个seed输就换指标/挑任务，也不把增强筛选力度的下一轮混入本对。

随机臂仍见No OpenCL device，critic臂未见；随机臂仍取得更好最终分。
因此不能把本次critic落后归因于“它遇到OpenCL故障”。库故障值得修复，但这是一项共同环境工作。
独立检查已确认ICD目录缺失；13009又发现GPU0分配下GPU9设备也可打开，故在调用OpenCL前停止。
计划在新的同镜像A/B诊断中，双方统一只读遮蔽未分配设备，再比较仅有/没有ICD绑定。
该工作不修改13004结果；人工LightGBM库计算即使通过，也不是端到端收益或完整sandbox安全证明。

## 资源与可复核产物

13004分配GPU时=2577×2/3600=1.4316666666666666；连同前一次12977为2.0522222222222224。
这些不包含独立OpenCL诊断。critic启动162.9721515569836秒，已在整体分配成本内，不重复相加。
service_srun_exited=true、原controller的service_cleanup_confirmed=false；后续独立sacct确认所有step终态，
不篡改旧清理字段。Slurm正常完成也不等于整个原8run矩阵已完成。

- `results/forets_resilience_20260910/readout/{runs.csv,pairs.csv,summary.json,costs.partial.json}`。
- `selection-diagnostic.json`、`campaign.finished.json`、`terminal-structure.json`位于上述结果目录。
- summary SHA256：9f3578b14acb2aeec383569225d3fb30360a79105e0b3ad5c27c05f39458b74c。
- campaign.finished SHA256：37cc6748fab3def3d2a68b14dfc420a9262c39321601f14867f5e244e92d82da。

不修改学长dojo-reproduce分支；本报告及代码只发布我方phase1-value-critic。

## 同日晚间环境排查终态

13007、13009、13010已结束，分别分配1、217、2秒单卡，实际共0.06111111111111111 GPUh。
13007修正了诊断查询字段不兼容；后两次发现只分配GPU0却仍可打开GPU9，所以都在OpenCL调用前停止。
请求的只读遮蔽未生效。无GPU的设备绑定复现给出明确警告：绑定到/dev时，来源与目的路径必须相同。
当前运行时为Singularity CE 4.3.0+77-g2244f30fe；登录机没有找到nvidia-container-cli，计算节点是否有尚未确认。

这些证据不说明13004曾使用GPU9，也不能把设备可访问性当已发生的硬件混用。它们说明原定的
OpenCL单卡隔离验证尚未通过；未执行OpenCL或新增模型/任务训练，未升级镜像或CPU回退。
已请用户向学长/管理员确认GPU9是否按集群约定共享、以及受支持的单卡OpenCL暴露方式。
等待此项外部事实，不再用新GPU作业反复撞同一限制。结果与失败均保留，不称作修复成功。
