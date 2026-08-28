# Tree linearization 的 edge-level estimand sensitivity：后验解析声明

## 诚实的时间线

0HC 的 multiplicity histogram 和 0HD 的 exact-recovery certificate 已公开后，我用该 histogram 做了一次探索性
解析计算，先看到了 edge-level TV、inverse-HHI diversity 和最大质量膨胀的数值，才写本声明。因此后续只能称
**已发表聚合量的确定性后验解析推论**，不能称结果前发现、独立确认或新假设检验。

已看到的探索值已逐项写进机器协议，避免用后续实现制造“盲算”假象。这里没有阈值、p 值、模型选择、任务筛选或
可被结果 rescue 的分支；正式工作的目的只是用精确有理数、第二种实现和固定输入哈希防止手算与代码错误。

## 固定问题与公式

令 `E` 为 canonical unique edges，`M` 为 path edge occurrences，`m_e` 为 edge `e` 的 path multiplicity：

- canonical measure：`p_e=1/E`；
- path-linearized measure：`q_e=m_e/M`；
- `TV(p,q)=1/2 * sum_e |1/E-m_e/M|`；
- `A+={e:m_e*E>M}`，严格检查 `q(A+)-p(A+)=TV(p,q)`；
- 对全部 `[0,1]` bounded edge statistics，`sup_f |E_q[f]-E_p[f]|=TV(p,q)`；
- canonical/path inverse-HHI descriptive diversity 分别为 `E` 与 `M^2/sum_e m_e^2`；
- 最大单 edge 质量膨胀为 `max(m_e)*E/M`；
- 每个 path occurrence 使用 `1/m_e` 后，逐 edge mass 精确回到 1，修正后 measure 与 canonical 的 TV 为 0。

inverse-HHI 只称描述性多样性，不称统计有效样本量。TV 的 sharp envelope 只说明存在某个 edge indicator 达到该差异；
不声称真实 predictor accuracy 或任何自然指标达到最坏界。

## 固定输入与边界

- linearization receipt SHA-256：
  `642e9fd793950d4dfd082669df164be0781bd13847f35d6483ebd8611a136ea8`；
- compatibility receipt SHA-256：
  `d5009a3464fb5d0597e67922bc7763af45271d0a06497b02b8fc2b7db989212d`；
- 只读这两份 aggregate receipts，不重新打开 blind manifests、raw archive、identity、code、truth 或 prediction；
- GPU/API/model fit/base update=`0/0/0/0`；
- 机器协议：`phase1/tree_linearization_estimand_sensitivity_corollary_v1.json`。
- 机器协议 SHA-256：`e4e6fcdb7fe859fc3b66b660cdca65093e8859b3b754ec54bc6e2cd33d1a84c0`。

正式 producer/verifier 必须分别从 histogram 做精确整数/有理数复算，并要求两个 receipts 的 E、M、duplicate count 与
完整 histogram 相同。任何 hash、分类、snapshot、accounting 或 exact identity 漂移均 fail closed。
