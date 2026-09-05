# 训练文件到实际 consumer 的 CPU 验收（2026-09-06）

## 设计与边界

接入已存在的四fit开发screen和token consumer，不修改五臂确认协议、不重做数据划分。
新文件读取器严格绑定TRAIN topology/L targets/G targets；Lbudget不打开G targets。
生产入口注册表保持空：没有真实生产来源、预算、存储及GPU验收，不会加载生产模型。
hash/role声明只是绑定，不等于资格。prepare→计划核验→所需标签→模型→训练→完整状态保存。

本轮只用在`/tmp/critic-entry-cpu-*`生成的8个虚构endpoint，4G/4L边；
同端点复用、相同token cap；Lbudget/G-to-L各seed6/7，共4完整轨迹；
seed6每臂另加prefix/resume，共8轨迹；A/B重复，共16条工程轨迹。
每轨迹2进程CPU、4433参数随机Qwen、float32、AdamW/WD0、dropout0.1、2updates；
不是Qwen1.7B训练、不是真16K压力测量，不产生accuracy/utility或源数据资格。

## 逐项预检

1. 产物记录arm/seed/plan SHA、实际pair/token/update/LR、step owner及完整状态哈希。
2. 新入口先本地纯函数测试，再远端实际CPU-DDP四fit和新进程恢复，不占用GPU队列。
3. 数据仅脚本生成；不打开真实train/dev/protected路径。哨兵文件禁止输入读取。
4. 逐rank/逐轨迹核验；工程计数不能解释为研究分布或统计功效。
5. 不运行效果评估；任务分层与长度配平在后续独立、合格开发读出中执行。
6. 每个固定停止点保存model、AdamW、Python/NumPy/Torch RNG、cursor、manifest。
7. 原训练角色/内容哈希检查，不创建真实split、不访问保护集去查重。
8. 配对同seed同初始化；恢复前故意使用不同RNG，核所有状态和实际消费前后拼接。
9. 提交、导出、公开回执均credential-shape scan；原日志远端留存，不公开原文。
10. A/B各最长15min（外层timeout给清理余量），单轨迹150sec并终止整组子进程；
    无后台无限循环、不新建Slurm/API任务。运行时间和峰值记录但不外推1.7B成本。
11. 8endpoint只检功能，不宣称有学习功效；来源、真实pair规模、跨task/experiment支持仍待实际证据。
12. 链式步骤失败立即停，保留失败目录和日志，不将后续成功覆盖原失败。
13. 不修改accrual或抽签；first-960/Target-300/522、已有GPU12535及原冻结协议不变。

## 验证与证据

commit后按Git blob导出依赖闭包，禁止CRLF改变远端审计哈希；使用已固定R5运行时。
独立verifier先校验每个checkpoint manifest绑定/文件SHA，再比较自有工程checkpoint实际
模型、优化器、所有rank RNG字节。比较A/B结构状态，不要求时间/路径/容器序列化字节相等。
trace只宣称覆盖的进程文件访问检查，不宣称OS sandbox。
只有CPU完成后才能说训练入口贯通；仍不能说生产准入、GPU完成、scaling或方法收益成立。
