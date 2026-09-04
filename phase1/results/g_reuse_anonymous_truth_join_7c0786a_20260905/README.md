# G-reuse anonymous prediction--truth join kernel

状态：`ANONYMOUS_JOIN_KERNEL_READY_NOT_AUTHORIZED_FOR_PRODUCTION_UNSEAL`。

结果前 commit `7c0786a295dd9b56e85a4f81c505770d8ab3c417`固定了纯内存 join：prediction 与 truth
分别只能含匿名 SHA+margins、匿名 SHA+truth sign；pair support 必须 exact 相等，同一 pair 的 task/parent/run
SHA 必须逐项一致。排序后才调用既有冻结统计核，producer 与不导入 producer 的 verifier 分别 join 和重算。

正式 Linux 回执：

- exact archive SHA-256：`f0a44472c4fef017388ab605757fc4e75fdf806e4d19e1c90e8bef4a0642e82a`
- root：`/research/d7/spc/yzyang4/g-reuse-anonymous-join/formal-7c0786a-v1`
- A/B：`9 passed` / `9 passed`
- protocol SHA-256：`d6a0540b3a78cae15827d88dddb2419bef599be2fdf936e51abb74201212d7f9`
- producer SHA-256：`90ecaf8bda2014d450bcb54a7350dfe8d39c459ec0dde6feec83340bb09dd263`
- independent verifier SHA-256：`57f2423b4fe75577d5863146d6185db7888fbf4c246934cb512749bacd56febd`

测试覆盖正层级、阻断层级、missing/extra support、cluster漂移、duplicate、truth schema污染、NaN、协议漂移
与聚合gate篡改。开发期首轮发现协议字段顺序预期写错；次轮发现测试把scope声明键误当逐行truth并且独立统计异常
未统一封装。两项均在源码commit和正式运行前修正，未读取真实数据。

边界：该kernel不读文件，不认证prediction escrow、checkpoint、closure或pristine truth package，也没有生产CLI；
因此它不能打开或授权任何vault。未来仍需一个hash-bound one-shot caller按协议顺序认证上游后调用它。当前真实
truth、prediction和accuracy读取均为0，GPU/API/model fit也为0。
