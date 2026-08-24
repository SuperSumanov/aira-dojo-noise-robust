# target-300 首次闭合到 prediction escrow：自动接力部署收据

日期：2026-08-24

状态：`CLOSURE_HOOK_ARMED / IDENTITY_ONLY / TRUTH_UNREAD`

## 1. 缺口与裁决

target-300 identity cohort 的首次闭合 runner 已能在达到 300 个 unique physical runs（保留完整 boundary
archive overshoot）时，以 `O_EXCL` 发布固定
`FIRST_CLOSED_COHORT_ANCHOR.json`。另一方面，后续 dual-truth runner 已把 component-breadth prediction
escrow 设为 first outcome-bearing read 的硬前驱。此前这两步虽然各自实现并测试，但闭合锚出现后仍需人工记得先运行
prediction runner；漏掉不会绕过 hard guard，却会在真正揭盲时造成不必要的流程阻塞。

本轮部署单次 closure hook，只监视上述固定锚路径。锚不存在时资源消耗为一个 300 秒轮询进程；锚第一次出现后必须同时
满足：regular non-symlink、无写权限、协议/状态精确匹配、selected runs≥300、identity selected before truth=true，且
label/score/outcome/replay 均仍为 false。随后它只运行已冻结的 component-breadth prediction escrow，不调用 dual-truth
runner，不接受备选 cohort，不重试失败，也不自动授权 replay/effect/GPU。

## 2. 固定执行身份

- closure monitor PID：`1922925`；
- monitor root：
  `/research/d7/spc/yzyang4/critic-component-breadth-future/monitor-e1093d8-first-closure-v1`；
- monitor SHA-256：
  `aa62ca508bfc877051d29a12ececa2785e18733bfbac3c8ff8e2b22c49e1d23d`；
- frozen runner SHA-256：
  `257373604bea09d4864431d17a9caf4f7fb5013829aa77d354647759969d7d97`；
- scientific control commit：`e1093d8007449954c4561611c2ff381c55f7abe8`；
- 固定矩阵：`broad/concentrated/random × seeds 20260823/20260824/20260825`；producer×2 与不导入
  truth module 的 source-refit verifier×2，总计 36 次 CPU fit；
- 轮询：4,033×300 秒，约 14 天；触发后预计 45–90 分钟；GPU/API/base-LLM update=0/0/0。

部署前确认 closure anchor、formal prediction root 与对应 worktree 均不存在；相关 runner/anchor contract 测试
`15 passed`。首轮日志为 `no_anchor poll=1`，因此截至本记录写入时 target-300 仍是 collecting，prediction 未拟合，
truth/outcome 未打开。成功触发后也只满足 dual-truth 的一个硬前驱；是否打开 truth 仍需 closure 后另行授权。

## 3. 边界

该 hook 不改变 target-300 的 estimand、archive 顺序、300-run target、boundary overshoot 或首次闭合锚；也不改变
first-960+accrual-closure 的独立 fixed-scorer confirmation。它是一项防止人工漏步的结果盲基础设施完善，不是方法结果、
accuracy、scaling、search utility 或正效果。
