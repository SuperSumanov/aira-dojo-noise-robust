# 当前短交接 — 2026-09-14 01:56 UTC
六小时会话：09-13 21:06:43→09-14 03:06:43 UTC（HK11:06）。用户要求会话内实质研究，勿新建自动任务替代；继续至端点并完整核验新结果，不能为了正结果改seed/隐藏失败。方向CURRENT_DIRECTION 0L204。

## 正在运行，严禁中期效果读取
13311于01:54:24单次提交，01:55:31确认gpu28 RUNNING/首条真实执行/native bindings3。
ROOT=/research/d7/spc/yzyang4/forets-wallclock-20260912-9uosb6me
STAGE=/research/d7/spc/yzyang4/forets-class-gate-stage-20260914-RWKXbwxc
OLDSTAGE=/research/d7/spc/yzyang4/forets-cheap-v2-stage-20260914-bqkP9eR8
矩阵8条Leaf/Space×新48×uniform/short_code/learned_validity/class_gate。Leaf顺序H/G/U/S；Space U/S/H/G。单95分钟单GPU/6CPU，一次一个search，消除跨臂责任预留争用；仍有provider/臂内等待。
600秒总搜索/300秒程序/64step/100adapter/2生成1执行；原MLE镜像3090、共同RF起点/Fresh后端。类别门固定旧HGB p>.5→1否则0，同类别原随机；不阈值调优/拟合/底座更新。
源b7f8ab0f65dba9877ac3af35e3e770fc32546565；archive293b6b346229b359bde13da5a9d6b92a9a053b38fd4ca6b019e736e3adc899ac；artifactcommit5bb9e2a05fc18c659d2835694c06290c75d6e7ca；prepared0d924c4b9bde28a8a90367db23f1b6c098e8555d130798f01fd05316ce358581；auth34fda0d3db198b8088f7378a2ccaa704cfbd2620c62096bfe4f607d0f8c89759。
readout-plan89724a497de7febe646488fb186e4ffe6f1930e92b971cba8c8411769fabb4ba，包括次要short对照addendum、builder/main/core/selection/数值helpers；冻结后不得改。
预计03:10–03:25UTC闭合。STAGE/monitor_class_gate_20260914.py只结构账务。全8与allocation闭合后STAGE/readout_class_gate_20260914.py ROOT一次；含exclusive产物，不盲重跑。然后需新独立CSV/原主次效果核验器（待写），不能改已冻结主reader。
已过5读出测试/实际8配置batch+80prioritycases/原CPU截止验证，复用既有GPU验收。不重做G0。
账从km65uuej原子承接并封旧，原100RMB→10USD累计责任帽，两旧未知保留；01:55calls2844/held8844896340/settled6744896340nUSD/unresolved3含在途，非新增永久未知。不减.7预留、不换key、不重置。
主投资门：全8合格，gate两任务对每个baseline无损且对U/H各至少1胜；允许与short平。次要short-vsU/H在48之前明示。单seed/任务无方差/统计确认。不中期读分、不调门、不替换seed。

## 已验证真实正信号与失败边界
13298/13299全12闭合/技术合格/有效，独立原提交数值+选择器/CSV通过。原root km65uuej不可再main读出。
Leaf46/47 U均1.51485；short .35474/.36555；H均1.51485（loss↓）。
Space46 U.79655/S.81839/H.80805；47 U.8046/S.8069/H.8023（accuracy↑）。
H原投资门FALSE，对U1胜2平1负，对S0胜4负。S对U/H均4配对全胜，是读出后发现的控制臂次要比较，不假装原主假设或确认。
2并行allocation共享账wait不均：U158.686141秒/S98.829411/H107.524577。不减等待调整分数，不称纯单旋钮因果确认。6433allocation秒/1.7869444444444444GPUh。
summarya2024478c6aa23feb7457d8d45738b51c622725b71eeba928af5e4d0a9dcac82；independent1bc25e391e6c2022cd174a5d16e3a682c6eef55bb4325ff8b841e0dd43750e6f。
本地results/forets_cheap_e2e_s46_s47_20260914/8manifest成员已验；tar54aa6fc034484e7b61abd76921d8ba7268248994e277e3c51ea1fbaafb7206f5。报告FORETS_CHEAP_E2E_RESULTS_20260914.md。
传统另8条小搜索Leaf median .05948仍强，1200秒/不同space非本轮配对，不能说超传统/SOTA。

