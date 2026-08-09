"""deepseek-v4-flash is a reasoning model: the answer lands in content only AFTER
reasoning_content finishes, so a tight max_tokens returns an empty string with
finish_reason=length. Give the judge room to think -- crippling it would make a null
unconvincing ("you never let it reason") -- and parse content first, falling back to the
tail of the reasoning trace only when the answer was cut off."""
import io
P = "phase1/llm_judge.py"
s = io.open(P, encoding="utf-8").read()
NL = chr(10)

s = s.replace('ap.add_argument("--max-chars", type=int, default=5000)',
              'ap.add_argument("--max-chars", type=int, default=5000)' + NL +
              'ap.add_argument("--max-tokens", type=int, default=1500)', 1)
s = s.replace('"max_tokens": 4, "temperature": 0.0}).encode()',
              '"max_tokens": a.max_tokens, "temperature": 0.0}).encode()', 1)

old = ('            txt = r["choices"][0]["message"]["content"].strip().upper()' + NL +
       '            m = re.search(r"[AB]", txt)')
new = ('            msg = r["choices"][0]["message"]' + NL +
       '            txt = (msg.get("content") or "").strip().upper()' + NL +
       '            m = re.search(r"\b([AB])\b", txt) or re.search(r"[AB]", txt)' + NL +
       '            if not m:' + NL +
       '                # answer never emitted (reasoning hit the cap): take the last A/B' + NL +
       '                # the trace committed to, and mark it so it can be excluded later' + NL +
       '                tr = (msg.get("reasoning_content") or "").upper()' + NL +
       '                cands = re.findall(r"SOLUTION ([AB])|ANSWER[: ]+([AB])", tr)' + NL +
       '                flat = [x or y for x, y in cands]' + NL +
       '                if flat:' + NL +
       '                    return ("~" + flat[-1], r.get("usage", {}).get("prompt_tokens", 0),' + NL +
       '                            r.get("usage", {}).get("completion_tokens", 0))')
assert s.count(old) == 1, "parse anchor"
s = s.replace(old, new, 1)

s = s.replace('        if pick in ("A", "B"):' + NL +
              '            chose_first = (pick == "A")',
              '        if pick and pick.lstrip("~") in ("A", "B"):' + NL +
              '            chose_first = (pick.lstrip("~") == "A")', 1)
s = s.replace('"order": order, "pick": pick, "correct": correct,',
              '"order": order, "pick": pick, "correct": correct,' + NL +
              '                "truncated": bool(pick and pick.startswith("~")),', 1)
io.open(P, "w", encoding="utf-8", newline=NL).write(s)
print("llm_judge.py: reasoning-aware parsing + max-tokens flag")
