from __future__ import annotations

import hashlib
import json
import sys
import time
from collections import Counter
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
OFFICIAL = ROOT / "external" / "fgsv" / "source" / "Faithful_GSV-main" / "exp1_benchmark"
sys.path.insert(0, str(OFFICIAL))

from estimators import (  # noqa: E402
    FGSV,
    complement,
    group_testing,
    kernel_shap,
    leverage_shap,
    one_for_all,
    permutation,
    unbiased_kernel_shap,
)
from utils import U_sou, generate_sou_game, sv_sou_true  # noqa: E402


OUT = ROOT / "outputs" / "v4_0" / "R2" / "sou_partial"
OUT.mkdir(parents=True, exist_ok=True)
LOG = OUT / "run.log"


def log(message: str) -> None:
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {message}"
    print(line, flush=True)
    with LOG.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


class CountedSOU:
    def __init__(self) -> None:
        self.calls = 0
        self.size_histogram: Counter[int] = Counter()
        self.compute_seconds = 0.0

    def __call__(self, selection, S_list=None, alpha=None, d=None):
        array = np.asarray(selection)
        size = int(array.sum()) if array.dtype == bool else len(array)
        started = time.perf_counter()
        result = U_sou(array, S_list, alpha, d)
        self.compute_seconds += time.perf_counter() - started
        self.calls += 1
        self.size_histogram[size] += 1
        return result


def evaluate_group_curves(
    estimates: np.ndarray,
    groups: list[list[int]],
    truths: list[float],
) -> tuple[list[float], list[float]]:
    aucc = []
    final_are = []
    for group, truth in zip(groups, truths):
        curve = estimates[group].sum(axis=0)
        relative = np.abs(curve - truth) / abs(truth)
        aucc.append(float(relative.mean()))
        final_are.append(float(relative[-1]))
    return aucc, final_are


def main() -> None:
    if LOG.exists():
        LOG.unlink()
    n = 64
    d = n**2
    neval = 20_000
    nsave = 100
    log("official SOU n=64 one-replication partial reproduction started")

    S_list, alpha = generate_sou_game(n, d, seed=42)
    truth = sv_sou_true(n, S_list, alpha)
    groups = [[index for index in range(n) if index % 4 == group] for group in range(4)]
    group_truth = [float(truth[group].sum()) for group in groups]
    efficiency_gap = float(truth.sum() - (U_sou(np.arange(n), S_list, alpha, d) - U_sou(np.array([]), S_list, alpha, d)))
    if abs(efficiency_gap) >= 1e-12:
        raise AssertionError(f"SOU analytic truth efficiency mismatch: {efficiency_gap}")

    arrays: dict[str, np.ndarray] = {"sv_true": truth}
    results = {}

    counted = CountedSOU()
    started = time.perf_counter()
    fgsv_curves = np.zeros((4, nsave), dtype=float)
    for index, group in enumerate(groups):
        fgsv_curves[index] = FGSV(
            counted, n, S_list, alpha, d, group, neval // 4, nsave, thres=10
        )
    elapsed = time.perf_counter() - started
    fgsv_relative = np.abs(fgsv_curves - np.asarray(group_truth)[:, None]) / np.abs(
        np.asarray(group_truth)[:, None]
    )
    arrays["fgsv_group_curves"] = fgsv_curves
    results["fgsv"] = {
        "aucc": fgsv_relative.mean(axis=1).tolist(),
        "final_are": fgsv_relative[:, -1].tolist(),
        "utility_calls": counted.calls,
        "runtime_seconds": elapsed,
        "utility_compute_seconds": counted.compute_seconds,
        "sampled_coalition_sizes": {str(k): v for k, v in sorted(counted.size_histogram.items())},
        "budget_argument": neval // 4,
        "number_of_groups": 4,
    }
    log(f"fgsv completed in {elapsed:.3f}s calls={counted.calls}")

    methods = {
        "permutation": permutation,
        "group_testing": group_testing,
        "complement": complement,
        "one_for_all": one_for_all,
        "kernel_shap": kernel_shap,
        "unbiased_kernel_shap": unbiased_kernel_shap,
        "leverage_shap": leverage_shap,
    }
    for name, function in methods.items():
        counted = CountedSOU()
        started = time.perf_counter()
        estimates = function(counted, n, S_list, alpha, d, neval, nsave)
        elapsed = time.perf_counter() - started
        aucc, final_are = evaluate_group_curves(estimates, groups, group_truth)
        arrays[f"{name}_individual_curves"] = estimates
        results[name] = {
            "aucc": aucc,
            "final_are": final_are,
            "utility_calls": counted.calls,
            "runtime_seconds": elapsed,
            "utility_compute_seconds": counted.compute_seconds,
            "sampled_coalition_sizes": {
                str(k): v for k, v in sorted(counted.size_histogram.items())
            },
            "all_estimates_zero": bool(np.all(estimates == 0)),
        }
        log(f"{name} completed in {elapsed:.3f}s calls={counted.calls}")

    np.savez_compressed(OUT / "curves.npz", **arrays)
    summary = {
        "status": "PARTIAL",
        "scope": "official SOU target, n=64, one replication; n=128/256 and 30 replications not run",
        "official_source_modified": False,
        "archive_sha256": "763C9CAD2689F87B5E7A891CEA4C3707AEFC72D186EDF97AB53BD3EB879E9FB0",
        "source_hashes": {
            path.name: sha256(path)
            for path in sorted(OFFICIAL.glob("*.py"))
        },
        "parameters": {
            "n": n,
            "d": d,
            "groups": groups,
            "neval_argument": neval,
            "nsave": nsave,
            "seed": 42,
            "threshold": 10,
        },
        "analytic_truth": {
            "group_values": group_truth,
            "individual_sum": float(truth.sum()),
            "efficiency_gap": efficiency_gap,
        },
        "methods": results,
        "known_code_observations": {
            "group_testing_save_target": (
                "The code computes s_hat but stores sv_hat * Z; sv_hat is never updated, "
                "so saved estimates are all zero."
            ),
            "permutation_budget": (
                "The loop completes whole permutations and may exceed 20,000 calls; "
                "the appendix says the last permutation stops exactly at the budget."
            ),
            "one_for_all_budget": (
                "The internal num_eval excludes 2n+2 deterministic calls, so actual calls exceed the argument."
            ),
            "kernel_family_budget": (
                "Empty/full utility calls are not included in internal num_eval; actual calls are reported by the wrapper."
            ),
        },
    }
    (OUT / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    log("partial SOU evidence run completed")


if __name__ == "__main__":
    main()
