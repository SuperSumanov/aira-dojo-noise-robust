# Outcome-blind 887 六小时无空窗续接预检

日期：2026-08-29

状态：`FROZEN_PRE_SUCCESSOR_AWAITING_PUBLIC_COMMIT_DEPLOYMENT`

## 动机

检查时 `LATEST=887491a021d75d889c00a5af672a11b8b06e249d98e84fd91288534080f62697`，尚无新稳定
snapshot，config-v2 sidecar filename count 为 0。现有 guard v3 的剩余窗口短于用户离开的六小时；transition、
prediction-receipt、config-v7 与 Target-300 也会在期间自然结束。为避免结果盲结构链出现无人值守空窗，本次只冻结
monitor continuity，不改变科学 population、阈值、estimand、selection、Target-300 quiescence 或 task-balance 协议。

## 固定顺序

1. supervisor 只读 LATEST、PID、锁、marker、exact normal-completion tail、hash、sidecar filename count 和
   `outcomes_read=false` 汇总。
2. 只有 guard v3 进程退出、锁 free、`COMPLETE` 与 manifest exact 时，才从公开 Git object 启动 fresh guard v4。
3. 只有 v4 已 live/lock-held，且 transition、receipt、config-v7、Target-300 全部以 887 正常结束、旧 PID dead、锁
   free，state/prior/script hash exact 时，才续接同一原协议。
4. transition/receipt/config 各保持 72×300 秒；Target-300 保持 144×300 秒；WL、intake、Target-522 与 live
   task-balance 均不重启。
5. 若观察到新 snapshot，只写 identity handoff 并停止 baseline renewal；若发现 config-v2 sidecar，只写 filename
   metadata count 并停在 redaction/review 前。任何未知 marker、重复进程、哈希漂移或锁异常均 fail-closed。

## 13 项预检摘要

- 方向与问题：仅 Decision Corpus + Predictor Benchmark + Audit Protocol 的结果盲连续性。
- 输入与禁区：允许结构 metadata；禁止 label、outcome、prediction value、accuracy、utility、raw archive 与 sidecar
  payload。
- 对照与身份：固定 baseline 887、公开 commit、原 monitor script hash、state/prior artifact hash 与 exact tail。
- 失败语义：自然超时不是科学失败；异常不得 retry/rescue；successor/sidecar 交给既有专用链。
- 资源与时长：CPU metadata polling；GPU/API/model fit/base update 均为 0；supervisor 上限 480×60 秒。
- 复现与安全：新固定 roots、umask 077、first-poll postflight、SHA256SUMS；不接触任何凭据。

## 实现与静态复验

- `guard_outcome_blind_continuity_887_20260829_v4.sh`：
  `7c67778bebe0c401a0b4b8e137f07f360eb5cae2f2829353f08baf60c7548a12`
- `renew_outcome_blind_monitors_887_20260829_v4.sh`：
  `53c24da67d2c9dc292307380e079b0b7c8cc3550fd4843815a01610131076a29`
- `supervise_outcome_blind_continuity_887_20260829_v1.sh`：
  `8febae8ee4397f5f9ec5b0a00da98f1a778acb138fe1d24a00aa41fc19b337e9`
- static test：`398dc9d4ecbe458f80a733c88a5a4d279ad5ecbb399064f8f05594f38968f01c`
- Bash syntax：三份脚本均 PASS；focused tests：`5 passed in 0.14s`。

本预检没有读取 prospective scientific values，没有启动 GPU、API 或训练。只有公开提交、推送、fresh post-push
复验全部通过后才允许部署 supervisor。
