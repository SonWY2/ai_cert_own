"""Compare preregistered development evidence offline; never run a target or model."""

import argparse
import json
import sys
from pathlib import Path

from modules.evaluation.development import evaluate


def _unique(pairs):
    result = {}
    for name, value in pairs:
        if name in result:
            raise ValueError(f"Duplicate JSON key: {name}")
        result[name] = value
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="One preregistered offline JSON comparison")
    args = parser.parse_args(argv)
    try:
        with args.input.open("r", encoding="utf-8") as stream:
            document = json.load(stream, object_pairs_hook=_unique,
                                 parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))
        result = evaluate(document)
    except (OSError, ValueError, TypeError, KeyError, IndexError, OverflowError) as error:
        print(f"Development comparison rejected: {error}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
