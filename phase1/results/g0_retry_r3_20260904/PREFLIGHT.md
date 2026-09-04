# 单次G0 r3提交前范围 — 2026-09-04

用户明确批准：“提交吧，我是不是还要排队等好久”。只批准一作业、2 GPUs、117分钟、no-requeue。
12181/12288累计320 GPU秒；本次最坏累计14360 GPU秒（3.988888888888889 GPU·h）。正式五臂15 fits未批准。
目标：跑通固定10步的独立critic工程校准，取得训练/dev/保存墙钟；不验证scaling或搜索收益。
不是agent底座更新，不接触first960/Target300/Target522值，不改变任务、输入或训练旋钮。

固定：Qwen3-1.7B-Base@ea980cb0a6c2ae4b936e82123acc929f1cec04c1，seed6，16384ctx，bf16/ZeRO3，
2×8×8=128 pairs/batch，10steps，LR1e-5/cosine/0.03warmup，step10唯一dev/唯一模型保存，final-only不回载best。
原控制94ad7dafff1866c6d50eb54927a4bf56547facc2、训练源5f3bc362db922c8edee2ef134656dfdb9a2b74fb，
Torch2.11.0+cu128/Transformers5.12.1/Accelerate1.14.0/DeepSpeed0.19.3；两张PRO6000、projgpu39、gpu_24h/gpu。

## 对照项目预检清单（现有清单实际含13项）

1. 配置产物：复用exact resolved_cli及新静态回执，runtime rebind检查seed/context/batch/save参数；上卡后原worker再次核对。
2. 新路径：只换独占提交目录和已批准作业名，不改训练/保存路径；bash语法检查，既有G0与修复回执17项测试通过。
3. 重复/采样：无oversampling、LOTO、flip或新pair生成，固定train/dev SHA；本次不是采样或效果实验。
4. 分布解释：G0只计价，不从单seed或dev均值作正效果结论；不新看冻结任务结果。
5. 评估配平：固定一次完整历史dev，不为G0新增stratify/length-control旋钮；正式效果仍遵守其冻结配平门。
6. 模型保存：原save_only_model+final-only已做CPU保存回归；GPU唯一checkpoint-10必须由原完整verifier验证，尚不声称已跑通。
7. 泄漏：只用原component-split历史train/dev与固定Cards；既有pair/endpoint/run分离不变，不把此项冒充新的字节代码查重或干净scaling确认。
8. RNG：seed6、Python hash seed6，未改shuffle、输入长度或划分。
9. 发布安全：新提交只显式传递必要环境变量，不导出.env/密钥；运行日志不直接输出效果或凭据；发布前单独扫描。
10. 墙钟：尚无真实秒/步，不能保证10步在117分钟内完成；本作业即获取计价证据，上限由Slurm强制，超时失败保留不自动重试。
11. 功效：这是工程校准，无跨seed功效主张；正式15fits仍需来源和预算门。
12. 返回码：立即保存sbatch rc、orchestrator EXIT rc；不使用时间命令覆盖失败状态；不确定提交禁止重试。
13. 新语料：不扩训练集、不重抽split、不读新前瞻值；语料摄取与本次校准分离。

## 提交即时门

提交脚本会重新核验两次旧作业记账、空队列、修复后的干净且根目录不可写源码、原控制hash；
实际4 GiB fallocate/fsync检查成功才继续，诊断只移除自身临时文件，不删其它数据。运行库再绑定、末次git和队列检查通过后
才发出唯一sbatch。每次检查结果写独占submission目录；任何失败或不确定响应均不再次调用提交器。
源根只读不会被放宽；static/model/input hash上卡时仍由原worker重验，提交检查不保证排队期间环境永不变化。

排队事实（提交前05:14:51 UTC）：projgpu39两张PRO6000均被运行作业占用，其时间上限到香港9月5日12:38:50。
这是占用作业的最大结束时间，不是本作业的启动保证；实际预计时间需在提交后另查并按观测时间记录。
