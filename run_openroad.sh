#!/usr/bin/env bash
set -euo pipefail
export OMP_NUM_THREADS="${PLACEMENT_THREADS:-4}" OPENBLAS_NUM_THREADS="${PLACEMENT_THREADS:-4}" MKL_NUM_THREADS="${PLACEMENT_THREADS:-4}"
exec /usr/bin/openroad "$@"
