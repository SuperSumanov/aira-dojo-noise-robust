# Transition future-escrow support audit

日期：2026-08-21。正式状态：`CURRENT_SUPPORT_NOT_SOURCE_INDEPENDENT`。

这是 future transition scorer 激活前的 outcome-blind 支持审计，不是效果实验。固定 source commit=
`4b6b997bdd08e48494ab68497a6f48f28e5a5032`，snapshot=
`83ab1d681ed863d2374a6648df4801e6dbd6fb80d89f4f20cec8d46de1d5c047`。producer 两次逐字节一致；不导入
producer 的 verifier 两次逐字节一致并对每个字段精确复算。

正式盘点：249 runs、6,471 cards、1,665 canonical sibling pairs；1,412 pairs 有同 task/run 父代码，coverage=
`0.848048048048048`，覆盖 24 tasks，最大 task share=`0.18838526912181303`。其中 1,134 parent-covered pairs
相对 train+dev 实际使用闭包满足 endpoint ID、physical run 与 parent/children code SHA 三重 source-novel。

但 current support 全体仍有 579 card IDs 和 579 code SHAs 落入实际训练闭包；physical-run overlap 为 0。
因此当前 snapshot 不能作独立效果验证。它全部早于未来 activation，strict future inventory=0，未读取 outcome
vault、score registry 或 effect metric。这个结果支持“未来协议结构可行”，不支持 transition 方法已经得到前瞻确认。

验证链：10 focused tests 与 574 phase tests 通过；producer/verifier stderr 和 reproducibility diff 均为空；
syscall forbidden-path hits=0；credential-shape hits=0；完整远端产物只读封存于
`/research/d7/spc/yzyang4/transition-future-support-audit/4b6b997-v1`。

封存 wrapper 在四次科学计算完成后因 `grep` 零匹配在 `pipefail` 下返回 1 而提前退出。结果读取前已识别该
后处理错误；finalizer 未重跑或修改任何科学输出，只写入零命中、erratum、conclusion 与 manifest。完整 erratum
保留在远端 `runner_erratum.txt`。

关键 SHA-256：

- producer summary：`820c4e1df9dc8d711dd2114e3cfac9c8eaac27d5d059be0632e784be9e54f57a`
- independent verification：`3bcb0587a551e28d2517df8612af78721e9ca68cfa11c0b4e00b30`
- conclusion：`ed71c37e34ba67678e7bd10513cd8d5ef0f61cbce1a81b276694c243d19a069a`
- output manifest：`c3579b4a3db7f2783d88e9e2aced53d5b0120c2afc36c895b0a7233aa7ccc067`
