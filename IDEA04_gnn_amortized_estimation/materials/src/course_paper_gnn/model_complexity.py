from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import torch

from .model import build_model


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Report neural model parameter counts")
    parser.add_argument(
        "--model",
        action="append",
        required=True,
        help="LABEL=PATH_TO_CHECKPOINT; may be repeated",
    )
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.output.exists():
        raise FileExistsError(f"Refusing to overwrite: {args.output}")
    args.output.mkdir(parents=True)
    rows: list[dict] = []
    for specification in args.model:
        label, path_text = specification.split("=", 1)
        checkpoint = torch.load(
            Path(path_text),
            map_location="cpu",
            weights_only=False,
        )
        training_args = checkpoint["args"]
        model = build_model(
            checkpoint["model_name"],
            hidden_dim=int(training_args["hidden_dim"]),
            num_layers=int(training_args["num_layers"]),
            dropout=float(training_args["dropout"]),
            use_edges=not bool(training_args.get("no_edges", False)),
            use_anchor=not bool(training_args["no_anchor"]),
            use_zero_mask=not bool(training_args["no_zero_mask"]),
            use_simplex=not bool(training_args["no_simplex"]),
        )
        parameters = sum(parameter.numel() for parameter in model.parameters())
        trainable = sum(
            parameter.numel()
            for parameter in model.parameters()
            if parameter.requires_grad
        )
        rows.append(
            {
                "label": label,
                "checkpoint": str(path_text),
                "model_name": checkpoint["model_name"],
                "parameters": parameters,
                "trainable_parameters": trainable,
                "hidden_dim": int(training_args["hidden_dim"]),
                "num_layers": int(training_args["num_layers"]),
            }
        )
    with (args.output / "model_complexity.csv").open(
        "w", encoding="utf-8", newline=""
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    (args.output / "model_complexity.json").write_text(
        json.dumps(rows, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(json.dumps(rows, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
