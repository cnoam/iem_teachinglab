#!/usr/bin/env python3
"""Parse the students' public-key CSV and emit keys/<group_NN>.pub files.

The CSV (exported from a Google Sheet) looks like:

    Group ID (e.g. group06),Public Key,[optional] your name,...
    ,,,...
    group01,ssh-ed25519 AAAA... group01-deploy,Alice,...

Each data row carries a group id like ``group01`` and an SSH public key.
Terraform names teams ``group_NN`` (see main.tf), and deploy-keys.yml looks
up ``keys/<group_name>.pub``, so we normalize ``group01`` -> ``group_01``
and write the key there.

Usage:
    python scripts/parse_student_keys.py [CSV] [--keys-dir keys] [--dry-run]
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path

# Default location students upload to.
DEFAULT_CSV = Path.home() / "Downloads" / "keys_for_project(גיליון1).csv"

GROUP_RE = re.compile(r"^\s*group[_\-\s]?0*(\d+)\s*$", re.IGNORECASE)
VALID_KEY_TYPES = (
    "ssh-ed25519",
    "ssh-rsa",
    "ssh-ed25519-sk",
    "sk-ssh-ed25519@openssh.com",
    "ecdsa-sha2-nistp256",
    "ecdsa-sha2-nistp384",
    "ecdsa-sha2-nistp521",
    "sk-ecdsa-sha2-nistp256@openssh.com",
)


def normalize_group(raw: str) -> str | None:
    """`group01`, `group_1`, `Group 6` -> `group_06`. None if not a group id."""
    m = GROUP_RE.match(raw or "")
    if not m:
        return None
    return f"group_{int(m.group(1)):02d}"


def validate_key(raw: str) -> tuple[bool, str]:
    """Return (ok, cleaned_key). Cleaned key is type + base64 + optional comment."""
    key = (raw or "").strip()
    parts = key.split()
    if len(parts) < 2:
        return False, key
    if parts[0] not in VALID_KEY_TYPES:
        return False, key
    # base64 blob should be non-trivial
    if len(parts[1]) < 40:
        return False, key
    return True, key


def parse_csv(csv_path: Path) -> tuple[dict[str, str], list[str]]:
    """Return (group -> key, warnings)."""
    keys: dict[str, str] = {}
    warnings: list[str] = []
    with csv_path.open(newline="", encoding="utf-8-sig") as fh:
        for lineno, row in enumerate(csv.reader(fh), start=1):
            if not row:
                continue
            group = normalize_group(row[0])
            if group is None:
                continue  # header / blank / junk row
            raw_key = row[1] if len(row) > 1 else ""
            ok, key = validate_key(raw_key)
            if not ok:
                warnings.append(f"line {lineno}: {group}: invalid/empty key, skipped")
                continue
            if group in keys:
                warnings.append(
                    f"line {lineno}: {group}: duplicate row, overwriting earlier key"
                )
            keys[group] = key
    return keys, warnings


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv", nargs="?", type=Path, default=DEFAULT_CSV,
                    help=f"input CSV (default: {DEFAULT_CSV})")
    ap.add_argument("--keys-dir", type=Path,
                    default=Path(__file__).resolve().parent.parent / "keys",
                    help="output directory for <group>.pub files")
    ap.add_argument("--dry-run", action="store_true",
                    help="print what would be written without touching files")
    args = ap.parse_args()

    if not args.csv.exists():
        print(f"error: CSV not found: {args.csv}", file=sys.stderr)
        return 1

    keys, warnings = parse_csv(args.csv)

    for w in warnings:
        print(f"WARN  {w}", file=sys.stderr)

    if not keys:
        print("error: no valid keys found", file=sys.stderr)
        return 1

    args.keys_dir.mkdir(parents=True, exist_ok=True)
    for group, key in sorted(keys.items()):
        out = args.keys_dir / f"{group}.pub"
        if args.dry_run:
            print(f"[dry-run] would write {out}")
        else:
            out.write_text(key + "\n", encoding="utf-8")
            print(f"wrote {out}")

    print(f"\n{len(keys)} key(s) processed"
          + (f", {len(warnings)} warning(s)" if warnings else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
