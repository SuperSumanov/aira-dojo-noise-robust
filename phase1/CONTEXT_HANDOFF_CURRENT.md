# 当前交接：共同环境修复四run已在gpu28启动

更新：2026-09-12香港；最后现场观察2026-09-11 20:42:11.521165 UTC。
恢复：fetch → CURRENT_DIRECTION.md最新0L162 → 本文件 → 核现场。学长指导见ADVISOR_DIRECTIVES.md L/M/N。
没有重查的状态不得称实时；进程completed不等于有效最终解。用户要求会话内推进，不新增自动任务。

## 当前实际作业

- **13113 RUNNING / gpu28**，2026-09-11 20:41:55.022896 UTC提交，20:42:11已运行16秒。
  此时四worker尚pending、critic启动中，不能声称MLE候选已成功。
- 新版本两任务leaf-classification、spaceship-titanic；新seed10，两臂random/critic，共4run。
  顺序leaf random→critic，spaceship critic→random；四run全闭合后一起读最终成绩。
- 只改共同生成上下文：draft/improve/debug系统提示补原镜像版本/API和原300秒总程序时限；
  analyze、critic/输入编码、模型/路由、原SIF/Torch、5-fold、6步、width4/top2择1均不改。
  旧draft/improve已有部分early_stopping提醒；此次补verbose_eval/sklearn fit等遗漏，不是“此前完全没提示”。
- 角色是开发可运行性，不是跨seed正收益确认。用有效最终解数/4与逐任务配对，不用worker退出码代替。
  如仍失败保留全4run，禁止重跑失败槽位、手修旧候选、挑中途submission、翻转critic或调k。

## 新版本定位与预算（不要重复提交）

- 新根：/research/d7/spc/yzyang4/forets-env-20260912-edcpizid
- 实际执行controller commit **dfad1bba2171b62f6d476129e661de66d3c4801b**；
  source tree **0a587f6b220b1aa0bd154f537f36594bc0690cb3**。
- prepared SHA 1e0f29be3f48fb376a2ce4a2740da583d5c39fcdefa9c5f6d2bceac7b100eda9；
  inventory SHA 0342f6feb8ff7c6fd94b3a04e18d151422ce7738a3fda255d61f030b7f6714c7；
  release SHA 0ddfbdd870d005d9123b8fbcb58c6bb614501db830d373ac3683662517f39e45；
  context SHA 0e1a197fab7c8f6bafd5170e6f634c11095a78a07c4ccac19702b635e01ba8b8。
- 新增单块280分钟双GPU，含退出余量上限10GPUh；原实耗3.2583333333333333GPUh另计。
- 用户100人民币总API授权不重置。新版新增最多1.50USD，显式预扣旧0.318775548USD，
  累积上限1.818775548USD（低于原10USD上限）。新auth SHA
  942afbfc8864bb07dd6580c1d85a71743e35fea47bc1bdc71081666cab32ecb2。
- 旧账124call全部结算、0未结；本轮只把旧auth.stopped设1防重复花费，旧calls/费用/结果没有删除。
  新账closed_predecessor一条为124call费用结转，**不是一次新API请求**；计数必须扣这1条再加历史124。
  新旧全部实际调用最后126次（新route2次），总已结算0.318929208USD、0未结。
- 新root/submit-intent.json、submission.json、block-1.route.json已存在；**不能重跑submit/route/activate**。
  新账不可初始化或复制绕过上限。每请求0.70USD预留、未知费用保持预留并停机；无模型/路由fallback。
- 无新增自动监控，g0-r5仍PAUSED；12535 JobHeldUser旧作业不要释放/取消。

## 会话操作

远端新根下：
- forets_environment_session_20260912.py status：只看排程、pool状态和费用，不看最终成绩。
- 四run整块关闭后调用同脚本closeout：独立sacct→派生固定4run reader→journal/task-call复验。
  生成runtime-manifest.json、final-readout/{summary.json,runs.csv,pairs.csv,blocks.csv}、diagnostics.json。
  尚未运行closeout；若读取/字段校验失败，修reader并保留事实，不改已执行配置或补分。
