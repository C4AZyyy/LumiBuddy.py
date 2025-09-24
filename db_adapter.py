с# db_adapter.py
import os
import json
from typing import Optional, Dict, Any, Iterable

DB_URL = os.getenv("DATABASE_URL", "").strip()

# --- Лёгкий файловый стор ---
class FileStore:
    def __init__(self, path: str = None):
        self.path = path or os.getenv("STATE_FILE", "users.json")

    def is_db(self) -> bool:
        return False

    def init_schema(self) -> None:
        pass  # для файла не нужно

    def load_users_from_file(self) -> Iterable[Dict[str, Any]]:
        if not os.path.exists(self.path):
            return []
        with open(self.path, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
            except Exception:
                data = {}
        # ожидаем формат {chat_id: {...}}
        for k, v in data.items():
            try:
                chat_id = int(k)
            except Exception:
                continue
            row = {"chat_id": chat_id, **(v or {})}
            yield row

# --- Postgres стор ---
class DbStore:
    def __init__(self, url: str):
        import psycopg
        self.psycopg = psycopg
        self.url = url

    def is_db(self) -> bool:
        return True

    def init_schema(self) -> None:
        psycopg = self.psycopg
        with psycopg.connect(self.url) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    chat_id BIGINT PRIMARY KEY
                );
                """)
                cur.execute("""
                ALTER TABLE users
                  ADD COLUMN IF NOT EXISTS language                   TEXT,
                  ADD COLUMN IF NOT EXISTS policy_shown               BOOLEAN     DEFAULT FALSE,
                  ADD COLUMN IF NOT EXISTS accepted_at                TIMESTAMPTZ,
                  ADD COLUMN IF NOT EXISTS free_used                  INTEGER     DEFAULT 0,
                  ADD COLUMN IF NOT EXISTS premium_plan               TEXT,
                  ADD COLUMN IF NOT EXISTS premium_until              TIMESTAMPTZ,
                  ADD COLUMN IF NOT EXISTS permanent_plan             TEXT,
                  ADD COLUMN IF NOT EXISTS news_opt_out               BOOLEAN     DEFAULT FALSE,
                  ADD COLUMN IF NOT EXISTS news_opted_at              TIMESTAMPTZ,
                  ADD COLUMN IF NOT EXISTS history                    JSONB       DEFAULT '[]'::jsonb,
                  ADD COLUMN IF NOT EXISTS offer_prompted             BOOLEAN     NOT NULL DEFAULT FALSE,
                  ADD COLUMN IF NOT EXISTS offer_remind_at            TIMESTAMPTZ NULL,
                  ADD COLUMN IF NOT EXISTS abuse_strikes              INTEGER     NOT NULL DEFAULT 0,
                  ADD COLUMN IF NOT EXISTS lyrics_expected            BOOLEAN     NOT NULL DEFAULT FALSE,
                  ADD COLUMN IF NOT EXISTS last_seen_at               TIMESTAMPTZ NULL,
                  ADD COLUMN IF NOT EXISTS last_username              TEXT        NULL,
                  ADD COLUMN IF NOT EXISTS last_first_name            TEXT        NULL,
                  ADD COLUMN IF NOT EXISTS last_last_name             TEXT        NULL,
                  ADD COLUMN IF NOT EXISTS last_full_name             TEXT        NULL,
                  ADD COLUMN IF NOT EXISTS last_vent_at               TIMESTAMPTZ NULL,
                  ADD COLUMN IF NOT EXISTS last_vent_note             TEXT        NULL,
                  ADD COLUMN IF NOT EXISTS premium_source             TEXT        NULL,
                  ADD COLUMN IF NOT EXISTS premium_started_at         TIMESTAMPTZ NULL,
                  ADD COLUMN IF NOT EXISTS premium_payment_method     TEXT        NULL,
                  ADD COLUMN IF NOT EXISTS premium_payment_reference  TEXT        NULL
                ;
                """)
            conn.commit()

    def bulk_upsert_users(self, rows: Iterable[Dict[str, Any]]) -> int:
        # простой upsert: вставка с on conflict
        psycopg = self.psycopg
        count = 0
        with psycopg.connect(self.url) as conn:
            with conn.cursor() as cur:
                for r in rows:
                    chat_id = int(r.get("chat_id"))
                    # удаляем лишние ключи, которых нет в таблице — можно оставить,
                    # если ты уверен в колонках
                    cols = [k for k in r.keys()]
                    vals = [r[k] for k in cols]
                    placeholders = ", ".join(["%s"] * len(vals))
                    columns = ", ".join(cols)
                    updates = ", ".join([f"{k}=EXCLUDED.{k}" for k in cols if k != "chat_id"])
                    cur.execute(
                        f"INSERT INTO users ({columns}) VALUES ({placeholders}) "
                        f"ON CONFLICT (chat_id) DO UPDATE SET {updates};",
                        vals
                    )
                    count += 1
            conn.commit()
        return count

# --- Фабрики/утилиты ---
def get_store():
    if DB_URL:
        return DbStore(DB_URL)
    return FileStore()

store = get_store()

def db_init():
    store.init_schema()

def auto_migrate_file_to_db():
    # если мы в БД — перетащим users.json
    if isinstance(store, DbStore):
        file_store = FileStore()
        rows = list(file_store.load_users_from_file())
        if rows:
            inserted = store.bulk_upsert_users(rows)
            print(f">>> migrated {inserted} users from file to DB")
