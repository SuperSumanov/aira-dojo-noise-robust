# 0820 LMSYS archive 结构性拒收

- 精确归档：`0820/lmsys-chatbot-arena-8seeds.tar.gz`
- SHA-256：`88cda8b980ee3b03fb2a19b6fdbddf35e4330e9e2adbc678c83cf20e3510f5b3`
- 诊断收据 SHA-256：`c71a3a7e952e693fb715d34dd82bc71c7a53ccb0285f2bfa06680d5dbbc09728`
- registry SHA-256：`766a4fa678a4cb9ae55fdb460ae94b5f1be93ce2040b64ed7e48c13260f9aebd`
- 双跑结果逐字节一致；4 个 checkpoint journals 的 task identity cardinality 均为 0。
- 裁决：整包结构性拒收；不得根据文件名补 task，不得接纳其中任何 seed。
- 安全边界：raw journal 先做凭据扫描；env/live-event journal 未读；输出不含 task identity 值、代码、stdout、grade、metric 或 outcome。

生产 intake 在 task identity 门 fail-closed，未提交该 transaction、未读 outcome。只有在 clean control commit
中绑定上述 registry 与全部既有 registry SHA 后，才允许恢复 0820 剩余归档的 CPU intake；恢复不会改变
scientific commit、activation、estimand 或任何已冻结 scorer。
