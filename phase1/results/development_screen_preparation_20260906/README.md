# 四fit开发准备与真实来源支持检查

2026-09-06，起点`404d63345469e87796317f35e48bebc61e2bd39c`。
用户批准按推荐推进，未将缺失来源或未量化GPU预算视为已解决。

## 已交付

- `g_reuse_development_screen_v1.json`：两方法、两seed的独立开发登记，不覆盖原五臂/保护确认协议。
- `g_reuse_development_screen_plan.py`：复用既有token planner，固定顺序为Lbudget6/full6/full7/Lbudget7；
  G端点必须属于同context的L执行端点人口。仅准备，不包含训练/读取/作业提交入口。
- S01–S24历史snapshot定位清单：从三个已固定结构产物生成。MD SHA
  `94a8a1f50bb0c6aa919ef2ad0940b6375a225b104f7c980c4175b64f60dc7495`；JSON SHA
  `7ccc2a066fc32956cb81b471d508a973a63f457a871babce01aa9f9f51591b1b`。
  本地副本核SHA相同，可直接私下发学长，不要求其访问我方研究盘；不公开个人路径。

## 实际核对的来源支持

固定84run、15任务、24保守组件、24recorded配置strata。逐task run数排序：
`[2,4,4,4,4,4,6,6,6,6,6,6,8,8,10]`；逐task组件数排序：
`[1,1,1,1,1,1,1,1,1,2,2,2,3,3,3]`。

仅6任务至少两个组件，3任务至少三个。这里的组件来自先前保守来源/hold闭包，不等同已确认scientific experiment。
这些计数只检查同task train/dev覆盖的必要支持，不给pair yield、准确率、统计功效或训练资格背书。
没有选split、打开journal/标签、改变旧hold；不能根据本结果删任务凑新结论。
这促使我们立即并行询问已有合格开发来源，而不是等待24份旧snapshot后才检查覆盖。

输入：ledger `8e48b4c6598cf8efe205fc6cba5cdd27d14621eb13fad42a7fd4180953da00d1`；
lineage `fe05dddcd4fe8a3f2208652ce51c9b06df9b9b8f57a5fa655d2029caddcf9981`；
84scope `fc13d25745c1c8ea408374741358137e9eb374b3b214e0c9f6d4b856b071464b`。
仅读取这三份已有结构JSON；源快照只查目录状态，不打开内容。原始安全回执随本目录保存。

## 验证范围

本地Python3.13、pytest8.4.0：

```text
python -m pytest -q phase1/tests/test_g_reuse_development_screen_plan.py phase1/tests/test_global_local_training_inputs.py phase1/tests/test_global_local_token_budget_plan.py phase1/tests/test_g_reuse_effect_protocol.py
67 passed in 0.66s
```

覆盖固定矩阵、独立既有plan复核、同执行端点复用拒绝控制、来源顺序/方向不影响计划、Lbaseline不索取G标签、
旧协议SHA不漂移。使用合成输入；不代表实卡、实际生产包或方法效果完成。
snapshot请求脚本实际SHA=`9e20a84361114f30307b5b224d97ebdd04ad769891d85a7607280b11c7a3c3c3`；
支持检查脚本SHA=`b8de09c7b1fd96660a13e466b77e5fe416adda6a91f3a101e9b3e6747bea1440`。
两者本轮是在/tmp执行的小型运维导出，非结果前Git固定的科学效果实验；脚本副本保留于operations，不冒充旧commit。

## 尚未发生

没有新model fit、GPU/API提交、开发accuracy读出或保护cohort访问；没有把局部同token cap称相同GPU耗时。
12535仍等待资源，暂估香港9月6日19:38:15，并非承诺。0904归档尚未成熟，未提前摄取。
科学关键路径仍是：可用来源→合格同版本实际构建→GPU/预算→四fit真实开发读出。
