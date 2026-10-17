# 当前短交接：现场、边界和恢复动作

最后观察2026-10-18香港00:51；新用户窗口至HK03:30/UTC19:30。停止quota，选择R15小规模随机流选解资格。尚未提交GPU。
完整上一交接在Git d9ddd4951be9fe8b7b9f6b352fb00d315559eb37；原件不重读覆盖。

## 当前位置与授权

- checkout C:/Research/New/my_project/MLEvolve/_codex_tmp/publication-feedback-20261001，故意detached HEAD。
- 本次已fetch：myfork/phase1-value-critic=d9ddd4951be9fe8b7b9f6b352fb00d315559eb37；学长dojo-reproduce=e4d478350e704e8c5927eba566b2847aaa6dcbab，无新提交。
- 用户已统一批准限定实验，不重复索权；旧批不重开、失败不自动重试、无界试错不允许。新矩阵/成本/门已在会话给出。
- SSH yzyang4@linux5.cse.cuhk.edu.hk；PY=/research/d7/spc/yzyang4/venvs/aira/bin/python；SLURM_CONF=/opt1/slurm/gpu-slurm.conf。
- stage=/research/d7/spc/yzyang4/quota-queue-source-20261017-ymOz45；新root计划rng-selection-20261018-v1，尚未prepare。
- 本地Python=C:/Users/yanze/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe；本机无torch，用远端CPU做新hook测试。
- 最后队列16:44UTC仅Held12535，本人无活动GPU；gpu3 idle，gpu1/27/29 mix。勿把旧状态当实时，不碰Held。

## 本窗口已完成和待做

- 读方向/路线/近期提交和R4原证据；不再提泛化缓存/集成作为新方法。已核CRN/同步流/Net2Net/LEMONADE/HELIX近邻，链接见ROUTE。
- closed_rng_structure_20261018.py只读三个自有已闭合DEV批18770/18807/18997：Aerial66、Denoise35有效返回，DataLoader101、explicitgenerator0。不是101独立程序、不是实际排序噪声。
- 安全结构回执远端stage/rng-structure-20261018.safe.json SHA d9e239b93d062fe733eef326fadfa7fb143ba7cee8d52881af15346e7522293a。
- 固定来源18997每任务按episode/candidate时间取前2份不同有效源码；不按分数挑选、不换样本。已凭据先查后读，原源码不下载/发布。
- data_rng_coupling_20261018.py远端CPU自检通过：global顺序/增强均漂移，sampler顺序同/增强异，addressed均同；跨epoch变化、原global加记录器前后逐值一致。非GPU训练收益。
- rng_selection_readout_20261018.py本地合成检查通过：缺失不填、同选解不算提升、RMSE方向正确；不等于真实数据读出通过。
- rng_selection_pilot_20261018.py qualify会话51434退出0：实际factory32配置、4历史CUDA来源、公开数据hash过；候选0只有TTA重设seed，其余无全局seed重设。没有提交。
- 原任务SIF无GPU/无数据挂载的CPU hook自检会话20059退出0；样本优先键不含全集身份，子集变化保持公共输入相对顺序。宿主通过不替代镜像检查；镜像本轮也已通过，无候选训练。
- 精确矩阵32：24选解（2任务×2程序×2seed×3臂）+8共享global部署核验（4程序×2新seed）。4张gpu3、1h≤4GPUh，全启动/失败/空闲/清理计入；无模型服务/API/底座训练。
- 4101/4102只用于选解；先封选择回执，再读4103/4104共同部署分数。选解每臂同4次/任务；核验开销不是免费线上预算。
- 三臂global/sampler/addressed，反序选解块；源码、镜像、300s、2CPU、独占GPU固定。寻址只干预数据RNG，不把模型初始化/墙钟轨迹当完全受控。
- 门：完整32、CUDA/隔离/输入/干预/成本过；addressed在两个部署seed均比global/sampler去噪RMSE至少好.001且Aerial均不退。否则停此配方，不补seed/换源/重投。
- 固定库、新RNG但同DEV，仅探索资格；经典CRN非新颖，同库部署不是自适应LLM搜索。不能作顶会主张或泛化确认。
- 下一步完成资格及冻结source/plan，再一次提交；只读结构监视，结束后唯一读出+独立统计。当前无结果，不提前解读。

## 必须保留的关闭事实

- 19136在gpu3六卡32启动/31完整，FAILED1:0；29676GPU秒=8.243333333333334GPUh，清理true。source6db9d7c6，plan2736fb9326f62f3c83bc0cebc4854ba629991e5b5e4bb69e708aa91e24b74e7e。
- quota实际借用0/11/9/0、峰值4，干预生效；index26 readiness失败，底层原因未知。33重评分+独立14传输SHA和32分母核验通过，但完整性/原质量门false。
- 全16去噪描述性两次差+.00790502349919136/−.0006739912365923625；Aerial首轮−.00012026747486404421，末轮缺失不填。停止该配方，不称严格负确认或广义调度无用。
- 18770 FIFO/18807 cap2/18997静态准入均无稳定终分；19004未实际干预；19118未执行取消。所有旧批不补跑/改门，原件见ROUTE。
- 现有calibration/ensemble只属已用DEV的离线标签诊断，不是合法在线同信息收益；经典公式不是创新，未做真实常量预测查询。

## 硬边界

- 不读first960/Target300/522、D_val/officialtest、16560；不使用付费API、不训练agent底座、不改学长分支或用户dirty。
- 原兼容gpu1/3/27/28/29优先；不投projgpu39、不改镜像/Torch/退CPU；不绕保留节点和QOS。4TB至2027-08-30是授权非实时剩余。
- SCP退出0才执行；SSH脚本避免引号；原始源码/预测/标签只在远端，发布前显式文件清单+凭据扫描+文件名守卫。
- 未跟踪用户报告、_codex_tmp、pooling_host_compat_20261016.sh保留。短入口≤100/140/80，详细证据留Git，不创建长报告/新跟进。
