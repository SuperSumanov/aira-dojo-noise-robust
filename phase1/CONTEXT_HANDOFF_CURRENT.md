# 当前短交接

## 2026-10-03 14:35香港（06:35UTC）：V6作业15414 RUNNING/gpu3；V5已完整闭合

用户本轮批准新方向和自主决策，要求完整约四小时工作；窗口13:37—17:37香港。唯一方向入口0L418。只做这一次阶段提示修正V6，不再扫提示/加GPU批次。预算此前七作业2.3494444444444444GPUh＋V6最大5.333333333333333GPUh＝7.682777777777778GPUh，≤原8GPUh。

### 当前唯一活跃作业

- **15414**，14:35香港squeue实测RUNNING/gpu3/0:24；服务加载中、0请求、无controller错误。launch session35816已exit0；无活动工具session。**不要重提、不要重跑prepare/freeze/CPU。** 四RTX3090，2服务+2执行，最长80分钟至约15:55香港。
- root /research/d7/spc/yzyang4/automatic-specification-20261003-gpu3-v6；plan **71340fc4a5fb97f09fa1dc31b5189500bffef3e73b68382a6bff9b628b61e154**，baseGit392321794b3bbf02a99a5bf1bc70355bb5ca80b4。
- source B/automatic_specification_v6_20261003.py（冻结运行副本root/task_feedback_real_20261001.py）；本地publication/phase1/scripts同名。2新first-valid根seed105101/105102，再12比较seed105201/105211（Pizza）、105202/105212（Spooky）。600秒/4调用/4096tokens/代码300秒，wrapper RNG42。
- 修正只在比较提示：所有臂显式CURRENT MODEL CALL；B/C首调用PLAN要求仅call1，后续明确实施/检查已有方案。COMMON/RULES、动作菜单、parser、wrapper、源冻结、compat均不变。没有加Pizza人工修法，也没有用V5旧来源。两新来源任一失败即停，不换seed/救回；同一开发数据，不能把V5→V6当纯提示因果对照或独立确认。
- 原主门不变：4可比三元组、初态预测同SHA，B−A和B−C在两任务中位均正、每seed无负差、B确有新改善且方案落实。达不到不扩大。仍须区分已知规则重发现和新颖机制。

### 已完成预检与接下来命令

远端Python **/research/d7/spc/yzyang4/venvs/aira/bin/python**，B=/research/d7/spc/yzyang4，SSH linux5。SLURM_CONF=/opt1/slurm/gpu-slurm.conf。

- CPU已PASS：14 typed/14禁网SDK/30真实循环合成测试/3根冻结/3身份guard；CPU SHA4d26c9a4513e439b57316b06c00b7224b6c353525e595445a3735de171ce84da，另12阶段提示表PASS。不把合成测试当模型/效果。
- analysis wrapper **B/automatic_specification_v6_analysis_20261003.py status**：只结构。全闭合且作业终态后，依次analyze、verify、sensitivity，均create-exclusive不要重复。analysis receiptcd74bff3f7fd9e03d7da3972dde46ba359c751d689c5b008c66a1b926a7e4963。
- 初次analysis freeze因生成模板里literal backslash-n发生SyntaxError，GPU/模型未启动。failed模板+partial readout freeze保存在root/analysis_preflight_failed_1/，修复wrapper并加AST解析后freeze成功；plan/实验源码未改。不可把这个预检失败当模型失败或隐去。
- **B/automatic_specification_v6_mechanism_20261003.py inspect --brief/--index N --step K**：闭合终态后才能看，先做credential scan。机制rubric已freeze，SHA65b3bfc2eb984525a4e80a9446bd7d3508cdee25b64e58afda0a5825e11b8bd0。先核方案和代码，理由可能透分，不声称完全盲审。
- V6 exporter已上传 **automatic_specification_v6_export_20261003.py**，要求manual mechanism-audit含全部14records、summary/planSHA。**V6 close审核脚本尚未写**，必须依据实际全轨迹，不机械复制V5结论。导出后校验receipt和所有文件原字节，CSV Git -text。

### V5已封口，禁止重做

15389 COMPLETED1572秒×4，1.7466666666666666GPUh；2来源/12比较闭合、独立核验PASS。full summary **41767d4d72bc8f396c5f53632769f0c52a6943addbef17bd55265e3444cb0f40**；mechanism **e644e0cb468761392f8eb17d7adf3f2a425e8b01542a08a8a98cdef8f32cf44a**。
B四条各3PLAN/0新候选，数值门false。Pizza A[0,.14823008849557517] C[0,.1160009567089213]；Spooky A[.01141375121780508,0] C[.005133781579247154,0]；B全0。固定查询bootstrap为条件敏感性，不含任务/训练/适应性选点不确定性。
Pizza根读样例CSV当训练表，常数初态AUC.5；所有臂同初态。普通A的104811在step3显式读真实train.json，发现2295×32训练表（不是错误300×2），step4训练LR达到AUC.6482300884955752。该正增益来自普通臂，不归给B。C的.6160009567089213来自无监督手工启发式，不是监督TFIDF。Spooky A最好.3985592426690203（step3），C最好.40483921230757824，起点.4099729938868254；都是已知文本/线性方法调整。
安全16文件＋receipt已下载并逐字节核对PASS：publication/phase1/results/automatic_specification_v5_20261003；receipt **65d557b283dcff715bfb8d7430ffca8159339a87ad25c7bd30a0e9239c35f0a2**。无raw标签/预测/代码/回复。V5prepare/freeze/analyze/verify/sensitivity/close/export均不可重跑。

V4 15365两root失败、12对照未启动，0.5788888888888889GPUh；包括前五设备/失败账后V4累计.6027777777777777。旧15414之外12535held不动。

### 本地/Git/安全

publication=C:/Research/New/my_project/MLEvolve/_codex_tmp/publication-feedback-20261001；HEAD/myfork研究分支最后核392321794b3bbf02a99a5bf1bc70355bb5ca80b4；V5/V6源码、V5results及方向文档尚未commit。学长dojo-reproduce最后核1a4b06212727f45b6410a9d007803a0d0581219b（14:00前fetch无变化），不改学长分支。研究push仅myfork phase1-value-critic；主checkout有其他dirty，禁止bulkstage/reset。
先为新results目录加窄.gitattributes -text，再stage/查secret文件名及内容/receipt-vs-index原字节/ff push。必要时只对本批result git add --renormalize，不能重写原结果文件。
用户不要求每轮新长报告；维护一份短交接和方向，最终重点是科学增益/停止判断。VibeRepair已有spec-first、MLE-STAR已有组件精修，不能换名当创新。
不读first960/Target300/522、D_val、官方test；不更新agent底座、不恢复critic/HCE/多保真/Probe；不调用付费API。凭据远端.env且不回显。存储4TB授权至2027-08-30。GPU3原镜像已实算兼容，GPU39不投任务容器，GPU1双卡原掩码异常不绕隔离。
