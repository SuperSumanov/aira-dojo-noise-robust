# Historical UST predictor sensitivity v2：正式结果

## 裁决

历史 931-pair same-pool 支持上的 UST/effective-resistance 重加权已经通过 exact-commit formal。结论分成两层：

1. **结构层是非平凡正结果**：931 条 pair rows 的 endpoint-edge incidence rank 只有 `787`，cycle rows=`144`；
   UST 与 uniform edge distribution 的 total variation=`0.12106505144691318`，task-weight TV=
   `0.049068032215226765`。因此仅报告 pair-row 数确实会掩盖比较图依赖，rank/UST 审计不是空修饰。
2. **历史 predictor 结论没有被救活，也没有被推翻**：冻结的 nested `pair→parent→task` headline 下，12 个模型的
   raw/UST 排序 discordant pairs=`0`。冻结 champion `static_gbm_task` 从 raw=`0.54801174684043918` 变为
   UST=`0.5483277645334842`，变化仅 `+0.00031601769304501204`，task-clustered 95% CI=
   `[-0.00037747374181428185, 0.001145659286141352]`。这不是模型性能突破。

最诚实的论文表述是：我们得到一个可外推到 FOREAGENT 的 graph-aware benchmark audit 标准，并证明旧 predictor 排名对该
修正稳健；不能把它写成 critic 已获得显著提升。

## 冻结 headline

| 模型 | raw nested task-parent | UST nested task-parent | UST−raw |
|---|---:|---:|---:|
| `tfidf_lr` | `0.56652923211993333` | `0.56658677190961804` | `5.7539789684701859e-05` |
| `static_gbm_task` | `0.54801174684043918` | `0.5483277645334842` | `0.00031601769304501204` |
| `static_gbm_pooled` | `0.5354380880702363` | `0.53565860219453076` | `0.00022051412429446859` |
| `static_lr_task` | `0.5027714544544446` | `0.50225803762176646` | `-0.00051341683267813742` |
| `static_lr_pooled` | `0.4648194101630117` | `0.46516752612262768` | `0.00034811595961597996` |

冻结 champion 的 UST headline 95% CI=`[0.49819079664424992, 0.60078820168816471]`，下界没有超过
`0.5`。相对固定 `tfidf_lr` 的 paired UST delta=`-0.018259007376133896`，95% CI=
`[-0.10907272623875371, 0.086268880671008574]`；没有证据说明 champion 优于 TF-IDF。TF-IDF 在 raw 与
UST headline 中都保持第一；不能在 test 上重选 champion。

task-pair sensitivity 中全部 12 个模型只有 1 个顺序 discordance，primary 五模型仍为 0；global-parent 与 task-pair
敏感性也没有为 champion 提供可替代 headline 的显著优势。它们按 v2 预注册只能作 sensitivity，不能 rescue 主结论。

## 图结构

- pairs=`931`，endpoint memberships=`1346`；
- tasks=`28`，decision parents=`550`，connected components=`559`；
- complete/incomplete components=`445/114`；
- incidence rank=`787`，cycle rows=`144`；
- UST weight sum=`786.99999999999989`，Foster identity 通过；
- minimum/median/maximum edge weight=`0.23901264298615302/0.99999999999999978/1`；
- raw/rank maximum task share=`0.10741138560687433/0.10927573062261753`。

这里的 `787` 只表示 endpoint-edge incidence design rank，不是有效样本量、独立标签数、feature-matrix rank 或 Shannon
information。历史支持中 114 个 incomplete components 也说明不能把每个 parent 机械当作完整 clique；按实际 comparison
graph 计算 UST 是必要的。

## Formal 与独立复验

- exact source commit：`65b2e2a6669a1ddc41059746c843fab501895190`；
- scientific protocol SHA-256：`dc23bbac584600f11f7d6de62313c210377576aadc727fce79694de2b823771c`；
- formal root：`/research/d7/spc/yzyang4/historical-ust-predictor-sensitivity/formal-65b2e2a-v2`；
- focused/full：`13 passed in 6.92s` / `1760 passed, 48 warnings in 114.66s`；
- producer A/B 与 grounded-inverse verifier A/B 均逐字节相同；四份 stderr 都是 `0 bytes`；
- independent maximum absolute numeric difference=`1.1368683772161603e-13`；
- result/verification/manifest SHA-256：
  `9f0ba71b1be84a79b64edc27b0c625579bb1d2c0a781c3daf43fbbb339f41a7c` /
  `4b522f844c6f49429c836986fd5ccd15a9f662ad3660ce480fc2b277a7cbf188` /
  `12b18ae96e07a3e202671749527270de45caf67304b35eb9a7d820fce6b67e74`；
- 23-entry manifest 全通过，结果根/result/verification mode=`500/400/400`；
- producer/verifier forbidden path 与 network hits=`0/0/0/0`；credential filename/content=`0/0`；
- prospective values 未读；GPU/API/model fit/base update=`0/0/0/0`。

机器回执：`phase1/historical_ust_predictor_sensitivity_formal_receipt_20260830.json`。

## 论文边界与下一步

允许的主张：pair benchmark 应同时报告 rows、vertices、components/incidence rank、实际 comparison graph、UST/rank-aware
敏感性、真实 decision/run grouping 与 cluster assumptions；该标准在我方历史图和 FOREAGENT 公开图上都产生了非平凡结构读数。

禁止的主张：新 graph theorem、有效样本量、prospective confirmation、test-selected model improvement、task-unseen
generalization 或 search utility。下一步应把 graph-aware 字段固化进 Decision Corpus release/audit protocol，同时继续等待
first-960 closure 与 Target-300 closure；不得因本次历史结果追加模型或事后更换 headline。
