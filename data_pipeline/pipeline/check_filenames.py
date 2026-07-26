"""Check every filename under datasets/raw/ against the 255-byte filesystem limit.

Thai filenames are multi-byte UTF-8 (3 bytes/char) so byte length blows past
the limit well before character count looks alarming. Long names break git,
Typhoon OCR upload, and normalize/chunk downstream with unclear errors.

Run from the repo root:

    python -m data_pipeline.pipeline.check_filenames

Exit code 0 if all filenames pass, 1 if any exceed the limit.
"""
from __future__ import annotations

import sys

from data_pipeline.pipeline.triage import INPUT_DIR, iter_sources

NAME_BYTE_LIMIT = 255


def main() -> int:
    files = list(iter_sources(INPUT_DIR))
    if not files:
        print(f"No source files found under {INPUT_DIR}/")
        return 0

    checked = [(p, len(p.name.encode("utf-8")), len(p.name)) for p in files]
    violations = [c for c in checked if c[1] > NAME_BYTE_LIMIT]
    max_bytes = max(c[1] for c in checked)

    if not violations:
        print(f"All under {NAME_BYTE_LIMIT}-byte limit (max {max_bytes})")
        return 0

    print(f"{len(violations)} file(s) exceed {NAME_BYTE_LIMIT}-byte limit:")
    for path, nbytes, nchars in sorted(violations, key=lambda c: -c[1]):
        print(f"  {nbytes} bytes ({nchars} chars)  {path.relative_to(INPUT_DIR.parent)}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
