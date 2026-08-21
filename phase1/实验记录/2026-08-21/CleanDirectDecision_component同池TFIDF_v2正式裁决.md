# Component 同池 char-TFIDF v2：正式裁决

日期：2026-08-21。状态：`BASELINE_VALID_AND_INDEPENDENTLY_VERIFIED`。科学 source=
`a6075d15722a08c76d2d316a19aff19ac91d6dea`；senior data commit=
`baf6bddefe62b769b2fab699ff5805dd627dc69f`。证据等级固定为 retrospective same-pool baseline。

## 1. 正式结果

| split / subset | pairs | micro accuracy | task macro | task-clustered 95% CI | parent-clustered 95% CI |
|---|---:|---:|---:|---:|---:|
| dev merged | 551 | 0.604355716878403 | 0.5643959081886237 | [0.48453914211874166, 0.6400960498179192] | [0.5445134575569358, 0.6534954407294833] |
| test merged | 931 | **0.5714285714285714** | **0.5757982662586206** | **[0.5066135214563272, 0.6409030224715225]** | **[0.5322425162766734, 0.6111639404566828]** |
| test Draft | 314 | 0.5796178343949044 | 0.5782137604459034 | [0.46515226960539463, 0.6866530798070976] | [0.4950486826091247, 0.660001240694789] |
| test Improve | 617 | 0.5672609400324149 | 0.588373953515658 | [0.5365270978210426, 0.6441683589249306] | [0.5257899205791036, 0.6103059581320451] |

test merged 为 532/931 正确，0 ties；Draft 182/314，Improve 350/617。merged 的 task-clustered 与
parent-clustered 下界都严格高于 0.5，支持“廉价字符信号确实存在”；但点估计仅 57.14%，仍留下大模型超过它的
实际空间。Draft/Improve 相差 `0.012356894362489546`，没有一个子集随机、另一个子集独自撑起结果。

dev 比 test 高 `0.03292714544983155`。这不是可忽略的细节：component dev 有 25 tasks、Draft share=
`0.5335753176043557`，test 有 28 tasks、Draft share=`0.3372717508055854`。因此后续 Qwen 只能用 dev 选
checkpoint；模型主张必须以一次性 test、逐语义、task/parent clustered paired delta 和 drop-one-task 为准。

## 2. 与旧数字的正确关系

旧 exact-config pooled TF-IDF 用全部 5,240 outer-train pairs 拟合，test=`0.5832438238453276`。本次为了给 Qwen
留出 run/component-clean dev，只用 4,689 train pairs，test 低 `0.011815252416756183`。两者训练池不同，不能把
差值叫成 component split 导致的性能下降，更不能选较高旧数继续当同池门槛。未来 G1 的唯一 paired baseline 是
本次 931 行逐对 margin，对照 micro=`0.5714285714285714`。

## 3. 复核与失败链

固定 20k code prefix、char_wb 3--5 gram、30k features、min_df=3、C=0.5；vocabulary/IDF/model 只由 4,689
train pairs 的 4,095 endpoints 拟合。词表 size=30,000，LR 5 iterations 收敛，pair margin 完全有限且
anti-symmetry max abs=0.0。

producer×2 四个产物逐字节相同；不 import producer 的 verifier×2 各自重建词表并 full refit，margin、metric、
model receipt、per-task accuracy 最大绝对差全部 0.0。3/3 聚焦测试通过；四次正式 fit/refit wall 为
5:21.49 / 5:28.21 / 5:22.53 / 5:22.68，max RSS 约 3.03 GB；文件名/内容 credential scan 均为 0。

第一次 source `e5f97d2...` 在写 summary 前因 classifier intercept 破坏 pair antisymmetry 而失败。新 source 只把
pair margin 修正为 `coef·difference`，保留原阈值和其他全部设置；失败 bundle 也永久保留。正式 v2 bundle：

- `/research/d7/spc/yzyang4/critic-component-tfidf/a6075d1-baf6bdd-v2.tar.gz`；
- SHA-256=`b3db165f86b44ab2264bf0aa78424ac2d9e05d2222a48c5f9927196824d6514d`。

## 4. 下一步边界

本结果固定了 G1 的 baseline，不是模型方法正结论。G0 仍为 Qwen3-1.7B、seed 6、2×96GB Pro6000、10 optimizer
steps、完整 dev eval、hard cap 4 GPU·h，且绝不读 test；它需要用户对该精确矩阵/预算明确批准后才能提交。
