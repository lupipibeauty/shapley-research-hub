# Preliminary Experimental Results

> Superseded for final course-paper numbers: use
> `RESULTS_FINAL_EXPERIMENTS.md` and `runs/final_summary_v8`.

> Status: E0 has partial SQL coverage and the SF1 scale test is complete. These
> values can support the current draft, but the remaining caveats below must be
> resolved or disclosed before final submission.

## Dataset

TPC-H SF0.1 derived:

- 1,000 games;
- 11,582 player facts;
- 3,451,392 exact coalition values;
- 700 train / 105 validation / 70 in-distribution test / 125 OOD games;
- three model seeds: 20261107, 20261108, 20261109.
- separate SF1 external set: 200 games, 2,328 players, 708,608 coalition values.

SQL audit:

- one game with all 4,096 coalitions: PASS;
- 20 games stratified across all eight conditions, 128 sampled masks each:
  PASS;
- 2,560 audited masks in the stratified run;
- maximum absolute SQL/state utility difference: 1.78e-15.

## Main overall Share-L1

Lower is better. Values are game-level means. Model values average three seeds.
Confidence intervals are in `runs/final_summary_v4/summary_metrics.csv`.

| Method | In-distribution | Combination OOD | SF1 scale OOD |
|---|---:|---:|---:|
| Additive base | 0.1443 | 0.3250 | 0.1629 |
| Feature-MLP | 0.1447 | 0.3248 | 0.1631 |
| RPV-GNN | 0.0754 | 0.1086 | 0.0806 |
| RPV-GNN without graph edges | 0.0943 | 0.1768 | 0.1045 |
| RPV-GNN without additive anchor | 0.1276 | 0.1123 | 0.1287 |
| Permutation MC, 64 nominal steps | 0.0569 | 0.1348 | 0.0803 |
| Permutation MC, 256 nominal steps | 0.0404 | 0.0971 | 0.0511 |
| Permutation MC, 1024 nominal steps | 0.0160 | 0.0387 | 0.0190 |
| Permutation MC, 4096 nominal steps | 0.0179 | 0.0416 | 0.0197 |

## RPV-GNN supplementary metrics

| Metric | In-distribution | OOD |
|---|---:|---:|
| Owner Share-L1 | 0.0682 | 0.0975 |
| Spearman rank correlation | 0.9261 | 0.8527 |
| Top-3 overlap | 0.9143 | 0.9538 |
| Zero-player payment | 0.0 | 0.0 |
| Efficiency error | 4.82e-8 | 5.44e-8 |

## Extended evaluation metrics

The authoritative per-game metric file now records:

- player-share L1 and owner-share L1;
- MAE-share;
- 95th-percentile player absolute error;
- maximum player absolute error;
- top-quartile target-share MAE;
- Spearman and Top-3 overlap;
- NDCG@3;
- zero-player payment;
- efficiency error.

Values for the main and safe-routed models:

| Method | Split | P95 abs error | High-value MAE | NDCG@3 |
|---|---|---:|---:|---:|
| RPV-GNN | In-distribution | 0.0309 | 0.0211 | 0.9957 |
| Safe router | In-distribution | 0.0172 | 0.0139 | 0.9993 |
| RPV-GNN | Combination OOD | 0.0422 | 0.0330 | 0.9990 |
| Safe router | Combination OOD | 0.0422 | 0.0330 | 0.9990 |
| RPV-GNN | SF1 scale OOD | 0.0333 | 0.0224 | 0.9945 |
| Safe router | SF1 scale OOD | 0.0218 | 0.0170 | 0.9992 |

Macro-condition and overall means coincide in the current balanced design.
Worst-condition analysis shows that the residual difficulty remains in joint
value conditions, not additive-value conditions:

- in-distribution worst condition: tree/independent/joint, Share-L1 = 0.1187;
- combination OOD: cross/shared/joint, Share-L1 = 0.1086;
- SF1 worst condition: tree/shared/joint, Share-L1 = 0.1164.

## Interpretable findings

### Condition-level heterogeneity

