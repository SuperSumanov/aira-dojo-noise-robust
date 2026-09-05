# 历史实际 launcher 清单恢复（结果前冻结）

8-run corrected leaf archive中已发现真实srun_pool manifest，task-set目录hash、执行目录、Slurm step与固定配置匹配。
下一步全量恢复固定旧历史范围；不依据覆盖率挑归档，不以合成测试代替生产证据。

- 输入：676-run source ledger SHA `8e48b4c6598cf8efe205fc6cba5cdd27d14621eb13fad42a7fd4180953da00d1`。
- 范围：该账本对应143种压缩SHA，旧archive manifest及单独corrected leaf；不扩入新0904或任何protected cohort。
- 每archive前后hash/stat核验；只读严格`batch/srun_pool/<hash12>/manifest.json`。其他manifest仅统计headers。
- 原文先credential scan、重复JSON key/schema/日期/目录检查，private仅保留调度来源字段；journal/env/log payload不读。
- 同archive+batch+config.id+experiment_dir绑定历史run。step不匹配单列，不悄悄改写。未匹配任务保留未解决计数。
- 真实launcher实例由created_at/snapshot/python/pool_dir/完整task集合定义；只是记录实例，不保证完整科学experiment。
- 新launcher联系只能合并旧保守组件，不能拆开旧hold闭包或释放任何留出run。输出全676行，不训练、不取效果。
- 两CPU，1500秒内部上限，逐archive落盘；任何未知schema/重复/漂移停止最终成功产物，保留失败。无GPU/API/fit。
- 先便宜负控制、固定Git代码；执行记录真实命令/时刻/Python/输入输出hash。独立实现复查membership和闭包。
- 样本量/统计功效/模型seed不适用：没有科学效果检验或随机抽样。字节确定性通过相同冻结输入重复运行验证。
- 源码README确有MLE-bench安装版本d0f60ad0d3b2287469ac3c8ac9767330c928c980，包含cache patch；
  这是安装recipe，不是当时已安装环境证明。已知snapshot与python路径无权限，不绕过，不补造pristine声明。
- 原S0失败、原hold、first960/Target300/522盲态、GPU12535配置与预算保持不变。

预期实物扫描约4—10分钟（不是保证）。A/B若任何未知schema失败，先保存失败，仅凭源代码验证schema后才考虑修复。

## 00:30追加：local_gpu_pool，同一固定输入，不放宽未知schema

首轮14e38d2已经恢复85个srun manifest、448个run，59个其它manifest仅查headers。
最小归档header显示local_gpu_pool；已先读取生产方b8d0951的实际生成函数，源码SHA
`c2b494bc78f1b079086c5cbf428c1dd8ff2fdaaf2a3bed2dc5057f5a1103156e`。
第二阶段同样固定143归档/676run，仅增加严格`batch/local_gpu_pool/<hash12>/manifest.json`。
local有独立task/attempt schema，记录execution_id/GPU分配而不是伪造Slurm对应；不读取results文件或GPU日志。
每次仍两CPU/1500秒上限，另固定新code及A/B输出。原首轮结果与异常保留，不覆盖。
必须将完整清单中不在676范围的任务计为未解决范围，不能凭已匹配部分宣称whole-experiment完成。

53a6b21第一次local阶段在43归档遇attempt_schema并fail-closed，无最终lineage，无B轮。
独立最小archive键名核查发现未知字段仅result；生产方_finish_task确将worker进程退出记录嵌入该键。
main_local_worker源码SHA `f3a56cc5d39867b0c2e99ccd9f8e673bf85ed88af54bd136c96040c48abe4ee2`确认它记录进程状态/异常，
不是评分器接口。修复仅接受此键但完全不访问或投影其对象/exception_summary；未知其它字段继续拒绝。
旧失败目录保留；固定新commit后同143输入A/B重跑，不改分组/筛选条件。