## 模型及诊断资产（不再重跑）
固定model root forets-task-validity-20260914-n8q3h72y/code_only.private.joblib，SHA05379469122879c798f1d2c571eb733956a067dac314050feeb06d3e09c641d1；2482旧节点/138run/14task，28static code[:30000]features HGB100/15/min20/l2=1，sklearn1.6.1；无task/runtime/feedback。
旧v9有锚点run补失败，排除无锚点全失败run，非无偏全语料。模型不再拟合/按48结果选模型。
四旧协议32计划run→15有完整对run/45完整对/11discordant，H10/11/S4/11/尺寸HGB6/11；H对S实际run4胜0负11平，不把11pair独立。scope缺失最坏界Leaf/Space仍正，width0，memory Leaf未知，报告全部。
only3both-valid全Space：H均选较低质量，vsU平均-.004405；6原提交数值复核。14-task LOTO full .48886771165193804 vs size .5158798185810396 vs short .5558735851921456；H对S3task胜11负，不能称任务外能力。28CPUfit诊断模型不部署。详CHEAP_TRANSFER_FINDINGS_20260914.md，结果/代码公开707ffb85。
classgate旧固定CPUassay：11discordant期望7.5（H10/S4/U5.5），3both-valid保留uniform探索，vsH质量和+.013214999999999866但不普遍优于S，非E2E。
OLDSTAGE/cheap-class-gate.json fafa41645ee8eeaa97eaf3aa476b19d88ab3cf7556ea914898e08fda09ab8224；independent89a0c3afa37d3d030c3e4cd3cbe24173b25ed389d7461c703eade9b6e36d7d13。

## 关键禁止重复与操作
v1 13293/94各67秒取消，证明0生成0searchAPI，只有4route，PIDreceipt路径修复后整矩阵同seedv2；不删失败。临时tpjljg17激活回滚、旧q_imzdb_ sealed；不要复用。
旧EScope16门失败（4可比0胜4负4未知），272module接口拒绝；读出representation addendum不是改结果，不重复exclusive。经典13284/Fresh13286/87/G0/12892/8B已完成，禁重验。旧T1/width/memory/critic失败保留。
CodeScaler/Automata AST与长度控制/MARS已有先例，静态有效性/门控/短代码不是新算法。论文希望是被充分证明的预算质量取舍机制，尚需新任务/更强生成器/重复。
学长branch01:55fetch仍be9335348b569086ef9b0af36a15b13e61fec45c；0912tar4config已隔离非4eligible，未知重复failclosed不重下、不摄取新保护cohort。不借他人allocation/未确认27Bendpoint。
SSH linux5；Python /research/d7/spc/yzyang4/venvs/aira/bin/python；SLURM_CONF=/opt1/slurm/gpu-slurm.conf。MLE仅gpu27/gpu28原镜像，禁projgpu39/Torch升级/CPUfallback。12535 held不动。
远端aira-dojo/.env OPENROUTER_API_KEY；source ~/env_setup.sh有proxy，绝不回显/本地/git/重索。复杂命令脚本scp后等结束再执行。SQLite closing防NFS。
本地 C:/Research/New/my_project/MLEvolve/aira-dojo-codex-20260813；只push myfork HEAD:phase1-value-critic。不新建branch/改学长branch。最新已确认公开80feddc0634595185f00d813ed4fbdb82a068db1，248成员源archive和结果全扫描无credential。每push再查staged名与credentialshape，不含密钥/私人余额。无关untracked保留。
保护first960/Target300/522仍封；HCE/多保真/Probe/score-channel/K>=1/agent底座更新禁。研究盘1TB到2026-09-29，续期未知。记录轻量，不能替代实验。
