# Frozen 0.5B @ 8192 长实验逐项预检

对应 outcome 前预注册：`Frozen05B8192_RunOOF发现门_预注册.md`。以下 13 项必须由 launcher 在远端
实际产物侧 fail-closed 验证，不能只靠代码阅读打勾。

1. **产物侧旋钮**：smoke/full 的 `metadata.json` 必须写入 commit、worker SHA、模型 SHA、cards/
   manifest SHA、max_len=8192、head_fraction=0.25、batch=2、chunk=32、shard 和 GPU/backend；rank
   summary 必须写入唯一 head 配置。
2. **便宜测试优先**：本地和远端 `py_compile + pytest`；随后只抽 16 个 label-blind sorted-prefix
   endpoints。验证 feature shape=(16,1792)、finite、token<=8192、chunk SHA 与二次调用不覆盖后才 full。
3. **pair/test 去重**：训练 pair 按 unordered endpoints 必须 0 重复/反向；manifest 只由明确 train 文件
   构建；冻结 pair 文件名不得出现在 discovery Python 的参数或打开文件日志中。
4. **分布**：实际打印 pair/run/task/parent/endpoint、每 shard、每 task 与 dominant share；dominant
   share>0.25 立即停止。最终报告 pooled、run macro、task macro 与逐任务值。
5. **评估平衡/长度**：GroupKFold 按 physical run；每 parent 等总训练权；报告 token min/median/max 与
   truncated share；task macro 和 parent-equal utility 防止任务、pair-set、长度代理主导。
6. **保存昂贵产物**：每 32 endpoints 原子写 float16 NPZ；metadata 保存 chunk SHA 和 resume 前缀；
   不删失败目录；底座本身只读且记录完整权重 SHA。
7. **三层泄漏**：pair unordered 去重；train/frozen node/run 零交集由既有 v11 audit 锁定；manifest
   code SHA 与 cards SHA；discovery 不接受 frozen 参数。后续若解锁，须重新做 pair/node/code hash 三查。
8. **RNG 流**：shard 由固定 CRC32，不使用 Python salted hash；GroupKFold 输入顺序为冻结的 pair 文件
   顺序；seed=887；不在扩语料后重抽旧 holdout。
9. **密钥**：提交前执行精确 staged filename scan 和内容模式 scan；产物只保存命令/环境版本，不 dump
   环境变量；API=0。
10. **墙钟**：smoke 测到 elapsed；按每 shard card 数外推；>3.5h/shard 不提交 full；Slurm hard cap
    4h，worker 每 chunk checkpoint；CPU head hard cap 900s。
11. **训练侧功效**：4,263 pairs / 333 runs / 23 tasks / 5,499 endpoints；比旧约 250-node 失败诊断
    高一个数量级，且采用 parent-equal weights；但只把本实验视为一个固定小模型基线，不外推 scaling law。
12. **真实 rc**：所有 worker、rank、verifier 均 `set +e; command; rc=$?; set -e` 后记录并原样 exit；
    禁止在读取 `$?` 前执行 `date`/`echo`。
13. **扩语料冻结抽签**：使用 v11 已冻结的 train/frozen physical-run 分配和逐字保留的旧 pair；manifest
    仅从 v11 train 端点确定性构建。v12+ 不得使旧元素重排或进入本次结果。

节点排除固定为 `projgpu7,projgpu8,projgpu33,gpu36,gpu38`；Slurm 命令前固定
`SLURM_CONF=/opt1/slurm/gpu-slurm.conf`；QOS 同时最多 4 jobs / 8 GPUs。
