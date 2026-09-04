# G-reuse 对 local decision context 的覆盖与连接：正式结果

总状态：`G_REUSE_DECISION_CONTEXT_REACH_NOT_SUPPORTED`。十项结果前 gate 中九项通过，一项失败；不得降门。

## 聚合结果

历史 L 的 4,689 个 local pairs 构成 1,473 个唯一 `(task,parent)` contexts；每个 endpoint 唯一映射到一个
context。三臂结果为：

| arm | G edges | G valid tokens | 跨 context 边占比 | context coverage | local-pair any / both coverage | parent-rank gain | 正 gain tasks |
|---|---:|---:|---:|---:|---:|---:|---:|
| basis | 790 | 5,773,896 | 1.0000000000000000 | 0.6293279022403259 | 0.4817658349328215 / 0.08999786734911495 | 787 | 28/28 |
| spectral50 | 1,811 | 12,610,283 | 0.9889563776918829 | 0.6300067888662594 | 0.6201748773725742 / 0.29174664107485604 | 787 | 28/28 |
| full | 2,745 | 19,601,875 | 0.9675774134790528 | 0.6300067888662594 | 0.6728513542333120 / 0.41245468116869266 | 787 | 28/28 |

full 触达 928/1,473 contexts，2,656/2,745 边跨 context，双端触达 1,934/4,689 local pairs；
最大单任务 parent-rank gain share 为 `0.09148665819567979`。这些 full gates 全过，说明其 endpoint-graph
结果确实广泛对应 local decision contexts，而不是只在少量 parent/task 内形成连接。

spectral50 相对 full 保留 `1.0` 的 parent-rank gain 和 `1.0` 的 context coverage，同时 G-token reduction 为
`0.3566797564008545`。但它的 both-endpoint local-pair coverage 为 1,368/4,689，只保留 full 的
`0.7073422957600828`，低于预注册 `0.75`；因此总状态必须失败。basis 虽已拥有相同 parent-rank，但只双端触达
422 个 local pairs，说明 parent-rank 本身不能代表对 local pair 的充分曝光。

## 复验与失败链

结果前科学 commit 为 `8da7fd6b9972e278f1ec2afc8aaefd82dbc70df9`。前三个根均在任何输入/metrics 前
失败并保留：r1/r2 因 source-root import 未绑定，stdout 0、stderr 各 271 字节；r3 已绑定 root 但精简 archive
漏两个间接依赖，stdout 0、stderr 909 字节。commit `39b8e4dc738e8fd601cad8f06f5c5af7a49a2d37`
只修 `PYTHONPATH`；`d379f0062d46def1df4f6b003f4ceb7820ed5cea` 只记录并补全 source archive，科学代码和门未变。

正式 source archive SHA-256 为 `188e56c06ccee016d252951ea5489174592288e08e5e803f9b5ecdd1ba4bcfda`；
结果 archive 远端/本地 SHA-256 均为 `8e370024ccc4200d63cb7ad0dbc35919e2dcf52ac1289586e53f4d9c1b0bce77`。
内部 manifest 全过；producer A/B 与 verifier A/B 分别逐字节一致，producer/verifier metrics 完全相同；
receipt SHA-256 为 `c9f17ba4e7354aea19288f3ef58f2a8f25f979f962e0872bbda5e01ce1312bfe`。
四次耗时 50.65097326040268、50.641775402240455、46.06466743629426、48.16948652733117 秒，均 rc0/stderr0；
credential/身份字段扫描通过。GPU/API/model fit=0，未输出 task/parent/run/card/edge 身份或训练池。

## 结论边界

可保留的正结论是：full G-reuse 广泛跨 parent context，并覆盖全部任务和多数 context；spectral50 以更低 token
完整保留 context-level rank/reach。不能声称 spectral50 已保留足够 local-pair exposure，更不能声称 critic accuracy、
训练收益、执行成本归零或新算法。0L23 的 conditional model challenger 可继续作为实证问题，但本结果提高了风险：
若 core 通过，spectral50 必须按原非劣门真实训练，不能只凭 rank/谱指标宣布 Pareto。
