#!/usr/bin/env python3
"""Fail-closed one-token provider probes; never prints credentials or response bodies."""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request


PROVIDERS = (
    ("deepseek-v4-flash", "https://api.deepseek.com/chat/completions", "PRIMARY_KEY_DEEPSEEK_V4_FLASH"),
    (
        "qwen3-coder-flash",
        "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
        "PRIMARY_KEY_QWEN3_CODER_FLASH",
    ),
    ("glm-5", "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions", "PRIMARY_KEY_GLM_5"),
)


def main() -> int:
    proxy = urllib.request.ProxyHandler({"https": os.environ.get("https_proxy", "")})
    opener = urllib.request.build_opener(proxy)
    for model, url, key_name in PROVIDERS:
        key = os.environ.get(key_name)
        if not key:
            print(f"PROVIDER_PROBE_FAIL model={model} reason=key_missing")
            return 2
        body = json.dumps(
            {"model": model, "messages": [{"role": "user", "content": "1"}], "max_tokens": 1}
        ).encode()
        request = urllib.request.Request(
            url,
            data=body,
            headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"},
        )
        try:
            with opener.open(request, timeout=45) as response:
                if int(response.status) < 200 or int(response.status) >= 300:
                    print(f"PROVIDER_PROBE_FAIL model={model} reason=http_status")
                    return 2
                response.read(1)
        except urllib.error.HTTPError as error:
            print(f"PROVIDER_PROBE_FAIL model={model} reason=http_{error.code}")
            return 2
        except Exception as error:  # only the class is safe to print
            print(f"PROVIDER_PROBE_FAIL model={model} reason={type(error).__name__}")
            return 2
        print(f"PROVIDER_PROBE_PASS model={model} max_tokens=1")
    print("BALANCED_CLIENT_PROVIDER_PROBES_PASS providers=3")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
