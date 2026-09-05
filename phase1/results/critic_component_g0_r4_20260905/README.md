# G0 R4：作业12486已失败，未跑通

2026-09-05终态更新：香港13:07:12开始、13:10:23结束，两卡191秒后在CPU Adam初始化因ninja入口缺失失败。
没有训练更新或checkpoint-10，没有自动重试。详见[终态独立核验](terminal/README.md)。
以下保留提交、排队与预算修正历史，不再代表当前PENDING状态。

最后现场核验：2026-09-05 11:45 Hong Kong，PENDING/Resources，已运行0秒。
调度器估计开始2026-09-06 11:47:17、结束13:36:17；只是可变化的排程，不是保证。

- 实际只提交一个job 12486，不重排、不重投；前三次失败12181/12288/12377保留。
- trainer/source仍5f3bc362db922c8edee2ef134656dfdb9a2b74fb。
- 有效control=adbfa80180e44805a6c0231e55c000b4718ad23b。
  其路径保留`/research/d7/spc/yzyang4/worktrees/g0_r4_46cd8f4_sparse`旧前缀；以Git HEAD和hash为准。
- 两张PRO6000/projgpu39、gpu_24h/gpu、12CPU、mem0、seed6、16K、batch128、10步、final-only不变。
- TimeLimit最终01:49:00；6540秒+300秒KillWait+60秒调度余量，连同已耗582 GPU-seconds合计14382，
  在14400授权预算内。实际成本最后以sacct为准，不把排队时间算训练成本。
- 4GiB真实空间预留通过，诊断自己的临时文件已删除；旧实验和检查点未删除。
- 源/模型/三输入assets及runtime重新绑定；最终远端27 tests passed in 0.27s，stderr0字节。

## 保留的失败与修正链

1. 初版trace改变launcher调用形式，使一个旧静态字符串测试失败（24通过/1失败）；恢复无trace原分支并
   单独测试trace分支，未绕过输出隔离检查。初版修复后本地/远端26项通过。
2. 新建`--no-checkout` control的index为空，第一次部署在Git clean门停止，未进入GPU提交。
   验证只有空index与零源码文件后初始化sparse checkout；没有重置或删除用户工作树。
3. sbatch请求01:55:09被Slurm按分钟向上取整到01:56:00。独立调度检查抓到后在PENDING/0秒时hold；
   先收紧到01:55:00，再结合真实KillWait收紧到01:49:00。没有GPU时间消耗或新job。
4. correction helper第一次在切换control前发生CalledProcessError，停在held状态，未发布修正完成回执；
   原始小回执保留。通过已配置环境单独fetch后，从精确held/old-HEAD状态继续；27项远端测试、
   worker/source不变和实际资源字段核验通过，才release原12486。

## 精确结构回执

远端目录`/research/d7/spc/yzyang4/critic-component-g0/submissions/20260905-g0-r4`：

|回执|原始SHA-256|
|---|---|
|READY.json（初版，已被有效修正替代）|84c353122a703e2e1d68489601f5669e945254aa91ba8df559462750e967fdf2|
|SUBMITTED.json|769efcc1f4b4efd3b2f83f21bab7400a8e42f210a4918cb44ad0076be6fb550f|
|CORRECTED_READY.json|0868a21175204dd0e93fe0d29afb8d0eaee66c8988717054f3663286f4274929|
|RELEASED.json|c325b07a27f8db850f8098cb3b9ef03861a5beb1d68c2e09bfc2c21ba6a93441|

运行根将为`/research/d7/spc/yzyang4/critic-component-g0/runs/job-12486`。
只有完整10步、唯一dev、checkpoint-10、数据/模型/源码未漂移和双卡资源回执通过才称工程跑通。
另需审查私有file_access.strace，不能把训练日志里没出现test当作完整文件隔离证明。
G0分数不是方法效果，也不能用于模型选择；同producer G-reuse包仍未验收。

本轮已把过期的六小时守护更新为30分钟只读G0跟进；仅状态变化通知，终态复验后停止，不授权新训练。
