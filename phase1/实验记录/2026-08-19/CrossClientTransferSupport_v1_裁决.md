# CrossClientTransferSupport v1：裁决

日期：2026-08-19。裁决：`INSUFFICIENT_CROSS_CLIENT_TRANSFER_SUPPORT`。

## 验证结果

- 结果前 commit：`2e7ea07fc7ff5dfe476e6b6d8bfcf8877ff91adb`；
- Linux 全套测试：`399 passed in 35.11s`；
- producer 双跑、独立 verifier 双跑均逐字节一致；
- summary SHA：`43405484450ffea994ba69ef06b45c7c8e9db9962a8bda5e84327cf10513bb94`；
- verifier SHA：`19ea5b0a8c6d8c85a4f5f1df180c860076a32e7489cce59f09e0b5bde2da41e1`。

31,742 cards / 676 runs / 28 tasks / 11 clients / 11,946 train pairs 中，11,030 pairs 的两端同 client
且 exact execution stratum。所有 client 的跨 client exact-code overlap pair 数均为 0，排除了逐字节代码复制
作为结构阻塞原因。

真正的阻塞是共享 support：严格要求 held-out client 的每个 test stratum 在其他 client 中有≥50 pairs/≥2
clients 后，没有任何 client 同时通过预注册的样本、任务、run、训练量和集中度门。最接近的
`deepseek-v4-pro` 为 415 test pairs/4 tasks/14 runs/922 train pairs；`qwen3.5-397b-a17b` 为
442/4/14/895。全局 0 eligible clients、0 eligible test pairs，两个主门均失败。

## 裁决边界

按协议不实现、不运行 LOSO char-TFIDF/static 效果实验，不降低 15-run/1,000-train 等门，不把相近 client
单独挑出。该结果不能被表述为 critic 不可跨 generator 泛化；它表明当前自然语料的 generator、task 和执行环境
覆盖纠缠，严格 cross-generator estimand 不可识别。

下一次数据生产应把 client 作为显式设计轴：同一 task、hardware、time limit、execution timeout 下为多个 client
分配独立 physical runs，并在 outcome 前冻结矩阵。这样既补 future exact-stratum clean scaling，也能把
cross-generator transfer 从事后相关性改成可审计的分布外评测。
