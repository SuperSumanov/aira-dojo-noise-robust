# Exact protocol-byte binding for the anonymous truth join

Classification: `HASH_BINDING_REPAIRED_SOFTWARE_ONLY_NOT_MODEL_EFFECT`.

Adversarial review found that commit `7c0786a` validated join-protocol semantics but accepted
any caller-supplied 64-hex value as the protocol SHA written to the result. No real prediction,
truth or effect result had been processed, so the defect affected receipt authenticity rather
than scientific values. The earlier hash-bound wording is withdrawn.

Result-before commit `80ed7044f2b09b0ae9d70413ad43a4ebece7f36d` changes both the producer and its
independently implemented verifier to accept raw join/readout protocol bytes, require the exact
frozen SHA-256 before parsing, reject duplicate JSON keys, and write only the authenticated fixed
hash. The caller no longer supplies a claimed hash.

Formal Linux evidence:

- root: `/research/d7/spc/yzyang4/g-reuse-anonymous-join/formal-80ed704-v1`;
- exact overlay archive SHA-256: `6e8cd9655b12de5098d2229c953f39660f203fb368a8cca312274cb2ff8a33f0`;
- deterministic 74-file source archive SHA-256:
  `eccdab6db627e49722d60572f09bc07c427784db76bacc052b8a758f9082a39a`;
- source manifest SHA-256: `accbd8461482e30f46bb64bad69ded87ea9ce0003e7e2b570131513a37e248c6`;
- join/readout protocol SHA-256:
  `d6a0540b3a78cae15827d88dddb2419bef599be2fdf936e51abb74201212d7f9` /
  `3e82858a9b66e5deb9f96efb27968259823470106d86dc0b439b11c666bfb2d5`;
- focused A/B: `11 passed in 7.38s` / `11 passed in 7.16s`;
- full 18-module A/B: `136 passed in 21.60s` / `136 passed in 20.97s`;
- all four stderr files are zero bytes.

New negative controls mutate the join semantics and add whitespace only to each of the join and
readout protocols. Producer and verifier independently reject each at its SHA gate. Existing
support, cluster, duplicate, truth-schema, NaN, hierarchy and aggregate-tampering attacks remain.

Boundary: this authenticates protocol bytes supplied to an in-memory synthetic kernel. It still
does not authenticate checkpoints, define a pristine truth package, authorize vault access or
establish critic effect. GPU jobs, paid API calls, model fits and protected reads are zero.
