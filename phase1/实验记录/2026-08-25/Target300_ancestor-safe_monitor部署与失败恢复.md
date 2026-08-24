# target-300 ancestor-safe monitor：部署与失败恢复

日期：2026-08-25

状态：`DEPLOYED / FIRST_POLL_NO_CHANGE / OUTCOME_UNREAD`

## 1. 部署目标

`ab59a01...` 已把 target cohort formal runner 的发布证明从 exact branch-head equality 修正为 ancestor proof，同时保留调用者
control commit 的 exact detached worktree。部署目标是让下一次 snapshot 仍使用该 exact commit，但不再因后续 docs-only
push 失败。baseline 固定为 `f109ac...`，previous prefix 固定为既有 53-run `producer_a`；identity/order/boundary overshoot
契约不变。

## 2. 首次交接失败

交接顺序为先完整准备新 worktree/runner/monitor，再确认旧 monitor 未触发，随后停止旧 PID 并封存。首次脚本正确停止了
旧 PID `1926934`，但在复制 stop receipt 时错误假定旧 root 存在 `runner_sha256.txt`，因 `cp` 找不到文件而 fail closed。

失败边界经恢复前独立核验：

- `LATEST` 仍为 `f109ac...`；
- 旧 monitor 没有 `new_snapshot/formal_finished` 记录，也没有 formal stdout/stderr/rc；
- 新 root 与 exact clean worktree 已完成准备，但没有 `monitor.pid`，即尚未启动；
- truth/outcome/prediction effect 未打开，GPU/API=`0/0`。

恢复没有删除或覆盖失败史。旧 runner 本体仍在，因此从本体现场计算哈希，而不是伪造缺失 sidecar；首次脚本 SHA-256
`a90181c5503fe8c03ebd40c206437c59cbf68ba4c5b5830a601b4d8409eae222` 与错误原因都写入 stop receipt。

## 3. 不可变旧 monitor 收据

旧 root 在恢复后封存为：

`/research/d7/spc/yzyang4/score-channel-future-identity-cohort/monitor_795e3da_stopped_by_ab59a01`

逐文件 `sha256sum -c SHA256SUMS` 全部通过，`COMPLETE` 与 `SHA256SUMS` 为只读；后者自身 SHA-256 为：

`1857ec8bbb1bd37b7d144e9640bfe47c7b555a1f85fa1318062c872731594847`

机器字段为 `new_snapshot_seen=false`、`formal_runner_started=false`、`outcomes_read=false`、GPU/API=`0/0`。

## 4. 新 monitor

新 root：

`/research/d7/spc/yzyang4/score-channel-future-identity-cohort/monitor_ab59a01_next`

固定标识：

- control commit：`ab59a011d945e4a96daf7dbbbc927a59027da077`；
- runner SHA-256：`c6f6ed7abda2fbe6252271f2707e576845b1fd950aa9884d03597b86be8f660e`；
- monitor SHA-256：`02fd9081d5732bc82e8b91527da31e83a8ebae6656bc23092b07d6e4b25636b0`；
- launcher SHA-256：`00f62349ce2ce9b361445004e2c958efd1e834c46fe588447a4ad6583a6c2048`；
- PID：`1985359`。

首轮在 `2026-08-24T19:40:59Z` 写入 `no_change poll=1`，baseline 仍为 `f109ac...`，outcomes unread。静态复核确认
runner 同时含 `merge-base --is-ancestor` 和 exact worktree `rev-parse HEAD == commit` 两道门。此部署只修复控制面脆弱性，
不新增 effect、accuracy 或 cohort 样本。
