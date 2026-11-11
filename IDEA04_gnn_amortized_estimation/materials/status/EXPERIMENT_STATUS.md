# Experiment Status

Updated: 2026-11-08

## Completed

- Implemented TPC-H context extraction and 12-player-or-smaller game generation.
- Implemented G0, threshold, and joint utility functions.
- Implemented exact Shapley enumeration for games with at most 12 players.
- Implemented heterogeneous provenance-value graph construction.
- Implemented RPV-GNN without PyTorch Geometric.
- Implemented Feature-MLP baseline.
- Implemented permutation Monte Carlo and additive-base baselines.
- Implemented player-level and owner-level metrics plus game-level bootstrap intervals.
- Created an isolated CPU PyTorch environment.
- Added unit/property tests for exact Shapley efficiency, utility monotonicity,
  graph validity, metric definitions, MC validity, and allocation constraints.
- Generated and validated TPC-H SF0.1 smoke datasets.
- Ran short smoke training for RPV-GNN, Feature-MLP, and the no-edge ablation.
- Generated the 1,000-game final candidate dataset (`data/final/tpch_g1000_v2.jsonl`).
- Ran three training seeds for RPV-GNN and Feature-MLP.
- Ran three training seeds for the no-edge and no-anchor ablations.
- Evaluated in-distribution, combination-OOD, and SF1 scale-OOD splits.
- Built game-level bootstrap summaries and provisional figures.
- Ran a full 4,096-coalition SQL audit on one game.
- Ran stratified SQL audit on 20 games across all eight conditions, using 128
  sampled coalitions per game.
- Ran paired game-level bootstrap comparisons with Holm correction.
- Evaluated a value-conditioned safe router on all three test regimes.
- Built a 100-game dummy-player control with 199 disconnected players.
- Verified exact zero payment with the structural mask and a small positive
  payment when the mask is disabled.
- Benchmarked CPU graph-tensor construction and model inference.
- Added P95/max/high-value tail metrics and NDCG@3.
- Added macro-condition summaries and worst-condition reporting.
- Added seed-ensemble uncertainty diagnostics.
- Added a context-local DuckDB SQL utility cost benchmark.
- Added three-seed cached permutation MC and a regression control-variate MSR
  strong baseline.
- Reran the study into a unified three-seed final summary.
- Completed a 10-game end-to-end DuckDB lineage, graph, model, and MC benchmark.
- Completed frozen D1-P/P3 zero-shot schema-adapter tests.
- Completed 0/5/10/20/30% graph-edge perturbation tests with three perturbation
  seeds and three model seeds.
- Generated final Chinese-labelled figures in `figures/final_zh_v12`.

## Current Smoke Data

```text
data/smoke/tpch_g16.jsonl
  16 games, 186 players, 56,320 coalition values

data/smoke/tpch_g80.jsonl
  80 games, 929 players, 279,552 coalition values
  train: 42
  validation: 14
  in_distribution: 14
  ood: 10
```

## Smoke Run Directories

```text
runs/smoke_rpv_anchored2_20261107
runs/smoke_mlp_anchored_20261107
runs/smoke_no_edges_20261107
runs/smoke_baselines_20261107
runs/smoke_summary_20261107_v4
runs/final_summary_v3
runs/final_summary_v4
runs/paired_comparisons_v1
runs/safe_route_summary_v1
runs/safe_route_paired_v1
runs/dummy_summary_v1
runs/dummy_paired_v1
runs/benchmark_rpv_ind_20261113
runs/benchmark_mlp_ind_20261113
runs/benchmark_mc_ind_20261113
runs/benchmark_rpv_ood_20261113
runs/benchmark_mc_ood_20261113
runs/benchmark_rpv_sf1_20261113
runs/benchmark_mc_sf1_20261113
runs/final_summary_v6
runs/uncertainty_rpv_v1
runs/uncertainty_safe_v1
runs/model_complexity_v1
runs/benchmark_sql_ind_g10_20261114
figures/provisional_v2
figures/provisional_v3
figures/final_zh_v5
figures/final_zh_v8
```

Earlier short runs are retained as debugging history and should not be used for
the paper.

## Important Limitations

- Full-data results remain provisional until the agreed SQL-audit coverage is
  completed and frozen with the manuscript.
- The current data generator uses TPC-H-derived Python provenance-state labels;
  one full game and a stratified 20-game mask sample have been audited so far.
- Dummy-player zero payment is validated on the generated negative-control set.
- The SQL benchmark includes local context-table preparation and utility queries,
  but not SQL lineage or provenance-graph construction.
- Strong sampling baselines beyond permutation MC have not been run.

## Current Gate

The planned experiment work for the course-paper scope is complete. The final
evidence and claim boundaries are recorded in
`RESULTS_FINAL_EXPERIMENTS.md`. Remaining work is manuscript integration and
final citation and format checking.
