"""
One-time backfill: reads the local spy_1m.db (SQLite, retired by this
migration) and upserts its raw OHLCV rows into the new Supabase `bars`
table, so the real accumulated history isn't lost when the pipeline
switches over.

Only raw OHLCV is migrated — `features` is left NULL for these rows.
The next `smaug_pipeline.py` run recomputes features over the whole
retained window and fills them in (see upsert_features_supabase there),
so this script doesn't need to reimplement compute_features().

Run once, manually, with SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY set
in the environment — never commit those values, and never run this
against production without first checking the row count/date range
below look right.

Usage:
  export SUPABASE_URL=...
  export SUPABASE_SERVICE_ROLE_KEY=...
  python scripts/migrate_bars_to_supabase.py [--db path/to/spy_1m.db]
"""

import argparse
import sqlite3
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from smaug_pipeline import upsert_bars_supabase  # noqa: E402


def load_sqlite_bars(db_path):
    conn = sqlite3.connect(db_path)
    df = pd.read_sql("SELECT * FROM bars ORDER BY ts", conn)
    conn.close()
    df["ts"] = pd.to_datetime(df["ts"], utc=False)
    if df["ts"].dt.tz is None:
        df["ts"] = df["ts"].dt.tz_localize(
            "America/New_York", ambiguous="NaT", nonexistent="NaT"
        )
    df = df.dropna(subset=["ts"]).set_index("ts")
    return df[["open", "high", "low", "close", "volume"]]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="spy_1m.db")
    args = ap.parse_args()

    df = load_sqlite_bars(args.db)
    if df.empty:
        print("No rows found in local DB — nothing to migrate.")
        return

    print(f"Local DB: {len(df)} rows, {df.index.min()} .. {df.index.max()}")
    n = upsert_bars_supabase(df)
    print(f"Upserted {n} rows into Supabase `bars`.")
    print(
        "Note: features are NULL for these rows until the next "
        "smaug_pipeline.py run recomputes and fills them in."
    )


if __name__ == "__main__":
    main()
