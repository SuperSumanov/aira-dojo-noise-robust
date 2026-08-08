"""Guard recon2 against non-finite grades/self-reports (some graded values are NaN)."""
import io
P = "phase1/recon2.py"
s = io.open(P, encoding="utf-8").read()
NL = chr(10)

old = ("def sr_of(d):" + NL +
       "    try:" + NL +
       '        return float(d["obs"].get("val_at_low"))' + NL +
       "    except (TypeError, ValueError):" + NL +
       "        return None")
new = ("def _fin(x):" + NL +
       "    \"\"\"NaN grades exist in the corpus; they poison every downstream statistic.\"\"\"" + NL +
       "    try:" + NL +
       "        v = float(x)" + NL +
       "    except (TypeError, ValueError):" + NL +
       "        return None" + NL +
       "    return v if math.isfinite(v) else None" + NL + NL + NL +
       "def sr_of(d):" + NL +
       '    return _fin(d["obs"].get("val_at_low"))')
assert s.count(old) == 1, "anchor sr_of"
s = s.replace(old, new, 1)

s = s.replace('    s, g = sr_of(d), d["label"].get("graded")',
              '    s, g = sr_of(d), _fin(d["label"].get("graded"))', 1)
s = s.replace('    g = d["label"].get("graded")' + NL + '    runs[d["run_id"]]',
              '    g = _fin(d["label"].get("graded"))' + NL + '    runs[d["run_id"]]', 1)
s = s.replace('    graded = [c for c in par_broken if cards[c]["label"].get("graded") is not None]',
              '    graded = [c for c in par_broken if _fin(cards[c]["label"].get("graded")) is not None]', 1)
io.open(P, "w", encoding="utf-8", newline=NL).write(s)
print("recon2.py: non-finite guard added")
