# Partial-update DDP CPU validation (2026-09-04)

Status: **synthetic engineering validation passed; real Trainer/effect work remains blocked.**

The fixture uses one complete 128-pair update plus the real historical terminal
remainder for each phase: G=`128+48`, L=`128+81`.  It uses a two-parameter CPU
model and integer token fixtures only.

- 16 fresh Gloo trajectories over world sizes 2 and 4
- 48 global optimizer updates and 612 all-rank forward calls
- 4 deterministic distributed trajectories matched independent full-update
  references at `rtol=atol=1e-12`
- 4 stochastic prefix→fresh-process resume cases preserved model, optimizer,
  Python/NumPy/PyTorch RNG and consumption events bit-for-bit across 12 rank states
- G→L and Ghash→L input traces were identical after excluding only the arm-bound
  plan hash
- missing rank, corrupt rank bytes and missing manifest-rank cases were all rejected

The tested partial-update rule scales each rank-local mean loss by
`world_size * local_real_pairs / global_update_real_pairs` before DDP averaging.
No repeated real pair, synthetic placeholder, empty rank, source-mixed update,
real data, GPU context, API call or research model fit was used.

This does not establish compatibility with the real Hugging Face Trainer,
DeepSpeed/ZeRO3, bf16, or arbitrary power failures.  Those remain explicit gates.

