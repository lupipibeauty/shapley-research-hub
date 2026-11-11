# Final Course-Paper Experiment Report

Updated: 2026-11-08

This report records the experiments completed after the preliminary result
freeze. The primary unit is one complete Shapley game. Model seeds and graph
perturbation seeds are averaged within a game before game-level uncertainty is
estimated.

## 1. Final evaluation scope

TPC-H SF0.1 training and test data:

- 1,000 games and 11,582 player facts;
- 700 train / 105 validation / 70 in-distribution / 125 combination OOD;
- three model seeds: 20261107, 20261108, 20261109.

TPC-H SF1 scale-OOD data:

- 200 games and 2,328 player facts.

The final result table uses the cached permutation implementation for MC so
that repeated coalition masks do not trigger repeated SQL evaluations. All
main methods use the same game split and target normalization.

## 2. Final overall Share-L1

Lower is better. Values are game-level means with three model seeds.

| Method | In-distribution | Combination OOD | SF1 scale OOD |
|---|---:|---:|---:|
| Additive proxy | 0.1443 | 0.3250 | 0.1629 |
| Feature-MLP | 0.1447 | 0.3248 | 0.1631 |
| RPV-GNN | 0.0754 | 0.1086 | 0.0806 |
| RPV-GNN without edges | 0.0943 | 0.1768 | 0.1045 |
| RPV-GNN without additive anchor | 0.1276 | 0.1123 | 0.1287 |
| **Value-conditioned safe route** | **0.0464** | **0.1086** | **0.0555** |
| Cached permutation MC-64 | 0.0799 | 0.1847 | 0.0980 |
| Cached permutation MC-256 | 0.0465 | 0.1108 | 0.0553 |
| Cached permutation MC-1024 | 0.0206 | 0.0505 | 0.0244 |
| Regression control-variate MSR-64 | 0.1514 | 0.3542 | 0.1834 |
| Regression control-variate MSR-256 | 0.1369 | 0.3209 | 0.1603 |
| Regression control-variate MSR-1024 | 0.1353 | 0.3141 | 0.1566 |

Safe routing uses the known value-function type only:

```text
additive value -> exact additive share
joint value    -> RPV-GNN prediction
```

The safe route improves over MC-64 in all three splits. Its paired differences
in Share-L1 are:

| Split | Alternative | Mean difference | 95% CI | Holm p |
|---|---|---:|---:|---:|
| In-distribution | MC-64 | 0.0336 | [0.0240, 0.0442] | 0.0007 |
| Combination OOD | MC-64 | 0.0761 | [0.0693, 0.0829] | 0.0007 |
| SF1 | MC-64 | 0.0426 | [0.0352, 0.0503] | 0.0007 |

Positive differences mean the alternative has higher error. The safe route is
not statistically distinguishable from MC-256 in the three splits. MC-1024 is
still significantly more accurate than the safe route.

## 3. Strong regression baseline

The implemented regression MSR is an affine additive control variate fitted
from sampled coalition values, followed by residual permutation sampling under
the same cached coalition budget. It is a defensible local adaptation, not a
claim that every published MSR variant has been reproduced.

The additive proxy does not explain the threshold and joint games. Residual
sampling therefore has higher variance than ordinary permutation MC, and the
regression baseline fails to beat MC at every tested budget. This is retained
as a negative result rather than hidden or replaced by a weaker baseline.

## 4. Extended metrics

Safe-route uncertainty intervals are game-level bootstrap intervals after
averaging three model seeds:

| Split | Share-L1 | P95 absolute error | High-contribution MAE | NDCG@3 | Owner-L1 |
|---|---:|---:|---:|---:|---:|
| In-distribution | 0.0464 | 0.0172 | 0.0139 | 0.9993 | 0.0409 |
| Combination OOD | 0.1086 | 0.0422 | 0.0330 | 0.9990 | 0.0975 |
| SF1 | 0.0555 | 0.0218 | 0.0170 | 0.9992 | 0.0499 |

The worst condition remains a joint-value condition in every split. Current
condition means are balanced, so macro averages are numerically equal to
overall averages.

## 5. Graph perturbation

Randomly removed edges are restricted to
`witness_supports_coordinate` and `coordinate_to_value_factor`. Player nodes and
the final report node remain in place. Each nonzero removal fraction uses
three perturbation seeds and all three trained model seeds.

| Removal | In-distribution Share-L1 | Combination OOD | SF1 |
|---:|---:|---:|---:|
| 0% | 0.0754 | 0.1086 | 0.0806 |
| 5% | 0.0755 | 0.1085 | 0.0806 |
| 10% | 0.0756 | 0.1084 | 0.0806 |
| 20% | 0.0775 | 0.1089 | 0.0821 |
| 30% | 0.0905 | 0.1180 | 0.0962 |

