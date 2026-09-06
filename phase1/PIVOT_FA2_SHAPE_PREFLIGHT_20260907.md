# FA2修复后的同尺寸验收：执行前矩阵

2026-09-07。用户授权六小时会话内合理决策。本文件不授权真实效果数据、保护确认人口或底座更新。
构建12641与后继尺寸作业分别核验，不能把前者编译成功当作后者通过。

## 不改变的科学与工程负载

独立critic：Qwen3-1.7B-Base固定ea980cb snapshot，1720577025参数；双PRO6000/projgpu39、12CPU、mem0，
BF16/FA2/ZeRO3/CPUAdam，16384context，每卡microbatch8、累积8、seed6。
合成G一步保存→新进程恢复→L一步保存，两个完整检查点；原driver逐字不改。
不是效果fit，不是完整尺寸uninterrupted-vs-resumed parity（4433参数tiny版已独立验收）。

唯一依赖修复是从12641产物绑定独立FA2 overlay，不修改原r5环境、不降后端或缩短长度。
新exclusive输出submission-20260907-fa2；旧12577失败、12535held及各构建失败记录保留。

## 时间与GPU预算

新双卡作业1个，26min，driver1200秒；kernel预检120秒且结束后再核剩余时间。
两卡保守上限3840GPU秒。历史实际7297GPU秒，加12641构建上限2760和尺寸上限3840，
合计13897≤14400。准备时从Slurm逐项重核历史终态，12641必须COMPLETED/0:0并使用实际耗时入账。
没有自动retry/requeue；未先通过构建产物、CPU、模型、容量、held独立复核，不release尺寸作业。

## 13项预检逐项落实

1. 产物旋钮：保留实际attention backend、参数量、dtype、设备、全部配置和code/model/build SHA。
2. 新路径：CPU负控覆盖构建stage失败/漂移、overlay、作用域恢复、预算终态、两卡数值回执；真实Linux复测才提交。
3. 测试集查重：本工程无真实数据，不触碰任何test，不能据合成输入声明开发隔离。
4. 分布：双rank及两个阶段逐项验收；不从单行COMPLETED推断所有阶段成功。
5. 评估配平：无科学评估；不输出accuracy或utility。
6. 保存：两个完整ZeRO3模型/优化器/RNG/cursor检查点，实际64GiB预分配与释放两次门。
7. 泄漏：工程只允许固定官方模型、代码、合成输入；实际文件trace独立核验保护路径访问。
8. RNG：固定seed6，恢复前故意错置RNG以核实际恢复；原已验收consumer保持不变。
9. 发布：staged文件名和内容凭据扫描；不公开语料、环境或私有identity。
10. 墙钟：26min包含kernel、容量和driver；kernel后elapsed+1200+60≤1560，否则停止，不能缩短driver。
11. 训练功效：工程不回答效果/功效；四fit仍需完整来源、隔离和真实token成本，不能用本轮替代。
12. 退出码：shell finish第一行保存真实rc；超时或缺终态不进入后继，不依据最后echo判断成功。
13. 抽签：未扩真实数据/改变hold/抽签；固定84run来源诊断与工程严格分离。

FA2正确性先于模型初始化：两卡分别执行BF16/GQA/causal的dense129与varlen31+97，
forward/dq/dk/dv对FP32参考均须relative-L2≤0.02且max-absolute≤0.05；16K实际前后向有限。
阈值沿用结果前冻结值，不事后调参。只在全部检查、完整尺寸save/restore与独立终态审计通过后称工程通过。

## 当前状态

本地相关CPU单测52通过、3因无Torch跳过；不冒称Linux/GPU已通过。
12641在UTC22:09:01观测RUNNING/gpu37；后继尺寸作业尚未提交。
当前无新的critic收益或scaling结果，来源准入仍空。
