# Tree linearization within-stratum decomposition 结果前预注册

日期：2026-08-28

固定 snapshot：`887491a021d75d889c00a5af672a11b8b06e249d98e84fd91288534080f62697`

## 问题

已知 root-to-leaf linearization 相对 one-edge-one-vote 的整体 edge-measure TV 为 0.38618771447395162，task 与
physical-run marginal TV 分别为 0.1603376038171571 和 0.18894421733497543。下一步不是重复证明“有重复”，而是
回答审稿人最直接的反驳：整体差异是否仅由任务/运行的 composition shift 造成，还是在固定这些边际质量后，组内 edge
measure 仍发生广泛、非单组主导的改变。

## 结果前诚实披露

新 within-task / within-run 数值尚未计算或查看；但以下事实已知：由三角不等式，canonical-marginal-standardized
within TV 至少分别为：

- task：0.38618771447395162 - 0.1603376038171571 = 0.22585011065679452；
- physical run：0.38618771447395162 - 0.18894421733497543 = 0.19724349713897619。

所以“组内 TV 大于零/达到上述量级”是已有 aggregate 的逻辑推论，不能包装成新发现。真正冻结的强正结果要求
匿名 conditional profile 同时通过 breadth 与 anti-dominance 门。

### 结果前修订（仍未计算 synthetic 或真实新数值）

初版 commit `e99499efc2c85be0ac1551179a828ee06f23921a` 曾把“比 triangle lower bound 再高 0.05”设为
强门。实现审计发现这在概念上不对：slack 衡量的是三角界松紧，不是组内 distortion 强度；当 group marginals 完全
不变、全部 distortion 都在组内时，slack 恰可为 0。故在任何新 within-stratum 数值产生前移除该决策门，保留 exact
slack 仅作诊断。主门改为低于已披露逻辑下界的 `W_p` integrity floor 加 breadth/anti-dominance；真正的新证据只来自
后两者。这一修订不是看到结果后的降门。

## 固定 estimand

对每条 observed edge `e`，canonical measure 为 `p(e)=1/E`，path-frequency measure 为 `q(e)=m_e/M`。
对 task 或 physical-run partition `G`，组内条件 TV 为：

`c_g = TV(p(e|g), q(e|g))`。

主指标为 canonical-marginal standardization：

`W_p(G) = sum_g (E_g/E) c_g`。

它等价于保留 canonical group marginals、只替换组内 conditional distribution 后的 measure TV。secondary
`W_q(G)=sum_g(M_g/M)c_g` 仅做 sensitivity，不能 rescue 主指标。

## 强正结果门

条件 TV reference 沿用既有 TV reference 0.10。conditionable group 固定为至少有两条 observed edges 的 group，
零 TV group 仍留在 breadth 分母。

两个轴各自必须同时满足：

1. `W_p` integrity floor：task≥0.20、run≥0.15（两者均弱于已披露逻辑下界，不算新证据）；
2. task 中至少 1/2、run 中至少 1/4 的 conditionable groups 达到 `c_g >= 0.10`；
3. 最大匿名 canonical contribution share：task 不超过 0.40，run 不超过 0.20。

两个轴都通过才允许分类 `BROAD_NONCOMPOSITIONAL_LINEARIZATION_DISTORTION`。一个轴通过只能写 one-axis；其余只写
profile below strong gate。所有 exact fractions（含非决策性的 triangle slack）、匿名 histogram、median/p90/max、breadth counts 与最大贡献 share 都需
由不 import producer 的独立 verifier 重算。

## 13 项 preflight

1. question：固定边际后组内 distortion 的大小、广度与集中度；PASS。
2. estimand：canonical-marginal `W_p` primary，path-marginal `W_q` secondary；PASS。
3. inputs：固定 887 snapshot、原 tree audit 协议与两份 hash-bound aggregate receipts；PASS。
4. split/leakage：只读 blind manifest 与 aggregate receipt；禁止 label/outcome/prediction；PASS。
5. controls：synthetic equal-multiplicity、composition-only、pure-within（验证 slack 可为 0）、multi-group、tamper、cross-run、hash-drift negatives；12 个新测试通过，相邻回归合计 `48 passed, 1 skipped`；PASS。
6. sample/support：固定全部 10,895 observed edges；conditionable task/run 最低 15/150；PASS。
7. randomness：纯确定性 exact rational arithmetic，`PYTHONHASHSEED=0`；PASS。
8. inference：无 p-value/CI/accuracy/effect；按固定阈值作描述性分类；PASS。
9. cost：CPU-only，预计低于 0.5 CPU·h；GPU/API/model-fit/base-update=`0/0/0/0`；PASS。
10. resume：唯一 formal root，失败不写 COMPLETE，不覆盖已有输出；PASS。
11. environment：精确公开 commit 的 fresh detached no-smudge Linux worktree；PASS。
12. security：允许 basename 白名单、file trace、credential scan、匿名 aggregate-only 输出；PASS。
13. promotion：仅 A/B、独立 verifier、focused/full、trace、安全和 manifest 全部通过后发布；PASS。

## 边界

即使最高档通过，也不声称一般概率分解或图论 novelty，不证明完整 source tree、predictor accuracy/effect、search utility、
因果机制或 first-960 closure。它能支持的正面贡献仅是：在真实 MLE-agent observed forest 上，composition 并不足以吸收
tree linearization 引入的 edge-estimand distortion，且该现象按预注册标准跨 task/run 广泛存在。

## 结果前实现回执

在真实 population 运行前，producer、独立 verifier 与 synthetic tests 已完成：

- producer SHA-256：`38aa702d58e1250db31790227778130d6fca41939cdc4f74249cbfa3d766e25c`；
- verifier SHA-256：`c6158bb201d604180739c24f9cf57309f2159dbd2e7233190e0fe36db5690e16`；
- tests SHA-256：`08d874d98ed443378627213362e3e66b7af757f0d447228be6fc739ada11e3fd`；
- 新 synthetic：12 passed；连同 tree-linearization 相邻回归：48 passed、1 skipped。

此时尚未调用真实 887 population，因此没有 within-task/run aggregate 或分类可读。