Pairing each perturbed game to its own unperturbed prediction gives:

- 5% removal: practically negligible changes; in-distribution Holm
  `p = 0.0502` and the other splits are not significant;
- 10% removal: a statistically detectable but tiny in-distribution increase of
  0.00011; OOD and SF1 changes are not significant;
- 20% removal: significant only for SF1, increase 0.00149;
- 30% removal: significant in every split, with increases of 0.0150, 0.0094,
  and 0.0155, respectively.

The practical conclusion is that the trained model is insensitive to removing
up to roughly 10% of eligible structural edges and begins to degrade clearly
at 30%. The model is not uniformly dependent on every source edge.

## 6. D1-P and P3 zero-shot adaptation

A frozen semantic adapter was applied without retraining:

- D1-P: 12 logical record-bundle players, exact V1/V2 standard Shapley targets;
- P3-0: 13 physical-fact players, exact G0/G1 standard Shapley targets;
- player identities and target normalization were preserved;
- source, witness, report coordinate, value-factor, and report nodes were
  mapped to the existing RPV graph schema.

Overall Share-L1:

| External game | Uniform baseline | Feature-MLP | RPV-GNN |
|---|---:|---:|---:|
| D1-P V1 | 0.1000 | 0.1000 | 0.1127 |
| D1-P V2 | 0.0897 | 0.0897 | 0.1049 |
| P3-0 G0 | 0.1846 | 0.1846 | 0.1909 |
| P3-0 G1 | 0.2280 | 0.2281 | 0.2088 |

RPV-GNN lowers Share-L1 only on P3-0 G1. Its player-rank Spearman correlations
are approximately -0.154 for both D1-P games and 0.113, 0.223 for P3-0 G0/G1.
These values do not establish useful cross-schema ranking transfer. With only
four external games, the result is descriptive and cannot support a
population-level generalization claim.

The manuscript should state that the frozen TPC-H model has not demonstrated
cross-schema generalization. TPC-H same-schema and SF1 scale transfer remain
the supported scope.

## 7. End-to-end SQL and inference cost

Measured on 10 stratified in-distribution games with DuckDB and a single CPU
checkpoint. Each per-game value is the median of three repeats.

| Stage | Median ms/game |
|---|---:|
| SQL bind/plan (`EXPLAIN`) | 3.87 |
| Source and lineage extraction | 18.61 |
| Provenance-value graph construction | 0.21 |
| Graph tensorization | 0.28 |
| Model forward | 3.95 |
| Owner aggregation | 0.016 |
| **RPV-GNN end to end** | **27.12** |
| **MC-64 end to end** | **796.75** |
| **MC-256 end to end** | **2581.18** |
| **MC-1024 end to end** | **7328.36** |

The MC path de-duplicates masks before executing SQL. Across the 10/12-player
benchmark games, nominal 64-step budgets commonly require 50-56 unique SQL
evaluations, while nominal 1024-step budgets require roughly 480-670 unique
evaluations.

The benchmark:

- includes SQL planning, source extraction, graph construction, tensorization,
  model forward, and owner aggregation for the model path;
- includes utility queries and owner aggregation for MC;
- excludes training-label enumeration, model training, connection setup, disk
  cache effects, and process startup;
- uses one checkpoint for the timing comparison, not the three-seed accuracy
  aggregate.

The model's inference start-up cost is therefore much lower than repeated MC
under database-backed utility evaluation, but this does not erase the
training-label or training cost. The correct claim is amortized inference
potential, not zero-cost contribution estimation.

## 8. Reproducibility

Primary outputs:

- `runs/final_summary_v8/summary_metrics.csv`
- `runs/advanced_summary_v1/summary_metrics.csv`
- `runs/paired_safe_vs_alternatives_share_l1_v2/paired_comparisons.csv`
- `runs/external_zero_shot_v3/summary.json`
- `runs/benchmark_end_to_end_ind_g10_final_20261108/summary.json`
- `runs/graph_perturbation_v1/per_game_metrics.csv`
- `runs/graph_perturbation_summary_v1/summary_metrics.csv`
- `figures/final_zh_v12/figure_manifest.json`

The final figures are Chinese-labelled, opaque RGB PNG and PDF at 600 dpi.

## 9. Claims that are not supported

Do not claim that:

- RPV-GNN dominates exact Shapley or high-budget MC;
- the safe router has solved cross-schema generalization;
- the method is uniformly robust to arbitrary graph corruption;
- graph edges matter equally for every player or condition;
- regression MSR is universally weak, since only one additive-control-variate
  adaptation was tested;
- end-to-end timings include training-label generation.
