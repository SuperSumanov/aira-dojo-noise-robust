"""Explicit offline Qwen3-1.7B critic setup; never called by a default fallback.

Requires separately admitted data, resource budget and production GPU readiness.
No agent generator is changed. Construction uses the hash-bound senior forward,
but deliberately refuses an attention-backend fallback across experimental arms.
"""
from pathlib import Path
import random

from phase1.global_local_execution_plan import PlanError


def create_zero3_setup(*, source_root, model_snapshot, pad_id):
    """Return the actual model/optimizer/session factory; no import-time CUDA."""
    def setup(plan, pools, encoding_provider, true_sign, *, training_contract_sha256):
        import os
        from datetime import timedelta
        import numpy as np
        import torch
        from torch import nn
        from accelerate import Accelerator, DeepSpeedPlugin
        from accelerate.utils import InitProcessGroupKwargs
        from transformers import AutoModel
        from phase1.global_local_critic_consumer import PlannedCriticConsumer
        from phase1.global_local_zero3_session import DeepSpeedCriticSession
        from phase1.global_local_zero3_padding import initialized_partition_padding
        from phase1.scripts.validate_g_reuse_endpoint_inference_cpu_20260905 import source_definitions

        if (os.environ.get('HF_HUB_OFFLINE') != '1' or os.environ.get('TRANSFORMERS_OFFLINE') != '1'
                or plan.shape.world_size != 2 or plan.encoder.max_len != 16384):
            raise PlanError('offline_pivot_setup_contract')
        rank = int(os.environ['LOCAL_RANK'])
        torch.cuda.set_device(rank)
        if torch.cuda.device_count() != 2 or 'PRO 6000' not in torch.cuda.get_device_name(rank).upper():
            raise PlanError('production_hardware_mismatch')
        random.seed(plan.seed); np.random.seed(plan.seed); torch.manual_seed(plan.seed)
        torch.backends.cuda.matmul.allow_tf32 = False
        torch.backends.cudnn.allow_tf32 = False
        reference = source_definitions(source_root)
        cls = reference['BradleyTerryRewardModel']
        model = cls.__new__(cls)
        nn.Module.__init__(model)
        # The caller has already hashed the complete fixed safetensors snapshot.
        model.backbone = AutoModel.from_pretrained(str(Path(model_snapshot)), local_files_only=True,
            trust_remote_code=False, torch_dtype=torch.bfloat16, attn_implementation='flash_attention_2')
        model.backbone.config.use_cache = False
        model.backbone.config.pad_token_id = pad_id
        model.backbone.gradient_checkpointing_enable(gradient_checkpointing_kwargs={'use_reentrant': False})
        model.head = nn.Linear(model.backbone.config.hidden_size, 1, dtype=torch.bfloat16)
        model.train()
        if (sum(p.numel() for p in model.parameters()) != 1720577025
                or model.backbone.config._attn_implementation != 'flash_attention_2'):
            raise PlanError('production_pivot_or_attention_mismatch')
        shape = plan.shape
        config = {
            'train_micro_batch_size_per_gpu': shape.pairs_per_rank,
            'gradient_accumulation_steps': shape.accumulation,
            'train_batch_size': shape.world_size*shape.pairs_per_rank*shape.accumulation,
            'gradient_clipping': 1.0, 'bf16': {'enabled': True}, 'fp16': {'enabled': False},
            'zero_force_ds_cpu_optimizer': True,
            'zero_optimization': {'stage': 3, 'offload_optimizer': {'device': 'cpu', 'pin_memory': True},
                'overlap_comm': False, 'contiguous_gradients': True, 'reduce_bucket_size': 1000000,
                'stage3_param_persistence_threshold': 0, 'stage3_gather_16bit_weights_on_model_save': False},
        }
        accelerator = Accelerator(mixed_precision='bf16', gradient_accumulation_steps=shape.accumulation,
            deepspeed_plugin=DeepSpeedPlugin(hf_ds_config=config),
            kwargs_handlers=[InitProcessGroupKwargs(timeout=timedelta(seconds=300))])
        optimizer = torch.optim.AdamW(model.parameters(), lr=1e-5, weight_decay=0.0)
        with initialized_partition_padding():
            model, optimizer = accelerator.prepare(model, optimizer)
        consumer = PlannedCriticConsumer(plan=plan, pools=pools, accelerator=accelerator,
            model=model, optimizer=optimizer, encoding_provider=encoding_provider,
            true_sign=true_sign, pad_id=pad_id)
        session = DeepSpeedCriticSession(consumer, training_contract_sha256=training_contract_sha256)
        # Same per-rank stream for paired arms of a seed. Fresh-process restore
        # subsequently restores the saved streams, never this initial seed.
        rng_seed = plan.seed*1000003 + rank
        random.seed(rng_seed); np.random.seed(rng_seed); torch.manual_seed(rng_seed)
        torch.cuda.manual_seed_all(rng_seed)
        return session
    return setup