The overall averages mix additive and joint-value games. The current RPV-GNN
improves strongly on joint-value games but does not preserve the exact additive
baseline in additive games. On in-distribution additive conditions,
Feature-MLP remains close to the exact base (about 7e-4 Share-L1), while RPV-GNN
has about 0.046-0.055 Share-L1. This is a material limitation and motivates a
value-conditioned safe router:

```text
additive value -> exact additive baseline
joint value    -> RPV-GNN residual allocation
```

Using existing condition-level errors only as a post-hoc estimate, such routing
would reduce in-distribution Share-L1 from 0.0754 to approximately 0.0464 and
SF1 from 0.0806 to approximately 0.0555 without changing combination-OOD points.
This estimate must be validated by a new, pre-specified run.

1. The full graph model substantially improves over the additive base and
   Feature-MLP on the in-distribution, combination-OOD, and SF1 scale-OOD
   regimes.
2. Removing graph edges increases OOD Share-L1 from 0.1086 to 0.1768 in the
   three-seed aggregate and from 0.0806 to 0.1045 on SF1, supporting the role of
   relational graph encoding.
3. Removing the additive anchor increases in-distribution Share-L1 from 0.0754
   to 0.1276, combination-OOD from 0.1086 to 0.1123, and SF1 from 0.0806 to
   0.1287. The three-seed results therefore support the additive anchor as a
   stability mechanism, while its combination-OOD gain is small.
4. High-budget MC remains more accurate than the neural predictor. The neural
   model's potential advantage is amortized inference for repeated games, not
   replacement of exact or high-budget sampling when maximum accuracy is
   required.

## Paired game-level comparisons

Positive differences mean RPV-GNN has lower error than the alternative.
Intervals and Holm-adjusted p-values are in
`runs/paired_comparisons_v1/paired_comparisons.csv`.

| Split | Alternative | Mean difference | 95% CI | Holm p |
|---|---|---:|---:|---:|
| In-distribution | Additive base | 0.0689 | [0.0352, 0.1048] | 0.0032 |
| In-distribution | Feature-MLP | 0.0692 | [0.0356, 0.1050] | 0.0032 |
| In-distribution | No graph edges | 0.0189 | [0.0077, 0.0307] | 0.0048 |
| In-distribution | No additive anchor | 0.0521 | [0.0406, 0.0627] | 0.0008 |
| In-distribution | MC-64 | -0.0186 | [-0.0294, -0.0058] | 0.0048 |
| Combination OOD | Additive base | 0.2164 | [0.1983, 0.2335] | 0.0008 |
| Combination OOD | Feature-MLP | 0.2162 | [0.1981, 0.2333] | 0.0008 |
| Combination OOD | No graph edges | 0.0682 | [0.0617, 0.0745] | 0.0008 |
| Combination OOD | No additive anchor | 0.0038 | [-0.0024, 0.0099] | 0.2294 |
| Combination OOD | MC-64 | 0.0262 | [0.0159, 0.0372] | 0.0008 |
| SF1 scale OOD | Additive base | 0.0823 | [0.0610, 0.1032] | 0.0008 |
| SF1 scale OOD | Feature-MLP | 0.0825 | [0.0614, 0.1034] | 0.0008 |
| SF1 scale OOD | No graph edges | 0.0239 | [0.0168, 0.0309] | 0.0008 |
| SF1 scale OOD | No additive anchor | 0.0481 | [0.0407, 0.0554] | 0.0008 |
| SF1 scale OOD | MC-64 | -0.0003 | [-0.0113, 0.0117] | 0.9600 |

The additive-anchor effect on combination OOD is not statistically resolvable
under the game-level sign-flip test. The paper must state this rather than
claiming a uniform advantage.

## Value-conditioned safe routing

The router uses only the known value-function type:

- additive value -> exact additive baseline;
- joint value -> RPV-GNN output.

Three-seed, game-level results:

| Split | RPV-GNN | Safe router |
|---|---:|---:|
| In-distribution | 0.0754 | **0.0464** |
| Combination OOD | 0.1086 | 0.1086 |
| SF1 scale OOD | 0.0806 | **0.0555** |

