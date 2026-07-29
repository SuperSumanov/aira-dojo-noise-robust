#!/usr/bin/env bash
# Smoke-test a second generator BEFORE spending a collection batch on it.
# Usage: gen2_smoke.sh <model_id> <base_url> <api_key>
set -u
M="$1"; B="$2"; K="$3"
export https_proxy="http://137.189.90.241:8000/" http_proxy="http://137.189.90.241:8000/"
curl -s --max-time 60 "$B/chat/completions" -H "Authorization: Bearer $K" \
  -H "Content-Type: application/json" \
  -d "{\"model\":\"$M\",\"messages\":[{\"role\":\"user\",\"content\":\"Reply with exactly: PONG\"}],\"max_tokens\":8}" \
  | head -c 400
echo
