# 给学长：Global→Local 验证进展与最小解锁清单

我们仍在推进 **Decision Corpus + Predictor Benchmark**，近期优先验证一个具体机制：
相同训练预算下，先学习全局质量、再适配局部 sibling，能否优于只训练 local，以及只训练 global。
另有同样代码暴露、但移除真实 global 质量标签的负控。不是恢复多保真，也不是训练 agent 底座。

## 已经能做什么

五臂、三个seed的受控计划与历史输入编码已核验；阶段顺序、梯度归一化、实际Accelerate保存/恢复在
合成CPU轨迹上通过。真实reward-model、ZeRO3/bf16仍待获准接入验证，不等于生产训练已经就绪。
这些是执行准备，**尚无新增跨seed正收益，也没有新的干净scaling确认**。双卡G0（job12288）仍排队，
只用于估算真实训练成本；正式15 fits尚未启动。接口可复用，不再重复堆合成测试。

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
2. `run_id → source-date、batch-id、archive path/SHA、producer commit`的不可变映射。
   对旧缺失/歧义来源作显式修复或声明无法修复；不要从task/date/config猜身份。已有验收器：
   `phase1/validate_senior_source_provenance_manifest.py`。
3. 实际生成配置的来源绑定，并按完整experiment划分train/dev/frozen；配对后仍验证pair/card/run零交集。
   本轮不会替你删除问题样本；如果需要新历史开发子集，我们先固定新协议再物化，不改旧S0裁决。

未来干净scaling另走 **outcome-before config-v2**：现成补丁在
`phase1/upstream_patches/0001-Add-prospective-config-v2-producer-hook-18-tests.patch`，默认关闭，需维护者审阅和启用。
本次确认最新b8d0951的四个相关目标路径与此前已验证5baccb1无差异；hook仍未并入。既有19项兼容测试是之前的，
这次只复查Git路径/对象，不把它说成重新跑过测试。补丁不更改搜索策略、模型或预算；它本身不提供历史来源修复。
请对**今后的新run**启用并标明稳定generator release，不要事后回填成outcome-before。

来源门通过后，我方重算实际token预算，拿G0实测成本列出正式矩阵/GPU·h，再申请一次明确授权。
保留原效果门：跨seed方向一致、同预算paired任务聚类区间、全局标签负控和单任务主导检查。
如果不产生可靠正效应就如实报告；不会通过修改评估口径制造提升。

证据：`phase1/results/historical_global_local_source_gate_20260904/`；正式结构回执SHA
`e34d9f1432fe71bc4c9de8e9074dc47eaf84569f94478e06f1070c778146bb07`。
这份报告可以直接转发；本轮没有代你向学长发消息、改写其分支或部署其producer。
