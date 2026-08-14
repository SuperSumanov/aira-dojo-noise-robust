# Balanced continuation：Qwen 两脚本 execution-only smoke 预注册

日期：2026-08-14。状态：用户已批准后续 E1；本门发生在任何 fresh-anchor E1-Q API/GPU 动作前。
稳定论文主线仍是 run-clean、decision-local benchmark 与 first-960 前瞻确认。本门只判定两个先前
hash-bound 的 Qwen 完整脚本能否实际运行，不估计方法效果。

## 固定输入与不可越界项

- 来源 probe summary SHA-256：
  `a30aa463a75ead9fa48fcd53a37921749425ac4a8ee696b18c2d0be33413ed1d`；
- 两个 raw response 已在 0-GPU probe 中产生并以 mode 0600 保存；本门 API calls=0，不重生成、不重试；
- 模型身份只作 provenance：`qwen3-coder-flash`、temperature=0、thinking=false、max tokens=8192；
- 固定任务顺序为 `spaceship-titanic`、`tabular-playground-series-may-2022`；
- 旧 warm states 的 D_val 已在工程诊断中揭开，因此这里只检查进程状态与 public
  `sample_submission.csv` 的 header、逐行 ID、行数、有限预测；禁止读取或报告 D_search、D_val、D_test、
  external score、gain、utility、first-960 或 prospective outcome。候选按冻结 prompt 打印的内部
  train-validation marker 只留在原始 terminal receipt，不进入 gate 或汇总字段。

## 资源矩阵与执行契约

`2 tasks × 1 frozen response/task = 2 Slurm jobs = 2 candidate executions`。每 job 1×RTX3090、6 CPU，
执行硬 cap 600 秒，候选部分最坏 `2×600/3600 = 0.333333333333333` GPU·时；API=0、retry=0、
replacement=0。array concurrency=2，排除 `projgpu7,projgpu8,projgpu33,gpu36,gpu38`。

候选在 fresh per-index workspace 中运行；Singularity 固定
`--containall --cleanenv --net --network none --no-home --no-mount bind-paths --no-eval`，仅只读挂载
public task 与 HF cache。原始 response、旧 sealed labels 和 host 凭据不挂入 candidate。

## 预注册 kill gate

只有以下条件全过，才解锁 fresh-anchor E1-Q 的准备与提交：

1. 两个 job 都产生原子 rc receipt，producer 与安全扫描 rc=0；
2. 两个脚本均未 timeout、进程 exit 0，并实际产出 submission；
3. submission header、逐行 ID 顺序、行数与 public sample 完全相同，所有预测可解析且有限；
4. 不 import producer 的 verifier 重建 response→code hash、检查容器命令、submission 与无分数边界；
5. 文件名和内容凭据扫描均为 0。

任一失败即状态 `VERIFIED_QWEN_EXECUTION_SMOKE_FAIL`，停止 fresh-anchor E1-Q；不改脚本、不换模型、
不增加 token/time、不重试来追 PASS。即使 2/2 通过，也只说明 execution engineering 可行，不说明
Qwen 优于 DeepSeek、continuation 有 gain 或 hurdle critic 有效。

## 13 项预检映射

1. estimand/撤回边界：只测脚本可执行性；
2. cheap tests：producer 与独立 verifier 聚焦测试必须先过；
3. 输入：恰好两个已 hash-bound response，任务与顺序固定；
4. 资源：2 jobs、2 executions、0 API、上界 0.333333333333333 GPU·时；
5. 划分：旧揭盲 anchor 只作工程回归，不读 frozen/first-960/D_test；
6. resume：每 index 新目录；存在即 fail closed，不重复计费；
7. 公平：只检查同一冻结脚本，禁止方法比较；
8. RNG：无新 generation；response 与 prompt hash 固定；
9. 密钥：raw mode 0600，candidate clean env，push 前双扫描；
10. wall smoke：两任务都须在 600 秒内产合法 public submission；
11. 停止：2/2 全过才解锁；
12. rc：Slurm/producer/verifier/safety 分别保留；
13. append-only：精确 commit、新 run root、独立 verifier 与 hash receipt。
