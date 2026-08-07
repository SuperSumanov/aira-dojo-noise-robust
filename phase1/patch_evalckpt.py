"""Add --eval-ckpt (load saved RM, evaluate only) + RM_DUMP_HITS per-pair dump to rm_train_hf.py.

Why: the L2 2x2 off-diagonal cells and the "0.83 lookahead model scored on decision pairs"
cell need to EVALUATE saved checkpoints on a different pairs file without retraining. The
eval functions already take a bare model; this adds the loading branch so 100% of the eval
code path (test acc, len-ctrl, flip evals, CSV row) is reused instead of duplicated.
"""
import io

P = "phase1/rm_train_hf.py"
s = io.open(P, encoding="utf-8").read()
NL = chr(10)

# --- A: argparse flag ---
oldA = 'ap.add_argument("--save-adapter", default="")'
newA = (oldA + NL +
        'ap.add_argument("--eval-ckpt", default="",' + NL +
        '                help="saved RM dir (backbone + head.pt): load and evaluate only, no training")')
assert s.count(oldA) == 1, "anchor A"
s = s.replace(oldA, newA, 1)

# --- B: eval-only branch around model build + train ---
oldB = ('    sub = train_pool[:N]' + NL +
        '    model = RM(a.model)' + NL +
        '    targs = TrainingArguments(' + NL +
        '        output_dir="/tmp/rmhf_" + str(os.getpid()) + "_" + str(N),' + NL +
        '        per_device_train_batch_size=a.bs,' + NL +
        '        gradient_accumulation_steps=a.accum, num_train_epochs=a.epochs, learning_rate=a.lr,' + NL +
        '        lr_scheduler_type="cosine", warmup_ratio=0.03, max_grad_norm=1.0, bf16=True,' + NL +
        '        logging_steps=50, save_strategy="no", report_to=[], seed=a.seed,' + NL +
        '        deepspeed=a.deepspeed, remove_unused_columns=False, dataloader_num_workers=2)' + NL +
        '    tr = BTTrainer(model=model, args=targs, train_dataset=PairDS(sub), data_collator=collate)' + NL +
        '    t0 = time.time()' + NL +
        '    tr.train()')
newB = ('    sub = train_pool[:N]' + NL +
        '    if a.eval_ckpt:' + NL +
        '        model = RM(a.eval_ckpt)' + NL +
        '        model.head.load_state_dict(' + NL +
        '            torch.load(os.path.join(a.eval_ckpt, "head.pt"), map_location="cpu"))' + NL +
        '        if torch.cuda.is_available():' + NL +
        '            model = model.cuda()' + NL +
        '        from types import SimpleNamespace' + NL +
        '        tr = SimpleNamespace(model=model, is_world_process_zero=lambda: True)' + NL +
        '        t0 = time.time()' + NL +
        '    else:' + NL +
        '        model = RM(a.model)' + NL +
        '        targs = TrainingArguments(' + NL +
        '            output_dir="/tmp/rmhf_" + str(os.getpid()) + "_" + str(N),' + NL +
        '            per_device_train_batch_size=a.bs,' + NL +
        '            gradient_accumulation_steps=a.accum, num_train_epochs=a.epochs, learning_rate=a.lr,' + NL +
        '            lr_scheduler_type="cosine", warmup_ratio=0.03, max_grad_norm=1.0, bf16=True,' + NL +
        '            logging_steps=50, save_strategy="no", report_to=[], seed=a.seed,' + NL +
        '            deepspeed=a.deepspeed, remove_unused_columns=False, dataloader_num_workers=2)' + NL +
        '        tr = BTTrainer(model=model, args=targs, train_dataset=PairDS(sub), data_collator=collate)' + NL +
        '        t0 = time.time()' + NL +
        '        tr.train()')
assert s.count(oldB) == 1, "anchor B"
s = s.replace(oldB, newB, 1)

# --- C: CSV model column names the checkpoint, not the tokenizer base ---
oldC = '"model": os.path.basename(a.model), "seed": a.seed, "wall_s": wall,'
newC = ('"model": ("ckpt:" + "/".join(a.eval_ckpt.rstrip("/").split("/")[-2:]))' + NL +
        '                              if a.eval_ckpt else os.path.basename(a.model),' + NL +
        '                     "seed": a.seed, "wall_s": wall,')
assert s.count(oldC) == 1, "anchor C"
s = s.replace(oldC, newC, 1)

# --- D: trainer tag ---
oldD = '"trainer": "hf+ds" if a.deepspeed else "hf"}'
newD = '"trainer": "eval-only" if a.eval_ckpt else ("hf+ds" if a.deepspeed else "hf")}'
assert s.count(oldD) == 1, "anchor D"
s = s.replace(oldD, newD, 1)

# --- E: never re-save in eval-only mode ---
oldE = '        if a.save_adapter:'
newE = '        if a.save_adapter and not a.eval_ckpt:'
assert s.count(oldE) == 1, "anchor E"
s = s.replace(oldE, newE, 1)

# --- F: per-pair hit dump (RM_DUMP_HITS env), main eval only (breakdown=True) ---
oldF = ('    if breakdown:' + NL +
        '        import collections as _c')
newF = ('    if breakdown:' + NL +
        '        _dump = os.environ.get("RM_DUMP_HITS")' + NL +
        '        if _dump:' + NL +
        '            with open(_dump, "a") as _f:' + NL +
        '                for h, p_ in zip(hits, ps):' + NL +
        '                    _f.write(json.dumps({"better": p_["better"], "worse": p_["worse"],' + NL +
        '                                         "budget": p_.get("budget"), "task": p_["task"],' + NL +
        '                                         "gap_raw": p_.get("gap_raw"),' + NL +
        '                                         "hit": int(h)}) + chr(10))' + NL +
        '        import collections as _c')
assert s.count(oldF) == 1, "anchor F"
s = s.replace(oldF, newF, 1)

io.open(P, "w", encoding="utf-8", newline=NL).write(s)
print("patched: --eval-ckpt branch, ckpt-named CSV, eval-only trainer tag, save guard, RM_DUMP_HITS")
