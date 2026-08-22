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
- `phase1/实验记录/2026-08-23/ScoreChannel_FutureIdentifiabilityCohort_结果前冻结.md`。
