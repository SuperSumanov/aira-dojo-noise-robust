# Frozen 0.5B @ 8192 run-OOF discovery result

Verdict: **`VERIFIED_DISCOVERY_NO_UNLOCK`**. The fixed global linear head over frozen
Qwen2.5-0.5B endpoint embeddings did not pass the outcome-pre-registered training-only gate. No frozen/test
pair file was opened by the discovery chain.

## Exact headline

- training support: 4,263 b0 sibling pairs / 333 physical runs / 23 tasks / 5,499 endpoints;
- OOF pair accuracy: `0.5038705137227305`;
- run macro: `0.533114303371386`, bootstrap 95% CI
  `[0.4979728629806076, 0.5669365473627407]`;
- task macro: `0.5228910940725503`, bootstrap 95% CI
  `[0.48356131499662064, 0.5711860235770172]`;
- complete-parent top-1: `0.44710048694112436` on 2,259 complete parents;
- parent-equal gap utility: `0.5105066477670084`;
- supported-task nonchance share: `10/20 = 0.5`;
- deterministic random control: `0.5036359371334741`;
- train/held run, node, and raw-code-hash overlaps: all zero;
- frozen read: `false` in producer and independent verifier.

The result rejects only the pre-registered representation/head combination:
`task-name + whole code -> frozen last-layer masked mean + last token -> one global linear rank head`.
It does not establish that long context, frozen representations, task-conditioned heads, listwise losses, or heterogeneous
predictor ensembles cannot work.

## Provenance and accessibility

- git commit: `f339eb971c6d04fd149c608cc570b4bcdcdd1aac`;
- model weight SHA-256: `fdf756fa7fcbe7404d5c60e26bff1a0c8b8aa1f72ced49e7dd0210fe288fb7fe`;
- endpoint manifest SHA-256: `8c9621dd9d863d5640c54d1eefee42f5c170bbaf5d7bceceda7aa372ac1afc19`;
- prediction CSV SHA-256: `083f4daa23ab3f8b1d9e412184fbe9ee06d891385e8f66e0bbbb29b3e3055a96`;
- producer summary SHA-256: `465fa89bc78bbc8754907cef16301a8ddc16d14317f27b6ff0d4091a536d1215`;
- deterministic complete archive SHA-256:
  `096a3581bfce48c83019f3440e88089d4b8a4dd0a768224493f892941a3d64f7`.

`full_artifacts.tar.gz` is Git LFS-tracked and contains all four embedding shards (174 checkpoint chunks), their
metadata and hashes, manifest/rebuild, smoke, OOF predictions, producer/verifier outputs, source snapshots, and logs.
It was scanned before packaging: 217 files, zero API-key patterns, and zero non-ASCII archive paths. The two Chinese
pre-registration Markdown files are already normal Git files and are intentionally not duplicated inside the archive.
The archive was extracted on Windows and the independent verifier rerun successfully from the transported chunks. This
makes the result usable without access to the author's cluster storage.

The two `prior_preflight_*.log` files preserve failed pre-outcome attempts: first the inference venv lacked pytest;
second a multi-file `grep -c` guard returned `filename:0` strings. Neither attempt submitted a GPU job or produced model
outcomes. They are retained rather than overwritten.

## Next gate

The descriptive per-task OOF range is large (for example, supported-task accuracies span about 0.37--0.67), while one
global linear head cannot express task-by-code interactions. This observation only motivates, but does not validate, a
new protocol: a task-conditioned, parent-level top-centered/listwise lightweight head, followed by a strictly nested
heterogeneous ensemble if base errors are complementary. It must receive a new pre-registration and run-grouped OOF
gate; this archive cannot be used to lower the finished gate or unlock frozen evaluation.
