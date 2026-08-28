# Decision Corpus Evidence Index v8（complete-release temporal split）

固定 future snapshot：`887491a021d75d889c00a5af672a11b8b06e249d98e84fd91288534080f62697`

正式 source commit：`3d30826ed6aac9aa1c09e30b454a13b4e3b6dae3`

状态：`PROVISIONAL_TEMPORAL_SPLIT_CERTIFIED_EVIDENCE_STACK_AWAITING_FIRST960`

## 正式结果

v8 从 clean-provenance v7 的 14 个 entries 原样继承，再追加 physical-run split certificate 与
complete-release temporal-overlap certificate，共 16 entries、43 artifacts、3 bound files、499 条精确
JSON assertions。builder A/B 与不 import builder 的 verifier A/B 均逐字节一致。

完整、可逐字节重建的 v11 历史 release 含 16,012 endpoints、667 physical runs、25 tasks；固定 future
snapshot 含 11,906 endpoints、435 runs、34 tasks。在预注册的 identifier/literal-erased Python token 表示下，
primary Jaccard 17/20 精确检查 18,510,294 个 candidate pairs，得到 0 links；strict 19/20 sensitivity 同样为
0 links。全部六个完整性门通过，分类为 `ZERO_IDENTIFIER_ERASED_RELEASE_LINKS`。

正式 focused/full 为 `30/1288 passed`，full 有 47 warnings。formal manifest、complete-release package
manifest、builder/verifier 输出及安全回执全部由机器哈希绑定；GPU/API/model-fit/base-update=`0/0/0/0`。

## 边界

- 这是固定表示和阈值下的 syntactic temporal-split certificate，不证明 semantic clone 缺失。
- 不证明未知预训练语料没有污染，也不覆盖所有可能历史来源。
- future 中 12 个未成功 fingerprint 的 endpoints 不在零链接证书内。
- 当前仍为 435/960、closure=false；状态明确为 provisional。
- 未读取 prospective label/grade/outcome/prediction values，未计算 predictor accuracy、effect 或 search utility。
- 首轮只因 1,800 秒资源上限失败（formal rc=124、deployment rc=1）；r2 只把上限改为 5,400 秒，科学协议未变。

机器绑定见 `source_bindings.json`；完整正式收据及其原始 manifest 见 `formal/`。完整历史 release 的紧凑证书
另见相邻目录 `historical_release_future_identifier_erased_overlap_887_20260828_8bf9512_r2/`。
