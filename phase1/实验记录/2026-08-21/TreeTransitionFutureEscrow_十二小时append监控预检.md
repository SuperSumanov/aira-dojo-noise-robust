# Tree Transition Future Escrow：十二小时 append 监控预检

日期：2026-08-21。状态：`MONITOR_PREFLIGHT_PASS_READY_TO_LAUNCH`。正式 activation 已由
`3e17ff7...` 报告固定；本监控只在 `prospective_decision_v1/LATEST` 变化时对新 blind snapshot 追加预测，
不读取 score/outcome，不计算 effect。

## 固定行为

- 默认每 300 秒检查一次，共 144 次，约 12 小时；无变化只记 receipt，不重复 full-fit；
- checkpoint 为 `last_snapshot / prior_artifact / prior_summary_sha256` 三元组，原子更新并用 `flock` 禁止双实例；
- 每个新 snapshot 固定执行 producer×1 + independent verifier×1，共 6 次既定 HGB fit；
- 必须保留 prior 的全部 pair rows 且逐字段不变，训练 reference 与 future margin 独立复算差必须为 0；
- producer/verifier 都在 `strace -e trace=file` 下运行，forbidden path 或 credential-shape 任一命中即 fail closed；
- 每个成功 append 独立 manifest、验证后递归只读，失败不推进 checkpoint；
- 固定 commit、protocol、activation、model spec/reference/verification 与全部 SHA，不使用当前 branch 的后续源码。

## 资源与边界

常态无新 snapshot 时只有轻量 metadata poll。每个新 snapshot 为单线程 CPU、6 次固定 HGB fit，预计 3--6 分钟；
GPU=0、API=0、base-LLM update=0。监控输出只报告 support inventory 与 append receipt；即使支持门意外达到，也不自动
读取效果、不自动揭盲，只提示另行执行冻结统计。启动前必须完成 `bash -n`、单 poll no-change smoke、源码凭据扫描和
远端锁/状态路径核对。

## 预检结果

候选脚本 SHA-256=`52df665581b31986bb9db0cb79458e69194d1e7398cbabcd409b6670c5ded154`。本地
`bash -n` 通过；远端从正式只读 activation/model/escrow 初始化 checkpoint 后，以 poll=1、sleep=1 的 no-change
smoke 正常退出。它读取到的 LATEST、checkpoint snapshot 与 prior summary SHA 均逐字节等于正式 receipt；没有生成
append artifact、没有 full-fit、没有 outcome 访问。正式 144-poll 实例只可在本脚本提交并再次核对 SHA 后启动。
