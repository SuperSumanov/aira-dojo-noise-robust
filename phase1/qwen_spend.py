"""Token accounting for the Qwen campaign (dashscope exposes no balance endpoint).

Spend control is batch count, but the cap was set on a guess. This reads the token usage
LiteLLM logs per call and prices it, so the cap can be adjusted on evidence. Prices are
declared here, not fetched -- a rate change silently makes this optimistic, so state the
assumption whenever the number is quoted.

Log shape (verified against gen2Q01, note completion first and a newline mid-dict):
    'usage': {'completion_tokens': 1503
    , 'prompt_tokens': 3902, 'total_tokens': 5405
'prompt_tokens_details' must not be mistaken for 'prompt_tokens'; the closing quote-colon
in the pattern is what separates them.

Usage: python phase1/qwen_spend.py [issue_glob]
"""
import glob, re, sys

IN_PER_M = 1.0    # CNY per 1M input tokens  (qwen3-coder-flash, assumed)
OUT_PER_M = 4.0   # CNY per 1M output tokens (qwen3-coder-flash, assumed)

pat = sys.argv[1] if len(sys.argv) > 1 else "gen2Q*"
root = "/research/d7/spc/yzyang4/aira-dojo-runs/aira-dojo"
logs = []
for d in glob.glob(root + "/*issue_mcts_data_" + pat):
    logs += glob.glob(d + "/srun_pool/**/logs/*.err", recursive=True)
    logs += glob.glob(d + "/srun_pool/**/logs/*.out", recursive=True)

rx = re.compile(r"'completion_tokens':\s*(\d+)[\s\S]{0,40}?'prompt_tokens':\s*(\d+)")
pin = pout = calls = 0
for f in logs:
    try:
        s = open(f, errors="ignore").read()
    except OSError:
        continue
    for m in rx.finditer(s):
        pout += int(m.group(1))
        pin += int(m.group(2))
        calls += 1

cost = pin / 1e6 * IN_PER_M + pout / 1e6 * OUT_PER_M
print("logs scanned: " + str(len(logs)) + "   usage records: " + str(calls))
print("input tokens : {:,}".format(pin))
print("output tokens: {:,}".format(pout))
print("estimated spend: CNY {:.2f}  (assumed {}/{} per 1M in/out)".format(
    cost, IN_PER_M, OUT_PER_M))
if calls:
    print("per-call mean: {:.0f} in / {:.0f} out".format(pin / calls, pout / calls))
