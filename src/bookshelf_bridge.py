#!/usr/bin/env python3
"""Exact pin-offset Bookshelf -> synthetic LEF/DEF bridge for placement only.

One Bookshelf unit is one micron, with 1000 DBU per micron. Identical cell
geometry and ordered pin signatures share masters. No technology/timing or
routing claim is possible with the synthetic two-layer technology.
"""
from __future__ import annotations
import argparse
from collections import defaultdict
import gzip
import json
from pathlib import Path
import re


def lines(p):
    with (gzip.open(p, 'rt') if p.suffix == '.gz' else p.open()) as f:
        for s in f:
            s = s.strip()
            if s and not s.startswith('#') and not s.startswith('UCLA'):
                yield s


def read(prefix):
    prefix = Path(prefix)
    def path(ext):
        p = prefix.with_suffix(ext)
        return p if p.exists() else Path(str(p) + '.gz')
    nodes = {}
    for s in lines(path('.nodes')):
        p = s.split()
        if p[0].startswith('Num'): continue
        nodes[p[0]] = (float(p[1]), float(p[2]), 'terminal' in s)
    positions = {}
    for s in lines(path('.pl')):
        p = s.split(); positions[p[0]] = (float(p[1]), float(p[2]), p[4])
        # UCLA marks fixed macros and terminals in the placement file, while
        # the nodes file marks only terminals. Preserve both kinds as fixed.
        if p[0] in nodes and '/FIXED' in p[4:]:
            w, h, _ = nodes[p[0]]; nodes[p[0]] = (w, h, True)
    nets = []; pins = defaultdict(list); remaining = 0
    for s in lines(path('.nets')):
        p = s.split()
        if p[0].startswith('Num'): continue
        if p[0] == 'NetDegree':
            remaining = int(p[2]); nets.append((p[3], [])); continue
        assert remaining > 0
        name, direction = p[:2]
        j = p.index(':'); ox, oy = map(float, p[j+1:j+3])
        pin_id = len(pins[name]); pins[name].append((direction, ox, oy))
        nets[-1][1].append((name, pin_id)); remaining -= 1
    assert remaining == 0
    rows = []; row = {}
    for s in lines(path('.scl')):
        p = s.split()
        if p[0] == 'CoreRow': row = {}
        elif p[0] == 'End': rows.append(row)
        elif ':' in p:
            row[p[0]] = float(p[2])
            if p[0] == 'SubrowOrigin': row['NumSites'] = int(p[5])
    return nodes, positions, nets, pins, rows


