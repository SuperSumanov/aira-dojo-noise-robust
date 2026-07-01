#!/usr/bin/env bash
# Recon for DetectReplan: which DeepSeek models the API serves (need a reasoning model) + venv pkgs.
source ~/env_setup.sh 2>/dev/null
echo "=== relevant env (values masked) ==="
env | grep -iE "PRIMARY_KEY|DEEPSEEK|http_proxy|https_proxy" | sed 's/=.*/=<set>/'
KEY="${PRIMARY_KEY:-${PRIMARY_KEY_DEEPSEEK_V4_PRO:-}}"
[ -z "$KEY" ] && echo "WARNING: no PRIMARY_KEY in env after sourcing env_setup.sh"
echo "=== GET /v1/models ==="
curl -sS https://api.deepseek.com/v1/models -H "Authorization: Bearer $KEY" --max-time 25
echo
echo "=== venv pkgs (numpy/litellm/openai) ==="
/research/d7/spc/yzyang4/venvs/aira/bin/python - <<'PY'
for m in ["numpy", "litellm", "openai"]:
    try:
        mod = __import__(m); print(m, getattr(mod, "__version__", "?"))
    except Exception as e:
        print(m, "MISSING", e)
PY
echo MODELS_DONE
