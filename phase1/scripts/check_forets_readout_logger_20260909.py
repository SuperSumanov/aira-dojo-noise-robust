"""New reader with real deployed JsonLogger; only artificial result events."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace as NS


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root',type=Path,required=True)
    parser.add_argument('--reader-root',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    os.environ.update(LOGGING_DIR='/tmp',CUDA_VISIBLE_DEVICES='',LITELLM_LOCAL_MODEL_COST_MAP='True')
    sys.path[:0]=[str(args.reader_root),str(args.source_root/'src')]
    from dojo.utils.logger import JsonLogger,LogEvent
    from forets_e2e_readout import ROLE,run_order,summarize
    with tempfile.TemporaryDirectory(prefix='forets-readout-real-logger-',dir='/tmp') as folder:
        root=Path(folder)
        manifest=dict(schema=1,role=ROLE,source_tree='0'*40,runs=[])
        for index,(task,seed,policy) in enumerate(run_order()):
            run_dir=root/f'run-{index}'
            logger=JsonLogger(NS(logger=NS(output_dir=str(run_dir))),'artificial')
            logger.log_dict({'score':0.0,'selected_node_id':f'artificial-{index}'},LogEvent.EVAL)
            logger.stop()
            (run_dir/'process').mkdir()
            (run_dir/'process/summary.json').write_text(json.dumps(dict(started=True,status='completed',returncode=0,elapsed_seconds=1.)))
            manifest['runs'].append(dict(run_id=f'artificial-{index}',run_dir=f'run-{index}',
                config_sha256=f'{index:064x}',
                process_summary=f'run-{index}/process/summary.json',task=task,seed=seed,policy=policy))
        result=summarize(manifest,root)
        assert result['planned_runs']==8 and result['comparable_pairs']==4
        assert all(row['comparable_score']==0.0 and row['comparable_final'] for row in result['runs'])
        assert all(row['improvement']==0.0 for row in result['pairs'])
        receipt=dict(status='ARTIFICIAL_LOGGER_INTEGRATION_PASS',artificial_run_records=len(result['runs']),
            artificial_pairs=len(result['pairs']),real_task_runs=0,gpu_jobs=0,model_loads=0,external_api_calls=0,
            protected_data_read=False,reader_sha256=hashlib.sha256((args.reader_root/'forets_e2e_readout.py').read_bytes()).hexdigest(),
            logger_sha256=hashlib.sha256((args.source_root/'src/dojo/utils/logger.py').read_bytes()).hexdigest(),
            scope='actual JsonLogger + new reader, artificial events and process summaries; not real e2e')
    with args.output.open('x') as file:
        json.dump(receipt,file,indent=2)
        file.write('\n')
    print(json.dumps(receipt))


if __name__=='__main__':
    main()
