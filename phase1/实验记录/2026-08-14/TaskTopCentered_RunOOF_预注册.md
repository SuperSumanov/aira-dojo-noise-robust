# Task-conditioned top-centered run-OOF（outcome 前预注册）

日期：2026-08-14；协议：`task_topcenter_v11_discovery_v1`；seed=887。本协议在任何新 arm 的
v11 OOF outcome 产生前冻结。它承接 `TaskParentSupport_结构审计.md`，属于 run-clean MLE-agent
sibling-decision benchmark 主线，不是旧 HCE、多保真或 probe 方向。

## GCCV

**Goal**：检验旧 frozen global-linear head 的失败，是否主要来自两个可分离的错配：训练目标把同一
parent 的所有 pair 当成等价，以及一个全局 code 方向无法表达 task×code interaction。

**Context**：训练支持固定为 4,263 pairs / 333 physical runs / 23 tasks / 2,293 parents / 5,499
endpoints。2,259 个完整 parent 全部形成严格总序；773 个多候选 parent 覆盖 2,743 个 pair。论文
frozen/test 不作为参数、不读取、不抽 embedding；v12+ 也不进入本门。

**Constraints / fairness contract**：

- 复用已落盘的 Qwen2.5-0.5B@8192 frozen endpoint embedding；不再调用 GPU、API，不更新底座；
- 表示仍为两个 896 维半向量分别 L2-normalize 后 concat 的 1,792 维向量，不换 layer、pooling、
  tokenizer、context 或任务集合；
- outer 5-fold 逐行复用 SHA-256=`083f4daa23ab3f8b1d9e412184fbe9ee06d891385e8f66e0bbbb29b3e3055a96`
  的旧 training OOF fold 列，确保与 global-linear baseline 同 pool、同 physical-run split；
- 每个 outer-fit 内另做 3-fold `GroupKFold` by physical run；所有正则选择只看 inner OOF，outer-valid
  在超参选择结束前不可见；
- score 固定为 `s_t(x)=w0^T x + u_t^T x`。global arm 固定 `u_t=0`；task arm 对所有 23 个 task
  共享 `w0` 并对 residual 做更强 L2。某 task 在 outer-fit 中缺失时，其 `u_t` 必须精确为 0，回退 global；
- 损失是无截距凸 logistic rank loss。all-pair 对一个 parent 的全部 edge 等总权；top-centered 只保留
  完整严格总序 parent 的 winner-vs-each-rest edge，并同样让每个 parent 等总权；`gap_raw` 不进损失；
- 固定正则网格：`lambda_global in {0.001, 0.005, 0.02}`；task arm 再取
  `lambda_task in {0.02, 0.1, 0.5}`。不在 outcome 后增删网格；
- 每个 outer fold 内，候选按聚合 inner-OOF 的 `(complete-parent top1, parent-equal gap utility)`
  字典序最大化；仍并列时优先更大的 `lambda_task`，再优先更大的 `lambda_global`；
- L-BFGS-B 从全零启动，float64 优化与 checkpoint，`maxiter=300, ftol=1e-10, gtol=1e-6, maxls=50`；每个 outer
  fold 原子保存完整 inner-candidate OOF score 矩阵、选择记录、最终权重和 outer-valid scores，可由
  verifier 重算选择后 resume；
- `gap_raw` 只用于预注册 utility 与 inner tie-break，不进入主损失；不能 outcome 后改成 gap-weighted loss；
- 所有 task、run、parent、feature、fold 和输出记录 SHA-256；实验目录 append-only。

## 历史锚 + 2×2 factorial 消融

| arm | edge objective | task interaction | 角色 |
|---|---|---|---|
| A `fixed_global_allpair` | all-pair | 无 | 已完成且哈希锁定的历史 baseline，不重训；只作解锁锚 |
| G `nested_global_allpair` | all-pair | 无 | factorial control：加入同一 nested 正则协议 |
| B `nested_global_topcenter` | winner-vs-rest | 无 | 相对 G 只改变 parent objective |
| C `nested_task_allpair` | all-pair | 强收缩 residual | 相对 G 只改变 task conditioning |
| D `nested_task_topcenter` | winner-vs-rest | 强收缩 residual | 主模型，组合两项 |

