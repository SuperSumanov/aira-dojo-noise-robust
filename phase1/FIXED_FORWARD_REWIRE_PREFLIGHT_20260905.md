# 固定前向输入的比较换边：一次历史结构可行性检查

状态：候选设计，未采用，不改冻结v2/历史开发v1，也不是训练申请。
先提交本文件和源码，再接触本次真实结构结果。只读历史L-train与旧Cards的元数据，
不使用G候选、模型、分数、gap、预测或protected cohort。不把已有pair方向当新跨分量比较标签。

## 假设与单一旋钮

G-reuse保持端点集合，却不保持每个端点的出现频次。本候选在同一rank微批次中
把(a,b),(c,d)改为(a,c),(b,d)，只改loss索引，不重排/复制/再编码任何forward occurrence。
双方因此共享任务组成、每端点次数、输入顺序、padding、有效tokens、更新归一化和LR计划。
这里检验的是输入/图必要条件，不证明模型运行时状态或GPU等价，更不证明效果。

保留由canonical endpoint ID次序确定的原图生成森林，只换两条非森林边，且两条边在
当前图不同分量、四端点具有相同task与四项非空记录配置。按batch和pair-slot顺序贪心，
每个原pair最多换一次；两条新边连起两个原分量。不会声称此贪心最大化支持。
候选ID仅远端内存使用，不发布loss索引/训练池；原图构造可能含质量筛选，两臂共同继承。

## 固定矩阵、停止线

- seed固定6/7/8；形状2x8x8、4x8x4；各只遍历L一次，不fit。
- 主候选stratum_shared：双方共同按task/config分组，组间按seed哈希排序，组内保留旧hash顺序。
- 兼容性对照legacy：原L输入次序，不改旧planner。两种方式均必须完整报告，不挑最好seed/形状。
- 使用旧partial-layout实现，最后不足128的更新保留所有样本；只作一次L-pass的结构诊断，
  warmup设1仅产生布局对象，其LR字段不作为未来超参建议。
- 主候选每个seed/shape至少改变10%原pair，且至少10个task各改变20对，否则不建议为此
  严格微批次候选申请正式训练。此线是事前工作优先级线，不是统计功效或显著性保证。
- 不因失败扩大microbatch、跨rank收集、改seed、取消配置约束或重选生成森林。

## 验证与计算约束

依赖仅Python标准库及已有纯planner；CPU一次A/B，每个子进程300秒上限，总计不超过10分钟。
独立BFS/集合核验：输入occurrence每个恰好使用一次、无重复新边、度序列精确、原分量不拆开、
分量减少数=换边次数；合成loss有限差分及反向排列测试。A/B字节与输入/源码前后SHA相等。
固定历史train文件及cached encoding绑定；credential-first扫描，guard拒绝未列数据与写入/网络。
Python guard不是OS隔离；JSON解析会把历史容器中未使用的label/code字段读入内存，不能宣称字节未读。
零GPU/API/model-fit；未读first960/Target300/522；不中途打开旧test，也不物化训练池。

## 将来验证需要什么

若结构支持足够，仍需要同版本来源与experiment-closed gate、实际前向独立编码的训练adapter、
可信每端点execution-score绑定、完整训练矩阵/GPU小时批准。仅有原pair二元方向不能确定跨分量顺序。
候选建议未来精确平分tie用BCE target=.5而非删样，非有限grade整项预检失败，不按效果择样；
这项尚未采用，不能改写冻结旧协议。科学确认仍须跨seed同预算收益及真实搜索任务效益。

## 文献与适用边界

保度双边交换不是新算法：[NetworkX double_edge_swap](https://networkx.org/documentation/stable/reference/algorithms/generated/networkx.algorithms.swap.double_edge_swap.html)。
比较图结构影响排序估计已有[Graph Resistance and Learning from Pairwise Comparisons](https://arxiv.org/abs/1902.00141)。
该文研究重复含噪BTL比较，不直接证明复用确定执行分数训练神经critic的收益；图rank不等于独立标签数。
本轮只判断一个更公平的监督关系对照能否落地，不声明first/novel/scoop-safe。
