# Confidence--cost scaling extension verification

状态：`ANALYZER_READY_EFFECT_ASSETS_PENDING`。本目录只记录结果前协议实现与独立复核，不含模型效果或真实 future truth。

- exact scientific commit：`72129bb2a0ad98ae075bdea3f0ef2269c9ead345`；
- extension contract SHA-256：`00ba64a222ae793c3f5d196ee754f0af9e2f01986ad85ed78c11b6f570da665b`；
- focused extension/primary/materializer tests：32/32（4.52s）；
- full `phase1/tests`：858/858（86.31s），33 个既有 warning；
- changed-file credential filename/content hits：0/0；
- fresh no-smudge worktree clean；
- persistent log：`/research/d7/spc/yzyang4/prospective_decision_v1/postpush_confidence_cost_72129bb.log`，
  6,309 bytes，SHA-256=`773c11ecb3cf7a111a44ef195f15f43df5efad29e487ed6b5ade5130f341952f`；
- future truth/GPU/API/model fit：`false/0/0/0`。

第一次扩大回归因漏设数值库线程上限而 CPU 过度并行，已主动中断且不计为证据；正式重跑固定
`OMP_NUM_THREADS=OPENBLAS_NUM_THREADS=MKL_NUM_THREADS=NUMEXPR_NUM_THREADS=1`。防 scoop 与项目内部前身的文档勘误在
`56a32caf2099b0b3f0b14975cdf0bcee958cf069`，不改机器契约或 scientific code。