不允许只挑 G/B/C/D 中最好者作为主结论；D 预先固定为 main，G/B/C 用于机制消融。机制效应固定为
`B-G`（global 下的 objective）、`C-G`（all-pair 下的 task）、`D-B`（top-centered 下的 task）和
`D-C`（task 下的 objective）；另报 `G-A` 以隔离 nested regularization 本身。解锁主比较仍是 D-A，
因为 A 是在 outcome 前已完成并锁哈希的 benchmark anchor。

## 指标、推断与控制

1. 主指标：complete-parent top-1，预测并列沿用旧 verifier 的 precision 计分；
2. 共同主指标：parent-equal gap utility；
3. secondary：pair accuracy、run/task macro、至少 20 pairs 的 task consistency；
4. 对 D-A 逐 parent 计算 paired delta；分别以 physical run 和 task 的 cluster mean 做 10,000 次
   paired bootstrap，固定 seed；top-1 与 utility 都报告 micro、run-macro、task-macro 和 95% CI；
5. A 的 prediction SHA、逐行 fold/endpoint、既有 pair/top1/utility 必须被新程序和独立 verifier 精确复算；
6. deterministic random control pair accuracy 仍须在 `[0.47,0.53]`，orientation oracle=1；
7. G-A、B-G、C-G、D-B、D-C 全报告，不以它们替换 D-A 的预注册门。

## Discovery unlock（全部满足）

完整性：pairs=4,263、runs=333、tasks=23、parents=2,293、complete parents=2,259、fold physical-run
overlap=0、feature/OOF 覆盖严格相等；A 的固定 hash 与旧指标复现；全部 fit finite，outer fit 收敛或
满足 `max|projected gradient|<=1e-5`；真实 rc=0；总 CPU wall<=2,700 秒；random/oracle 通过。

主模型 D 的效果门：

1. complete-parent top-1 >= 0.50，且 D-A micro delta >= 0.03；
2. top-1 paired delta 的 run-macro 和 task-macro bootstrap 95% CI 下界均 > 0；
3. parent-equal gap utility >= 0.55，且 D-A micro delta >= 0.02；
4. utility paired delta 的 run-macro 和 task-macro bootstrap 95% CI 下界均 > 0；
5. pair accuracy >= 0.50；至少 15 个 supported tasks，且其中 pair accuracy>=0.50 的比例>=0.60。

任一失败即 `DISCOVERY_NO_UNLOCK`，不得读取 `decision_frozen_v11_b*.jsonl`。全部通过也只得到
`DISCOVERY_UNLOCK_RECOMMENDED`，必须另写一次性 frozen 评分协议。不能用 B/C 的偶然正结果替换 D，
也不能按 per-task outcome 路由模型。

## 资源矩阵与 ETA

- synthetic smoke：0 GPU / 1 CPU，预计 <2 分钟，只验优化、fold、checkpoint/resume、unseen-task
  fallback 和 verifier；不读取 v11 outcome；
- train-only engineering smoke：固定前缀 runs、固定单个网格点，0 GPU / 1 CPU，预计 1--5 分钟；
  只决定墙钟/内存是否可运行，不改变网格、arm 或门；
- formal nested OOF：0 GPU / 1 CPU，5 outer folds × 每 fold 3 inner folds；G/B 各 3 个网格点，C/D 各
  9 个网格点。预计 8--35 CPU 分钟，hard cap 45 分钟；每个 outer fold 原子 checkpoint/resume；
- independent verifier：0 GPU / 1 CPU，预计 1--8 分钟；重算每个 candidate 的 inner top-1/utility、
  fixed grid 选择、outer checkpoint scores 和全部 gate；API=0，底座训练=0。

## 允许的结论

若通过，只能称“parent-aligned objective 与强收缩 task interaction 使 frozen lightweight critic 成为
正向 baseline”；listwise/task-conditioned 本身在 NAS/ranking 已有先例，不单独主张 novelty。论文的新颖性仍是
run-clean MLE-agent tree benchmark、真实 sibling top-1/utility、标签/删失/成本协议和最终 prospective
fixed-budget search A/B。若失败，只关闭这一个凸 head family，不外推 frozen representation 或 critic 普遍无效。
