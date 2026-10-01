# 当前短交接

更新时间2026-10-01 07:30 UTC（香港15:30）。以下动态状态为最后观察，恢复后重核；不要重复提交。

## 用户请求与方向

用户要求真实续跑并在三小时后给有价值信号；本轮04:33 UTC开始，07:33为汇报节点。研究盘续期已收到管理员确认，用户已直接确认，不再询问。当前方向0L394/0L392：固定生成器、任务内可信反馈，A强普通反思/B额外固定聚合事实/C与B同事实加证据使用规则。没有critic训练前置，不恢复旧HCE、多保真、Probe、K≥1或底座更新；first-960/Target-300/Target-522、D_val/官方test均未读取。

## 正在运行，禁止重投

- **15140 RUNNING gpu28**，唯一根目录 /research/d7/spc/yzyang4/task-feedback-real-20261001-v6。05:48:58提交、05:58:43服务ready（582.625秒）。冻结plan SHA 15751d3b52bdc42617df02006ce724635f4bf49df6e477686769fd1979d53403。
- 07:26最后观察：首起点9条闭合/7条有效；第二起点A的episode9/10/11已启动，随后B12/13/14、C15/16/17自动按固定顺序运行。全18分母保留；并非全批完成。
- 5GPU（2服务+3任务）、30CPU、3h40 allocation上限；加失败15135总毛上限19.430555555555557 GPUh，不追加预算。其余owned12535 JobHeldUser，不触碰。
- SSH linux5可用；Python /research/d7/spc/yzyang4/venvs/aira/bin/python；SLURM_CONF=/opt1/slurm/gpu-slurm.conf。任务镜像留在RTX3090 gpu28，不升级/换CPU/改投projgpu39。
- 状态：远端Python -B /tmp/task-feedback-stage-20261001/task_feedback_status_20261001.py --errors。只看安全回执，勿cat私有日志；--v5仅旧失败包。
- 没有本轮新automation，按用户偏好在会话内核验。若任务完成，核all-closed、closed和sacct，勿把pid/进度当完成。

## 第一代码起点结果：真实但仅开发

| task | initial | A | B | C |
|---|---:|---:|---:|---:|
| Spooky logloss（低好） |0.38797591250098007|0.37976945033064013|0.38797591250098007|0.38797591250098007|
| Pizza AUC |0.6281392011480507|0.681296340588376|0.6402774455871801|0.6281392011480507|
| Tweet Jaccard |invalid|invalid|0.5244375305167687|invalid|

B-A收益差：Spooky -0.008206462170339934，Pizza -0.04101889500119582。Tweet只有B修复成功，不能把初始缺分当零。B首次无切片事实，因此也不能把修复归因于切片信息。C目前没有额外优势，不追加提示补丁或追seed；原定第二起点继续，不能因正负换任务/起点/预算。A/B都自主提议TF-IDF，不能拿B自我改善宣传诊断收益。解释性的意图观察不是因果证明。

readout-first-start / verify-first-start.json已复制到本地phase1/results/task_feedback_pilot_20261001/first_start/：18行完整分母，12启动/9闭合；独立复核当时47返回动作、13有效提交全部PASS（含第二起点初始动作）。initial_first_start.json证明实际原始/执行代码hash相同、两个有效任务初分相同、三任务B/C首条facts逐字相同；两个null不算数值相同。第二起点尚未形成完整配对，不能叫跨seed确认。

## 试验契约与正确读法

FEEDBACK_REAL_PILOT_20261001.md、scripts/task_feedback_real_20261001.py和task_feedback_facts_20261001.py为冻结运行文件。18条=3任务×2旧代码起点×A/B/C；每个起点只有一个续跑seed，不是纯同起点多seed。每条1800秒包括初始重执行/诊断/生成/执行，最多4次原生Improve/Debug；代码执行请求timeout480，记录exec_seconds另含内核准备，不是纯计算时长。截止后不选结果，未返回动作成本不能伪装为零。

旧代码在每步干净工作目录重执行，不继承历史权重/文件/RNG，绝不是完整物理快照恢复或完整ForeTS E2E。生成器27B INT4/no-thinking，最大8192输出，本地无付费API；同gpu28原任务镜像，服务/任务GPU不重合。初始固定选旧run最早execution_started=true非空代码，不按分数选。未见D_val/test或任何保护cohort。

A只见可信整体D_search分+日志+强普通反思；B/C额外事实同状态字节相同，轨迹分化后可不同。公开训练词长边界固定Spooky17/30、Pizza43/82、Tweet9/16；不事后改切片/阈值。parent_delta绑定实际生成父代码，缺父预测保留unknown。valid失败/格式拒绝不删。B Pizza action2重复python围栏而执行前拒绝，exit0不等于成功，未热改解析器。

## 已关闭失败与预检，勿重做

15135(v5)已05:33取消：初次生成前nested DictConfig不能JSON序列化，且复制的旧源码未实际含有界传输。无生成续改；sacct790秒×5GPU=3950GPU秒，原包和operator-stop保留。不用它作方法比较。v6共有修正普通JSON配置、复用0011有界单次传输/600秒/无retry、原生模板step_limit5替代10000；任务/seed/科学处理不变。所有stop/finalize/prepare/submit脚本均不可重跑。

已完成18配置/36原生模板、真实SDK6次mock HTTP（0网络）、三臂15动作原生循环mock、镜像及6权重shardhash、4个人工指标压力样例；事实7测试、读出7测试。新返回提交独立重算，不再重复G0/权重验收。

## 读出工具与Git

- 临时远端task_feedback_table_20261001.py [--trace]：完整分母/已闭合配对。
- task_feedback_readout_20261001.py --out <新的唯一目录>：CSV/JSON快照；主对比oriented_gain_difference，最终分差次指标；usage缺失为未知。
- task_feedback_verify_20261001.py --out <新的唯一json>：只重算本批开发提交，非新执行。
- task_feedback_initial_check_20261001.py：起点比较；其发布版为scripts/check_task_feedback_initial_state_20261001.py。
- 意图/错误类助手只辅助解释，不构成根因或处理效应结论。
- 主目录HEAD14188f8956d5becfc1f192455647d7c4aedd1f82有大量旧脏改，绝不整体stage/push/reset/rebase。
- 干净发布工作树C:/Research/New/my_project/MLEvolve/_codex_tmp/publication-feedback-20261001，仅发布限定路径；上一公开head4d839e9dd205ab03c7b2b22cddd30b20c89c6af2。本次0L394与首批结果准备发布，成功后记录确切新SHA。
- 学长dojo-reproduce最后fetch e385f863cb531904e611e987f7f71606796db656，未修改学长分支。
- 主目录CURRENT_DIRECTION与公开历史有1427行差异，**不可整份复制**；本次只分别插入0L394。
- 原始token/密钥仍只在远端，不复制.env或generation.private、node.private、submission.private。
