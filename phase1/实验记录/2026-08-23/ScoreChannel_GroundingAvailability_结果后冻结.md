# Score-channel grounding availability：结果后冻结的描述性分解

日期：2026-08-23（冻结 UTC：2026-08-22T17:41:12Z）。状态：
`FROZEN_POST_HOC_SECONDARY_NOT_RUN`。本文件不授权 GPU、API 或模型训练；只冻结一个 CPU secondary analysis。

## 1. 时间线与证据等级

旧的 320-candidate score-channel replay 已于 2026-08-19 完成，仓库报告在本协议冻结前已经公开以下 aggregate：

- primary verdict=`SCORE_CHANNEL_MECHANISM_KILL`；
- completed replay=320；finite external=15，keyed stdout=92，both=7；
- primary common support=6 cards / 3 parents；external/stdout top-1 都是 1.0，delta=0。

因此本分析不是 outcome-blind、不是第二个 confirmatory test，也不能改变 primary KILL。冻结协议时没有打开四个 raw
result shards 或 label vault，但已有 aggregate knowledge；该事实已写入机器可读协议并由 producer/verifier 强制校验。
只有详细 parent-level 分解尚未计算。协议 commit 并 push 前禁止运行真实输入。

## 2. 冻结问题与 estimand

目标不是救回“external beats stdout”，而是描述 120 秒共同执行预算下，grounded channel 的价值由多少
**availability loss** 与多少 **conditional ranking loss** 组成。固定 158 parents / 320 candidates，不增删 task、parent、
candidate 或 cap：

- `external_then_uniform`：存在 finite pristine score 时按 oriented score 最大值选；否则在 parent 全候选均匀回退；
- `stdout_then_uniform`：存在 keyed numeric stdout 时同理；bare stdout 明确排除；
- `external_then_stdout_then_uniform`：有 external 就优先 external，无 external 才用 keyed stdout，再无则均匀回退；
- full oracle=max frozen `y_norm`；restricted oracle=max channel-available candidate 的 `y_norm`；完全无 channel 时按均匀
  expected truth 定义 restricted oracle；
- availability regret=`full oracle - restricted oracle`；ranking regret=`restricted oracle - policy expected truth`；
  total regret 必须逐 parent 满足前两者之和，绝对容差 `1e-12`；
- signal ties 对所有绝对差 `<=1e-12` 的 maxima 均匀取 expected truth；
- primary uncertainty=physical-run clustered bootstrap，secondary=task-clustered，10,000 draws，seed=20260813。

联合状态固定为 `both / external_only / stdout_only / neither`。输出 candidate CSV 只含身份与 availability bit，parent CSV
只含计数和 regret，不写 raw score、stdout、label 或 code。所有 task 均报告，不允许结果后挑 task 或 cap。

## 3. 锁定输入

- selection summary SHA=`f168a90043769d0d80257ec0af7f71c57d18b098f7390f615d66b1617ddd9441`；
- selected parents SHA=`49e808747532034ae653e0fdb45a3144f5fe4545ae5b8d1755d79545d4c64b81`；
- replay summary SHA=`0ea4766bd464248a91b95c10d4be720862ca2b631d2b849d78b4189deff580bf`；
- replay manifest SHA=`e20b43b9eee55395380def2772bfdab21f261eb3d850fc9a67ff0ccb4bc5fe58`；
- orientation SHA=`81c9684741cb166bf1b4e2d7cb91ed0c8742c5040945b44d22f1c61f18baf85a`；
- frozen worker commit=`ca3bb7315078f2c4bed99fa4c33d93c2f353d670`。

四个 result SHA、approval SHA 仍必须从已封存执行收据显式传入；producer 和独立 verifier 都要求恰好四片、320/320、
identity/SHA/worker 全绑定后才计算。协议 SHA 由结果前 preflight receipt 单独打印，禁止人工抄算。

## 4. 双实现与 fail-closed 门

`score_channel_grounding_availability.py` 生成三份原子输出；
`verify_score_channel_grounding_availability.py` 不导入该 producer，独立重算 availability、tie policy、regret、bootstrap 与
全部 CSV/summary。它只复用既有 independent frozen-input reader。任一 SHA、schema、orientation、worker、四片完整性、
regret 非负性、恒等式、CSV 或 summary 不一致即 rc=2，且不覆盖已有输出/receipt。

## 5. 13 项预飞

1. **产物侧旋钮**：四联合状态、bare 排除和三策略均出现在 candidate/parent schema；定向合成测试逐项断言。
2. **便宜验证新路径**：只跑合成 CPU 测试；真实 raw shards 在协议 commit 前不读。
3. **测试集查重**：无训练与过采样；固定 parent/card identity 逐层 SHA 绑定，candidate 不能跨 parent 重复。
4. **先看分布**：冻结 per-task、joint-state、parent availability 与 run/task clustered CI，不允许只报 aggregate mean。
5. **评估配平**：无模型 eval sampling；所有 17 selected tasks 原样保留，另报 task cluster，不做 task subset。
6. **模型保存**：无训练、无 checkpoint，N/A。
7. **泄漏三查**：无 train/test 学习；分析只读冻结 replay、vault label 和 receipt，输出不泄露 raw label/score/code。
8. **RNG 复现**：bootstrap seed=20260813；每个 cluster×contrast 用固定 CRC32 offset，输入排序固定。
9. **密钥扫描**：提交前必须同时做 filename scan 和高置信内容 scan；结果写入 preflight receipt。
10. **墙钟核算**：GPU=0、API=0、model fit=0；仅 CPU 线性 320-card 解析与 4×10,000 cluster bootstrap。
11. **训练侧功效**：无训练；统计支持固定为 158 parents/177-run cohort，不能因低 external coverage 追加样本救结果。
12. **链脚本 rc**：本轮不使用宽松链脚本；producer/verifier 任一异常均返回 rc=2，输出目录/receipt拒绝覆盖。
13. **扩语料前冻结抽签**：selection/replay 五个 SHA 与 158/320 counts 固定；0821 新语料不得进入本分析。

## 6. 解释边界

- 这是 post-execution scoring-channel systems diagnostic，不是执行前 critic，也不节省这 320 次 replay 的成本。
- tiny external coverage 已知，任何新数都必须同时展示 support；漂亮的 regret 点估计不能覆盖 primary KILL。
- hybrid 是预定义 fallback policy 的离线描述，不是已验证的在线 search controller。
- aggregate result 已知意味着所有 secondary p/CI 都是描述性 uncertainty，不是新的显著性证据。
- 直接竞品已关闭 broad grounding-gap novelty；该分析只能服务 D&B 的 MLE-specific availability measurement。

正式真实输入运行只允许在本协议、两份实现、测试与本记录 commit+push 后执行；结果无论正负都原样登记。
