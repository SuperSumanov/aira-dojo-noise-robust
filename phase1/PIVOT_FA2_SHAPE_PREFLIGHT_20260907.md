# FA2修复后的同尺寸验收：执行前矩阵

## 2026-09-07修订：原未运行后继入口改为显式R4续编绑定

编辑时间纠正：本段原写UTC23:07，实际commit4cb39e0为UTC23:04:29。事实时间以原回执为准。
后续实际Linux224测试通过（23.74秒），源码4cb39e0；回执已导出，不再是Linux待做。
独立完整尺寸postflight另在6b2af78完成38项实际Linux测试；均非真实GPU验收。

以下旧12641成功前提已失败，不得据旧段提交。12641实际FAILED/2126秒，保留完整失败证据；
12648在独立held核验6608源码/32对象后释放，UTC23:01观测gpu37 RUNNING。本段不声称它已构建完成。
后继改用flash-attn-build-20260907-r4，source15402474dec5b5da1e376d3c812f53fe416c5c0b，
构建脚本15353d409ceb52c25a9aa7f6080a90849839d5f571bab359b132d29489055893，
PRIOR_VERIFIED 43def888311cc5156a91980af6fb1ce46381fcf70a8d769d45e7e5441a0bac7d。
新exclusive后继目录submission-20260907-fa2-r4，原从未执行的R3后继入口由本次commit取代。
使用单独resumed binder，原fresh binder明确拒绝resumed classification；generic overlay仅绑定字节/ABI，不授予成功资格。
完整核32旧对象、13失败证据、15副本、ninja graph、独立held回执及3个续编stage；Slurm成功与GPU数学仍分开验证。
实际9423GPU秒，加续编保守5760及双卡3840，19023≤21600（本轮明确扩为6GPUh工程上限）。
模型/上下文/批次/seed/数值容差/driver/真实来源规则逐项未变；双卡尚未提交。
本地65通过/3跳过（两项无Torch、一项Windows symlink），实际Linux仍须复测，不能据本地称GPU通过。

## 以下为修订前的历史设计记录

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
