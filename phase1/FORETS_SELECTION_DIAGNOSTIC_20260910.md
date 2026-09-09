# ForeTS：区分有效筛选、打平和没有筛选机会

2026-09-10（香港）；只为既定12933实验补充结果解释，不改变已提交入口或8run主指标。

## 问题与解释边界

主要问题仍是“同预算下critic能否改善最终选中解的外部成绩”。仅观察critic臂选了不同候选不够：
当所有分数完全相同时，当前稳定排序按原槽位保留前top-k，仍可能与全池随机选择不同。
这可能是位置规则的作用，不能当成学到质量区分。候选数不超过top-k时，候选范围完全没缩小。

新增工具 `forets_selection_diagnostic.py` 只读取本轮显式开发包，按run/批次给出：

- 有记录的选择数；生成/评分未完成保留为未知，不填成“无干预”。
- 候选是否多于top-k；top-k边界是否严格分离、是否打平、是否所有分数相同。
- 用冻结selector对同一批候选做纯函数重放，核实际选中槽位与记录是否一致。
- 相同批次、相同选择随机源的全池随机槽位是否不同、是否被top-k排除。
- 选中候选是否实际完成执行。只记录选择但跳过预算，不能算执行成功。

“同批次随机槽位”不是另一个臂的轨迹，更不是没执行候选的反事实最终成绩。
两臂各自生成的代码可能不同；不跨臂比较槽位身份，不推算未知代码质量、不计算ranking accuracy。
分数打平使用精确相等，不在看过数据后调epsilon；边界以外的局部打平不混作边界打平。
这些诊断不能挽救失败的主指标；不依据它改本轮top-k、seed、生成器、默认关闭的bypass或选胜者。

## 读取范围与调用时机

唯一包：`/research/d7/spc/yzyang4/forets-e2e-package-20260910-SWMoh2/package-c`，job12933、source-v5不变。
先由调用者独立核对sacct已终止、无活动writer，再运行；finished文件自身不证明Slurm已终止。
工具要求started/finished、提交身份与完整8run清单；核准备配置hash与runtime对应身份，
但不将准备配置hash冒充pool重新序列化的字节hash。运行侧实际配置等价检查仍由冻结controller负责。
只读每个run下固定batch-0至batch-3的SQLite；不递归找别的语料或模型。
缺批次可能是debug跳步、提前结束、失败或未开始，不猜原因；错误/锁/哈希异常保留为invalid。
不导出代码、prompt、候选身份或critic数值，不打开最终成绩、标签或任何保护cohort。

独立工具部署目录：`/research/d7/spc/yzyang4/forets-selection-diagnostic-20260910-6uwXNX`。
工具未接入或改写排队作业，**目前尚未对真实候选运行诊断**。

```text
/research/d7/spc/yzyang4/venvs/aira/bin/python -B /research/d7/spc/yzyang4/forets-selection-diagnostic-20260910-6uwXNX/forets_selection_diagnostic.py --package /research/d7/spc/yzyang4/forets-e2e-package-20260910-SWMoh2/package-c --output <新的独立诊断JSON路径>
```

## 已实际验证

- 本地12项人工单元测试通过，覆盖边界打平/全打平/全池、部分生成、无评分随机臂、错误绑定、缺分、
  重放不一致、只读SQLite及完整8run缺项保留。初次测试有2个fixture连接未关闭的清理错误，
  修正测试代码显式关闭后12项通过；生产reader已显式关闭，不是远端任务失败。
- 2026-09-09 22:36:06 UTC远端6项定向检查通过：使用冻结source-v5的真实schema-4账本写入器，
  但候选/分数是人工输入，全部未执行任务。新reader读前读后SQLite字节一致。
- 真实12933包在未完成时被拒绝，未读取真实候选。0新增GPU、模型加载、外部API或真实task。
- 回执：`results/forets_e2e_20260910/selection-diagnostic-integration.json`。
- 2026-09-09 22:34:35 UTC最新队列检查仍PENDING(Resources)、RunTime0、无started/finished；
  暂估香港9月10日19:59:12启动，非承诺。学长分支仍065b0fba，未修改。

下一步先等12933的实际执行和原最终成绩读出；必要时用此诊断解释机制。
本轮补强的是“结果出来后能区分为什么”，没有新的critic收益、干净scaling或e2e正结果。
