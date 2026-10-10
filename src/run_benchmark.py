#!/usr/bin/env python3
"""Fetch original public inputs, run bounded OpenROAD and official evaluators."""
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tarfile
import time
import urllib.request
from bookshelf_bridge import convert, export, read

ROOT = Path(__file__).resolve().parents[1]
BASE = 'https://www.ispd.cc/contests/05/ispd05-contest/'

def fetch(bench):
    assert bench in ['adaptec1','adaptec2','adaptec3','adaptec4','bigblue1','bigblue2','bigblue3','bigblue4']
    folder = ROOT/'data/benchmarks'/bench; folder.mkdir(parents=True,exist_ok=True)
    prefix = folder/bench
    if not prefix.with_suffix('.nodes').exists():
        url = BASE+('' if bench in ['adaptec1','adaptec3'] else 'benchmarks/')+bench+'.tar.gz'
        archive = folder/(bench+'.tar.gz'); urllib.request.urlretrieve(url,archive)
        with tarfile.open(archive) as tf:
            tf.extractall(folder,filter='data')
        for ext in ['.nodes','.nets','.pl','.scl','.aux','.wts']:
            target = prefix.with_suffix(ext)
            if target.exists(): continue
            candidates = list(folder.rglob(bench+ext))+list(folder.rglob(bench+ext+'.gz'))
            assert candidates, (bench,ext)
            source = candidates[0]
            target.write_bytes(gzip.decompress(source.read_bytes()) if source.suffix == '.gz' else source.read_bytes())
        provenance = dict(url=url,archive_sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),source_page='https://www.ispd.cc/contests/05/contest.htm')
        (folder/'source.json').write_text(json.dumps(provenance,indent=2)+'\n')
    return prefix

def official(prefix,placement,out):
    prefix,placement,out = Path(prefix).resolve(),Path(placement).resolve(),Path(out).resolve()
    def run(name,args):
        with (out/(name+'.log')).open('w') as log:
            subprocess.run(['nice','-n','19','perl',str(ROOT/'src'/name),*[str(x) for x in args]],cwd=out,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=180)
    run('hpwl.pl',[prefix.with_suffix('.nodes'),prefix.with_suffix('.pl'),placement,prefix.with_suffix('.nets')])
    run('legal2.pl',[prefix.with_suffix('.nodes'),prefix.with_suffix('.pl'),placement,prefix.with_suffix('.scl'),'100'])
    score = float(re.search(r'Total HPWL:\s*(\S+)',(out/'hpwl.pl.log').read_text()).group(1))
    errors = (out/'legality.error').read_text(); assert 'ERROR' not in errors
    return score

def experiment(bench,variant,gpl_options,threads,timeout,prefix=None,verify_existing=False):
    prefix = Path(prefix).resolve() if prefix else fetch(bench)
    bridge = ROOT/'data'/('bridge-'+bench+'-'+variant)
    if not (bridge/'bridge.json').exists(): convert(prefix,bridge)
    out = ROOT/'results'/f'{bench}-{variant}'; out.mkdir(parents=True,exist_ok=True)
    if not verify_existing:
        # Expected start score is computed with the official contest script.
        with (out/'input-hpwl.log').open('w') as log:
            subprocess.run(['nice','-n','19','perl',str(ROOT/'src/hpwl.pl'),str(prefix.with_suffix('.nodes')),str(prefix.with_suffix('.pl')),str(prefix.with_suffix('.pl')),str(prefix.with_suffix('.nets'))],stdout=log,stderr=subprocess.STDOUT,check=True,timeout=180)
        expected = re.search(r'Total HPWL:\s*(\S+)',(out/'input-hpwl.log').read_text()).group(1)
        env = os.environ.copy(); env.update(BRIDGE_DIR=str(bridge),PLACEMENT_OUT=str(out),BOOKSHELF_PREFIX=str(prefix),EXPECTED_INPUT_HPWL=expected,GPL_OPTIONS=gpl_options,PLACEMENT_THREADS=str(threads))
        command = ['nice','-n','19','/usr/bin/time','-v',str(ROOT/'run_openroad.sh'),'-exit','-python',str(ROOT/'src/openroad_place.py')]
        (out/'command.json').write_text(json.dumps(dict(command=command,environment={k:env[k] for k in ['BRIDGE_DIR','PLACEMENT_OUT','BOOKSHELF_PREFIX','EXPECTED_INPUT_HPWL','GPL_OPTIONS','PLACEMENT_THREADS']},timeout_seconds=timeout),indent=2)+'\n')
        with (out/'openroad.log').open('w') as log:
            subprocess.run(command,env=env,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=timeout)
    placement = out/(bench+'.pl')
    export(prefix,out/'legal.def',placement)
    score = official(prefix,placement,out)
    metrics = json.loads((out/'metrics.json').read_text())
    assert score == metrics['legal']['hpwl_bookshelf_units'], (score,metrics['legal'])
    with placement.open('rb') as f,gzip.open(str(placement)+'.gz','wb',compresslevel=9) as z: z.write(f.read())
    summary = dict(benchmark=bench,variant=variant,official_hpwl=score,legal=True,threads=threads,gpl_options=gpl_options,metrics=metrics,placement_sha256=hashlib.sha256(placement.read_bytes()).hexdigest())
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n'); print(json.dumps(summary),flush=True)
    return summary

if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('--bench',required=True); ap.add_argument('--variant',required=True); ap.add_argument('--gpl-options',default=''); ap.add_argument('--threads',type=int,default=4); ap.add_argument('--timeout',type=int,default=1100); ap.add_argument('--prefix'); ap.add_argument('--verify-existing',action='store_true')
    experiment(**vars(ap.parse_args()))
