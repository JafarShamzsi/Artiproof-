"""Read one explicit synthetic JSON file; print metadata proposals to stdout."""

import argparse
import json
from pathlib import Path
import sys

from . import AuditInputError, MAX_BYTES, classify, load_synthetic


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        # argparse's default error repeats unknown arguments (possibly secrets).
        self.exit(2, "Invalid arguments; use --help for synthetic offline usage.\n")


def main():
    parser = _Parser(description="Synthetic metadata only; no DB, apply or production mode.",
                     allow_abbrev=False)
    parser.add_argument("--synthetic-input", required=True,
                        help="Explicit synthetic .json fixture (never production exports).")
    args = parser.parse_args()
    try:
        raw_path = args.synthetic_input
        # Windows treats both separators alike, including mixed UNC/device
        # prefixes. Normalize strings only, before constructing/probing a path.
        lexical_path = raw_path.replace("\\", "/")
        if raw_path.startswith("\\") or lexical_path.startswith("//") or "://" in lexical_path:
            raise AuditInputError()
        path = Path(raw_path)
        if path.suffix.lower() != ".json" or path.is_symlink() or not path.is_file():
            raise AuditInputError()
        with path.open("rb") as handle:
            raw = handle.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            raise AuditInputError()
        result = classify(load_synthetic(raw.decode("utf-8")))
    except (AuditInputError, OSError, UnicodeError, ValueError):
        print("Invalid synthetic metadata input.", file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
