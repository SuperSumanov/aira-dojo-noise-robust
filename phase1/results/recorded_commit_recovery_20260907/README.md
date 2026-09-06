# Metadata Git版本恢复与12577终态（2026-09-07）

学长明确说明：直接使用metadata中的`git_commit_id`，多数旧snapshot已删除。
本轮据此核验已有Git对象，不再将找回24份物理snapshot作为恢复已提交代码的必需条件。
检查截止2026-09-07香港02:37（UTC 2026-09-06T18:37:11）。

## 可以确认的进展

- 固定676个历史run的metadata共记录24个commit，22个Git对象可读。
- **先前已固定的84个候选run涉及12个commit，12个全部可读，覆盖84/84。**
  独立实现重新连接原账本与原范围，并验证Git树对象SHA-1及文件清单SHA-256。
- 两个缺失commit涉及20和12个历史run，但在当前84范围各为0，不是该范围代码恢复的阻塞。
- 所有22个可读版本的`get_git_commit_id`只执行`git rev-parse HEAD`。
  所以恢复的是metadata记录的已提交代码，不是未提交文件或实际安装环境的证明。
- 不扩选范围，不读journal/成绩，不改旧hold，不新增训练准入，不启动真实Cards/G/L构建。
  后续以这12个确切版本继续来源核验；未提交改动、实际evaluator以及experiment/开发隔离仍分开记账。
  不能再笼统称“全部生产来源缺失”，也不能凭代码可读宣布同源干净训练包已经完成。

## GPU状态纠正

12577已于UTC 2026-09-06 08:09:11在projgpu39实际启动，08:10:49退出；
`FAILED / 1:0`，98秒、2张卡、实际196GPU秒。不是仍在排队，也不是存储再次不足。
已分配节点上的构建工具/尺寸门通过，但固定模型工厂要求FlashAttention2而运行环境缺包，
在模型初始化时报ImportError；没有轨迹完成summary，1.7B/16K验收未通过，没有critic/scaling收益。
此前171项CPU检查漏掉实际attention依赖，这是预检缺口，不以检查数量代替GPU成功。

12535仍为`PENDING / JobHeldUser`。本轮没有新提交、重试、安装依赖或后端降级；
12577失败目录和六份原始产物的hash保留。修复应单独固定依赖与真实后端检查，再登记新的有界尝试，
不能直接重投旧exclusive路径或把最长24小时理解为允许一次占满24小时。

学长给的交互式资源请求如下；两张卡、最长24小时是其说明，不是即时排队时间保证：

```bash
srun -c 12 -p gpu_24h -w projgpu39 --gres=gpu:2 --pty /bin/bash
```

我方已有batch流程已实际获配同节点双卡；不为此再开一份重复交互式请求。
集群操作仍设置`SLURM_CONF=/opt1/slurm/gpu-slurm.conf`，长任务用实际预算和可恢复作业管理。

## 学长分支与证据

本轮fetch观察`dojo-reproduce`为`40d7dea10738f159fc97cad8487ab4ada88022a3`，
提交日期2026-09-05T21:25:21+08:00。相较b8d0951的变更路径没有新outcome报告；
未打开新的train/test数据payload，未修改学长分支，不能把新代码提交当作新效果。

原始结果`recorded-commit-recovery-20260907.json` SHA-256：
`428db130b5eff7016469867c5d6c98288909449feceb087e9057c968e03b65cb`。
独立结果`recorded-commit-recovery-independent-20260907.json` SHA-256：
`ecb4ae0d00b04dcfb060f6a299b1505fe2c3b32d176558b8301a79e7f47ab1ab`。

两份脚本存于本目录；实际执行basename为`check_recorded_commits_20260907.py`和
`verify_recorded_commits_20260907.py`，在远端`/tmp`执行。两者只读固定历史元数据、Git对象与Slurm日志，
仅向研究盘根下各自命名的exclusive结果JSON写入一次。原路径已经完成，禁止直接重跑覆盖。
私有逐run身份不发布；输出只含commit级聚合、结构hash与工程失败信息。脚本SHA见原始结果。
