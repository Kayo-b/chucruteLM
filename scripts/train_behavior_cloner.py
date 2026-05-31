#!/usr/bin/env python3

from __future__ import annotations

import argparse
import logging
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from chucrutelm.actions import ActionSpace
from chucrutelm.config import GridSize, ModelConfig, TrainingConfig
from chucrutelm.model import AsciiGridPolicyModel, AsciiGridTokenizer
from chucrutelm.profiles import build_profile, default_action_names
from chucrutelm.training import (
    BehaviorCloningDataset,
    BehaviorCloningTrainer,
    recorded_action_names,
    split_dataset,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Train a compact ASCII-grid policy model.")
    parser.add_argument("--data", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--profile-name", default="tibia")
    parser.add_argument("--actions")
    parser.add_argument("--grid-width", type=int, default=80)
    parser.add_argument("--grid-height", type=int, default=60)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--epochs", type=int, default=5)
    parser.add_argument("--learning-rate", type=float, default=3e-4)
    parser.add_argument("--eval-split", type=float, default=0.1)
    parser.add_argument("-v", "--verbose", action="store_true")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    manifest_path = args.data / "manifest.jsonl"
    configured_action_names = (
        [name.strip() for name in args.actions.split(",") if name.strip()]
        if args.actions is not None
        else default_action_names(args.profile_name)
    )
    profile = build_profile(args.profile_name, action_names=configured_action_names)
    action_names = (
        configured_action_names
        if args.actions is not None
        else recorded_action_names(
            manifest_path,
            preferred_order=configured_action_names,
            profile=profile,
        )
    )
    if not action_names:
        raise SystemExit(f"No labeled actions were found in {manifest_path}")
    action_space = ActionSpace.from_names(action_names)
    tokenizer = AsciiGridTokenizer()
    dataset = BehaviorCloningDataset(
        manifest_path=manifest_path,
        tokenizer=tokenizer,
        action_space=action_space,
        grid_size=GridSize(args.grid_width, args.grid_height),
        profile=profile,
    )
    train_dataset, eval_dataset = split_dataset(dataset, eval_ratio=args.eval_split, seed=42)
    model_config = ModelConfig(
        grid_size=GridSize(args.grid_width, args.grid_height),
        vocab_size=len(tokenizer.charset),
        num_actions=len(action_space),
    )
    model = AsciiGridPolicyModel(model_config)
    trainer = BehaviorCloningTrainer(
        model=model,
        action_space=action_space,
        config=TrainingConfig(
            data_path=args.data,
            output_dir=args.output,
            batch_size=args.batch_size,
            epochs=args.epochs,
            learning_rate=args.learning_rate,
            eval_split=args.eval_split,
        ),
    )
    best_accuracy = trainer.train(train_dataset, eval_dataset)
    trainer.save_metadata(model_config)
    print(f"Best eval accuracy: {best_accuracy:.2%}")
    print(f"Parameter count: {model.parameter_count():,}")


if __name__ == "__main__":
    main()
