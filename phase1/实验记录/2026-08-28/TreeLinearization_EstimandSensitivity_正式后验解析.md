# Tree linearization estimand sensitivity：正式后验解析

## 正式裁决

固定 aggregate receipts 上的正式分类为
`VERIFIED_EXACT_EDGE_MEASURE_SENSITIVITY_COROLLARY`。后验声明 commit=
`d8214ce0a1aecdc184ef6909fc2542c3e1506719`，正式实现 commit=
`5a96d92e0d638af6dba6f65c5f4a96e1ab37e9b4`。

必须保留时间线：0HC/0HD 的 multiplicity aggregate 已公开后，先探索性看到了本轮数值，才冻结机器声明。因此本轮
是对已发布聚合量做精确有理数重算和独立实现核验，不是结果前发现、独立 replication 或新假设检验。

## 精确结果

- canonical unique edges=`10895`，path edge occurrences=`26107`，duplicate occurrences=`15212`；
- edge-measure TV=`109845598/284435765`=`0.38618771447395162`；
- sharp maximizing set 含 2,286 条 unique edges 和 15,560 个 path occurrences；
- 其 canonical mass=`2286/10895`=`0.20982101881597062`；
- 其 path mass=`15560/26107`=`0.59600873328992221`；
- canonical inverse-HHI descriptive diversity=`10895`；
- path inverse-HHI descriptive diversity=`681575449/296317`=`2300.1564169453659`；
- diversity retention=`681575449/3228373715`=`0.2111203686962245`；
- maximum single-edge mass inflation=`1568880/26107`=`60.094227601792625`；
- inverse-multiplicity correction 后对 canonical 的 exact TV=`0/1`。

TV 是两种固定经验 measure 的总变差距离，同时是所有 `[0,1]` edge-level bounded statistics 的 sharp worst-case
期望差。maximizing set 的质量差逐分数恰等于 TV，避免把浮点近似当证明。

## 对论文主线的增量

0HC 已证明 path linearization 会改变 task/run weights；0HD 已证明 canonical tree-native view 与 trajectory-only
consumer 可以用 `1/m_e` 双视图兼容。本轮补上最容易被审稿人追问的量级：即使暂不指定某个 predictor，未经修正的
path-frequency measure 与 canonical edge measure 已相距 38.62 个百分点的 sharp bounded-statistic envelope，且描述性
edge diversity 只保留约 21.11%。因此“发布 tree-native estimand + 明示 compatibility weights”不是格式偏好，而是
会实质决定 benchmark 经验分布的合同。

这仍不是新算法：`1/m_e` 是初等恒等式，TV/inverse-HHI 也是标准量。可守贡献是把它们绑定到真实 MLE-agent physical-run
provenance、固定 aggregate receipts、结果盲审计、双视图 schema 与独立 fail-closed verifier。

## 复验与安全

- formal focused=`27 passed`；full=`1330 passed, 47 warnings`；postflight focused=`16 passed`；
- producer A/B、verifier A/B 各自 byte-identical；第二 fresh worktree verifier 与 formal verifier byte-identical；
- final receipt SHA-256=`2587db7f1a77a5bcc13dd0bed2191616ccca6c5cbc57b73104ebb7b425c57cc4`；
- independent verification SHA-256=`4801ff22d308d45fa0302174547ff1a2c724a0731e27e41fdc13f7fd8c16a49d`；
- formal/postflight manifest SHA-256=
  `4b82d111df374cdfb742e68a612e07d4c9d8d6bb8f073c81c785f051eaf73d84` /
  `cb943d828d2fd4307d5f32b2de5c0e29c7c7a2ce3ae42618988023bf012c27ed`；
- forbidden-open、credential filename/content=`0/0/0`；
- prospective truth/prediction、raw archive/blind manifest、identity/code 未读写；GPU/API/model-fit/base-update=`0/0/0/0`。

传输后，本地 package-focused 回归为 `19 passed, 1 skipped`（Windows 无符号链接权限时按设计 skip）。另一次本地
`phase1/tests` 全量尝试在 test collection 阶段因该 Python 3.13 环境未安装 SciPy/scikit-learn 而停止，共报告 11 个
`ModuleNotFoundError`；没有进入测试断言。这是本地依赖环境失败，不是科学 gate 失败，也不由临时安装依赖掩盖。
正式全量证据仍是 fresh Linux 固定 venv 中记录并纳入 manifest 的 `1330 passed, 47 warnings`。

## 不得越界

- 不得把 38.62pp 写成观察到的 predictor accuracy change；它是任意 bounded edge statistic 的 sharp envelope。
- 不得把 inverse-HHI 写成统计 ESS。
- 不得把后验解析包装成预注册独立发现。
- 不得从 observed edges 外推 complete source tree/choice sets。
- 当前 435/960、closure=false；最终 closure 后仍需按固定合同重签，且不能用本结果 rescue predictor primary。

结果包：`phase1/results/tree_linearization_estimand_sensitivity_887_20260828_5a96d92/`。
