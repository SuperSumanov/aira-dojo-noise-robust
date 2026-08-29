# Distribution-matched yield screen：公开结果包

固定分类：`POST_AUDIT_DISTRIBUTION_MATCHED_YIELD_SCREEN_DOES_NOT_ADVANCE`

本包只含公开 aggregate，不含 endpoint IDs、task/run identities、per-pair predictions 或任何前瞻 cohort value。

## 核心结论

结构优化达到独立 DP 全局下界，且六个 checkpoint 的 task-distribution L1 均大幅优于旧 yield；但这没有转化为 critic
收益。冻结七门只有 L1 gate 通过，其余六门失败。terminal 相对 old yield 的 pooled/task-macro accuracy delta 为
`-0.07971014492753623/-0.08391887524240466`，log-loss/Brier 也变差。因此 availability-matching acquisition 不晋级，
不得事后修改 gate、预算、task 集或 tie-break 救回。

## 审计锚点

- protocol SHA-256：`37ad2fab68227d4aa236f1ce8c70c6197d1160b3f885adc466288ea1af41b06e`
- formal commit：`ba75d078e1abf9542a11fa73c0de1a960312b5da`
- formal manifest：`44c41f55533d4fa3d94918bdc502128bebd4fd921fdc15038e6d47b4df85ed87`
- independent verifier SHA-256：`9de0e843d1c33c28ab26512273bc82b6bcd335d25c42deba06ae1f3494a27e4f`
- postflight manifest：`60949acd8203548a31f8ce1df4f701a2e8e346574dfb89a92ac2122b7963bf4d`
- focused/full：`26 passed` / `1652 passed, 48 warnings`
- GPU/API/new critic fits/base-agent updates：`0/0/2/0`

`runs.csv` 在纳入 Git 时统一为 LF；formal 原始 CSV SHA-256 是
`883d0d12d0573b043e9065aa9b99385845314d3e14094446a23680364e5cf2b1`，本包 LF-normalized 文件 SHA-256 是
`1f0007ca112ee48d77e3f3698a48a0d7d09ba21e71b80f039ece4f31bdaa9594`。

文件说明：

- `selection.public.json`：结构 objective、六 checkpoint aggregate 与 old-yield L1 对照；
- `summary.json`：两个新 critic、成对比较、七门和最终分类；
- `runs.csv`：一行一个新 critic fit；
- `verifier.json`：不导入 producer、0 refit 的独立重建回执；
- `preflight_13.txt`：正式运行前置检查；
- `formal_receipt.json`：本包与远端 formal/postflight 锚点；
- `scanner_audit_public.json`：r2 scanner false-positive 的结果盲审计摘要。
