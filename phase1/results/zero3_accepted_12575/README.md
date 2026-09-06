# Real tiny ZeRO-3 restart accepted; not a model-effect result

Job12575, source `1c211b87880a1110e3a67cc1dc7d277e5db18441`, completed in271seconds
on twoRTX3090s (542allocatedGPU-seconds). Five trajectories and nine real checkpoint bundles
were saved. Strict final state/consumption checks passed at both restart cuts on both ranks.

An independent CPU reader loaded the actual authenticated files:12 checkpoint-payload comparisons
passed, including model/master/Adam/RNG bytes. Three fresh final models reconstructed from
actual shards had bitwise-equal weights and synthetic forward outputs. This is4433parameters,
not1.7B/16K readiness, scientific data admission, critic quality or search improvement.

Terminal receipt SHA: `14dae4dbc7e1497695d1081517a1603833f4a6f97bd8ac3d534b5e0debdffaa2`.
Checker source: `c3eb1d546ac5314a8685bc692817b6cfde534c68`.
Terminal verifier source: `30a507d26478a7819ae8469d872a8a7651719d80`.

The original independent check failed on an unsupported native DeepSpeed enum. Its original
failure/log is retained in `post_original`; the corrected exact enum comparison is in the
independent R2 check. No field was omitted or tolerance relaxed; the GPU job was not repeated.
The earlier12574 real FP32-master mismatch remains a failed run in its separate evidence bundle.

This directory contains77 byte-preserved raw files, including a manifest authenticating76 members.
Full file-access traces and pickle/checkpoint payloads remain private on the research disk;
their hashes and independent verification receipts are included. The terminal verifier checked
the GPU and CPU traces, source hashes, nine bundles/81members, and129 read-only artifacts.

Archive SHA: `d6db115376ade88acbc4665f632a8ec682863a526c35fd8f6a5d43b23ff4f84b`.
Raw manifest SHA: `06aff13233793a4f7ae65e969a1614a90976a079ef56605df27288cf1baf275d`.

Original location: `/research/d7/spc/yzyang4/critic-zero3-engineering/job-12575`.
No protected corpus values or credentials are exported. No tiny retry remains necessary.
