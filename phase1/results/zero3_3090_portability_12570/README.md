# RTX3090 portability attempt — stopped before model work

2026-09-06 HK05:25, job12570, source97306120a1c203bb6e72a2b7468a21acbf44371a.
Public gpu28, twoRTX3090,20min,no-requeue. Separate disclosed cap3120GPU-seconds;
existing12535 unchanged. This attempt is NOT production qualification or a method result.

Remote124CPU tests passed in9.63s;33source files pinned and unchanged. Slurm held
fields independently inspected before release. Local35passed/8skipped was only a
preliminary check, not substituted for remote tests. Actual64MiB storage check
allocated67108864bytes and removed only its own test file; no guarantee for future checkpoints.

Terminal sacct: FAILED,1allocated second,2GPU-seconds,exit1:0.
Required `/usr/local/cuda-12.8/bin/nvcc` is absent on gpu28. The compiler check raised
before driver/model initialization; no trajectory, checkpoint, resume comparison
or real-GPU final-readout result was produced. The failure does not establish that
RTX3090 cannot run this workload; it establishes this node lacks the pinned toolchain.
No environment repair or automatic retry under this frozen attempt.

Failure receiptSHA9e30ef8381ac026c530924e1bb5f58f26a0104e43371662b6b1856e7dce7dca5.
ExportSHA1e58aad704b992ae849a5e177e4ecb3ab9b8ec0330ed6b8ea02987132fcda4ba.
17raw evidence files hash-verified inmanifest.json; controller, command, held
resource record, runtime, tests, actual worker failure and terminal accounting included.
No raw corpus, checkpoint or credential exported.
