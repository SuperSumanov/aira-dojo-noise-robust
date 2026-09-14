ACCELERATE_LOG_LEVEL=info \
accelerate launch \
--config_file src/mle_critic/recipes/zero3.yaml \
--main_process_port 29501 \
--num_processes=2 \
../Hista/src/rl/grpo.py \
--config src/mle_critic/recipes/trl_cc/Qwen3-4B/GRPO_inst_csipo.yaml \
> ./outputs/Qwen3-4B/GRPO_mlejudger_easy_inst_csipo_sampling.log 2>&1

ACCELERATE_LOG_LEVEL=info \
accelerate launch \
--config_file src/mle_critic/recipes/zero3-offload.yaml \
--main_process_port 29501 \
--num_processes=2 \
../Hista/src/rl/grpo.py \
--config src/mle_critic/recipes/trl_cc/Qwen3-1.7B/GRPO_inst_csipo.yaml \
> ./outputs/Qwen3-1.7B/GRPO_mlejudger_easy_inst_csipo_sampling.log 2>&1