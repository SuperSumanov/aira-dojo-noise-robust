# Task-conditioned top-centered run-OOF：13 项长实验预检

对应 outcome 前预注册：`TaskTopCentered_RunOOF_预注册.md`。以下 13 项必须由远端 launcher 在正式
v11 新 arm outcome 产生前 fail-closed 检查；不能只靠代码阅读打勾。

1. **产物侧旋钮**：summary/fold checkpoint 必须写入 commit、源码 SHA、输入/feature/baseline SHA、
   历史锚与 nested 2×2 四臂定义、两个固定网格、inner/outer folds、优化器全部容差和 seed。
2. **便宜测试优先**：本地 `py_compile`；远端固定 exp 环境 pytest；synthetic 完整链验证 winner edge、
   task fallback、run split、checkpoint 重入和独立复算；随后才允许 train-only engineering smoke。
3. **pair/test 去重**：训练 pair unordered duplicate/reverse=0；producer/verifier/launcher 均不得接受或打开
   文件名含 `frozen/test/held` 的 pair 参数；baseline OOF 必须逐行等于训练 pair。
4. **分布**：打印 pair/run/task/parent/endpoint、候选数直方图、各 outer fold 和 per-task run support；
   正式结构必须等于已推送 support audit，不得按任务删样本。
5. **评估平衡**：outer/inner 均按 physical run；损失每 parent 等总权；报告 micro、run macro、task macro
   与 paired cluster CI；D 固定为 main，禁止挑 G/B/C/D 最好者；factorial 效应只在共同 nested 协议内比较。
6. **保存昂贵产物**：每 outer fold 原子保存完整 inner-candidate OOF score 矩阵、inner grid、所选超参、
   float64 权重、outer-valid score 和 SHA；resume 前逐项校验，不覆盖失败目录；verifier 从 inner scores
   重算网格选择，并从权重重算 outer scores。
7. **三层泄漏**：沿用 v11 train/frozen node/run/code-hash 零交集审计；本实验只读既有 train endpoint
   chunks；inner 不见 outer-valid outcome；outer 不见 frozen；新 verifier 重新检查 fold-run 唯一性。
8. **RNG/数值流**：seed=887；旧 fold 列哈希锁定；inner GroupKFold 输入顺序锁定；L-BFGS 全零启动；
   BLAS threads=1；不得使用 Python salted hash；fit/checkpoint 均为 float64。
9. **密钥**：API=0，不 dump 环境变量；push 前执行精确 staged filename scan 和高置信内容扫描，均须为 0。
10. **墙钟**：synthetic 与 engineering smoke 实测后外推；formal hard cap 2,700 秒；每 outer fold checkpoint；
    超时只记 `ENGINEERING_TIMEOUT`，不得当科学失败或改网格重跑。
11. **训练侧功效**：4,263 pairs / 333 runs / 2,259 complete parents；773 multiway parents 覆盖 64.34%
    pairs；但稀疏任务存在，故 residual 强收缩并对 unseen task 回退 global，禁止独立 task heads。
12. **真实 rc**：producer/verifier 都先保存 `$?` 再打印；任一非零立即停止，禁止用部分 fold 计算 headline；
    optimization `success` 与 projected gradient 都落盘。
13. **冻结/append-only**：锁定 v11 LF 输入 SHA、旧 OOF SHA、feature manifest/chunk SHA；实验目录由正式
    commit 前缀唯一命名，已存在即 ABORT；v12+ 不进入本次结果，outcome 后变更须新 amendment/commit。

本实验不提交 GPU；若后续任何步骤意外需要 Slurm GPU，仍固定排除
`projgpu7,projgpu8,projgpu33,gpu36,gpu38`，并先设
`SLURM_CONF=/opt1/slurm/gpu-slurm.conf`，同时不超过 4 jobs / 8 GPUs。
