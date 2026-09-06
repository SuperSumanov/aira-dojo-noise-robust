# Actual Socket trial: checkpoint-boundary failure, not accepted training

Job12573, sourceb84e8baea4de65a16038b4136cee094d29716964. FAILED133seconds/266GPU-seconds,
zero completed trajectories and checkpoint manifests. Socket initialization completed, no SIGSEGV.
The first checkpoint boundary rejected persistent CPU-offload master gradients with the old zero-value test.
Pinned Stage3 deliberately retains those already-consumed buffers; correction and separate follow-up are
documented in ZERO3_CONSUMED_GRADIENT_PREFLIGHT_20260906.md. Do not rerun this failed job or its final reader.

23 original safe files, including MANIFEST.json, imported byte-for-byte. Manifest contains22 members;
this README is an explanation, not an original artifact. No checkpoint deserialization or trace publication.

- Failure receipt: a79b966c57a5fbd115712fb821c472b533bb34daf04f268873daef353af1403d.
- Archive: 293cceb08ecf32ac70fbcf625506fe948bb9e1268d3b9830c0ec7f3ea28ebc59.
- Manifest: 7973ae491c3f3b63d8722cd267e7e11ba0f65eaa3ea34af1179074350d5c8ad3.
- Original trace108033194bytes: 7a2b1f7ecce4962776738bb38a3392261b970e90e827be9149c3b3febbf232cb.

Source and manifest hashes rechecked; full trace credential/protected-path scan zero hits.
Total completed optional-group GPU use including this failure419seconds. No model/scaling benefit measured.
