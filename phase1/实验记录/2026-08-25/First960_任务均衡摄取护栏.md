# first-960 任务均衡摄取护栏

## 给学长的一页结论

first-960 的结构门早已冻结为“任一任务不得超过 canonical sibling pairs 的 25%”。截至最终 0823 snapshot，
first-960 有 339/960 runs、2,635 pairs、30 tasks；其中 OSIC 有 823 pairs，占 31.23%，所以即使 run 数最终达到
960，任务均衡门也不会自动通过。

不需要删除旧数据，也不应改变 chronological first-960 的定义。接下来只需做结果盲的 producer task allocation：

1. 暂时不再安排 OSIC，优先轮换其他任务；
2. 以实际产出的 canonical sibling pairs 记账，不按 raw runs 或预期产量记账；
3. 观察到至少 657 个新增非 OSIC pairs 后再重算；
4. 之后每新增 1 个 OSIC pair，累计至少再配 3 个非 OSIC pairs；
5. 每个稳定 snapshot 同时检查所有任务，而不仅是 OSIC。

这不会提前揭盲，也不是停止规则；它只是把既有 25% 门变成了可执行的前瞻收数护栏。

## 1. 精确推导

令当前总 pair 数 `N=2635`，OSIC pair 数 `D=823`，未来新增非 OSIC/OSIC pair 数分别为 `x/y`。
要求 OSIC 最终占比不超过 1/4：

```text
(823+y)/(2635+x+y) <= 1/4
4*823 - 2635 + 3*y <= x
x >= 657 + 3*y
```

因此：

| 未来非 OSIC pairs `x` | 最多允许的未来 OSIC pairs `y` |
|---:|---:|
| 657 | 0 |
| 1,000 | 114 |
| 2,000 | 447 |
| 3,000 | 781 |
| 4,000 | 1,114 |

若先令 `y=0` 并补足 657，最终总数为 3,292，所有任务均须不超过 823 pairs。故 657 是解除当前 OSIC 债务的
必要且对 OSIC 充分的数量，但不是全局任务均衡的单独充分条件。对任意任务 `t`，还要同时满足：

```text
4*(current_t+future_t) <= current_total+sum_future_all_tasks
```

构建器同时输出所有任务的当前 headroom 和 debt-clearance endpoint allocation capacity；独立验证器不调用构建器，
而是从两个哈希绑定输入重新计算上述整数包络、逐任务约束和结果盲证明。

## 2. 证据与复现边界

- structural gate SHA-256：
  `ca44845bc0f5feaf5de0e77ec658e4b0cca3f5a451b75b33bb4c63acfc1eccca`；
- seven-arm coverage matrix SHA-256：
  `be63fbe02c63c306bb488aa30416de7260e83e4701bdce3ed3f1d8843fd6f6b7`；
- guard SHA-256：`fd87246bb3656befba27de5a98c88f808ca39e178e7322d27ae9536fe4a751b0`；
- independent verification SHA-256：
  `7feaf1a7ad317963bbc6a7169f624a7e91f447424563df480d4765e2cba6760d`。

本护栏没有读取 label、grade、outcome、winner orientation 或 prediction values；没有计算 accuracy、方法 effect 或
search utility；GPU/API 调用均为 0。它也不授权旧 checkpoint scoring、transition effect 揭盲或任何 GPU 训练。

## 3. 科学意义与限制

这是对数据集质量的正面完善：它在 closure 前发现并可修复一个原本可能让 first-960 最终失效的结构风险，同时保留全部
历史 run 和预注册时间序。它不是 critic 性能突破，不能提高方法效果结论；真正的 predictor 正结果仍需等 first-960 +
independent closure 后按冻结协议一次性评估。

pair yield 在不同 run/task 间不固定，因此不能对学长说“再跑 657 个 runs”。准确说法是：暂时避开 OSIC，继续生产其他
任务，并由持续结构监控累计实际新增 pairs；每次新 snapshot 都重算债务与所有任务上界。
