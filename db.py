import sqlite3, time
from .config import DB_PATH

def db():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")
    return c

def init():
    with db() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS users(
          username TEXT PRIMARY KEY, uuid TEXT NOT NULL, token TEXT UNIQUE NOT NULL,
          total_bytes INTEGER NOT NULL, used_bytes INTEGER NOT NULL DEFAULT 0,
          expire_ts INTEGER NOT NULL, enabled INTEGER NOT NULL DEFAULT 1, created_ts INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS usage_daily(
          username TEXT, day TEXT, bytes INTEGER NOT NULL DEFAULT 0, PRIMARY KEY(username, day));
        """)

def is_active(u):
    return bool(u["enabled"]) and u["used_bytes"] < u["total_bytes"] and u["expire_ts"] > time.time()
