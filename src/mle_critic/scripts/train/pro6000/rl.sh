export CC=/bin/g++
export CXX=/bin/g++
export VLLM_ATTENTION_BACKEND=FLASHINFER

ACCELERATE_LOG_LEVEL=info \
accelerate launch \
--config_file src/mle_critic/recipes/zero2.yaml \
--main_process_port 29501 \
--num_processes=2 \
../../hista_trl_os/intermediate/Hista/src/rl/grpo.py \
--config src/mle_critic/recipes/trl/pro6000/Qwen3-0.6B/GRPO_inst_csipo.yaml \
> ./outputs/Qwen3-0.6B/GRPO_mlejudger_easy_inst_csipo_sampling.log 2>&1

ACCELERATE_LOG_LEVEL=info \
accelerate launch \
--config_file src/mle_critic/recipes/zero3.yaml \
--main_process_port 29501 \
--num_processes=2 \
../../hista_trl_os/intermediate/Hista/src/rl/grpo.py \
--config src/mle_critic/recipes/trl/pro6000/Qwen3-4B/GRPO_inst_csipo.yaml \
> ./outputs/Qwen3-4B/GRPO_mlejudger_easy_inst_csipo_sampling.log 2>&1