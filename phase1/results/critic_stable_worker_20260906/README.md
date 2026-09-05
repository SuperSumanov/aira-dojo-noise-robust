# 合法续跑身份修复与训练worker边界（2026-09-06）

这解决真实生产入口的连接缺陷；不是数据来源补证、实卡验收或模型收益。
没有新GPU/API任务；12535仍使用原09911b15代码，本次未改其目录、环境或参数。

## 1. 修复了什么

原production entry把整个launch文件SHA传入session。合法续跑必须换新输出目录、恢复checkpoint路径及其SHA，
因此launch SHA必变，旧checkpoint会被固定binding拒绝。此前CPU测试使用固定工程字符串作为training contract，
证明了session恢复，却没有覆盖这个生产入口的契约连接问题。不能据旧测试声称生产续跑已就绪。

现在launch-v2引用逐字节固定的training definition。模型、来源/切分、encoder、四fit计划、runtime/code绑定
都留在该definition；每次作业的output/stop/checkpoint/resume另行记录。checkpoint绑定definition SHA，
launch SHA仍保留作审计。科学定义更改仍不允许沿用旧checkpoint，不设忽略binding的开关。
ADMITTED_RELEASES仍空；格式验证不能认证实际来源、runtime、隔离、预算和硬件。

## 2. 实际执行和独立复核

- 修复代码：`cfee2b099fa4524892463c9d8c95f4e98f6e05d3`。
- 固定accum8合成fixture：随机4433参数Qwen、2 CPU rank、float32 AdamW、dropout0.1、seed6。
  两臂各full/prefix/resume，重复A/B，共12工程轨迹、32小checkpoint。不是1.7B/16K内存试验。
- 各臂三个launch SHA确实不同，但固定definition SHA相同。8组实际model/AdamW/Python-Numpy-Torch RNG
  比较、8次rank最终状态比较和消费序列精确拼接均通过；A/B工程状态逐字节相同。
- 独立回执SHA：`69d8879fb3d3e1ab2a93ee0e4c62acdef49008bbe1d0d7261120764276cd7353`。
- 原始`runs.csv`逐工程轨迹记录seed、commit、预算配置、实际消费和状态。时间只是本次CPU工程开销，不估算生产速度。
- trace只作文件/进程路径负扫描；没有网络/FD/read语义全证据，不声称OS隔离。自有dev sentinel的创建/rename/stat
  不是读入；单独检查其read-open为零。worker单元测试未被这份trace覆盖。

## 3. worker新增边界

`b361b5b988d72556f15eb0ceb9efda4080bf8c24`补上已分配作业内的父worker：
核实际RUNNING、两PRO6000、CPU/节点/请求和分配TRES、禁止requeue/restart、历史主作业终态账、
累计GPU秒和剩余deadline。子进程超时/中断时处理自己的进程组；不调用sbatch、release或自动重试。
训练子进程不继承任意API key/proxy/PYTHONPATH。进程退出仅标为待独立验收，不替代训练完成回执。

Linux exp环境实际运行56测试通过，包括自有child/grandchild忽略TERM后的timeout/kill检查；
`worker_tests.txt` SHA=`eea662d0211de87ffefe14dbfb329281ad0a012c43f383bd7e8c4cd7955cffe7`。
Windows跳过Linux进程组测试不算通过，之后才在真实Linux补验。当前仍没有已准入的真实launch，
这不是实际Slurm worker/GPU验收；登记真实合同前不能启动。

## 4. 失败和边界完整保留

首次`e5c9b6935cde07849ab4a9067a9fb0ad16c3a038`在fit1-full训练前失败：工程读取清单未列新definition.json。
原失败日志和零checkpoint事实保留。修正为精确的definition→topology→必要targets序列后，在新目录A/B重跑；
没有扩大数据访问或改数值容差。科学checkpoint binding与原ZeRO3 session校验器未被绕开。

真实生产/evaluator/experiment及开发资格、实际Cards/G/L包、完整GPU入口验收、实测预算和存储仍缺。
这次新增证据不能成为G→L收益或干净scaling结论；也不能抵消原受保护cohort的访问限制。

## 5. 复现材料

`manifest.json`绑定11份原始文件；运输tar SHA为
`59b994f9502c7cbd798bb2f76f1c194bcf11566c941f8c85787971f6c37f7cf8`。
`operations/`保存初次/修正launcher、Linux测试launcher、源文件export和证据export；
源tar在运行前逐文件匹配exact Git blobs，执行后再次匹配，凭据形状命中零。
README和operations是随后附上的解释/命令材料，不冒充原11份结果manifest的成员。
