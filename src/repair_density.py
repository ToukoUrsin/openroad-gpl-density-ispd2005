import os, time
from pathlib import Path
from openroad import Tech, Design
folder=Path(os.environ['BRIDGE_DIR']).resolve(); source=Path(os.environ['SOURCE_DEF']).resolve(); out=Path(os.environ['OUT_DIR']).resolve(); out.mkdir(parents=True,exist_ok=True)
tech=Tech(); tech.readLef(str(folder/'cells.lef')); design=Design(tech); design.readDef(str(source)); print('loaded',len(design.getBlock().getInsts()),flush=True)
for cmd in [f'detailed_placement -max_displacement {os.environ.get("MAX_DISP","100000")}', 'check_placement -verbose']:
    print('COMMAND',cmd,flush=True); t=time.perf_counter(); design.evalTclString(cmd); print('seconds',time.perf_counter()-t,flush=True)
design.evalTclString(f'write_def {out}/repaired.def')
