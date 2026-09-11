"""Deterministic opt-in auto-tool patch; fixed existing default is unchanged."""
import difflib
import hashlib
from pathlib import Path
import subprocess
import sys

TREE = '3aae90ae26b5ae7b65e6efed14fb49f2907c9c42'
BACKEND = 'src/dojo/core/solvers/llm_helpers/backends/lite_llm.py'
BEFORE_SHA = 'b58fd9603d8712928c1195da75b6fb2ed701129a54a6f530c4df44048fd9c2ec'


def revised(raw):
    if hashlib.sha256(raw).hexdigest() != BEFORE_SHA:
        raise ValueError('unexpected source')
    text = raw.decode()
    changes = [
        ('async def _query_once_bounded(self, messages, request_kwargs, func_spec, transport, timeout_seconds):',
         "async def _query_once_bounded(self, messages, request_kwargs, func_spec, transport, timeout_seconds, tool_choice_mode='named'):"),
        ("                kwargs['tool_choice'] = func_spec.openai_tool_choice_dict\n",
         "                kwargs['tool_choice'] = 'auto' if tool_choice_mode == 'auto' else func_spec.openai_tool_choice_dict\n"),
        ("        bounded_timeout = model_kwargs.pop('bounded_request_timeout_seconds', 60.)\n",
         "        bounded_timeout = model_kwargs.pop('bounded_request_timeout_seconds', 60.)\n"
         "        tool_choice_mode = model_kwargs.pop('bounded_tool_choice_mode', 'named')\n"
         "        if tool_choice_mode not in ('named', 'auto'):\n"
         "            raise ValueError('tool choice mode must be named or auto')\n"
         "        if tool_choice_mode != 'named' and bounded is not True:\n"
         "            raise ValueError('auto tool choice requires explicit bounded transport')\n"),
        ('        if structured_output_mode not in {"json", "tools"}:\n',
         "        if tool_choice_mode == 'auto' and (structured_output_mode != 'tools' or func_spec is None):\n"
         "            raise ValueError('auto tool choice requires the tools schema path')\n"
         '        if structured_output_mode not in {"json", "tools"}:\n'),
        ('                                                 structured_output_mode, bounded_timeout), bounded_attempts)\n',
         '                                                 structured_output_mode, bounded_timeout, tool_choice_mode), bounded_attempts)\n'),
    ]
    for old, new in changes:
        if text.count(old) != 1: raise ValueError('unexpected patch anchor')
        text = text.replace(old, new)
    return text


def main():
    raw = subprocess.check_output(['git', 'show', TREE+':'+BACKEND], cwd=Path(__file__).resolve().parents[1])
    new = revised(raw)
    patch = 'diff --git a/'+BACKEND+' b/'+BACKEND+'\n'+''.join(difflib.unified_diff(
        raw.decode().splitlines(True), new.splitlines(True), fromfile='a/'+BACKEND, tofile='b/'+BACKEND))
    sys.stdout.buffer.write(patch.encode())


if __name__ == '__main__': main()
