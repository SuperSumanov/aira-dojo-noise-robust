# 输入桥接到真实critic生命周期：结果前工程计划

本轮用户要求继续剩余工作；承接8f48365，同范围合理修复不再重复审批。
12510保留原GPU commit/预算/配置，不将新代码塞入排队作业，不提交第二个GPU作业。

## 修复与问题

上一版桥接要求提供G/L全部标签，即便Ghash计划不使用真实G方向。它在批次函数内没有读取G truth，
但上游仍须提供G标签，不满足冻结协议的完整边界。改为先根据已验证计划计算需要的label keys，
只接收当前臂实际需要的真标签；Ghash仅接收L。拒绝额外标签，不静默丢弃。

本轮要回答：投影Cards经过真实编码、计划和consumer后，实际随机critic的AdamW更新、保存和恢复
能否仍保持逐位一致？不是再跑旧fixture的已有结果，也不是在真实语料上找效果。

## 固定矩阵与预算

- 两个CPU进程、每进程Torch/BLAS一线程，无CUDA；固定R5 runtime和原hash-bound senior reward class。
- 随机4433参数Qwen3，float32、AdamW、dropout0.1、seed6；新合成Cards共48端点，G11/L13对。
- 使用8-token head/tail截断，与原CardEncoder逐条独立比较；不加载预训练模型或真实语料。
- G_to_L与Ghash_to_L各full4、prefix2/resume2、prefix3/resume3，执行A/B两次；20条工程轨迹。
- 复用已有CriticSession生命周期worker，只增加显式inputs_factory，不重写训练/保存逻辑。
- 单个远端CPU wrapper上限600秒（含两次完整运行、检查与退出）；不增加GPU/API预算。

## 验收

结果前固定：计划与全局hash臂输入一致、Ghash无真实G标签访问、真实token等于原encoder、
prefix+resume消费序列等于完整训练、模型/AdamW/各rank RNG逐位一致、A/B结构产物逐字节一致。
独立验收读取已核SHA的自生成checkpoint实际张量，不只相信driver的hash或PASS；保留失败、trace和确切commit。
来源资格仍由外部真实生产记录决定；这一步通过不代表合格数据包或BF16 ZeRO3 GPU验证通过。

## 首轮诊断后的样例修正

c0dc128已启动的首轮使用共同代码尾部，经静态检查发现48端点截断后只剩1种编码。
该轮仅保留为退化输入诊断，不作为新输入桥接的正式通过证据。修改尾部保留来源/序号/端点标识，
在模型初始化前强制48种不同编码；原seed、参数、算法、轨迹和逐位验收标准不改。
开发单元测试曾因外来plan被TokenPlanVerificationError拒绝、而测试期待PlanError而失败1项；
接口已统一转换成固定reason的PlanError，23项本地测试通过。
