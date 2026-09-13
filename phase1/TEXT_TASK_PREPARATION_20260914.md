# 第三个任务：只准备，不宣称泛化或追加效果实验

2026-09-14 HK。远端公开CSV表头已核实：spooky-author-identification训练为id,text,author，待预测表为id,text。没有读取私有标签、外部分数或新搜索结果。

预设共享起点为词1–2gram TF-IDF（min_df2，max_features50000，sublinear_tf）与C1 LogisticRegression。全部拟合仅在训练内80/20 split的训练侧开始，分数打印后再全公开训练集拟合、按输入id原序写概率列。参数不是从该任务外部分数挑出的。

采用单列原始文本DataFrame，后续如需要模块接口，可允许build_model中的文本处理/pipeline变动，同时固定读取、split、label列顺序和提交。这只是接口准备；当前EScope仍只有Leaf/Space，源码/配置未改，不自动启动第三任务，也不绕过其失败的扩大门。

CPU合成测试覆盖原程序及AST拼接版本、缺文本、输入id乱序、概率列/有限性/行和、实际fit样本数先48后60。合成分类数据不是效果证据。不把这里的简单起点冒充强AutoML基线；以后若用本任务，还需字符特征/线性SVM等实际强参照和新的完整协议。
