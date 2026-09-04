# 给学长：Global→Local 验证进展与最小解锁清单

我们仍在推进 **Decision Corpus + Predictor Benchmark**，近期优先验证一个具体机制：
相同训练预算下，先学习全局质量、再适配局部 sibling，能否优于只训练 local，以及只训练 global。
另有同样代码暴露、但替换 global 目标方向的负控。它不消除比较图构造本身可能携带的质量信息。
不是恢复多保真，也不是训练 agent 底座。

## 9月4日新增方法候选：复用同一批执行标签

新发现的关键控制问题是：旧G比L多3640个程序，即使训练tokens相同也可能多用了执行标签。
真实train结构复核找到3058对额外global比较，两端都已在L，覆盖28任务；完整G-reuse→L仍只有L的4095个端点。
其中2969条连接原L图中不同分量，不只是重复原pair，但这不代表新增独立标签或已经提高critic。
复用固定编码后，一次候选的token总量为54407806，原G→L为104863947；仅是规划输入成本，未测训练加速或效果。

建议在同版本包可用后优先检验这一更窄主张：**同一批程序/执行标签，不增加执行，而通过全局→局部的监督组织
改善sibling决策。** 主对照仍是同预算L，负控及三个seed保留；不再同时探索更多模型/loss旋钮。
复用池仍有143对记录配置不一致、193对来源未明（23对同时存在两问题）；我们没有自动筛掉它们训练。
请尽量在下述连贯开发包中保留可对应的L端点及其G比较，并绑定同一次执行/评分记录；不要为了凑3058或2745
这些诊断数字修改生产规则。若无法修复历史来源，明确说明并提供新的连贯开发包即可。
完整发现、四格来源表和对照边界：`LABEL_REUSE_FINDINGS_20260904.md`。这仍是效果待验证候选，不是已获正收益。

14:27补充：新候选的五臂×三seed×两种并行形状共30份完整pair消费计划已逐一独立重放通过。
L1与Lbudget的前37步在输入/归一化/LR层面完全相同。因此未来若真实checkpoint状态与派生评估绑定通过，
可以保留15个评估单元、以12条训练流共享L1前缀，少约12.9%的重复训练tokens。当前没有真正训练或少花GPU小时，
不能直接改名checkpoint，不能在Lbudget继续前评估L1，模型检查点数/存储也不会自动减少。
这项准备旨在降低接下来严格对照的成本，不是新的模型正结果；同版本来源交付仍是最关键的解锁项。
证据：`results/historical_reuse_execution_20260904/README.md`。

## 已经能做什么

五臂、三个seed的受控计划与历史输入编码已核验；阶段顺序、梯度归一化、实际Accelerate保存/恢复在
合成CPU轨迹上通过。真实reward-model、ZeRO3/bf16仍待获准接入验证，不等于生产训练已经就绪。
这些是执行准备，**尚无新增跨seed正收益，也没有新的干净scaling确认**。香港9月4日13时更新：双卡G0
（job12288）在获配4秒后被源码干净门拦截，尚未训练；原因是我们之前清理默认环境后遗漏未跟踪锁文件。
该文件已原样隔离保留，源码/模型/输入/运行库重新验证不变。用户新批准后13:16提交12377，双卡117分钟，
14:02核验仍PENDING/Resources，最新估计9月5日12:38:50开跑（非保证）；双卡实际训练仍未验证。
G0只用于估算真实训练成本；正式15 fits尚未启动。接口可复用，不再重复堆合成测试。

## 今天在真实候选数据上查清的阻塞

对当前历史L=4689对、G候选=9392对，复用已有run→真实batch映射，双生产与独立双复核一致：

- G中415对的card记录配置不一致；L没有这项不一致。这里检查client、hardware、time_limit、execution_timeout。
- G中676对、L中365对无法唯一连接到来源batch；两池都涉及19个歧义run和6个缺失run。
- 109个已知L-train来源batch中，79个在训练边界外也有run。外部未区分dev/test/unused，**不能直接叫测试泄漏**，
  但“run无交集”本身不够证明完整experiment隔离。

另查Git的LFS指针发现，现有执行诊断用的是92a9651的旧Cards，而G来自ac008af的batch-value文件。
二者不是同一版本的完整生成包；这可能影响配置对应，但尚不能归因415个不一致全由版本差造成。
注意G来源是`batch_value_pairs_filtered_runsplit.jsonl`，不是另一份`value_pairs_hardware_timelimit_gap_filtered_runsplit.jsonl`。
没有偷偷换文件、过滤问题对或把新Cards混进冻结评测。

## 最有用的下一项交付

请优先给一个**同一producer版本、历史开发专用**的可复现包，而不只是再上传更多pair行：

1. Cards、G、L、split及生成命令/配置各自的完整SHA/LFS OID、producer commit；所有输入属于同一明确来源。
   G/L物理train-only文件与dev/test文件分开。需要说明哪些旧实验曾接触评测，不能把它们改叫全新确认集。
2. 每run一行的不可变来源声明：`run_id, task, launch_date, source_date, batch_id, archive_path,
   archive_sha256, journal_member, producer_commit, producer_instance_id`，按run_id排序，无额外字段。
   `launch_date`是run后缀日期，`source_date`是归档日期，**二者允许不同**；journal_member给出完整路径。
   producer_instance_id须来自实际执行记录，不能由我们临时按日期/run名生成替代；没有权威记录就声明无法修复。
   新入口`phase1/validate_senior_source_provenance_v2.py`；字段说明见`phase1/SOURCE_DECLARATION_V2_20260904.md`。
   旧验收器不改；v2只验声明的唯一header与哈希，不替代执行配置和物理实例的权威证明，不自动解除旧S0。
3. 实际生成配置的来源绑定，并按完整experiment划分train/dev/frozen；配对后仍验证pair/card/run零交集。
   本轮不会替你删除问题样本；如果需要新历史开发子集，我们先固定新协议再物化，不改旧S0裁决。

未来干净scaling另走 **outcome-before config-v2**：现成补丁在
`phase1/upstream_patches/0001-Add-prospective-config-v2-producer-hook-18-tests.patch`，默认关闭，需维护者审阅和启用。
本次确认最新b8d0951的四个相关目标路径与此前已验证5baccb1无差异；hook仍未并入。既有19项兼容测试是之前的，
这次只复查Git路径/对象，不把它说成重新跑过测试。补丁不更改搜索策略、模型或预算；它本身不提供历史来源修复。
请对**今后的新run**启用并标明稳定generator release，不要事后回填成outcome-before。

本次修正不是凭空放宽日期门：已有636个唯一来源中99个的两种日期确实不同，双生产和独立复算一致。
它们原本已有唯一来源，**不是多恢复99个run**；当前候选中的19个歧义/6个缺失run仍需真实来源补齐。
新接口在Linux上36项检查通过，未读取真实归档payload或前瞻评测。尚没有收到新真实来源声明并通过验收。

来源门通过后，我方重算实际token预算，拿G0实测成本列出正式矩阵/GPU·h，再申请一次明确授权。
保留原效果门：跨seed方向一致、同预算paired任务聚类区间、全局标签负控和单任务主导检查。
如果不产生可靠正效应就如实报告；不会通过修改评估口径制造提升。

证据：`phase1/results/historical_global_local_source_gate_20260904/`；正式结构回执SHA
`e34d9f1432fe71bc4c9de8e9074dc47eaf84569f94478e06f1070c778146bb07`。
这份报告可以直接转发；本轮没有代你向学长发消息、改写其分支或部署其producer。
