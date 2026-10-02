# 当前短交接

更新2026-10-02 16:35 UTC（香港10月3日00:35）。用户要求在会话内持续三小时，窗口14:38:55—17:38:55 UTC；尚未到交付时点，不另挂周期任务。研究盘总配额4TB、原路径、授权至2027-08-30，非实时剩余空间。

## 已完成的真实实验

15272已COMPLETED，3466秒×4GPU，3.851111111111111 GPU小时；本轮GPU实验已结束，不是排队或继续运行。根 /research/d7/spc/yzyang4/state-feedback-pizza-20261002-v1，plan 4b95fcc575c2f8fa438bd3737d05ec6f40ffa0aa2bfdfc89de38e76e71979b5b。8条=Pizza一任务×2合并初始化/生成seed×4臂，每条720秒/4调用×4096token/代码300秒。

A冷重建+遮蔽初态stdout，B保留状态+遮蔽，C冷重建+可见，D普通持久agent+可见。以后所有stdout/错误/D_search均返回，允许重新取证。D是已有普通参照，不是新方法。全成功cell重放的冷基线不是最优依赖感知重建或原AIRA完整程序执行的等价物。

全部8条保留起点AUC0.6867376225783306；五种配对差与交互的2seed中位数/样本方差均0，冻结数值门false。独立逐样本AUC及比较代数PASS，14有效评分=8初态+6新解，0改善/1精确相同预测/5较低。24生成、10格式拒收、5条耗尽总时限，完整分母保留。summary c3bbcbf9ccce5ef356dfa7722d1607aa8fc63a009b280072f143321e66e09097；verification a0bbde230c21331ad65005283d424608cf4620975b15cdcfc27a47044e204ae2。

源码/汇总在publication worktree phase1/scripts/state_*_20261002.py 和results/state_feedback_pizza_20261002。只导出聚合，不含逐样本预测、标签、原始模型/终端输出或候选代码。export-receipt覆盖远端9文件；census、mechanism-review、sensitivity是明确追加的分析，不谎称原始export包括它们。

## 科学裁决与机制

不扩当前配方，不补seed、不热改/追正，不给普通缓存起新方法名。保留状态组产生5新有效解和2次CHECK，冷组1新解；不能忽略格式/启动/策略差异就声称纯缓存效应。两个B的CHECK只用1.1526791339274496/0.16884793085046113秒，后续采用所检查的权重/温度，仍未提高起点；所以不能笼统声称反馈未被看到或使用。D一条重训完整原程序，另一条普通网格精修。新增线性成员/融合都属已知参考，不是开放新发现。

一个可疑解释是“Ridge导致退步”：当时融合权重也变了，Ridge打印权重四舍五入为0。只支持错误归因风险，未确认实际精确零贡献，也没证明修正归因就改善搜索。不能把它立即升级新方法。

读分后单CPU敏感性检查6.246992803178728秒，2000次、seed103401、允许开发集300请求（不是受保护Target-300 runs）。五负差的条件95%区间全部跨0，第六份预测精确等同起点。其条件IID请求重采样不修复已见开发集、历史起点选优、候选适应性，不是独立泛化或seed不确定性。停止扩大是管理裁决，非统计无效/等价证明。

## 资格与不得误恢复

15267已完成885秒×2GPU；原两任务资格门false。Pizza两次公开OOF/诊断/submission精确一致；Spooky两次embedding OOF漂移，TFIDF与最终submission一致，根因未证明。含首次构建的分量合计成本比中位Pizza1.9545907617346723、Spooky2.1011132841969764；不是2000倍E2E，先暖后冷固定顺序且完整冷流程是阶段求和非单独第三轨迹。
资格plan e9926dcf48ea6385f542142e070faa811ab528a644bfa29970aa4bf750740af3，verification0772468c61d78c8005205d9318d42557366d973a8bbba39e49b33ce51f6bbb37。
原 state-feedback-factorial-20261002-v1 16条只准备，未提交且不得自动提交；Pizza8是按事前身份合格缩范围的另一次探索，不算跨任务门通过。

旧15227两任务8条/4配对全0，0/8触及900秒总deadline；不要重新归咎总时间不够。旧15213中止不救回。AST85修改筛查已做，追加26含18重复，不再作为创新；局部路由随机反证896/1000不低于观测oracle，不复活。

## 约束与操作

不更新agent底座，不读first960/Target300/522、D_val或官方test。只用明确开放开发任务。旧critic训练、HCE、多保真、Probe、score-channel、K>=1 lookahead保持关闭。普通缓存、局部编辑、诊断工具、经验遮蔽均有强近邻；论文无新效益/新颖性通过结论。

16:22UTC fetch后公开myfork/phase1-value-critic仍f0d18a56ea8ebd2dbb2836d4037602e022fca7a8；学长dojo-reproduce仍1a4b06212727f45b6410a9d007803a0d0581219b。学长1002 outcome先安全读，SHA38f64015e6a81ea1628106a58181b9f4311b75ec9c4b0bac3e647a259504d918。新short/random结果与policy起步记在ADVISOR_DIRECTIVES的U节，不是我方训练授权，不改学长分支。

主dirty checkout C:/Research/New/my_project/MLEvolve/aira-dojo-codex-20260813；不可整体stage/reset。发布worktree C:/Research/New/my_project/MLEvolve/_codex_tmp/publication-feedback-20261001，detached f0d18a56，目前本轮尚未commit/push。已有前轮复盘/计划/学长建议编辑已阅读；发布只明确白名单、结果/源码SHA对齐、密钥扫描、快进，禁止force。git只用命令级safe.directory。

SSH linux5；Python /research/d7/spc/yzyang4/venvs/aira/bin/python；SLURM_CONF=/opt1/slurm/gpu-slurm.conf。MLE镜像gpu28/gpu27兼容，不能projgpu39或静默CPU。旧12535 JobHeldUser不动。SCP退出0再用文件。密钥只远端.env。当前下一步：完成关键解释/邻近文献核对与安全发布，不新启一个同义harness实验。
