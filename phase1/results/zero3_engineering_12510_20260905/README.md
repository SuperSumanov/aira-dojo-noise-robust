# 新 critic 入口接入与双卡验收提交（2026-09-05）

本轮执行用户最新明确授权，不重复请求同一预算批准，不创建守护，不重跑已完成的G0。

## 当前实况

作业 **12510** 已在held状态核验并release，当前 **PENDING / Resources**，尚未运行。
结果前GPU代码固定为`d22a17f3f6e676432f59f46dcfd8e4418548267d`；双PRO6000/projgpu39、30分钟、
12CPU、mem=0、no-requeue。包括300秒结束等待和60秒调度余量，上界 **4320 GPU-seconds = 1.2 GPU·h**。
截至本回执`sacct`实际分配GPU秒为0。16:35左右香港时间的调度估计为**9月6日15:19:29**，不保证到点开始，也可能提前。
现场节点两张卡均已分配，没有第二个可见PRO6000节点可作等配置替代；未私自切换其它型号或重复占位。

验证对象是固定seed6、随机4433参数、BF16/ZeRO3 CPU-offload DeepSpeedCPUAdam的五条完整/截断/恢复轨迹。
不是1.7B/16K压力测量，不读取真实语料或权重，也不是G-reuse/scaling收益实验。

## 本轮完成的修复与实际检查

1. 提交前发现共享CPU参考模块导入时会清空`CUDA_VISIBLE_DEVICES`。仅在CPU独立入口保留这项设置，
   GPU导入后再核分配。20项本地入口测试通过；远端实际import也保留`0,1`，没有初始化CUDA。
2. 第一次远端Git fetch因登录节点直连GitHub被拒绝而停止，路径`submission-20260905-r1`保留失败。
   代理启动wrapper第一次返回1；改为按站点正常shell环境加载后`site_setup_exit=0`，新准备目录r2成功。
   两次均在GPU提交前，未产生失败GPU作业。
3. 远端完整相关测试 **101 passed in 11.27s**；26个checkout文件逐一对Git blob核SHA，固定依赖源码核验通过。
   真实预留64MiB（67108864 bytes）并核实际分配量后，仅移除了本次自建的临时检查文件；没有清理用户资产。
4. 已提交12510后，held检查因单节点显示为`NumNodes=1-1`而拒绝放行。原请求资源没有问题。
   修复checker接受等价的`1`/`1-1`且要求TRES node=1，另增加GPU型号/数量、工作目录和脚本路径核验；
   随后放行**同一个作业**，没有重提。实际release控制脚本SHA记录于`launch/VERIFIED_HELD.json`。

## 排队期间推进的接入工作

代码`d684d53eac617a32541ba61e145158274a5b252c`新增训练输入桥接：
已获准的纯训练Cards投影及G/L拓扑 → 复用现有CardEncoder等价编码 → 现有Endpoint/Pair与token计划 → consumer回调。
不新增排序规则，不做静默筛选，重复/跨任务/额外Cards/原始含grade Cards均拒绝；标签在计划之外另行绑定。
明确使用batch协议的`encoding_digest`，不能误用另一接口的同名SHA属性。

新增独立终态验收器：先核全部checkpoint清单和文件SHA，再在CPU加载本作业自生成的实际模型/优化器/RNG文件，
逐位比较连续训练与两种恢复结果。训练driver的“PASS”与哈希字符串不是唯一证据。
该验收器还需等待12510的真实输出；不会在本报告中预先宣称GPU或真实checkpoint已通过。

本地新增组合测试44通过、8跳过（没有Torch及一个symlink能力项）；随后在远端CPU完整运行：
**52 passed in 5.95s，0 skipped**。覆盖五臂编码/计划/批次连接、方向和顺序不变性、标签支持、
文件缺失/篡改/别名/链接/重复JSON，以及真实BF16值、dtype、shape、signed zero、NaN、优化器缺失和RNG差异。
远端目录`/tmp/zero3-followup-qova_jdt`；代码tar SHA为
`39b87a4f4e32a688e7547be5952970ba78b6c347a58969ba945622aa75c85bf5`。
这52项是组件测试，**不是新桥接已经在真实模型或合格语料上完成训练**。12510固定旧提交，不捎带修改排队作业。

## 可复核绑定

- 批准回执SHA：`5e8dca606f335dde507422afadf49f8d704c6325ce5a2ec259ac7478d191682b`
- READY SHA：`e87e58b04e61a316fcd893f0e8005484d9ccd8b00339f50bbb9fe0e6ae156138`
- RELEASED SHA：`e190cd44735a0880b9975fb22ac6886c6624b01b73d90fef205dc3f2ecbc76d6`
- 远端发出并本地复核的回执tar SHA：`27b205cecc3bd71ca5083971696d269f2baf6464bb1be283c81185d749a80b61`
- 解包文件的逐文件字节/SHA清单：`files.json`。同目录附scheduler/accounting/start_estimate及原始测试日志。

## 尚未解锁的真实效果工作

学长branch再次fetch仍为`b8d095180415957aa1bab31fa53ead1bba261c03`；这只说明该Git分支未变，
不推断所有共享位置都没有新上传。完整历史开发来源、run→experiment映射及真实生成/评分记录仍待生产端事实。
通用批准不能替代这些事实，也不能把七角色声明当成合格训练包。

因此目前不能声称新的跨seed收益、干净scaling或正式训练已启动。后续先完成真实ZeRO3验收与来源包物化，
再运行固定预算的开发效果闭环；保留first-960/Target-300/Target-522盲态及现有方法成功门。