The router improves in-distribution and SF1 while leaving the all-joint
combination-OOD split unchanged by construction. Paired game-level differences:

- in-distribution: -0.0291, 95% CI [-0.0348, -0.0230];
- SF1: -0.0251, 95% CI [-0.0287, -0.0216];
- combination OOD: exactly zero.

This result supports a value-aware hybrid algorithm rather than a standalone GNN
for every value function.

## Dummy-player negative control

Constructed 100 games stratified across all conditions with 199 disconnected
players. The original players, SQL logic, graph edges, and utilities were
unchanged for the connected component.

Three-seed results across all 100 games:

| Model | Share-L1 | Owner-L1 | Zero-player payment |
|---|---:|---:|---:|
| Full RPV-GNN | 0.0815 | 0.0746 | **0.0** |
| Zero mask disabled | 0.0815 | 0.0746 | 8.35e-9 |

Connected-player accuracy is unchanged. The hard mask is therefore necessary
for exact zero payment; without it, the softmax output retains a small but
nonzero payment to disconnected players.

## Runtime and amortization

CPU measurements, five repeats, in-memory value evaluation:

| Method | Median ms/game |
|---|---:|
| RPV-GNN, batch 1 | 5.33 |
| RPV-GNN, batch 8 | 1.19 |
| RPV-GNN, batch 32 | 0.74 |
| Feature-MLP, batch 32 | 0.45 |
| MC-64 | 0.78 |
| MC-256 | 2.92 |
| MC-1024 | 12.14 |

One representative RPV-GNN seed required 27.47 seconds to train. With inference
at 0.74 ms/game, amortized CPU cost at K=1,000 is still about 28.2 ms/game.

This benchmark does **not** include SQL execution or optional lineage
construction because MC uses the prebuilt Python utility evaluator. In this
cheapest-utility setting, RPV-GNN has no amortization-speed advantage over
MC-64. A database-backed benchmark is required before making an efficiency
claim.

A separate DuckDB SQL utility benchmark on 10 games measured:

- median context-table preparation: 13.65 ms per game;
- median query cost: 17.27 ms per SQL utility evaluation;
- implied MC-64: about 1,119 ms per game;
- implied MC-256: about 4,396 ms per game;
- RPV-GNN graph tensorization plus model forward at batch 32: about 0.74 ms.

These SQL timings still exclude provenance graph construction. They show why
the amortization conclusion depends critically on the cost of utility calls.

## Seed-ensemble uncertainty

Three-seed prediction variability was computed for each player. The model's
uncertainty is not calibrated:

| Model | Split | Seed SD | Spearman(seed SD, error) | 95% interval coverage |
|---|---|---:|---:|---:|
| RPV-GNN | In-distribution | 0.00258 | 0.284 | 0.164 |
| RPV-GNN | Combination OOD | 0.00219 | 0.163 | 0.139 |
| RPV-GNN | SF1 scale OOD | 0.00245 | 0.293 | 0.174 |
| Safe router | In-distribution | 0.00076 | 0.915 | 0.589 |
| Safe router | Combination OOD | 0.00219 | 0.163 | 0.139 |
| Safe router | SF1 scale OOD | 0.00091 | 0.886 | 0.560 |

High-uncertainty quartiles have roughly twice the error of low-uncertainty
quartiles, but the nominal 95% seed intervals substantially under-cover the
true values. They should be presented as diagnostic dispersion, not calibrated
confidence intervals.

## Model complexity

- RPV-GNN: 69,188 trainable parameters.
- Feature-MLP: 27,075 trainable parameters.

## Required caveats

- SQL validation covers one full game and a stratified sample from 20 games,
  not all 1,000 games. The course paper must describe this scope precisely.
- The current dataset contains no target-zero players, so the zero-payment
  metric is currently vacuous.
- Inference timing has been recorded only with an in-memory utility evaluator;
  SQL-grounded and graph-construction costs remain untested.
- Figures in `figures/final_zh_v8` are generated from the current frozen
  summary and are explicitly provisional.
