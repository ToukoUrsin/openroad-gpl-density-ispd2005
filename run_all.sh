#!/usr/bin/env bash
# Bounded adaptec3 OpenROAD screen: default GPL vs -density 0.85, same DPL (-max_displacement 100000), 4 threads.
set -uo pipefail
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq && apt-get install -y -qq ./data/openroad_26Q2-1164-g08f67ee5ec_amd64-ubuntu-24.04.deb perl python3 time > results/apt.log 2>&1 || { tail -30 results/apt.log; exit 2; }
/usr/bin/openroad -version | tee results/openroad-version.txt
nproc | tee results/nproc.txt
export DPL_OPTIONS="-max_displacement 100000"
for v in "default-dpl100k|" "density085-dpl100k|-density 0.85"; do
  name=${v%%|*}; opts=${v#*|}
  echo "=== adaptec3 $name gpl='$opts' $(date -u +%FT%TZ)"
  python3 src/run_benchmark.py --bench adaptec3 --variant "$name" --gpl-options "$opts" --threads 4 --timeout 4500 --prefix data/benchmarks/adaptec3/adaptec3 > results/adaptec3-$name.run.log 2>&1
  echo "rc=$?"; tail -3 results/adaptec3-$name.run.log
  rm -f data/bridge-adaptec3-$name/*.def.big results/adaptec3-$name/global.def results/adaptec3-$name/roundtrip.def
done
