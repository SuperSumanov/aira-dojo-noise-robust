# 当前交接：收费ForeTS八run已失败收尾，优先修共同生成可运行性

更新：2026-09-12香港；本轮独立终态复核2026-09-11 20:23:45.591463 UTC。
恢复：fetch → CURRENT_DIRECTION.md最新0L161 → 本文件 → 核现场。学长指导见ADVISOR_DIRECTIVES.md L/M/N。
所有动态数值为注明时刻的最后观察；不要把旧“控制器completed”当模型/候选程序成功。

## 最新真实结论

- 13088与13112均COMPLETED / gpu28 / 0:0，8个worker进程completed、各1attempt；两块均已释放。
- 但是24次候选执行+16次debug执行全部exit1；0/8有效最终解、0/4可比成绩对。
  无最终eval事件，不是文件名误读。不能补零、报打平、选中途submission补分或只保留成功子集。
- 64生成候选；每run三个池宽4/3/1、5次实际执行（6步上限包含root且debug占步）。
  4个critic run共有8个可剪枝池，top2边界全部非打平；并非没有发生实际评分/筛选机会。
- 失败分类：14 LightGBM移除/错误参数，6超时，6 categorical赋值，2混合类型编码，
  2实验性导入，2缺目标列，8其他代码错误。独立journal与task-call回执一致。
- 这是本配置端到端有效率失败；无法估计critic相对最终成绩收益，不是正结果，也不否定所有critic。
  科学目标仍是同预算最终解收益，不恢复旧benchmark-only或G0循环。
- 详见FORETS_PAID_E2E_CLOSEOUT_20260912.md及results/forets_paid_e2e_20260912/。
  两块最终成绩只在全部终态后一起读取；没有用第一块结果重选第二块。

## 费用与边界

- 用户2026-09-11批准100人民币生成API总上限，固定8run/19GPUh。
- 实际13088=3135秒双卡，13112=2730秒双卡；总3.2583333333333333GPUh。
- 124次API（120真实operator传输+4 route），全部结算0.318775548USD，0未结，未触发停机。
- 保留唯一paid.sqlite与原授权：10USD全账本、8run各1.10、route共1.20，每请求0.70预留。
  不重建/复制初始化、不复用旧scope追加新实验、不改已完成矩阵或隐式fallback。
  原预算尚有余额不等于自动扩大8run；后继版本须明确新矩阵和跨版本总预算。
- 两块route/submit/execute/collect/readout都完成，禁止重复。会话监督/收尾链session25007已正常退出。
  没有新增自动监控；g0-r5仍PAUSED；不要干预12535 JobHeldUser。

## 下一项实质工作

1. 原任务镜像只读核实：LightGBM4.6.0、pandas2.1.4、sklearn1.9.0、numpy1.26.4、
   catboost1.2.10、xgboost2.1.4、torch2.5.1+cu124；见image-api-facts.json。
   四项错误LightGBM参数的签名绑定均拒绝，接口支持callbacks；没有GPU运算或模型拟合。
2. 当前生成提示只列包名，未给版本/API信息。优先准备所有生成/修复臂共同使用的真实环境信息，
   原SIF/Torch/critic不变。该信息尚未接入新生产包，未证明能提高可运行率；不能把接口核对当修复成功。
3. 独立开发可运行性检查先于下一组新seed效果对照。不要通过手改旧候选、延长旧超时、反转critic、
   调k、挑任务或补中途成绩“救跑”。API参数之外还有类型/逻辑/超时失败，不能只修一个词就宣称全部解决。
4. 不再做G0/12892/13076或下载权重；不要把100人民币重新解释为缺密钥/缺费用批准。
   后续若需新增GPU/API，先更新新版本范围、累计成本和配置矩阵；不启动未经界定的长贵实验。

## 已冻结产物与身份

- 根 /research/d7/spc/yzyang4/forets-paid-20260911-oh3np7b8。
- 执行controller commit f051cfded55259d5320407a9e0269ab9141ab345；
  source tree f9087ae47470f7f1868c61405c3b827327f31c2c。
- prepared SHA 58558eed5abe1f793c77049572549c66de8c104255f8a13fa3c48e0a8b4d3593；
  inventory SHA 6857f18c60fecaa745710960c0f2f9dfd50d485717ca8a7e86faa47dedc10c1b；
  release SHA 819621d75c9c95efe1e337866884b8701ad5f3f71cf5ea7e849f2b6ab0dd8798。
- runtime-manifest-20260912.json、final-readout-20260912/、cost-work-20260912/均已完整生成。
- post-closeout-20260912/independent-failure-verification.json：不导入主reader，重新核sacct、
  原journal、task-call及SQLite整数费用。verifier SHA d82f878ad2d0efcb1f4aca5cff9a7553268c2b727e488c6043dee9afdd049dd2。
- post-closeout-20260912/image-api-facts.json：原镜像只读版本/签名，脚本SHA
  41fbecfa5e675902ea5fde9febe6d26281dcbd803507093fe2fa9b34679c4d37。
- 已将9份安全结果文件取回本地results/forets_paid_e2e_20260912；没有下载原始journal、代码、prompt或密钥。
  成本/执行量辅助6项测试本地与Linux通过。测试不是模型收益。
- 我方公开HEAD最后已核push为0f8d7daf；本次收尾报告的最终push另核Git，不把报告commit当执行commit。

## 仍关闭与操作规则

- 13004首对及13085闭池负结果保留；CPU期限筛查25-fit无投资信号已停止。免费模型失败窗口关闭。
  旧设备9误映射adapter撤回，不复用；当前gpu28 native UUID绑定已验证，无需再索要gres.conf。
- first-960/Target-300/Target-522标签、结果、预测及私有选择继续隔离。
  HCE、多保真、Probe、score-channel、K≥1 lookahead不恢复；不更新agent底座。
- 学长dojo-reproduce最后fetch 065b0fbaa89e0eb663f2834ec768081f5d56394d，未修改其分支。
  19:51:45.958128 UTC已知0907、0909、0909/mcts网盘列表无变化，未覆盖其他目录。
  senior-quarantine-20260911-v1的32配置不等于32合格runs，未并入训练。
  LATEST最后759总physical/733 eligible，closure=false；本轮未重算，不解封。
- repo C:/Research/New/my_project/MLEvolve/aira-dojo-codex-20260813；只push myfork HEAD:phase1-value-critic。
  凭据仅远端.env OPENROUTER_API_KEY→worker PRIMARY_KEY；不写本地/Git/输出、不再索要。
- SSH linux5；网络先source /uac/y24/yzyang4/env_setup.sh；SLURM_CONF=/opt1/slurm/gpu-slurm.conf。
  CPU Python=/research/d7/spc/yzyang4/venvs/aira/bin/python；模型同根venvs/exp/bin/python。
- 复杂SSH脚本/scp；代码归档仅src/aira_core、src/dojo且core.autocrlf=false，不能整树archive触发大LFS。
  Windows用rg -g过滤文件，不把未展开的通配符当路径；读文件设置错误即停，不能把缺文件的null算作0。
- 两臂同硬件/原镜像；gpu28不是projgpu28/39。QOS4jobs/8GPU；排除projgpu7/8/33、gpu36/38。
  保留未跟踪codex_tmp/output/tmp等用户文件。官方研究盘1TB，到期2026-09-29，续期未知。
- 历史交接保留Git5cbf2a6a与dated报告；短入口覆盖当前事实，不追加无变化轮询。
