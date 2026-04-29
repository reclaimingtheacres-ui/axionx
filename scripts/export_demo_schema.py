#!/usr/bin/env python3
"""
Export the AxionX production schema to scripts/demo_schema.sql.

Run this whenever the production database schema changes to keep the demo
seed script in sync. The generated file is committed to version control.

Usage:
    python3 scripts/export_demo_schema.py [--db axion.db]
"""
import argparse
import os
import sqlite3
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
_OUT  = os.path.join(_HERE, "demo_schema.sql")


def main():
    ap = argparse.ArgumentParser(description="Export production schema to demo_schema.sql")
    ap.add_argument("--db", default=os.path.join(_ROOT, "axion.db"),
                    help="Path to source SQLite database (default: axion.db)")
    ap.add_argument("--out", default=_OUT,
                    help=f"Output file (default: {_OUT})")
    args = ap.parse_args()

    if not os.path.exists(args.db):
        print(f"[ERROR] Database not found: {args.db}", file=sys.stderr)
        sys.exit(1)

    con = sqlite3.connect(args.db)
    rows = con.execute(
        "SELECT sql FROM sqlite_master WHERE sql IS NOT NULL ORDER BY type DESC, name"
    ).fetchall()
    con.close()

    lines = [
        "-- Auto-generated demo schema — do not edit manually.",
        "-- Regenerate with:  python3 scripts/export_demo_schema.py",
        "",
    ]
    for (sql,) in rows:
        if sql:
            lines.append(sql.strip() + ";")
            lines.append("")

    with open(args.out, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))

    print(f"[OK] Exported {len(rows)} schema objects → {args.out}")


if __name__ == "__main__":
    main()
