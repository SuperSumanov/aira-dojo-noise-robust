# Future score-channel identifiability cohort freeze

状态：`FROZEN_OUTCOME_UNREAD_WAITING_COHORT`。protocol SHA-256=
`54187f386ee18f009b57ccd04f851083160db3e607a4e8a760e070b276ac377d`。

冻结时 0821 archives=12、ready=0、committed 0821 intakes=0；只读 path/size/mtime inventory，archive payload、label、
grade、code、stdout、submission 均未打开。GPU=0、API=0、model fit=0。

本协议固定 first-300 accepted physical-run cohort、完整 boundary archive、每 run 最多 2 parent 的 SHA lottery、exact
non-tie 与固定 gap bins，以及 80 parents / 8 tasks / dominant≤0.25 / 60 runs 四道 CPU 资格门。PASS 只允许准备另一个
精确 GPU 申请，不自动授权 replay。

直接证据：

- `phase1/score_channel_future_identifiability_protocol_v1.json`；
- `phase1/实验记录/2026-08-23/ScoreChannel_FutureIdentifiabilityCohort_结果前冻结.md`；
- `remote_verification_74e4920/`：从 GitHub commit
  `74e492027b95cd1e44f205f7705c00736d9740b5` 建立的 fresh no-smudge worktree 回执。远端 Python 3.11 下
  focused=`1 passed in 0.03s`，完整 phase1=`748 passed, 33 warnings in 58.59s`，前后 worktree 均 clean，
  文件名/内容密钥扫描均为 0；`SHA256SUMS` 文件自身 SHA-256=
  `b05583c1f85f6e8fade8612365f37ce1763c046e3b6a21c2783519a694a9f86a`；
- `formal_identity_cohort_53ce46f/`：identity-only closure producer×2 与非导入式 verifier×2 formal 回执。
  fresh no-smudge focused=`11 passed in 0.56s`、完整 phase1=`758 passed, 33 warnings in 55.55s`；forbidden
  open、文件名密钥扫描、内容密钥扫描都为 0。当前机器状态为 observed future archives=12、future transactions=0、
  settled=0、selected runs=0/300，首个 pending archive=ranzcr。`SHA256SUMS` 文件自身 SHA-256=
  `fefb6a767ebe77ce9232c1423212d8fe062340b6753ad4493f97301d62e3febe`。

`0/300` 只表示归档尚未跨过预先固定的 6 小时稳定门，不是 effect 估计，也不授权 replay。
