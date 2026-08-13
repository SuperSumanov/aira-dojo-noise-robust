# ParentPatchCritic sparse V3：长跑前预检记录

日期：2026-08-14。对象为最多 15 分钟、0 GPU/0 API 的 CPU discovery gate。以下检查发生在
真实 patch accuracy 产生之前；synthetic smoke 不使用 v11 outcome，不能当科学结果。

1. **旋钮从产物验证**：`summary.json` 固定写入 folds=5、hash dimensions=`2^18`、char 3--5、
   text limit=20,000、alpha=`1e-5`、parent equal weight、seed=887、软件版本和命令。synthetic
   smoke 已验证这些字段和条件式 frozen 路径均可落盘。
2. **新代码路径便宜验证**：本地 4/4 unit tests；远端 critic Python 4/4 pytest-free tests；
   synthetic 400 train + 200 frozen pairs 完整跑出 GREEN，独立 verifier 复算通过。首次 verifier
   发现 sparse margin 与 score difference 有约 `1.4e-6` 浮点次序差，只把代数一致性容差改为
   `1e-5`；所有 gate 指标仍从 CSV 严格重算。
3. **测试集/重复检查**：v11 b0 train/frozen 的 oriented duplicate=0、reverse conflict=0；主脚本
   再次 fail closed。`intask_split==test` 只在 discovery 全闸通过后读取，绝不进 fit。
4. **先看分布**：train 4,263 pairs / 333 runs / 23 tasks，dominant task 21.11%；frozen
   1,498 / 92 / 22，dominant 40.72%。parent-present coverage 分别 3,948/4,263 与
   1,424/1,498。parent top-1 仅在完整 pair graph 上报，不完整集合单列。
5. **评估配平**：两臂严格同 pair/common-parent support、同 run folds、同 classifier；训练按 parent
   等权；主推断同时报 pair、parent、run-macro、task-macro 与双聚类 CI，不以单任务汇总替代。
6. **保存可复算产物**：该 CPU gate 不需要保存大模型 checkpoint；逐 pair margin、两端 score、hit、
   完整 config/input SHA/source commit 全保存，独立 verifier 不 import 主实现。
7. **泄漏三查**：GroupKFold 按 physical run；IDF 只 fit train-fold endpoint；hashing 无 vocabulary；
   frozen 解锁后强制 train/frozen endpoint overlap=0、run overlap=0。代码不加载 card label、stdout、
   runtime、self-report。
8. **RNG**：Python/hash/model/bootstrap 全固定 seed 887；GroupKFold 不 shuffle；deterministic CRC32
   random baseline。
9. **密钥**：代码/文档不含凭据；push 前对 staged filename 运行用户指定的
   `git diff --cached --name-only | grep -icE 'env|key|token|secret'`，并做内容扫描；两者必须为 0。
10. **墙钟**：V2 重复 fit 超过 10 分钟；V3 一次 hash、每折仅 fit IDF/head，目标 4--8 分钟，
    内外双重 900 秒 cap，单进程且 BLAS threads=1。超时=`ENGINEERING_TIMEOUT`，不得解释科学结果。
11. **训练侧功效**：train parent coverage 92.61%、333 independent runs、23 tasks；unlock 还要求
    ≥10 个 n≥20 tasks 且 ≥60% 非负，防止只靠 pair 数或 spooky 单任务。
12. **真实 rc**：launcher 对 gate/verifier 都先保存 `$?` 到 `gate_rc`/`verify_rc` 再打印；任一非零
    立即停止，不允许坏产物进入下游。
13. **冻结/append-only**：输入远端 SHA 在 launcher 中固定核验；实验目录由 commit 前缀唯一命名，
    已存在即 ABORT；脚本不会修改 frozen 文件。任何 outcome 后参数变化必须新 amendment + 新 commit。

输入远端 SHA-256：

- cards v11: `6794acbf1dbc21ca75bed5899f4dd071b4b0d1a5b092c2e60bc634a8c5701b75`；
- run map: `3d774d8414e7b0553e4efdab9410b06aa67ed80cac48fff2d69cbe056baa0e30`；
- b0 train: `bd31b4679c7b4405703b976921df0bc63acba4fc0c4a002f4b8f36d171251fca`；
- b0 frozen: `2717e331c9e7156bdc47a31ea1fdd13c5eecb4465c33ad249c41bfac597a8da8`。

Windows checkout 因 CRLF 可能有不同工作树 byte SHA；科学运行以 launcher 核验的远端 LF 文件为准。
