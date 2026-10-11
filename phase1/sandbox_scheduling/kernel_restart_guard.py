"""Surface kernel-wide death before request-ID filtering; never retry a task.

Jupyter Server2.20.0 channels._send_status_message emits parentless restarting/
dead messages for the kernel-specific websocket. They invalidate active state.
"""
import ast

ANCHOR='            # Ignore messages that are not for this execution.\n'
GUARD='''            # Kernel-wide gateway lifecycle events have no execute-request parent.
            # A restart destroys this execution even if a replacement kernel is alive.
            content_for_status = message.get("content")
            if (
                message.get("msg_type") == "status"
                and message.get("channel") == "iopub"
                and isinstance(content_for_status, dict)
                and content_for_status.get("execution_state") in ("restarting", "dead")
            ):
                return JupyterKernelClient.ExecutionResult(
                    is_ok=False,
                    output=["ERROR: Kernel state lost during execution (gateway lifecycle event)."],
                    data_items=[],
                    timed_out=False,
                )

'''

def overlay(source):
    tree=ast.parse(source)
    cls=next(x for x in tree.body if isinstance(x,ast.ClassDef) and x.name=='JupyterKernelClient')
    method=next(x for x in cls.body if isinstance(x,ast.FunctionDef) and x.name=='execute')
    text=''.join(source.splitlines(keepends=True)[method.lineno-1:method.end_lineno])
    assert text.count(ANCHOR)==1 and source.count(ANCHOR)==1
    result=source.replace(ANCHOR,GUARD+ANCHOR,1)
    compile(result,'kernel-restart-guard','exec')
    return result

if __name__=='__main__':
    import sys
    from pathlib import Path
    original,target=map(Path,sys.argv[1:])
    with target.open('x') as f:f.write(overlay(original.read_text()))
