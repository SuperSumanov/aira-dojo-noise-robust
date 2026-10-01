# 当前短交接

更新时间2026-10-01 05:20 UTC（香港13:20），动态状态必须再核现场。

## 当前用户请求与已获授权

用户要求真实续跑，三小时后有价值信号。本轮04:33 UTC开始，目标07:33 UTC。用户已明确确认研究盘续期获管理员批准，不再询问或列为阻塞。当前主线0L392/0L391：固定生成器任务内可信反馈，同信息B/C、全成本A；不再以critic训练为前置。所有保护cohort、D_val/test边界不变，不恢复旧HCE/多保真/Probe/K≥1/底座更新。

## 本轮真实作业，禁止重复提交

- Slurm **15135**：05:19:59 UTC提交，05:20:02 controller claim；05:20:30最后观察RUNNING gpu28，5GPU/30CPU、4h上限=20GPUh。无付费API/模型训练。只有旧12535仍JobHeldUser，不触碰。
- 远端唯一运行包：`/research/d7/spc/yzyang4/task-feedback-real-20261001-v5`。
- plan SHA `b4c9462f2d664b60506019e2b5ec540278634b5c5ab911fbd28fc9f3ca360ea3`。
- 18条=Spooky/Pizza/Tweet×2起点×A/B/C；每条1800秒含初始代码重执行，程序480秒，最多4次后续原生Improve/Debug。2GPU本地27B INT4/no-thinking/8192输出上限，3任务执行卡，同臂区组并行、第二起点逆序，不跨臂共享服务排队。不是完整ForeTS E2E、不是独立终评。
- 最后观察只到服务加载，无已确认候选执行或新效果。service-ready、episode-*/launch/result/closed与all-closed才是后续证据。
- SSH linux5可用，Python `/research/d7/spc/yzyang4/venvs/aira/bin/python`，Slurm配置 `/opt1/slurm/gpu-slurm.conf`。状态脚本 `/tmp/task-feedback-stage-20261001/task_feedback_status_20261001.py --errors` 只给安全进度和脱敏异常，不cat私有日志。

## 协议、边界与有效预检

协议`FEEDBACK_REAL_PILOT_20261001.md`；源码`scripts/task_feedback_real_20261001.py`、`task_feedback_facts_20261001.py`；读出`task_feedback_readout_20261001.py`。所有三臂共有原生算子、任务镜像、共同parser修复与GPU UUID/minor白名单。agent只绑定本次work和公开开发视图，默认研究盘挂载禁用，标签只在trusted host评分。

旧checkpoint没有完整文件/RNG快照，本轮明确为同一旧代码在干净目录重执行后续改，不冒充历史状态恢复。起点固定每run最早execution_started=true的非空代码，Spooky原9/27 run0/3，Pizza1/2；Tweet原9/28 text run1和unstarted run0。不按成绩挑起点。初始代码重执行可能有随机性，要核三臂实际初始成绩/执行hash再解释效果。

B/C同一状态facts字节相同；轨迹分化后可以产生不同事实。长度边界只用公开训练词数：Spooky17/30、Pizza43/82、Tweet9/16。诊断整体/组分差绑定实际生成父代码SHA，不比较最近较差兄弟；缺父预测/单类AUC不是零。只有开发描述，不能声称自适应显著性或泛化。

CPU已完成：18原生配置/36模板；真实episode主循环mock三臂共15动作/12原生prompt、回退/保留最优；7 facts单测+4读出单测。3真实D_search scorer与独立常数预测聚合一致：n=1761/300/2454；仅CPU测量核验、不是模型效果。任务/服务镜像与全部6权重shard hash通过才提交。

v1起点索引错误、v2 factory配置/运行对象属性错误被CPU拦住；v3预检通过后补接原已验证容器白名单；v4父参照歧义于sbatch前中止，确认无intent/launch/新job。所有旧准备目录保留，无GPU耗用，不从其中读效果或重投。v5是唯一真实提交。

## Git与继续方式

公开head最后核bc74d8774eadbf3f82773bb456badde6e3b77f7f，学长e385f863cb531904e611e987f7f71606796db656，本轮未修改学长分支。主目录HEAD仍14188f8956d5becfc1f192455647d7c4aedd1f82且有大量历史脏改，不整体stage/push/reset/rebase。
干净发布工作树`C:/Research/New/my_project/MLEvolve/_codex_tmp/publication-feedback-20261001`已放入本轮6个源码/协议/测试文件及仅0L392顶部裁决与精确gitattributes，尚未stage/commit/push。**本地主目录CURRENT_DIRECTION与公开版有1427行历史差异，绝不能整份拷过去**。此轮只在公开版顶部加新裁决。等实际launch/结果做限定路径安全扫描发布。

继续会话内监控15135，独立核真实指标、三臂起点一致性与预算；首批配对后给真实数值，完整18分母保留not_started/unknown/失败。固定读出不可丢未成功样本；不因开发正负改任务/seed/阈值/预算。三小时窗口内仍不足则报告确切完成量，不制造正结果。旧合成统计/204解析修复/旧critic分析已结束，不重跑。
