# Light pairwise predictors

This package ports the student branch's three sklearn baselines:

- `tfidf_lr`: train-only character 3–5 gram TF-IDF followed by logistic regression;
- `static_lr`: 34 handcrafted decision-time features followed by scaled logistic regression;
- `static_gbm`: the same 34 features with histogram gradient boosting.

All models learn from `feature(better) - feature(worse)` and an order-reversed copy of every
training pair. Run the complete in-task split from the repository root with:

```bash
source /research/d2/gds/zzchen2/anaconda/bin/activate aira-dojo
PYTHONPATH=. python -m src.mle_critic.src.train.light_predictor.train \
  --pairs data/mle_critic/value_pairs_runsplit.jsonl \
  --cards data/mle_critic/cards_current.jsonl \
  --output /tmp/light_predictor_results.json
```

Use `--models`, `--train-cap`, and `--test-cap` for individual models or smoke tests.
