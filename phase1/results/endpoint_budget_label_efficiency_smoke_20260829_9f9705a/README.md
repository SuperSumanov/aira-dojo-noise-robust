# Endpoint-budget label-efficiency single-fold smoke

固定分类：`HISTORICAL_SINGLE_FOLD_ENDPOINT_LABEL_EFFICIENCY_SMOKE_DOES_NOT_ADVANCE`。

本目录只发布 aggregate/public 产物，不含 task/run/pair identity、per-pair prediction、train-only labels、topology witness、private
selection witness 或 model checkpoint。完整私有产物只保存在 mode-0600 remote formal root：
`/research/d7/spc/yzyang4/endpoint-label-efficiency-smoke/formal-9f9705a-r1`。

## 绑定

- source commit：`9f9705a14eac5bf73a070ac7c37091a815c4e31b`
- protocol SHA-256：`e0dd7414ce0885257234d87112507a3b89393260111398349dd22b05abb29761`
- formal manifest SHA-256：`4995bdf6e936b2e7f62fb9f44174e69cc3752b203a950816b17d2dd01f4c6e38`
- public selection SHA-256：`d1e4274b1046c4e4fea294818beb5522fcdd352a9379a2d72e8bc3255b59bd15`
- summary SHA-256：`b8068e691c84c1413d1e21091bde4ef89914dc3a0777ff44ba92bfe57f1ed6ec`
- runs CSV SHA-256：`5037e206092cd594b84e6ef895d226386a338b3d22cefea6f36a19e494747a12`

## 解释边界

两个预算点的 accuracy、log-loss 与 Brier 都描述性同向，而且两臂诱导 pair 数几乎相同；但 clustered CI 均跨 0，terminal
drop-dominant-task accuracy delta 为负，触发结果前冻结的否决门。不得把本目录写成确认性正结论，不得删掉主导任务或事后重加权，
也不得把 fold0 当作 future confirmation。

`verifier.json` 记录 0-refit 独立聚合重算；`firewall_receipt.json` 证明模型链只收到 train-only orientation 且 senior test 导出为 0。
formal postflight 另核验了整棵 SHA256SUMS、双跑逐字节一致、4 个 mode-0600 checkpoint 与 7 个空的边界/网络/凭据扫描器。
