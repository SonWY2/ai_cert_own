"""Offline paired-evaluation CLI; never executes target code or submits model data."""

import argparse
import json
import os
import sys
from pathlib import Path

from modules.evaluation.paired import evaluate
from modules.evaluation.head_to_head import evaluate as evaluate_head_to_head


def _unique(pairs):
    result = {}
    for name, value in pairs:
        if name in result:
            raise ValueError(f"Duplicate JSON key: {name}")
        result[name] = value
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description="Evaluate evaluator-sealed frozen final results")
    parser.add_argument("input", type=Path, help="One evaluator-owned JSON evidence bundle")
    args = parser.parse_args(argv)
    try:
        key = bytes.fromhex(os.environ["PAIRED_EVALUATION_KEY"])
        with args.input.open("r", encoding="utf-8") as stream:
            document = json.load(stream, object_pairs_hook=_unique,
                                 parse_constant=lambda value: (_ for _ in ()).throw(ValueError(f"Invalid JSON number: {value}")))
        protocol = document.get("protocol") if isinstance(document, dict) else None
        if isinstance(protocol, dict) and protocol.get("version") == "evaluation-protocol-v2":
            report = evaluate_head_to_head(document, key)
        else:
            report = evaluate(document, key)
    except (OSError, KeyError, ValueError, TypeError, OverflowError) as error:
        print(f"Evaluation rejected: {error}", file=sys.stderr)
        return 1
    print(json.dumps(report, ensure_ascii=False, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
