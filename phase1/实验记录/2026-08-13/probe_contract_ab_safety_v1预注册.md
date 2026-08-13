# Probe-First Contract 小规模因果 A/B：Safety/Discovery V1 预注册

日期：2026-08-13
状态：**任何候选生成、API POST 或 GPU scientific outcome 之前冻结**

## 1. 唯一问题与边界

V2 已证明两个新任务可在约 11–13 秒产生候选特异且可外部评分的 probe，但没有标准 prompt 对照。
本实验只问：在新任务上，向 draft prompt 加入冻结的 anytime artifact contract，是否相对原始 draft
提高 host 120 秒内的可评分候选覆盖，同时不明显破坏 full candidate 的产出和质量。

这是 safety/discovery，不是论文确认实验：每任务只有一个 seed，禁止显著性、总体成功率、搜索加速或
venue-level 效果声明。V1/V2 的四个任务均不复用；旧 100-set fidelity 数据和 `decision_clean_b*.jsonl`
冻结 test 完全不读取、不训练、不用于阈值。

## 2. 冻结矩阵

固定 seed=`873`，底座和所有 operator client 均为 `deepseek-v4-flash`。六个 task×seed block 各有
original/contract 两臂，共 12 次 generation；每个相邻 pair 并行启动，命令顺序交替：

| index | task | arm |
|---:|---|---|
| 0 | chaii-hindi-and-tamil-question-answering | original |
| 1 | chaii-hindi-and-tamil-question-answering | contract |
| 2 | leaf-classification | contract |
| 3 | leaf-classification | original |
| 4 | nomad2018-predict-transparent-conductors | original |
| 5 | nomad2018-predict-transparent-conductors | contract |
| 6 | plant-pathology-2020-fgvc7 | contract |
| 7 | plant-pathology-2020-fgvc7 | original |
| 8 | google-quest-challenge | original |
| 9 | google-quest-challenge | contract |
| 10 | tabular-playground-series-dec-2021 | contract |
| 11 | tabular-playground-series-dec-2021 | original |

任务只按 modality 多样性和公开数据/标准 lowercase sample 是否完整选择：多语言 QA、表格+图像、材料
回归、图像多标签、文本多目标和超大表格。选择发生在任何该矩阵候选结果之前；不按结果替换任务。

## 3. 唯一允许变化的旋钮

- original：仓库原始 `mlebench/aira_operators/draft`；
- contract：`schema_probe_draft`，只新增 V2 已冻结的四条 artifact-contract bullet；
- preflight 必须对每个 task 的 resolved solver 删除 draft prompt 后逐字相等，并证明从 contract prompt
  删除恰好四条冻结 bullet 后逐字等于 original prompt，否则实验不启动。

两臂共同固定：task public data、seed、底座、温度/top-p、analyze/debug/improve prompt、算子集、
`step_limit=3`、`num_children=1`、`max_debug_depth=1`、`stop_after_first_valid=true`、candidate
`execution_timeout=600` 秒、solver 1200 秒、同一容器、GPU/CPU、pristine grader 和 grader 调用协议。
两臂都公平获得至多一次 conditional debug；首次 valid draft/debug 后立即停止。禁止 retry、补代码或换 leaf。

## 4. 冻结执行与观测

generation 完成后严格检查每个 run 只能为 `root→valid draft` 或
`root→buggy draft→single debug`；任何额外 branch、improve、配置漂移或 API/entry 非零均使本轮
**INVALID**，不替换。冻结最终 leaf 后，每个 code 在 production Singularity 中只连续 replay 一次；
public data 只读，checkpoints=`30,60,120,240,360,600` 秒，host poll=0.10 秒。

容器外 watcher 记录每次 stable `submission.csv` transition、host monotonic time、内容哈希、进程状态和
stdout/stderr；候选进程退出/终止后才由 pristine grader 评分 snapshot。candidate 不得接触 grader、private
labels 或 grader 输出。共同 sample copy、常数预测、schema 不合法、非有限 grade 均不算 scoreable artifact。

## 5. 冻结指标

逐 task×arm 报：

