#!/usr/bin/env python3

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect a recorded manifest.")
    parser.add_argument("--data", required=True, type=Path)
    args = parser.parse_args()

    manifest_path = args.data / "manifest.jsonl"
    metadata_path = args.data / "metadata.json"
    action_counts: Counter[str] = Counter()
    feature_names: set[str] = set()
    samples = 0

    with manifest_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            payload = json.loads(line)
            action_name = payload["action"]["action_name"] or "unlabeled"
            action_counts[action_name] += 1
            feature_names.update(payload["observation"]["numeric_features"].keys())
            samples += 1

    print(f"Samples: {samples}")
    print(f"Feature names: {sorted(feature_names)}")
    print("Action distribution:")
    for action_name, count in sorted(action_counts.items()):
        print(f"  {action_name}: {count}")
    if metadata_path.exists():
        print("\nMetadata:")
        print(metadata_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
