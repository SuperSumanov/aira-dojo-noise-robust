# G0 R4：输出隔离后的单次真实双卡重试

用户在本轮明确要求推进“G0真实跑通，以及同一生产版本、完整隔离的训练数据包”。
本轮按既有累计4 GPU-hour上限执行一次G0，不启动五臂正式训练，不更新agent底座。

## 固定配置与成本

Qwen3-1.7B-Base@ea980cb0a6c2ae4b936e82123acc929f1cec04c1；两张PRO6000，projgpu39，
gpu_24h/gpu，12 CPU，mem=0；seed6，max_len16384，microbatch8，grad_accum8，effective pair batch128，
10 optimizer steps，LR1e-5/cosine/warmup0.03，单次step10 dev评估，final-only。
source仍为5f3bc362db922c8edee2ef134656dfdb9a2b74fb；train/dev/Cards与前三次G0完全相同。
这些历史输入仅供工程校准，不能冒充新G-reuse来源包，也不能用于确认scaling。

Slurm本轮复核12181/12288/12377分别156/4/131秒，均分配两卡，累计582 GPU-seconds。
R4最长6909秒（01:55:09），最多13818 GPU-seconds；最坏累计14400 GPU-seconds。
单次提交、no-requeue、全新输出根；提交结果不明时禁止重投。排队耗时不算已用GPU成本。

## 唯一控制侧差异

沿用已通过A/B检查的shared OUTPUT/LOG外置修复；验收器增加具名R4精确时限，旧时限契约不变。
对真实launcher加file-syscall trace，保持私有；它可能带来时间开销，所得成本是带trace的工程校准，
不用于声称无trace吞吐加速。只有完成后的访问审查通过，才可补充隔离结论。

## 提交前13项检查

1. fetch最新方向；保留关闭方向及前瞻盲态；已读学长最新意见。
2. 精确源与control commit、干净工作树、不可写源根。
3. 源文件、模型离线snapshot、三输入SHA与已验收assets一致；只hash不输出数据。
4. 固定runtime依赖版本/关键文件与既有CPU保存回归重新绑定；不安装新包。
5. 新预算模式的正反例与原G0测试通过；shell语法检查通过。
6. 4GiB真实空间预留通过；只删除本次诊断临时文件，不清理旧产物。
7. 复核前三个job状态/耗时/卡数，queue为空；没有未知重复提交。
8. 只读源码外的私有新submission/run/scratch根；原失败证据保留。
9. strace可用，记录launcher后代文件访问；不把日志字符串检查冒充完整隔离证明。
10. 单job、两卡、6909秒、no-requeue；源和worker不可自行递归提交。
11. warmup首步与后九步分开记时；显存双卡采样；只有单seed校准，不报跨seed效果。
12. 完成要求真实10步、唯一dev、checkpoint-10完整、退出0、源/数据/模型不漂移。
13. 先保存失败/成功日志与hash，独立复核再报告；不读前瞻vault，不运行正式效果模型。

本文件替代旧报告中“本次仍未获授权”的操作状态，不修改历史失败或科学资格。
