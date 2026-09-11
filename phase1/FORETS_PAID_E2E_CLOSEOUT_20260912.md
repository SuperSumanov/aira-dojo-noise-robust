# ForeTS收费同预算端到端：完整失败收尾

香港2026-09-12；独立复核时间2026-09-11 20:23:45.591463 UTC。

## 结论先行

本轮8个真实run已跑完，但**有效最终解为0/8**。两任务、两个seed、两臂都没有可读的最终选中解成绩，
因此不能计算critic相对随机的最终成绩收益。没有正收益结论，也不能把缺失记成零分并宣称两臂打平。
这是当前完整配置端到端可运行性失败，不是单纯的读出文件名问题，也不是对所有critic能力的否定。

之前进度中的“正常结束/没有失败”指控制器及worker进程成功退出；没有提前查看程序执行结果。
这不能等同于候选程序成功。这次收尾纠正该易混淆表述，后续汇报分开列进程完成率与有效最终解率。

## 实际对照与结果

固定生成器Qwen3 Coder Flash（OpenRouter/Alibaba），现成8B critic/16384上下文，原SIF/gpu28 RTX3090。
两臂只有选择规则不同：全池随机 vs critic top2内随机；6步上限、width4、300秒单次执行、3540秒worker等不变。
第二块在第一块结果未读取时提交；两块独立终态后一次性读取全部8槽位，没有挑任务/seed或补跑。

|任务|seed|随机进程|critic进程|随机有效最终解|critic有效最终解|最终成绩差|
|---|---:|---|---|---|---|---|
|leaf-classification|8|completed|completed|无|无|不可估计|
|leaf-classification|9|completed|completed|无|无|不可估计|
|spaceship-titanic|8|completed|completed|无|无|不可估计|
|spaceship-titanic|9|completed|completed|无|无|不可估计|

- 64个生成候选，24次被选候选执行、16次修复执行，共40次；全部exit1、全部被记录为buggy。
- 每run都是3个候选池（宽度4/3/1）、5次实际执行。6步配置包含根节点，修复也占步。
- 每个critic run有2个真正可剪枝池；合计8个池的top2边界均非打平。不能把当前失败解释为模型从未改变筛选。
- 没有最终eval事件；独立检查checkpoint journal、task-call回执、进程摘要与冻结读出一致。
- 不挑中途submission、不事后取轨迹最高分、不反转critic分数、不改top-k救旧结果。

## 失败在哪里

按每次执行的终端错误分类，一次执行只归一类；分类是事后诊断，不是新的效果终点。

|错误类型|执行次数|
|---|---:|
|LightGBM已移除/错误参数|14|
|达到300秒执行时限|6|
|Pandas categorical赋值错误|6|
|混合类型编码错误|2|
|实验性Imputer导入错误|2|
|缺目标列|2|
|其他代码错误|8|

直接在**原任务镜像**只读核实：LightGBM4.6.0、pandas2.1.4、scikit-learn1.9.0、numpy1.26.4、
catboost1.2.10、xgboost2.1.4、torch2.5.1+cu124。没有GPU计算或拟合，也没有更换镜像/Torch。
`lightgbm.train`的`verbose_eval`/`early_stopping_rounds`，以及`LGBMClassifier.fit`的
`verbose`/`early_stopping_rounds`，四项签名绑定都拒绝；实际接口提供callbacks。
原配置的available_packages仅列名称，没有提供版本/API信息。

这支持把**共同生成环境信息**列为优先修复项，但不证明它是所有失败的唯一原因：还有数据处理错误和超时。
现阶段不能说环境说明已修复可运行性，更不能把修复前后变化归为critic收益。

## 资源与证据

|作业|节点|分配秒数|GPU数|GPU·h|终态|
|---|---|---:|---:|---:|---|
|13088|gpu28|3135|2|1.7416666666666667|COMPLETED / 0:0|
|13112|gpu28|2730|2|1.5166666666666666|COMPLETED / 0:0|

总计 **3.2583333333333333 GPU·h**，含服务和闲置时间。124次API全部结算：120次真实operator传输、4次路由检查；
合计 **0.318775548 USD**，无未结预留。没有把账户余额写入报告，也没有把费用未知写成零。
原100人民币/19GPUh上限未超；没有追加GPU、重新初始化paid.sqlite或给旧矩阵新增槽位。

- 执行commit：`f051cfded55259d5320407a9e0269ab9141ab345`。
- 执行source tree：`f9087ae47470f7f1868c61405c3b827327f31c2c`。
- prepared SHA：`58558eed5abe1f793c77049572549c66de8c104255f8a13fa3c48e0a8b4d3593`。
- 远端根：`/research/d7/spc/yzyang4/forets-paid-20260911-oh3np7b8`。
- [冻结读出](results/forets_paid_e2e_20260912/summary.json)、[逐run结果](results/forets_paid_e2e_20260912/runs.csv)、
  [成本/执行量](results/forets_paid_e2e_20260912/runs_cost_work.csv)、
  [独立复核](results/forets_paid_e2e_20260912/independent-failure-verification.json)、
  [原镜像接口事实](results/forets_paid_e2e_20260912/image-api-facts.json)。

独立验证器不导入主读出器；重新查sacct、逐项核进程/终端错误/候选账本，并从只读SQLite整数费用独立求和。
费用/执行量补充6项小测试在本地和Linux通过；这些测试是软件正确性，不是性能结果。

## 修复顺序与边界

先把真实库版本/API事实提供给各生成/修复臂，保持任务镜像、critic和评分口径不动。
再用独立开发可运行性检查确认至少能形成有效最终解，之后才值得新seed的critic对照。
这属于共同实验条件修复，不是新算法或论文正结果；不能把筛掉失败代码后留下的子集当原八run成功。
当前只完成失败定位和环境事实准备，未部署新生成提示、未追加API或GPU来“救跑”。

学长已知0907、0909、0909/mcts网盘目录在19:51:45.958128 UTC列表无变化；不据此断言所有其他目录没有更新。
学长Git仍为065b0fbaa89e0eb663f2834ec768081f5d56394d，未修改其分支。保护cohort继续隔离。
