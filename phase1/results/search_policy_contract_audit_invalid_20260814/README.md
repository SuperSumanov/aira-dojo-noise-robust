# Historical search-policy contract audit: invalid

Protocol: `search_policy_contract_audit_v1`

Frozen implementation commit: `d6b1e388e79ada7f5045a56235844902d2431357`

Formal start: `2026-08-14T01:47:16Z`

Final status: **`HISTORICAL_POLICY_AUDIT_INVALID_NO_CAUSAL_CLAIM`**

The formal remote run passed all 13 preflight items and 28 tests, then failed closed before
producing any scientific summary:

```text
AuditError: non-root parent contract violated
PRODUCER_RC=1
```

The first safely isolated anomaly was in the 0802 MCTS arm: task
`denoising-dirty-documents`, seed 4, checkpoint-journal SHA-256
`70a6b991754274f477aa52fb27659a3197696c8642beffd30ec6e899084d9266`.
Step 21 had an empty parent list despite being non-root. It was the only malformed non-root
node among 180 non-root nodes in that archive's six complete runs. A later archive also
exceeded the preregistered 64 MiB allowlisted-member cap. Neither condition was waived after
inspection.

The historical arms also fail the fairness contract independently of the malformed journal.
A pre-result nomad sample differed in base model (`deepseek-v4-flash` versus
`qwen3.5-397b-a17b`), execution/interpreter timeout (14,400 versus 4,800 seconds), children
per expansion (5 versus 2), total time limit (86,400 versus 82,800 seconds), and source
commit. No committed MCTS/config diff was found that proves the claimed 0805
“sequential/no-selection” intervention; the available solver still performs UCT selection.

Consequences:

- No formal structure estimate, confidence interval, outcome, grade, or critic metric was
  produced.
- The exploratory fragment-level `0.73` versus `0.56` variance-share comparison is retracted
  as a causal result and must not appear in an abstract, main table, or claim list.
- The only valid next test is a newly collected, explicitly implemented matched intervention:
  fixed siblings and equal continuation budget under an otherwise identical contract.

`diagnostic_summary.json` is the machine-readable decision record. `formal_failure.log`
contains only the concise preflight/failure receipt; it contains no card code, grade, prompt,
environment value, or credential.
