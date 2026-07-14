"""Decisive diagnosis of identical blind==grounded H2 result: does the 14B teacher actually produce a
DIFFERENT rationale when it sees the true grade (grounded) vs blind? Generates both for 3 cards."""
from phase1.cards import load_cards
from phase1.dataset import labeled
from phase1.critics.qwen_backend import load_model, _chat, build_value_prompt

TEACHER = "/research/d7/spc/yzyang4/models/Qwen2.5-Coder-14B-Instruct"


def main():
    import torch
    if not torch.cuda.is_available():
        raise SystemExit("CUDA not available")
    model, tok = load_model(TEACHER, "4bit")
    cards = labeled(load_cards("phase1/cards_real_mm.jsonl"))[:3]

    def gen(p):
        enc = tok(p, return_tensors="pt", truncation=True, max_length=768).to(model.device)
        with torch.no_grad():
            g = model.generate(**enc, max_new_tokens=200, do_sample=False, pad_token_id=tok.pad_token_id)
        return tok.decode(g[0][enc["input_ids"].shape[1]:], skip_special_tokens=True)

    for c in cards:
        blind_p = _chat(tok, build_value_prompt(c, for_reasoning=True, max_code=1200))
        base = build_value_prompt(c, for_reasoning=True, max_code=1200).rsplit("# Instructions", 1)[0]
        gp = (base + f"# Verified true score (for your reasoning ONLY)\ntrue_score = {c.y:.3f}\n\n"
              "# Instructions\nThe verified true score is given above. In 2-4 sentences, explain — from the "
              "code, cheap signals, and lineage ALONE — WHY this solution earns that score. Do NOT restate "
              "the score or any numeric metric value; a reader must not be able to recover the number from "
              f"your text. Then output the final line exactly as `predicted_final_score: {c.y:.3f}`.")
        rb = gen(blind_p)
        rg = gen(_chat(tok, gp))
        print(f"\n===== card {c.id[:22]} y={c.y:.3f} =====", flush=True)
        print(f"BLIND rationale:\n  {rb[:300]}", flush=True)
        print(f"GROUNDED rationale:\n  {rg[:300]}", flush=True)
        print(f"IDENTICAL={rb.strip() == rg.strip()}", flush=True)


if __name__ == "__main__":
    main()
