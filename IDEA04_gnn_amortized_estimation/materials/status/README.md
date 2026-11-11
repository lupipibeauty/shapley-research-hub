# Course Paper GNN

Implementation workspace for the course paper:

> 基于图神经网络的关系数据贡献估算方法研究

This package builds TPC-H-derived local relational games, computes exact
Shapley shares for 12-player-or-smaller games, converts each game into a
heterogeneous provenance-value graph, and trains an RPV-GNN or feature-MLP
baseline.

## Status

- Isolated environment: created at `.venv-course`.
- Installed: PyTorch 2.15.0 CPU, DuckDB 1.5.6, NumPy 2.4.6, pandas 3.1.1.
- Dataset and model code: initial implementation complete.
- Unit/property tests: 9 passed.
- TPC-H smoke dataset: 80 games, 929 players, 279,552 coalition values.
- Training and ablation runs: three seeds for RPV-GNN, Feature-MLP, No-Edge,
  and No-Anchor variants.
- Full candidate dataset: 1,000 SF0.1 games plus 200 SF1 scale-OOD games.
- SQL audit: one full game and a stratified 20-game sample passed.
- Full experiments remain provisional because SQL-audit coverage and inference
  timing are incomplete.

## Environment

Data generation uses Python 3.11, DuckDB, NumPy, and pandas. Model training
requires PyTorch.

The existing TPC-H DuckDB files are:

```text
..\tmp\researchlab_v2\workspace\BRBD_v1\runs\R1_luo\tpch_sf01\tpch_sf01.duckdb
..\tmp\researchlab_v2\workspace\BRBD_v1\runs\R1_luo\tpch_sf1\tpch_sf1.duckdb
```

## Generate a smoke dataset

From the `course_paper_gnn` directory:

```powershell
$env:PYTHONPATH="src"
.\.venv-course\Scripts\python.exe -m course_paper_gnn.build_dataset `
  --db "..\tmp\researchlab_v2\workspace\BRBD_v1\runs\R1_luo\tpch_sf01\tpch_sf01.duckdb" `
  --output "data\smoke\tpch_g16.jsonl" `
  --games-per-condition 2 `
  --seed 20261107
```

The final candidate uses 125 games per condition. Add
`--output data\final\tpch_g1000_v2.jsonl` to generate it.

## Run tests

```powershell
$env:PYTHONPATH="src"
.\.venv-course\Scripts\python.exe -m unittest discover -s tests -v
```

## Train

```powershell
$env:PYTHONPATH="src"
.\.venv-course\Scripts\python.exe -m course_paper_gnn.train `
  --data data\final\tpch_g1000.jsonl `
  --output runs\rpv_gnn_seed20261107 `
  --model rpv_gnn `
  --seed 20261107
```

Do not launch the full run until the smoke dataset, graph checks, and
four-game overfit check pass. Continue to treat results as provisional until
the SQL audit and performance measurements are frozen.
