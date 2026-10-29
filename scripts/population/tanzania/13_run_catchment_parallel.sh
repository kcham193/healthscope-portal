#!/usr/bin/env bash
# NOTE: run from the hf-data-portal project root - paths below expect its
# "population and access tab/" folder (rasters are not committed here).
# Run catchment_pop_bayesian_regional.R for all Tanzania regions on N
# parallel workers, then combine. Run from anywhere; survives logout if
# started with nohup:
#   nohup bash "population and access tab/run_catchment_parallel.sh" > logs/catchment_full.log 2>&1 &
set -u
cd "$(dirname "$0")/.."
SCRIPT="population and access tab/catchment_pop_bayesian_regional.R"
N_WORKERS=${N_WORKERS:-4}
mkdir -p logs

# Regions largest-first (by facility count), dealt round-robin to workers
REGIONS=("Dar es Salaam" "Morogoro" "Mwanza" "Dodoma" "Tanga" "Pwani" "Arusha"
         "Mbeya" "Tabora" "Kilimanjaro" "Mara" "Ruvuma" "Kagera" "Shinyanga"
         "Njombe" "Kigoma" "Mtwara" "Singida" "Geita" "Iringa" "Lindi"
         "Manyara" "Simiyu" "Songwe" "Rukwa" "Katavi")

pids=()
for ((w = 0; w < N_WORKERS; w++)); do
  mine=()
  for ((i = w; i < ${#REGIONS[@]}; i += N_WORKERS)); do mine+=("${REGIONS[$i]}"); done
  echo "[$(date +%T)] worker $w: ${mine[*]}"
  Rscript "$SCRIPT" "${mine[@]}" > "logs/catchment_worker$w.log" 2>&1 &
  pids+=($!)
done
for p in "${pids[@]}"; do wait "$p"; done

echo "[$(date +%T)] workers finished; combining"
Rscript "$SCRIPT" 2>&1 | grep -vE '^ *\|'
echo "[$(date +%T)] all done"
