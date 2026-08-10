"""Add a --provider switch so the judge can run on DashScope/Qwen.

Two reasons this matters beyond budget. First, the DeepSeek run showed only 38% of the
median program to the judge, which makes its at-chance result a lower bound; qwen3-coder-flash
answers directly (no reasoning tokens at all -- verified) so the whole budget can go to
INPUT and the full program fits. Second, the pairwise-judging literature warns against
using the same model family as generator and judge: our corpus is DeepSeek-written, so a
DeepSeek judge has a family match that a Qwen judge does not.
"""
import io
P = "phase1/llm_judge.py"
s = io.open(P, encoding="utf-8").read()
NL = chr(10)

s = s.replace('ap.add_argument("--model", default="deepseek-v4-flash")',
              'ap.add_argument("--model", default="deepseek-v4-flash")' + NL +
              'ap.add_argument("--provider", default="deepseek", choices=["deepseek", "qwen"])', 1)

old = ("KEY = None" + NL +
       'for line in open("/research/d7/spc/yzyang4/aira-dojo/.env"):' + NL +
       '    if line.strip().startswith("PRIMARY_KEY_DEEPSEEK_V4_FLASH="):' + NL +
       "        KEY = line.strip().split(\"=\", 1)[1].strip().strip('\"').strip(\"'\")" + NL +
       'assert KEY, "no deepseek key"')
new = ("_WANT = ('PRIMARY_KEY_DEEPSEEK_V4_FLASH=' if a.provider == 'deepseek'" + NL +
       "         else 'PRIMARY_KEY_QWEN3_CODER_FLASH=')" + NL +
       "_URL = ('https://api.deepseek.com/chat/completions' if a.provider == 'deepseek'" + NL +
       "        else 'https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions')" + NL +
       "KEY = None" + NL +
       'for line in open("/research/d7/spc/yzyang4/aira-dojo/.env"):' + NL +
       "    if line.strip().startswith(_WANT):" + NL +
       "        KEY = line.strip().split(\"=\", 1)[1].strip().strip('\"').strip(\"'\")" + NL +
       'assert KEY, "no key for provider " + a.provider')
assert s.count(old) == 1, "key anchor"
s = s.replace(old, new, 1)
s = s.replace('        "https://api.deepseek.com/chat/completions", data=body,', '        _URL, data=body,', 1)
io.open(P, "w", encoding="utf-8", newline=NL).write(s)
print("llm_judge.py: --provider {deepseek,qwen}")
