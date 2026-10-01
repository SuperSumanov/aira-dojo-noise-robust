# 当前短交接

更新时间2026-10-01 05:50 UTC（香港13:50），动态状态必须再核现场。

## 当前用户请求与已获授权

用户要求真实续跑，三小时后有价值信号。本轮04:33 UTC开始，目标07:33 UTC。用户已明确确认研究盘续期获管理员批准，不再询问或列为阻塞。当前主线0L392/0L391：固定生成器任务内可信反馈，同信息B/C、全成本A；不再以critic训练为前置。所有保护cohort、D_val/test边界不变，不恢复旧HCE/多保真/Probe/K≥1/底座更新。

## 本轮真实作业，禁止重复提交

- Slurm **15135已于05:33取消**，不是仍运行：首批C的Pizza/Tweet完成初始重执行后，首次生成请求因嵌套DictConfig不能JSON序列化失败；没有生成续改。整个失败批次保留，不作效果样本。sacct最终790秒×5GPU=3950GPU秒；旧12535不触碰。
- v5远端包保留：`/research/d7/spc/yzyang4/task-feedback-real-20261001-v5`，旧plan SHA `b4c9462f2d664b60506019e2b5ec540278634b5c5ab911fbd28fc9f3ca360ea3`，operator-stop.json记取消原因。
- **v6真实作业15140已运行gpu28**：05:48:58 UTC提交、05:49:00 claim；05:49:35最后观察RUNNING，服务加载中、无episode。唯一当前包`/research/d7/spc/yzyang4/task-feedback-real-20261001-v6`，plan SHA `15751d3b52bdc42617df02006ce724635f4bf49df6e477686769fd1979d53403`。共同修正JSON物化、复用0011有界后端（原source未安装，光config开关无效）、600秒单次请求不重试、原生模板step_limit由继承10000改为实际5。任务/起点/seed/每条1800/4修改/臂顺序未变。两次显式预提交manifest修订保留before文件；不能用旧v5 SHA验证v6。
- 18条=Spooky/Pizza/Tweet×2起点×A/B/C；每条1800秒含初始代码重执行，程序480秒，最多4次后续原生Improve/Debug。2GPU本地27B INT4/no-thinking/8192输出上限，3任务执行卡，同臂区组并行、第二起点逆序，不跨臂共享服务排队。不是完整ForeTS E2E、不是独立终评。
- v5服务启动585.604秒，无新方法效果。v6分配上限3h40=18.333GPUh，连同失败最多19.430555555555557GPUh，仍≤原20。service-ready、episode-*/launch/result/closed与all-closed才是后续证据。
- SSH linux5可用，Python `/research/d7/spc/yzyang4/venvs/aira/bin/python`，Slurm配置 `/opt1/slurm/gpu-slurm.conf`。状态脚本 `/tmp/task-feedback-stage-20261001/task_feedback_status_20261001.py --errors` 只给安全进度和脱敏异常，不cat私有日志。

## 协议、边界与有效预检

协议`FEEDBACK_REAL_PILOT_20261001.md`；源码`scripts/task_feedback_real_20261001.py`、`task_feedback_facts_20261001.py`；读出`task_feedback_readout_20261001.py`。所有三臂共有原生算子、任务镜像、共同parser修复与GPU UUID/minor白名单。agent只绑定本次work和公开开发视图，默认研究盘挂载禁用，标签只在trusted host评分。

旧checkpoint没有完整文件/RNG快照，本轮明确为同一旧代码在干净目录重执行后续改，不冒充历史状态恢复。起点固定每run最早execution_started=true的非空代码，Spooky原9/27 run0/3，Pizza1/2；Tweet原9/28 text run1和unstarted run0。不按成绩挑起点。初始代码重执行可能有随机性，要核三臂实际初始成绩/执行hash再解释效果。

B/C同一状态facts字节相同；轨迹分化后可以产生不同事实。长度边界只用公开训练词数：Spooky17/30、Pizza43/82、Tweet9/16。诊断整体/组分差绑定实际生成父代码SHA，不比较最近较差兄弟；缺父预测/单类AUC不是零。只有开发描述，不能声称自适应显著性或泛化。

CPU已完成：18原生配置/36模板；真实episode主循环mock三臂共15动作/12原生prompt、回退/保留最优；7 facts单测+4读出单测。3真实D_search scorer与独立常数预测聚合一致：n=1761/300/2454；仅CPU测量核验、不是模型效果。任务/服务镜像与全部6权重shard hash通过才提交。

v1起点索引错误、v2 factory配置/运行对象属性错误被CPU拦住；v3预检通过后补接原已验证容器白名单；v4父参照歧义于sbatch前中止，确认无intent/launch/新job。所有旧准备目录保留，无GPU耗用，不从其中读效果或重投。v5是唯一真实提交。

## Git与继续方式

公开分支本轮已快进push到`42f504632b2cbb0f4e24692e685275dbc98c2af8`，9个限定文件凭据scan零命中、3个冻结文件Git blob SHA逐字节一致。学长e385f863cb531904e611e987f7f71606796db656，本轮未修改学长分支。主目录HEAD仍14188f8956d5becfc1f192455647d7c4aedd1f82且有大量历史脏改，不整体stage/push/reset/rebase。
干净发布工作树`C:/Research/New/my_project/MLEvolve/_codex_tmp/publication-feedback-20261001`用于后续限定路径发布。**本地主目录CURRENT_DIRECTION与公开版有1427行历史差异，绝不能整份拷过去**。此轮只在公开版顶部加0L392。新独立重算脚本`scripts/task_feedback_verify_20261001.py`仅准备，不改冻结运行包，结果出现后从真实submission重算原生与独立指标。

v6最终CPU已完成（18配置/36模板、6真实SDK mock HTTP、三臂15动作主循环）；镜像/权重全部重新校验后才提交15140，submit session32114已完成。**不能重复submit/prepare**。状态脚本默认v6，--v5可核失败包。原生SDK测试已证明旧DictConfig拒绝、B/C事实入prompt且C证据规则存在，0网络；不是模型效果。本地7 facts+4读出单测再次通过。`readout`/`verify`现指向v6最终plan，仅访问新开发数据。
随后继续会话内监控新job，独立核真实指标、三臂起点一致性与预算；首批配对后给真实数值，完整18分母保留not_started/unknown/失败。固定读出不可丢未成功样本；不因开发正负改任务/seed/阈值/预算。三小时窗口内仍不足则报告确切完成量，不制造正结果。旧合成统计/204解析修复/旧critic分析已结束，不重跑。
