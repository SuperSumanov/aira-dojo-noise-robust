# G-reuse anonymous join hash-binding repair preflight

Status: written before the formal Linux rerun and before any real prediction or truth input.

1. **Question**: can the join result name a protocol SHA that was never authenticated against
   the protocol bytes supplied to the kernel?
2. **Observed defect**: yes. Commit `7c0786a295dd9b56e85a4f81c505770d8ab3c417` validated
   protocol semantics but accepted any syntactically valid 64-hex `join_protocol_sha256`.
3. **Scope**: change only the anonymous join producer, its independently implemented verifier
   and focused synthetic tests. Do not change effect gates, estimands, arms, seeds or data.
4. **Binding rule**: both implementations receive raw join/readout protocol bytes, require their
   exact frozen SHA-256 values, reject duplicate JSON keys, parse only after the hash gate, and
   record only the authenticated fixed hash.
5. **Frozen identities**: join protocol SHA-256
   `d6a0540b3a78cae15827d88dddb2419bef599be2fdf936e51abb74201212d7f9`; readout protocol
   SHA-256 `3e82858a9b66e5deb9f96efb27968259823470106d86dc0b439b11c666bfb2d5`.
6. **Positive control**: unchanged frozen bytes and the existing positive/blocked synthetic
   fixtures must still be recomputed identically by producer and verifier.
7. **Negative controls**: semantic mutation and whitespace-only mutation of each protocol must
   fail at the relevant SHA gate; aggregate tampering and all prior row/schema attacks remain.
8. **Success rule**: focused tests pass twice on Linux with zero stderr, followed by the complete
   G-reuse suite twice from a hash-recorded source bundle.
9. **Failure rule**: any import, hash, assertion or independent-verifier failure blocks promotion;
   do not weaken the exact-byte gate or silently canonicalize the protocol.
10. **Resources**: CPU only; no GPU, paid API, model fit, checkpoint, label/outcome vault or
    protected cohort access.
11. **Interpretation**: success repairs receipt authenticity only. It cannot authorize production
    unseal or upgrade synthetic/software readiness to critic effect evidence.