- 状态命令：/research/d7/spc/yzyang4/venvs/aira/bin/python -B 新根/forets_environment_session_20260912.py status
- 本轮6项测试本地/Linux通过；12个真实GenericLLM渲染（替代网络边界）确认系统信息实际到达请求；
  源码233文件仅paid_budget.py改变，实验环境信息位于配置模板；测试和route均不证明MLE可运行。
- 最初unittest discover误扫phase1子包出两个相对导入错误，改为直接执行指定测试，6项通过；
  没有修改那些无关包，也没有忽略新测试失败。
- 计划与预检见FORETS_ENVIRONMENT_REPAIR_PLAN_20260912.md；实际提交脚本scripts/forets_environment_20260912.sbatch。
  交接/监督脚本后续commit不冒充实际controller dfad1bba。推送前扫描完整待推文件。

## 前版本已封闭的事实

- 13088/13112均completed并释放：8/8进程结束，但0/8有效最终解、0/4可比成绩对。
- 64生成候选，24候选执行+16debug全exit1；无final eval，不能补零或声称打平。
- 4critic run共8个可剪枝池，top2边界非打平；不是没有发生评分/筛选。
- 失败分类14 LightGBM接口、6超时、6categorical赋值、2混合编码、2实验性导入、2缺目标列、8其他。
- 旧根forets-paid-20260911-oh3np7b8，实际controller f051cfde，source f9087ae4；
  收尾完整报告/安全结果已push **133618ba**。见FORETS_PAID_E2E_CLOSEOUT_20260912.md和results/forets_paid_e2e_20260912。
- 原镜像确认numpy1.26.4/pandas2.1.4/sklearn1.9.0/lightgbm4.6.0/catboost1.2.10/xgboost2.1.4/torch2.5.1+cu124。
- 这是否定该配置有效率，不是新critic正结果，不推出所有critic无用。

## 仍关闭与操作规则

- 13004/13085负结果、CPU期限25-fit无投资信号保留；不重开免费模型失败窗口或G0/12892/13076。
- first-960/Target-300/Target-522标签、结果、预测与私有选择继续隔离；
  HCE、多保真、Probe、score-channel、K>=1 lookahead不恢复；不更新agent底座。
- 学长dojo-reproduce最后fetch 065b0fbaa89e0eb663f2834ec768081f5d56394d，未修改。
  2026-09-11 19:51:45.958128UTC已知0907/0909/0909-mcts列表无变化，未覆盖其他目录。
  senior-quarantine-20260911-v1的32配置不等于32合格runs；LATEST最后759physical/733eligible，closure=false，未重算。
- repo C:/Research/New/my_project/MLEvolve/aira-dojo-codex-20260813，只push myfork HEAD:phase1-value-critic。
- 凭据仅远端.env OPENROUTER_API_KEY→worker PRIMARY_KEY，绝不本地/Git/输出或再次索要。
- SSH linux5；网络source /uac/y24/yzyang4/env_setup.sh；SLURM_CONF=/opt1/slurm/gpu-slurm.conf。
  CPU Python同研究根venvs/aira/bin/python，模型venvs/exp/bin/python。
- 两臂同硬件/原镜像；gpu28不是projgpu28/39；现有MLE镜像不能投projgpu39。QOS4jobs/8GPU。
- 不索要gres.conf、不猜设备9、不启用失修pool恢复路径。fresh-start失败保留，不冒充续跑。
- 复杂SSH用脚本/scp；源码只archive src/aira_core src/dojo，core.autocrlf=false，避免大LFS404。
- 保留用户未跟踪codex_tmp/output/tmp等。官方研究盘1TB、2026-09-29到期，续期未知。
