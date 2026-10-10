#!/usr/bin/env python3
"""Execute via openroad -python. Configuration is supplied by environment."""
import json
import os
from pathlib import Path
import sys
import time
from openroad import Tech, Design

sys.path.insert(0,str(Path(__file__).resolve().parent))
from bookshelf_bridge import read

folder = Path(os.environ['BRIDGE_DIR']).resolve()
out = Path(os.environ['PLACEMENT_OUT']).resolve(); out.mkdir(parents=True,exist_ok=True)
start = time.perf_counter()
tech = Tech(); tech.readLef(str(folder/'cells.lef'))
design = Design(tech); design.readDef(str(folder/'input.def'))
design.evalTclString('set_thread_count '+os.environ.get('PLACEMENT_THREADS','4'))
block = design.getBlock()
print('Loaded',len(block.getInsts()),len(block.getNets()),flush=True)
iterm = block.getITerms()[0]
print('First pin',iterm.getAvgXY(),flush=True)

def score_and_audit(audit=False):
    hpwl = 0; pins = 0; mismatches = 0
    if audit:
        nodes, pos, _, signatures, _ = read(os.environ['BOOKSHELF_PREFIX'])
    for net in block.getNets():
        xs=[]; ys=[]
        for pin in net.getITerms():
            ok,x,y = pin.getAvgXY(); assert ok
            xs.append(x); ys.append(y); pins += 1
            if audit:
                inst = pin.getInst().getName(); pid = int(pin.getMTerm().getName()[1:])
                _,ox,oy = signatures[inst][pid]; w,h,_ = nodes[inst]
                px,py,_ = pos[inst]
                expected = (round((px+w/2+ox)*1000), round((py+h/2+oy)*1000))
                if (x,y) != expected: mismatches += 1
        if len(xs)>1: hpwl += max(xs)-min(xs)+max(ys)-min(ys)
    result = dict(hpwl_bookshelf_units=hpwl/1000,pins=pins,nets=len(block.getNets()),pin_coordinate_mismatches=mismatches)
    print(json.dumps(result),flush=True)
    if audit: assert mismatches == 0
    return result

before = score_and_audit(True)
assert before['hpwl_bookshelf_units'] == float(os.environ['EXPECTED_INPUT_HPWL'])
design.evalTclString(f'write_def {out}/roundtrip.def')
(out/'roundtrip.json').write_text(json.dumps(before,indent=2)+'\n')
if os.environ.get('ROUNDTRIP_ONLY') != '1':
    placement_start = time.perf_counter()
    command = 'global_placement' + (' '+os.environ['GPL_OPTIONS'] if os.environ.get('GPL_OPTIONS') else '')
    print('COMMAND',command,flush=True)
    design.evalTclString(command)
    gp_seconds = time.perf_counter()-placement_start
    gp_score = score_and_audit()
    design.evalTclString(f'write_def {out}/global.def')
    dp_start = time.perf_counter()
    dpl_options = os.environ.get('DPL_OPTIONS', '')
    dpl_command = 'detailed_placement' + (' ' + dpl_options if dpl_options else '')
    print('COMMAND', dpl_command, flush=True)
    design.evalTclString(dpl_command)
    dp_seconds = time.perf_counter()-dp_start
    design.evalTclString('check_placement -verbose')
    after = score_and_audit()
    design.evalTclString(f'write_def {out}/legal.def')
    result = dict(before=before,global_placement=gp_score,legal=after,gp_seconds=gp_seconds,dp_seconds=dp_seconds,total_seconds=time.perf_counter()-start,global_placement_command=command)
    (out/'metrics.json').write_text(json.dumps(result,indent=2)+'\n')
