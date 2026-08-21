# Status-Certified Source Partial Order v1：正式裁决

结论：通过，状态为 `VERIFIED_MATERIAL_STATUS_CERTIFIED_RELATION_RECOVERY`。

## 冻结问题与结果

控制 commit `82e1be5839506556e0edde5cd240e1918e2eed66` 固定了输入、关系、阈值与所有边界后，才读取真实
per-parent census 和 status registry。原发布覆盖为 5,897/9,755=`0.6045105074320861`。902 个精确恢复的
execution-error/grade-absent child 与同 parent finite children 形成 2,079 条 conservative validity relations；
certified coverage 因此提高到 7,976/9,755=`0.8176319835981548`，绝对增加
`0.2131214761660687`，恢复原缺口的 `0.5388802488335925`。

train 与 frozen gain 分别为 `0.22235838779956427` 和 `0.18819351975144252`，均远高于冻结的 0.08 门；
extension 为 `0.13924050632911392`。14 个支持任务中 11 个有新增 relation，dominant task share=
`0.18759018759018758`，未触发 0.35 集中度门。新增关系数、overall gain、gap recovery、两 role、任务支持、集中度、
整数 accounting 与 unknown 不提升共九个门全部通过。

94 个 unknown-status children、332 个未注册 missing slots、invalid-invalid 关系和未发布 finite-finite 关系均没有
被猜测，最终仍有 1,779 条 unresolved relations。这是 partial order，不是完整 total order。

## 防 scoop 与主张边界

- [NAS-Bench-101](https://proceedings.mlr.press/v97/ying19a.html) 已把 invalid architecture 返回最差 error；
- [PESC](https://proceedings.mlr.press/v37/hernandez-lobatob15.html) 与
  [BE-CBO](https://proceedings.mlr.press/v235/tian24g.html) 已覆盖 unknown feasibility/constraint 与 objective 的联合优化；
- [AMLB](https://arxiv.org/abs/2207.12560) 已把 AutoML framework failures 纳入 benchmark 分析。

所以 validity-first、failure-aware optimization 或 feasibility decomposition 都不申 novelty。可防守贡献仅是：自然
MLE-agent physical-run siblings、source identity/status provenance、failure-censored observability denominator 与
unknown-preserving certified relation release。`C(n,2)` 不是实际比较次数，validity relation 不是 missing numeric score；
不证明 predictor accuracy、search utility、MAR、因果性或 complete choice set。

## 完整性与失败历史

producer×2/verifier×2 逐字节一致；focused=`5 passed`，完整 phase tests=`649 passed, 25 warnings`；路径审计、
秘密扫描、worktree 漂移和可写文件均为 0。正式回传的 54 个 manifest payload 全部通过 SHA-256。

结果前的第一次 synthetic test 因 expected roles 含零计数 extension，而 `Counter` 的观测字典省略零键，5 项测试均在
真实输入前 fail。修复只把三个固定 role 的零计数显式补回；没有读取真实 relation 数、改 category、阈值、任务集或
科学计算。修复后 5/5 synthetic tests 通过，首次正式真实输入运行即得到本裁决。

该结果强化 Decision Corpus / D&B 正资产，不改变 first-960 closure、strict-future transition escrow 或 Qwen
G0/G1 的授权门。

