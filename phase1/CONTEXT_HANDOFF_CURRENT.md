# 当前短交接

最后核验2026-10-01 08:34 UTC（香港16:34）。本轮全部完成；不要重复提交或重跑一次性读出。

## 最新裁决与用户授权

用户要求真实续跑并三小时提供有价值信号；04:33 UTC开始，07:33已交付首批并push，现已完成原定18条。用户已确认研究盘续期，不能再询问或当作待审批。唯一方向入口CURRENT_DIRECTION.md顶部0L395；同任务冻结生成器、可信事实A/B/C。本轮结果不支持扩大当前长度分组+证据格式约束版本。不恢复critic训练前置、旧HCE/多保真/Probe/K≥1或底座更新。不读first-960/Target-300/Target-522、D_val/官方test。

## 已完成的真实运行（勿重投）

- 15140 v6：05:48:58提交，05:58:43本地27B服务ready；08:27:27全部18条闭合、08:27:30服务关闭。Slurm最终COMPLETED，9512秒×5GPU；无controller/infrastructure error。唯一根目录 /research/d7/spc/yzyang4/task-feedback-real-20261001-v6。
- 冻结plan SHA 15751d3b52bdc42617df02006ce724635f4bf49df6e477686769fd1979d53403。18=3任务×2旧代码起点×A/B/C，每条1800秒且最多4次原生修改，固定RTX3090 gpu28、2服务+3任务GPU。不是完整历史状态恢复。
- 先前15135 v5在首次生成前接口失败，05:33停止，790秒×5GPU；证据保留。v6连同它总实际14.308333333333334GPUh，低于原20。无付费API、无fit、无新追加作业。
- 最后队列只剩原owned12535 PENDING JobHeldUser，不触碰。没有活跃functions单元、SSH会话或新automation。
- 所有prepare/submit/stop/finalize脚本均不可重复运行。不要重验G0、权重或旧GPU隔离。

## 完整结果与边界

完整目录 phase1/results/task_feedback_pilot_20261001/complete/：
runs.csv（18行）、comparisons.csv、summary.json、verify-complete.json、exposure-complete.json、initial_state.json、public_view_identity.json、descriptive_analysis.json、accounting.json、closure.json。

89返回动作、31有效提交独立原生评分和聚合重算全部PASS，pending为空。18条16最终有效，A5/6、B6/6、C5/6；72次生成全部返回，1个最后执行在截止前未形成结果。六起点初始代码hash一致，B/C首事实相同；仅两起点初始有效，不能把其他null置0。
预定主收益：B-A两负；C-B一平一负。次指标5个双方有效配对：B-A/C-A各1胜1平3负，C-B2胜2平1负，另有C无效/B有效1对。完整六行表见0L395，不按有效子集宣称胜出。

Tweet第二起点A0.5226682748344275、B0.5731426197663997、C0.5853067573584102，有局部相对提升但仍低于全文复制参考0.593357488208652。参考是07:38的一次事后固定规则，0GPU/API/fit、2454行，独立重算0.5933574882086521；未喂agent，不是第四臂。两起点公开view逐字相同，不能误称独立数据。勿重跑/tmp/task-feedback-tweet-copy-reference-20261001或改规则追分。

B/C各24生成仅10次有聚合事实（合计20/48），valid-parent为处理依赖中间变量，不据此筛选估效。部分失败修复没有切片证据，不能把修复归因于切片诊断。A在两个Pizza起点都高于B/C；不能拿B自我改善替代胜A。C当前证据格式prompt不是已证明的新analyzer算法。

本轮仅D_search开发筛查、两种停止上限、3文本任务、2不同代码起点且每起点1seed、共享服务相关。不是跨seed/全E2E/独立终评。actual elapsed不同、exec_seconds包含内核准备且遗漏未返回动作；总成本采用完整Slurm分配。下一大实验前先明确可执行修改与额外证据的关系及强简单基线，不围绕最新失败无限加补丁。本轮不再提交GPU。

## 保存/发布

主目录 aira-dojo-codex-20260813 HEAD14188f8956d5becfc1f192455647d7c4aedd1f82有大量旧脏改，不整体stage/push/reset/rebase。
干净发布工作树 C:/Research/New/my_project/MLEvolve/_codex_tmp/publication-feedback-20261001，detached HEAD；只正常推HEAD:phase1-value-critic，不新建分支、不动学长分支。
本次发布基线5cbab426461f8ef3c01d0708f15388655fa07751（首批+全文参考），完整结果随本次限定路径提交保存。发布前14路径安全核验通过，敏感文件名/凭据形状命中均0；10产物和1源码暂存字节与原文件一致，CSV/JSON及统计独立算术复核通过。推送后以git log/ls-remote确认，不以本文件自引用commit作为远端证明。
主/公开CURRENT_DIRECTION历史相差很多，不能整份复制；本次0L395分别插入。学长dojo-reproduce最后核验e385f863cb531904e611e987f7f71606796db656，未修改。
只上传指定聚合、验证hash与代码；不上传.env、原始私有generation/node/submission/标签。scripts/analyze_task_feedback_exposure_20261001.py实际SHA67c0e1afab2833950530f2982a526143cfb06198f1d12ed2efc503edc3aad598，仅读既有反馈收据，无新执行。
14既有诊断/读出单测通过；11项源码/结果暂存字节校验已通过。summary SHA50f43b5ce3b7ec9e724d3a58f2283263d8842797592e389d3d31b39f41a206fe，verifier SHA23713e5f5eaa1f06037328d2454ea4d3be52d8f578f2941caa9ccd71beab8319。

## 只读核验入口

SSH linux5；Python /research/d7/spc/yzyang4/venvs/aira/bin/python；SLURM_CONF=/opt1/slurm/gpu-slurm.conf。
安全现场：Python -B /tmp/task-feedback-stage-20261001/task_feedback_status_20261001.py --errors。
一次性已完成输出：readout-complete/、verify-complete.json、exposure-complete.json。不要相同路径重跑；需要查看直接读安全汇总。
私有日志先远端脱敏；凭据只留远端变量/位置，不回显值。
