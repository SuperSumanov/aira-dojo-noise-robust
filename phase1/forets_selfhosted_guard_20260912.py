"""Explicit local-service auth only. No network, fallback, or deployment."""
from urllib.parse import urlsplit

MODEL = 'qwen3.8-27b'
VARIABLE = 'PRIMARY_KEY_QWEN3_8_27B'


def selfhosted_key(model, base_url, environment):
    if model != MODEL or not isinstance(base_url, str):
        raise ValueError('unapproved local model/endpoint')
    if any(c.isspace() for c in base_url):
        raise ValueError('invalid local endpoint')
    try:
        url = urlsplit(base_url)
        port = url.port
    except ValueError:
        raise ValueError('invalid local endpoint') from None
    if (url.scheme != 'http' or url.hostname not in ('127.0.0.1', 'localhost')
            or port != 8000 or url.path.rstrip('/') != '/v1'
            or url.username is not None or url.password is not None or url.query or url.fragment):
        raise ValueError('only the documented node-local endpoint is allowed')
    key = environment.get(VARIABLE)
    if not isinstance(key, str) or not key.strip() or any(c.isspace() for c in key):
        raise ValueError('local model-specific credential missing or invalid')
    if key.startswith('sk-or-'):
        raise ValueError('OpenRouter credential cannot be used for the local service')
    return key


def patch_backend(source):
    """Patch a future isolated source, never the closed experiment in place."""
    old = '''        api_key = os.getenv("PRIMARY_KEY_" + self.model.replace("-", "_").replace(".", "_").upper(), "")
        if api_key:
            self.api_key = api_key
        else:
            self.api_key = os.getenv("PRIMARY_KEY", "")
'''
    new = '''        if client_cfg.provider == "selfhosted":
            from .selfhosted_guard import selfhosted_key
            self.api_key = selfhosted_key(self.model, self.base_url, os.environ)
        else:
            api_key = os.getenv("PRIMARY_KEY_" + self.model.replace("-", "_").replace(".", "_").upper(), "")
            if api_key:
                self.api_key = api_key
            else:
                self.api_key = os.getenv("PRIMARY_KEY", "")
'''
    if source.count(old) != 1:
        raise ValueError('exact backend auth block changed')
    return source.replace(old, new, 1)
