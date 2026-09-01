# Kaggle rules triage for Decision Corpus v11

> Status: `PARTIAL_RULES_TRIAGE_NOT_LEGAL_CLEARANCE`
> Read time: 2026-09-01T20:31:47Z
> Scope: the exact 25 task slugs present in `cards_current_v11.jsonl`.

## What this closes

The old release checklist used a stale 22-competition denominator. The v11 card
release contains 25 distinct task slugs, and all 25 canonical Kaggle rules URLs
were directly opened and rendered. This closes URL discovery and first-pass
clause-shape triage. It does **not** close institutional/legal review, provider
terms, final dataset licensing, or permission to publish generated competition
code outside Kaggle.

Rendered-rule observations:

- rules page visible: 25/25;
- detailed pages containing both Competition Data and Submission Code sections:
  16/25;
- compact legacy pages without those detailed sections: 7/25;
- detailed legacy pages with nonstandard section numbering: 2/25;
- an explicit private-sharing prohibition: 25/25;
- a statement allowing public forum sharing: 25/25;
- an explicit OSI license clause that does not limit commercial use: 18/25;
- the exact standard Competition Data non-redistribution sentence: 13/25.

Absence of a matched sentence is recorded as **not observed**, never as
permission. In particular, the seven compact legacy pages require manual legal
review; the two text-normalization pages and three detailed pages with modified
data language also require clause-level review.

## Per-task triage

Legend: `full` = detailed Data + Code sections; `legacy` = compact rules page;
`custom` = detailed older template with different numbering. `data-NR` and
`OSI-commercial` mean the exact clauses were observed, not inferred.

| Task | Template | data-NR | OSI-commercial | Winner-license label | Rules |
|---|---:|---:|---:|---|---|
| aerial-cactus-identification | full | yes | yes | none; solution-license waiver observed | [rules](https://www.kaggle.com/competitions/aerial-cactus-identification/rules) |
| aptos2019-blindness-detection | full | yes | yes | OPEN SOURCE | [rules](https://www.kaggle.com/competitions/aptos2019-blindness-detection/rules) |
| chaii-hindi-and-tamil-question-answering | full | yes | yes | Open Source | [rules](https://www.kaggle.com/competitions/chaii-hindi-and-tamil-question-answering/rules) |
| denoising-dirty-documents | legacy | not observed | not observed | not observed | [rules](https://www.kaggle.com/competitions/denoising-dirty-documents/rules) |
| dog-breed-identification | legacy | not observed | not observed | not observed; acceptance not required | [rules](https://www.kaggle.com/competitions/dog-breed-identification/rules) |
| dogs-vs-cats-redux-kernels-edition | legacy | not observed | not observed | not observed | [rules](https://www.kaggle.com/competitions/dogs-vs-cats-redux-kernels-edition/rules) |
| google-quest-challenge | full | yes | yes | Open-Source | [rules](https://www.kaggle.com/competitions/google-quest-challenge/rules) |
| histopathologic-cancer-detection | full | not observed | yes | not observed; solution-license waiver observed | [rules](https://www.kaggle.com/competitions/histopathologic-cancer-detection/rules) |
| kuzushiji-recognition | full | yes | yes | Open Source under MIT License | [rules](https://www.kaggle.com/competitions/kuzushiji-recognition/rules) |
| leaf-classification | legacy | not observed | not observed | not observed | [rules](https://www.kaggle.com/competitions/leaf-classification/rules) |
| learning-agency-lab-automated-essay-scoring-2 | full | yes | yes | OPEN SOURCE - MIT | [rules](https://www.kaggle.com/competitions/learning-agency-lab-automated-essay-scoring-2/rules) |
| mlsp-2013-birds | legacy | not observed | not observed | not observed | [rules](https://www.kaggle.com/competitions/mlsp-2013-birds/rules) |
| nomad2018-predict-transparent-conductors | full | not observed | yes | not observed | [rules](https://www.kaggle.com/competitions/nomad2018-predict-transparent-conductors/rules) |
| petfinder-pawpularity-score | full | yes | yes | Open-Source | [rules](https://www.kaggle.com/competitions/petfinder-pawpularity-score/rules) |
| random-acts-of-pizza | legacy | not observed | not observed | not observed | [rules](https://www.kaggle.com/competitions/random-acts-of-pizza/rules) |
| ranzcr-clip-catheter-line-classification | full | yes | yes | not observed | [rules](https://www.kaggle.com/competitions/ranzcr-clip-catheter-line-classification/rules) |
| spaceship-titanic | full | yes | yes | not observed | [rules](https://www.kaggle.com/competitions/spaceship-titanic/rules) |
| spooky-author-identification | full | not observed | yes | not observed | [rules](https://www.kaggle.com/competitions/spooky-author-identification/rules) |
| tabular-playground-series-dec-2021 | full | yes | yes | None | [rules](https://www.kaggle.com/competitions/tabular-playground-series-dec-2021/rules) |
| tabular-playground-series-may-2022 | full | yes | yes | None | [rules](https://www.kaggle.com/competitions/tabular-playground-series-may-2022/rules) |
| text-normalization-challenge-english-language | custom | not observed | yes | not observed | [rules](https://www.kaggle.com/competitions/text-normalization-challenge-english-language/rules) |
| text-normalization-challenge-russian-language | custom | not observed | yes | not observed | [rules](https://www.kaggle.com/competitions/text-normalization-challenge-russian-language/rules) |
| tweet-sentiment-extraction | full | yes | yes | Open Source | [rules](https://www.kaggle.com/competitions/tweet-sentiment-extraction/rules) |
| us-patent-phrase-to-phrase-matching | full | yes | yes | OPEN SOURCE | [rules](https://www.kaggle.com/competitions/us-patent-phrase-to-phrase-matching/rules) |
| whale-categorization-playground | legacy | not observed | not observed | not observed | [rules](https://www.kaggle.com/competitions/whale-categorization-playground/rules) |

## Release interpretation

1. Competition Data remains zero-byte redistribution. Users must acquire it
   from Kaggle and accept the applicable rules themselves.
2. A winner-license label is not treated as a blanket license for every
   participant's generated code or for a tree dataset assembled from it.
3. Public-forum-sharing language is not treated as automatic authorization for
   GitHub/Hugging Face publication. Forum/kernel posting and an institutionally
   reviewed release notice remain open actions.
4. `licenses_v11_draft.json` is a machine-readable triage record, not a final
   `licenses.json` or legal opinion.
5. Final clearance still requires provider-output terms, the v11 content scan,
   a final LICENSE/NOTICE, and institutional/legal review.
