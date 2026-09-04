# 固定前向输入换边：结构支持不足，不推进正式训练

2026-09-05香港凌晨，会话内提出、预先冻结、实现并在真实历史L-train上做完一次可行性检查。
不是GPU模型实验，不是新accuracy，不是“已证明所有关系重组无效”。

## 结果与裁决

两种形状2x8x8和4x8x4的计数相同；均保留4689个pair、4095个端点、32187742有效tokens、37次更新。
下表按seed汇总，不把双/四卡布局当成独立训练重复。

| seed | 现有批次改变pair数 | 共同按任务/配置分组后改变pair数 | 后者占比 | 涉及task | 每task至少20个改变pair的task数 |
|---|---:|---:|---:|---:|---:|
| 6 | 14 | 122 | 2.60% | 13 | 2 |
| 7 | 12 | 118 | 2.52% | 12 | 2 |
| 8 | 4 | 112 | 2.39% | 12 | 2 |

预先固定的优先级门是每seed/shape至少10%比较被改变、至少10个task各改变20对。
主候选全部不通过；不扩大microbatch/跨rank收集、不换seed或生成森林来追门。
这只是这个保守、同微批次、保留原生成森林的贪心构造支持不足，不是全部保度换边的最优上界，
也不推出较大批次、所有图方法或Global→Local没有效果。

独立BFS和集合核验显示：每个forward occurrence恰好参与一个loss项，度序列不变、无重复边，
原连通分量没有拆开；分组方案的incidence rank分别增加61/59/56。这些不是有效独立标签数或泛化收益。
只有loss索引发生变化，规划描述器未变；未实际运行模型，不能报告运行时/前向状态等价或训练加速。

分组还使padding描述量下降，但这是同时观察到的**探索性成本线索**，不是预注册效果终点，
不据此另开优化网格、修改G0或声称GPU节约。完整输入与布局量见cells.csv，不只发布漂亮数字。

## 对主线的实际影响

1. G-reuse→L仍是待来源/预算解锁的主候选；这次不改旧五臂、checkpoint、训练池或冻结文件。
2. 收窄主张：在相同执行端点集合和训练token预算下，监督组织的**整体训练方案**是否改善sibling决策。
   G-reuse与L仍有端点频次/任务配比差异，因此不能称已经单独验证“比较图拓扑效应”。
3. 正确G方向优于Ghash负控，不能单独证明正迁移；随机方向本身可能造成伤害。必须先赢同预算L、
   排除Lbudget过训（L1门）、比较G-only，按原跨seed/任务聚类与单任务主导规则联合报告。
4. 不再为这个低覆盖候选投入正式训练。若主线后来有真实收益，再研究机制；当前先完成已准备的受控主实验。
5. 新跨分量标签不能由旧pair二元方向推出来；需同一次可信execution-score及exact-config绑定。
   来源声明、同版本Cards/G/L和experiment-closed拆分未收到，本轮未自行补造或筛除有问题的run。

## 可复核证据

- exact code：`064f48a312a9e2f43ca3b9822cb1bfdbc2942caf`，先提交再执行。
- archive SHA：`00af3d051328753b26302592277c4d6e27dd553af55c9cb5764b0534f55ba708`。
- 远端根：`/tmp/fixed-forward-20260905-aTxd1p`；CPU Python3.11.15，标准库与固定旧planner。
- A/B rc均0、stderr均0；耗时55.40729812160134/49.178927480243146秒，完整记录runs.csv。
- 两次产物逐字节相同，receipt SHA：`10b5d604e5f66a3ac4ea6537fc13d12118707263c1f202d95781fa8adb6b8850`。
- 下载manifest的5文件、Git archive中7个绑定源码blob均核验；冻结v2/历史开发v1哈希未变。
- 本地Python3.13与远端Python3.11各9项单元检查通过，含有限差分、反向排列、tie与30个固定合成图。
  这些是实现验证，不算真实模型实验的seed或样本量。
- 只读精确白名单、凭据形状扫描、输入/源码前后SHA；未读取保护cohort，未加载模型或拟合、零GPU/API。
  历史JSON容器的未使用code/label字段经过解析，不能称整段原始字节完全未读；选择仅用身份/结构元数据。
- `manifest.json`仅覆盖远端原始5个文件，后加的cells.csv/publication_verification/live_status/README由Git绑定。

## 同时核查的实际状态

香港9月5日01:16：G0 12377仍PENDING/Resources、Runtime0，源5f3bc36干净；调度估计12:39:11开始，非保证。
4GiB存储测试及65依赖/5运行库哈希已绑定，但双卡训练尚未真正跑通，正式五臂15fits未启动。
学长fetch成功，head仍b8d095180415957aa1bab31fa53ead1bba261c03，无新commit/outcome；语料目录316归档，
LATEST bc9833d834fba65adbbf174301fe968c2c12da4eb8190a8f418ece58d0219456，619/960eligible，closure=false/config-v2=0。
摄取PID3884166已在9月4日07:04:03UTC正常完成145轮，现不存活；六小时heartbeat触发窗口也已过期。
没有把旧监控称为仍在持续摄取，没有重启失败Target522-rank，详见live_status.json。

实验设计技能促使本轮先固定单一旋钮、支持门和廉价验证；结果失败后停止这个候选，不回改门槛。
一次本地定位记忆文件误用了无日期文件名，报不存在后改读ACTIVE_WORK_SESSION_20260904.md及CONTEXT_HANDOFF_CURRENT.md；
不影响任何数据输入或产物。文献依据与预检范围见FIXED_FORWARD_REWIRE_PREFLIGHT_20260905.md。
