"""Same verified native namespace adapter, new explicit diagnostic context."""
import sys
import forets_closed_pool_native_20260911 as native
from forets_current_pool_20260912 import binding_context

native.binding_context=binding_context

if __name__=='__main__':
    try:native.main()
    except Exception as exc:
        print('CURRENT_POOL_BINDING_FAILED '+type(exc).__name__,file=sys.stderr)
        raise SystemExit(70)
