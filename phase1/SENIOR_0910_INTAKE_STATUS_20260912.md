# 学长0910上传：已隔离，尚未作为新增有效run或训练数据

观察时间：2026-09-11 23:20–23:26 UTC（香港2026-09-12）。

发现0910目录，六个压缩包已下载到远端独立隔离区，共115079888 bytes；没有落到本地/Git。
目录在下载前后清单一致，六份压缩载荷哈希互异。最初根列表恰好50项，不能凭旧接口宣称完整。
00:19:25 UTC参考gdown v6.0.0官方新目录接口作独立交叉检查：两次embedded列表均50项，与即时旧接口及此前50项逐身份/名称一致，新增0项。
本次可见九月目录仍为0901–0907、0909、0910，未发现额外0911/0912；这不是Google完成全部上传索引的证明。
未升级实验环境、未访问归档正文。公开root_crosscheck.json SHA256为
`c43e73a9127a3fad471bbeb15b4b5add727305f2806ccddb613e3fc9c22c3c62`。
来源：[gdown v6.0.0实现](https://github.com/wkentaro/gdown/blob/v6.0.0/gdown/download_folder.py)。

只读取经过凭据形状扫描的dojo_config.json：24份配置、24个不同配置父路径，凭据拒读0份。
其中16份记录commit `065b0fbaa89e0eb663f2834ec768081f5d56394d`，8份记录
`61459c0a1248900079dafed7c505afa87e476b40`；20份num_children=2、4份num_children=3。
这些是配置计数，不是完成数、独立physical-run数或合格新训练样本数。两个版本/宽度不能无说明地混为同一生产条件。
其中61459c0a的本地Git对象可读，提交时间为2026-08-26 23:21:46+08:00；上传目录日期不能替代代码版本或实际运行日期。

未打开journal、env dump、候选代码、评分或保护集值；未解压归档，未改生产摄取入口或训练准入。
归档头可见24份journal和24份env文件，不等于这些文件的内容已安全或run已完成。
不因此推进first-960/Target-300/Target-522，不沿用24作为新增run计数。

远端：`/research/d7/spc/yzyang4/senior-quarantine-0910-20260912`。
私有manifest SHA256：`536251cce2d7aa0324f2e5b5ad638cbeced5e33b76166f2dc02f2e491b802c2c`。
公开结构回执在 `results/senior_0910_metadata_20260912/`：

- quarantine-summary.json：`6ff289af7ae1f7c9ef8d20da82c7a06c7c033c5a0147037fb368634597adc8af`
- config-metadata-summary.json：`d8e6ab87c935e39421cfc77325858472467bd7d22537494011db955293cf41a8`

下载、配置检查均已消费其只写一次输出，禁止重跑覆盖。后续若需摄取，应复用隔离副本完成原有去重/来源门；
当前优先级仍是13118的同预算端到端复验，不为累计语料数字而读取盲态结果。