1. 首个 candidate-specific、schema-valid、finite-pristine-score artifact 的 host 时间；
2. `coverage_120`、120 秒时最新可评分 artifact 的分数；
3. process rc、artifact transitions、contract probe compliance；
4. full-like validity：contract 必须有 probe 后、600 秒内、hash-matched 的 full marker/event 且 rc=0；
   original 必须 rc=0 且有 finite candidate-specific endpoint；
5. full pristine score；公开任务指标方向预冻结为 Chaii/Plant/Google/Dec 越大越好，Leaf/Nomad 越小越好；
6. generation wall、LLM calls/tokens/latency、replay wall 和 scheduler allocation，不把 endpoint 的
   `cost=0.0` 字段解释成零货币成本。

主 paired estimand 是六个 block 的 `contract coverage_120 - original coverage_120` 之和。full quality
只在两臂均有 full-like finite score 的 block 上计算方向修正后的相对差：
`orientation*(contract-original)/max(abs(original),1e-8)`；同时完整报告缺失和 validity，禁止 complete-case
结果冒充总体。

## 6. Outcome 前唯一裁决门

- K0 compliance：contract 至少 4/6 个合法 probe；
- K1 coverage：contract 至少 4/6 coverage，且 paired 净增至少 2 个 block；
- K2 full validity：contract full-like 数不得比 original 少超过 1；
- K3 quality safety：至少 3 个 paired full scores；其中相对方向差的 median≥-0.05，且 `<-0.10` 的
  catastrophic harm 最多 1 个 task。

裁决：

- 四门全过：`PROMISING`，只授权冻结更大、独立 multi-seed/search-utility 确认；
- quality pair 少于 3：`INCONCLUSIVE`；
- K2/K3 失败：`QUALITY_KILL`，关闭 prompt-only contract；
- quality 可评但 K0/K1 失败：`NO_COVERAGE_GAIN`，不扩大；
- 任何 generation/replay/provenance/manifest 完整性失败：`INVALID`，不按方法输赢解释。

这些门不允许按 outcome 修改。同一批结果不得另开“更宽松”裁决。

## 7. 资源、成本和停止预算

- generation：一个 4×RTX3090 allocation，三波 pair-concurrent steps；每 entry 最多一 draft、一 debug、
  两次 analyze，共最多 48 条逻辑 LLM usage records；candidate execution 上限合计 2.0 GPU·h，parent
  90 分钟 hard cap 对应 6.0 scheduler GPU·h；
- replay：12 个 1×RTX3090 array elements，最大并发 4、每项 candidate cap 600 秒、scheduler 20 分钟；
  candidate execution 上限合计 2.0 GPU·h，scheduler hard cap 合计 4.0 GPU·h；
- 总 candidate execution 上限 4.0 GPU·h，总 scheduler allocation hard cap 10.0 GPU·h；不提交 150-run
  评分通道实验，不训练/微调任何底座 LLM；
- 排除 `projgpu7/8/33`、`gpu36/38`，设置 `SLURM_CONF=/opt1/slurm/gpu-slurm.conf`，并发不超过 4 GPU。

## 8. 13 项长实验前清单

1. 旋钮：矩阵、seed、prompt、温度、step/debug/time、checkpoint、容器与门全部落盘；
2. cheap test：py_compile、拓扑 fixture、worker/validator self-test、Hydra 12-grid compose；
3. 去重：6 tasks 唯一，original/contract 各一次，与 V1/V2 task 零交集；
4. 分布：六种任务结构逐项报告，不用 12 个 candidate 当独立同分布样本；
5. 评测分层：compliance/coverage/full validity/quality/成本分开；
6. 保存：完整 config、status、export hash、code、artifact、grader hash、命令与环境；
7. 泄漏：只挂 public data，candidate 不见 private/grader；冻结 decision test 完全不访问；
8. RNG/顺序：seed 873、index 映射和并发 pair 固定，不按 outcome retry/重排；
9. 密钥：只 source 远端 `.env`，不打印、不复制，commit/push 前文件名与内容双扫描；
10. walltime：generation/replay 双层 candidate 与 scheduler cap，失败进入结果；
11. power：N=6 仅 safety/discovery，不报 p-value/总体效应；
12. rc：entry、scientific step、parent、replay、validator rc 分开保存后再写日志；
13. freeze：本文、代码、tests、resolved configs 与 Git commit 必须在任何 API POST/GPU outcome 前固定。
