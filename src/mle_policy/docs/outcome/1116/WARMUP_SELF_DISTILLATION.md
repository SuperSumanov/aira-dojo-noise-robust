# 1116

一波实验结果和对应的调整。

## 1. Warmup Testset效果显著

运行逻辑：根据任务，数据，和指标设计，从trainset中切出大约5%test set大小的数据作为warmup test set。为了最小化policy的理解成本，warmup和原testset直接拼接在一起给policy，policy产出solution之后再由后台逻辑切分和分别评分。analysis的时候会根据cv和warmup分的大小判断solution是否buggy

测了4个任务，2个指标和数据较复杂的任务提升非常大，2个指标和数据较简单的任务有少量提升

| large scale compare | machine 1 | machine 2 | machine 3 | machine 4 | machine 5 | avg |
| --- | --- | --- | --- | --- | --- | --- |
| tgs-baseline | 0.4314 | 0.3383 | 0.3514 | 0.0221 | 0.3165 | 0.29194 |
| with warmup | 0.6698 | 0.5722 | 0.6685 | 0.5216 | 0.7687 | 0.64016 |

| large scale compare | machine 1 | machine 2 | machine 3 | machine 4 | machine 5 | avg |
| --- | --- | --- | --- | --- | --- | --- |
| chaii-baseline | 0.4948 | 0.5489 | 0.4941 | 0.3959 | 0.0488 | 0.3965 |
| with warmup | 0.5296 | 0.5569 | 0.53 | 0.4361 | 0.0757 | 0.42566 |

| large scale compare | machine 1 | machine 2 | machine 3 | machine 4 | machine 5 | avg |
| --- | --- | --- | --- | --- | --- | --- |
| dog-mistake | -0.3801 | -0.5144 | -0.5966 | -0.4421 | -0.4214 | -0.47092 |
| with warmup | -0.4058 | -0.4399 | -0.6605 | -0.3835 | -0.3946 | -0.45686 |

| tensorflow2 qa | max score | avg max score | max metric | avg max metric | max selected score | avg selected score |
| --- | --- | --- | --- | --- | --- | --- |
| baseline | 0.5754 | 0.547 | 0.796 | 0.3592 | 0.5754 | 0.2549 |
| with warmup | 0.5989 | 0.5192 | 0.629 | 0.1933 | 0.58 | 0.3963 |

从tensorflow2 qa这个任务来看，metric和score也是处在差不多的水平，没有出现过高的metric和过低的score。说明我们之前的猜想是对的，模型并不是一开始就有hack cv的恶意，只是test评估流程完全不透明而已。

## 2. Context Distillation 仍有问题

虽然上一个报告说第三层想要和harness结合起来改，但最近为了快速探索，还是直接用hindsight实现了第二层和第三层。跑了一轮chaii任务，收益不显著

| large scale compare | machine 1 | machine 2 | machine 3 | machine 4 | machine 5 | avg |
| --- | --- | --- | --- | --- | --- | --- |
| chaii-baseline | 0.5296 | 0.5569 | 0.53 | 0.4361 | 0.0757 | 0.42566 |
| chaii-day1 | 0.403 | 0.4138 | 0.5343 | 0.526 | 0.161 | 0.40762 |

这里的avg变化应该还是噪音范围内，之前也会出现类似现象。但更重要的是fast tokenizer改了没有。我做了一个脚本，取draft operation的输入，让baseline和day1各输出100条，看看fast tokenizer的比例：

```markdown
| 组别 | 条数 | 思考：明确标识符 | 思考：含文字描述 | 最终代码：明确标识符 |
| --- | ---: | ---: | ---: | ---: |
| comparison100 的 base | 100 | 1 | 2 | 0 |
| comparison100 的 context-distillation day1 | 100 | 0 | 0 | 0 |
```

| 组别 | 条数 | 思考：明确标识符 | 思考：含文字描述 | 最终代码：明确标识符 |
| --- | --- | --- | --- | --- |
| chaii-baseline | 100  | 1 | 2 | 0 |
| chaii-day1 | 100 | 0 | 0 | 0 |

原本思考中还是有可能出现的，训过之后甚至还训没了。个人感觉的原因是

> hindsight context导致模型思维中出现了一个重大分支“However, the hindsight notes suggest...”，而hindsight context带来的改进都是基于进入这个分支的，但训练的时候ppo clip起效，这个分支本来概率就低，在一轮训练之后进入的概率也没有提高多少。
> 

尝试改了下prompt，但也阻止不了思维链进入这个分支

## 3. OPSD

昨晚给codex一个goal让它把这玩意实现出来（原生verl里面竟然没有），做几次测试，然后到chaii tokenizer这个case上测测效果 （实现还有点问题，比如说codex直接用正在更新的模型当teacher模型了，还把bsz设为4）

| 组别 | 条数 | 思考：明确标识符 | 思考：含文字描述 | 最终代码：明确标识符 | 最终有效代码 | 平均token |
| --- | --- | --- | --- | --- | --- | --- |
| 本轮保守 OPSD，10 步 | 32 | 2 | 2 | 1 | 29/32 | 14.8 K |
| 本轮较大更新 OPSD，5 步 | 8 | 3 | 4 | 0 | 1/8 | 52.4 K |
1. 本轮保守 OPSD：lr 3e-6，kl loss coef = 1
2. 本轮较大更新 OPSD：lr 1e-5，kl loss coef = 0

虽然不是很完美，但有积极信号，我打算试一下。