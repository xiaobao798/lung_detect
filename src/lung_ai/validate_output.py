from __future__ import annotations

import argparse
from pathlib import Path

from .dataset import discover_studies
from .writer import validate_result_set


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate one competition predicate directory")
    parser.add_argument("dataset_path", type=Path)
    parser.add_argument("predicate_path", type=Path)
    args = parser.parse_args()
    studies = discover_studies(args.dataset_path)
    validate_result_set(args.predicate_path, studies)
    print(f"validated {len(studies)} studies")


if __name__ == "__main__":
    main()
