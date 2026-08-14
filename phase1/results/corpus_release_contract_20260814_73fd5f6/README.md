# Byte-exact corpus release verification

Status: `VERIFIED_BYTE_EXACT_CORPUS_RELEASES_V6_THROUGH_V11`.

At the final implementation commit `73fd5f6a927e8deeb07d84372e1ba87fb7d2b3c5`, the
release system pins an append-only batch registry prefix, every batch's SHA-256/byte/row
triple, a release-specific serialization protocol, and the output SHA-256/byte/row triple.
The cluster materialized batches from the fork's Git LFS endpoint and compared each rebuilt
release with the retained original using `cmp`.

| release | batches | rows | bytes | runs | protocol | result |
|---|---:|---:|---:|---:|---|---|
| v6 | 23 | 9,433 | 160,043,881 | 457 | basic | byte exact |
| v7 | 25 | 10,755 | 184,329,618 | 515 | basic | byte exact |
| v8 | 26 | 12,383 | 214,866,914 | 553 | basic | byte exact |
| v9 | 27 | 14,323 | 271,496,136 | 586 | basic | byte exact |
| v10 | 28 | 15,158 | 287,373,736 | 624 | sanitized-v10 | byte exact |
| v11 | 29 | 16,012 | 305,750,663 | 667 | sanitized-v11 | byte exact |

The failed attempts are retained, not hidden:

- a first LFS pull queried Facebook upstream instead of the fork and received a 404;
- replaying v9 with the *current* mutable transformer preserved 14,323 rows but changed
  744,500 bytes, proving that immutable batches alone do not freeze serialization;
- one verification helper used a nonexistent temporary-directory parent and stopped before
  rebuilding;
- the first frozen sanitized protocol omitted the v11-only dogs-vs-cats task and stopped at
  v11; the final protocol splits the v10/v11 taxonomies and adds a regression test;
- the first v10-only helper omitted `cd` and exited 127 before running the builder.

v4/v5 remain explicitly unrecoverable from published batches: their recorded row counts
(8,607/9,323) differ from the surviving batch prefixes (8,579/9,433), and no original merged
artifact was found. No replacement release was fabricated.

The merged verification outputs were generated in validated temporary directories and
removed after exact comparison. Only receipts, summaries, and honest logs are archived here;
no card content, API credential, environment file, or new outcome analysis is included.
