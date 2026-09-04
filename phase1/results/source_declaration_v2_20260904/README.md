# 来源日期契约：真实历史诊断与新声明v2验收

问题：旧来源声明的“启动日期等于归档目录日期”是否与已确认的历史header映射相容？
结论：不完全相容。固定676行中636已有唯一来源，99两日期不同，537相同；32歧义/8缺失状态不改。
目录日减启动日为-1的73条、+1的26条。日期差原因未核实，不能推断时区或恢复更多physical runs。

这是诊断/验收修复，不是效果实验；不生成训练池，不解除旧S0，真实新producer声明尚未交付。
不存在新accuracy、跨seed收益或scaling结果。G0 job12377排队配置不动，五臂15 fits仍未获预算。

## 实际执行与绑定

- exact code commit：`7083668352f924860da4613c4dd2724cd3570c37`。
- Git archive SHA：`380462cdb10d309bb876be09aa2ca9589ba9413b46d238fd9ef961df3917b809`；旧依赖的导出换行差异见下文。
- 远端根：`/tmp/source-declaration-v2-20260904-CYEGWQ`；命令见`run_validation.sh`。
- Python：`/research/d7/spc/yzyang4/venvs/exp/bin/python`，3.11.15；pytest 7.4.3；数学线程1、CUDA隐藏、PYTHONHASHSEED=0。
- 执行脚本SHA：`aab00fb5ff9660c60daaba6907a8921518c1a0bb8800d0bc92707696ef66bca3`；此处脚本与远端as-run字节绑定。
- Linux旧/新验收器合计36 passed/0 skipped，见原始`linux_tests.txt`，包括Windows不能创建的symlink检查。
- Windows推送前组合回归55 passed/1 skipped；这不是55次效果实验，跳过原因是symlink创建权限。确切命令为
  `python -B -m pytest -p no:cacheprovider -q phase1/tests/test_senior_source_provenance_v2.py
  phase1/tests/test_senior_source_provenance_manifest.py phase1/tests/test_historical_global_local_source_gate.py
  phase1/tests/test_global_local_historical_development_protocol.py phase1/tests/test_global_local_calibration_candidate_protocol.py`。
- 实际历史输入为旧header-only映射`senior-true-batch-identity-support/a466888-v3/producer_1/run_batch_manifest.jsonl`，
  SHA `60846a3a68f4cc9644ad676aa89e0d250b5fb8c0a3b8f6c1a708f2b5d0fb3e4d`。
- 真实日期生产A/B逐字节相同，SHA `6c7ce58883fb451e1be9d7f6646ff4129d0fa387f52b7894da85e5df3e956b07`。
  `independent.json`来自不导入producer的独立set/list实现，结果相同，独立回执SHA为
  `0d4a5a2e76e2b51b0907813e9f15eaa2913cc7ae0b89981b1452dfbd9979f463`。末尾`exit_status.txt`为0。
- 真实归档扫描/真实payload解析/Cards/pairs/前瞻值/模型fit/新增GPU均0；验收器单测仅打开自产合成tar fixtures。
  数据集本身不复制或上传；这里仅发布聚合结构回执和代码。

`source.sha256`是远端as-run文件哈希。Windows Git archive把未指定eol的旧验收器导出为CRLF（17891字节、439个CRLF），SHA
`f48f0464f70511558ed70d71f0ae0f22d9e28d37278317cd2aeaa9f9c73d5cd7`；Git blob和当前Windows工作区实际均LF（17452字节），SHA
`13d164f6b82098751b97dec6e4a6f5e2a34fc308e958ef951e0078dc392c987a`。发布核验最初据原始blob哈希拒绝，没有隐去；
随后逐字验证exact archive member等于该blob的LF→CRLF展开，新代码三个文件与blob完全相同。旧Git对象未修改，
也没有修改其属性或重写as-run产物。不能把两份旧文件原始字节说成相同，或把首次拒绝说成正式诊断失败。
旧测试Windows SHA仍`8ee2befba435e6880575343ddb172dbcc8579790a463c07521010f0870b262da`。
冻结v2 SHA仍`3e0785a13f9d9fc3638a222e78fd74010757b1201249ebd0ad7a5597c224a2e9`；历史开发v1仍
`1964e8e48e998660584c045a7e8fe2a03d61a946ba266d29d74555f934482902`。

## v2边界

完整说明见`../../SOURCE_DECLARATION_V2_20260904.md`。新入口显式分开两种日期，要求唯一实例声明和完整journal路径。
返回`HEADER_BACKED_DECLARATION_ONLY_NOT_EFFECT_ELIGIBLE`，绝不把路径/哈希存在当成实际执行commit、配置、实例或
experiment-closed划分已证明。不能自动解开旧32/8/2错误，更不能解开当前G/L候选的19/6或过滤415配置不一致对。
收到同版本、维护者确认的历史开发包后仍要走来源/配置/划分门；first960/Target300/Target522保持原盲态。

## 诚实保留

本轮初次找错一个pointer receipt文件名、Windows glob写法错误、一次远端find的换行转义丢失；均仅用于定位，
未作为正式计数证据。纠正后使用上述固定路径/SHA并独立复算。v2在看过日期结构后制定，不能包装为未知结构下的
新S0预注册。所有旧失败裁决保留。本轮没有启动新的训练或新贵实验。