def convert(prefix, out):
    out = Path(out); out.mkdir(parents=True, exist_ok=True)
    nodes, pos, nets, pins, rows = read(prefix)
    widths = {r['Sitewidth'] for r in rows}; heights = {r['Height'] for r in rows}
    assert len(widths) == len(heights) == 1
    sw, rh = next(iter(widths)), next(iter(heights))
    masters = {}; node_master = {}
    for name, shape in nodes.items():
        signature = (shape, tuple(pins[name]))
        if signature not in masters: masters[signature] = f'm{len(masters)}'
        node_master[name] = masters[signature]
    with (out/'cells.lef').open('w') as f:
        f.write('VERSION 5.8 ;\nBUSBITCHARS "[]" ;\nDIVIDERCHAR "/" ;\nUNITS\n DATABASE MICRONS 1000 ;\nEND UNITS\nMANUFACTURINGGRID 0.001 ;\n')
        for layer, direction in [('M1','HORIZONTAL'), ('M2','VERTICAL')]:
            f.write(f'LAYER {layer}\n TYPE ROUTING ;\n DIRECTION {direction} ;\n PITCH 1 ;\n WIDTH 0.1 ;\n SPACING 0.1 ;\nEND {layer}\n')
        f.write(f'SITE core\n CLASS CORE ;\n SYMMETRY X Y ;\n SIZE {sw:g} BY {rh:g} ;\nEND core\n')
        for ((w,h,fixed), pinlist), master in masters.items():
            cls = 'BLOCK' if fixed or h != rh else 'CORE'
            f.write(f'MACRO {master}\n CLASS {cls} ;\n ORIGIN 0 0 ;\n SIZE {w:g} BY {h:g} ;\n SYMMETRY X Y ;\n')
            if cls == 'CORE': f.write(' SITE core ;\n')
            for i,(direction,ox,oy) in enumerate(pinlist):
                x,y = w/2+ox,h/2+oy
                assert abs(x*1000-round(x*1000)) < 1e-6 and abs(y*1000-round(y*1000)) < 1e-6
                direction = {'I':'INPUT','O':'OUTPUT','B':'INOUT'}[direction]
                f.write(f' PIN p{i}\n  DIRECTION {direction} ;\n  USE SIGNAL ;\n  PORT\n   LAYER M1 ;\n   RECT {x-.001:.6f} {y-.001:.6f} {x+.001:.6f} {y+.001:.6f} ;\n  END\n END p{i}\n')
            f.write(f'END {master}\n')
        f.write('END LIBRARY\n')
    xlo = min(r['SubrowOrigin'] for r in rows); ylo = min(r['Coordinate'] for r in rows)
    xhi = max(r['SubrowOrigin']+r['NumSites']*r['Sitespacing'] for r in rows)
    yhi = max(r['Coordinate']+r['Height'] for r in rows)
    # Die encloses IO macros; rows still define the original placement core.
    dxlo = min([xlo]+[pos[n][0] for n in nodes if nodes[n][2]])
    dylo = min([ylo]+[pos[n][1] for n in nodes if nodes[n][2]])
    dxhi = max([xhi]+[pos[n][0]+nodes[n][0] for n in nodes if nodes[n][2]])
    dyhi = max([yhi]+[pos[n][1]+nodes[n][1] for n in nodes if nodes[n][2]])
    q = lambda x: round(x*1000)
    with (out/'input.def').open('w') as f:
        f.write(f'VERSION 5.8 ;\nDIVIDERCHAR "/" ;\nBUSBITCHARS "[]" ;\nDESIGN {Path(prefix).name} ;\nUNITS DISTANCE MICRONS 1000 ;\nDIEAREA ( {q(dxlo)} {q(dylo)} ) ( {q(dxhi)} {q(dyhi)} ) ;\n')
        for i,r in enumerate(rows):
            f.write(f'ROW r{i} core {q(r["SubrowOrigin"])} {q(r["Coordinate"])} N DO {r["NumSites"]} BY 1 STEP {q(r["Sitespacing"])} 0 ;\n')
        f.write(f'COMPONENTS {len(nodes)} ;\n')
        for n in nodes:
            x,y,orient = pos[n]; assert orient == 'N', (n,orient)
            status = 'FIXED' if nodes[n][2] else 'PLACED'
            f.write(f'- {n} {node_master[n]} + {status} ( {q(x)} {q(y)} ) N ;\n')
        f.write(f'END COMPONENTS\nNETS {len(nets)} ;\n')
        for n,connections in nets:
            f.write(f'- {n} ' + ' '.join(f'( {cell} p{p} )' for cell,p in connections) + ' ;\n')
        f.write('END NETS\nEND DESIGN\n')
    meta = dict(nodes=len(nodes), pins=sum(len(x) for x in pins.values()), nets=len(nets), masters=len(masters), fixed=sum(x[2] for x in nodes.values()), core=[xlo,ylo,xhi,yhi], scale_microns_per_bookshelf_unit=1)
    (out/'bridge.json').write_text(json.dumps(meta,indent=2)+'\n'); print(json.dumps(meta),flush=True)


def export(prefix, def_path, output):
    nodes, original, _, _, _ = read(prefix)
    s = Path(def_path).read_text(); section = s.split('COMPONENTS ',1)[1].split('END COMPONENTS',1)[0]
    positions = {}
    for name,x,y,orient in re.findall(r'-\s+(\S+)\s+\S+\s+\+\s+(?:FIXED|PLACED)\s+\(\s*(-?\d+)\s+(-?\d+)\s*\)\s+(\S+)',section):
        assert orient == 'N', (name,orient)
        positions[name] = (int(x)/1000,int(y)/1000,orient)
    assert positions.keys() == nodes.keys(), (len(positions),len(nodes))
    with Path(output).open('w') as f:
        f.write('UCLA pl 1.0\n')
        for name,(_,_,fixed) in nodes.items():
            x,y,o = positions[name]
            if fixed: assert positions[name] == original[name], (name,positions[name],original[name])
            f.write(f'{name} {x:g} {y:g} : {o}' + (' /FIXED' if fixed else '') + '\n')
    print(f'Exported {len(positions)} nodes',flush=True)


if __name__ == '__main__':
    ap = argparse.ArgumentParser(); sub = ap.add_subparsers(dest='mode',required=True)
    a = sub.add_parser('convert'); a.add_argument('prefix'); a.add_argument('out')
    a = sub.add_parser('export'); a.add_argument('prefix'); a.add_argument('def_path'); a.add_argument('output')
    args = vars(ap.parse_args()); mode = args.pop('mode')
    (convert if mode == 'convert' else export)(**args)
