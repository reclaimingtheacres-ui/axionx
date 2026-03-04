import sqlite3
import os

DB_FILE = os.getenv("AXIONX_DB_PATH", "axion.db")

conn = sqlite3.connect(DB_FILE)
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS login_throttle (
  key TEXT PRIMARY KEY,
  fail_count INTEGER NOT NULL DEFAULT 0,
  locked_until TEXT,
  updated_at TEXT NOT NULL DEFAULT (datetime('now'))
)
""")

conn.commit()
conn.close()
print("OK: login_throttle table ready")
