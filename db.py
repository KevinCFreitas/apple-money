import os
import sqlite3
from datetime import datetime, timedelta

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("DB_PATH", os.path.join(BASE_DIR, "market.db"))

DEFAULT_ASSETS = [
    {
        "symbol": "AAPL34.SA",
        "name": "Apple Inc. BDR",
        "url": "https://finance.yahoo.com/quote/AAPL34.SA",
        "currency": "R$",
        "provider": "yahoo",
    }
]


def now_iso():
    return datetime.now().isoformat(timespec="seconds")


def get_conn():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    with get_conn() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS assets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL UNIQUE COLLATE NOCASE,
                name TEXT NOT NULL,
                url TEXT NOT NULL,
                currency TEXT NOT NULL DEFAULT 'R$',
                provider TEXT NOT NULL DEFAULT 'yahoo',
                alert_above REAL,
                alert_below REAL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS prices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                asset_id INTEGER NOT NULL REFERENCES assets(id) ON DELETE CASCADE,
                price REAL NOT NULL,
                captured_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_prices_asset_time
                ON prices(asset_id, captured_at);

            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                asset_id INTEGER REFERENCES assets(id) ON DELETE CASCADE,
                symbol TEXT NOT NULL,
                kind TEXT NOT NULL,
                message TEXT NOT NULL,
                price REAL NOT NULL,
                created_at TEXT NOT NULL
            );
            """
        )

        columns = {row["name"] for row in conn.execute("PRAGMA table_info(assets)")}
        if "provider" not in columns:
            conn.execute(
                "ALTER TABLE assets ADD COLUMN provider TEXT NOT NULL DEFAULT 'yahoo'"
            )

    if not list_assets():
        for asset in DEFAULT_ASSETS:
            add_asset(**asset, alert_above=None, alert_below=None)


def list_assets():
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM assets ORDER BY symbol").fetchall()
    return [dict(row) for row in rows]


def get_asset(asset_id):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM assets WHERE id = ?", (asset_id,)).fetchone()
    return dict(row) if row else None


def get_asset_by_symbol(symbol):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM assets WHERE symbol = ? COLLATE NOCASE", (symbol,)
        ).fetchone()
    return dict(row) if row else None


def add_asset(
    symbol,
    name,
    url="",
    currency="R$",
    provider="yahoo",
    alert_above=None,
    alert_below=None,
):
    with get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO assets
                (symbol, name, url, currency, provider, alert_above, alert_below, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (symbol, name, url, currency, provider, alert_above, alert_below, now_iso()),
        )
        asset_id = cur.lastrowid
    return get_asset(asset_id)


def update_asset(asset_id, **fields):
    allowed = {"name", "url", "currency", "alert_above", "alert_below"}
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return get_asset(asset_id)
    columns = ", ".join(f"{key} = ?" for key in updates)
    values = list(updates.values()) + [asset_id]
    with get_conn() as conn:
        conn.execute(f"UPDATE assets SET {columns} WHERE id = ?", values)
    return get_asset(asset_id)


def delete_asset(asset_id):
    with get_conn() as conn:
        conn.execute("DELETE FROM assets WHERE id = ?", (asset_id,))


def add_price(asset_id, price, captured_at=None):
    captured_at = captured_at or now_iso()
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO prices (asset_id, price, captured_at) VALUES (?, ?, ?)",
            (asset_id, price, captured_at),
        )
    return {"price": price, "captured_at": captured_at}


def latest_price(asset_id):
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT price, captured_at FROM prices
            WHERE asset_id = ?
            ORDER BY captured_at DESC, id DESC
            LIMIT 1
            """,
            (asset_id,),
        ).fetchone()
    return dict(row) if row else None


def previous_price(asset_id):
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT price, captured_at FROM prices
            WHERE asset_id = ?
            ORDER BY captured_at DESC, id DESC
            LIMIT 1 OFFSET 1
            """,
            (asset_id,),
        ).fetchone()
    return dict(row) if row else None


def history(asset_id, minutes=None, limit=2000):
    query = "SELECT price, captured_at FROM prices WHERE asset_id = ?"
    params = [asset_id]
    if minutes:
        cutoff = (datetime.now() - timedelta(minutes=int(minutes))).isoformat(
            timespec="seconds"
        )
        query += " AND captured_at >= ?"
        params.append(cutoff)
    query += " ORDER BY captured_at ASC, id ASC LIMIT ?"
    params.append(int(limit))
    with get_conn() as conn:
        rows = conn.execute(query, params).fetchall()
    return [dict(row) for row in rows]


def add_alert(asset_id, symbol, kind, message, price, created_at=None):
    created_at = created_at or now_iso()
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO alerts (asset_id, symbol, kind, message, price, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (asset_id, symbol, kind, message, price, created_at),
        )
    return {
        "asset_id": asset_id,
        "symbol": symbol,
        "kind": kind,
        "message": message,
        "price": price,
        "created_at": created_at,
    }


def recent_alerts(limit=100):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM alerts ORDER BY id DESC LIMIT ?", (int(limit),)
        ).fetchall()
    return [dict(row) for row in rows]


def assets_summary():
    assets = list_assets()
    summary = []
    for asset in assets:
        latest = latest_price(asset["id"])
        previous = previous_price(asset["id"])
        change = None
        change_pct = None
        if latest and previous and previous["price"]:
            change = round(latest["price"] - previous["price"], 4)
            change_pct = round((change / previous["price"]) * 100, 4)
        summary.append(
            {
                **asset,
                "price": latest["price"] if latest else None,
                "previous_price": previous["price"] if previous else None,
                "captured_at": latest["captured_at"] if latest else None,
                "change": change,
                "change_pct": change_pct,
            }
        )
    return summary
