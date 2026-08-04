"""Refuse to start an API-burning batch when the account cannot finish it.

Both providers died mid-batch today: DeepSeek ran dry 70 minutes into deepB (total loss, no
checkpoint), DashScope went overdue halfway through gen2VAL (half loss). A batch that starts
with insufficient balance converts money into nothing, so every collection submission now
probes first and holds below a floor.

Exit 0 = enough balance, exit 1 = hold. Prints the balance either way (goes to the fill log).
Usage: balance_guard.py deepseek [min_cny]     (default floor 25)
"""
import json, os, sys, urllib.request

provider = sys.argv[1] if len(sys.argv) > 1 else "deepseek"
floor = float(sys.argv[2]) if len(sys.argv) > 2 else 25.0

key = None
want = "PRIMARY_KEY_DEEPSEEK_V4_FLASH=" if provider == "deepseek" else "PRIMARY_KEY_QWEN3_CODER_FLASH="
for line in open("/research/d7/spc/yzyang4/aira-dojo/.env"):
    if line.strip().startswith(want):
        key = line.strip().split("=", 1)[1].strip().strip('"').strip("'")
        break
if not key:
    print("balance_guard: key missing, holding")
    sys.exit(1)

proxy = urllib.request.ProxyHandler({"https": os.environ.get("https_proxy", "")})
opener = urllib.request.build_opener(proxy)

try:
    if provider == "deepseek":
        req = urllib.request.Request("https://api.deepseek.com/user/balance",
                                     headers={"Authorization": "Bearer " + key})
        r = json.load(opener.open(req, timeout=25))
        cny = next((float(b["total_balance"]) for b in r.get("balance_infos", [])
                    if b.get("currency") == "CNY"), 0.0)
        ok = r.get("is_available") and cny >= floor
        print(f"balance_guard: deepseek CNY {cny:.2f} (floor {floor}) -> {'GO' if ok else 'HOLD'}")
        sys.exit(0 if ok else 1)
    else:
        # DashScope exposes no balance endpoint on this API surface; a one-token call
        # distinguishes alive from overdue, which is the failure mode we actually hit.
        body = json.dumps({"model": "qwen3-coder-flash",
                           "messages": [{"role": "user", "content": "1"}],
                           "max_tokens": 1}).encode()
        req = urllib.request.Request(
            "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
            data=body, headers={"Authorization": "Bearer " + key,
                                "Content-Type": "application/json"})
        opener.open(req, timeout=30)
        print("balance_guard: dashscope probe OK -> GO")
        sys.exit(0)
except urllib.error.HTTPError as e:
    print(f"balance_guard: {provider} HTTP {e.code} -> HOLD")
    sys.exit(1)
except Exception as e:
    print(f"balance_guard: {provider} probe failed ({type(e).__name__}) -> HOLD (fail-closed)")
    sys.exit(1)
