# OpenROAD global placement: target density 0.85 vs default on ISPD2005 adaptec2/adaptec3

Legal, officially scored placements of the ISPD2005 Bookshelf benchmarks with OpenROAD
`26Q2-1164-g08f67ee5ec` (Ubuntu 24.04 release .deb), comparing `global_placement` at its default
target density (0.70, logged as `GPL-0023`) with `global_placement -density 0.85`. Everything else is identical.

| design | default HPWL | `-density 0.85` HPWL | delta | runtime default / 0.85 |
|---|---:|---:|---:|---:|
| adaptec2 | 97,582,013 | 89,643,547 | **-8.14%** | 232.5 s / 360.1 s (1.55x) |
| adaptec3 | 218,907,385 | 206,830,024 | **-5.52%** | 362.8 s / 400.3 s (1.10x) |

HPWL is the official ISPD2005 `hpwl.pl` value; every placement passes the official `legal2.pl`
check with 0 errors of types 0–3, full node coverage, and unchanged fixed terminals. An earlier
same-binary screen on adaptec1 gave 78,974,740 vs 84,076,202 (-6.07%).

Flow: Bookshelf -> synthetic LEF/DEF (fixed-aware bridge, `src/bookshelf_bridge.py`) ->
`global_placement [GPL options]` -> `detailed_placement -max_displacement 100000` ->
`check_placement` -> DEF -> Bookshelf `.pl` -> official scripts.

- adaptec3 (`adaptec3/`, fresh run on a 4 vCPU Daytona sandbox, 4 threads): both arms use
  `detailed_placement -max_displacement 100000`. Without it, the default arm did not finish
  detailed placement within 1,100 s in an earlier 2-thread run.
- adaptec2 (`adaptec2/`, 2 threads): default `detailed_placement` left 5 cells unplaced; the
  default arm was repaired with `detailed_placement -max_displacement 100000` (runtime included).

Reproduce adaptec3: `bash run_all.sh` on Ubuntu 24.04 with the OpenROAD release .deb and the
ISPD2005 inputs from https://www.ispd.cc/contests/05/ispd05-contest/ (the official `hpwl.pl`
and `legal2.pl` come from the same contest page).

Scope: HPWL only. No global/detailed routing, congestion or DRV numbers were measured, so this
says nothing about routability, which is the usual reason for a lower default target density.
