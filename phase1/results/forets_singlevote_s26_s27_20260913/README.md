# Seed26/27 单票开发矩阵

全部8搜索闭合后统一读出；不是确认cohort，不是8B模型训练或scaling。
主结果为wallclock-summary.json及逐run CSV；readout-finished绑定主结果与计时归因hash。
singlevote-selection-verification证明真实选择的独立回放，不能推断未执行代码的效果。
singlevote-execution-metadata覆盖39个任务调用；exit0不代表有效submission。

错误分类是揭盲后描述：使用singlevote-journal-errors-v2.json。
原singlevote-journal-errors.json误把两个任务根占位分别计入每臂日志数，已被v2取代，不得引用其总数。
保留原件为更正证据；v2通过supersedes字段绑定其SHA。v2仅覆盖Space实际保存的27份执行日志，
其中critic14/random13；未保存的返回调用与Leaf日志缺失不补造。
数据不含原代码、日志全文、凭据或受保护cohort。

完整解释见 ../../FORETS_SINGLE_VOTE_RESULTS_20260913.md。
