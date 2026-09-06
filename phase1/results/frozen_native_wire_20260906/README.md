# 共同候选请求原生接口检查，不是critic/搜索收益

source `f5b3f6f4e262e19f0045d15957f93d8223d03af2`。
2026-09-06 UTC03:00:58完成：Linux34项通过，无失败/跳过；
210个源文件与Git blob逐字节相符，无网络尝试、无保护路径尝试、无真实API或MLE执行。
本地再次核验Git源码清单、两个日志哈希、pytest XML及子进程回执，均通过。

真正被验证的是：三个既有complexity分支使用真实Dojo算子、Node/Journal、OmegaConf、Jinja与
GenericLLM.__call__时，预冻结请求与参考调用的messages/解码参数一致；
活对象或客户对象变动不污染后续请求，批次并发不重复发起，失败不自动重试。

测试替换了provider factory/client、外部W&B遥测和dotenv加载，配置为合成任务/日志位置。
未验收provider SDK、网络协议、重试费用、完整agent rollout或真实资源与prompt的一致性。
未修改默认solver；不含任何模型准确率、regret、scaling或在线收益结果。

## 失败保留

- 8e91565检查缺litellm，30通过/3失败。
- 3f346a9检查首个W&B导入缺sentry_sdk，后续部分初始化错误；另记录一次socket.bind被拒绝。
- b8c9a57的208文件包缺aira_core，31通过/3失败。
- 同source补齐210文件后，合成fixture缺LOGGING_DIR，31通过/3失败。
- f5b3f6f设测试自有路径并禁止dotenv读取后，本页结果通过。未在失败目录原地重跑。

源包SHA256 `84504067830fa7413fb9165632f908f2bf4cdb75e2b8842b0fe619c503fbf2ba`。
MANIFEST绑定六份原始回执；SOURCE_MANIFEST绑定210源文件。
测试时日志中“sending query”来自真实GenericLLM日志，但接收方是无网络FakeClient，不是API调用。
