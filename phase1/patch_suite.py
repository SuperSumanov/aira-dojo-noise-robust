"""Scale features before the linear ranker (lbfgs hit its iteration cap on raw counts
spanning code_len ~1e4 down to binary flags), and widen the trained-critic slot so any
score dump can be plugged in as it lands."""
import io
P = "phase1/predictor_suite.py"
s = io.open(P, encoding="utf-8").read()
NL = chr(10)

s = s.replace("from sklearn.linear_model import LogisticRegression",
              "from sklearn.linear_model import LogisticRegression" + NL +
              "from sklearn.preprocessing import StandardScaler", 1)

old = ("Xtr, ytr = pair_matrix(train)" + NL +
       "lr = LogisticRegression(max_iter=2000, C=1.0).fit(Xtr, ytr)")
new = ("Xtr, ytr = pair_matrix(train)" + NL +
       "# differences of raw counts span 1e4 (code_len) to 1 (flags); unscaled lbfgs" + NL +
       "# never converges. Scale with mean 0 so the antisymmetry of the design survives." + NL +
       "sc = StandardScaler(with_mean=False).fit(Xtr)" + NL +
       "lr = LogisticRegression(max_iter=4000, C=1.0).fit(sc.transform(Xtr), ytr)")
assert s.count(old) == 1, "anchor lr"
s = s.replace(old, new, 1)
s = s.replace('evaluate("static_lr", lambda b, w: int(lr.decision_function(' + NL +
              '    (fvec(b) - fvec(w)).reshape(1, -1))[0] > 0), t_lr, None,',
              'evaluate("static_lr", lambda b, w: int(lr.decision_function(' + NL +
              '    sc.transform((fvec(b) - fvec(w)).reshape(1, -1)))[0] > 0), t_lr, None,', 1)

s = s.replace('for tag, path in (("rm_1.5b_2048", "phase1/rm_scores_sibling.json"),):',
              'for tag, path in (("rm_1.5b_2048_sib", "phase1/rm_scores_sibling.json"),' + NL +
              '                  ("rm_1.5b_2048", "phase1/rm_scores_testpairs.json"),' + NL +
              '                  ("rm_0.5b_8192", "phase1/rm_scores_05b8192.json"),' + NL +
              '                  ("llm_judge", "phase1/judge_scores.json")):', 1)
io.open(P, "w", encoding="utf-8", newline=NL).write(s)
print("predictor_suite.py: scaled linear ranker + open slots for more critics")
